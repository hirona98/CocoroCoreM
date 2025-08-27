"""
CocoroCoreM Server-Sent Events (SSE) サポート

ストリーミングレスポンス用ヘルパー
"""

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SSEHelper:
    """Server-Sent Events ヘルパークラス"""
    
    @staticmethod
    def format_data(data: Any, event_type: str = "text") -> str:
        """
        SSE形式でデータをフォーマット
        
        Args:
            data: 送信するデータ
            event_type: イベントタイプ
            
        Returns:
            str: SSE形式の文字列
        """
        try:
            if isinstance(data, str):
                payload = {"type": event_type, "data": data}
            else:
                payload = {"type": event_type, "data": data}
            
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.error(f"SSE形式変換エラー: {e}")
            return SSEHelper.format_error("データ形式変換に失敗しました")
    
    @staticmethod
    def format_error(error_message: str) -> str:
        """
        エラー用SSE形式
        
        Args:
            error_message: エラーメッセージ
            
        Returns:
            str: エラー用SSE形式の文字列
        """
        try:
            payload = {"type": "error", "data": error_message}
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        except Exception:
            return 'data: {"type": "error", "data": "エラー処理に失敗しました"}\n\n'
    
    @staticmethod
    def format_end() -> str:
        """
        終了用SSE形式
        
        Returns:
            str: 終了用SSE形式の文字列
        """
        try:
            payload = {"type": "end"}
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        except Exception:
            return 'data: {"type": "end"}\n\n'
    
    @staticmethod
    def format_metadata(metadata: Dict) -> str:
        """
        メタデータ用SSE形式
        
        Args:
            metadata: メタデータ辞書
            
        Returns:
            str: メタデータ用SSE形式の文字列
        """
        try:
            payload = {"type": "metadata", "data": metadata}
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"メタデータSSE形式変換エラー: {e}")
            return SSEHelper.format_error("メタデータ変換に失敗しました")