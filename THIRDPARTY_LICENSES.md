# Third-Party Licenses

このファイルには、CocoroCoreMで使用されているサードパーティライブラリのライセンス情報が含まれています。

## ライセンス情報の取得方法

仮想環境で以下のコマンドを実行することで、最新のライセンス情報を取得できます：

```bash
# 仮想環境を有効化
.\.venv\Scripts\Activate

# pip-licensesをインストール
pip install pip-licenses

# ライセンス情報を自動生成
pip-licenses --format=markdown --with-authors --with-urls --output-file=THIRDPARTY_LICENSES_AUTO.md

# その他の便利な形式
pip-licenses --format=json --output-file=licenses.json
pip-licenses --format=csv --output-file=licenses.csv
pip-licenses --format=plain-vertical --with-license-file --no-license-path > licenses_full.txt
```

THIRDPARTY_LICENSES.txt
  - 配布用の統合ファイル
  - 上部にJREのライセンス情報と説明を記載
  - 下部にlicenses_full.txtの内容を追記

## 主要ライブラリのライセンス概要

### MemOS および関連コンポーネント
- **MemoryOS** (1.0.0) - Apache License 2.0
  - 著作権: Copyright 2025 - Present MemTensor Research
  - URL: https://memos.openmem.net/

### ウェブフレームワーク
- **FastAPI** - MIT License
- **uvicorn** - BSD License
- **Starlette** - BSD License

### データ処理・検証
- **Pydantic** - MIT License
- **SQLAlchemy** (2.0.43) - MIT License
- **Pillow** - HPND License

### AI/LLM関連
- **OpenAI** - MIT License
- **Transformers** - Apache License 2.0
- **sentence-transformers** - Apache License 2.0
- **scikit-learn** - BSD License (3-clause)

### データベース・キャッシュ
- **neo4j** - Apache License 2.0
- **redis** - BSD License (3-clause)

### HTTPクライアント
- **httpx** - BSD License
- **aiohttp** - Apache License 2.0

### メッセージング
- **pika** (RabbitMQ client) - BSD License

### その他の重要なライブラリ
- **numpy** - BSD License
- **PyYAML** (6.0.2) - MIT License
- **Jinja2** (3.1.6) - BSD License
- **cryptography** (45.0.6) - Apache-2.0 OR BSD-3-Clause
