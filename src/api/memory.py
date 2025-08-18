"""
CocoroCore2 メモリ管理API

MemOS統合メモリ管理機能へのREST APIインターフェース
キャラクター別記憶管理に対応（CocoroDock互換）
"""

import logging
from typing import Dict, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import JSONResponse

from models.api_models import (
    CharacterListResponse,
    CharacterMemoryInfo,
    CharacterMemoryStatsResponse,
    CharacterMemoryDeleteResponse,
    MemoryDeleteDetails,
    ErrorResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["memory"])

# グローバルアプリケーションインスタンス（既存パターン準拠）
_app_instance = None


def get_core_app():
    """CoreAppの依存性注入 - 遅延初期化対応"""
    global _app_instance
    if _app_instance is None:
        from main import get_app_instance
        _app_instance = get_app_instance()
    return _app_instance


def _convert_character_list_to_response(characters_data: List[Dict]) -> CharacterListResponse:
    """内部キャラクターリストデータを外部APIレスポンスに変換"""
    character_infos = []
    
    for char in characters_data:
        character_infos.append(CharacterMemoryInfo(
            memory_id=char.get("memory_id", ""),
            memory_name=char.get("memory_name", char.get("memory_id", "")),
            role=char.get("role", "character"),
            created=char.get("created", True)
        ))
    
    return CharacterListResponse(data=character_infos)


def _convert_character_stats_to_response(stats_data: Dict, memory_id: str) -> CharacterMemoryStatsResponse:
    """内部統計データを外部APIレスポンスに変換"""
    return CharacterMemoryStatsResponse(
        memory_id=memory_id,
        total_memories=stats_data.get("total_memories", 0),
        text_memories=stats_data.get("text_memories", 0),
        activation_memories=stats_data.get("activation_memories", 0),
        parametric_memories=stats_data.get("parametric_memories", 0),
        last_updated=stats_data.get("last_updated"),
        cube_id=stats_data.get("cube_id", ""),
        timestamp=datetime.utcnow()
    )


def _convert_character_delete_result_to_response(delete_result: Dict, memory_id: str) -> CharacterMemoryDeleteResponse:
    """削除結果データを削除レスポンスに変換"""
    details = MemoryDeleteDetails(
        text_memories=delete_result.get("details", {}).get("text_memories", 0),
        activation_memories=delete_result.get("details", {}).get("activation_memories", 0),
        parametric_memories=delete_result.get("details", {}).get("parametric_memories", 0)
    )
    
    return CharacterMemoryDeleteResponse(
        status="success",
        message="記憶を削除しました",
        deleted_count=delete_result.get("deleted_count", 0),
        details=details,
        timestamp=datetime.utcnow()
    )


@router.get("/memory/characters", response_model=CharacterListResponse)
async def get_memory_characters(app=Depends(get_core_app)):
    """
    キャラクター一覧取得
    
    CocoroDockからの記憶管理対象キャラクター一覧を取得
    
    Returns:
        CharacterListResponse: キャラクター一覧
    """
    try:
        logger.debug("キャラクター一覧取得開始")
        
        # CocoroProductWrapperから内部キャラクターリストを取得
        characters_data = app.cocoro_product.get_character_list()
        
        # 外部APIレスポンス形式に変換
        response = _convert_character_list_to_response(characters_data)
        
        logger.info(f"キャラクター一覧取得成功: {len(response.data)}件")
        return response
        
    except Exception as e:
        logger.error(f"キャラクター一覧取得エラー: {e}")
        error_response = ErrorResponse(
            error="character_list_failed",
            message="キャラクター一覧の取得に失敗しました",
            details={"error": str(e)}
        )
        return JSONResponse(status_code=500, content=error_response.dict())


@router.get("/memory/character/{memory_id}/stats", response_model=CharacterMemoryStatsResponse)
async def get_character_memory_stats(
    memory_id: str = Path(..., description="キャラクターのメモリID"),
    app=Depends(get_core_app)
):
    """
    キャラクター記憶統計情報取得
    
    指定されたキャラクター（メモリID）の記憶統計情報を取得
    
    Args:
        memory_id: 統計取得対象のキャラクターメモリID
        
    Returns:
        CharacterMemoryStatsResponse: キャラクター記憶統計情報
    """
    try:
        logger.debug(f"キャラクター記憶統計取得開始: {memory_id}")
        
        # CocoroProductWrapperから統計データを取得
        stats_data = app.cocoro_product.get_character_memory_stats(memory_id)
        
        # 外部APIレスポンス形式に変換
        response = _convert_character_stats_to_response(stats_data, memory_id)
        
        logger.info(f"キャラクター記憶統計取得成功: {memory_id}, 総記憶数: {response.total_memories}")
        return response
        
    except Exception as e:
        logger.error(f"キャラクター記憶統計取得エラー: {memory_id}, {e}")
        
        # 特殊ケース: キャラクターが存在しない場合は空の統計を返す（CocoroDock互換）
        if "not found" in str(e).lower() or "見つかりません" in str(e) or "存在しない" in str(e):
            logger.info(f"キャラクターが存在しないため空の統計を返します: {memory_id}")
            empty_stats = CharacterMemoryStatsResponse(
                memory_id=memory_id,
                cube_id=f"user_user_{memory_id}_cube"
            )
            return empty_stats
        
        error_response = ErrorResponse(
            error="character_memory_stats_failed",
            message=f"キャラクター記憶統計の取得に失敗しました: {memory_id}",
            details={"memory_id": memory_id, "error": str(e)}
        )
        return JSONResponse(status_code=500, content=error_response.dict())


@router.delete("/memory/character/{memory_id}/all", response_model=CharacterMemoryDeleteResponse)
async def delete_character_memories(
    memory_id: str = Path(..., description="キャラクターのメモリID"),
    app=Depends(get_core_app)
):
    """
    キャラクターの全記憶削除
    
    指定されたキャラクター（メモリID）の全記憶を削除
    
    Args:
        memory_id: 削除対象のキャラクターメモリID
        
    Returns:
        CharacterMemoryDeleteResponse: 削除結果
    """
    try:
        logger.info(f"キャラクター全記憶削除開始: {memory_id}")
        
        # CocoroProductWrapperで記憶削除実行
        delete_result = app.cocoro_product.delete_character_memories(memory_id)
        
        # 削除結果レスポンス生成
        response = _convert_character_delete_result_to_response(delete_result, memory_id)
        
        logger.info(f"キャラクター全記憶削除成功: {memory_id}, 削除数: {response.deleted_count}")
        return response
        
    except Exception as e:
        logger.error(f"キャラクター全記憶削除エラー: {memory_id}, {e}")
        
        # 特殊ケース: キャラクターが存在しない場合
        if "not found" in str(e).lower() or "見つかりません" in str(e) or "存在しない" in str(e):
            error_response = ErrorResponse(
                error="character_not_found",
                message=f"キャラクターが見つかりません: {memory_id}",
                details={"memory_id": memory_id}
            )
            return JSONResponse(status_code=404, content=error_response.dict())
        
        error_response = ErrorResponse(
            error="character_memory_delete_failed",
            message=f"キャラクター記憶削除に失敗しました: {memory_id}",
            details={"memory_id": memory_id, "error": str(e)}
        )
        return JSONResponse(status_code=500, content=error_response.dict())