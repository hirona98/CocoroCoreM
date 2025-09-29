# CocoroDock Web API仕様書

## 概要
CocoroDockはWebブラウザからWebSocket経由でCocoroAIと対話するためのAPIを提供します。

## サーバー設定
- **プロトコル**: HTTPS (自己署名証明書)
- **ポート**: 55607 (設定ファイルのcocoroWebPortで変更可能)
- **アドレス**: 0.0.0.0 (全てのネットワークインターフェースで待ち受け)

## エンドポイント

### WebSocketエンドポイント
**URL**: `wss://[host]:55607/mobile`

WebSocket接続を確立してリアルタイムメッセージングを行います。

### 静的ファイル配信
**URL**: `https://[host]:55607/`

Webアプリケーション（HTML/CSS/JavaScript）を配信します。

### 音声ファイル配信
**URL**: `https://[host]:55607/audio/{filename}`

TTS生成した音声ファイルをダウンロードします。

## WebSocketメッセージフォーマット

### リクエストメッセージ

#### 1. チャットメッセージ
```json
{
  "type": "chat",
  "timestamp": "2024-01-01T12:00:00Z",
  "data": {
    "message": "こんにちは",
    "chat_type": "text",
    "images": []
  }
}
```

#### 2. 音声メッセージ
```json
{
  "type": "voice",
  "timestamp": "2024-01-01T12:00:00Z",
  "data": {
    "audio_data_base64": "base64エンコードされた音声データ",
    "encoding": "base64",
    "sample_rate": 16000,
    "channels": 1,
    "format": "wav",
    "processing": "rnnoise"
  }
}
```

#### 3. 画像メッセージ
```json
{
  "type": "image",
  "timestamp": "2024-01-01T12:00:00Z",
  "data": {
    "image_data_base64": "base64エンコードされた画像データ",
    "encoding": "base64",
    "format": "jpeg",
    "width": 1920,
    "height": 1080,
    "camera_facing": "user",
    "message": "これは何ですか？"
  }
}
```

### レスポンスメッセージ

#### 1. 応答メッセージ
```json
{
  "type": "response",
  "timestamp": "2024-01-01T12:00:01Z",
  "data": {
    "text": "こんにちは！何かお手伝いできることはありますか？",
    "audio_url": "/audio/response_20240101120001.wav",
    "speaker_id": 3,
    "source": "cocoro_core_m"
  }
}
```

#### 2. エラーメッセージ
```json
{
  "type": "error",
  "timestamp": "2024-01-01T12:00:01Z",
  "data": {
    "code": "CORE_M_ERROR",
    "message": "サーバーエラーが発生しました"
  }
}
```

## エラーコード
- `VOICEVOX_ERROR`: 音声合成エラー
- `CORE_M_ERROR`: CocoroCore処理エラー
- `NETWORK_ERROR`: ネットワークエラー
- `INVALID_MESSAGE`: メッセージフォーマットエラー
- `SERVER_ERROR`: サーバー内部エラー
- `VOICE_RECOGNITION_ERROR`: 音声認識エラー
- `AUDIO_PROCESSING_ERROR`: 音声処理エラー
- `VOICE_DATA_ERROR`: 音声データエラー
- `IMAGE_PROCESSING_ERROR`: 画像処理エラー

## 処理フロー
1. ブラウザがHTTPSでアクセス
2. WebSocket接続を`/mobile`エンドポイントに確立
3. メッセージ送受信（JSON形式）
4. CocoroCoreM/VoiceVoxと連携して応答生成
5. 音声ファイルは`/audio`エンドポイントから配信