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
    StandardResponse,
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




@router.delete("/memory/character/{memory_id}/all", response_model=StandardResponse)
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
        StandardResponse: 標準成功レスポンス
    """
    try:
        logger.info(f"キャラクター全記憶削除開始: {memory_id}")
        
        # CocoroProductWrapperで記憶削除実行
        app.cocoro_product.delete_character_memories(memory_id)
        
        logger.info(f"キャラクター全記憶削除成功: {memory_id}")
        return StandardResponse(message="記憶を削除しました")
        
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