# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## CocoroCoreM - MemOS統合バックエンド

CocoroCoreMは、MemOS（Memory Operating System）を統合したCocoroAIのバックエンドシステムです。


## 開発環境セットアップ

### 必須要件
- Python 3.10以上
- **重要**: Python UTF-8モード必須（`python -X utf8`）
- Windows環境またはWSL2環境
- WSL環境ではpowershell.exe経由でpythonを実行すること

### セットアップ手順

```bash
# 仮想環境作成
py -3.10 -m venv .venv

# 仮想環境活性化（WSL環境）
powershell.exe ".\.venv\Scripts\Activate"

# 仮想環境活性化（Windows環境）
.\.venv\Scripts\Activate

# 依存関係インストール
pip install -r requirements.txt
```

## 開発・実行コマンド

### 開発実行
```bash
# 実行（UTF-8モード必須）
python -X utf8 src/main.py

# 設定ファイル指定（UTF-8モード必須）
python -X utf8 src/main.py --config-file ../UserDataM/setting.json
```

### ビルド
```bash
# 自動ビルド実行
build.bat

# または手動実行
python build_cocoro2.py
```

## MemOSドキュメント
ソースコード: ../Reference/MemOS
ドキュメント: ../Reference/MemOS-Docs
GitHub: https://github.com/MemTensor/MemOS （Deepwiki対応）
