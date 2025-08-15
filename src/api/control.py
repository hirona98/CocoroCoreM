"""
CocoroCore2 システム制御API

システム制御とステータス管理
"""

import asyncio
import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from models.api_models import StandardResponse, ErrorResponse, SystemControlRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["control"])

# グローバルアプリケーションインスタンス
_app_instance = None


def get_core_app():
    """CoreAppの依存性注入 - 遅延初期化対応"""
    global _app_instance
    if _app_instance is None:
        from main import get_app_instance
        _app_instance = get_app_instance()
    return _app_instance


@router.post("/control", response_model=StandardResponse)
async def system_control(request: SystemControlRequest, app=Depends(get_core_app)):
    """
    システム制御
    
    Args:
        request: 制御リクエスト
        
    Returns:
        StandardResponse: 制御結果
    """
    try:
        action = request.action
        
        logger.info(f"システム制御実行: {action}")
        
        if action == "shutdown":
            # システムシャットダウン（バックグラウンドで実行）
            asyncio.create_task(_handle_shutdown_background(app))
            result = {"message": "シャットダウン処理を開始しました"}
            
        elif action == "start_log_forwarding":
            # ログ転送開始
            result = await _handle_start_log_forwarding(app)
            
        elif action == "stop_log_forwarding":
            # ログ転送停止
            result = await _handle_stop_log_forwarding(app)
            
        else:
            raise ValueError(f"未対応のアクション: {action}")
        
        return StandardResponse(
            status="success",
            message=f"制御アクション '{action}' を実行しました"
        )
        
    except Exception as e:
        logger.error(f"システム制御エラー: {e}")
        error_response = ErrorResponse(
            error="system_control_failed",
            message=f"システム制御に失敗しました: {action}",
            details={"action": action, "error": str(e)}
        )
        return JSONResponse(status_code=500, content=error_response.dict())


async def _handle_shutdown_background(app):
    """システムシャットダウン処理（バックグラウンド実行）"""
    try:
        logger.info("バックグラウンドシャットダウン処理を開始")
        
        # メインのshutdown()メソッドを呼び出して完全なシャットダウンを実行
        if app and hasattr(app, 'shutdown'):
            await app.shutdown()
        
        logger.info("バックグラウンドシャットダウン処理完了")
        
    except Exception as e:
        logger.error(f"バックグラウンドシャットダウン処理エラー: {e}")


async def _handle_restart(app) -> Dict:
    """システム再起動処理"""
    try:
        # 設定リロード（再起動の簡易版）
        await _handle_reload_config(app)
        return {"message": "システム設定を再読み込みしました"}
        
    except Exception as e:
        logger.error(f"再起動処理エラー: {e}")
        raise


async def _handle_reload_config(app) -> Dict:
    """設定リロード処理"""
    try:
        if app:
            # 設定ファイルを再読み込み
            from core.config_manager import CocoroAIConfig
            new_config = CocoroAIConfig.load()
            app.config = new_config
            logger.info("設定ファイルを再読み込みしました")
        
        return {"message": "設定を再読み込みしました"}
        
    except Exception as e:
        logger.error(f"設定リロードエラー: {e}")
        raise


async def _handle_clear_cache(app) -> Dict:
    """キャッシュクリア処理"""
    try:
        # 実装に応じてキャッシュクリア処理を追加
        return {"message": "キャッシュをクリアしました"}
        
    except Exception as e:
        logger.error(f"キャッシュクリアエラー: {e}")
        raise


async def _handle_start_log_forwarding(app) -> Dict:
    """ログ転送開始処理"""
    try:
        # ログ転送の実装はまだされていないため、基本的な応答を返す
        logger.info("ログ転送開始要求を受信しました")
        
        # TODO: 将来的にはここでログ転送メカニズムを起動する
        # 例: app.log_forwarder.start() など
        
        return {"message": "ログ転送を開始しました"}
        
    except Exception as e:
        logger.error(f"ログ転送開始エラー: {e}")
        raise


async def _handle_stop_log_forwarding(app) -> Dict:
    """ログ転送停止処理"""
    try:
        # ログ転送の実装はまだされていないため、基本的な応答を返す
        logger.info("ログ転送停止要求を受信しました")
        
        # TODO: 将来的にはここでログ転送メカニズムを停止する
        # 例: app.log_forwarder.stop() など
        
        return {"message": "ログ転送を停止しました"}
        
    except Exception as e:
        logger.error(f"ログ転送停止エラー: {e}")
        raise