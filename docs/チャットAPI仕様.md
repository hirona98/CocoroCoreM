# CocoroCore2 チャットAPI仕様書（正式版）

## 概要

CocoroCore2における統合チャット機能のAPI仕様を定義します。4つのチャット機能（テキストチャット、画像付きチャット、通知機能、デスクトップウォッチ機能）を的に処理し、MemOSとの完全統合を実現します。

## 設計原則

1. **API**: 4つの機能を1つのエンドポイントで処理
2. **MOSProduct活用**: 既存のMOSProduct.chat_with_references()を基盤として拡張
3. **画像処理強化**: 機能仕様に基づく詳細な画像分析機能を実装
4. **並行処理対応**: 複数リクエストの同時処理をサポート
5. **ストリーミング配信**: Server-Sent Events (SSE) による高速レスポンス

## APIエンドポイント

### メインチャットAPI

```
POST /api/chat/stream
```

#### リクエスト仕様

```typescript
interface ChatRequest {
  // 基本情報
  query: string;                    // ユーザークエリ（必須）
  cube_id: string;                  // メモリキューブID（必須） - CocoroAIは単一ユーザーシステムのため、キャラクター別のキューブIDで識別
  
  // 機能識別
  chat_type: "text" | "text_image" | "notification" | "desktop_watch";
  
  // 画像関連
  images?: ImageData[];             // 画像データ配列（画像機能時）
  
  // 通知関連
  notification?: NotificationData;  // 通知データ（通知機能時）
  
  // デスクトップウォッチ関連
  desktop_context?: DesktopContext; // デスクトップコンテキスト（ウォッチ機能時）
  
  // オプション
  history?: ChatMessage[];          // 会話履歴（セッション管理はMemOS側で自動実行）
  internet_search?: boolean;        // インターネット検索（明示的な有効化オプション）
  request_id?: string;              // リクエスト識別ID（並行処理用、レスポンスに同じ値が返却される）
}

interface ImageData {
  data: string;                     // Base64エンコード画像データ（data URL形式）
                                    // 例: "data:image/png;base64,iVBORw0KG..."
                                    // クリップボードからの貼り付けは常にPNG形式に変換される
}

interface NotificationData {
  from: string;                     // 通知元アプリ名
  original_message: string;         // 元の通知メッセージ
}

interface DesktopContext {
  window_title?: string;            // アクティブウィンドウタイトル
  application?: string;             // アプリケーション名
  capture_type: "active" | "full";  // キャプチャタイプ
  timestamp: string;                // キャプチャ時刻
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
}
```

#### レスポンス仕様（SSE）

```typescript
// Server-Sent Events ストリーム
interface SSEResponse {
  data: string; // JSON文字列
}

// データタイプごとの構造
interface StatusEvent {
  type: "status";
  data: {
    stage: "processing" | "analyzing" | "generating" | "completed"; // 処理段階
    message: string;  // 段階の説明テキスト
    progress?: number; // 0-100 処理進捗率（UIでプログレスバー表示用）
  };
}

// StatusEventの動作仕様:
// - 各処理段階の開始時に1回だけ送信される（定期送信ではない）
// - "processing": 記憶検索開始時
// - "analyzing": 画像分析開始時（画像がある場合のみ）
// - "generating": LLM応答生成開始時
// - "completed": 全処理完了時
// - TextEventが流れ始めたらStatusEventは送信されない

interface TextEvent {
  type: "text";
  data: {
    content: string;     // ストリーミングテキスト
    chunk_id: number;    // チャンク番号
  };
}

interface ImageAnalysisEvent {
  type: "image_analysis";
  data: {
    analysis: ImageAnalysisResult[];
  };
}

interface ReferenceEvent {
  type: "reference";
  data: {
    memories: MemoryReference[];
  };
}

interface MetricsEvent {
  type: "metrics";
  data: {
    processing_time: number;
    tokens_generated: number;
    memory_count: number;
  };
}

interface ErrorEvent {
  type: "error";
  data: {
    error_code: string;
    message: string;
    details?: object;
  };
}

interface EndEvent {
  type: "end";
  data: {
    request_id?: string;
  };
}
```


## 機能別処理仕様

### 1. テキストチャット機能

**特徴**: 基本的な文字会話、MemOS記憶活用、ストリーミング配信

```typescript
// リクエスト例
{
  "query": "今日の予定を教えて",
  "cube_id": "character_123_cube",
  "chat_type": "text",
  "internet_search": true
}
```

**処理フロー**:
1. MOSProduct.chat_with_references()を直接活用
2. 記憶検索→システムプロンプト構築→LLM生成→ストリーミング配信
3. 会話履歴への自動保存

### 2. 画像付きチャット機能

**特徴**: 画像内容理解、詳細分析、統合応答生成

```typescript
// リクエスト例（ファイルから）
{
  "query": "この画像について教えて",
  "cube_id": "character_123_cube",
  "chat_type": "text_image",
  "images": [{
    "data": "data:image/jpeg;base64,/9j/4AAQ..."
  }]
}

// リクエスト例（クリップボードから貼り付け）
{
  "query": "この画像について教えて",
  "cube_id": "character_123_cube",
  "chat_type": "text_image",
  "images": [{
    "data": "data:image/png;base64,iVBORw0KGgo..."  // 常にPNG形式
  }]
}
```

**処理フロー**:
1. **画像前処理**: Base64デコード、フォーマット検証、サイズチェック
2. **画像分析実行**: 
   - 内容説明生成（Vision LLM使用）
   - カテゴリ分類（機械学習モデル）
   - 雰囲気分析（感情認識API）
   - 時間帯推定（画像解析アルゴリズム）
   - OCR処理（文字検出時）
3. **コンテキスト構築**: 分析結果をユーザーメッセージの前文として統合
4. **統合応答生成**: 画像理解を含む自然な会話応答
5. **結果配信**: 分析結果と応答をストリーミング配信

### 3. 通知機能

**特徴**: 外部アプリ通知への自然な独り言応答、画像対応

```typescript
// リクエスト例
{
  "query": "通知への反応をお願いします",
  "cube_id": "character_123_cube",
  "chat_type": "notification", 
  "notification": {
    "from": "LINE",
    "original_message": "写真が送信されました",
    "app_type": "messaging"
  },
  "images": [/* 画像データ */]
}
```

**処理フロー**:
1. **通知解析**: アプリ種別、メッセージ内容、画像有無の確認
2. **画像分析**: （画像ある場合）詳細分析実行
3. **報告メッセージ生成**: 
   - システムプロンプト: 「〇〇から△△ってメッセージが来たよ。大変みたいだね。」という報告形式+感想の簡潔な反応
   - アプリ名と内容を含む自然な表現
   - 質問形式を避けた独白スタイル
4. **応答配信**: 独り言をストリーミング配信

### 4. デスクトップウォッチ機能

**特徴**: 画面内容理解、独り言形式のツッコミ、必須画像データ

```typescript
// リクエスト例
{
  "query": "",  // デスクトップウォッチでは自動生成されるため空文字
  "cube_id": "character_123_cube",
  "chat_type": "desktop_watch",
  "desktop_context": {
    "window_title": "Visual Studio Code",
    "application": "vscode",
    "capture_type": "active",
    "timestamp": "2024-01-20T10:30:00Z"
  },
  "images": [/* スクリーンショット */]
}
```

**処理フロー**:
1. **画像必須チェック**: 画像データが必須、未提供時はエラー
2. **画面分析**: Vision LLMによる画像内容の直接解析
3. **独り言生成**:
   - システムプロンプト: 「キャラクター性を活かした独り言形式」
   - 画面内容に応じた感想・ツッコミ
   - 1-2文の簡潔な独り言
4. **応答配信**: 独り言をストリーミング配信

