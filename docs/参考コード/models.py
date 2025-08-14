"""
CocoroCore2 画像処理関連のデータモデル
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional


@dataclass
class ImageAnalysisResult:
    """画像分析結果のデータクラス"""
    description: str     # 詳細説明
    category: str       # カテゴリ分類
    mood: str          # 雰囲気
    time: str          # 時間帯  # フォールバック結果かどうか


@dataclass
class ImageContext:
    """画像のコンテキスト情報"""
    source_type: Literal["chat", "notification", "desktop_monitoring"]
    notification_from: Optional[str] = None
    timestamp: Optional[datetime] = None