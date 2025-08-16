"""
CocoroCore2 WebSocket チャットAPI

WebSocket最適化されたリアルタイムチャット機能
"""

import asyncio
import json
import logging
import uuid
from asyncio import Queue
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, Any
from pathlib import Path

from fastapi import WebSocket, WebSocketDisconnect, Depends, APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ws", tags=["websocket"])


class ChatRequest(BaseModel):
    """WebSocketチャットリクエスト"""
    query: str
    chat_type: str = "text"  # "text", "text_image", "notification", "desktop_watch"
    images: Optional[list] = None
    history: Optional[list] = None
    internet_search: bool = False


class WebSocketMessage(BaseModel):
    """WebSocketメッセージ基本形式"""
    action: str
    session_id: str
    request: Optional[ChatRequest] = None



class WebSocketChatManager:
    """WebSocketチャット管理クラス"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.active_sessions: Dict[str, dict] = {}  # session_id -> session_data
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="MOSProduct")
        logger.info("WebSocketChatManager初期化完了")
    
    async def connect(self, client_id: str, websocket: WebSocket):
        """WebSocket接続処理"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket接続確立: client_id={client_id}")
    
    def disconnect(self, client_id: str):
        """WebSocket切断処理"""
        # 接続を削除
        self.active_connections.pop(client_id, None)
        
        # 該当クライアントのセッションを無効化
        sessions_to_stop = [s for s in self.active_sessions if s.startswith(f"{client_id}_")]
        for session_id in sessions_to_stop:
            session_info = self.active_sessions.get(session_id)
            if session_info:
                session_info["active"] = False
                # 実行中のタスクをキャンセル
                if session_info.get("task") and not session_info["task"].done():
                    session_info["task"].cancel()
        
        logger.info(f"WebSocket切断処理完了: client_id={client_id}, 停止セッション数={len(sessions_to_stop)}")
    
    async def handle_message(self, client_id: str, message: dict, app):
        """WebSocketメッセージ処理"""
        websocket = self.active_connections.get(client_id)
        if not websocket:
            logger.warning(f"接続が見つかりません: client_id={client_id}")
            return
        
        try:
            action = message.get("action")
            
            if action == "chat":
                await self._handle_chat_action(websocket, client_id, message, app)
            else:
                await self._send_error(websocket, None, f"未知のアクション: {action}")
                
        except Exception as e:
            logger.error(f"メッセージ処理エラー: {e}", exc_info=True)
            await self._send_error(websocket, message.get("session_id"), str(e))
    
    async def _handle_chat_action(self, websocket: WebSocket, client_id: str, message: dict, app):
        """チャットアクション処理"""
        session_id = message.get("session_id")
        if not session_id:
            session_id = f"{client_id}_{uuid.uuid4().hex[:8]}"
        
        request_data = message.get("request", {})
        
        logger.info(f"チャット開始: session_id={session_id}, query={request_data.get('query', '')[:50]}...")
        
        # 既存の同一セッションがあれば停止
        if session_id in self.active_sessions:
            self.active_sessions[session_id]["active"] = False
        
        # 新しいセッション開始
        await self._process_chat_stream(websocket, session_id, request_data, app)
    
    async def _process_chat_stream(self, websocket: WebSocket, session_id: str, request_data: dict, app):
        """チャットストリーミング処理（非ブロッキング）"""
        
        # セッション用キューとステータス
        session_queue = Queue(maxsize=100)
        session_info = {
            "queue": session_queue,
            "active": True,
            "task": None
        }
        self.active_sessions[session_id] = session_info
        
        try:
            # メインループのイベントループを取得
            main_loop = asyncio.get_event_loop()
            
            # バックグラウンドでMOSProduct処理を実行
            def mos_product_worker():
                """別スレッドでMOSProduct処理（完全にブロッキング分離）"""
                try:
                    # 拡張クエリ構築
                    enhanced_query = self._build_enhanced_query(request_data)
                    cube_id = app.cocoro_product.get_current_cube_id()
                    
                    logger.info(f"MOSProduct処理開始: session_id={session_id}, cube_id={cube_id}")
                    
                    # MOSProductのストリーミング処理（同期処理）
                    chunk_count = 0
                    for sse_chunk in app.cocoro_product.mos_product.chat_with_references(
                        query=enhanced_query,
                        user_id="user",
                        cube_id=cube_id,
                        history=request_data.get("history"),
                        internet_search=request_data.get("internet_search", False)
                    ):
                        chunk_count += 1
                        
                        # キューに結果を追加（メインループ指定）
                        future = asyncio.run_coroutine_threadsafe(
                            session_queue.put(sse_chunk),
                            main_loop
                        )
                        future.result(timeout=1.0)  # タイムアウト付き待機
                        
                        # 終了チェック
                        if '"type": "end"' in sse_chunk:
                            logger.info(f"MOSProduct処理完了: session_id={session_id}, チャンク数={chunk_count}")
                            break
                            
                except Exception as e:
                    logger.error(f"MOSProduct処理エラー: {e}", exc_info=True)
                    # エラーをキューに送信
                    error_chunk = f'data: {{"type": "error", "content": "{str(e)}"}}\n\n'
                    try:
                        future = asyncio.run_coroutine_threadsafe(
                            session_queue.put(error_chunk),
                            main_loop
                        )
                        future.result(timeout=1.0)
                    except Exception as queue_error:
                        logger.error(f"エラーキュー送信失敗: {queue_error}")
                finally:
                    # 終了マーカー
                    try:
                        future = asyncio.run_coroutine_threadsafe(
                            session_queue.put(None),  # 終了シグナル
                            main_loop
                        )
                        future.result(timeout=1.0)
                    except Exception as cleanup_error:
                        logger.error(f"終了マーカー送信失敗: {cleanup_error}")
            
            # 別スレッドでMOSProduct処理開始
            session_info["task"] = self.executor.submit(mos_product_worker)
            
            # 軽量プロキシ：キューからの読み取りとWebSocket送信
            sent_count = 0
            while session_info["active"]:
                try:
                    # キューから取得（タイムアウト付き）
                    sse_chunk = await asyncio.wait_for(session_queue.get(), timeout=0.1)
                    
                    if sse_chunk is None:  # 終了シグナル
                        logger.info(f"終了シグナル受信: session_id={session_id}")
                        break
                    
                    # WebSocketメッセージに変換して送信
                    ws_message = self._convert_sse_to_websocket(sse_chunk, session_id)
                    if ws_message:
                        await websocket.send_json(ws_message)
                        sent_count += 1
                        
                except asyncio.TimeoutError:
                    # タイムアウト時は継続（keep-alive不要）
                    continue
                except Exception as e:
                    logger.error(f"プロキシ処理エラー: {e}")
                    break
            
            logger.info(f"プロキシ処理完了: session_id={session_id}, 送信メッセージ数={sent_count}")
            
        finally:
            # セッションクリーンアップ
            session_info["active"] = False
            self.active_sessions.pop(session_id, None)
            
            # タスクのクリーンアップ
            if session_info.get("task") and not session_info["task"].done():
                session_info["task"].cancel()
    
    def _build_enhanced_query(self, request_data: dict) -> str:
        """拡張クエリ構築（既存のchat.pyロジックを流用）"""
        base_query = request_data.get("query", "")
        chat_type = request_data.get("chat_type", "text")
        
        # 通知コンテキスト追加
        if chat_type == "notification" and request_data.get("notification"):
            notification = request_data["notification"]
            base_query = f"【{notification.get('from_')}からの通知】{notification.get('original_message')}\n\n{base_query}"
        
        # デスクトップ監視コンテキスト追加  
        elif chat_type == "desktop_watch" and request_data.get("desktop_context"):
            desktop_context = request_data["desktop_context"]
            base_query = f"【デスクトップ監視】{desktop_context.get('application')}で作業中\nウィンドウタイトル: {desktop_context.get('window_title')}\n\n{base_query}"
        
        # 画像分析結果追加（将来の実装用）
        if chat_type == "text_image" and request_data.get("images"):
            image_count = len(request_data["images"])
            base_query = f"{base_query}\n\n【画像情報】\n{image_count}枚の画像が添付されています（分析機能は実装予定）"
        
        return base_query
    
    def _convert_sse_to_websocket(self, sse_chunk: str, session_id: str) -> Optional[dict]:
        """SSE形式をWebSocketメッセージに変換"""
        if not sse_chunk.startswith("data: "):
            return None
        
        try:
            # "data: " プレフィックスを除去
            json_str = sse_chunk[6:].strip()
            if not json_str:
                return None
            
            mos_data = json.loads(json_str)
            message_type = mos_data.get("type")
            
            # メッセージタイプ別にデータ構造を適切に変換
            if message_type == "text":
                # textタイプの場合、contentとis_incrementalを含むオブジェクトとして構造化
                data = {
                    "content": mos_data.get("data", ""),
                    "is_incremental": True
                }
            elif message_type == "error":
                # errorタイプの場合、messageとcodeを含むオブジェクトとして構造化
                data = {
                    "message": mos_data.get("content", str(mos_data.get("data", ""))),
                    "code": "PROCESSING_ERROR"
                }
            elif message_type == "reference":
                # referenceタイプの場合、参照リストを構造化
                data = {
                    "references": mos_data.get("data", [])
                }
            elif message_type == "time":
                # timeタイプの場合、時間情報を構造化
                time_data = mos_data.get("data", {})
                data = {
                    "total_time": time_data.get("total_time", 0.0),
                    "speed_improvement": time_data.get("speed_improvement", "")
                }
            elif message_type == "end":
                # endタイプの場合、最終情報を構造化
                end_data = mos_data.get("data", {})
                data = {
                    "total_tokens": end_data.get("total_tokens", 0),
                    "final_text": end_data.get("final_text", "")
                }
            else:
                # その他のタイプの場合は生データをそのまま使用
                data = mos_data.get("data") or mos_data.get("content")
            
            # WebSocket形式に変換
            message = {
                "session_id": session_id,
                "type": message_type,
                "data": data
            }
            
            return message
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析エラー: {e}, chunk: {sse_chunk[:100]}")
            return None
    
    async def _send_error(self, websocket: WebSocket, session_id: Optional[str], error_message: str):
        """エラーメッセージ送信"""
        try:
            await websocket.send_json({
                "session_id": session_id or "unknown",
                "type": "error",
                "data": {
                    "message": error_message,
                    "code": "PROCESSING_ERROR"
                }
            })
        except Exception as e:
            logger.error(f"エラーメッセージ送信失敗: {e}")
    
    def shutdown(self):
        """シャットダウン処理"""
        logger.info("WebSocketChatManager シャットダウン開始")
        
        # 全セッションを停止
        for session_id, session_info in self.active_sessions.items():
            session_info["active"] = False
            if session_info.get("task") and not session_info["task"].done():
                session_info["task"].cancel()
        
        # スレッドプールをシャットダウン
        self.executor.shutdown(wait=True, timeout=5.0)
        
        logger.info("WebSocketChatManager シャットダウン完了")


# グローバルマネージャー
chat_manager = WebSocketChatManager()


@router.websocket("/chat/{client_id}")
async def websocket_chat(client_id: str, websocket: WebSocket):
    """WebSocketチャットエンドポイント"""
    await chat_manager.connect(client_id, websocket)
    
    try:
        # FastAPIのstate経由でアプリケーションインスタンスを取得
        app = getattr(websocket.app.state, 'core_app', None)
        if app is None:
            logger.error("アプリケーションインスタンスが見つかりません")
            await websocket.close(code=1011, reason="アプリケーション初期化エラー")
            return
        
        while True:
            # メッセージ受信
            message = await websocket.receive_json()
            await chat_manager.handle_message(client_id, message, app)
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket正常切断: client_id={client_id}")
    except Exception as e:
        logger.error(f"WebSocketエラー: client_id={client_id}, error={e}", exc_info=True)
    finally:
        chat_manager.disconnect(client_id)


def get_websocket_manager() -> WebSocketChatManager:
    """WebSocketマネージャー取得（シャットダウン用）"""
    return chat_manager