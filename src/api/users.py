"""
CocoroCore2 ユーザー管理API

ユーザー管理とメモリ操作API
"""

import logging
from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, Depends, Path
from fastapi.responses import JSONResponse

from models.api_models import StandardResponse, ErrorResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["users"])

# グローバルアプリケーションインスタンス
_app_instance = None


def get_core_app():
    """CoreAppの依存性注入 - 遅延初期化対応"""
    global _app_instance
    if _app_instance is None:
        from main import get_app_instance
        _app_instance = get_app_instance()
    return _app_instance


@router.get("/users")
async def get_users_list(app=Depends(get_core_app)):
    """
    システムに登録されているユーザーリストを取得
    
    Returns:
        Dict: ユーザーリスト情報
    """
    try:
        # TODO: MOSProductが利用できる場合はそこからユーザー情報を取得
        if app and hasattr(app, 'cocoro_product') and app.cocoro_product:
            try:
                # MemOSからユーザー情報を取得
                users_data = await _get_users_from_memos(app.cocoro_product)
                user_count = len(users_data)
                
                response_data = {
                    "status": "success",
                    "message": f"{user_count}名のユーザーを取得しました",
                    "data": users_data
                }
                
            except Exception as e:
                logger.warning(f"MemOSからのユーザー取得に失敗: {e}")
                # フォールバック: サンプルデータを返す
                users_data = [
                    {
                        "user_id": "550e8400-e29b-41d4-a716-446655440000",
                        "user_name": "デフォルトユーザー"
                    }
                ]
                
                response_data = {
                    "status": "success", 
                    "message": f"{len(users_data)}名のユーザーを取得しました",
                    "data": users_data
                }
        else:
            # MOSProductが利用できない場合のフォールバック
            users_data = [
                {
                    "user_id": "550e8400-e29b-41d4-a716-446655440000",
                    "user_name": "デフォルトユーザー"
                }
            ]
            
            response_data = {
                "status": "success",
                "message": f"{len(users_data)}名のユーザーを取得しました", 
                "data": users_data
            }

        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error(f"ユーザーリスト取得エラー: {e}")
        error_response = ErrorResponse(
            error="users_list_failed",
            message="ユーザーリスト取得に失敗しました",
            details={"error": str(e)}
        )
        return JSONResponse(status_code=500, content=error_response.dict())


@router.delete("/memory/user/{user_id}/all")
async def delete_user_memory(
    user_id: str = Path(..., description="削除対象のユーザーID"),
    app=Depends(get_core_app)
):
    """
    指定ユーザーの全記憶を削除
    
    Args:
        user_id: 削除対象のユーザーID
        
    Returns:
        Dict: 削除結果
    """
    try:
        logger.info(f"ユーザー記憶削除要求: user_id={user_id}")
        
        # TODO: MOSProductが利用できる場合はそこから記憶を削除
        if app and hasattr(app, 'cocoro_product') and app.cocoro_product:
            try:
                # MemOSからユーザー記憶を削除
                deleted_count = await _delete_user_memory_from_memos(app.cocoro_product, user_id)
                
                response_data = {
                    "status": "success",
                    "message": f"ユーザー {user_id} の記憶を削除しました",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
                
                logger.info(f"ユーザー記憶削除完了: user_id={user_id}, deleted_count={deleted_count}")
                
            except Exception as e:
                logger.error(f"MemOSからの記憶削除に失敗: {e}")
                # 削除操作のエラーは重要なので、エラーとして返す
                raise e
        else:
            # MOSProductが利用できない場合
            logger.warning("MOSProductが利用できないため、記憶削除をスキップしました")
            response_data = {
                "status": "success", 
                "message": f"ユーザー {user_id} の記憶削除を実行しました（MOSProduct未初期化）",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error(f"ユーザー記憶削除エラー: user_id={user_id}, error={e}")
        error_response = ErrorResponse(
            error="user_memory_delete_failed",
            message=f"ユーザー {user_id} の記憶削除に失敗しました",
            details={"user_id": user_id, "error": str(e)}
        )
        return JSONResponse(status_code=500, content=error_response.dict())


async def _get_users_from_memos(cocoro_product) -> List[Dict]:
    """MemOSからユーザー情報を取得"""
    try:
        # CocoroProductWrapperからユーザー情報を取得する実装
        # TODO: 現在は簡易実装として設定からユーザーIDを取得
        if hasattr(cocoro_product, 'config') and cocoro_product.config:
            user_id = getattr(cocoro_product.config, 'user_id', 'default_user')
            user_name = getattr(cocoro_product.config, 'character_name', 'ユーザー')
            
            return [
                {
                    "user_id": user_id,
                    "user_name": user_name
                }
            ]
        
        # フォールバック
        return [
            {
                "user_id": "default_user",
                "user_name": "デフォルトユーザー"
            }
        ]
        
    except Exception as e:
        logger.error(f"MemOSユーザー情報取得エラー: {e}")
        raise


async def _delete_user_memory_from_memos(cocoro_product, user_id: str) -> int:
    """MemOSからユーザー記憶を削除"""
    try:
        # TODO: CocoroProductWrapperから記憶削除を実行する実装
        if hasattr(cocoro_product, 'delete_user_memory'):
            deleted_count = await cocoro_product.delete_user_memory(user_id)
            return deleted_count
        else:
            logger.warning("CocoroProductに記憶削除メソッドが実装されていません")
            return 0
            
    except Exception as e:
        logger.error(f"MemOS記憶削除エラー: user_id={user_id}, error={e}")
        raise