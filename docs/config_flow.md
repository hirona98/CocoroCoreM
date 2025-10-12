# CocoroCoreM 設定処理フロー

## 起動時の全体像
- `src/main.py` の `CocoroCoreMApp.initialize()` が起点。最初に `core/config_manager.py` の `CocoroAIConfig.load()` が `UserDataM/Setting.json` を読み込む。
- 読み込んだ `CocoroAIConfig` を使って `core/cocoro_product.py` の `CocoroProductWrapper` を初期化。ここで LiteLLM 用設定 (`litellm_config`) を作り、`core/cocoro_mos_product.py` の `CocoroMOSProduct` に渡す。
- `CocoroProductWrapper.initialize()` がユーザー登録とメモリキューブの新規作成／再利用を担当。

## キューブ新規作成 (`_create_cube`)
- `UserDataM/Memory/cubes/<cube_id>/` を作成。`cube_id` は `<memoryId>_<memoryId>_cube`。
- キャラクター設定から LLM/Embedding/Neo4j 情報を取得し、MemOS が要求する最小構成の `config.json` を生成。
- `register_mem_cube()` を呼び出し、MemOS 標準の初期化を通して `config.json` の内容で `MemCube` を構築。
- MemOS 初期化後に `CocoroMOSProduct` 側の LiteLLM インテグレーションが走り、MemCube 内の LLM/Embedder/dispatcher_llm が LiteLLM に差し替わる。

## 既存キューブ再利用 (`_setup_current_character_cube`)
- `memos_users.db` からキューブ一覧を取得し、対象の `cube_id` が存在すれば `register_mem_cube()` を再実行。
- 既存 `config.json` を読み込み直し、LiteLLM 差し替えを再適用。
- `cube_path` が欠落している場合のみ `_create_cube()` を再実行して再生成。

## 次回起動時の挙動
- `Setting.json` を再読込して `CocoroAIConfig` を再構築する点は同じ。
- 既存キューブがある場合は `config.json` 再生成は行わず、再度 `register_mem_cube()` で読み込み → LiteLLM 差し替え。
- `Setting.json` を変更した場合、再起動で LiteLLM 設定は更新されるが、既存 `config.json` は自動更新されない。

## `config.json` が変わるケース
- `_create_cube()` が呼ばれた時のみ新規生成。
- `delete_character_memories()` でキューブを削除するとフォルダごと消えるため、次回起動で再生成が走る。

## LiteLLM 差し替え (`core/cocoro_mos_product.py`)
- コンストラクタ内で `_setup_litellm*` 系メソッドが呼ばれ、MemOS 標準の LLM/Embedder/dispatcher_llm を LiteLLM で置き換える前準備をする。
- `register_mem_cube()` オーバーライド後にも `_replace_new_memcube_*` が呼ばれ、新規 MemCube に対して常に LiteLLM 差し替えが適用される。

## 設定リロード
- `api/control.py` の `reload_config` が `CocoroAIConfig.load()` を再実行し、`CocoroCoreMApp.config` を差し替える。
- ただし既存 `config.json` は書き換えられない。更新が必要ならキューブ削除→再作成が必要。

## 保持している理由
- MemOS は初期化時に `config.json` を読み、本来の OpenAI クライアントや UniversalAPIEmbedder を構築する。この初期化が成功しないと LiteLLM 差し替え位置まで到達できない。
- Neo4j 接続など LiteLLM が触らない値も `config.json` から供給されるため、初期化成功・フォールバック時の安全策として `config.json` のエントリは残しておく必要がある。
