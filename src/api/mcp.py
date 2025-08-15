"""
CocoroCore2 MCP API

MCP (Model Context Protocol) ツール管理API
"""

import logging
from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from models.api_models import StandardResponse, ErrorResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/mcp", tags=["mcp"])

# グローバルアプリケーションインスタンス
_app_instance = None


def get_core_app():
    """CoreAppの依存性注入 - 遅延初期化対応"""
    global _app_instance
    if _app_instance is None:
        from main import get_app_instance
        _app_instance = get_app_instance()
    return _app_instance


@router.get("/tool-registration-log")
async def get_tool_registration_log(app=Depends(get_core_app)):
    """
    MCPツール登録ログを取得
    
    Returns:
        Dict: MCPツール登録ログ情報
    """
    try:
        # TODO: 現在未実装のため、仕様書通りのレスポンスを返す
        response_data = {
            "status": "success",
            "message": "MCPは現在実装されていません",
            "logs": [],
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error(f"MCPツール登録ログ取得エラー: {e}")
        error_response = ErrorResponse(
            error="mcp_tool_registration_log_failed",
            message="MCPツール登録ログ取得に失敗しました",
            details={"error": str(e)}
        )
        return JSONResponse(status_code=500, content=error_response.dict())