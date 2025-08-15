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

### チャット

TODO: 要検討

CocoroDockからチャットリクエストを処理します。画像対応機能を含みます。

**メッセージタイプ**
- `chat`: 通常チャット
- `notification`: 通知
- `desktop_monitoring`: デスクトップ監視

---


### ユーザー記憶統計

TODO: 要検討

指定ユーザーの記憶統計情報を取得します。

**リクエスト**
```
GET /api/memory/user/user123/stats
```

**レスポンス**
```json
{
  "user_id": "user123",
  "total_memories": 150,
  "text_memories": 120,
  "activation_memories": 20,
  "parametric_memories": 10,
  "last_updated": "2025-01-01T11:30:00Z",
  "cube_id": "cube123",
  "timestamp": "2025-01-01T12:00:00Z"
}
```

---

### ユーザー記憶削除

#### `DELETE /api/memory/user/{user_id}/all`

指定ユーザーの全記憶を削除します。

**リクエスト**
```
DELETE /api/memory/user/user123/all
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

### ユーザーリスト取得

#### `GET /api/users`

システムに登録されているユーザーリストを取得します。

**リクエスト**
```
GET /api/users
```

**レスポンス**
```json
{
  "status": "success",
  "message": "3名のユーザーを取得しました",
  "data": [
    {
      "user_id": "550e8400-e29b-41d4-a716-446655440000",
      "user_name": "田中太郎"
    },
    {
      "user_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
      "user_name": "佐藤花子"
    }
  ]
}
```

---

### ユーザー作成

TODO: 要検討

新しいユーザーを作成します。


## 注意事項

- すべてのAPIは`127.0.0.1`でのローカル接続のみ対応
- 画像ファイルはBase64エンコードで送信
