# CocoroCoreM チャットAPI仕様書（正式版）

## 概要

CocoroCoreMにおける統合チャット機能のAPI仕様を定義します。4つのチャット機能（テキストチャット、画像付きチャット、通知機能、デスクトップウォッチ機能）を統一的に処理し、MemOSとの完全統合を実現します。

## 設計原則

1. **統一API**: 4つの機能を1つのWebSocketエンドポイントで処理
2. **CocoroMOSProduct活用**: CocoroAI専用システムプロンプト統合MOSProductクラスを基盤とした実装
3. **リアルタイム通信**: WebSocketによる双方向通信とストリーミングレスポンス
4. **並行処理対応**: 複数セッションの同時処理をサポート
5. **非ブロッキング処理**: 長時間処理でも他のリクエストをブロックしない設計
6. **高度機能**: テキストバッファリング、コンテキスト自動統合

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
  query: string;                                                         // ユーザークエリ（必須）
  
  // 機能識別
  chat_type: "text" | "text_image" | "notification" | "desktop_watch";  // チャットタイプ（必須）
  
  // 画像関連
  images?: ImageData[];                                                  // 画像データ配列（画像機能時）
  
  // 機能別コンテキスト
  notification?: NotificationData;                                       // 通知データ（通知機能時）
  desktop_context?: DesktopContext;                                     // デスクトップコンテキスト（監視機能時）
  
  // オプション
  history?: HistoryMessage[];                                           // 会話履歴（セッション管理はMemOS側で自動実行）
  internet_search?: boolean;                                            // インターネット検索（明示的な有効化オプション）
  request_id?: string;                                                  // リクエスト識別ID（オプション）
}

interface ImageData {
  data: string;                     // Base64エンコード画像データ（data URL形式）
                                    // 例: "data:image/png;base64,iVBORw0KG..."
                                    // クリップボードからの貼り付けは常にPNG形式に変換される
}

interface NotificationData {
  original_source: string;                    // 通知送信元（必須）
  original_message: string;         // 元の通知メッセージ（必須）
}

interface DesktopContext {
  window_title: string;             // ウィンドウタイトル（必須）
  application: string;              // アプリケーション名（必須）
  capture_type: "active" | "full";  // キャプチャタイプ（必須）
  timestamp: string;                // キャプチャ時刻（ISO形式、必須）
}

interface HistoryMessage {
  role: "user" | "assistant";       // メッセージの役割（必須）
  content: string;                  // メッセージ内容（必須）
  timestamp: string;                // メッセージ時刻（ISO形式、必須）
}
```


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
  "session_id": "dock_20240120123456789",
  "request": {
    "query": "今日の予定を教えて",
    "chat_type": "text",
    "internet_search": true
  }
}
```

**処理フロー**:
1. CocoroMOSProduct.chat_with_references()を直接活用
2. 記憶検索→CocoroAIシステムプロンプト統合→LLM生成→WebSocketストリーミング配信
3. 会話履歴への自動保存（MemOS内部処理）
4. バッファリング機能による最適化されたレスポンス配信

### 2. 画像付きチャット機能

**特徴**: 画像データ受信と基本処理（画像分析機能は実装予定）

```typescript
// WebSocketメッセージ例（ファイルから）
{
  "action": "chat",
  "session_id": "dock_20240120123456789",
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
  "session_id": "dock_20240120123456789", 
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
1. **画像データ受信**: Base64 data URL形式の画像データを受信
2. **画像分析**: 画像対応LLMで画像説明を生成
3. **コンテキスト統合**: 生成された画像説明とユーザークエリを統合
4. **MOSProduct処理**: 統合されたクエリでCocoroMOSProduct.chat_with_references()処理
5. **結果配信**: WebSocketストリーミング配信

### 3. 通知機能

**特徴**: 外部アプリ通知への自然な独り言応答、通知コンテキスト自動統合

```typescript
// WebSocketメッセージ例
{
  "action": "chat",
  "session_id": "dock_20240120123456789",
  "request": {
    "query": "写真が送信されました",
    "chat_type": "notification",
    "notification": {
      "original_source": "LINE",
      "original_message": "田中さんから写真が届きました"
    },
    "images": [/* 画像データ */]
  }
}
```

**処理フロー**:
1. **コンテキスト統合**: 通知データを自動的にクエリに統合（例：「【LINEからの通知】田中さんから写真が届きました\n\n写真が送信されました」） # TODO:
2. **MOSProduct処理**: 統合されたクエリでCocoroMOSProduct.chat_with_references()処理
3. **独り言生成**: キャラクター性を活かした独り言形式の応答生成
4. **応答配信**: WebSocketストリーミング配信

**実装状況**: 通知コンテキストの自動統合機能は実装済み

### 4. デスクトップウォッチ機能

**特徴**: デスクトップコンテキスト自動統合、独り言形式のツッコミ（画像分析は実装予定）

```typescript
// WebSocketメッセージ例
{
  "action": "chat",
  "session_id": "dock_20240120123456789",
  "request": {
    "query": "デスクトップ画面を見て感想を教えて",
    "chat_type": "desktop_watch",
    "desktop_context": {
      "window_title": "Visual Studio Code - main.py",
      "application": "Visual Studio Code",
      "capture_type": "active",
      "timestamp": "2024-01-20T12:34:56.789Z"
    },
    "images": [/* スクリーンショット */]
  }
}
```

**処理フロー**:
1. **コンテキスト統合**: デスクトップコンテキストを自動的にクエリに統合（例：「【デスクトップ監視】Visual Studio Codeで作業中\nウィンドウタイトル: Visual Studio Code - main.py\n\nデスクトップ画面を見て感想を教えて」）
2. **MOSProduct処理**: 統合されたクエリでCocoroMOSProduct.chat_with_references()処理  
3. **独り言生成**: キャラクター性を活かした独り言形式の応答
4. **応答配信**: WebSocketストリーミング配信


## 技術実装詳細

### WebSocket接続

- **エンドポイント**: `ws://localhost:{port}/ws/chat/{client_id}`
- **client_id**: 一意なクライアント識別子（例: `dock_20240120123456789`）
- **接続ライフサイクル**: 接続後、複数セッションの並行処理が可能

### セッション管理

- **session_id**: 各チャットリクエストに対する一意識別子
- **並行処理**: 複数セッションが同時に処理可能
- **非ブロッキング**: 長時間処理でも他のリクエストをブロックしない

### メッセージフロー

1. **受信**: クライアントからWebSocketメッセージ受信
2. **検証**: action="chat"、リクエスト形式の検証
3. **コンテキスト統合**: chat_typeに応じた自動コンテキスト統合（通知・デスクトップ監視）
4. **処理開始**: ThreadPoolExecutorで別スレッドでCocoroMOSProduct.chat_with_references()実行
5. **ストリーミング**: SSE形式からWebSocket形式に変換、バッファリング処理
6. **終了**: "end"メッセージで完了通知、早期終了によるレスポンス高速化

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


## MemOS統合詳細

### CocoroMOSProduct
- MemOSの`MOSProduct`クラスを継承したCocoroAI専用クラス
- CocoroAIのキャラクター設定からシステムプロンプトを自動取得・統合
- UUID部分マッチングによるシステムプロンプトファイル検索機能

### キューブ管理
- キャラクターごとの独立したメモリキューブ（`user_user_{memoryId}_cube`）
- Neo4j Community Editionによる高速ベクトル検索
- TreeTextMemoryによる階層的記憶構造

### システムプロンプト統合
- UserDataM/SystemPromptsディレクトリからの自動読み込み
- MemOSの記憶情報と統合したプロンプト構築
- PersonalMemoryとOuterMemoryの適切な分類・統合
