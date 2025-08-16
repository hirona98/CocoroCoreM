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


class LoggingConfig(BaseModel):
    """ログ設定"""

    level: str = "INFO"
    file: str = "logs/cocoro_core2.log"
    max_size_mb: int = 10
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


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
            "enable_act_memory_update": cocoro_config.enable_activation_memory,
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

    userdata_dir = base_dir.parent / "UserData2"

    # Setting.jsonから設定を読み込み
    try:
        setting_path = userdata_dir / "Setting.json"
        if not setting_path.exists():
            raise ConfigurationError(f"Setting.jsonが見つかりません: {setting_path}")

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

    Args:
        mos_config_dict: MemOS設定辞書

    Returns:
        MOSConfig: MOSConfigオブジェクト

    Raises:
        ConfigurationError: MOSConfig作成に失敗した場合
    """
    try:
        # 遅延インポートでMemOSの循環依存を回避
        from memos.configs.mem_os import MOSConfig

        # 辞書からMOSConfigオブジェクトを作成
        return MOSConfig(**mos_config_dict)

    except ImportError as e:
        raise ConfigurationError(f"MemOSライブラリが利用できません: {e}")
    except Exception as e:
        raise ConfigurationError(f"MOSConfig作成に失敗しました: {e}")

