# CocoroCore2 チャットAPI仕様書（正式版）

## 概要

CocoroCore2における統合チャット機能のAPI仕様を定義します。4つのチャット機能（テキストチャット、画像付きチャット、通知機能、デスクトップウォッチ機能）を統一的に処理し、MemOSとの完全統合を実現します。

## 設計原則

1. **統一API**: 4つの機能を1つのWebSocketエンドポイントで処理
2. **MOSProduct活用**: MOSProduct.chat_with_references()を基盤とした実装
3. **リアルタイム通信**: WebSocketによる双方向通信とストリーミングレスポンス
4. **並行処理対応**: 複数セッションの同時処理をサポート
5. **非ブロッキング処理**: 長時間処理でも他のリクエストをブロックしない設計

## APIエンドポイント

### メインチャットAPI（WebSocket）

```
WebSocket /ws/chat/{client_id}
```

#### 接続仕様

WebSocket接続後、以下の形式でメッセージを送受信します：

##### 送信メッセージ（クライアント→サーバー）

```typescript
interface WebSocketMessage {
  action: "chat";                   // アクション（現在は"chat"のみサポート）
  session_id: string;               // セッション識別ID（クライアント生成）
  request: ChatRequest;             // チャットリクエスト詳細
}

interface ChatRequest {
  // 基本情報
  query: string;                    // ユーザークエリ（必須）
  
  // 機能識別
  chat_type: "text" | "text_image" | "notification" | "desktop_watch";
  
  // 画像関連
  images?: ImageData[];             // 画像データ配列（画像機能時）
  
  // オプション
  history?: ChatMessage[];          // 会話履歴（セッション管理はMemOS側で自動実行）
  internet_search?: boolean;        // インターネット検索（明示的な有効化オプション）
}

interface ImageData {
  data: string;                     // Base64エンコード画像データ（data URL形式）
                                    // 例: "data:image/png;base64,iVBORw0KG..."
                                    // クリップボードからの貼り付けは常にPNG形式に変換される
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
}
```

**注意**: 
- 通知機能とデスクトップウォッチ機能は、chat_typeで識別されますが、現在の実装では特別処理は行われません
- 追加のコンテキスト情報はクライアント側でクエリ内に統合する必要があります
- notification、desktop_contextフィールドは現在未使用です

##### 受信メッセージ（サーバー→クライアント）

```typescript
// WebSocketレスポンスの基本形式
interface WebSocketResponse {
  session_id: string;               // セッション識別ID
  type: string;                     // メッセージタイプ
  data: any;                        // タイプ別のデータ
}

// データタイプごとの構造
interface TextMessage {
  session_id: string;
  type: "text";
  data: {
    content: string;                // ストリーミングテキスト（チャンク）
    is_incremental: boolean;        // 増分フラグ（常にtrue）
  };
}

interface StatusMessage {
  session_id: string;
  type: "status";
  data: any;                        // ステータス情報（MOSProductから受信した生データ）
}

interface ReferenceMessage {
  session_id: string;
  type: "reference";
  data: {
    references: any[];              // 参照メモリリスト
  };
}

interface TimeMessage {
  session_id: string;
  type: "time";
  data: {
    total_time: number;             // 処理時間（秒）
    speed_improvement: string;      // 速度改善情報
  };
}

interface EndMessage {
  session_id: string;
  type: "end";
  data: {
    total_tokens: number;           // 総トークン数
    final_text: string;             // 最終テキスト
  };
}

interface ErrorMessage {
  session_id: string;
  type: "error";
  data: {
    message: string;                // エラーメッセージ
    code: string;                   // エラーコード
  };
}
```


## 機能別処理仕様

### 1. テキストチャット機能

**特徴**: 基本的な文字会話、MemOS記憶活用、WebSocketストリーミング配信

```typescript
// WebSocketメッセージ例
{
  "action": "chat",
  "session_id": "dock_20240120123456_abcd1234",
  "request": {
    "query": "今日の予定を教えて",
    "chat_type": "text",
    "internet_search": true
  }
}
```

**処理フロー**:
1. MOSProduct.chat_with_references()を直接活用
2. 記憶検索→システムプロンプト構築→LLM生成→WebSocketストリーミング配信
3. 会話履歴への自動保存（MemOS内部処理）

### 2. 画像付きチャット機能

**特徴**: 画像内容理解、MOSProduct画像処理、統合応答生成

```typescript
// WebSocketメッセージ例（ファイルから）
{
  "action": "chat",
  "session_id": "dock_20240120123456_abcd1234",
  "request": {
    "query": "この画像について教えて",
    "chat_type": "text_image",
    "images": [{
      "data": "data:image/jpeg;base64,/9j/4AAQ..."
    }]
  }
}

// WebSocketメッセージ例（クリップボードから貼り付け）
{
  "action": "chat",
  "session_id": "dock_20240120123456_abcd1234", 
  "request": {
    "query": "この画像について教えて",
    "chat_type": "text_image",
    "images": [{
      "data": "data:image/png;base64,iVBORw0KGgo..."  // 常にPNG形式
    }]
  }
}
```

**処理フロー**:
1. **画像前処理**: Base64デコード、フォーマット検証
2. **MOSProduct処理**: MOSProduct.chat_with_references()に画像データを渡す
3. **統合応答生成**: MOSProduct内での画像理解と自然な会話応答
4. **結果配信**: WebSocketストリーミング配信

### 3. 通知機能

**特徴**: 外部アプリ通知への自然な独り言応答、画像対応

```typescript
// WebSocketメッセージ例
{
  "action": "chat",
  "session_id": "dock_20240120123456_abcd1234",
  "request": {
    "query": "LINEから写真が送信されました", // クライアント側で通知内容を統合
    "chat_type": "notification",
    "images": [/* 画像データ */]
  }
}
```

**処理フロー**:
1. **基本処理**: 通常のテキストチャットと同じMOSProduct.chat_with_references()処理
2. **chat_type識別**: "notification"タイプとして識別（将来の拡張用）
3. **独り言生成**: キャラクター性を活かした独り言形式の応答生成
4. **応答配信**: WebSocketストリーミング配信

**注意**: 現在の実装では通知固有の特別処理は行われず、基本的なチャット処理として動作します。

### 4. デスクトップウォッチ機能

**特徴**: 画面内容理解、独り言形式のツッコミ、必須画像データ

```typescript
// WebSocketメッセージ例
{
  "action": "chat",
  "session_id": "dock_20240120123456_abcd1234",
  "request": {
    "query": "デスクトップ画面を見て感想を教えて", // クライアント側でコンテキスト統合
    "chat_type": "desktop_watch",
    "images": [/* スクリーンショット */]
  }
}
```

**処理フロー**:
1. **基本処理**: 通常のテキストチャットと同じMOSProduct.chat_with_references()処理
2. **画像解析**: MOSProduct内での画像理解処理
3. **chat_type識別**: "desktop_watch"タイプとして識別（将来の拡張用）
4. **独り言生成**: キャラクター性を活かした独り言形式の応答
5. **応答配信**: WebSocketストリーミング配信

**注意**: 現在の実装では特別なデスクトップコンテキスト処理は行われず、基本的な画像チャット処理として動作します。

## 技術実装詳細

### WebSocket接続

- **エンドポイント**: `ws://localhost:{port}/ws/chat/{client_id}`
- **client_id**: 一意なクライアント識別子（例: `dock_HOSTNAME_timestamp`）
- **接続ライフサイクル**: 接続後、複数セッションの並行処理が可能

### セッション管理

- **session_id**: 各チャットリクエストに対する一意識別子
- **並行処理**: 複数セッションが同時に処理可能
- **非ブロッキング**: 長時間処理でも他のリクエストをブロックしない

### メッセージフロー

1. **受信**: クライアントからWebSocketメッセージ受信
2. **検証**: action="chat"、リクエスト形式の検証
3. **処理開始**: 別スレッドでMOSProduct.chat_with_references()実行
4. **ストリーミング**: SSE形式からWebSocket形式に変換して送信
5. **終了**: "end"メッセージで完了通知

### パフォーマンス特徴

- **ThreadPoolExecutor**: 最大4ワーカーでMOSProduct処理
- **asyncio.Queue**: スレッド間の安全な通信
- **変換処理**: SSE→WebSocket形式の軽量変換
- **タイムアウト**: 各操作に適切なタイムアウト設定

## 使用例

### 基本的なテキストチャット

```typescript
// 送信
{
  "action": "chat",
  "session_id": "session_001",
  "request": {
    "query": "こんにちは",
    "chat_type": "text"
  }
}

// 受信例
{"session_id": "session_001", "type": "status", "data": "処理中..."}
{"session_id": "session_001", "type": "text", "data": {"content": "こんにちは！", "is_incremental": true}}
{"session_id": "session_001", "type": "end", "data": {"total_tokens": 50, "final_text": "こんにちは！元気ですか？"}}
```

### 画像付きチャット

```typescript
// 送信
{
  "action": "chat", 
  "session_id": "session_002",
  "request": {
    "query": "この画像について説明して",
    "chat_type": "text_image",
    "images": [{"data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."}]
  }
}
```

## エラーハンドリング

### エラーレスポンス

```typescript
{
  "session_id": "session_id", 
  "type": "error",
  "data": {
    "message": "エラーメッセージ",
    "code": "PROCESSING_ERROR"
  }
}
```

### 一般的なエラー

- **接続エラー**: アプリケーション初期化失敗
- **処理エラー**: MOSProduct処理中の例外
- **形式エラー**: 不正なリクエスト形式
- **タイムアウト**: 処理時間超過

## 互換性情報

- **旧SSE API**: 完全に削除済み、WebSocketのみサポート
- **CocoroDock**: WebSocketクライアント実装済み
- **MOSProduct**: 既存のchat_with_references()メソッドを活用
