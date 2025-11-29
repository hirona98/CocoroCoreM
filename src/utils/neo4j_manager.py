"""
CocoroCoreM Neo4j管理システム

組み込みNeo4jの起動・停止・接続管理
"""

import asyncio
import json
import logging
import locale
import os
import platform
import sys
import signal
import socket
import subprocess
import threading
import time
from collections import deque
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
        self._stdout_thread: Optional[threading.Thread] = None
        self._stdout_buffer = deque(maxlen=200)
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
        self.console_verbose = config.get("verbose", False)
        
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
            self.console_verbose = fresh_config.get("verbose", False)
            
            # ポート番号を抽出
            if ":" in self.uri:
                self.bolt_port = int(self.uri.split(":")[-1])
            else:
                self.bolt_port = 7687
            
            self.logger.debug(
                f"Setting.json再読み込み完了: uri={self.uri}, web_port={self.web_port}, "
                f"embedded_enabled={self.embedded_enabled}, bolt_port={self.bolt_port}, "
                f"verbose={self.console_verbose}"
            )
                
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
            
            self.logger.debug(f"Neo4j設定ファイル更新開始: {config_path}")
            
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
                self.logger.debug(
                    f"Neo4j設定は既に最新: bolt={self.bolt_port}, http={self.web_port}"
                )
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
            self.logger.debug("Neo4j設定ファイルの書き換えが完了しました")
            return True
            
        except Exception as e:
            self.logger.error(f"Neo4j設定ファイル更新エラー: {e}")
            return False

    def _check_ports_available(self) -> bool:
        """Neo4j使用ポートの利用可能性を確認"""
        ports_to_check = [self.bolt_port, self.web_port]
        self.logger.debug(f"Neo4jポート確認開始: {ports_to_check}")
        
        for port in ports_to_check:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(1)
                    result = sock.connect_ex(('127.0.0.1', port))
                    if result == 0:  # 接続成功 = ポート使用中
                        self.logger.error(f"ポート {port} は既に使用中です")
                        return False
                    self.logger.debug(f"ポート {port} は空き状態です")
            except Exception as e:
                self.logger.warning(f"ポート {port} の確認に失敗: {e}")
                # エラー時は起動を試行（ネットワーク設定などの問題の可能性）
        
        return True
    
    def _start_stdout_reader(self) -> None:
        """Neo4j起動プロセスの標準出力を取り込む"""
        if not self.process or not self.process.stdout:
            return
        
        if self._stdout_thread and self._stdout_thread.is_alive():
            return
        
        preferred_encoding = locale.getpreferredencoding(False) or "utf-8"
        
        def _reader():
            for raw_line in iter(self.process.stdout.readline, b''):
                try:
                    line = raw_line.decode(preferred_encoding, errors='replace').rstrip()
                except Exception:
                    line = raw_line.decode('utf-8', errors='replace').rstrip()
                if line:
                    self._stdout_buffer.append(line)
                    self.logger.debug(f"[Neo4j STDOUT] {line}")
        
        self._stdout_thread = threading.Thread(
            target=_reader,
            name="Neo4jStdoutReader",
            daemon=True,
        )
        self._stdout_thread.start()
    
    def _log_recent_stdout(self, message: str, level: int = logging.ERROR) -> None:
        """Neo4jの最新標準出力をまとめて出力"""
        if not self._stdout_buffer:
            self.logger.log(level, f"{message}（Neo4j標準出力は空です）")
            return
        
        joined = "\n".join(self._stdout_buffer)
        self.logger.log(level, f"{message}\n--- Neo4j STDOUT (last {len(self._stdout_buffer)} lines) ---\n{joined}\n--- End of Neo4j STDOUT ---")

    async def start(self) -> bool:
        """
        Neo4jサービスを起動
        
        Returns:
            bool: 起動成功したかどうか
        """
        self.logger.debug(
            f"Neo4j起動処理開始: embedded_enabled={self.embedded_enabled}, "
            f"bolt_port={self.bolt_port}, web_port={self.web_port}"
        )
        if not self.embedded_enabled:
            self.logger.info("組み込みNeo4jが無効になっています")
            return True
        
        if self.is_running:
            self.logger.info("Neo4jは既に起動しています")
            return True
        
        try:
            # 1. 残留java.exeプロセス確認・終了
            self.logger.debug("Neo4j起動ステップ1: java.exeプロセス整理を開始")
            await self._cleanup_java_processes()
            
            # 2. 最新のSetting.json設定を再読み込み
            self.logger.debug("Neo4j起動ステップ2: Setting.jsonを再読み込み")
            if not self._reload_config():
                self.logger.error("Setting.jsonの再読み込みに失敗しました")
                return False
            
            # 3. Neo4j実行ファイルの存在確認
            self.logger.debug(f"Neo4j起動ステップ3: 実行ファイル確認 {self.neo4j_executable}")
            if not self.neo4j_executable.exists():
                self.logger.error(f"Neo4j実行ファイルが見つかりません: {self.neo4j_executable}")
                return False
            
            # 4. Neo4j設定ファイル更新（最新の設定で）
            self.logger.debug("Neo4j起動ステップ4: Neo4j設定ファイルを更新")
            if not self._update_neo4j_config():
                self.logger.error("Neo4j設定ファイルの更新に失敗しました")
                return False

            # 5. ポート利用可能性確認
            self.logger.debug("Neo4j起動ステップ5: ポート利用状況を確認")
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
            if self.console_verbose:
                console_cmd.append("--verbose")
                self.logger.debug("Neo4j起動オプション: --verbose を付与しました")
            self.logger.debug(f"Neo4j起動ステップ6: コマンド={console_cmd}, 作業ディレクトリ={self.neo4j_dir}")
            self.logger.debug(
                f"Neo4j起動環境: JAVA_HOME={java_home}, NEO4J_HOME={self.neo4j_dir}, "
                f"NEO4J_CONF={self.neo4j_dir / 'conf'}"
            )
            self._stdout_buffer.clear()
            
            self.process = subprocess.Popen(
                console_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(self.neo4j_dir),
                env=env,
                text=False,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
            self._start_stdout_reader()
            
            # 起動待ち
            self.logger.debug("Neo4j起動ステップ7: 起動完了待機を開始")
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
            self._log_recent_stdout("Neo4j標準出力ダイジェスト（起動例外時）")
            return False
    
    async def _wait_for_startup(self) -> bool:
        """起動完了を待つ"""
        start_time = time.time()
        attempt = 0
        self.logger.debug(f"Neo4j起動監視を開始: タイムアウト={self.startup_timeout}秒")
        
        while time.time() - start_time < self.startup_timeout:
            if self.process and self.process.poll() is not None:
                # プロセスが終了している
                self.logger.error(f"Neo4jプロセスが異常終了しました (終了コード: {self.process.returncode})")
                self._log_recent_stdout("Neo4j標準出力ダイジェスト（異常終了検知時）")
                return False
            
            # 接続テスト
            self.logger.debug(f"Neo4j起動監視: 接続テスト試行 {attempt + 1}")
            if await self._test_connection():
                self.logger.info(f"Neo4j接続成功 (試行回数: {attempt + 1}, 経過時間: {time.time() - start_time:.1f}秒)")
                return True
            
            # ポーリング待機時間
            await asyncio.sleep(0.5)
            attempt += 1
        
        self.logger.error(f"Neo4j起動がタイムアウトしました（タイムアウト: {self.startup_timeout}秒）")
        self._log_recent_stdout("Neo4j標準出力ダイジェスト（起動タイムアウト）")
        return False
    
    async def _test_connection(self) -> bool:
        """Neo4j接続テスト（遅延インポート対応）"""
        # Neo4jドライバーの遅延インポート
        self.logger.debug(f"Neo4j接続テスト開始: uri={self.uri}")
        driver_available, GraphDatabase = _ensure_neo4j_driver()
        if not driver_available:
            self.logger.debug("Neo4jドライバーが未導入のため接続テストを実行できません")
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

            success = await asyncio.get_event_loop().run_in_executor(None, _test_driver)
            if success:
                self.logger.debug("Neo4j接続テスト成功")
            else:
                self.logger.debug("Neo4j接続テスト失敗（レスポンス異常）")
            return success
                
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
        
        if self.process and self.process.stdout:
            try:
                self.process.stdout.close()
            except Exception as e:
                self.logger.debug(f"Neo4j標準出力クローズ時に警告: {e}")
        
        self.process = None
        self._stdout_thread = None
        self.is_running = False
    
    async def _cleanup_java_processes(self):
        """CocoroCoreMのjreを使用するjava.exeプロセスのみを終了"""
        try:
            self.logger.debug("Neo4j起動前クリーンアップ: java.exeプロセス確認を開始")
            # CocoroCoreMのjreディレクトリパス
            java_home = str(self.base_dir / "jre")
            
            # PowerShellでプロセス一覧を取得（wmic非推奨対応）
            ps_command = (
                "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
                "Get-Process java -ErrorAction SilentlyContinue | "
                f"Where-Object {{ $_.Path -and $_.Path -like '{java_home}*' }} | "
                "Select-Object Id,Path | ConvertTo-Json -Compress"
            )
            self.logger.debug(f"Neo4j起動前クリーンアップ: PowerShellコマンド={ps_command}")

            def run_powershell():
                return subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_command],
                    capture_output=True,
                    text=False,
                    timeout=10
                )

            result = await asyncio.get_event_loop().run_in_executor(None, run_powershell)

            if result.returncode != 0:
                # self.logger.error("PowerShellによるJavaプロセス取得に失敗しました")
                return

            stdout_text = result.stdout.decode("utf-8", errors="replace")
            try:
                parsed = json.loads(stdout_text) if stdout_text.strip() else []
            except json.JSONDecodeError as e:
                self.logger.error(f"PowerShell出力のJSONデコードに失敗しました: {e}")
                return

            processes = parsed if isinstance(parsed, list) else [parsed]
            target_pids = []
            for proc in processes:
                try:
                    pid = int(proc.get("Id"))
                    target_pids.append(pid)
                    self.logger.info(f"CocoroCoreMの残留java.exeプロセスを発見: PID {pid}")
                except Exception as e:
                    self.logger.debug(f"PowerShell出力の行解析をスキップ: {proc} (エラー: {e})")
            
            # 対象プロセスを終了
            if not target_pids:
                self.logger.debug("CocoroCoreMのjava.exeプロセスは検出されませんでした")
            
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
            
            if target_pids:
                # プロセス終了後、ポート解放まで少し待機
                self.logger.info("java.exeプロセスのポート解放を待機しています...")
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
