"""
リマインダー管理システム

時間指定リマインダーの管理と実行を行うモジュール
SQLiteでリマインダーを永続化し、時刻になったら通知として送信
"""

import asyncio
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class ReminderManager:
    """リマインダー管理クラス"""
    
    def __init__(self, db_path: str = "UserDataM/reminders.db", app_instance=None):
        """
        初期化
        
        Args:
            db_path: SQLiteデータベースファイルパス
            app_instance: CocoroCoreMAppインスタンス（通知送信に使用）
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.app_instance = app_instance
        self.active_timers: Dict[int, asyncio.Task] = {}
        self._initialize_db()
        logger.info(f"ReminderManager初期化完了: DB={self.db_path}")
    
    @contextmanager
    def _get_db_connection(self):
        """データベース接続のコンテキストマネージャー"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 結果を辞書風にアクセス可能にする
        try:
            yield conn
        finally:
            conn.close()
    
    def _initialize_db(self):
        """データベース初期化"""
        with self._get_db_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    remind_datetime TEXT NOT NULL,
                    requirement TEXT NOT NULL
                )
            """)
            
            # インデックス作成（検索高速化）
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_remind_datetime 
                ON reminders(remind_datetime)
            """)
            conn.commit()
            logger.debug("リマインダーデータベース初期化完了")
    
    async def add_reminder(
        self, 
        datetime_str: str, 
        requirement: str
    ) -> Optional[int]:
        """
        リマインダー追加
        
        Args:
            datetime_str: 日時文字列（YYYY-MM-DD HH:MM:SS）
            requirement: リマインダー要件
            
        Returns:
            リマインダーID（エラー時はNone）
        """
        try:
            # 日時形式の検証
            remind_time = datetime.fromisoformat(datetime_str)
            
            # 過去の時刻チェック
            if remind_time <= datetime.now():
                logger.warning(f"過去の時刻が指定されました: {datetime_str}")
                return None
            
            # データベースに保存
            with self._get_db_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO reminders (remind_datetime, requirement)
                    VALUES (?, ?)
                """, (datetime_str, requirement))
                reminder_id = cursor.lastrowid
                conn.commit()
            
            # タイマー設定
            await self._schedule_reminder(reminder_id, datetime_str, requirement)
            
            logger.info(f"リマインダー登録: ID={reminder_id}, 時刻={datetime_str}, 要件={requirement[:50]}")
            return reminder_id
            
        except ValueError as e:
            logger.error(f"日時形式エラー: {datetime_str} - {e}")
            return None
        except Exception as e:
            logger.error(f"リマインダー追加エラー: {e}", exc_info=True)
            return None
    
    async def _schedule_reminder(
        self, 
        reminder_id: int, 
        datetime_str: str, 
        requirement: str
    ):
        """
        リマインダーのスケジューリング
        
        Args:
            reminder_id: リマインダーID
            datetime_str: 日時文字列
            requirement: リマインダー要件
        """
        try:
            remind_time = datetime.fromisoformat(datetime_str)
            delay = (remind_time - datetime.now()).total_seconds()
            
            if delay > 0:
                # 既存タイマーがあればキャンセル
                if reminder_id in self.active_timers:
                    self.active_timers[reminder_id].cancel()
                
                # 新しいタイマー作成
                task = asyncio.create_task(
                    self._wait_and_trigger(reminder_id, delay, requirement)
                )
                self.active_timers[reminder_id] = task
                logger.debug(f"タイマー設定: ID={reminder_id}, 待機時間={delay:.0f}秒")
            else:
                logger.warning(f"リマインダー時刻が過去: ID={reminder_id}")
                
        except Exception as e:
            logger.error(f"スケジューリングエラー: {e}", exc_info=True)
    
    async def _wait_and_trigger(
        self, 
        reminder_id: int, 
        delay: float, 
        requirement: str
    ):
        """
        指定時間待機してリマインダーをトリガー
        
        Args:
            reminder_id: リマインダーID
            delay: 待機時間（秒）
            requirement: リマインダー要件
        """
        try:
            # 長時間のタイマーを分割（メモリ効率）
            while delay > 3600:  # 1時間以上の場合
                await asyncio.sleep(3600)  # 1時間待機
                delay -= 3600
                
                # リマインダーがまだ存在するか確認
                if not await self._reminder_exists(reminder_id):
                    logger.info(f"リマインダーが削除されました: ID={reminder_id}")
                    return
            
            # 残り時間を待機
            if delay > 0:
                await asyncio.sleep(delay)
            
            # トリガー実行
            await self.trigger_reminder(reminder_id, requirement)
            
        except asyncio.CancelledError:
            logger.info(f"リマインダータイマーキャンセル: ID={reminder_id}")
        except Exception as e:
            logger.error(f"リマインダー待機エラー: {e}", exc_info=True)
    
    async def _reminder_exists(self, reminder_id: int) -> bool:
        """リマインダーが存在するか確認"""
        with self._get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT id FROM reminders WHERE id = ?", 
                (reminder_id,)
            )
            row = cursor.fetchone()
            return row is not None
    
    async def trigger_reminder(
        self, 
        reminder_id: int, 
        requirement: str
    ):
        """
        リマインダーをトリガー（LLMに要件を伝えてメッセージ生成）
        
        Args:
            reminder_id: リマインダーID
            requirement: リマインダー要件
        """
        try:
            logger.info(f"リマインダートリガー開始: ID={reminder_id}, 要件={requirement}")
            
            # リマインダーをデータベースから削除
            with self._get_db_connection() as conn:
                conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
                conn.commit()
            
            # アクティブタイマーから削除
            self.active_timers.pop(reminder_id, None)
            
            # 通知送信処理
            await self._send_reminder_notification(requirement)
            
            logger.info(f"リマインダートリガー完了: ID={reminder_id}")
            
        except Exception as e:
            logger.error(f"リマインダートリガーエラー: {e}", exc_info=True)
    
    async def _send_reminder_notification(self, requirement: str):
        """
        リマインダー通知を専用chat_type "reminder"で送信
        
        Args:
            requirement: リマインダー要件
        """
        try:
            # WebSocket経由でリマインダーを送信
            if not self.app_instance:
                logger.error("アプリインスタンスが利用できません")
                return
                
            from api.websocket_chat import chat_manager
            import uuid
            
            # アクティブなクライアントから最初のものを取得
            active_clients = list(chat_manager.active_connections.keys())
            if not active_clients:
                logger.warning("アクティブなWebSocketクライアントが見つかりません")
                return
                
            # 最初に見つかったクライアントIDを使用
            target_client_id = active_clients[0]
            logger.debug(f"リマインダー送信先クライアント決定: {target_client_id} (全{len(active_clients)}クライアント中)")
            session_id = f"reminder_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            
            # reminder専用リクエストを構築
            reminder_request = {
                "query": "",  # プロンプトから生成
                "chat_type": "reminder",
                "reminder": {
                    "requirement": requirement,
                    "triggered_at": datetime.now().isoformat()
                },
                "internet_search": False
            }
            
            # WebSocketメッセージフォーマット
            ws_message = {
                "action": "chat",
                "session_id": session_id,
                "request": reminder_request
            }
            
            # アクティブなWebSocketクライアントにリマインダーを送信
            await chat_manager.handle_message(
                target_client_id,
                ws_message,
                self.app_instance
            )
            
            logger.info(f"✅ リマインダー送信完了: {requirement} -> クライアント: {target_client_id}")
            
        except ImportError as e:
            logger.error(f"モジュールインポートエラー: {e}")
        except Exception as e:
            logger.error(f"リマインダー送信エラー: {e}", exc_info=True)
    
    async def reload_active_reminders(self):
        """
        起動時にリマインダーを再スケジュール
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, remind_datetime, requirement 
                    FROM reminders 
                    WHERE remind_datetime > datetime('now')
                """)
                
                reminders = cursor.fetchall()
                
            for reminder in reminders:
                await self._schedule_reminder(
                    reminder['id'],
                    reminder['remind_datetime'],
                    reminder['requirement']
                )
            
            logger.info(f"リマインダー再読み込み: {len(reminders)}件")
            
        except Exception as e:
            logger.error(f"リマインダー再読み込みエラー: {e}", exc_info=True)
    
    async def cancel_reminder(self, reminder_id: int) -> bool:
        """
        リマインダーをキャンセル
        
        Args:
            reminder_id: リマインダーID
            
        Returns:
            成功時True
        """
        try:
            # タイマーキャンセル
            if reminder_id in self.active_timers:
                self.active_timers[reminder_id].cancel()
                del self.active_timers[reminder_id]
            
            # データベースから削除
            with self._get_db_connection() as conn:
                conn.execute(
                    "DELETE FROM reminders WHERE id = ?", 
                    (reminder_id,)
                )
                conn.commit()
            
            logger.info(f"リマインダーキャンセル: ID={reminder_id}")
            return True
            
        except Exception as e:
            logger.error(f"キャンセルエラー: {e}", exc_info=True)
            return False
    
    async def get_active_reminders(self) -> List[Dict]:
        """
        アクティブなリマインダーを取得
        
        Returns:
            リマインダーリスト
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM reminders 
                    ORDER BY remind_datetime
                """)
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"リマインダー取得エラー: {e}", exc_info=True)
            return []
    
    async def cleanup_old_reminders(self, days: int = 30):
        """
        過去のリマインダーをクリーンアップ（通常は自動削除されるため不要）
        
        Args:
            days: 保持日数
        """
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            with self._get_db_connection() as conn:
                cursor = conn.execute("""
                    DELETE FROM reminders 
                    WHERE remind_datetime < ?
                """, (cutoff_date,))
                deleted_count = cursor.rowcount
                conn.commit()
            
            logger.info(f"古いリマインダー削除: {deleted_count}件")
            
        except Exception as e:
            logger.error(f"クリーンアップエラー: {e}", exc_info=True)
    
    def shutdown(self):
        """シャットダウン処理"""
        try:
            # すべてのタイマーをキャンセル
            for task in self.active_timers.values():
                task.cancel()
            
            self.active_timers.clear()
            logger.info("ReminderManagerシャットダウン完了")
            
        except Exception as e:
            logger.error(f"シャットダウンエラー: {e}", exc_info=True)