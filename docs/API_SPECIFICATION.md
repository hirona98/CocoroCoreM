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


### キューブ記憶統計

#### `GET /api/memory/user/{memory_id}/stats`

指定メモリキューブの記憶統計情報を取得します。

**リクエスト**
```
GET /api/memory/user/listy/stats
```

**レスポンス**
```json
{
  "memory_id": "listy",
  "cube_id": "user_user_listy_cube",
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

#### `DELETE /api/memory/user/{memory_id}/all`

指定メモリキューブの全記憶を削除します。

**リクエスト**
```
DELETE /api/memory/user/listy/all
```

**レスポンス**
```json
{
  "status": "success",
  "message": "listyの記憶を削除しました",
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
  "message": "2つのメモリキューブを取得しました",
  "data": [
    {
      "memory_id": "miku",
      "cube_id": "user_user_miku_cube",
      "character_name": "初音ミク"
    },
    {
      "memory_id": "tsukuyomichan",
      "cube_id": "user_user_tsukuyomichan_cube", 
      "character_name": "つくよみちゃん"
    }
  ]
}
```
