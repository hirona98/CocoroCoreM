# チャットストリーミングAPI実装設計書

## 概要

CocoroCore2の`/api/chat/stream`エンドポイント実装について、CocoroDockとの統合を考慮した詳細設計を記載します。

## 🚨 重要な発見と課題

### エンドポイント

**現状の問題**:
- API仕様書: `/api/chat/stream` 
- CocoroDock実装: `/api/memos/chat/stream`を呼び出している（CocoroCoreClient.cs:328）

**解決策**: 
- `/api/chat/stream`に
- `/api/memos/chat/stream`は**廃止**
- CocoroDockの実装を修正してエンドポイントを変更

### 実装方針の重要な修正

**⚠️ MemOS調査により設計を修正**:

- ❌ **SSEHelper不要**: MemOSが既にSSE形式（`data: {...}\n\n`）で出力
- ✅ **CocoroProductWrapper**: MemOS統合（`src/core/cocoro_product.py`）
- ✅ **FastAPI基盤**: 非同期、依存性注入対応
- ⚠️ **ステータスメッセージ制限**: MemOSは数字コード（`"0"`, `"1"`, `"2"`）のみ提供

## 実装仕様

### 1. APIエンドポイント仕様

#### 1.1 基本情報

**エンドポイント**:
- `POST /api/chat/stream` （新規実装）
- `/api/memos/chat/stream` は**廃止**

**Content-Type**: 
- Request: `application/json`
- Response: `text/event-stream`

#### 1.2 リクエスト形式

##### API仕様 (`/api/chat/stream`)

```json
{
  "query": "今日の予定を教えて",
  "cube_id": "character_123_cube",
  "chat_type": "text",
  "images": [
    {
      "data": "data:image/png;base64,iVBORw0KGgo..."
    }
  ],
  "notification": {
    "from": "LINE",
    "original_message": "写真が送信されました"
  },
  "desktop_context": {
    "window_title": "Visual Studio Code",
    "application": "vscode",
    "capture_type": "active",
    "timestamp": "2025-01-15T10:30:00Z"
  },
  "history": [
    {
      "role": "user",
      "content": "こんにちは",
      "timestamp": "2025-01-15T10:25:00Z"
    }
  ],
  "internet_search": true,
  "request_id": "req_12345"
}
```

**フィールド詳細**:
- `query`: ユーザークエリ（必須）
- `cube_id`: メモリキューブID（必須）
- `chat_type`: チャットタイプ（`text`, `text_image`, `notification`, `desktop_watch`）
- `images`: 画像データ配列（Base64 data URLフォーマット）
- `notification`: 通知データ（chat_type=notification時）
- `desktop_context`: デスクトップコンテキスト（chat_type=desktop_watch時）
- `history`: 会話履歴（オプション）
- `internet_search`: インターネット検索有効化（オプション）
- `request_id`: リクエスト識別ID（オプション）

**注意**: 従来の`/api/memos/chat/stream`は廃止し、上記のAPIを使用してください。

### 2. レスポンス形式（MemOS準拠SSE）

#### 2.1 実際のMemOS出力形式

**⚠️ MemOSが直接出力するSSE形式**:

```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive

data: {"type": "status", "data": "0"}

data: {"type": "text", "data": "こんにちは！"}

data: {"type": "text", "data": "今日はどのような"}

data: {"type": "reference", "data": [...]}

data: {"type": "time", "data": {"total_time": 1.23, "speed_improvement": "15%"}}

data: {"type": "end"}
```

#### 2.2 MemOS実装準拠イベント仕様

**MemOS MOSProduct.chat_with_references()の実際の出力**:

| タイプ | データ形式 | 説明 | 送信タイミング |
|-------|-----------|------|-------------|
| `status` | `"0"`, `"1"`, `"2"` | 数字ステータスコード | 各処理段階で1回 |
| `text` | `"テキストチャンク"` | 応答テキスト文字列 | ストリーミング中継続 |
| `reference` | `[{memory_id, reference_number, ...}]` | 参照記憶配列 | 応答完了後 |
| `time` | `{total_time, speed_improvement}` | 処理時間統計 | 応答完了後 |
| `end` | なし | ストリーム終了 | 最終 |
| `error` | `"エラーメッセージ"` | エラー文字列 | エラー発生時 |

**StatusEvent数字コード**:
- `"0"`: メモリ検索開始
- `"1"`: メモリ検索完了
- `"2"`: LLM応答生成開始

### 3. 実装詳細

#### 3.1 簡略化されたファイル構成

**⚠️ streaming.py は不要** - MemOSが既にSSE形式で出力:

```
CocoroCore2/src/
├── api/
│   └── chat.py                  # 新規作成 - 軽量チャットエンドポイント
├── core/
│   ├── cocoro_product.py        # 既存 - MemOS統合（修正不要）
│   └── image_analyzer.py        # 新規作成 - 画像分析
└── models/
    └── chat_models.py           # 新規作成 - チャット関連モデル
```

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
            # 1. cube_idの自動生成
            cube_id = request.cube_id or f"{request.cube_id}_cube"
            
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

#### 3.3 CocoroDock側の変更が必要

**CocoroCoreClient.cs の修正**:
```csharp
// 変更前: 
var requestUrl = $"{_baseUrl}/api/memos/chat/stream";

// 変更後:
var requestUrl = $"{_baseUrl}/api/chat/stream";
```

**リクエスト形式の調整**:
従来の`MemOSChatRequest`から新しい`ChatRequest`形式に変更が必要です。

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

### 4. CocoroDock側の必要な変更

**⚠️ CocoroDock側の変更が必要**:

1. **CocoroCoreClient.cs の修正**:
   - エンドポイントURL: `/api/memos/chat/stream` → `/api/chat/stream`
   - リクエスト形式: `MemOSChatRequest` → 新API仕様の`ChatRequest`
   
2. **SSE処理**: 既存のStreamReader処理は継続使用可能

3. **段階的移行**:
   - まずCocoroCore2で新APIを実装
   - 次にCocoroDockのエンドポイントとリクエスト形式を変更

### 5. main.pyへの統合

**簡単な1行追加のみ**:

```python
# main.py に追加
from api.chat import router as chat_router

# APIルーター追加部分（initialize()メソッド内）
self.app.include_router(chat_router)
```

## 実装優先度

### フェーズ1: 軽量実装 🔥 **大幅簡略化**
1. **`api/chat.py`**: 軽量エンドポイント実装（MemOS転送のみ）
2. **`models/chat_models.py`**: データモデル定義
3. **main.pyにルーター追加**: 1行のみ追加
4. **CocoroDock修正**: エンドポイントとリクエスト形式変更

### フェーズ2: 画像対応 🎯
5. **`core/image_analyzer.py`**: Vision LLM統合
6. **画像処理の統合**: text_imageチャット完全対応

### フェーズ3: 特殊機能 🔧
7. **notificationチャット**: 通知処理の完全実装
8. **desktop_watchチャット**: デスクトップ監視の統合

## テスト計画

### 単体テスト
- [ ] `ChatRequest`バリデーション
- [ ] SSE形式変換
- [ ] MemOSChatRequest→ChatRequest変換
- [ ] 画像分析エラーハンドリング

## 注意事項とリスク

### 運用リスク  
- **APIキー管理**: セキュアな設定管理が必要
- **ログ機密性**: 画像内容のログ出力制御
- **エラー処理**: 部分的な失敗時の継続処理

## 結論 - 大幅簡略化により超高速実装可能

**⚠️ MemOS調査により設計を根本的に修正**:

✅ **SSEHelper不要**: MemOSが既にSSE形式で出力済み
✅ **軽量実装**: MemOSの出力をそのまま転送するだけ  
✅ **高速開発**: 複雑なSSE形式作成が不要

**移行手順**:
1. CocoroCore2で軽量API実装（MemOS転送のみ）
2. CocoroDockのエンドポイント変更
3. 旧`/api/memos/chat/stream`を完全廃止

**超高速実装可能**: MemOS統合により複雑性を大幅削減