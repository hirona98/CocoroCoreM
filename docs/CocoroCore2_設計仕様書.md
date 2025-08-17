# CocoroCore2 設計仕様書

## 1. プロジェクト概要

### 1.1 システム概要
CocoroCore2は、MemOS（Memory Operating System）のMOSProductをベースとして、CocoroAIプロジェクト専用のAPIを追加したバックエンドアプリケーションです。

### 1.2 主要機能
- **マルチモーダル対話**: テキスト+画像対応のストリーミングチャット
- **完全自動記憶管理**: MemScheduler統合による全自動記憶保存・整理・最適化
- **高度記憶機能**: MemOS統合によるNeo4j+SQLiteベースの永続記憶
- **キューブID自動決定**: Setting.jsonから自動生成
- **通知・監視機能**: 外部通知とデスクトップ監視の独り言生成
- **設定統合管理**: Setting.json統合による動的設定変換
- **ログ統合管理**: CocoroDockとの連携ログシステム

### 1.3 重要な設計発見
**MemOS MemSchedulerによる完全自動記憶管理（確証済み）**:
- `MOSProduct.chat_with_references()`が記憶を完全自動処理
- ユーザークエリ+アシスタント応答が自動保存
- 手動`add()`メソッド呼び出しは不要
- QUERY_LABEL、ANSWER_LABELの自動MemScheduler連携

### 1.4 システム要件
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


---

## 3. 設定管理システム

### 設定ファイルパス
```
# PyInstaller実行時
{exe_dir}/../UserData2/Setting.json

# 開発実行時  
{project_root}/../UserData2/Setting.json
```

---

## ⚠️ 重要な注意事項
  **DeepWiki情報の信頼性について**:
   - DeepWikiでは、MOSCore・MOSProduct・MemOS全般について整理されていない情報が混在する可能性があります
   - 本報告書のDeepWiki由来の情報は「参考情報」として扱い、実際のソースコード確認が必要です
   - 確証のある情報として扱えるのは、MemOS-DocsおよびReference/MemOS実コードのみです

---

## MemOSドキュメント
ソースコード: ../Reference/MemOS
ドキュメント: ../Reference/MemOS-Docs
GitHub: https://github.com/MemTensor/MemOS （Deepwiki対応）
