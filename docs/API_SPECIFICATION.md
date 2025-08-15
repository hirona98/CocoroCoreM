# CocoroCore2 API 仕様書

## 概要

CocoroCore2は、MemOS統合による高度な記憶機能とリアルタイム応答を実現するCocoroAIのバックエンドシステムです。
このドキュメントは、CocoroCore2が提供するAPIエンドポイントの詳細な仕様をまとめています。

## エンドポイント一覧

### ヘルスチェック

#### `GET /health`

システムの稼働状態を確認します。

**リクエスト**
```
GET /api/health
```

**レスポンス**
```json
{
  "status": "healthy"
}
```

**フィールド説明**
- `status`: システム状態（"healthy", "error"）

---

### システム制御

#### `POST /api/control`

システムの制御コマンドを実行します。

**リクエスト**
```json
{
  "action": "shutdown",
  "params": {},
  "reason": "管理者による停止"
}
```

**レスポンス**
```json
{
  "status": "success",
  "message": "システム終了要求を受け付けました。"
}
```

**サポートするコマンド**
- `shutdown`: システム終了
- `start_log_forwarding`: ログ転送開始
- `stop_log_forwarding`: ログ転送停止

---

### MCPツール登録ログ取得

#### `GET /api/mcp/tool-registration-log`

MCPツールの登録ログを取得します（現在未実装）。

**リクエスト**
```
GET /api/mcp/tool-registration-log
```

**レスポンス**
```json
{
  "status": "success",
  "message": "MCPは現在実装されていません",
  "logs": [],
  "timestamp": "2025-01-01T12:00:00Z"
}
```

---

### チャットAPI

#### `POST /api/chat/stream`

CocoroDockからのチャットリクエストを処理し、ストリーミング形式で応答を返します。

**リクエスト**
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

**フィールド説明**
- `query`: ユーザークエリ（必須）
- `cube_id`: メモリキューブID（必須）
- `chat_type`: チャットタイプ（必須）
  - `text`: テキストのみチャット
  - `text_image`: テキスト+画像チャット
  - `notification`: 通知への反応
  - `desktop_watch`: デスクトップ監視
- `images`: 画像データ配列（chat_type=text_image/notification/desktop_watch時）
- `notification`: 通知データ（chat_type=notification時）
- `desktop_context`: デスクトップコンテキスト（chat_type=desktop_watch時）
- `history`: 会話履歴（オプション）
- `internet_search`: インターネット検索の有効化（オプション）
- `request_id`: リクエスト識別ID（オプション）

**レスポンス（Server-Sent Events）**
```
Content-Type: text/event-stream

data: {"type": "status", "data": {"stage": "processing", "message": "記憶を検索しています..."}}

data: {"type": "status", "data": {"stage": "analyzing", "message": "画像を分析しています..."}}

data: {"type": "status", "data": {"stage": "generating", "message": "応答を生成しています..."}}

data: {"type": "text", "data": {"content": "こんにちは！", "chunk_id": 1}}

data: {"type": "text", "data": {"content": "今日の予定について", "chunk_id": 2}}

data: {"type": "reference", "data": {"memories": [...]}}

data: {"type": "status", "data": {"stage": "completed", "message": "処理が完了しました"}}

data: {"type": "end", "data": {"request_id": "req_12345"}}
```

**エラーレスポンス**
```
data: {"type": "error", "data": {"error_code": "image_analysis_failed", "message": "画像の分析に失敗しました"}}
```

**イベントタイプ**
- `status`: 処理状況の通知
- `text`: 応答テキストの配信
- `reference`: 参照された記憶情報
- `error`: エラー通知
- `end`: ストリーム終了

---


### キューブ記憶統計

#### `GET /api/memory/cube/{cube_id}/stats`

指定キューブの記憶統計情報を取得します。

**リクエスト**
```
GET /api/memory/cube/character_123_cube/stats
```

**レスポンス**
```json
{
  "cube_id": "character_123_cube",
  "total_memories": 150,
  "text_memories": 120,
  "activation_memories": 20,
  "parametric_memories": 10,
  "last_updated": "2025-01-01T11:30:00Z",
  "timestamp": "2025-01-01T12:00:00Z"
}
```

---

### キューブ記憶削除

#### `DELETE /api/memory/cube/{cube_id}/all`

指定キューブの全記憶を削除します。

**リクエスト**
```
DELETE /api/memory/cube/character_123_cube/all
```

**レスポンス**
```json
{
  "status": "success",
  "message": "ユーザー user123 の記憶を削除しました",
  "timestamp": "2025-01-01T12:00:00Z"
}
```

---

### キャラクターキューブリスト取得

#### `GET /api/cubes`

すべてのキャラクターキューブの一覧を取得します。

**リクエスト**
```
GET /api/cubes
```

**レスポンス**
```json
{
  "status": "success",
  "message": "2つのキャラクターキューブを取得しました",
  "data": [
    {
      "cube_id": "character_miku_cube",
      "character_name": "初音ミク"
    },
    {
      "cube_id": "character_tsukuyomi_cube", 
      "character_name": "つくよみちゃん"
    }
  ]
}
```
