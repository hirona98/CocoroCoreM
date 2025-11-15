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
    
    def __init__(self, model_name: str, api_key: str, base_url: str | None = None,
                 extra_config: Dict[str, Any] = None, **kwargs):
        self.model_name_or_path = model_name
        self.api_key = api_key
        # OpenAI互換エンドポイント用の明示的なbase_url
        self.base_url = base_url
        
        self.max_tokens = kwargs.get('max_tokens', 8192)
        
        self.remove_think_prefix = kwargs.get('remove_think_prefix', False)
        self.extra_config = extra_config or {}
        
        
        # プロバイダー名を自動抽出（例: "xai/grok-2-latest" → "xai"）
        self.provider = model_name.split('/')[0] if '/' in model_name else 'openai'
        
        # 推論モデル用thinking制御設定を追加
        self._configure_reasoning_control()
        
    def _configure_reasoning_control(self):
        """推論モデル用のthinking制御設定"""
        # ユーザーがreasoning_effortを指定している場合は優先して適用
        user_reasoning = (self.extra_config.get('reasoning_effort') or "").strip()
        if user_reasoning:
            self.extra_config['reasoning_effort'] = user_reasoning
            logger.info(f"ユーザー指定reasoning_effortを適用: {user_reasoning}")
            return

        # Note: {'reasoning_effort': ''} のような無効な値は
        # _prepare_completion_params で動的に処理され、drop_paramsが有効化される
        reasoning_models = {
            'gemini-2.5-flash': {'reasoning_effort': 'disable'},
            'gemini-2.5-flash-lite': {'reasoning_effort': 'disable'},
            'gemini-2.5-pro': {'reasoning_effort': ''},

            'deepseek-r1': {'reasoning_effort': ''},
            'deepseek-reasoner': {'reasoning_effort': ''},

            'o1-mini': {'reasoning_effort': 'low'},
            'o3-mini': {'reasoning_effort': 'low'},

            'gpt-5.1': {'reasoning_effort': 'none'},
            'gpt-5': {'reasoning_effort': 'minimal'},
            'gpt-5-mini': {'reasoning_effort': 'minimal'},
            'gpt-5-nano': {'reasoning_effort': 'minimal'},

            'grok-3-mini': {'reasoning_effort': 'low'},
            'grok-3-mini-fast': {'reasoning_effort': 'low'},
            'grok-4': {'reasoning_effort': ''},
            'grok-4-fast-non-reasoning': {'reasoning_effort': ''},
        }
        
        # モデル名から推論制御設定を検出・適用
        for reasoning_model, thinking_config in reasoning_models.items():
            if reasoning_model in self.model_name_or_path:
                # extra_configにthinking制御設定をマージ
                self.extra_config.update(thinking_config)
                logger.info(f"推論制御適用: {self.model_name_or_path} → {thinking_config}")
                break


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
            
            # LiteLLMのログレベルを設定
            logging.getLogger("LiteLLM").setLevel(logging.INFO)
            logging.getLogger("litellm").setLevel(logging.INFO)
            
            # LiteLLMのログを切り詰めるためのカスタムハンドラー設定
            litellm_logger = logging.getLogger("LiteLLM")
            
            # 既存のハンドラーを取得して切り詰め機能を追加
            class TruncateLogHandler(logging.Handler):
                def __init__(self, original_handlers):
                    super().__init__()
                    self.original_handlers = original_handlers
                    
                def emit(self, record):
                    if hasattr(record, 'msg') and isinstance(record.msg, str):
                        if len(record.msg) > 300:
                            record.msg = record.msg[:300] + "...[切り詰め]"
                    
                    # 元のハンドラーに転送
                    for handler in self.original_handlers:
                        if handler.level <= record.levelno:
                            handler.emit(record)
            
            # カスタムハンドラーを適用
            original_handlers = litellm_logger.handlers.copy()
            if original_handlers:
                litellm_logger.handlers.clear()
                truncate_handler = TruncateLogHandler(original_handlers)
                litellm_logger.addHandler(truncate_handler)
        except ImportError:
            raise RuntimeError("LiteLLMがインストールされていません。pip install litellm でインストールしてください。")
        
        # base_url が指定されている場合は OpenAI互換運用として明示
        base_url_effective = getattr(self.config, 'base_url', None) or self.config.extra_config.get('base_url')
        if base_url_effective:
            logger.info(f"OpenAI互換運用: base_url={base_url_effective}")

        logger.info(f"LiteLLMWrapper初期化完了: model={self.config.model_name_or_path}")
    
    def _setup_environment_variables(self):
        """プロバイダー別環境変数設定"""
        provider = self.config.provider
        api_key = self.config.api_key or ""
        extra = self.config.extra_config or {}
        base_url = getattr(self.config, 'base_url', None) or extra.get('base_url')

        # プロバイダー別APIキー環境変数のマッピング
        provider_key_env = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "xai": "XAI_API_KEY",
            "gemini": "GEMINI_API_KEY",
        }

        # 共通: APIキーの設定（存在する場合のみ）
        if provider in provider_key_env and api_key:
            env_name = provider_key_env[provider]
            os.environ[env_name] = api_key
            logger.info(f"   → {env_name} に設定")

        # Vertex AI は追加の環境変数を使用
        if provider == "vertex_ai":
            if "project_id" in extra:
                os.environ["VERTEXAI_PROJECT"] = extra["project_id"]
            if "location" in extra:
                os.environ["VERTEXAI_LOCATION"] = extra["location"]
            logger.info(f"   → VERTEX_AI 環境変数に設定")

        # LM Studio は per-call の base_url/api_base 指定で対応。環境変数は汚染しない。
        if provider == "lm_studio":
            effective_base_url = base_url or "http://localhost:1234/v1"
            logger.info(f"   → LM_STUDIO: 環境変数は変更せず per-call 指定 (base_url={effective_base_url})")
    
    def _prepare_completion_params(self, **kwargs) -> Dict[str, Any]:
        """
        completion関数用のパラメータを準備し、無効なreasoning_effortを処理
        
        Args:
            **kwargs: 動的パラメータ
            
        Returns:
            Dict[str, Any]: 処理済みのパラメータ辞書
        """
        # extra_configとkwargsをマージしてチェック
        params = {**self.config.extra_config, **kwargs}
        
        # reasoning_effortが空文字列の場合は削除してdrop_paramsを有効化
        if params.get('reasoning_effort') == '':
            params.pop('reasoning_effort', None)
            params['drop_params'] = True
            logger.debug("空のreasoning_effortを検出 → パラメータ削除とdrop_params有効化")
        
        # OpenAI互換系の安定動作用に、per-call でも base_url / api_base を注入（環境変数依存回避）
        resolved_base_url = getattr(self.config, 'base_url', None) or self.config.extra_config.get('base_url')
        # LM Studio では base_url が必須。未指定ならデフォルトを補完。
        if not resolved_base_url and self.config.provider == "lm_studio":
            resolved_base_url = "http://localhost:1234/v1"
        if resolved_base_url:
            # LiteLLM の版差に備えて両方渡す
            params.setdefault('base_url', resolved_base_url)
            params.setdefault('api_base', resolved_base_url)

        # LM Studio は OpenAI 互換 API を使うが、Authorization ヘッダーは空だと httpcore エラーになる。
        # 環境変数は汚染しない方針なので、per-call で非空の api_key を必ず渡す。
        if self.config.provider == "lm_studio":
            effective_key = self.config.api_key if self.config.api_key else None
            if not effective_key:
                # LM Studio は任意のトークンで通るため、ダミー値を使用
                params.setdefault('api_key', 'lm-studio')
            else:
                params.setdefault('api_key', effective_key)
        return params
    
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
            # パラメータを準備（空のreasoning_effortをチェック・処理）
            params = self._prepare_completion_params(**kwargs)
            
            # LiteLLM completion呼び出し
            response = self.litellm.completion(
                model=self.config.model_name_or_path,
                messages=messages,
                max_tokens=self.config.max_tokens,
                **params
            )
            
            response_content = response.choices[0].message.content
            
            # contentがNoneまたは空の場合のエラーハンドリング
            if response_content is None:
                finish_reason = getattr(response.choices[0], 'finish_reason', 'unknown')
                error_msg = f"LLMレスポンスがNoneです。finish_reason: {finish_reason}"
                logger.error(error_msg)
                if finish_reason == 'length' or finish_reason == 'max_tokens':
                    error_msg += f" (max_tokens={self.config.max_tokens}を増やす必要があります)"
                raise ValueError(error_msg)
            
            if response_content == "":
                logger.warning("LLMが空文字列を返しました")
                response_content = "{}"  # MemOS用の最小限有効JSON
            
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
            # パラメータを準備（空のreasoning_effortをチェック・処理）
            params = self._prepare_completion_params(**kwargs)
            
            # LiteLLM completion（ストリーミング）呼び出し
            response = self.litellm.completion(
                model=self.config.model_name_or_path,
                messages=messages,
                stream=True,  # ストリーミング有効
                max_tokens=self.config.max_tokens,
                **params
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
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        テキストの埋め込みベクトル生成（エラー時は例外を再発生）
        
        Args:
            texts: 埋め込み対象のテキストリスト
            
        Returns:
            List[List[float]]: 埋め込みベクトルのリスト
        """
        try:
            # パラメータ準備（per-call で base_url / api_base / api_key を注入）
            params: Dict[str, Any] = {**self.config.extra_config}
            resolved_base_url = getattr(self.config, 'base_url', None) or self.config.extra_config.get('base_url')
            if not resolved_base_url and self.config.provider == "lm_studio":
                # LM Studio かつ未設定の場合はデフォルトで補完
                resolved_base_url = "http://localhost:1234/v1"
            if resolved_base_url:
                params.setdefault('base_url', resolved_base_url)
                params.setdefault('api_base', resolved_base_url)

            if self.config.provider == "lm_studio":
                effective_key = self.config.api_key if self.config.api_key else None
                params.setdefault('api_key', effective_key or 'lm-studio')

            # LiteLLM embedding呼び出し
            response = self.litellm.embedding(
                model=self.config.model_name_or_path,
                input=texts,
                **params  # プロバイダー固有設定 + per-call 注入
            )
            
            # 埋め込みベクトルを抽出（LiteLLMのレスポンス形式に対応）
            embeddings = []
            for data in response.data:
                if hasattr(data, 'embedding'):
                    # オブジェクト形式の場合
                    embeddings.append(data.embedding)
                elif isinstance(data, dict) and 'embedding' in data:
                    # 辞書形式の場合
                    embeddings.append(data['embedding'])
                else:
                    data_str = str(data)
                    if len(data_str) > 200:
                        data_str = data_str[:200] + "..."
                    logger.error(f"予期しないレスポンス形式: {type(data)} - {data_str}")
                    raise ValueError(f"Embedding レスポンスの形式が正しくありません: {type(data)}")
            
            # ログ出力（デバッグ用）
            logger.debug(f"LiteLLM Embedding: model={response.model}, tokens={response.usage.total_tokens if hasattr(response, 'usage') else 'N/A'}")
            
            return embeddings
                
        except Exception as e:
            # 詳細なエラー情報を出力
            self._log_detailed_error(e, "embed", [{"role": "user", "content": str(texts)}], {})
            # エラーを再発生（フォールバックしない）
            raise
