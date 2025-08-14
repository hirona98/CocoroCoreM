# CocoroCore2設計調査結果と疑問点リスト

## 調査サマリー

CocoroCore2は、MemOS（Memory Operating System）のMOSProductをベースとして、CocoroAIプロジェクト専用のAPIを追加したバックエンドアプリケーションです。

### 主要な発見

1. **MemOS MOSProduct**: 高機能なマルチユーザー対応のメモリ管理システム
2. **CocoroCore2の現状**: srcディレクトリが空で、実装はこれから開始
3. **Neo4j統合**: 既に組み込みNeo4jが配置済み
4. **API仕様**: 基本的なAPIエンドポイントが定義済み

## 技術アーキテクチャの理解

### MemOS MOSProduct の主要機能

#### コア機能
- **マルチユーザー管理**: ユーザー登録、設定管理、権限管理
- **メモリタイプ**: テキスト、アクティベーション（KVキャッシュ）、パラメトリック
  ● 今回はテキストメモリのみです
- **永続化**: ユーザーデータとメモリキューブの永続保存
- **チャット機能**: メモリ拡張型対話（参照付きストリーミング）
  ● 基本的には、ユーザーから始まるチャットだが、通知機能とデスクトップウォッチ機能がある
  ● 通知機能
     1. 外部アプリからCocoroDockにREST APIで通知をいれる（カレンダーアプリからリマインダーなど）
     2. CocoroDockはCocoroCore2にその内容をチャットとして渡す（通知であることがわかるように渡す）
     3. CocoroCore2は、キャラクターに「カレンダーからXXっていう通知が来たよ」という形でユーザーに伝える
  ● デスクトップウォッチ機能
      1. CocoroDockが一定間隔でデスクトップキャプチャを行い、画像をチャットとしてCocoroCore2に渡す（デスクトップウォッチであるとわかるように渡す）
      2. CocoroCore2は、キャラクターが画面を覗き込んで独り言をいうかのように振る舞う（「SNSもほどほどにね」など）
  ● すべてのチャットは画像対応。MemOSは画像に対応していないため、一旦LLMで画像の説明をテキストで作成してもらい、それとユーザーコメントを一緒にMemOSにわたす。

- **検索機能**: セマンティック検索とグラフ検索
- **インターネット検索**: Google Custom Search統合

#### 実装されている主要メソッド
- `user_register()`: ユーザー登録とデフォルトキューブ作成
- `chat_with_references()`: メモリ参照付きチャット（ストリーミング）
- `search()`: メモリ検索
- `add()`: メモリ追加
- `get_all()`: メモリ取得（タイプ別）
- `register_mem_cube()`: MemCube登録

### CocoroCore2 要求API

#### 実装必要なエンドポイント（API_SPECIFICATION.mdより）
1. `GET /health` - ヘルスチェック ✅（簡単）
2. `POST /api/control` - システム制御 ✅（実装済みベース有り）
3. `GET /api/mcp/tool-registration-log` - MCP関連 ⚠️（未実装予定）
4. チャット機能 - TODO状態 ⚠️（要仕様確定）
5. `GET /api/memory/user/{user_id}/stats` - ユーザー記憶統計 ⚠️（要仕様確定）
6. `DELETE /api/memory/user/{user_id}/all` - ユーザー記憶削除 ✅（実装可能）
7. `GET /api/users` - ユーザーリスト取得 ✅（実装済みベース有り）
8. ユーザー作成 - TODO状態 ⚠️（要仕様確定）

## 主要な疑問点と課題

### 1. アーキテクチャ設計の疑問

#### 🔴 重要度：高
- **MOSProductの直接利用 vs カスタマイゼーション**
  - Q: MOSProductをそのまま継承するか、ラッパークラスを作成するか？
    ● ラッパークラスを作成

  - Q: MemOSの設定ファイル（MOSConfig）をCocoroAI用にどうカスタマイズするか？
    ● CocoroAIの設定は Setting.json にすべて入る。そこからMOSやneo4jの設定を作る。必要なら Setting.json に項目を追加する。
  
- **API エンドポイントの統合方式**
  - Q: MemOSのproduct_router.py（/productプレフィックス）とCocoroCore2のAPI仕様（/apiプレフィックス）をどう統合するか？
    ● /api にまとめる

  - Q: 既存のMemOS APIを活用するか、独自実装するか？
    ● おすすめは？

- **永続化ストレージの設定**
  - Q: ユーザーデータベース（MySQL）の設定はどこで管理するか？
    ● MySQLなんて使うの？SQLiteとNeo4jじゃないの？
    ● どんな設定が必要なの？

  - Q: MemCubeの保存先ディレクトリ（CUBE_PATH）をどう設定するか？
    ● 固定ディレクトリ（必要ならユーザ名などで自動決定）

### 2. 機能要件の詳細化

#### 🟡 重要度：中
- **チャット機能の仕様**
  - Q: CocoroDockからのチャットリクエスト形式は？
    ● こっちに合わせるので作りやすい形にして

  - Q: 画像対応の具体的な仕様は？（Base64エンコード済み？）
    ● こっちに合わせるので作りやすい形にして（Base64エンコード済みです）

  - Q: メッセージタイプ（chat/notification/desktop_monitoring）の処理方法は？
    ● おすすめは？

- **ユーザー記憶統計の詳細**
  - Q: どのような統計情報を提供するか？
    ● ユーザーの記憶を削除する必要があるとき、選択するための情報を提供する
    ● 最低限はユーザ名のみ

  - Q: リアルタイム更新が必要か？
    ● 不要

- **ユーザー作成機能**
  - Q: CocoroAI固有の要件があるか？
    ● エンドユーザーは一人、AIは複数人

  - Q: デフォルトの興味・設定はどう決定するか？
    ● 設定ファイルから読んでください

### 3. 技術的実装の詳細

#### 🟡 重要度：中
- **設定ファイル管理**
  - Q: `/UserData2/Setting.json`の構造とMemOSConfigの関係は？
    ● CocoroAIの設定はすべて Setting.json に入り、CocoroDockで編集します。それを元に、CocoroCore2はMemOSConfigを作ります
    ● 解説付きのデフォルト設定ファイルを D:\MyProject\AliceEncoder\DesktopAssistant\CocoroAI\CocoroCore2\docs\DefaultSetting.json においておきます
    ● MemOSの設定ファイルの項と合わせて検討すること
  
  - Q: Neo4j設定はMemOSのデフォルト設定で十分か？
    ● 必要な情報を Setting.json から読み込みます

- **ログとエラーハンドリング**
  - Q: MemOSのログ設定をCocoroAI用にカスタマイズする必要があるか？
    ● 未定

  - Q: DingDing通知（online_bot/error_bot）は使用するか？
    ● 使わない

- **パフォーマンス最適化**
  - Q: max_user_instancesの適切な値は？
    ● エンドユーザは一人、PC上で動作します。それに合わせてください。

  - Q: メモリ使用量の制限はあるか？
    ● エンドユーザは一人、PC上で動作します。それに合わせてください。

### 4. 開発・デプロイメントの課題

#### 🟢 重要度：低
- **依存関係管理**
  - Q: MemOSのrequirements.txtとCocoroCore2の依存関係をどう統合するか？
    ● CocoroCore2 の requirements.txt にMemOSが入る想定ですが、問題ありますか？

  - Q: オプショナル依存関係（tree-mem, mem-reader等）は何が必要か？
    ● 詳しく説明して

- **環境設定**
  - Q: 開発環境でのNeo4j起動方法は？
    ● PyInstallerですべてまとめる。CocoroCore2起動時に自動起動する。

  - Q: WSL環境でのパフォーマンス最適化は必要か？
    ● 不要

- **テスト方針**
  - Q: MemOSのテストフレームワークを活用するか？
    ● テストは使わない

  - Q: 統合テストの範囲はどこまでか？
    ● テストはしない

## 推奨される次のステップ

そのまえにまずは上記質問に答えてください

### フェーズ1: 基礎設計確定（優先度：高）
1. MOSProductベースのアーキテクチャ設計を確定
2. API仕様の詳細化（特にTODO項目）
3. 設定ファイル構造の設計

### フェーズ2: 実装準備（優先度：中）
1. 開発環境セットアップガイドの作成
2. MemOS依存関係の整理
3. 基本的なプロジェクト構造の作成

### フェーズ3: 段階的実装（優先度：中）
1. 基本APIエンドポイントの実装
2. MOSProduct統合
3. CocoroAI固有機能の追加

## 追加の注意点

● PyInstallerにまとめてユーザのPC（Windows）で動作させます。
● zip配布です
● インストーラーは使いません
● サービスとして動作させません

## 技術的な実装提案

### 推奨アーキテクチャ
```python
# CocoroCore2/src/cocoro_core/
# ├── main.py              # FastAPI アプリケーション
# ├── config/              # 設定管理
# │   ├── cocoro_config.py # CocoroAI固有設定
# │   └── memos_config.py  # MemOS統合設定
# ├── api/                 # APIエンドポイント
# │   ├── health.py        # ヘルスチェック
# │   ├── control.py       # システム制御
# │   ├── memory.py        # メモリ操作
# │   ├── users.py         # ユーザー管理
# │   └── chat.py          # チャット機能
# ├── core/                # コア機能
# │   ├── cocoro_product.py # MOSProductのラッパー
# │   └── message_handler.py # メッセージ処理
# └── utils/               # ユーティリティ
#     ├── logging.py       # ログ設定
#     └── error_handler.py # エラー処理
```

この調査結果をもとに、具体的な設計方針を決定してください。