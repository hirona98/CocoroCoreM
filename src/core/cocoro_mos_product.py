"""
CocoroAI専用MOSProduct実装

MemOSのMOSProductクラスを継承し、CocoroAIのシステムプロンプトを使用するようカスタマイズ
動的プロンプト置換により、外部ライブラリを変更せずに全MemOS機能を日本語化
"""

import logging
from typing import Optional, Callable, List, Dict, Any

from memos.mem_os.product import MOSProduct
from memos.memories.textual.item import TextualMemoryItem

from .cocoro_prompts import (
    COCORO_MEMORY_INSTRUCTION,
    # Tree Reorganize Prompts
    REORGANIZE_PROMPT_JP,
    DOC_REORGANIZE_PROMPT_JP,
    LOCAL_SUBCLUSTER_PROMPT_JP,
    PAIRWISE_RELATION_PROMPT_JP,
    INFER_FACT_PROMPT_JP,
    AGGREGATE_PROMPT_JP,
    REDUNDANCY_MERGE_PROMPT_JP,
    MEMORY_RELATION_DETECTOR_PROMPT_JP,
    MEMORY_RELATION_RESOLVER_PROMPT_JP,
    # Memory Scheduler Prompts
    INTENT_RECOGNIZING_PROMPT_JP,
    MEMORY_RERANKING_PROMPT_JP,
    QUERY_KEYWORDS_EXTRACTION_PROMPT_JP,
    # Memory Reader Prompts
    SIMPLE_STRUCT_MEM_READER_PROMPT_JP,
    SIMPLE_STRUCT_DOC_READER_PROMPT_JP,
    SIMPLE_STRUCT_MEM_READER_EXAMPLE_JP,
    # MOS Core Prompts
    COT_DECOMPOSE_PROMPT_JP,
    SYNTHESIS_PROMPT_JP,
    QUERY_REWRITING_PROMPT_JP
)

logger = logging.getLogger(__name__)


class CocoroMOSProduct(MOSProduct):
    """
    CocoroAI専用MOSProduct
    
    MemOSのMOSProductを継承し、動的プロンプト置換により
    全MemOS機能を日本語化してCocoroAIシステムと統合
    """
    
    def __init__(self, default_config=None, max_user_instances=1, 
                 system_prompt_provider: Optional[Callable[[], Optional[str]]] = None,
                 # LiteLLM統合パラメータ
                 litellm_config: Optional[Dict[str, Any]] = None,
                 reminder_enabled: bool = True):
        """
        初期化
        
        Args:
            default_config: MemOSデフォルト設定
            max_user_instances: 最大ユーザーインスタンス数
            system_prompt_provider: CocoroAIシステムプロンプト取得関数
            litellm_config: LiteLLM設定辞書
        """
        # MemOS全体のプロンプトを日本語版に置換
        self._replace_memos_prompts_with_japanese()
        
        # 通常のMOSProduct初期化（MemOS標準のchat_llmが作成される）
        super().__init__(default_config=default_config, max_user_instances=max_user_instances)
        
        self.system_prompt_provider = system_prompt_provider
        self._original_chat_llm = None  # フォールバック用（将来の拡張のため保持）
        
        # LiteLLM統合（方法1: chat_llmの直接置き換え）
        if litellm_config:
            self._setup_litellm(litellm_config)
            # EmbeddingもLiteLLMで統一
            self._setup_litellm_embedder(litellm_config)
            # Mem ReaderとMem SchedulerもLiteLLMで統一
            self._setup_litellm_mem_reader(litellm_config)
            self._setup_litellm_mem_scheduler(litellm_config)
            # TreeTextMemoryのdispatcher_llmもLiteLLMで統一（TaskGoalParser用）
            self._setup_litellm_tree_text_memory(litellm_config)
        
        self.reminder_enabled = reminder_enabled
        logger.info(f"CocoroMOSProduct初期化完了: LiteLLM={'有効' if litellm_config else '無効'}, リマインダー指示={'有効' if self.reminder_enabled else '無効'}")
    
    def _replace_memos_prompts_with_japanese(self):
        """
        MemOSの全プロンプトテンプレートを日本語版に動的置換
        
        外部ライブラリを変更せずに、実行時にMemOS内部で使用される
        全てのプロンプトを日本語版に置き換えることで完全日本語化を実現
        """
        try:
            # Tree Reorganize Prompts（記憶再編成機能）
            import memos.templates.tree_reorganize_prompts as tree_prompts
            tree_prompts.REORGANIZE_PROMPT = REORGANIZE_PROMPT_JP
            tree_prompts.DOC_REORGANIZE_PROMPT = DOC_REORGANIZE_PROMPT_JP
            tree_prompts.LOCAL_SUBCLUSTER_PROMPT = LOCAL_SUBCLUSTER_PROMPT_JP
            tree_prompts.PAIRWISE_RELATION_PROMPT = PAIRWISE_RELATION_PROMPT_JP
            tree_prompts.INFER_FACT_PROMPT = INFER_FACT_PROMPT_JP
            tree_prompts.AGGREGATE_PROMPT = AGGREGATE_PROMPT_JP
            tree_prompts.REDUNDANCY_MERGE_PROMPT = REDUNDANCY_MERGE_PROMPT_JP
            tree_prompts.MEMORY_RELATION_DETECTOR_PROMPT = MEMORY_RELATION_DETECTOR_PROMPT_JP
            tree_prompts.MEMORY_RELATION_RESOLVER_PROMPT = MEMORY_RELATION_RESOLVER_PROMPT_JP
            
            # Memory Scheduler Prompts（記憶スケジューラー機能）
            import memos.templates.mem_scheduler_prompts as scheduler_prompts
            scheduler_prompts.INTENT_RECOGNIZING_PROMPT = INTENT_RECOGNIZING_PROMPT_JP
            scheduler_prompts.MEMORY_RERANKING_PROMPT = MEMORY_RERANKING_PROMPT_JP
            scheduler_prompts.QUERY_KEYWORDS_EXTRACTION_PROMPT = QUERY_KEYWORDS_EXTRACTION_PROMPT_JP
            
            # Memory Reader Prompts（記憶抽出機能）
            import memos.templates.mem_reader_prompts as reader_prompts
            reader_prompts.SIMPLE_STRUCT_MEM_READER_PROMPT = SIMPLE_STRUCT_MEM_READER_PROMPT_JP
            reader_prompts.SIMPLE_STRUCT_DOC_READER_PROMPT = SIMPLE_STRUCT_DOC_READER_PROMPT_JP
            reader_prompts.SIMPLE_STRUCT_MEM_READER_EXAMPLE = SIMPLE_STRUCT_MEM_READER_EXAMPLE_JP
            
            # MOS Core Prompts（コア機能）
            import memos.templates.mos_prompts as mos_prompts
            mos_prompts.COT_DECOMPOSE_PROMPT = COT_DECOMPOSE_PROMPT_JP
            mos_prompts.SYNTHESIS_PROMPT = SYNTHESIS_PROMPT_JP
            mos_prompts.QUERY_REWRITING_PROMPT = QUERY_REWRITING_PROMPT_JP
            
            # Scheduler用プロンプトマッピングも更新
            if hasattr(scheduler_prompts, 'PROMPT_MAPPING'):
                scheduler_prompts.PROMPT_MAPPING.update({
                    "intent_recognizing": INTENT_RECOGNIZING_PROMPT_JP,
                    "memory_reranking": MEMORY_RERANKING_PROMPT_JP,
                    "query_keywords_extraction": QUERY_KEYWORDS_EXTRACTION_PROMPT_JP,
                })
            
        except ImportError as e:
            logger.warning(f"MemOSモジュールのインポートに失敗: {e}")
        except Exception as e:
            logger.error(f"プロンプト置換中にエラーが発生: {e}", exc_info=True)
    
    def _ensure_api_key(self, config: Dict[str, Any], key_name: str = 'api_key', component_name: str = '') -> None:
        """APIキーが空の場合はダミー値を設定する共通処理（ローカルLLM用）"""
        if key_name not in config or not config[key_name]:
            config[key_name] = 'dummy-api-key'
            model_name = config.get('model' if key_name == 'api_key' else 'embedding_model', 'unknown')
            logger.info(f"{component_name}APIキーが空のため、ダミー値を設定（ローカルLLM用）: model={model_name}")
    
    def _setup_litellm(self, config: Dict[str, Any]):
        """LiteLLMセットアップ（エラー時は例外を再発生）"""
        try:
            # 元のchat_llmをバックアップ（将来の拡張のため）
            self._original_chat_llm = self.chat_llm
            
            # LiteLLMWrapper import
            from .litellm_wrapper import LiteLLMConfig, LiteLLMWrapper
            
            # LiteLLMConfig作成（設定必須）
            if 'model' not in config or not config['model']:
                raise ValueError("❌ LiteLLM設定にmodelが設定されていません")
            self._ensure_api_key(config, 'api_key', '')
                
            # base_url を extra_config にも反映しておく（拾い漏れ防止）
            extra_cfg = config.get('extra_config', {}) or {}
            if 'base_url' in config and config['base_url']:
                extra_cfg.setdefault('base_url', config['base_url'])

            litellm_config = LiteLLMConfig(
                model_name=config['model'],
                api_key=config['api_key'],
                base_url=config.get('base_url'),
                max_tokens=config.get('max_tokens', 8192),
                extra_config=extra_cfg
            )
            
            # chat_llmをLiteLLMWrapperに置き換え
            self.chat_llm = LiteLLMWrapper(litellm_config)

            logger.info(f"✅ LiteLLM統合完了: {litellm_config.model_name_or_path}")
            logger.info(f"🔧 max_tokens設定: {config.get('max_tokens', 8192)}")
            
        except Exception as e:
            # 詳細エラー出力
            logger.error(f"❌ LiteLLMセットアップ失敗:")
            logger.error(f"   モデル: {config.get('model', 'N/A')}")
            logger.error(f"   エラー: {str(e)}")
            logger.error(f"   設定内容: {config}")
            
            # エラーを再発生（フォールバックしない）
            raise RuntimeError(f"LiteLLMセットアップエラー: {str(e)}")
    
    def _setup_litellm_embedder(self, config: Dict[str, Any]):
        """LiteLLM Embedder セットアップ（すべてのMemCubeのembedderを置き換え）"""
        try:
            from .litellm_embedder import LiteLLMEmbedder
            from .litellm_wrapper import LiteLLMConfig
            
            # Embedding用LiteLLMConfig作成（埋め込みモデル用、設定必須）
            if 'embedding_model' not in config or not config['embedding_model']:
                raise ValueError("❌ LiteLLM設定にembedding_modelが設定されていません")
            self._ensure_api_key(config, 'embedding_api_key', '埋め込み')
                
            # 埋め込み専用ベースURL設定（LLM設定とは独立）
            base_url = config.get('embedding_base_url')

            # LM Studio の場合は未指定でもデフォルトを補完
            if not base_url:
                try:
                    provider_prefix = str(config.get('embedding_model', '')).split('/')[0].lower()
                except Exception:
                    provider_prefix = 'openai'
                if provider_prefix in ['lm_studio', 'lmstudio']:
                    base_url = 'http://localhost:1234/v1'
                    logger.info(f"🔧 LM Studio用ベースURL自動設定: {base_url}")
                elif provider_prefix == 'openai' and not base_url:
                    # OpenAIの場合は明示的にデフォルトURLを設定しない（LiteLLMがハンドリング）
                    logger.info(f"🔧 OpenAI埋め込み: デフォルトエンドポイントを使用")

            embedder_config = {
                "model_name_or_path": config['embedding_model'],
                "api_key": config['embedding_api_key'],
                "extra_config": ({"base_url": base_url} if base_url else {})
            }

            # ベースURL設定状況をログ出力
            logger.info(f"🔧 Embedder ベースURL設定: {base_url or 'デフォルト'} (モデル: {config['embedding_model']})")
            
            # LiteLLMEmbedder作成して保存（MemCube作成後に使用するため）
            self._litellm_embedder = LiteLLMEmbedder(embedder_config)
            self._litellm_embedder_config = embedder_config
            
            # 既存のMemCubeのembedderを置き換え
            replaced_count = 0
            for cube_id, mem_cube in self.mem_cubes.items():
                if hasattr(mem_cube, 'text_mem') and mem_cube.text_mem is not None:
                    # TreeTextMemoryのembedderを置き換え
                    original_embedder = mem_cube.text_mem.embedder
                    mem_cube.text_mem.embedder = self._litellm_embedder
                    
                    # MemoryManagerのembedderも置き換え（一貫性のため）
                    if hasattr(mem_cube.text_mem, 'memory_manager'):
                        mem_cube.text_mem.memory_manager.embedder = self._litellm_embedder
                    
                    replaced_count += 1
                    logger.debug(f"MemCube {cube_id} のembedderをLiteLLMに置き換え")
            
            logger.info(f"🔄 LiteLLM Embedder統合完了: {replaced_count}個のMemCubeで置き換え完了")
            
            # インターネット検索リトリーバーをLiteLLMEmbedderに統一
            self._replace_internet_retriever_embedder()
            
        except Exception as e:
            logger.error(f"❌ LiteLLM Embedder統合失敗: {e}")
            # Embedder置き換え失敗は非致命的（LLMは動作する）
            logger.warning("Embedding機能に問題がありますが、LLM機能は正常に動作します")
    
    def _setup_litellm_mem_reader(self, config: Dict[str, Any]):
        """LiteLLM Mem Reader セットアップ（mem_reader.llmとembedderを置き換え）"""
        try:
            from .litellm_wrapper import LiteLLMConfig, LiteLLMWrapper
            from .litellm_embedder import LiteLLMEmbedder
            
            # Mem Reader用LiteLLMConfig作成（LLM用、設定必須）
            if 'model' not in config or not config['model']:
                raise ValueError("❌ LiteLLM設定にmodelが設定されていません")
            self._ensure_api_key(config, 'api_key', 'Mem Reader用')
                
            mem_reader_config = LiteLLMConfig(
                model_name=config['model'],
                api_key=config['api_key'],
                max_tokens=config.get('max_tokens', 8192),
                extra_config=config.get('extra_config', {})
            )
            
            # mem_reader.llmとembedderを置き換え
            if hasattr(self, 'mem_reader') and self.mem_reader is not None:
                replaced_count = 0
                
                # 1. LLMの置き換え
                if hasattr(self.mem_reader, 'llm'):
                    original_llm = self.mem_reader.llm
                    self.mem_reader.llm = LiteLLMWrapper(mem_reader_config)
                    replaced_count += 1
                    logger.debug("Mem Reader LLM をLiteLLMに置き換え")
                
                # 2. 重要：Embedderの置き換え（エラーの根本原因）
                if hasattr(self.mem_reader, 'embedder') and self.mem_reader.embedder is not None:
                    # LiteLLMEmbedderが準備されている場合は使用
                    if hasattr(self, '_litellm_embedder') and self._litellm_embedder is not None:
                        original_embedder = self.mem_reader.embedder
                        self.mem_reader.embedder = self._litellm_embedder
                        replaced_count += 1
                        logger.debug("Mem Reader Embedder をLiteLLMに置き換え")
                    else:
                        logger.warning("LiteLLMEmbedder が準備されていません")
                
                logger.info(f"🔄 Mem Reader LLM・Embedder をLiteLLMに置き換え完了: {replaced_count}個")
            else:
                logger.warning("mem_reader が見つかりません")
            
        except Exception as e:
            logger.error(f"❌ Mem Reader LiteLLM統合失敗: {e}")
            # mem_reader置き換え失敗は非致命的
            logger.warning("Mem Reader機能に問題がありますが、他の機能は正常に動作します")
    
    def _setup_litellm_mem_scheduler(self, config: Dict[str, Any]):
        """LiteLLM Mem Scheduler セットアップ（全階層の_process_llmを再帰的に置き換え）"""
        try:
            from .litellm_wrapper import LiteLLMConfig, LiteLLMWrapper
            
            # Mem Scheduler用LiteLLMConfig作成（LLM用、設定必須）
            if 'model' not in config or not config['model']:
                raise ValueError("❌ LiteLLM設定にmodelが設定されていません")
            self._ensure_api_key(config, 'api_key', 'Mem Scheduler用')
                
            mem_scheduler_config = LiteLLMConfig(
                model_name=config['model'],
                api_key=config['api_key'],
                max_tokens=config.get('max_tokens', 8192),
                extra_config=config.get('extra_config', {})
            )
            
            # LiteLLMWrapperインスタンスを作成
            litellm_wrapper = LiteLLMWrapper(mem_scheduler_config)

            # 追加: メモリスケジューラーはJSON配列のみを期待するため、
            # 余計なテキストが付与された場合でも先頭のJSON配列だけを返す薄いラッパーを適用
            class _JSONArrayFirstLineWrapper:
                """JSON配列のみを返すための薄いアダプタ（mem_scheduler専用）"""
                def __init__(self, base_llm):
                    self._base = base_llm

                def generate(self, messages, **kwargs):
                    text = self._base.generate(messages, **kwargs)
                    # 先頭の非空行がJSON配列ならそれだけ返す
                    for line in str(text).splitlines():
                        s = line.strip()
                        if s.startswith('['):
                            # 最頻ケース: 1行配列。終端 ']' がなくてもまずこの行を返す。
                            # memos 側はjson.loadsをかけるため、最小限の配列を優先。
                            return s
                    return text

                # その他の属性/メソッドは委譲（例えば generate_stream 等）
                def __getattr__(self, name):
                    return getattr(self._base, name)

            litellm_wrapper = _JSONArrayFirstLineWrapper(litellm_wrapper)
            
            # mem_scheduler内の全LLMインスタンスを再帰的に置き換え
            if hasattr(self, '_mem_scheduler') and self._mem_scheduler is not None:
                replaced_count = 0
                
                # 1. 直接_process_llm属性を持つ場合の対応
                if hasattr(self._mem_scheduler, '_process_llm'):
                    self._mem_scheduler._process_llm = litellm_wrapper
                    replaced_count += 1
                    logger.debug("Scheduler の_process_llmを直接置き換え")
                
                # 2. modules内のLLMを置き換え
                if hasattr(self._mem_scheduler, 'modules'):
                    for module_name, module in self._mem_scheduler.modules.items():
                        if hasattr(module, '_process_llm'):
                            module._process_llm = litellm_wrapper
                            replaced_count += 1
                            logger.debug(f"Scheduler module {module_name} の_process_llmを置き換え")
                
                # 3. 重要：monitor内のLLMを置き換え（エラーの根本原因）
                if hasattr(self._mem_scheduler, 'monitor') and self._mem_scheduler.monitor is not None:
                    if hasattr(self._mem_scheduler.monitor, '_process_llm'):
                        self._mem_scheduler.monitor._process_llm = litellm_wrapper
                        replaced_count += 1
                        logger.debug("Scheduler monitor の_process_llmを置き換え")
                
                # 4. 再帰的に全属性をチェック（念のため）
                replaced_count += self._replace_llm_recursive(self._mem_scheduler, litellm_wrapper, 'scheduler')
                
                logger.info(f"🔄 Mem Scheduler LLM をLiteLLMに置き換え完了: {replaced_count}個のLLMインスタンス")
            else:
                logger.warning("_mem_scheduler が見つかりません")
            
        except Exception as e:
            logger.error(f"❌ Mem Scheduler LiteLLM統合失敗: {e}")
            # mem_scheduler置き換え失敗は非致命的
            logger.warning("Mem Scheduler機能に問題がありますが、他の機能は正常に動作します")

    def _setup_litellm_tree_text_memory(self, config: Dict[str, Any]):
        """TreeTextMemoryのdispatcher_llm置き換え（TaskGoalParser用）"""
        try:
            from .litellm_wrapper import LiteLLMConfig, LiteLLMWrapper

            # TreeTextMemory用LiteLLMConfig作成（LLM用、設定必須）
            if 'model' not in config or not config['model']:
                raise ValueError("❌ LiteLLM設定にmodelが設定されていません")
            self._ensure_api_key(config, 'api_key', 'TreeTextMemory用')

            # TaskGoalParser用のLiteLLMWrapperを作成（JSON正規化ラッパー付き）
            tree_memory_config = LiteLLMConfig(
                model_name=config['model'],
                api_key=config['api_key'],
                base_url=config.get('base_url'),
                max_tokens=config.get('max_tokens', 8192),
                extra_config=config.get('extra_config', {})
            )

            # LiteLLMWrapperインスタンスを作成
            base_litellm_wrapper = LiteLLMWrapper(tree_memory_config)

            # TaskGoalParser専用：JSON正規化ラッパーを適用
            # MemOSのTaskGoalParserはeval()を使用するため、JSON形式をPython形式に変換
            class _TaskGoalParserJSONWrapper:
                """TaskGoalParser用JSON正規化ラッパー（eval()対応）"""
                def __init__(self, base_llm):
                    self._base = base_llm

                def generate(self, messages, **kwargs):
                    text = self._base.generate(messages, **kwargs)

                    # マークダウンコードブロックを除去
                    normalized_text = str(text).strip()

                    # ```json ... ``` 形式の除去
                    if normalized_text.startswith('```'):
                        lines = normalized_text.split('\n')
                        # 最初の行（```json）を除去
                        if lines[0].startswith('```'):
                            lines = lines[1:]
                        # 最後の行（```）を除去
                        if lines and lines[-1].strip() == '```':
                            lines = lines[:-1]
                        normalized_text = '\n'.join(lines).strip()

                    # JSON形式をPython eval()で解析可能な形式に正規化
                    # 小文字のJSON boolean/null値を大文字のPython値に変換
                    normalized_text = normalized_text.replace(': false', ': False')
                    normalized_text = normalized_text.replace(': true', ': True')
                    normalized_text = normalized_text.replace(': null', ': None')

                    # JSON配列内も対応
                    normalized_text = normalized_text.replace('[false', '[False')
                    normalized_text = normalized_text.replace('[true', '[True')
                    normalized_text = normalized_text.replace('[null', '[None')
                    normalized_text = normalized_text.replace(', false', ', False')
                    normalized_text = normalized_text.replace(', true', ', True')
                    normalized_text = normalized_text.replace(', null', ', None')

                    return normalized_text

                # その他の属性/メソッドは委譲
                def __getattr__(self, name):
                    return getattr(self._base, name)

            litellm_wrapper = _TaskGoalParserJSONWrapper(base_litellm_wrapper)

            # 全MemCube内のTreeTextMemoryのdispatcher_llmを置き換え
            if hasattr(self, 'mem_cubes') and self.mem_cubes is not None:
                replaced_count = 0

                for cube_id, mem_cube in self.mem_cubes.items():
                    if hasattr(mem_cube, 'text_mem') and mem_cube.text_mem is not None:
                        # TreeTextMemoryのdispatcher_llm属性をチェック
                        if hasattr(mem_cube.text_mem, 'dispatcher_llm') and mem_cube.text_mem.dispatcher_llm is not None:
                            # 元のdispatcher_llmの型をチェック（MemOS標準LLMかどうか）
                            original_dispatcher = mem_cube.text_mem.dispatcher_llm
                            dispatcher_type = type(original_dispatcher).__name__

                            # MemOS標準のLLMクラス（OpenAI, Ollama, Azure等）の場合のみ置き換え
                            if hasattr(original_dispatcher, 'generate') and hasattr(original_dispatcher, 'client'):
                                mem_cube.text_mem.dispatcher_llm = litellm_wrapper
                                replaced_count += 1
                                logger.debug(f"MemCube {cube_id} のTreeTextMemory.dispatcher_llmをLiteLLMに置き換え ({dispatcher_type} → LiteLLMWrapper)")
                            else:
                                logger.debug(f"MemCube {cube_id} のdispatcher_llmは既にカスタムLLM ({dispatcher_type})")
                        else:
                            logger.debug(f"MemCube {cube_id} のTreeTextMemoryにdispatcher_llmが見つかりません")

                logger.info(f"🔄 TreeTextMemory dispatcher_llm をLiteLLMに置き換え完了: {replaced_count}個のMemCube")
            else:
                logger.warning("mem_cubes が見つかりません")

        except Exception as e:
            logger.error(f"❌ TreeTextMemory LiteLLM統合失敗: {e}")
            # TreeTextMemory置き換え失敗は重要（TaskGoalParserのAPIキーエラーの根本原因）
            logger.error("TreeTextMemory機能の問題により、TaskGoalParserでAPIキーエラーが発生する可能性があります")
            # 但し、致命的エラーにはしない（他の機能は動作可能）

    def _replace_llm_recursive(self, obj, litellm_wrapper, parent_name: str, max_depth: int = 3) -> int:
        """オブジェクト内の_process_llmを再帰的に置き換え"""
        if max_depth <= 0:
            return 0
            
        replaced_count = 0
        try:
            # オブジェクトの全属性をチェック
            for attr_name in dir(obj):
                if attr_name.startswith('_') and attr_name != '_process_llm':
                    continue
                    
                try:
                    attr_value = getattr(obj, attr_name)
                    
                    # _process_llm属性を発見した場合は置き換え
                    if attr_name == '_process_llm' and attr_value is not None:
                        # OpenAIクライアント（memos.llms.openai）かどうかチェック
                        if hasattr(attr_value, 'generate') and hasattr(attr_value, 'client'):
                            setattr(obj, attr_name, litellm_wrapper)
                            replaced_count += 1
                            logger.debug(f"再帰的置き換え: {parent_name}.{attr_name}")
                    
                    # オブジェクト型の属性があれば再帰的にチェック
                    elif (hasattr(attr_value, '__dict__') and 
                          not isinstance(attr_value, (str, int, float, bool, list, dict, tuple)) and
                          not callable(attr_value)):
                        replaced_count += self._replace_llm_recursive(
                            attr_value, litellm_wrapper, 
                            f"{parent_name}.{attr_name}", max_depth - 1
                        )
                        
                except (AttributeError, TypeError):
                    continue
                    
        except Exception as e:
            logger.debug(f"再帰的LLM置き換え中の軽微なエラー: {e}")
            
        return replaced_count
    
    def register_mem_cube(self, *args, **kwargs):
        """MemCube登録をオーバーライドして、登録後にLiteLLMEmbedderとTreeTextMemory dispatcher_llmに置き換え"""
        # 親クラスの標準登録処理を実行
        result = super().register_mem_cube(*args, **kwargs)

        # LiteLLMEmbedderが準備されている場合は新しいMemCubeのembedderを置き換え
        if hasattr(self, '_litellm_embedder') and self._litellm_embedder is not None:
            self._replace_new_memcube_embedder()

        # LiteLLM統合が有効な場合は新しいMemCubeのTreeTextMemory dispatcher_llmも置き換え
        if hasattr(self, 'chat_llm') and hasattr(self.chat_llm, '__class__') and 'LiteLLMWrapper' in str(self.chat_llm.__class__):
            self._replace_new_memcube_tree_text_memory()

        if hasattr(self, '_litellm_embedder') and self._litellm_embedder is not None:
            self._replace_internet_retriever_embedder()

        return result
    
    def _replace_new_memcube_embedder(self):
        """新しく作成されたMemCubeのembedderをLiteLLMに置き換え"""
        try:
            replaced_count = 0
            for cube_id, mem_cube in self.mem_cubes.items():
                if hasattr(mem_cube, 'text_mem') and mem_cube.text_mem is not None:
                    # UniversalAPIEmbedderかどうかチェック（MemOSの標準embedder）
                    current_embedder = mem_cube.text_mem.embedder
                    embedder_type = type(current_embedder).__name__
                    
                    # UniversalAPIEmbedderの場合のみ置き換え
                    if embedder_type == 'UniversalAPIEmbedder':
                        # TreeTextMemoryのembedderを置き換え
                        mem_cube.text_mem.embedder = self._litellm_embedder
                        
                        # MemoryManagerのembedderも置き換え（一貫性のため）
                        if hasattr(mem_cube.text_mem, 'memory_manager'):
                            mem_cube.text_mem.memory_manager.embedder = self._litellm_embedder
                        
                        replaced_count += 1
                        logger.info(f"🔄 新規MemCube {cube_id} のembedderをLiteLLMに置き換え完了 ({embedder_type} → LiteLLMEmbedder)")
                    else:
                        logger.debug(f"MemCube {cube_id} のembedderは既にLiteLLM ({embedder_type})")
            
            if replaced_count > 0:
                logger.info(f"✅ 新規MemCube embedder置き換え完了: {replaced_count}個")
                
        except Exception as e:
            logger.error(f"❌ 新規MemCube embedder置き換え失敗: {e}")
            logger.warning("新しいMemCubeでEmbedding機能に問題がありますが、LLM機能は正常に動作します")

    def _replace_new_memcube_tree_text_memory(self):
        """新しく作成されたMemCubeのTreeTextMemory dispatcher_llmをLiteLLMに置き換え"""
        try:
            from .litellm_wrapper import LiteLLMWrapper

            # chat_llmがLiteLLMWrapperの場合のみ実行（設定が一致していることを確認）
            if not hasattr(self, 'chat_llm') or not isinstance(self.chat_llm, LiteLLMWrapper):
                logger.debug("chat_llmがLiteLLMWrapperではないため、TreeTextMemory置き換えをスキップ")
                return

            replaced_count = 0
            for cube_id, mem_cube in self.mem_cubes.items():
                if hasattr(mem_cube, 'text_mem') and mem_cube.text_mem is not None:
                    # TreeTextMemoryのdispatcher_llm属性をチェック
                    if hasattr(mem_cube.text_mem, 'dispatcher_llm') and mem_cube.text_mem.dispatcher_llm is not None:
                        # 現在のdispatcher_llmの型をチェック
                        current_dispatcher = mem_cube.text_mem.dispatcher_llm
                        dispatcher_type = type(current_dispatcher).__name__

                        # MemOS標準LLMの場合のみ置き換え（既にLiteLLMの場合はスキップ）
                        if (hasattr(current_dispatcher, 'generate') and
                            hasattr(current_dispatcher, 'client') and
                            'LiteLLMWrapper' not in dispatcher_type):

                            # chat_llmと同じ設定でLiteLLMWrapperを作成（一貫性のため）
                            mem_cube.text_mem.dispatcher_llm = self.chat_llm
                            replaced_count += 1
                            logger.info(f"🔄 新規MemCube {cube_id} のTreeTextMemory.dispatcher_llmをLiteLLMに置き換え完了 ({dispatcher_type} → LiteLLMWrapper)")
                        else:
                            logger.debug(f"新規MemCube {cube_id} のdispatcher_llmは既にLiteLLM ({dispatcher_type})")

            if replaced_count > 0:
                logger.info(f"✅ 新規MemCube TreeTextMemory dispatcher_llm置き換え完了: {replaced_count}個")

        except Exception as e:
            logger.error(f"❌ 新規MemCube TreeTextMemory dispatcher_llm置き換え失敗: {e}")
            logger.warning("新しいMemCubeでTreeTextMemory機能に問題がありますが、他の機能は正常に動作します")

    def _replace_internet_retriever_embedder(self) -> None:
        """MemCubeに紐づくインターネット検索リトリーバーのembedderをLiteLLMに統一する"""
        if not hasattr(self, '_litellm_embedder') or self._litellm_embedder is None:
            raise RuntimeError("LiteLLMEmbedderが初期化されていないためインターネット検索を利用できません")

        replaced_count = 0
        for cube_id, mem_cube in self.mem_cubes.items():
            text_mem = getattr(mem_cube, "text_mem", None)
            if text_mem is None:
                continue

            internet_retriever = getattr(text_mem, "internet_retriever", None)
            if internet_retriever is None:
                continue

            if not hasattr(internet_retriever, "embedder"):
                raise RuntimeError(f"MemCube '{cube_id}' のinternet_retrieverにembedderが存在しません")

            current_embedder = internet_retriever.embedder
            if current_embedder is self._litellm_embedder:
                continue

            internet_retriever.embedder = self._litellm_embedder
            replaced_count += 1
            logger.info(f"🔄 MemCube {cube_id} のinternet_retriever.embedderをLiteLLMに置き換え完了")

        if replaced_count > 0:
            logger.info(f"✅ インターネット検索リトリーバーのembedder置き換え完了: {replaced_count}件")

    def _build_enhance_system_prompt(
        self, user_id: str, memories_all: List[TextualMemoryItem]
    ) -> str:
        """
        CocoroAI専用システムプロンプト構築
        
        CocoroAIのシステムプロンプト + 記憶機能指示 + メモリ情報を統合
        """
        # CocoroAIのシステムプロンプトを取得
        cocoro_prompt = None
        if self.system_prompt_provider:
            try:
                cocoro_prompt = self.system_prompt_provider()
                logger.info(f"CocoroAIシステムプロンプト取得成功: {bool(cocoro_prompt)}")
            except Exception as e:
                logger.error(f"CocoroAIシステムプロンプト取得エラー: {e}")
        
        # フォールバック: CocoroAIプロンプトが取得できない場合は元のMemOSプロンプトを使用
        if not cocoro_prompt:
            logger.warning("CocoroAIプロンプト未設定、MemOSデフォルトプロンプトを使用")
            return super()._build_enhance_system_prompt(user_id, memories_all)
        
        # メモリ情報の追加処理（CocoroAI専用：記憶IDを除去してコンテンツのみ提供）
        if memories_all:
            personal_memory_context = "\n\n## Available PersonalMemory Memories:\n"
            outer_memory_context = "\n\n## Available OuterMemory Memories:\n"
            
            personal_memory_count = 0
            outer_memory_count = 0
            
            for i, memory in enumerate(memories_all, 1):
                # メモリコンテンツのみ取得（記憶IDは除去）
                memory_content = (
                    memory.memory if hasattr(memory, "memory") else str(memory)
                )
                
                # メモリタイプ別に分類（記憶IDなしでコンテンツのみ提供）
                if memory.metadata.memory_type != "OuterMemory":
                    personal_memory_context += f"- {memory_content}\n"
                    personal_memory_count += 1
                else:
                    # OuterMemoryの場合は改行を除去
                    memory_content = memory_content.replace("\n", " ")
                    outer_memory_context += f"- {memory_content}\n"
                    outer_memory_count += 1
            
            # 記憶がある場合は、CocoroAIプロンプト + 記憶機能指示 + メモリ情報
            memory_sections = ""
            if personal_memory_count > 0:
                memory_sections += personal_memory_context
            if outer_memory_count > 0:
                memory_sections += outer_memory_context
            
            result_prompt = cocoro_prompt + COCORO_MEMORY_INSTRUCTION + memory_sections
            return result_prompt

        return cocoro_prompt
    
    def get_suggestion_query(self, user_id: str, language: str = "ja") -> List[str]:
        """
        CocoroAI専用サジェスチョンクエリ生成（無効化）

        Args:
            user_id: ユーザーID
            language: 言語設定（日本語固定）

        Returns:
            List[str]: 空のリスト（機能無効化）
        """
        # サジェスチョン機能は使用しないため、常に空のリストを返す
        return []

    def _get_further_suggestion(self, message=None):
        """
        チャット内サジェスト生成（無効化）

        Args:
            message: メッセージリスト（使用しない）

        Returns:
            list: 空のリスト（機能無効化）
        """
        # サジェスチョン機能は使用しないため、常に空のリストを返す
        return []
