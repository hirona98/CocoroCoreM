"""
CocoroCoreM Configuration Management

MemOS統合による設定管理システム
"""

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, ValidationError, validator

logger = logging.getLogger(__name__)


class CharacterData(BaseModel):
    """キャラクター設定データ"""

    isReadOnly: bool = False
    modelName: str = ""
    isUseLLM: bool = False
    apiKey: str = ""
    llmModel: str = ""
    # 画像分析用設定
    visionModel: str = ""  # 画像分析用モデル
    visionApiKey: str = ""  # 画像分析用APIキー（空ならapiKeyを使用）
    localLLMBaseUrl: str = ""
    systemPromptFilePath: str = ""
    isEnableMemory: bool = False
    memoryId: str = ""
    embeddedApiKey: str = ""
    embeddedModel: str = ""
    
    def get_api_key(self) -> str:
        """APIキーを取得（空の場合はダミー値を返す）"""
        return self.apiKey or "dummy-api-key"
    
    def get_vision_api_key(self) -> str:
        """Vision APIキーを取得（空の場合はダミー値を返す）"""
        return self.visionApiKey or self.get_api_key()
    
    def get_embedded_api_key(self) -> str:
        """埋め込みAPIキーを取得（空の場合はダミー値を返す）"""
        return self.embeddedApiKey or self.get_api_key()
    


class LoggingConfig(BaseModel):
    """ログ設定"""

    level: str = "DEBUG"
    file: str = "logs/cocoro_core2.log"
    max_size_mb: int = 10
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # ログ長制限関連
    enable_truncation: bool = True
    truncate_marker: str = "【切り詰め】"
    max_message_length: int = 2000  # デフォルト値
    level_specific_lengths: Dict[str, int] = {
        "DEBUG": 200,
        "INFO": 200,
        "WARNING": 400,
        "ERROR": 10000,
        "CRITICAL": 10000
    }


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

    # CocoroCoreM用の追加設定
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # MemOS高度機能設定
    enable_query_rewriting: bool = Field(default=True, description="文脈依存クエリの書き換え機能を有効にする")
    max_turns_window: int = Field(default=20, description="会話履歴の最大保持数")
    enable_pro_mode: bool = Field(default=True, description="PRO_MODE（Chain of Thought）を有効にする")
    enable_internet_retrieval: bool = Field(default=False, description="インターネット検索機能を有効にする")
    enable_memory_scheduler: bool = Field(default=True, description="メモリスケジューラーを有効にする（常に有効）")
    enable_activation_memory: bool = Field(default=False, description="アクティベーションメモリ更新を有効にする（API経由LLMでは通常無効）")

    # Memory Scheduler詳細設定
    scheduler_top_k: int = Field(default=5, description="スケジューラーのメモリ取得数")
    scheduler_top_n: int = Field(default=3, description="スケジューラーの上位N件")
    scheduler_act_mem_update_interval: int = Field(default=300, description="アクティベーションメモリ更新間隔（秒）")
    scheduler_context_window_size: int = Field(default=5, description="スケジューラーのコンテキストウィンドウサイズ")
    scheduler_thread_pool_max_workers: int = Field(default=8, description="スケジューラーの最大ワーカー数")
    scheduler_consume_interval_seconds: int = Field(default=3, description="メッセージ消費間隔（秒）")
    scheduler_enable_parallel_dispatch: bool = Field(default=True, description="並列メッセージ処理を有効にする")

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
        return char.modelName

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
    parser = argparse.ArgumentParser(description="CocoroCoreM設定ローダー")
    parser.add_argument("--config-dir", "-c", help="設定ファイルのディレクトリパス")
    parser.add_argument("--config-file", "-f", help="設定ファイルパス")
    return parser.parse_args()


def find_config_file() -> str:
    """CocoroAI設定ファイルを自動検索する

    検索順序:
    1. ../UserDataM/Setting.json (統合設定ファイル)

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
        base_dir.parent / "UserDataM" / "Setting.json",  # CocoroCoreM/../UserDataM/
        base_dir.parent.parent / "UserDataM" / "Setting.json",  # CocoroAI/UserDataM/
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


def generate_memos_config_from_setting(cocoro_config: "CocoroAIConfig", use_relative_paths: bool = True) -> Dict[str, Any]:
    """Setting.jsonから動的にMemOS設定を生成する

    Args:
        cocoro_config: CocoroAI設定オブジェクト
        use_relative_paths: 相対パスを使用するかどうか（デフォルト: True）

    Returns:
        Dict[str, Any]: MemOS設定データ

    Raises:
        ConfigurationError: 設定が不正な場合
    """
    current_character = cocoro_config.current_character
    if not current_character:
        raise ConfigurationError("現在のキャラクターが見つかりません")

    # LLMモデルとAPIキーをキャラクター設定から取得
    llm_model = current_character.llmModel or ""
    api_key = current_character.get_api_key()

    # 埋め込みモデルとAPIキーをキャラクター設定から取得
    embedded_model = current_character.embeddedModel or ""
    embedded_api_key = current_character.get_embedded_api_key()
    
    # 埋め込みモデルがLiteLLM形式かチェック（プロバイダー推定用）
    if "/" in embedded_model:
        embedded_provider = embedded_model.split("/")[0]
    else:
        embedded_provider = "openai"  # デフォルトはOpenAI

    # UserDataMディレクトリを探す（DBファイル保存用）
    base_dir = Path(__file__).parent.parent
    user_data_paths = [
        base_dir.parent / "UserDataM",  # CocoroCoreM/../UserDataM/
        base_dir.parent.parent / "UserDataM",  # CocoroAI/UserDataM/
    ]
    
    user_data_dir = None
    for path in user_data_paths:
        if path.exists():
            user_data_dir = path
            break
    
    if user_data_dir is None:
        # デフォルトは一つ上のディレクトリに作成
        user_data_dir = base_dir.parent / "UserDataM"
    
    # Memory ディレクトリを作成し、memos_users.dbのパスを設定
    memory_dir = user_data_dir / "Memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    
    if use_relative_paths:
        # 相対パスを使用（プロジェクトルートからの相対パス）
        db_path = "UserDataM/Memory/memos_users.db"
        scheduler_dump_path = "UserDataM/Memory/scheduler"
    else:
        # 従来の絶対パス
        db_path = str(memory_dir / "memos_users.db")
        scheduler_dump_path = str(memory_dir / "scheduler")

    # 注意：MemOSの標準embedderは使用せず、LiteLLMEmbedderで置き換えるため、
    # 複雑な環境変数設定は不要（CocoroMOSProductで直接置き換え）
    logger.info(f"埋め込み設定: model={embedded_model}, provider={embedded_provider}")
    logger.info(f"注意: 実際の埋め込み処理はLiteLLMEmbedderで実行されます")

    # MemOS設定を動的に構築
    memos_config = {
        "user_id": current_character.memoryId,  # キャラクター固有のユーザーIDを使用
        "chat_model": {"backend": "openai", "config": {"model_name_or_path": llm_model, "api_key": api_key, "api_base": "https://api.openai.com/v1"}},
        "mem_reader": {
            "backend": "simple_struct",
            "config": {
                "llm": {"backend": "openai", "config": {"model_name_or_path": llm_model, "temperature": 0.0, "api_key": api_key, "api_base": "https://api.openai.com/v1"}},
                "embedder": {"backend": "universal_api", "config": {"model_name_or_path": embedded_model, "provider": "openai", "api_key": embedded_api_key, "base_url": "https://api.openai.com/v1"}},
                "chunker": {"backend": "sentence", "config": {"chunk_size": 512, "chunk_overlap": 128}},
            },
        },
        # UserManager設定（SQLiteのDB保存場所を指定）
        "user_manager": {
            "backend": "sqlite",
            "config": {
                "user_id": "root",
                "db_path": db_path
            }
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
    
    # 注意：下記のMemOS embedder設定は初期化時のみ使用され、
    # 実際の実行時はCocoroMOSProductでLiteLLMEmbedderに置き換えられます
    logger.info(f"MemOS標準embedder設定（初期化後に置き換え予定）: {embedded_model}")

    # Memory Scheduler設定を追加（常に有効）
    scheduler_config = {
        "top_k": cocoro_config.scheduler_top_k,
        "top_n": cocoro_config.scheduler_top_n,
        "act_mem_update_interval": cocoro_config.scheduler_act_mem_update_interval,
        "context_window_size": cocoro_config.scheduler_context_window_size,
        "thread_pool_max_workers": cocoro_config.scheduler_thread_pool_max_workers,
        "consume_interval_seconds": cocoro_config.scheduler_consume_interval_seconds,
        "enable_parallel_dispatch": cocoro_config.scheduler_enable_parallel_dispatch,
        "enable_act_memory_update": cocoro_config.enable_activation_memory,
    }
    
    # act_mem_dump_pathを追加（相対パス対応）
    if use_relative_paths:
        scheduler_config["act_mem_dump_path"] = scheduler_dump_path
    else:
        scheduler_config["act_mem_dump_path"] = scheduler_dump_path
    
    memos_config["mem_scheduler"] = {
        "backend": "general_scheduler",
        "config": scheduler_config,
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
        base_dir.parent / "UserDataM" / "Setting.json",  # CocoroCoreM/../UserDataM/
        base_dir.parent.parent / "UserDataM" / "Setting.json",  # CocoroAI/UserDataM/
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


def get_mos_config(config: "CocoroAIConfig" = None, use_relative_paths: bool = True):
    """MOSConfigオブジェクトを取得する

    Args:
        config: CocoroAI設定オブジェクト（必須）
        use_relative_paths: 相対パスを使用するかどうか（デフォルト: True）

    Returns:
        MOSConfig: MOSConfigオブジェクト

    Raises:
        ConfigurationError: MOSConfig作成に失敗した場合
    """
    if config is None:
        # configが指定されていない場合は現在の設定を読み込む
        config = CocoroAIConfig.load()

    memos_config_data = generate_memos_config_from_setting(config, use_relative_paths=use_relative_paths)
    return create_mos_config_from_dict(memos_config_data)