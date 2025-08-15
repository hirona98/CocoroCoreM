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
            "status": "healthy",
            "version": "1.0.0",
            "character": app.config.character_name if app and app.config else "つくよみちゃん",
            "memory_enabled": True,
            "active_sessions": 1,
            "mcp_status": {
                "total_servers": 0,
                "connected_servers": 0,
                "total_tools": 0
            }
        }
        
        # 現在のキャラクターのLLMモデルを取得
        if app and app.config and app.config.current_character:
            health_data["llm_model"] = app.config.current_character.llmModel
        else:
            health_data["llm_model"] = "gpt-4o-mini"
        
        # Neo4j状態を取得
        if app and hasattr(app, 'neo4j_manager'):
            neo4j_health = await app.neo4j_manager.health_check()
            health_data["neo4j_status"] = neo4j_health
        
        logger.info("ヘルスチェック実行完了")
        return HealthCheckResponse(**health_data)
        
    except Exception as e:
        logger.error(f"ヘルスチェックエラー: {e}")
        error_response = ErrorResponse(
            error="health_check_failed",
            message="ヘルスチェックに失敗しました",
            details={"error": str(e)}
        )
        return JSONResponse(status_code=500, content=error_response.dict())


@router.get("/health/neo4j")
async def neo4j_health(app=Depends(get_core_app)):
    """
    Neo4j専用ヘルスチェック
    
    Returns:
        Dict: Neo4j状態情報
    """
    try:
        if app and hasattr(app, 'neo4j_manager'):
            health_data = await app.neo4j_manager.health_check()
            stats_data = await app.neo4j_manager.get_stats()
            
            return {
                "success": True,
                "health": health_data,
                "stats": stats_data
            }
        else:
            return {
                "success": False,
                "error": "Neo4j管理システムが初期化されていません"
            }
            
    except Exception as e:
        logger.error(f"Neo4jヘルスチェックエラー: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "neo4j_health_check_failed",
                "message": str(e)
            }
        )