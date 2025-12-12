"""
LiteLLM埋め込みラッパー

MemOSのBaseEmbedderインターフェースに準拠し、
LiteLLMを使用してマルチプロバイダー埋め込み機能を提供
"""

import logging
from typing import List, Dict, Any
from memos.embedders.base import BaseEmbedder

import sys
import os

try:
    from .litellm_wrapper import LiteLLMWrapper, LiteLLMConfig
except ImportError:
    try:
        # PyInstaller対応：絶対インポート
        from core.litellm_wrapper import LiteLLMWrapper, LiteLLMConfig
    except ImportError:
        # 最後の手段：パスを動的に追加
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        from litellm_wrapper import LiteLLMWrapper, LiteLLMConfig

logger = logging.getLogger(__name__)


class LiteLLMEmbedder(BaseEmbedder):
    """
    LiteLLM埋め込みラッパークラス
    
    MemOSのBaseEmbedderインターフェースを実装し、
    LiteLLMを使用してマルチプロバイダー埋め込み機能を提供
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初期化
        
        Args:
            config: LiteLLM埋め込み設定
                - model_name_or_path: モデル名
                - api_key: APIキー
                - provider: プロバイダー名（オプション、モデル名から自動推定）
                - extra_config: 追加設定（オプション）
        """
        # OpenRouter対応: openrouter/ プレフィックスは保持し、base_urlを自動設定
        model_name = config["model_name_or_path"]
        base_url = config.get("base_url")
        
        if model_name.startswith("openrouter/"):
            if not base_url:
                base_url = "https://openrouter.ai/api/v1"
                
        # LiteLLMConfig作成
        litellm_config = LiteLLMConfig(
            model_name=model_name,
            api_key=config["api_key"],
            base_url=base_url,
            extra_config=config.get("extra_config", {})
        )
        
        # LiteLLMWrapper初期化
        self.wrapper = LiteLLMWrapper(litellm_config)
        
        logger.info(f"LiteLLMEmbedder初期化完了: model={config['model_name_or_path']}, provider={litellm_config.provider}")
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        テキストの埋め込みベクトル生成
        
        Args:
            texts: 埋め込み対象のテキストリスト
            
        Returns:
            List[List[float]]: 埋め込みベクトルのリスト
        """
        return self.wrapper.embed(texts)
