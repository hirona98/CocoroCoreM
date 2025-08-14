"""
CocoroCore2 Neo4j管理システム

組み込みNeo4jの起動・停止・接続管理
"""

import asyncio
import logging
import os
import platform
import signal
import socket
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional

try:
    from neo4j import GraphDatabase
    NEO4J_DRIVER_AVAILABLE = True
except ImportError:
    NEO4J_DRIVER_AVAILABLE = False
    GraphDatabase = None

logger = logging.getLogger(__name__)


class Neo4jManager:
    """組み込みNeo4j管理システム"""
    
    def __init__(self, config: Dict):
        """初期化"""
        self.config = config
        self.logger = logger
        self.process: Optional[subprocess.Popen] = None
        self.is_running = False
        self.startup_timeout = 60  # 1分
        
        # Neo4jディレクトリのパス
        self.base_dir = Path(__file__).parent.parent.parent  # CocoroCore2ディレクトリ
        self.neo4j_dir = self.base_dir / "neo4j"
        
        # Neo4j実行ファイル
        self.neo4j_executable = self.neo4j_dir / "bin" / "neo4j.bat"
        
        # 接続設定
        self.uri = config.get("uri", "bolt://127.0.0.1:55603")
        self.web_port = config.get("web_port", 55606)
        self.embedded_enabled = config.get("embedded_enabled", True)
        
        # ポート番号を抽出
        if ":" in self.uri:
            self.bolt_port = int(self.uri.split(":")[-1])
        else:
            self.bolt_port = 7687
    
    def _reload_config(self) -> bool:
        """Setting.jsonから最新設定を再読み込み"""
        try:
            from core.config_manager import load_neo4j_config
            fresh_config = load_neo4j_config()
            
            # 最新の設定値を更新
            self.uri = fresh_config.get("uri", "bolt://127.0.0.1:55603")
            self.web_port = fresh_config.get("web_port", 55606)
            self.embedded_enabled = fresh_config.get("embedded_enabled", True)
            
            # ポート番号を抽出
            if ":" in self.uri:
                self.bolt_port = int(self.uri.split(":")[-1])
            else:
                self.bolt_port = 7687
                
            return True
            
        except Exception as e:
            self.logger.error(f"設定の再読み込みに失敗: {e}")
            return False
    
    def _update_neo4j_config(self) -> bool:
        """Neo4j設定ファイルを動的に更新"""
        try:
            config_path = self.neo4j_dir / "conf" / "neo4j.conf"
            if not config_path.exists():
                self.logger.error(f"Neo4j設定ファイルが見つかりません: {config_path}")
                return False
            
            # 現在の設定を読み込み
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 期待する設定値
            expected_bolt = f"server.bolt.listen_address=127.0.0.1:{self.bolt_port}"
            expected_http = f"server.http.listen_address=127.0.0.1:{self.web_port}"
            expected_http_enabled = "server.http.enabled=true"
            
            # 既に正しい設定の場合は更新をスキップ
            if (expected_bolt in content and 
                expected_http in content and 
                expected_http_enabled in content):
                return True
            
            # 設定を更新
            lines = content.splitlines()
            updated_lines = []
            
            for line in lines:
                line_stripped = line.strip()
                
                if line_stripped.startswith("server.bolt.listen_address"):
                    updated_lines.append(expected_bolt)
                elif line_stripped.startswith("server.http.enabled"):
                    updated_lines.append(expected_http_enabled)
                elif (line_stripped.startswith("#server.http.listen_address") or 
                      line_stripped.startswith("server.http.listen_address")):
                    updated_lines.append(expected_http)
                else:
                    updated_lines.append(line)
            
            # ファイルに書き戻し
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(updated_lines) + '\n')
            
            self.logger.info(f"Neo4j設定更新: Bolt={self.bolt_port}, HTTP={self.web_port}")
            return True
            
        except Exception as e:
            self.logger.error(f"Neo4j設定ファイル更新エラー: {e}")
            return False

    def _check_ports_available(self) -> bool:
        """Neo4j使用ポートの利用可能性を確認"""
        ports_to_check = [self.bolt_port, self.web_port]
        
        for port in ports_to_check:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(1)
                    result = sock.connect_ex(('localhost', port))
                    if result == 0:  # 接続成功 = ポート使用中
                        self.logger.error(f"ポート {port} は既に使用中です")
                        return False
            except Exception as e:
                self.logger.warning(f"ポート {port} の確認に失敗: {e}")
                # エラー時は起動を試行（ネットワーク設定などの問題の可能性）
        
        return True

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
            # 1. 最新のSetting.json設定を再読み込み
            if not self._reload_config():
                self.logger.error("Setting.jsonの再読み込みに失敗しました")
                return False
            
            # 2. Neo4j実行ファイルの存在確認
            if not self.neo4j_executable.exists():
                self.logger.error(f"Neo4j実行ファイルが見つかりません: {self.neo4j_executable}")
                return False
            
            # 3. Neo4j設定ファイル更新（最新の設定で）
            if not self._update_neo4j_config():
                self.logger.error("Neo4j設定ファイルの更新に失敗しました")
                return False

            # 4. ポート利用可能性確認
            if not self._check_ports_available():
                self.logger.error(f"Neo4j起動に必要なポート（Bolt: {self.bolt_port}, HTTP: {self.web_port}）が使用中です。他のアプリケーションまたは前回のNeo4jプロセスが残っている可能性があります。")
                return False

            # Neo4jプロセス起動
            self.logger.info(f"Neo4jを起動しています... (ポート: {self.bolt_port}, Web: {self.web_port})")
            
            # 環境変数設定
            env = os.environ.copy()
            java_home = str(self.base_dir / "jre")
            env["JAVA_HOME"] = java_home
            env["PATH"] = str(Path(java_home) / "bin") + os.pathsep + env.get("PATH", "")
            env["NEO4J_HOME"] = str(self.neo4j_dir)
            env["NEO4J_CONF"] = str(self.neo4j_dir / "conf")
            
            # Neo4j起動
            console_cmd = [str(self.neo4j_executable), "console"]
            
            self.process = subprocess.Popen(
                console_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(self.neo4j_dir),
                env=env,
                text=False,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
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
        """Neo4j接続テスト"""
        if not NEO4J_DRIVER_AVAILABLE:
            return False
            
        try:
            def _test_driver():
                test_driver = GraphDatabase.driver(self.uri, auth=None)
                with test_driver.session() as session:
                    result = session.run("RETURN 1 AS num")
                    record = result.single()
                    success = record["num"] == 1
                test_driver.close()
                return success

            return await asyncio.get_event_loop().run_in_executor(None, _test_driver)
                
        except Exception as e:
            self.logger.debug(f"Neo4j接続テスト失敗: {e}")
            return False
    
    async def stop(self):
        """Neo4jサービスを停止"""
        if not self.embedded_enabled:
            return
        
        if not self.process:
            self.logger.info("Neo4jプロセスが見つかりません")
            return
        
        self.logger.info("Neo4jを停止しています...")
        
        # Neo4j公式推奨：SIGTERM送信（Ctrl+C相当）
        if platform.system() == "Windows":
            self.process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            self.process.send_signal(signal.SIGTERM)
        
        # プロセス終了を待機（10秒タイムアウト）
        try:
            await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, self.process.wait),
                timeout=10
            )
            self.logger.info("Neo4j停止完了")
        except asyncio.TimeoutError:
            self.logger.warning("Neo4j停止タイムアウト")
            self.process.terminate()
        
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
            
            return {
                "status": "running",
                "uri": self.uri,
                "web_port": self.web_port,
                "process_id": self.process.pid if self.process else None,
                "embedded_enabled": self.embedded_enabled
            }
            
        except Exception as e:
            self.logger.error(f"Neo4j統計取得エラー: {e}")
            return {"error": str(e)}
