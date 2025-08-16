# チャットストリーミングAPI実装設計書

## 概要

CocoroCore2の`/api/chat/stream`エンドポイント実装について、CocoroDockとの統合を考慮した詳細設計を記載します。

## 実装仕様

### 3. 実装詳細

#### 3.2 軽量チャットエンドポイント実装 (`api/chat.py`)

**⚠️ 大幅簡略化** - MemOSの出力をそのまま転送:

```python
"""
CocoroCore2 チャットAPI - MemOS直接統合版
"""

import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from models.chat_models import ChatRequest
from core.image_analyzer import ImageAnalyzer

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
    """
    
    async def generate_stream() -> AsyncIterator[str]:
        try:
            # 1. cube_idの自動決定（Setting.jsonから）
            current_character = app.config.current_character
            if not current_character:
                raise ValueError("現在のキャラクターが設定されていません")
            cube_id = f"user_{current_character.userId}_cube"
            
            # 2. 画像分析（必要時）
            enhanced_query = request.query
            if request.images and len(request.images) > 0:
                analyzer = ImageAnalyzer(app.config)
                analyzed_images = await analyzer.analyze_images(
                    [img.data for img in request.images]
                )
                enhanced_query = _build_enhanced_query(request, analyzed_images)
            else:
                enhanced_query = _build_enhanced_query(request)
            
            # 3. MemOSから直接SSE形式で出力を取得・転送
            async for sse_chunk in app.cocoro_product.chat_with_references(
                query=enhanced_query,
                cube_id=cube_id,
                history=request.history,
                internet_search=request.internet_search or False
            ):
                # MemOSの出力は既にSSE形式 - そのまま転送
                yield sse_chunk
            
        except Exception as e:
            logger.error(f"チャットストリーミングエラー: {e}")
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

def _build_enhanced_query(request: ChatRequest, analyzed_images=None) -> str:
    """チャットタイプに応じて拡張クエリを構築"""
    base_query = request.query
    
    # 通知コンテキスト追加
    if request.chat_type == "notification" and request.notification:
        base_query = f"【{request.notification.from_}からの通知】{request.notification.original_message}\n\n{base_query}"
    
    # デスクトップ監視コンテキスト追加
    elif request.chat_type == "desktop_watch" and request.desktop_context:
        base_query = f"【デスクトップ監視】{request.desktop_context.application}で作業中\nウィンドウタイトル: {request.desktop_context.window_title}\n\n{base_query}"
    
    # 画像分析結果追加
    if analyzed_images:
        image_descriptions = "\n".join([
            f"画像{i+1}: {img.get('description', '解析情報なし')}" 
            for i, img in enumerate(analyzed_images)
        ])
        base_query = f"{base_query}\n\n【画像情報】\n{image_descriptions}"
    
    return base_query
```

#### 3.4 画像分析実装 (`core/image_analyzer.py`)

```python
"""
CocoroCore2 画像分析機能
"""

import asyncio
import base64
import logging
from typing import List, Dict, Any
from io import BytesIO

from PIL import Image
import openai

logger = logging.getLogger(__name__)

class ImageAnalyzer:
    """画像分析クラス"""
    
    def __init__(self, config):
        self.config = config
        
        # Vision LLM設定
        current_char = config.current_character
        self.vision_model = current_char.visionModel if current_char else "gpt-4o-mini"
        self.vision_api_key = current_char.visionApiKey or current_char.apiKey if current_char else ""
        
        # OpenAIクライアント初期化
        self.client = openai.AsyncOpenAI(api_key=self.vision_api_key)
    
    async def analyze_images(self, image_data_urls: List[str]) -> List[Dict[str, Any]]:
        """
        複数画像の分析
        
        Args:
            image_data_urls: Base64 data URL配列
            
        Returns:
            List[Dict]: 分析結果配列
        """
        if not self.vision_api_key:
            logger.warning("Vision APIキーが設定されていません")
            return []
        
        tasks = []
        for i, data_url in enumerate(image_data_urls[:5]):  # 最大5枚制限
            tasks.append(self._analyze_single_image(data_url, i))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # エラーハンドリング
        analyzed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"画像{i+1}の分析に失敗: {result}")
                analyzed_results.append({
                    "image_index": i,
                    "error": str(result),
                    "description": "画像の分析に失敗しました"
                })
            else:
                analyzed_results.append(result)
        
        return analyzed_results
    
    async def _analyze_single_image(self, data_url: str, index: int) -> Dict[str, Any]:
        """単一画像の分析"""
        try:
            # データURL検証とフォーマット
            if not data_url.startswith("data:image/"):
                raise ValueError("無効な画像データURL形式")
            
            # Vision LLMで画像分析
            response = await self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "この画像の内容を簡潔に日本語で説明してください。重要な要素、文字、人物、物体などを含めて説明してください。"
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": data_url}
                            }
                        ]
                    }
                ],
                max_tokens=500
            )
            
            description = response.choices[0].message.content
            
            return {
                "image_index": index,
                "description": description,
                "model_used": self.vision_model,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"画像分析エラー: {e}")
            raise
```


## 実装優先度

### フェーズ2: 画像対応 🎯
5. **`core/image_analyzer.py`**: Vision LLM統合
6. **画像処理の統合**: text_imageチャット完全対応

### フェーズ3: 特殊機能 🔧
7. **notificationチャット**: 通知処理の完全実装
8. **desktop_watchチャット**: デスクトップ監視の統合
