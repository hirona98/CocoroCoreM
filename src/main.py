"""
CocoroCore2 メインアプリケーション

MemOS統合バックエンドサーバー
"""

import asyncio
import logging
import signal
import sys
import os
from pathlib import Path
from typing import Optional, Any

# Pythonパスにsrcディレクトリを追加
sys.path.insert(0, str(Path(__file__).parent))

# MemOSの設定
os.environ["MEMOS_BASE_PATH"] = str(Path(__file__).parent.parent)

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# ログディレクトリ作成
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

class HealthCheckFilter(logging.Filter):
    """ヘルスチェックリクエストを除外するフィルター"""
    def filter(self, record):
        # /api/health へのアクセスログを除外
        return not (hasattr(record, 'getMessage') and '/api/health' in record.getMessage())


class TruncatingFormatter(logging.Formatter):
    """メッセージ長を制限するカスタムフォーマッター（レベル別対応）"""
    
    def __init__(self, fmt=None, datefmt=None, max_length=1000, level_specific_lengths=None, truncate_marker="...", enable_truncation=True):
        super().__init__(fmt, datefmt)
        self.max_length = max_length  # デフォルト値
        self.level_specific_lengths = level_specific_lengths or {}
        self.truncate_marker = truncate_marker
        self.enable_truncation = enable_truncation
    
    def format(self, record):
        # 元のフォーマット処理
        formatted = super().format(record)
        
        # 長さ制限（有効な場合のみ）
        if self.enable_truncation:
            # レベル別制限を取得（なければデフォルト値を使用）
            max_length = self.level_specific_lengths.get(record.levelname, self.max_length)
            
            if len(formatted) > max_length:
                truncate_point = max_length - len(self.truncate_marker)
                formatted = formatted[:truncate_point] + self.truncate_marker
        
        return formatted


def setup_logging():
    """ログ設定を初期化"""
    # アプリケーション設定からログ設定を取得
    app_instance = get_app_instance()
    if app_instance and app_instance.config:
        log_config = app_instance.config.logging
    else:
        # デフォルト設定
        from core.config_manager import LoggingConfig
        log_config = LoggingConfig()
    
    # カスタムフォーマッター（レベル別ログ長制限付き）
    formatter = TruncatingFormatter(
        fmt=log_config.format,
        max_length=log_config.max_message_length,
        level_specific_lengths=log_config.level_specific_lengths,
        truncate_marker=log_config.truncate_marker,
        enable_truncation=log_config.enable_truncation
    )
    
    # ルートロガー設定
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_config.level.upper(), logging.INFO))
    
    # 既存のハンドラーをクリア
    root_logger.handlers.clear()
    
    # コンソールハンドラー
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_config.level.upper(), logging.INFO))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # ファイルハンドラー
    try:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_dir / log_config.file.split('/')[-1],  # ファイル名部分のみ使用
            maxBytes=log_config.max_size_mb * 1024 * 1024,
            backupCount=log_config.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, log_config.level.upper(), logging.INFO))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"ファイルロガーの設定に失敗しました: {e}")
    
    # uvicornのログレベル設定
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    
    # uvicorn.accessにヘルスチェックフィルターを追加
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.setLevel(logging.INFO)
    uvicorn_access_logger.addFilter(HealthCheckFilter())
    
    # Neo4jのログレベル設定
    logging.getLogger("neo4j").setLevel(logging.INFO)
    logging.getLogger("neo4j.io").setLevel(logging.INFO)
    logging.getLogger("neo4j.pool").setLevel(logging.INFO)
    logging.getLogger("neo4j.notifications").setLevel(logging.WARNING)

    # httpログレベル設定
    logging.getLogger("httpcore.http11").setLevel(logging.INFO)
    logging.getLogger("httpcore.connection").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.INFO)
    
    # MemOSのログレベル設定
    logging.getLogger("memos.utils").setLevel(logging.INFO)
    logging.getLogger("memos.llms.openai").setLevel(logging.WARNING)
    logging.getLogger("memos.memories.textual.tree_text_memory.retrieve.searcher").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

# コンポーネントのインポート
from core.config_manager import CocoroAIConfig, ConfigurationError, load_neo4j_config
# CocoroProductWrapperは重いmemosモジュールを含むため使用時に遅延インポート
from utils.neo4j_manager import Neo4jManager
from api.health import router as health_router
from api.control import router as control_router
from api.websocket_chat import router as websocket_router


class CocoroCore2App:
    """CocoroCore2メインアプリケーション"""
    
    def __init__(self):
        self.app: Optional[FastAPI] = None
        self.config: Optional[CocoroAIConfig] = None
        self.neo4j_manager: Optional[Neo4jManager] = None
        self.cocoro_product: Optional[Any] = None  # CocoroProductWrapper（遅延インポート）
        self.server_task: Optional[asyncio.Task] = None
        self.uvicorn_server: Optional[uvicorn.Server] = None
        self._shutdown_event = asyncio.Event()
        self._neo4j_task: Optional[asyncio.Task] = None
        
        # グローバルインスタンス設定
        global _app_instance
        _app_instance = self
    
    def _update_router_instances(self):
        """各ルーターのグローバルインスタンスを更新"""
        try:
            # control.pyのインスタンス更新
            from api import control
            control._app_instance = self
            
            # health.pyのインスタンス更新
            from api import health
            health._app_instance = self
            
            logger.info("ルーターのグローバルインスタンスを更新しました")
            
        except Exception as e:
            logger.warning(f"ルーターインスタンス更新で警告: {e}")
    
    async def initialize(self, config_path: Optional[str] = None):
        """アプリケーション初期化"""
        try:
            # ログ設定を最初に実行（MemOS初期化前）
            setup_logging()
            
            logger.info("CocoroCore2を初期化しています...")
            self.config = CocoroAIConfig.load(config_path)
            logger.info(f"設定読み込み完了: キャラクター={self.config.character_name}")
            
            # FastAPIアプリケーション作成（lifespanイベント付き）
            @asynccontextmanager
            async def lifespan(app: FastAPI):
                # 起動時処理はinitialize()で実行済み
                yield
                # 終了時処理
                try:
                    await self._cleanup_resources()
                except Exception as e:
                    logger.error(f"リソースクリーンアップエラー: {e}")
            
            self.app = FastAPI(
                title="CocoroCore2",
                description="MemOS統合CocoroAIバックエンド",
                version="1.0.0",
                lifespan=lifespan
            )
            
            # CORS設定
            self.app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
            
            # APIルーター追加
            self.app.include_router(health_router)
            self.app.include_router(control_router)
            self.app.include_router(websocket_router)
            
            # FastAPIのstate経由でアプリケーションインスタンスを保存
            self.app.state.core_app = self
            
            # 依存性注入のためのグローバルインスタンス更新
            self._update_router_instances()
            
            # 並行初期化開始
            logger.info("並行初期化を開始します")
            
            # Neo4j起動を非同期タスクとして開始
            async def start_neo4j():
                """Neo4j起動タスク"""
                logger.info("[並行] Neo4j管理システムを初期化しています...")
                neo4j_config = load_neo4j_config()
                self.neo4j_manager = Neo4jManager(neo4j_config)
                
                logger.info("[並行] Neo4j起動を開始...")
                success = await self.neo4j_manager.start()
                if success:
                    logger.info("[並行] Neo4j起動完了")
                else:
                    logger.error("[並行] Neo4j起動に失敗しました")
                    raise RuntimeError("Neo4jの起動に失敗しました")
                return success
            
            # Neo4j起動タスクを非同期で開始
            neo4j_task = asyncio.create_task(start_neo4j())
            
            # FastAPI初期化は並行して実行済み（上記で完了）
            logger.info("FastAPI初期化完了（並行処理中）")
            
            # MOSProduct初期化前にNeo4j起動完了を待機
            logger.info("Neo4j起動完了を待機中...")
            try:
                neo4j_started = await neo4j_task
                if not neo4j_started:
                    raise RuntimeError("Neo4jの起動に失敗しました")
            except Exception as e:
                logger.error(f"Neo4j起動エラー: {e}")
                # タスクのクリーンアップ
                if not neo4j_task.done():
                    neo4j_task.cancel()
                    try:
                        await neo4j_task
                    except asyncio.CancelledError:
                        pass
                raise
            
            # MOSProduct統合システム初期化（遅延インポート）
            logger.info("MOSProduct統合システムを初期化しています...")
            
            try:
                # MemOSのdictConfigを事前に無効化（インポート前）
                import memos.log
                def disabled_dictConfig(config):
                    pass
                memos.log.dictConfig = disabled_dictConfig
                logger.info("MemOSのdictConfigを事前無効化しました")
                
                # CocoroProductWrapperの遅延インポート（memosモジュール含む）
                logger.info("MemOSモジュールをインポート中...")
                from core.cocoro_product import CocoroProductWrapper
                
                # ログ設定を再適用（念のため）
                setup_logging()
                logger.info("ログ設定を再適用しました")
                
                self.cocoro_product = CocoroProductWrapper(self.config)
                await self.cocoro_product.initialize()
                logger.info("MOSProduct初期化完了")
                
            except ImportError as e:
                logger.error(f"MemOSモジュールのインポートに失敗しました: {e}")
                raise RuntimeError("MemOSモジュールが利用できません")
            except Exception as e:
                logger.error(f"MOSProduct初期化エラー: {e}")
                raise
            
            logger.info("CocoroCore2初期化完了")
            
        except Exception as e:
            logger.error(f"アプリケーション初期化エラー: {e}")
            raise
    
    async def start_server(self):
        """サーバー起動"""
        try:
            port = self.config.cocoroCorePort
            logger.info(f"CocoroCore2サーバーを起動しています... (ポート: {port})")
            
            # Uvicornサーバー設定
            config = uvicorn.Config(
                app=self.app,
                host="0.0.0.0",
                port=port,
                log_level="info",
                access_log=True
            )
            
            self.uvicorn_server = uvicorn.Server(config)
            logger.info(f"CocoroCore2サーバーが起動しました: http://127.0.0.1:{port}")
            # サーバー実行
            await self.uvicorn_server.serve()
            
        except Exception as e:
            logger.error(f"サーバー起動エラー: {e}")
            raise
    
    async def _cleanup_resources(self):
        """リソースクリーンアップ処理"""
        try:
            logger.info("リソースクリーンアップを開始...")
            
            # WebSocketマネージャー停止
            try:
                from api.websocket_chat import get_websocket_manager
                websocket_manager = get_websocket_manager()
                websocket_manager.shutdown()
                logger.info("WebSocketマネージャー停止完了")
            except Exception as e:
                logger.warning(f"WebSocketマネージャー停止エラー: {e}")
            
            # MOSProduct停止
            if self.cocoro_product:
                await self.cocoro_product.shutdown()
            
            # Neo4j停止
            if self.neo4j_manager:
                await self.neo4j_manager.stop()
            
            logger.info("リソースクリーンアップ完了")
            
        except Exception as e:
            logger.error(f"リソースクリーンアップエラー: {e}")
    
    async def shutdown(self):
        """アプリケーションシャットダウン"""
        try:
            logger.info("CocoroCore2をシャットダウンしています...")
            
            # シャットダウンイベントを設定
            self._shutdown_event.set()
            
            # Uvicornサーバーのgraceful shutdown
            if self.uvicorn_server:
                self.uvicorn_server.should_exit = True
                # サーバーが停止するまで少し待機
                await asyncio.sleep(0.1)
            
            logger.info("CocoroCore2シャットダウン完了")
            
        except Exception as e:
            logger.error(f"シャットダウンエラー: {e}")


# グローバルインスタンス
_app_instance: Optional[CocoroCore2App] = None


def get_app_instance() -> Optional[CocoroCore2App]:
    """アプリケーションインスタンスを取得"""
    return _app_instance


async def signal_handler(signum, frame):
    """シグナルハンドラー"""
    logger.info(f"シグナル受信: {signum}")
    if _app_instance:
        await _app_instance.shutdown()


async def main():
    """メイン実行関数"""
    app = None
    try:
        # アプリケーション作成
        app = CocoroCore2App()
        
        # シグナルハンドラー設定
        if sys.platform != "win32":
            loop = asyncio.get_event_loop()
            for sig in [signal.SIGTERM, signal.SIGINT]:
                loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(signal_handler(s, None)))
        
        # 初期化
        await app.initialize()
        
        # サーバー起動
        await app.start_server()
        
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt受信")
    except ConfigurationError as e:
        logger.error(f"設定エラー: {e}")
        if app:
            await app.shutdown()
        return
    except Exception as e:
        logger.error(f"予期しないエラー: {e}")
        if app:
            await app.shutdown()
        return
    finally:
        if app:
            await app.shutdown()


if __name__ == "__main__":
    try:
        # UTF-8モード確認
        if not (hasattr(sys, 'flags') and getattr(sys.flags, 'utf8_mode', False)):
            logger.warning("UTF-8モードが有効になっていません。`python -X utf8` で実行してください")
        
        # メイン実行
        asyncio.run(main())
        
    except KeyboardInterrupt:
        logger.info("アプリケーションが中断されました")
    except Exception as e:
        logger.error(f"致命的エラー: {e}")