"""
CocoroCore2 API データモデル

FastAPI用のリクエスト/レスポンスモデル定義
"""

from typing import Dict, List, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field


class StandardResponse(BaseModel):
    """標準成功レスポンス"""
    status: str = "success"
    message: str = "成功"


class ErrorResponse(BaseModel):
    """エラーレスポンス"""
    success: bool = False
    error: str
    message: str
    details: Optional[Dict] = None


class HealthCheckResponse(BaseModel):
    """ヘルスチェックレスポンス"""
    status: str = "healthy"


class MemorysListResponse(BaseModel):
    """ユーザーリストレスポンス"""
    success: bool = True
    memorys: List[Dict]


class MemoryInfoResponse(BaseModel):
    """ユーザー情報レスポンス"""
    success: bool = True
    memory_info: Dict


class MemoryStatsResponse(BaseModel):
    """記憶統計レスポンス"""
    success: bool = True
    stats: Dict


class MemoryDeleteResponse(BaseModel):
    """記憶削除結果レスポンス"""
    success: bool = True
    message: str = "記憶を削除しました"
    deleted_count: int = 0


class ImageContext(BaseModel):
    """画像コンテキスト"""
    source_type: str = Field(..., description="chat|notification|desktop_monitoring")
    images: List[str] = Field(default_factory=list, description="Base64画像配列")
    notification_from: Optional[str] = Field(None, description="通知元（通知時のみ）")


class SystemControlRequest(BaseModel):
    """システム制御リクエスト"""
    action: str = Field(..., description="制御アクション")
    params: Optional[Dict] = Field(default_factory=dict, description="パラメータ")
    reason: Optional[str] = Field(None, description="実行理由")


# ===========================================
# チャットAPI用モデル定義
# ===========================================

class ImageData(BaseModel):
    """画像データ"""
    data: str = Field(..., description="Base64 data URL形式の画像データ")


class NotificationData(BaseModel):
    """通知データ"""
    original_source: str = Field(..., alias="from", description="通知送信元")
    original_message: str = Field(..., description="元の通知メッセージ")


class DesktopContext(BaseModel):
    """デスクトップ監視コンテキスト"""
    window_title: str = Field(..., description="ウィンドウタイトル")
    application: str = Field(..., description="アプリケーション名")
    capture_type: Literal["active", "full"] = Field(..., description="キャプチャタイプ")
    timestamp: str = Field(..., description="キャプチャ時刻（ISO形式）")


class HistoryMessage(BaseModel):
    """会話履歴メッセージ"""
    role: Literal["user", "assistant"] = Field(..., description="メッセージの役割")
    content: str = Field(..., description="メッセージ内容")
    timestamp: str = Field(..., description="メッセージ時刻（ISO形式）")


class ChatRequest(BaseModel):
    """チャットAPIリクエスト"""
    query: str = Field(..., description="ユーザークエリ")
    chat_type: Literal["text", "text_image", "notification", "desktop_watch"] = Field(..., description="チャットタイプ")
    images: Optional[List[ImageData]] = Field(default=None, description="画像データ配列")
    notification: Optional[NotificationData] = Field(default=None, description="通知データ")
    desktop_context: Optional[DesktopContext] = Field(default=None, description="デスクトップコンテキスト")
    history: Optional[List[HistoryMessage]] = Field(default=None, description="会話履歴")
    internet_search: Optional[bool] = Field(default=False, description="インターネット検索有効化")
    request_id: Optional[str] = Field(default=None, description="リクエスト識別ID")


# ===========================================
# キャラクター別メモリ管理API用モデル定義
# ===========================================

class CharacterMemoryInfo(BaseModel):
    """キャラクターメモリ情報"""
    memory_id: str = Field(..., description="メモリID（キャラクターのmemoryId）")  
    memory_name: str = Field(..., description="キャラクター名")
    role: str = Field("character", description="役割（character固定）")
    created: bool = Field(True, description="作成状態")


class CharacterListResponse(BaseModel):
    """キャラクター一覧レスポンス - CocoroDock互換"""
    status: str = Field("success", description="ステータス")
    message: str = Field("キャラクター一覧を取得しました", description="メッセージ")
    data: List[CharacterMemoryInfo] = Field(default_factory=list, description="キャラクター一覧")




