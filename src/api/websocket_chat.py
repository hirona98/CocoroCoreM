"""
CocoroCore2 WebSocket チャットAPI

WebSocket最適化されたリアルタイムチャット機能
"""

import asyncio
import json
import logging
import re
import uuid
from asyncio import Queue
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, Any

from fastapi import WebSocket, WebSocketDisconnect, Depends, APIRouter
from pydantic import BaseModel

from models.api_models import NotificationData, DesktopContext, ChatRequest, ImageData
from utils.image_processor import generate_image_description, format_image_context_for_chat

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ws", tags=["websocket"])




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
    
    def _log_chunk_debug(self, sse_chunk: str, chunk_count: int):
        """チャンクのデバッグ出力（開発時のみ）"""
        try:
            if not sse_chunk.startswith("data: "):
                return
            
            json_data = sse_chunk[6:].strip()
            if not json_data or json_data == "[DONE]":
                return
            
            chunk_info = json.loads(json_data)
            chunk_type = chunk_info.get("type", "unknown")
            
            if chunk_type == "text":
                content = chunk_info.get("data", "")
                logger.debug(f"[MOSProduct] チャンク{chunk_count}: {content}")
            elif chunk_type == "end":
                logger.debug(f"[MOSProduct] 処理完了: チャンク数={chunk_count}")
            else:
                logger.debug(f"[MOSProduct] {chunk_type}: {json_data}")
                
        except Exception as e:
            logger.debug(f"デバッグ出力エラー: {e}")
    
    
    def _find_last_sentence_boundary(self, buffer: str) -> int:
        """80文字以上のバッファで最後の句読点位置を探す"""
        if len(buffer) < 80:
            return -1
        
        # 日本語文字が含まれているかチェック
        has_japanese = bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]', buffer))
        
        if has_japanese:
            # 日本語文書：主要な句読点のみ
            sentence_endings = re.compile(r'[。？．\n]')
        else:
            # 英語文書：ピリオドと改行のみ
            sentence_endings = re.compile(r'[.\n]')
        
        # バッファ全体で最後の句読点を探す
        matches = list(sentence_endings.finditer(buffer))
        if not matches:
            return -1
        
        # 最後の句読点位置を返す（80文字以上の場合のみ）
        last_match = matches[-1]
        return last_match.end()
    
    async def _flush_text_buffer(self, session_info: dict, websocket: WebSocket, session_id: str, force: bool = False):
        """テキストバッファの内容を送信"""
        buffer = session_info.get("text_buffer", "")
        if not buffer:
            return
        
        if force:
            # 強制送信：バッファ全体を送信
            send_content = buffer
            remaining_buffer = ""
        else:
            # 通常送信：適切な句読点位置を探す
            boundary_pos = self._find_last_sentence_boundary(buffer)
            if boundary_pos == -1:
                # 送信条件を満たさない
                return
            
            # 句読点位置まで送信、残りはバッファに保持
            send_content = buffer[:boundary_pos]
            remaining_buffer = buffer[boundary_pos:]
        
        if send_content:
            # バッファの内容を送信
            ws_message = {
                "session_id": session_id,
                "type": "text",
                "data": {
                    "content": send_content,
                    "is_incremental": True
                }
            }
            
            try:
                await websocket.send_json(ws_message)
                
                # 送信内容をログ表示
                logger.debug(f"[WebSocket送信] 文字数={len(send_content)}, 残り={len(remaining_buffer)}, force={force}")
                logger.info(f"[送信内容] {send_content}")
                if remaining_buffer:
                    logger.debug(f"[残りバッファ] {remaining_buffer}")
                
                # バッファを更新
                session_info["text_buffer"] = remaining_buffer
                session_info["last_send_time"] = asyncio.get_event_loop().time()
                
            except Exception as e:
                logger.error(f"バッファ送信エラー: {e}")
    
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
        
        logger.info(f"チャット開始: session_id={session_id}, query={request_data.get('query', '')}")
        
        # 既存の同一セッションがあれば停止
        if session_id in self.active_sessions:
            self.active_sessions[session_id]["active"] = False
        
        # 新しいセッション開始
        await self._process_chat_stream(websocket, session_id, request_data, app)
    
    async def _process_chat_stream(self, websocket: WebSocket, session_id: str, request_data: dict, app):
        """チャットストリーミング処理（非ブロッキング）"""
        
        # セッション用キューとステータス
        session_queue = Queue(maxsize=50)  # 適度なサイズ
        session_info = {
            "queue": session_queue,
            "active": True,
            "task": None,
            "text_buffer": "",  # テキストバッファリング用
            "last_send_time": asyncio.get_event_loop().time()  # 送信タイムアウト用
        }
        self.active_sessions[session_id] = session_info
        
        try:
            # 通知などにプロンプト追加処理
            enhanced_query = await self._build_enhanced_query(request_data, app)
            
            # メインループのイベントループを取得
            main_loop = asyncio.get_event_loop()
            
            # バックグラウンドでMOSProduct処理を実行
            def mos_product_worker():
                """別スレッドでMOSProduct処理（完全にブロッキング分離）"""
                try:
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
                        
                        # デバッグ出力
                        self._log_chunk_debug(sse_chunk, chunk_count)
                        
                        # キューに結果を追加（完全非同期）
                        try:
                            asyncio.run_coroutine_threadsafe(
                                session_queue.put(sse_chunk),
                                main_loop
                            )
                        except Exception as queue_error:
                            logger.error(f"キュー送信エラー: {queue_error}")
                            break
                        
                        # 終了チェック
                        if '"type": "end"' in sse_chunk:
                            logger.info(f"MOSProduct処理完了: session_id={session_id}, チャンク数={chunk_count}")
                            break
                            
                except Exception as e:
                    logger.error(f"MOSProduct処理エラー: {e}", exc_info=True)
                    # エラーをキューに送信
                    error_chunk = f'data: {{"type": "error", "content": "{str(e)}"}}\n\n'
                    try:
                        asyncio.run_coroutine_threadsafe(
                            session_queue.put(error_chunk),
                            main_loop
                        )
                    except Exception as queue_error:
                        logger.error(f"エラーキュー送信失敗: {queue_error}")
                finally:
                    # 終了マーカー
                    try:
                        asyncio.run_coroutine_threadsafe(
                            session_queue.put(None),  # 終了シグナル
                            main_loop
                        )
                    except Exception as cleanup_error:
                        logger.error(f"終了マーカー送信失敗: {cleanup_error}")
            
            # 別スレッドでMOSProduct処理開始
            session_info["task"] = self.executor.submit(mos_product_worker)
            
            # 軽量プロキシ：キューからの読み取りとバッファリング送信
            sent_count = 0
            buffer_timeout = 2.0  # バッファタイムアウト（秒）
            
            while session_info["active"]:
                try:
                    # キューから取得（タイムアウト付き）
                    sse_chunk = await asyncio.wait_for(session_queue.get(), timeout=0.1)
                    
                    if sse_chunk is None:  # 終了シグナル
                        logger.info(f"終了シグナル受信: session_id={session_id}")
                        # 残りバッファを強制送信
                        await self._flush_text_buffer(session_info, websocket, session_id, force=True)
                        break
                    
                    # WebSocketメッセージに変換
                    ws_message = self._convert_sse_to_websocket(sse_chunk, session_id)
                    if not ws_message:
                        continue
                    
                    message_type = ws_message.get("type")
                    
                    if message_type == "text":
                        # textタイプはバッファに蓄積
                        content = ws_message.get("data", {}).get("content", "")
                        session_info["text_buffer"] += content
                        
                        # バッファ送信判定
                        await self._flush_text_buffer(session_info, websocket, session_id)
                        
                    elif message_type == "end":
                        # 終了時は残りバッファを強制送信してからendを送信
                        await self._flush_text_buffer(session_info, websocket, session_id, force=True)
                        await websocket.send_json(ws_message)
                        logger.debug(f"[WebSocket送信] {message_type}タイプ: {ws_message.get('data', {})}")
                        sent_count += 1
                        
                    else:
                        # 非textタイプ（status, reference, time, error等）は即座に送信
                        await websocket.send_json(ws_message)
                        logger.debug(f"[WebSocket送信] {message_type}タイプ: {ws_message.get('data', {})}")
                        sent_count += 1
                        
                except asyncio.TimeoutError:
                    # タイムアウト時：バッファタイムアウトチェック
                    current_time = asyncio.get_event_loop().time()
                    if (session_info["text_buffer"] and 
                        current_time - session_info["last_send_time"] > buffer_timeout):
                        logger.debug(f"バッファタイムアウト: {buffer_timeout}秒経過")
                        await self._flush_text_buffer(session_info, websocket, session_id, force=True)
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
    
    async def _build_enhanced_query(self, request_data: dict, app) -> str:
        """画像処理と拡張クエリ構築（非同期）"""
        base_query = request_data.get("query", "")
        chat_type = request_data.get("chat_type", "text")
        images = request_data.get("images")
        
        # 画像処理が必要な場合
        if images:
            try:
                logger.info(f"画像処理開始: {len(images)}枚の画像")
                
                # 画像説明を生成（MemOSを使わずに直接LLM呼び出し）
                image_description = await generate_image_description(images, app.cocoro_product.cocoro_config)
                
                if image_description:
                    # 画像付き通知の場合
                    if chat_type == "notification":
                        notification = request_data.get("notification", {})
                        source = notification.get('original_source', '不明なアプリ')
                        original_msg = notification.get('original_message', '')
                        
                        enhanced_query = self._build_notification_with_image_prompt(
                            source, original_msg, image_description
                        )
                        logger.info(f"画像付き通知処理完了: 説明生成成功")
                        return enhanced_query
                    
                    # 画像付きチャット
                    else:
                        enhanced_query = format_image_context_for_chat(image_description, base_query)
                        logger.info(f"画像処理完了: 説明生成成功")
                        return enhanced_query
                else:
                    # 画像説明生成失敗時
                    logger.warning("画像説明の生成に失敗しました。テキストのみで処理を継続します。")
                    return await self._handle_image_processing_error(
                        request_data, chat_type, base_query, app,
                        f"\n\n【画像情報】\n{len(images)}枚の画像が添付されていますが、画像の分析に失敗しました。"
                    )
                    
            except Exception as e:
                logger.error(f"画像処理エラー: {e}")
                return await self._handle_image_processing_error(
                    request_data, chat_type, base_query, app,
                    f"\n\n【画像情報】\n{len(images)}枚の画像が添付されていますが、画像の分析でエラーが発生しました。"
                )
        
        # 画像なし通知の場合
        if chat_type == "notification" and request_data.get("notification"):
            notification = request_data["notification"]
            source = notification.get('original_source', '不明なアプリ')
            original_msg = notification.get('original_message', '')
            
            # 画像なし通知：直接プロンプト構築
            return self._build_notification_prompt(source, original_msg)
        
        # デスクトップ監視の場合
        if chat_type == "desktop_watch" and request_data.get("desktop_context"):
            desktop_context = request_data["desktop_context"]
            app_name = desktop_context.get('application', '不明')
            window_title = desktop_context.get('window_title', '')
            base_query = f"【デスクトップ監視】{app_name}で作業中\nウィンドウタイトル: {window_title}\n\n{base_query}"
        
        return base_query
    
    async def _handle_image_processing_error(self, request_data: dict, chat_type: str, base_query: str, app, error_msg: str) -> str:
        """画像処理エラー時の処理を共通化"""
        if chat_type == "notification":
            notification = request_data.get("notification", {})
            source = notification.get('original_source', '不明なアプリ')
            original_msg = notification.get('original_message', '')
            return self._build_notification_prompt(source, original_msg) + error_msg
        
        return base_query + error_msg
    
    def _build_notification_prompt(self, notification_source: str, original_message: str) -> str:
        """通知用独り言プロンプトを構築"""
        return (
            f"{notification_source}からの通知です。\n\n"
            f"通知内容: {original_message}\n\n"
            "以下の形式で、あなたの**キャラクター性を活かして**ユーザーに伝えてください：\n"
            "- 通知元と通知内容を含める\n"
            "- 最後に感想や意見を加える\n"
            "- 質問形式にしない\n"
            "- 2～3文で完結させる\n\n"
            "例：\n"
            " LINEでメッセージが来たよ。返事しなきゃね。\n"
            " Slackから会議の通知がありました。準備しましょう。\n"
            " Twitterで誰かがリプライしてる。何かなぁ。"
        )

    def _build_notification_with_image_prompt(self, notification_source: str, original_message: str, image_description: str) -> str:
        """画像付き通知用独り言プロンプトを構築"""
        return (
            f"{notification_source}からの通知で、画像が含まれています。\n\n"
            f"通知内容: {original_message}\n"
            f"画像内容: {image_description}\n\n"
            "以下の形式で、あなたの**キャラクター性を自然に活かして**ユーザーに伝えてください：\n"
            "- 通知元と通知内容を含める\n"
            "- 画像の内容についても軽く触れる（複数枚ある場合は総括して触れる）\n"
            "- 最後に感想や意見を加える\n"
            "- 質問形式にしない\n"
            "- 2～3文で完結させる\n\n"
            "例：\n"
            " LINEから写真が送られてきたよ。美味しそうな料理だね。\n"
            " Slackからプロジェクトの進捗報告がありました。順調そうで良かったですね。\n"
            " Twitterのトレンド通知で桜の写真が来てる。もう春なんだなぁ。"
        )


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
            logger.warning(f"JSON解析エラー: {e}, chunk: {sse_chunk}")
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