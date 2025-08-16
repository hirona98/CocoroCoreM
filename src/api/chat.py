"""
CocoroCore2 チャットAPI - MemOS直接統合版

MemOSの出力をそのまま転送する軽量実装
"""

import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from models.api_models import ChatRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])

# グローバルアプリケーションインスタンス
_app_instance = None


def get_core_app():
    """CoreAppの依存性注入"""
    global _app_instance
    if _app_instance is None:
        from main import get_app_instance
        _app_instance = get_app_instance()
    return _app_instance


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    app=Depends(get_core_app)
):
    """
    チャットストリーミングエンドポイント
    
    MemOSの出力をそのまま転送 - SSE形式は既に整形済み
    4つのチャットタイプをサポート:
    - text: テキストのみチャット
    - text_image: テキスト+画像チャット（フェーズ2で画像分析追加予定）
    - notification: 通知への反応
    - desktop_watch: デスクトップ監視
    """
    
    async def generate_stream() -> AsyncIterator[str]:
        try:
            # リクエスト検証
            if not app or not hasattr(app, 'cocoro_product') or not app.cocoro_product:
                error_sse = 'data: {"type": "error", "data": "CocoroProduct未初期化"}\n\n'
                yield error_sse
                yield 'data: {"type": "end"}\n\n'
                return
            
            # 事前設定済みのキューブIDを取得（起動時に確実に設定済み）
            try:
                cube_id = app.cocoro_product.get_current_cube_id()
            except RuntimeError as e:
                error_sse = f'data: {{"type": "error", "data": "キューブID取得エラー: {str(e)}"}}\n\n'
                yield error_sse
                yield 'data: {"type": "end"}\n\n'
                return
            
            # 拡張クエリの構築
            enhanced_query = _build_enhanced_query(request)
            
            # MemOSから直接SSE形式で出力を取得・転送
            logger.info(f"チャットストリーミング開始: cube_id={cube_id}, chat_type={request.chat_type}")
            
            async for sse_chunk in app.cocoro_product.chat_with_references(
                query=enhanced_query,
                cube_id=cube_id,
                history=_convert_history_format(request.history) if request.history else None,
                internet_search=request.internet_search or False
            ):
                # MemOSの出力は既にSSE形式（data: {...}\n\n） - そのまま転送
                if sse_chunk and sse_chunk.strip():
                    yield sse_chunk
            
            logger.info(f"チャットストリーミング完了: cube_id={cube_id}")
            
        except Exception as e:
            logger.error(f"チャットストリーミングエラー: {e}", exc_info=True)
            # エラー時のみ手動でSSE形式作成
            error_sse = f'data: {{"type": "error", "data": "チャット処理に失敗しました: {str(e)}"}}\n\n'
            yield error_sse
            yield 'data: {"type": "end"}\n\n'
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # nginx対応
        }
    )


def _build_enhanced_query(request: ChatRequest) -> str:
    """
    チャットタイプに応じて拡張クエリを構築
    
    Args:
        request: チャットリクエスト
        
    Returns:
        str: 拡張されたクエリ
    """
    base_query = request.query
    
    # 通知コンテキスト追加
    if request.chat_type == "notification" and request.notification:
        base_query = f"【{request.notification.from_}からの通知】{request.notification.original_message}\n\n{base_query}"
    
    # デスクトップ監視コンテキスト追加  
    elif request.chat_type == "desktop_watch" and request.desktop_context:
        base_query = f"【デスクトップ監視】{request.desktop_context.application}で作業中\nウィンドウタイトル: {request.desktop_context.window_title}\n\n{base_query}"
    
    # 画像分析結果追加（フェーズ2で実装予定）
    if request.chat_type == "text_image" and request.images:
        # TODO: フェーズ2で画像分析機能を追加
        image_count = len(request.images)
        base_query = f"{base_query}\n\n【画像情報】\n{image_count}枚の画像が添付されています（分析機能は実装予定）"
    
    return base_query


def _convert_history_format(history_messages: list) -> list:
    """
    HistoryMessage形式をMemOS互換形式に変換
    
    Args:
        history_messages: HistoryMessageのリスト
        
    Returns:
        list: MemOS互換形式の履歴
    """
    if not history_messages:
        return []
    
    # HistoryMessageオブジェクトを辞書形式に変換
    converted_history = []
    for msg in history_messages:
        if hasattr(msg, 'dict'):
            # Pydanticモデルの場合
            converted_history.append(msg.dict())
        else:
            # 既に辞書形式の場合
            converted_history.append(msg)
    
    return converted_history