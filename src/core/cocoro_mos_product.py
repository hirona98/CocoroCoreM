"""
CocoroAI専用MOSProduct実装

MemOSのMOSProductクラスを継承し、CocoroAIのシステムプロンプトを使用するようカスタマイズ
"""

import logging
import json
from typing import Optional, Callable, List
from pathlib import Path

from memos.mem_os.product import MOSProduct
from memos.memories.textual.item import TextualMemoryItem
from memos.mem_os.utils.format_utils import clean_json_response

from .cocoro_prompts import (
    COCORO_MEMORY_INSTRUCTION,
    COCORO_SUGGESTION_PROMPT_JP,
    COT_DECOMPOSE_PROMPT_JP,
    SYNTHESIS_PROMPT_JP,
    QUERY_REWRITING_PROMPT_JP
)
from .cocoro_mem_reader import CocoroMemReader

logger = logging.getLogger(__name__)


class CocoroMOSProduct(MOSProduct):
    """
    CocoroAI専用MOSProduct
    
    MemOSのMOSProductを継承し、CocoroAIのシステムプロンプト機能を統合
    """
    
    def __init__(self, default_config=None, max_user_instances=1, system_prompt_provider: Optional[Callable[[], Optional[str]]] = None):
        """
        初期化
        
        Args:
            default_config: MemOSデフォルト設定
            max_user_instances: 最大ユーザーインスタンス数
            system_prompt_provider: CocoroAIシステムプロンプト取得関数
        """
        super().__init__(default_config=default_config, max_user_instances=max_user_instances)
        self.system_prompt_provider = system_prompt_provider
        
        # カスタムメモリリーダーを初期化
        if hasattr(self, 'config') and hasattr(self.config, 'mem_reader'):
            self.mem_reader = CocoroMemReader(self.config.mem_reader.config)
            logger.info("CocoroMemReaderを使用してメモリリーダーを初期化")
        
        logger.info("CocoroMOSProduct初期化完了")
    
    def _build_enhance_system_prompt(
        self, user_id: str, memories_all: List[TextualMemoryItem]
    ) -> str:
        """
        CocoroAI専用システムプロンプト構築
        
        Args:
            user_id: ユーザーID
            memories_all: 検索されたメモリアイテムリスト
            
        Returns:
            str: 構築されたシステムプロンプト
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
            logger.error("CocoroAIプロンプト未設定")
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
    
    def query_rewrite(self, query: str, dialogue: str) -> dict:
        """
        クエリ書き換え機能（日本語プロンプト使用）
        
        Args:
            query: 現在のクエリ
            dialogue: 以前の対話内容
            
        Returns:
            dict: 書き換え結果（former_dialogue_related, rewritten_question）
        """
        prompt = QUERY_REWRITING_PROMPT_JP.format(
            dialogue=dialogue,
            query=query
        )
        
        messages = [{"role": "user", "content": prompt}]
        response_text = self.chat_llm.generate(messages)
        
        try:
            json_start = response_text.find("{")
            response_text = response_text[json_start:]
            response_text = response_text.replace("```", "").strip()
            if response_text[-1] != "}":
                response_text += "}"
            response_json = json.loads(response_text)
            return response_json
        except json.JSONDecodeError as e:
            logger.warning(
                f"Failed to parse LLM response as JSON: {e}\nRaw response:\n{response_text}"
            )
            return {}
    
    def cot_decompose(self, query: str) -> dict:
        """
        Chain of Thought分解機能（日本語プロンプト使用）
        
        Args:
            query: 分解対象のクエリ
            
        Returns:
            dict: 分解結果（is_complex, sub_questions）
        """
        prompt = COT_DECOMPOSE_PROMPT_JP.format(query=query)
        
        messages = [{"role": "user", "content": prompt}]
        response_text = self.chat_llm.generate(messages)
        
        try:
            json_start = response_text.find("{")
            response_text = response_text[json_start:]
            response_text = response_text.replace("```", "").strip()
            if response_text[-1] != "}":
                response_text += "}"
            response_json = json.loads(response_text)
            return response_json
        except json.JSONDecodeError as e:
            logger.warning(
                f"Failed to parse LLM response as JSON: {e}\nRaw response:\n{response_text}"
            )
            return {}
    
    def synthesis_response(self, qa_text: str) -> str:
        """
        情報合成機能（日本語プロンプト使用）
        
        Args:
            qa_text: Q&Aペアのテキスト
            
        Returns:
            str: 合成された回答
        """
        prompt = SYNTHESIS_PROMPT_JP.format(qa_text=qa_text)
        
        messages = [{"role": "user", "content": prompt}]
        response_text = self.chat_llm.generate(messages)
        
        return response_text