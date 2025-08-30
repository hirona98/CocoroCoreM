"""
CocoroAI専用MOSProduct実装

MemOSのMOSProductクラスを継承し、CocoroAIのシステムプロンプトを使用するようカスタマイズ
動的プロンプト置換により、外部ライブラリを変更せずに全MemOS機能を日本語化
"""

import logging
import json
from typing import Optional, Callable, List, Dict, Any

from memos.mem_os.product import MOSProduct
from memos.memories.textual.item import TextualMemoryItem
from memos.mem_os.utils.format_utils import clean_json_response

from .cocoro_prompts import (
    COCORO_MEMORY_INSTRUCTION,
    COCORO_SUGGESTION_PROMPT_JP,
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
                 litellm_config: Optional[Dict[str, Any]] = None):
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
        
        logger.info(f"CocoroMOSProduct初期化完了: LiteLLM={'有効' if litellm_config else '無効'}")
    
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
                
            logger.info("🎌 MemOS全機能のプロンプトを日本語版に置換完了")
            
        except ImportError as e:
            logger.warning(f"MemOSモジュールのインポートに失敗: {e}")
        except Exception as e:
            logger.error(f"プロンプト置換中にエラーが発生: {e}", exc_info=True)
    
    def _setup_litellm(self, config: Dict[str, Any]):
        """LiteLLMセットアップ（エラー時は例外を再発生）"""
        try:
            # 元のchat_llmをバックアップ（将来の拡張のため）
            self._original_chat_llm = self.chat_llm
            
            # LiteLLMWrapper import
            from .litellm_wrapper import LiteLLMConfig, LiteLLMWrapper
            
            # LiteLLMConfig作成
            litellm_config = LiteLLMConfig(
                model_name=config.get('model', 'gpt-4o-mini'),
                api_key=config.get('api_key', ''),
                max_tokens=config.get('max_tokens', 1024),
                extra_config=config.get('extra_config', {})
            )
            
            # chat_llmをLiteLLMWrapperに置き換え
            self.chat_llm = LiteLLMWrapper(litellm_config)
            
            logger.info(f"✅ LiteLLM統合完了: {litellm_config.model_name_or_path}")
            
        except Exception as e:
            # 詳細エラー出力
            logger.error(f"❌ LiteLLMセットアップ失敗:")
            logger.error(f"   モデル: {config.get('model', 'N/A')}")
            logger.error(f"   エラー: {str(e)}")
            logger.error(f"   設定内容: {config}")
            
            # エラーを再発生（フォールバックしない）
            raise RuntimeError(f"LiteLLMセットアップエラー: {str(e)}")
    
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
        
        # メモリ情報の追加処理（MemOSの標準フォーマットに従う）
        if memories_all:
            personal_memory_context = "\n\n## Available ID and PersonalMemory Memories:\n"
            outer_memory_context = "\n\n## Available ID and OuterMemory Memories:\n"
            
            personal_memory_count = 0
            outer_memory_count = 0
            
            for i, memory in enumerate(memories_all, 1):
                # メモリIDとコンテンツの取得（MemOSと同じ形式）
                memory_id = (
                    f"{memory.id.split('-')[0]}" if hasattr(memory, "id") else f"mem_{i}"
                )
                memory_content = (
                    memory.memory[:500] if hasattr(memory, "memory") else str(memory)
                )
                
                # メモリタイプ別に分類
                if memory.metadata.memory_type != "OuterMemory":
                    personal_memory_context += f"{memory_id}: {memory_content}\n"
                    personal_memory_count += 1
                else:
                    # OuterMemoryの場合は改行を除去
                    memory_content = memory_content.replace("\n", " ")
                    outer_memory_context += f"{memory_id}: {memory_content}\n"
                    outer_memory_count += 1
            
            # 記憶がある場合は、CocoroAIプロンプト + 記憶機能指示 + メモリ情報
            memory_sections = ""
            if personal_memory_count > 0:
                memory_sections += personal_memory_context
            if outer_memory_count > 0:
                memory_sections += outer_memory_context
            
            result_prompt = cocoro_prompt + COCORO_MEMORY_INSTRUCTION + memory_sections
            logger.info(f"システムプロンプト構築完了: CocoroAI + 記憶指示 + メモリ情報 (PersonalMemory: {personal_memory_count}, OuterMemory: {outer_memory_count})")
            return result_prompt
        
        # メモリがない場合はCocoroAIプロンプトのみ（記憶指示不要）
        logger.info("システムプロンプト構築完了: CocoroAIプロンプトのみ")
        return cocoro_prompt
    
    def get_suggestion_query(self, user_id: str, language: str = "ja") -> List[str]:
        """
        CocoroAI専用サジェスチョンクエリ生成（日本語専用）
        
        Args:
            user_id: ユーザーID
            language: 言語設定（日本語固定）
            
        Returns:
            List[str]: サジェスチョンクエリのリスト
        """
        # 最近の記憶を取得
        text_mem_result = super().search("my recently memories", user_id=user_id, top_k=3)[
            "text_mem"
        ]
        if text_mem_result:
            memories = "\n".join([m.memory[:200] for m in text_mem_result[0]["memories"]])
        else:
            memories = ""
        
        # 日本語プロンプトでクエリ生成
        message_list = [{"role": "system", "content": COCORO_SUGGESTION_PROMPT_JP.format(memories=memories)}]
        response = self.chat_llm.generate(message_list)
        clean_response = clean_json_response(response)
        response_json = json.loads(clean_response)
        return response_json["query"]