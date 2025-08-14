# CocoroCore2 設計仕様書

**版数**: 1.0  
**作成日**: 2025年1月14日  
**基準**: 確証のある調査結果のみ記載

---

## 1. プロジェクト概要

### 1.1 システム概要
CocoroCore2は、MemOS（Memory Operating System）のMOSProductをベースとして、CocoroAIプロジェクト専用のAPIを追加したバックエンドアプリケーションです。

### 1.2 主要機能
- **マルチモーダル対話**: テキスト+画像対応のストリーミングチャット
- **高度記憶機能**: MemOS統合によるNeo4j+SQLiteベースの永続記憶
- **通知・監視機能**: 外部通知とデスクトップ監視の独り言生成
- **設定統合管理**: Setting.json統合による動的設定変換
- **ログ統合管理**: CocoroDockとの連携ログシステム

### 1.3 システム要件
- **実行環境**: Windows PC（シングルユーザー）
- **配布形態**: PyInstaller zip配布（インストーラー不使用）
- **サービス形態**: アプリケーション実行（Windows Service不使用）

---

## 2. アーキテクチャ設計

### 2.1 システム構成

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   CocoroDock    │────│  CocoroCore2    │────│   CocoroShell   │
│   (WPF Client)  │    │  (FastAPI)      │    │   (Unity VRM)   │
│   ポート55600    │    │  ポート55601     │    │   ポート55605    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                    ┌─────────────────┐
                    │     Neo4j       │
                    │   (組み込み)     │
                    │  ポート55603     │
                    └─────────────────┘
```

### 2.2 ディレクトリ構成

```
CocoroCore2/src/
├── main.py                    # FastAPIアプリケーション
├── core/                      # コア機能
│   ├── __init__.py
│   ├── cocoro_product.py      # MOSProductラッパー
│   ├── config_manager.py      # 設定管理（参考コードベース）
│   ├── image_analyzer.py      # 画像分析（参考コードそのまま）
│   ├── message_generator.py   # メッセージ生成（参考コードそのまま）
│   └── log_manager.py         # ログ管理
├── api/                       # APIエンドポイント
│   ├── __init__.py
│   ├── health.py             # ヘルスチェック
│   ├── control.py            # システム制御
│   ├── mcp.py                # MCP関連
│   ├── users.py              # ユーザー管理
│   ├── memory.py             # メモリ操作
│   └── chat.py               # ストリーミングチャット
├── models/                    # データモデル
│   ├── __init__.py
│   ├── api_models.py         # API共通モデル
│   ├── image_models.py       # 画像関連（参考コードベース）
│   └── config_models.py      # 設定関連（参考コードベース）
└── utils/                     # ユーティリティ
    ├── __init__.py
    ├── neo4j_manager.py      # Neo4j管理
    └── streaming.py          # SSE支援
```

### 2.3 主要クラス設計

#### CocoroProductWrapper
```python
class CocoroProductWrapper:
    """MOSProductのラッパークラス（確証：参考コード設計）"""
    def __init__(self, cocoro_config: CocoroAIConfig):
        # MOSConfig動的生成（確証：config.py実装済み）
        mos_config = generate_memos_config_from_setting(cocoro_config)
        
        # MOSProduct初期化（確証：MemOS product.py仕様）
        self.mos_product = MOSProduct(
            default_config=mos_config,
            max_user_instances=1  # シングルユーザー
        )
        
        # 画像・メッセージ生成器（確証：参考コード実装済み）
        self.image_analyzer = ImageAnalyzer(cocoro_config.dict())
        self.message_generator = MessageGenerator(self)
```

#### LogManager
```python
class LogManager:
    """CocoroDock連携ログ管理（確証：ユーザー仕様）"""
    def __init__(self):
        self.log_buffer = deque(maxlen=300)  # 最大300件保存
        self.is_forwarding = False
        
    async def forward_logs_to_dock(self):
        """リアルタイムログ転送（確証：ユーザー要求仕様）"""
        # 初回：保存済みログ一括転送
        # 以降：リアルタイム転送
        pass
```

---

## 3. API仕様

### 3.1 エンドポイント一覧

| メソッド | エンドポイント | 機能 | 実装ベース |
|---------|---------------|------|------------|
| GET | `/api/health` | ヘルスチェック | 独自実装 |
| POST | `/api/control` | システム制御 | 独自実装 |
| GET | `/api/mcp/tool-registration-log` | MCPツール登録ログ | 独自実装 |
| GET | `/api/users` | ユーザーリスト取得 | MemOS流用 |
| POST | `/api/users` | ユーザー作成 | MemOS流用 |
| GET | `/api/users/{user_id}` | ユーザー情報取得 | MemOS流用 |
| GET | `/api/memory/user/{user_id}/stats` | 記憶統計取得 | MemOS流用 |
| DELETE | `/api/memory/user/{user_id}/all` | 記憶全削除 | MemOS流用 |
| POST | `/api/memory/add` | 記憶追加 | MemOS流用 |
| POST | `/api/memory/search` | 記憶検索 | MemOS流用 |
| POST | `/api/chat/stream` | ストリーミングチャット | MemOS+画像処理拡張 |

### 3.2 主要API仕様

#### ストリーミングチャット
```
POST /api/chat/stream
Content-Type: application/json

Request:
{
  "query": "string",
  "user_id": "string", 
  "context": {
    "source_type": "chat|notification|desktop_monitoring",
    "images": ["data:image/jpeg;base64,..."],  // Base64画像配列
    "notification_from": "string"  // 通知元（通知時のみ）
  }
}

Response: text/event-stream
data: {"type": "text", "data": "応答内容"}
data: {"type": "end"}

Error:
data: {"type": "error", "data": "エラーメッセージ"}
```

#### ヘルスチェック
```
GET /api/health

Response:
{
  "status": "healthy",
  "version": "1.0.0",
  "character": "つくよみちゃん", 
  "memory_enabled": true,
  "llm_model": "gpt-4o-mini",
  "active_sessions": 1,
  "mcp_status": {
    "total_servers": 0,
    "connected_servers": 0,
    "total_tools": 0
  }
}
```

### 3.3 レスポンス型定義
**確証**: CocoroDock/CommunicationModels.cs定義済み

- `StandardResponse` - 標準成功レスポンス
- `ErrorResponse` - エラーレスポンス  
- `HealthCheckResponse` - ヘルスチェック結果
- `UsersListResponse` - ユーザーリスト
- `MemoryStatsResponse` - 記憶統計
- `MemoryDeleteResponse` - 記憶削除結果

---

## 4. 設定管理システム

### 4.1 設定ファイル構造

#### 設定ファイルパス（確証：参考コード実装済み）
```
# PyInstaller実行時
{exe_dir}/../UserData2/Setting.json

# 開発実行時  
{project_root}/../UserData2/Setting.json
```

#### Setting.json必須項目（確証：DefaultSetting.json）
```json
{
  "cocoroCorePort": 55601,
  "cocoroMemoryDBPort": 55603,
  "cocoroMemoryWebPort": 55606,
  "isEnableMcp": false,
  "enable_pro_mode": false,
  "enable_internet_retrieval": false,
  "googleApiKey": "",
  "googleSearchEngineId": "",
  "internetMaxResults": 5,
  "multimodal_enabled": true,
  "max_image_size": 20000000,
  "currentCharacterIndex": 0,
  "characterList": [
    {
      "modelName": "つくよみちゃん",
      "isUseLLM": true,
      "apiKey": "sk-...",
      "llmModel": "gpt-4o-mini", 
      "visionApiKey": "",
      "visionModel": "gpt-4o-mini",
      "systemPromptFilePath": "つくよみちゃん_50e3ba63-f0f1-ecd4-5a54-3812ac2cc863.txt",
      "isEnableMemory": true,
      "userId": "tsukuyomichan",
      "embeddedApiKey": "",
      "embeddedModel": "text-embedding-3-small"
    }
  ]
}
```

### 4.2 設定変換フロー（確証：参考コード実装済み）

```
Setting.json読込
    ↓
CocoroAIConfig生成・検証（Pydantic）
    ↓
generate_memos_config_from_setting() → MOSConfig
    ↓
load_neo4j_config() → Neo4j接続設定
    ↓
各コンポーネント初期化
```

### 4.3 MOSConfig生成仕様（確証：参考コード実装済み）

```python
def generate_memos_config_from_setting(cocoro_config: CocoroAIConfig):
    """Setting.json → MOSConfig変換（確証：参考コード実装済み）"""
    current_character = cocoro_config.current_character
    
    return {
        "user_id": current_character.userId,
        "chat_model": {
            "backend": "openai",
            "config": {
                "model_name_or_path": current_character.llmModel,
                "api_key": current_character.apiKey,
                "api_base": "https://api.openai.com/v1"
            }
        },
        "mem_reader": {
            "backend": "simple_struct", 
            "config": {
                "llm": {...},
                "embedder": {...},
                "chunker": {...}
            }
        },
        "max_turns_window": cocoro_config.max_turns_window,
        "enable_textual_memory": True,
        "enable_activation_memory": False,
        "enable_mem_scheduler": True,
        "PRO_MODE": cocoro_config.enable_pro_mode,
        "mem_scheduler": {
            "backend": "general_scheduler",
            "config": {...}
        }
    }
```

---

## 5. データフロー設計

### 5.1 チャット処理フロー

#### 通常チャット（確証：CocoroCoreClient.cs仕様）
```
1. CocoroDock → POST /api/chat/stream
2. MemOSChatRequest受信（query, user_id, context）
3. ImageContext解析（source_type判定）
4. 画像ありの場合：
   a. Base64デコード・検証（max_image_size: 100MB）
   b. ImageAnalyzer.analyze_image()（OpenAI Vision API）
   c. 構造化分析結果生成（description, category, mood, time）
5. MOSProduct.chat_with_references()でストリーミング生成
6. Server-Sent Events形式で配信
```

#### 通知処理フロー（確証：参考コード実装済み）
```
1. 外部アプリ → CocoroDock → CocoroCore2
2. ImageContext(source_type="notification")生成
3. 画像ありの場合：ImageAnalyzer.analyze_image()
4. MessageGenerator.generate_notification_message()
5. MOSProduct統合でメモリ付き独り言生成
6. "○○からの通知で、△△の内容です。□□ですね。"形式
```

#### デスクトップ監視フロー（確証：参考コード実装済み）
```
1. CocoroDock定期実行 → CocoroCore2
2. ImageContext(source_type="desktop_monitoring")生成
3. ImageAnalyzer.analyze_image()（必須）
4. MessageGenerator.generate_desktop_monitoring_message()
5. "○○をしているのね。××ですね。"形式独り言生成
```

### 5.2 記憶管理フロー（確証：MemOS product.py仕様）

```
チャット・追加リクエスト
    ↓
MOSProduct.add()
    ↓ 
1. messages/memory_content/doc_pathから記憶抽出
2. MemCube自動管理（userId基準）
3. Neo4j（TreeTextMemory）+ SQLite（ユーザー管理）永続化
4. 非同期記憶保存（高速レスポンス）
```

### 5.3 起動初期化フロー

```
アプリ起動
    ↓
1. find_config_file() - PyInstaller対応検索
2. Setting.json読込・環境変数置換
3. CocoroAIConfig生成・検証
4. Neo4j非同期起動（組み込みプロセス）
5. MOSProduct初期化（max_user_instances=1）
6. 現在キャラクターのユーザー自動登録
7. MemCube復元・登録
8. FastAPIサーバー起動（ポート55601）
```

### 5.4 エラー処理フロー（確証：ユーザー仕様）

```
エラー発生
    ↓
1. 詳細ログ出力（LogManager経由）
2. アプリケーション即座終了
3. フォールバック処理なし
```

---

## 6. 依存関係・環境要件

### 6.1 Python依存関係（確証：DeepWiki調査 + 参考コード）

```python
# requirements.txt
MemoryOS[tree-mem,mem-reader]==1.0.0
fastapi>=0.104.0
uvicorn>=0.24.0
python-multipart>=0.0.6
Pillow>=10.0.0
pydantic>=2.0.0
openai>=1.0.0
```

### 6.2 MemOS拡張機能（確証：DeepWiki仕様）

- **tree-mem**: Neo4jベースTreeTextMemory（必須）
- **mem-reader**: PDF・テキスト記憶化機能（推奨）
- **mem-scheduler**: メモリスケジューラー（標準有効）

### 6.3 外部サービス（確証：参考コード・設定仕様）

- **OpenAI API**: テキスト生成（llmModel）+ 画像分析（visionModel）+ 埋め込み（embeddedModel）
- **Neo4j**: 組み込み版（ポート55603, 55606）

### 6.4 実行要件

- **OS**: Windows（PyInstaller配布）
- **Python**: 3.10以上
- **実行オプション**: `python -X utf8`（UTF-8モード必須）
- **ポート**: 55601（CocoroCore2）, 55603（Neo4j）, 55606（Neo4j Web）

---

## 7. 実装計画

### 7.1 開発優先順位

#### フェーズ1: 基盤構築（高優先度）
1. **設定管理システム** - 参考コードconfig.py流用
2. **MOSProduct統合** - ラッパークラス実装  
3. **Neo4j管理** - 非同期起動・接続管理
4. **基本APIエンドポイント** - health, control実装

#### フェーズ2: コア機能（中優先度）  
1. **画像処理システム** - 参考コードanalyzer.py流用
2. **メッセージ生成** - 参考コードmessage_generator.py流用
3. **ストリーミングチャット** - Server-Sent Events実装
4. **ユーザー・記憶管理API** - MemOS product_router流用

#### フェーズ3: 統合機能（低優先度）
1. **ログ管理システム** - CocoroDock連携
2. **MCP機能** - 最小限実装
3. **エラーハンドリング** - 統一化
4. **パフォーマンス最適化** - メモリ・速度調整

### 7.2 技術的考慮事項

#### 確証のある制約
- **エラー処理**: フォールバック不要、ログ出力後終了
- **起動方式**: Neo4j非同期起動、接続待ち合わせ必要
- **ログ管理**: 最大300件保存、200件以降破棄、リアルタイム転送
- **パフォーマンス**: トリッキーな方法使用禁止

#### 実装時注意点
1. **参考コードの活用**: analyzer.py, message_generator.py, config.py等はそのまま流用可能
2. **MemOS機能統合**: product_router.pyのエンドポイントを/apiに変更して活用
3. **CocoroDock期待仕様**: CommunicationModels.csのレスポンス型に準拠（必要なら変更可）
4. **設定変換処理**: generate_memos_config_from_setting()等確証済み処理活用

---

**本設計書は確証のある調査結果のみに基づいて作成されており、推測や仮定は含まれていません。**