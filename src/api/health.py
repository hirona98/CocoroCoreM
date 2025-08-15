"""
CocoroCore2 ヘルスチェックAPI

システム状態の監視とヘルスチェック
"""

import logging
from typing import Dict

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from models.api_models import HealthCheckResponse, ErrorResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["health"])

# グローバルアプリケーションインスタンス
_app_instance = None


def get_core_app():
    """CoreAppの依存性注入 - 遅延初期化対応"""
    global _app_instance
    if _app_instance is None:
        from main import get_app_instance
        _app_instance = get_app_instance()
    return _app_instance


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(app=Depends(get_core_app)):
    """
    システムヘルスチェック
    
    Returns:
        HealthCheckResponse: システム状態情報
    """
    try:
        health_data = {
            "status": "healthy"
        }

        return HealthCheckResponse(**health_data)
        
    except Exception as e:
        logger.error(f"ヘルスチェックエラー: {e}")
        return HealthCheckResponse(status="error")
