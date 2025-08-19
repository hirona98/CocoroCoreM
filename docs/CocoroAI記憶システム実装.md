# CocoroAI記憶システム実装

## 概要

CocoroAIは、記憶抽出と記憶活用を明確に分離した実装を採用しています。

### 記憶抽出（Memory Extraction）
- **実行者**: キャラクター性を持たない中立的なLLM
- **形式**: 客観的・第三者視点での事実記録
- **言語**: 英語（MemOS標準プロンプト使用）

### 記憶活用（Memory Usage）
- **実行者**: CocoroAIのキャラクターを持つLLM
- **形式**: 記憶を解釈して自然な会話に活用
- **言語**: 日本語（CocoroAIプロンプト使用）

## 実装アーキテクチャ

```
MemOSCore
└── MOSProduct（MemOS標準）
    └── CocoroMOSProduct（CocoroAI拡張）
        ├── 標準SimpleStructMemReader（記憶抽出）
        └── COCORO_MEMORY_INSTRUCTION（記憶活用指示）
```

## 実装詳細

### CocoroMOSProduct (cocoro_mos_product.py)

**機能**: MOSProductを継承し、CocoroAI専用の記憶活用指示を追加

**主要コンポーネント**:
- `COCORO_MEMORY_INSTRUCTION`: 日本語での記憶参照指示
- `_build_enhance_system_prompt()`: システムプロンプト構築

**記憶活用指示の内容**:
```
## 記憶機能について
私は過去の会話や情報を記憶する機能を持っています。
関連する記憶がある場合は、自然な会話の中で参照します。

### 記憶の参照方法
- 記憶を参照する際は `[番号:記憶ID]` の形式で記載します
```

## 処理フロー

### 1. 記憶保存時
```
会話データ → SimpleStructMemReader（英語プロンプト） → 客観的記憶
例: "The user expressed concern about the project deadline"
```

### 2. 記憶参照時
```
客観的記憶 → CocoroAI（日本語指示） → 自然な会話での活用
例: "前にプロジェクトのことで心配してたよね、大丈夫？"
```
