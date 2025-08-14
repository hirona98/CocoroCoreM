"""
CocoroCore2 メインアプリケーション

MemOS統合バックエンドサーバー
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/cocoro_core2.log", encoding="utf-8")
    ]
)

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
    
    async def initialize(self, config_path: Optional[str] = None):
        """アプリケーション初期化"""
        try:
            logger.info("CocoroCore2を初期化しています...")
            
            # 1. ログディレクトリ作成
            Path("logs").mkdir(exist_ok=True)
            
            # 2. 設定読み込み
            logger.info("設定ファイルを読み込んでいます...")
            self.config = CocoroAIConfig.load(config_path)
            logger.info(f"設定読み込み完了: キャラクター={self.config.character_name}")
            
            # 3. FastAPIアプリ初期化
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
            
            # 4. Neo4j管理システム初期化
            logger.info("Neo4j管理システムを初期化しています...")
            neo4j_config = load_neo4j_config()
            self.neo4j_manager = Neo4jManager(neo4j_config)
            
            # Neo4j起動
            neo4j_started = await self.neo4j_manager.start()
            if neo4j_started:
                logger.info("Neo4j起動完了")
            else:
                logger.warning("Neo4j起動に失敗しましたが、処理を続行します")
            
            # 5. MOSProduct統合システム初期化
            logger.info("MOSProduct統合システムを初期化しています...")
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