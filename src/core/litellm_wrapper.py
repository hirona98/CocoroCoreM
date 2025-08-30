"""
LiteLLM統合用ラッパークラス

MemOSのBaseLLMインターフェースに準拠し、
LiteLLMを使用してマルチプロバイダーLLM対応を実現
"""

import logging
import os
from collections.abc import Generator
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class LiteLLMConfig:
    """LiteLLM設定クラス"""
    
    def __init__(self, model_name: str, api_key: str, 
                 extra_config: Dict[str, Any] = None, **kwargs):
        self.model_name_or_path = model_name
        self.api_key = api_key
        self.max_tokens = kwargs.get('max_tokens', 1024)
        self.remove_think_prefix = kwargs.get('remove_think_prefix', False)
        self.extra_config = extra_config or {}
        
        # プロバイダー名を自動抽出（例: "xai/grok-2-latest" → "xai"）
        self.provider = model_name.split('/')[0] if '/' in model_name else 'openai'


class LiteLLMWrapper:
    """
    LiteLLMラッパークラス
    
    MemOSのBaseLLMインターフェースを実装し、
    LiteLLMを使用してマルチプロバイダーLLM機能を提供
    """
    
    def __init__(self, config: LiteLLMConfig):
        """
        初期化
        
        Args:
            config: LiteLLM設定
        """
        self.config = config
        self.logger = logger
        
        # 環境変数設定（プロバイダー別）
        self._setup_environment_variables()
        
        # LiteLLMインポート（遅延インポート）
        try:
            import litellm
            self.litellm = litellm
            # ログレベル設定（LiteLLMの詳細ログを抑制）
            litellm.set_verbose = False
        except ImportError:
            raise RuntimeError("LiteLLMがインストールされていません。pip install litellm でインストールしてください。")
        
        logger.info(f"LiteLLMWrapper初期化完了: model={self.config.model_name_or_path}")
    
    def _setup_environment_variables(self):
        """プロバイダー別環境変数設定"""
        if self.config.api_key:
            if self.config.provider == "openai":
                os.environ["OPENAI_API_KEY"] = self.config.api_key
            elif self.config.provider == "anthropic":
                os.environ["ANTHROPIC_API_KEY"] = self.config.api_key
            elif self.config.provider == "xai":
                os.environ["XAI_API_KEY"] = self.config.api_key
            elif self.config.provider == "vertex_ai":
                # Vertex AIの場合は追加設定が必要
                if "project_id" in self.config.extra_config:
                    os.environ["VERTEXAI_PROJECT"] = self.config.extra_config["project_id"]
                if "location" in self.config.extra_config:
                    os.environ["VERTEXAI_LOCATION"] = self.config.extra_config["location"]
            # 他のプロバイダーも同様に追加可能
    
    def generate(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        LLMレスポンス生成（エラー時は例外を再発生）
        
        Args:
            messages: メッセージリスト
            **kwargs: 追加パラメータ
            
        Returns:
            str: 生成されたレスポンス
        """
        try:
            # LiteLLM completion呼び出し
            response = self.litellm.completion(
                model=self.config.model_name_or_path,
                messages=messages,
                max_tokens=self.config.max_tokens,
                **self.config.extra_config,  # プロバイダー固有設定
                **kwargs  # 動的パラメータ
            )
            
            response_content = response.choices[0].message.content
            
            # ログ出力（デバッグ用）
            logger.debug(f"LiteLLM Response: model={response.model}, usage={response.usage}")
            
            return response_content
                
        except Exception as e:
            # 詳細なエラー情報を出力
            self._log_detailed_error(e, "generate", messages, kwargs)
            # エラーを再発生（フォールバックしない）
            raise
    
    def generate_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[str, None, None]:
        """
        ストリーミングレスポンス生成（エラー時は例外を再発生）
        
        Args:
            messages: メッセージリスト
            **kwargs: 追加パラメータ
            
        Yields:
            str: ストリーミングチャンク
        """
        try:
            # LiteLLM completion（ストリーミング）呼び出し
            response = self.litellm.completion(
                model=self.config.model_name_or_path,
                messages=messages,
                stream=True,  # ストリーミング有効
                max_tokens=self.config.max_tokens,
                **self.config.extra_config,  # プロバイダー固有設定
                **kwargs  # 動的パラメータ
            )
            
            reasoning_started = False
            
            # ストリーミングレスポンス処理
            for chunk in response:
                if not chunk.choices or not chunk.choices[0].delta:
                    continue
                    
                delta = chunk.choices[0].delta
                
                # reasoning_content対応（DeepSeek等）
                if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                    if not reasoning_started and not self.config.remove_think_prefix:
                        yield "<think>"
                        reasoning_started = True
                    if not self.config.remove_think_prefix:
                        yield delta.reasoning_content
                
                # 通常のcontent
                elif hasattr(delta, "content") and delta.content:
                    if reasoning_started and not self.config.remove_think_prefix:
                        yield "</think>"
                        reasoning_started = False
                    yield delta.content
            
            # thinking タグ終了処理
            if reasoning_started and not self.config.remove_think_prefix:
                yield "</think>"
                
        except Exception as e:
            # 詳細なエラー情報を出力
            self._log_detailed_error(e, "generate_stream", messages, kwargs)
            # エラーを再発生（フォールバックしない）
            raise
    
    def _log_detailed_error(self, error: Exception, operation: str, 
                           messages: List[Dict[str, str]], kwargs: Dict[str, Any]):
        """詳細なエラー情報をログ出力"""
        error_info = {
            "operation": operation,
            "provider": self.config.provider,
            "model": self.config.model_name_or_path,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "message_count": len(messages),
            "kwargs": {k: v for k, v in kwargs.items() if k not in ['api_key']},  # APIキーを除外
        }
        
        # エラー分類と詳細ログ
        error_str = str(error)
        if "401" in error_str or "Authentication" in error_str:
            logger.error(f"🔐 認証エラー - APIキーを確認してください: {error_info}")
        elif "429" in error_str or "rate limit" in error_str.lower():
            logger.error(f"⏱️ レート制限エラー - 使用量を確認してください: {error_info}")
        elif "timeout" in error_str.lower() or "TimeoutError" in error_str:
            logger.error(f"⏰ タイムアウトエラー - ネットワーク状況を確認してください: {error_info}")
        elif any(code in error_str for code in ["502", "503", "504"]):
            logger.error(f"🖥️ サーバーエラー - プロバイダー側の一時的な問題の可能性: {error_info}")
        elif "quota" in error_str.lower() or "limit" in error_str.lower():
            logger.error(f"💳 クォータ・制限エラー - 使用制限を確認してください: {error_info}")
        else:
            logger.error(f"❓ 予期しないエラー: {error_info}", exc_info=True)