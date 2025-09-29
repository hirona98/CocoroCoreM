# CocoroCoreM API 仕様 (最小版)

最終更新: 2025-09-29
バージョン: 1.0.0

本書は現行実装 (`src/api/*`, `src/main.py`) を元にした最小限の REST / WebSocket 仕様概要です。

## ベースURL
```
http://<host>:<cocoroCorePort>
```
`<cocoroCorePort>` は設定ファイルで指定、デフォルトは `55601`。

---
## 1. ヘルスチェック
### GET /api/health
システム稼働確認。

レスポンス 200:
```json
{
  "status": "healthy"
}
```

---
## 2. システム制御
### POST /api/control
CocoroCoreM の制御アクション実行。現在は `shutdown` のみ実装。

リクエスト例:
```json
{
  "action": "shutdown"
}
```

レスポンス 200 (成功受理):
```json
{
  "status": "success",
  "message": "制御アクション 'shutdown' を実行しました"
}
```

**注記**: shutdownアクションはバックグラウンドで処理され、即時応答が返されます。

エラー例 500:
```json
{
  "success": false,
  "error": "system_control_failed",
  "message": "システム制御に失敗しました: shutdown",
  "details": {"action": "shutdown", "error": "..."}
}
```

---
## 3. キャラクターメモリ管理
### GET /api/memory/characters
管理中キャラクター一覧取得。

レスポンス 200:
```json
{
  "status": "success",
  "message": "キャラクター一覧を取得しました",
  "data": [
    {
      "memory_id": "char_01",
      "memory_name": "Alice",
      "role": "character",
      "created": true
    }
  ]
}
```

### DELETE /api/memory/character/{memory_id}/all
指定キャラクターの全記憶を削除。

パスパラメータ:
- `memory_id` : 対象キャラクターのメモリID

レスポンス 200:
```json
{
  "status": "success",
  "message": "記憶を削除しました"
}
```

404 キャラクター未存在:
```json
{
  "success": false,
  "error": "character_not_found",
  "message": "キャラクターが見つかりません: <id>",
  "details": {"memory_id": "<id>"}
}
```

500 失敗:
```json
{
  "success": false,
  "error": "character_memory_delete_failed",
  "message": "キャラクター記憶削除に失敗しました: <id>",
  "details": {"memory_id": "<id>", "error": "..."}
}
```

取得失敗例 (一覧):
```json
{
  "success": false,
  "error": "character_list_failed",
  "message": "キャラクター一覧の取得に失敗しました",
  "details": {"error": "..."}
}
```

---
## 4. WebSocket チャット
### 接続 URL
```
ws://<host>:<cocoroCorePort>/ws/chat/{client_id}
```
`client_id` はクライアント任意識別子。

### クライアント送信メッセージ形式
```json
{
  "action": "chat",
  "session_id": "optional_session_id",  // 任意 (省略時サーバ生成)
  "request": {
    "query": "ユーザークエリ",
    "chat_type": "text",                 // text | text_image | notification | desktop_watch | reminder
    "images": [ { "data": "data:image/png;base64,..." } ],
  "notification": { "original_source": "Slack", "original_message": "通知本文" },
    "reminder": { "requirement": "会議", "triggered_at": "2025-09-29T10:00:00" },
    "history": [ { "role": "user", "content": "以前の質問", "timestamp": "2025-09-29T01:23:45" } ],
    "internet_search": false,
    "request_id": "任意ID"
  }
}
```

notification オブジェクト:
- `original_source` (必須) 通知元アプリ / サービス名
- `original_message` (必須) 元通知本文
欠落時は内部的に `不明なアプリ` が使用される (original_source 未指定時)。

chat_type 補足:
- `text`: 通常テキスト
- `text_image`: 画像付き会話 (images 配列あり) ※内部処理は text + 画像説明付与
- `notification`: 通知要約。notification オブジェクト必須
- `desktop_watch`: デスクトップ観察発話 (現在は追加メタは使用任意)
- `reminder`: リマインダー発火時の応答

### サーバ送信メッセージ (type別概要)
| type | data フォーマット | 説明 |
|------|--------------------|------|
| text | {"content":"<部分文字列>","is_incremental":true} | インクリメンタル本文 (句読点区切り)。複数回送信 |
| reference | {"references": [...] } | 参照メモリ等 (MemOS 由来) |
| time | {"total_time": <float>, "speed_improvement": "" } | 処理時間情報 |
| end | {"total_tokens": <int>, "final_text": "最終確定本文" } | 応答完了 |
| error | {"message": "エラー内容", "code": "PROCESSING_ERROR" } | エラー |

メッセージ共通フィールド:
```json
{
  "session_id": "<session_id>",
  "type": "text|reference|time|end|error",
  "data": { ... }
}
```

### ストリーミング仕様メモ
- text は内部バッファリングされ、文末推定（句読点/改行）で分割送信。
- 最後に残ったバッファは `end` 直前に強制送信。
- 記憶参照タグ ([xxxxxxxx]) や (PersonalMemory:...) などは送信前に除去。
- リマインダータグ `[REMINDER:YYYY-MM-DD HH:MM:SS|任意メモ]` は内部解析 → リマインダー登録、本文から除去後に履歴保存。
  - `|任意メモ` 部は省略可能。

---
## 5. 共通エラーレスポンス形式 (REST)
```json
{
  "success": false,
  "error": "error_code",
  "message": "人間可読メッセージ",
  "details": { "key": "value" }
}
```

**注記**: ヘルスチェックエンドポイント(`/api/health`)のみ例外的に `{"status": "error"}` 形式を使用します。

ヘルスチェック失敗例 (内部例外時):
```json
{ "status": "error" }
```

---
## 6. 認証
現行コードに認証/認可処理は未実装。必要に応じて将来 `API Key` もしくは `Bearer Token` 方式を追加予定。

---
## 7. 既知の制限 / TODO
- `/api/control` は `shutdown` のみ。
- メモリ管理 API は一覧取得/全削除のみ。
- WebSocket 以外のチャットRESTエンドポイントは未実装。
- エラーコード体系は暫定 (固定文字列)。

---
## 8. セキュリティ
- **CORS**: 全てのオリジンを許可 (`*`)
- **認証**: 未実装（将来 Bearer Token 方式を検討）
- **HTTPS**: 未対応（ローカルネットワーク使用を想定）
