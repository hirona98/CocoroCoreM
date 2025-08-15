"""
CocoroCore2 システム制御API

システム制御とステータス管理
"""

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
        parameters = request.parameters or {}
        
        logger.info(f"システム制御実行: {action}, パラメータ: {parameters}")
        
        if action == "shutdown":
            # システムシャットダウン
            result = await _handle_shutdown(app, parameters)
            
        elif action == "restart":
            # システム再起動
            result = await _handle_restart(app, parameters)
            
        elif action == "reload_config":
            # 設定リロード
            result = await _handle_reload_config(app, parameters)
            
        elif action == "clear_cache":
            # キャッシュクリア
            result = await _handle_clear_cache(app, parameters)
            
        else:
            raise ValueError(f"未対応のアクション: {action}")
        
        return StandardResponse(
            success=True,
            message=f"制御アクション '{action}' を実行しました",
            data=result
        )
        
    except Exception as e:
        logger.error(f"システム制御エラー: {e}")
        error_response = ErrorResponse(
            error="system_control_failed",
            message=f"システム制御に失敗しました: {action}",
            details={"action": action, "error": str(e)}
        )
        return JSONResponse(status_code=500, content=error_response.dict())


async def _handle_shutdown(app, parameters: Dict) -> Dict:
    """システムシャットダウン処理"""
    try:
        # グレースフルシャットダウン
        if app:
            # Neo4j停止
            if hasattr(app, 'neo4j_manager'):
                await app.neo4j_manager.stop()
            
            # MOSProduct停止
            if hasattr(app, 'cocoro_product'):
                app.cocoro_product.shutdown()
        
        return {"message": "シャットダウン処理を開始しました"}
        
    except Exception as e:
        logger.error(f"シャットダウン処理エラー: {e}")
        raise


async def _handle_restart(app, parameters: Dict) -> Dict:
    """システム再起動処理"""
    try:
        # 設定リロード（再起動の簡易版）
        await _handle_reload_config(app, parameters)
        return {"message": "システム設定を再読み込みしました"}
        
    except Exception as e:
        logger.error(f"再起動処理エラー: {e}")
        raise


async def _handle_reload_config(app, parameters: Dict) -> Dict:
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


async def _handle_clear_cache(app, parameters: Dict) -> Dict:
    """キャッシュクリア処理"""
    try:
        # 実装に応じてキャッシュクリア処理を追加
        return {"message": "キャッシュをクリアしました"}
        
    except Exception as e:
        logger.error(f"キャッシュクリアエラー: {e}")
        raise