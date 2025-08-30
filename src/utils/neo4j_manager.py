"""
CocoroCoreM Neo4j管理システム

組み込みNeo4jの起動・停止・接続管理
"""

import asyncio
import logging
import os
import platform
import sys
import signal
import socket
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional

# Neo4jドライバーは使用時に遅延インポート（起動高速化のため）
_neo4j_driver_checked = False
_neo4j_driver_available = False
_GraphDatabase = None

def _ensure_neo4j_driver():
    """Neo4jドライバーの遅延インポートと可用性確認"""
    global _neo4j_driver_checked, _neo4j_driver_available, _GraphDatabase
    
    if not _neo4j_driver_checked:
        try:
            from neo4j import GraphDatabase
            _GraphDatabase = GraphDatabase
            _neo4j_driver_available = True
            logger.debug("Neo4jドライバーを正常にインポートしました")
        except ImportError:
            _neo4j_driver_available = False
            _GraphDatabase = None
            logger.warning("Neo4jドライバーが利用できません")
        finally:
            _neo4j_driver_checked = True
    
    return _neo4j_driver_available, _GraphDatabase

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
        # PyInstaller対応: exe化時は実行ファイルと同じディレクトリを基準に
        if getattr(sys, 'frozen', False):
            # exe実行時
            self.base_dir = Path(sys.executable).parent
        else:
            # 通常のPython実行時
            self.base_dir = Path(__file__).parent.parent.parent  # CocoroCoreMディレクトリ
        
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
            expected_http_enabled = "server.http.enabled=false"
            
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
                    result = sock.connect_ex(('127.0.0.1', port))
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
            # 1. 残留java.exeプロセス確認・終了
            await self._cleanup_java_processes()
            
            # 2. 最新のSetting.json設定を再読み込み
            if not self._reload_config():
                self.logger.error("Setting.jsonの再読み込みに失敗しました")
                return False
            
            # 3. Neo4j実行ファイルの存在確認
            if not self.neo4j_executable.exists():
                self.logger.error(f"Neo4j実行ファイルが見つかりません: {self.neo4j_executable}")
                return False
            
            # 4. Neo4j設定ファイル更新（最新の設定で）
            if not self._update_neo4j_config():
                self.logger.error("Neo4j設定ファイルの更新に失敗しました")
                return False

            # 5. ポート利用可能性確認
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
        attempt = 0
        
        while time.time() - start_time < self.startup_timeout:
            if self.process and self.process.poll() is not None:
                # プロセスが終了している
                self.logger.error(f"Neo4jプロセスが異常終了しました (終了コード: {self.process.returncode})")
                return False
            
            # 接続テスト
            if await self._test_connection():
                self.logger.info(f"Neo4j接続成功 (試行回数: {attempt + 1}, 経過時間: {time.time() - start_time:.1f}秒)")
                return True
            
            # ポーリング待機時間
            await asyncio.sleep(0.5)
            attempt += 1
        
        return False
    
    async def _test_connection(self) -> bool:
        """Neo4j接続テスト（遅延インポート対応）"""
        # Neo4jドライバーの遅延インポート
        driver_available, GraphDatabase = _ensure_neo4j_driver()
        if not driver_available:
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
        
        # taskkillで確実に停止
        try:
            subprocess.run(
                f"taskkill /f /t /pid {self.process.pid}",
                shell=True,
                check=False,
                timeout=2
            )
            self.logger.info("Neo4j停止完了")
        except Exception as e:
            self.logger.error(f"Neo4j停止エラー: {e}")
        
        self.process = None
        self.is_running = False
    
    async def _cleanup_java_processes(self):
        """CocoroCoreMのjreを使用するjava.exeプロセスのみを終了"""
        try:
            # CocoroCoreMのjreディレクトリパス
            java_home = str(self.base_dir / "jre")
            
            # wmicでjava.exeプロセスの情報を取得
            cmd = 'wmic process where "name=\'java.exe\'" get processid,commandline /format:csv'
            
            def run_wmic():
                return subprocess.run(
                    cmd, 
                    shell=True, 
                    capture_output=True, 
                    text=True, 
                    timeout=5
                )
            
            result = await asyncio.get_event_loop().run_in_executor(None, run_wmic)
            
            if result.returncode != 0:
                self.logger.error(f"wmicコマンド実行エラー: {result.stderr}")
                return
            
            # CSVの解析（ヘッダー行をスキップ）
            lines = result.stdout.strip().split('\n')[1:]  # ヘッダーをスキップ
            target_pids = []
            
            for line in lines:
                if not line.strip():
                    continue
                
                # CSV形式: Node,CommandLine,ProcessId
                try:
                    parts = line.split(',', 2)
                    if len(parts) >= 3:
                        command_line = parts[1].strip()
                        pid_str = parts[2].strip()
                        
                        if java_home in command_line and pid_str.isdigit():
                            target_pids.append(int(pid_str))
                            self.logger.info(f"CocoroCoreMの残留java.exeプロセスを発見: PID {pid_str}")
                
                except (ValueError, IndexError) as e:
                    self.logger.debug(f"wmicの行解析をスキップ: {line[:50]}... (エラー: {e})")
                    continue
            
            # 対象プロセスを終了
            for pid in target_pids:
                try:
                    subprocess.run(
                        f"taskkill /f /pid {pid}",
                        shell=True,
                        check=False,
                        timeout=3
                    )
                    self.logger.info(f"残留java.exeプロセス終了完了: PID {pid}")
                except Exception as e:
                    self.logger.error(f"java.exeプロセス終了エラー (PID {pid}): {e}")
            
            if not target_pids:
                self.logger.info("CocoroCoreMのjava.exeプロセスは見つかりませんでした")
            else:
                # プロセス終了後、ポート解放まで少し待機
                self.logger.info("java.exeプロセス終了後、ポート解放を待機しています...")
                await asyncio.sleep(3)
                
        except Exception as e:
            self.logger.error(f"java.exeプロセスクリーンアップエラー: {e}")

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
