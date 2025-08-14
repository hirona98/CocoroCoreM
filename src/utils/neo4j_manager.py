"""
CocoroCore2 Neo4j管理システム

組み込みNeo4jの起動・停止・接続管理
"""

import asyncio
import logging
import os
import platform
import signal
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class Neo4jManager:
    """組み込みNeo4j管理システム"""
    
    def __init__(self, config: Dict):
        """
        初期化
        
        Args:
            config: Neo4j設定辞書
        """
        self.config = config
        self.logger = logger
        self.process: Optional[subprocess.Popen] = None
        self.is_running = False
        self.startup_timeout = 120  # 2分
        
        # Neo4jディレクトリのパス
        self.base_dir = Path(__file__).parent.parent.parent  # CocoroCore2ディレクトリ
        self.neo4j_dir = self.base_dir / "neo4j"
        
        # プラットフォーム別の実行ファイルパス
        if platform.system() == "Windows":
            self.neo4j_executable = self.neo4j_dir / "bin" / "neo4j.bat"
        else:
            self.neo4j_executable = self.neo4j_dir / "bin" / "neo4j"
        
        # 設定から接続情報を取得
        self.uri = config.get("uri", "bolt://127.0.0.1:7687")
        self.web_port = config.get("web_port", 7474)
        self.embedded_enabled = config.get("embedded_enabled", True)
        
        # ポート番号を抽出
        if ":" in self.uri:
            self.bolt_port = int(self.uri.split(":")[-1])
        else:
            self.bolt_port = 7687
    
    async def start(self) -> bool:
        """
        Neo4jサービスを起動
        
        Returns:
            bool: 起動成功したかどうか
        """
        if not self.embedded_enabled:
            self.logger.info("組み込みNeo4jが無効になっています")
            return True
        
        if self.is_running:
            self.logger.info("Neo4jは既に起動しています")
            return True
        
        try:
            # Neo4j実行ファイルの存在確認
            if not self.neo4j_executable.exists():
                self.logger.error(f"Neo4j実行ファイルが見つかりません: {self.neo4j_executable}")
                return False
            
            # Neo4jプロセス起動
            self.logger.info(f"Neo4jを起動しています... (ポート: {self.bolt_port}, Web: {self.web_port})")
            
            # 環境変数設定
            env = os.environ.copy()
            env["NEO4J_HOME"] = str(self.neo4j_dir)
            env["NEO4J_CONF"] = str(self.neo4j_dir / "conf")
            
            # プロセス起動
            if platform.system() == "Windows":
                # Windowsの場合
                self.process = subprocess.Popen(
                    [str(self.neo4j_executable), "console"],
                    cwd=str(self.neo4j_dir),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                # Linux/WSLの場合
                self.process = subprocess.Popen(
                    [str(self.neo4j_executable), "console"],
                    cwd=str(self.neo4j_dir),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    preexec_fn=os.setsid
                )
            
            # 起動待ち
            if await self._wait_for_startup():
                self.is_running = True
                self.logger.info(f"Neo4j起動完了 (PID: {self.process.pid})")
                return True
            else:
                self.logger.error("Neo4jの起動タイムアウト")
                await self.stop()
                return False
                
        except Exception as e:
            self.logger.error(f"Neo4j起動エラー: {e}")
            await self.stop()
            return False
    
    async def _wait_for_startup(self) -> bool:
        """起動完了を待つ"""
        start_time = time.time()
        
        while time.time() - start_time < self.startup_timeout:
            if self.process and self.process.poll() is not None:
                # プロセスが終了している
                self.logger.error(f"Neo4jプロセスが異常終了しました (終了コード: {self.process.returncode})")
                return False
            
            # 接続テスト
            if await self._test_connection():
                return True
            
            await asyncio.sleep(2)
        
        return False
    
    async def _test_connection(self) -> bool:
        """接続テスト"""
        try:
            import httpx
            
            # Neo4j HTTP エンドポイントへの接続テスト
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"http://127.0.0.1:{self.web_port}")
                return response.status_code in [200, 401]  # 401は認証が必要だが接続は成功
                
        except Exception:
            return False
    
    async def stop(self):
        """Neo4jサービスを停止"""
        if not self.embedded_enabled:
            return
        
        if not self.process:
            self.logger.info("Neo4jプロセスが見つかりません")
            return
        
        try:
            self.logger.info("Neo4jを停止しています...")
            
            if platform.system() == "Windows":
                # WindowsでCTRL+Cシグナルを送信
                self.process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                # Linux/WSLでプロセスグループにSIGTERMを送信
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            
            # 優雅な終了を待つ
            try:
                self.process.wait(timeout=30)
                self.logger.info("Neo4jが正常に停止しました")
            except subprocess.TimeoutExpired:
                # 強制終了
                self.logger.warning("Neo4jの優雅な停止がタイムアウトしました。強制終了します")
                if platform.system() == "Windows":
                    self.process.terminate()
                else:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                self.process.wait(timeout=10)
                
        except Exception as e:
            self.logger.error(f"Neo4j停止エラー: {e}")
            # 最後の手段として強制終了を試行
            try:
                if self.process and self.process.poll() is None:
                    self.process.kill()
                    self.process.wait()
            except Exception:
                pass
        
        finally:
            self.process = None
            self.is_running = False
    
    async def health_check(self) -> Dict:
        """ヘルスチェック"""
        result = {
            "neo4j_enabled": self.embedded_enabled,
            "neo4j_running": False,
            "neo4j_process_alive": False,
            "neo4j_connection_ok": False,
            "neo4j_uri": self.uri,
            "neo4j_web_port": self.web_port
        }
        
        if not self.embedded_enabled:
            return result
        
        # プロセス生存確認
        if self.process and self.process.poll() is None:
            result["neo4j_process_alive"] = True
        
        # 接続確認
        if await self._test_connection():
            result["neo4j_connection_ok"] = True
            result["neo4j_running"] = True
        
        return result
    
    async def get_stats(self) -> Dict:
        """Neo4j統計情報取得"""
        try:
            if not self.embedded_enabled or not await self._test_connection():
                return {"error": "Neo4jに接続できません"}
            
            # 基本統計情報を返す
            return {
                "status": "running",
                "uri": self.uri,
                "web_port": self.web_port,
                "process_id": self.process.pid if self.process else None
            }
            
        except Exception as e:
            self.logger.error(f"Neo4j統計取得エラー: {e}")
            return {"error": str(e)}