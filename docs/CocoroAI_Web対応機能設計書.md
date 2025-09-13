# CocoroAI Web機能設計書 v1.0

**プロジェクト**: CocoroAI スマートフォンWeb対応  
**作成日**: 2025-09-12  
**アーキテクチャ**: CocoroDock中央制御 + MemOSセッション管理  

---

## 1. プロジェクト概要

### 目的
CocoroAIをスマートフォンのWebブラウザからアクセス可能にし、PCと同等の音声対話・テキストチャット・画像送信機能を提供する。

### 基本方針
- **CocoroDock中央制御**: すべての通信をCocoroDockが仲介
- **CocoroCoreM変更なし**: CocoroCoreMは変更しない。CocoroDockがすべての違いを吸収する。
- **単一デバイス設計**: 複雑な同期機能は実装しない
- **VOICEVOX必須**: 音声合成はVOICEVOX統合必須
- **PWA対応**: スマートフォンアプリライクな体験

---

## 2. システムアーキテクチャ

### 全体構成
```
【スマートフォン PWA】
      ↓ WebSocket
【CocoroDock】(中央ハブ)
      ↓ 既存WebSocketChatClient  
【CocoreCoreM】(MemOS統合)
      ↓ 既存API
【CocoroShell】(VRM表示)

【VOICEVOX】← CocoroDock直接制御
```

### コンポーネント役割

| コンポーネント | 役割 | ポート | 変更内容 |
|---------------|------|--------|----------|
| **スマートフォンPWA** | Webクライアント | - | **新規作成** |
| **CocoroDock** | 中央制御・プロキシ | 55607(新規) | **WebSocket追加** |
| **CocoreCoreM** | AI処理・MemOS | 55601 | 変更なし |
| **CocoroShell** | VRM表示 | 55605 | 変更なし |
| **VOICEVOX** | 音声合成 | 50021 | 変更なし |

---

## 3. 技術仕様

### セッション管理方式

MemOSの既存機能をそのまま活用


### 通信プロトコル
- **WebSocket**: リアルタイム双方向通信
- **HTTP REST**: 静的ファイル配信・音声ファイル配信
- **JSON**: 全メッセージフォーマット

---

## 4. API仕様

### CocoroDock新規エンドポイント

#### WebSocketエンドポイント
```
ws://[CocoroDock_IP]:55607/mobile
```
- **認証**: なし（内部ネットワーク前提）
- **プロトコル**: WebSocket over TCP
- **メッセージ形式**: JSON

#### HTTPエンドポイント
| Method | Path | 説明 | Content-Type |
|--------|------|------|--------------|
| GET | `/` |     メインページ | text/html |
| GET | `/assets/*` | 静的アセット | auto-detect |
| GET | `/audio/{filename}` | VOICEVOX音声ファイル | audio/wav |

---

## 5. メッセージ仕様

### 基本メッセージ構造
```json
{
  "type": "chat|response|error",
  "timestamp": "2025-09-12T15:30:00Z",
  "data": { /* タイプ別データ */ }
}
```

### メッセージタイプ別仕様

#### チャットメッセージ（スマホ→CocoroDock）
```json
{
  "type": "chat",
  "timestamp": "2025-09-12T15:30:00Z",
  "data": {
    "message": "今日の天気を教えて"
  }
}
```

#### 応答メッセージ（CocoroDock→スマホ）
```json
{
  "type": "response",
  "timestamp": "2025-09-12T15:30:15Z", 
  "data": {
    "text": "今日は晴れです。最高気温25度の予報です。",
    "audio_url": "/audio/response_001.wav",  // VOICEVOX生成
    "speaker_id": 3,
    "source": "cocoro_core_m"
  }
}
```

#### 画像付きチャットメッセージ（スマホ→CocoroDock）
```json
{
  "type": "chat",
  "timestamp": "2025-09-12T15:30:00Z",
  "data": {
    "message": "この画像について教えて",
    "chat_type": "text_image",
    "images": [
      {
        "image_data": "data:image/jpeg;base64,/9j/4AAQ...",
        "source": "camera|gallery"
      }
    ]
  }
}
```

#### エラーメッセージ
```json
{
  "type": "error", 
  "timestamp": "2025-09-12T15:30:00Z",
  "data": {
    "code": "VOICEVOX_ERROR|CORE_M_ERROR|NETWORK_ERROR",
    "message": "エラー詳細メッセージ"
  }
}
```

---

## 6. 音声処理仕様（VOICEVOX統合）

### 音声認識フロー
```
1. スマホ: Web Speech API → テキスト変換
2. スマホ → CocoroDock: JSONメッセージ送信
3. CocoroDock → CocoreCoreM: 既存WebSocketChatClient使用
4. MemOS: 自動的に記憶検索・コンテキスト継続・応答生成
5. CocoreCoreM → CocoroDock: テキスト応答（既存WebSocketChatClient使用）
6. CocoroDock → VOICEVOX: 音声合成API呼び出し
7. VOICEVOX → CocoroDock: WAVファイル取得
8. CocoroDock → スマホ: テキスト＋音声URL送信
```

### VOICEVOX API統合仕様
```csharp
// CocoroDockでの音声合成処理
private async Task<string> SynthesizeVoiceAsync(string text, int speakerId = 3)
{
    // 1. audio_query API呼び出し
    var queryResponse = await _httpClient.PostAsync(
        $"http://localhost:50021/audio_query?text={Uri.EscapeDataString(text)}&speaker={speakerId}",
        new StringContent("")
    );
    var audioQuery = await queryResponse.Content.ReadAsStringAsync();
    
    // 2. synthesis API呼び出し  
    var synthesisResponse = await _httpClient.PostAsync(
        $"http://localhost:50021/synthesis?speaker={speakerId}",
        new StringContent(audioQuery, Encoding.UTF8, "application/json")
    );
    
    // 3. WAVファイル保存
    var audioData = await synthesisResponse.Content.ReadAsByteArrayAsync();
    var fileName = $"response_{DateTime.Now:yyyyMMddHHmmss}.wav";
    var filePath = Path.Combine("wwwroot/audio", fileName);
    await File.WriteAllBytesAsync(filePath, audioData);
    
    return fileName;
}
```

### 音声パラメータ

setting.jsonの値を使用する


---

## 8. 設定仕様

### CocoroDock設定追加項目

setting.jsonに追加する項目
```json
{
  "cocoroWebPort": 55607,
  "isEnableWebService": true
}
```

### 既存設定への影響
- **CocoreCoreM**: 設定変更なし（既存のMemOS設定を継続使用）
- **CocoroShell**: 設定変更なし
- **VOICEVOX**: 設定変更なし（既存の起動方法を継続）

---

## 9. セキュリティ・制限事項

### セキュリティ考慮事項
- **内部ネットワーク限定**: 認証機能は実装しない
- **CORS設定**: 無制限
- **ファイルアップロード制限**: 最大50MB、画像形式のみ

### 技術的制限事項
- **iOS Safari**: Web Speech API未対応（音声認識不可）
- **単一デバイス**: 複数デバイス間の同期機能なし  
- **オフライン**: 非対応

---

## 10. 実装時の技術注意事項

### CocoroDock実装ポイント
```csharp
// 既存のWebSocketChatClientを活用
private readonly WebSocketChatClient _cocoroClient;  // 既存クラス使用

// 新規WebSocketサーバー実装
public class MobileWebSocketHandler
{
    public async Task HandleConnection(WebSocket webSocket)
    {
        // 1. スマホからのメッセージ受信
        var message = await ReceiveMessage(webSocket);
        
        // 2. 既存のCocoreCoreMクライアントに転送  
        var response = await _cocoroClient.SendChatAsync(message.Data.Message);
        
        // 3. VOICEVOX音声合成
        var audioFile = await SynthesizeVoice(response);
        
        // 4. スマホに応答送信
        await SendResponse(webSocket, response, audioFile);
    }
}
```

### MemOS統合確認事項
- `app.cocoro_product.current_user_id`が適切に設定されていること
- `app.cocoro_product.get_current_cube_id()`が有効なcube_idを返すこと  
- TreeTextMemoryが正常に動作していること
- PersonalMemory/OuterMemoryが利用可能であること

---

## 11. 実装優先度・開発フェーズ

### Phase 1（MVP: 最小機能）
1. CocoroDock WebSocketサーバー追加
2. 基本PWA（テキストチャットのみ）
3. VOICEVOX音声合成統合

### Phase 2（音声対応）
4. Web Speech API音声認識
5. 音声再生機能

### Phase 3（完全版）
6. カメラ・画像送信機能
7. PWA最適化（Service Worker等）

---

## 12. PWAアプリケーション仕様

### ファイル構成・リポジトリ統合

PWAアプリケーションはCocoroDockリポジトリに統合し、単一リポジトリでの管理を行う。

#### ディレクトリ構造
```
CocoroDock/
├── Communication/              (既存)
│   ├── MobileWebSocketServer.cs    (新規実装済)
│   ├── MobileWebSocketModels.cs    (新規実装済)
│   └── VoicevoxClient.cs           (新規実装済)
├── Services/                   (既存)
├── wwwroot/                    (新規追加)
│   ├── index.html             (~200行) メインHTML
│   ├── manifest.json          (~30行)  PWAマニフェスト
│   ├── sw.js                  (~100行) Service Worker
│   ├── js/
│   │   ├── app.js            (~300行) メイン処理・UI制御
│   │   ├── websocket.js      (~150行) WebSocket通信処理
│   │   ├── audio.js          (~100行) 音声認識・再生処理
│   │   └── camera.js         (~80行)  カメラ・画像送信処理
│   ├── css/
│   │   └── style.css         (~200行) スタイルシート
│   └── icons/
│       ├── icon-192.png
│       └── icon-512.png
└── ... (既存ファイル)
```

### コード量見積もり
- **HTML**: ~200行
- **JavaScript**: ~630行 (app.js 300 + websocket.js 150 + audio.js 100 + camera.js 80)
- **CSS**: ~200行  
- **JSON**: ~30行 (manifest.json)
- **合計**: **約1,060行**

### 統合のメリット
1. **単一リポジトリ管理**: ビルド・デプロイが統一
2. **設定共有**: setting.jsonの設定値をそのまま活用
3. **静的ファイル配信**: MobileWebSocketServerが wwwroot/ を直接配信
4. **開発効率**: サーバー・クライアント同時修正が容易
5. **依存関係明確**: バックエンドAPIとフロントエンドの整合性保証

### 開発工数見積もり
- **Phase 2 (基本PWA)**: 2-3日
- **Phase 3 (音声・画像対応)**: 1-2日
- **Phase 4 (最適化)**: 1日
- **総開発工数**: 4-6日程度

### 技術的実装方針
- **静的ファイル配信**: MobileWebSocketServerのHTTPエンドポイントで配信
- **ビルド統合**: CocoroDockのビルドプロセスにwwwroot/も含める
- **設定連携**: isEnableWebService設定でWeb機能のON/OFF制御
- **開発モード**: 開発時はホットリロード対応

---

**End of Document**