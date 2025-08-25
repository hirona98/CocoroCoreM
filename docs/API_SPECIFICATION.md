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



### キャラクター記憶管理

#### キャラクター一覧取得

**エンドポイント**: `GET /api/memory/characters`

キャラクター（メモリキューブ）一覧を取得します。

**リクエスト**
```
GET /api/memory/characters
```

**レスポンス**
```json
{
  "status": "success",
  "message": "キャラクター一覧を取得しました",
  "data": [
    {
      "memory_id": "listy",
      "memory_name": "リスティー", 
      "role": "character",
      "created": true
    },
    {
      "memory_id": "miku", 
      "memory_name": "初音ミク",
      "role": "character",
      "created": true
    }
  ]
}
```

#### キャラクター記憶削除

**エンドポイント**: `DELETE /api/memory/character/{memory_id}/all`

指定キャラクターの全記憶を削除します。

**リクエスト例**
```
DELETE /api/memory/character/listy/all
```

**レスポンス**
```json
{
  "status": "success",
  "message": "記憶を削除しました"
}
```
