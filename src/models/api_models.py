"""
CocoroCore2 API データモデル

FastAPI用のリクエスト/レスポンスモデル定義
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class StandardResponse(BaseModel):
    """標準成功レスポンス"""
    success: bool = True
    message: str = "成功"
    data: Optional[Dict] = None


class ErrorResponse(BaseModel):
    """エラーレスポンス"""
    success: bool = False
    error: str
    message: str
    details: Optional[Dict] = None


class HealthCheckResponse(BaseModel):
    """ヘルスチェックレスポンス"""
    status: str = "healthy"
    version: str = "1.0.0"
    character: str = "つくよみちゃん"
    memory_enabled: bool = True
    llm_model: str = "gpt-4o-mini"
    active_sessions: int = 1
    mcp_status: Dict = Field(default_factory=lambda: {
        "total_servers": 0,
        "connected_servers": 0,
        "total_tools": 0
    })
    neo4j_status: Optional[Dict] = None


class UsersListResponse(BaseModel):
    """ユーザーリストレスポンス"""
    success: bool = True
    users: List[Dict]


class UserInfoResponse(BaseModel):
    """ユーザー情報レスポンス"""
    success: bool = True
    user_info: Dict


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


class MemOSChatRequest(BaseModel):
    """MemOSチャットリクエスト"""
    query: str = Field(..., description="ユーザークエリ")
    user_id: str = Field(..., description="ユーザーID")
    context: Optional[ImageContext] = Field(None, description="コンテキスト情報")
    cube_id: Optional[str] = Field(None, description="メモリキューブID")
    history: Optional[List[Dict]] = Field(None, description="会話履歴")
    internet_search: Optional[bool] = Field(False, description="インターネット検索を有効にするか")


class SystemControlRequest(BaseModel):
    """システム制御リクエスト"""
    action: str = Field(..., description="制御アクション")