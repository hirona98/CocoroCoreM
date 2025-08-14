"""
CocoroCore2 Configuration Management

MemOS統合による設定管理システム
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, ValidationError, validator


class CharacterData(BaseModel):
    """キャラクター設定データ"""

    isReadOnly: bool = False
    modelName: str = "つくよみちゃん"
    isUseLLM: bool = False
    apiKey: str = ""
    llmModel: str = "gemini/gemini-2.0-flash"
    # 画像分析用設定
    visionModel: str = "gpt-4o-mini"  # 画像分析用モデル
    visionApiKey: str = ""  # 画像分析用APIキー（空ならapiKeyを使用）
    localLLMBaseUrl: str = ""
    systemPromptFilePath: str = ""
    isEnableMemory: bool = False
    userId: str = ""
    embeddedApiKey: str = ""
    embeddedModel: str = "ollama/nomic-embed-text"


class LoggingConfig(BaseModel):
    """ログ設定"""

    level: str = "INFO"
    file: str = "logs/cocoro_core2.log"
    max_size_mb: int = 10
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class CocoroAIConfig(BaseModel):
    """CocoroAI統合設定（Setting.json形式）"""

    cocoroDockPort: int = 55600
    cocoroCorePort: int = 55601
    cocoroMemoryPort: int = 55602
    cocoroMemoryDBPort: int = 55603
    cocoroMemoryWebPort: int = 55606
    cocoroShellPort: int = 55605
    isEnableMcp: bool = True

    # キャラクター設定
    currentCharacterIndex: int = 0
    characterList: list[CharacterData] = Field(default_factory=list)

    # CocoroCore2用の追加設定
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # MemOS高度機能設定
    enable_query_rewriting: bool = Field(default=True, description="文脈依存クエリの書き換え機能を有効にする")
    max_turns_window: int = Field(default=20, description="会話履歴の最大保持数")
    enable_pro_mode: bool = Field(default=True, description="PRO_MODE（Chain of Thought）を有効にする")
    enable_internet_retrieval: bool = Field(default=False, description="インターネット検索機能を有効にする")
    enable_memory_scheduler: bool = Field(default=True, description="メモリスケジューラーを有効にする（常に有効）")

    # Memory Scheduler詳細設定
    scheduler_top_k: int = Field(default=5, description="スケジューラーのメモリ取得数")
    scheduler_top_n: int = Field(default=3, description="スケジューラーの上位N件")
    scheduler_act_mem_update_interval: int = Field(default=300, description="アクティベーションメモリ更新間隔（秒）")
    scheduler_context_window_size: int = Field(default=5, description="スケジューラーのコンテキストウィンドウサイズ")
    scheduler_thread_pool_max_workers: int = Field(default=8, description="スケジューラーの最大ワーカー数")
    scheduler_consume_interval_seconds: int = Field(default=3, description="メッセージ消費間隔（秒）")
    scheduler_enable_parallel_dispatch: bool = Field(default=True, description="並列メッセージ処理を有効にする")
    scheduler_enable_act_memory_update: bool = Field(default=False, description="アクティベーションメモリ更新を有効にする（API経由LLMでは通常無効）")

    # Internet Retrieval設定
    googleApiKey: str = Field(default="", description="Google Custom Search API キー")
    googleSearchEngineId: str = Field(default="", description="Google Custom Search Engine ID (cse_id)")
    internetMaxResults: int = Field(default=5, description="インターネット検索の最大結果数")

    # マルチモーダル画像処理設定
    multimodal_enabled: bool = Field(default=True, description="マルチモーダル画像処理機能を有効にする")
    max_image_size: int = Field(default=20000000, description="最大画像サイズ (20MB)")
    analysis_timeout_seconds: int = Field(default=60, description="画像分析のタイムアウト時間（秒）")
    
    # パフォーマンス最適化設定
    enable_parallel_processing: bool = Field(default=True, description="並列処理を有効にする")

    @property
    def current_character(self) -> Optional[CharacterData]:
        """現在選択されているキャラクターを取得"""
        if 0 <= self.currentCharacterIndex < len(self.characterList):
            return self.characterList[self.currentCharacterIndex]
        return None

    @property
    def character_name(self) -> str:
        """現在のキャラクター名"""
        char = self.current_character
        return char.modelName if char else "つくよみちゃん"

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "CocoroAIConfig":
        """設定ファイルから設定を読み込む

        Args:
            config_path: 設定ファイルパス（指定がない場合は自動検索）

        Returns:
            CocoroAIConfig: 設定オブジェクト
        """
        if config_path is None:
            config_path = find_config_file()

        # 設定ファイル読み込み
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)

        # 環境変数置換
        config_data = substitute_env_variables(config_data)

        try:
            return cls(**config_data)
        except ValidationError as e:
            raise ConfigurationError(f"設定ファイルの検証に失敗しました: {e}")


class ConfigurationError(Exception):
    """設定関連エラー"""

    pass


def parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析する"""
    parser = argparse.ArgumentParser(description="CocoroCore2設定ローダー")
    parser.add_argument("--config-dir", "-c", help="設定ファイルのディレクトリパス")
    parser.add_argument("--config-file", "-f", help="設定ファイルパス")
    return parser.parse_args()


def find_config_file() -> str:
    """CocoroAI設定ファイルを自動検索する

    検索順序:
    1. ../UserData2/Setting.json (統合設定ファイル)

    Returns:
        str: 設定ファイルパス

    Raises:
        ConfigurationError: 設定ファイルが見つからない場合
    """
    # 実行ディレクトリの決定
    if getattr(sys, "frozen", False):
        # PyInstallerなどで固められたexeの場合
        base_dir = Path(sys.executable).parent
    else:
        # 通常のPythonスクリプトとして実行された場合
        base_dir = Path(__file__).parent.parent

    # Setting.jsonのパス（複数パターンを試行）
    config_paths = [
        base_dir.parent / "UserData2" / "Setting.json",  # CocoroCore2/../UserData2/
        base_dir.parent.parent / "UserData2" / "Setting.json",  # CocoroAI/UserData2/
    ]
    
    for config_path in config_paths:
        if config_path.exists():
            return str(config_path)

    raise ConfigurationError(f"Setting.jsonが見つかりません。検索パス: {[str(p) for p in config_paths]}")


def substitute_env_variables(data: Any) -> Any:
    """設定データ内の環境変数を置換する

    ${VAR_NAME} 形式の環境変数参照を実際の値に置き換える

    Args:
        data: 設定データ（dict, list, str等）

    Returns:
        Any: 環境変数が置換された設定データ
    """
    if isinstance(data, str):
        # ${VAR_NAME} パターンを検索・置換
        def replace_env_var(match):
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))  # 見つからない場合は元の文字列を返す

        return re.sub(r"\$\{([^}]+)\}", replace_env_var, data)

    elif isinstance(data, dict):
        return {key: substitute_env_variables(value) for key, value in data.items()}

    elif isinstance(data, list):
        return [substitute_env_variables(item) for item in data]

    else:
        return data


def generate_memos_config_from_setting(cocoro_config: "CocoroAIConfig") -> Dict[str, Any]:
    """Setting.jsonから動的にMemOS設定を生成する

    Args:
        cocoro_config: CocoroAI設定オブジェクト

    Returns:
        Dict[str, Any]: MemOS設定データ

    Raises:
        ConfigurationError: 設定が不正な場合
    """
    current_character = cocoro_config.current_character
    if not current_character:
        raise ConfigurationError("現在のキャラクターが見つかりません")

    # LLMモデルとAPIキーをキャラクター設定から取得
    llm_model = current_character.llmModel or "gpt-4o-mini"
    api_key = current_character.apiKey or ""

    # 埋め込みモデルとAPIキーをキャラクター設定から取得
    embedded_model = current_character.embeddedModel or "text-embedding-3-large"
    embedded_api_key = current_character.embeddedApiKey or api_key  # APIキーが空なら通常のを使用

    # MemOS設定を動的に構築
    memos_config = {
        "user_id": current_character.userId or "user",
        "chat_model": {"backend": "openai", "config": {"model_name_or_path": llm_model, "api_key": api_key, "api_base": "https://api.openai.com/v1"}},
        "mem_reader": {
            "backend": "simple_struct",
            "config": {
                "llm": {"backend": "openai", "config": {"model_name_or_path": llm_model, "temperature": 0.0, "api_key": api_key, "api_base": "https://api.openai.com/v1"}},
                "embedder": {"backend": "universal_api", "config": {"model_name_or_path": embedded_model, "provider": "openai", "api_key": embedded_api_key, "base_url": "https://api.openai.com/v1"}},
                "chunker": {"backend": "sentence", "config": {"chunk_size": 512, "chunk_overlap": 128}},
            },
        },
        # MemOS高度機能設定
        "max_turns_window": cocoro_config.max_turns_window,
        "enable_textual_memory": True,
        "enable_activation_memory": False,  # API経由LLMでは無効
        "enable_mem_scheduler": cocoro_config.enable_memory_scheduler,
        "top_k": 5,
        # PRO_MODE (Chain of Thought) 設定
        "PRO_MODE": cocoro_config.enable_pro_mode,
    }

    # Memory Scheduler設定を追加（常に有効）
    memos_config["mem_scheduler"] = {
        "backend": "general_scheduler",
        "config": {
            "top_k": cocoro_config.scheduler_top_k,
            "top_n": cocoro_config.scheduler_top_n,
            "act_mem_update_interval": cocoro_config.scheduler_act_mem_update_interval,
            "context_window_size": cocoro_config.scheduler_context_window_size,
            "thread_pool_max_workers": cocoro_config.scheduler_thread_pool_max_workers,
            "consume_interval_seconds": cocoro_config.scheduler_consume_interval_seconds,
            "enable_parallel_dispatch": cocoro_config.scheduler_enable_parallel_dispatch,
            "enable_act_memory_update": cocoro_config.scheduler_enable_act_memory_update,
        },
    }

    return memos_config


def load_neo4j_config() -> Dict[str, Any]:
    """Neo4j設定をSetting.jsonから動的に生成する

    Returns:
        Dict[str, Any]: Neo4j設定データ

    Raises:
        ConfigurationError: 設定ファイルが見つからない場合
    """
    # 実行ディレクトリの決定
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).parent.parent

    # Setting.jsonのパス（複数パターンを試行）
    config_paths = [
        base_dir.parent / "UserData2" / "Setting.json",  # CocoroCore2/../UserData2/
        base_dir.parent.parent / "UserData2" / "Setting.json",  # CocoroAI/UserData2/
    ]
    
    setting_path = None
    for path in config_paths:
        if path.exists():
            setting_path = path
            break
    
    # Setting.jsonから設定を読み込み
    try:
        if not setting_path:
            raise ConfigurationError(f"Setting.jsonが見つかりません: {[str(p) for p in config_paths]}")

        with open(setting_path, "r", encoding="utf-8") as f:
            setting_data = json.load(f)

        # Neo4j設定を動的に生成
        current_char_index = setting_data.get("currentCharacterIndex", 0)
        character_list = setting_data.get("characterList", [])

        # embedded_enabledの決定
        if current_char_index < len(character_list):
            current_char = character_list[current_char_index]
            embedded_enabled = current_char.get("isEnableMemory", False)
        else:
            embedded_enabled = False

        # URIの生成
        memory_db_port = setting_data.get("cocoroMemoryDBPort", 7687)
        memory_web_port = setting_data.get("cocoroMemoryWebPort", 55606)
        uri = f"bolt://127.0.0.1:{memory_db_port}"

        # Neo4j設定辞書を作成
        neo4j_config = {"uri": uri, "web_port": memory_web_port, "embedded_enabled": embedded_enabled}

    except Exception as e:
        raise ConfigurationError(f"Setting.jsonの処理に失敗しました: {e}")

    return substitute_env_variables(neo4j_config)


def create_mos_config_from_dict(mos_config_dict: Dict[str, Any]):
    """辞書からMOSConfigオブジェクトを作成する
    
    MemOS公式APIConfig.create_user_config()と同じ方法を使用
    確証: /Reference/MemOS/src/memos/api/config.py:461

    Args:
        mos_config_dict: MemOS設定辞書

    Returns:
        MOSConfig: MOSConfigオブジェクト

    Raises:
        ConfigurationError: MOSConfig作成に失敗した場合
    """
    try:
        # 遅延インポートでMemOSの循環依存を回避
        from memos import MOSConfig
        import warnings
        import logging
        
        # Pydanticの cosmetic な警告を抑制（機能的には問題なし）
        # 理由: MemOS内部のmodel_validator処理でシリアライゼーション警告が出るが
        #       実際の動作には全く影響しない（MemOS公式でも同じ現象）
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", 
                                  message="Pydantic serializer warnings", 
                                  category=UserWarning)
            warnings.filterwarnings("ignore",
                                  message=".*PydanticSerializationUnexpectedValue.*",
                                  category=UserWarning)
            
            # MemOS公式コードと同じ辞書形式でMOSConfig作成 (config.py:461参照)
            return MOSConfig(**mos_config_dict)

    except ImportError as e:
        raise ConfigurationError(f"MemOSライブラリが利用できません: {e}")
    except Exception as e:
        raise ConfigurationError(f"MOSConfig作成に失敗しました: {e}")


def get_mos_config(config: "CocoroAIConfig" = None):
    """MOSConfigオブジェクトを取得する

    Args:
        config: CocoroAI設定オブジェクト（必須）

    Returns:
        MOSConfig: MOSConfigオブジェクト

    Raises:
        ConfigurationError: MOSConfig作成に失敗した場合
    """
    if config is None:
        # configが指定されていない場合は現在の設定を読み込む
        config = CocoroAIConfig.load()

    memos_config_data = generate_memos_config_from_setting(config)
    return create_mos_config_from_dict(memos_config_data)