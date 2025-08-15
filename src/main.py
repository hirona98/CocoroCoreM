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
from typing import Optional

# Pythonパスにsrcディレクトリを追加
sys.path.insert(0, str(Path(__file__).parent))

# MemOSの設定
os.environ["MEMOS_BASE_PATH"] = str(Path(__file__).parent.parent)

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ログディレクトリ作成
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

def setup_logging():
    """ログ設定を初期化"""
    # ログフォーマット
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # ルートロガー設定
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 既存のハンドラーをクリア
    root_logger.handlers.clear()
    
    # コンソールハンドラー
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # ファイルハンドラー
    try:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_dir / "cocoro_core2.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"ファイルロガーの設定に失敗しました: {e}")
    
    # uvicornのログレベル設定
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    
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
    logging.getLogger("memos.llms.openai").setLevel(logging.WARNING)
    logging.getLogger("memos.memories.textual.tree_text_memory.retrieve.searcher").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

# コンポーネントのインポート
from core.config_manager import CocoroAIConfig, ConfigurationError, load_neo4j_config
from core.cocoro_product import CocoroProductWrapper
from utils.neo4j_manager import Neo4jManager
from api.health import router as health_router
from api.control import router as control_router


class CocoroCore2App:
    """CocoroCore2メインアプリケーション"""
    
    def __init__(self):
        self.app: Optional[FastAPI] = None
        self.config: Optional[CocoroAIConfig] = None
        self.neo4j_manager: Optional[Neo4jManager] = None
        self.cocoro_product: Optional[CocoroProductWrapper] = None
        self.server_task: Optional[asyncio.Task] = None
        
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
            self.app = FastAPI(
                title="CocoroCore2",
                description="MemOS統合CocoroAIバックエンド",
                version="1.0.0"
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
            
            # 依存性注入のためのグローバルインスタンス更新
            self._update_router_instances()
            
            # Neo4j管理システム初期化
            logger.info("Neo4j管理システムを初期化しています...")
            neo4j_config = load_neo4j_config()
            self.neo4j_manager = Neo4jManager(neo4j_config)
            
            # Neo4j起動
            neo4j_started = await self.neo4j_manager.start()
            if neo4j_started:
                logger.info("Neo4j起動完了")
            else:
                logger.error("Neo4j起動に失敗しました。アプリケーションを終了します")
                # 起動要件未達のため起動処理を中断
                raise RuntimeError("Neo4jの起動に失敗しました")
            
            # MOSProduct統合システム初期化
            logger.info("MOSProduct統合システムを初期化しています...")
            
            # MemOSのdictConfigを事前に無効化
            try:
                import memos.log
                def disabled_dictConfig(config):
                    pass
                memos.log.dictConfig = disabled_dictConfig
                logger.info("MemOSのdictConfigを無効化しました")
            except Exception as e:
                logger.warning(f"MemOSのdictConfig無効化に失敗: {e}")
            
            self.cocoro_product = CocoroProductWrapper(self.config)
            await self.cocoro_product.initialize()
            logger.info("MOSProduct初期化完了")
            
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
            
            server = uvicorn.Server(config)
            self.server_task = asyncio.create_task(server.serve())
            
            logger.info(f"CocoroCore2サーバーが起動しました: http://localhost:{port}")
            
            # サーバー実行
            await self.server_task
            
        except Exception as e:
            logger.error(f"サーバー起動エラー: {e}")
            raise
    
    async def shutdown(self):
        """アプリケーションシャットダウン"""
        try:
            logger.info("CocoroCore2をシャットダウンしています...")
            
            # サーバー停止
            if self.server_task:
                self.server_task.cancel()
                try:
                    await self.server_task
                except asyncio.CancelledError:
                    pass
            
            # MOSProduct停止
            if self.cocoro_product:
                self.cocoro_product.shutdown()
            
            # Neo4j停止
            if self.neo4j_manager:
                await self.neo4j_manager.stop()
            
            logger.info("CocoroCore2シャットダウン完了")
            
        except Exception as e:
            logger.error(f"シャットダウンエラー: {e}")
        
        finally:
            # 強制終了
            sys.exit(0)


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
        sys.exit(1)
    except Exception as e:
        logger.error(f"予期しないエラー: {e}")
        sys.exit(1)
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
        sys.exit(1)