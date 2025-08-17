"""
CocoroAI専用MOSProduct実装

MemOSのMOSProductクラスを継承し、CocoroAIのシステムプロンプトを使用するようカスタマイズ
"""

import logging
from typing import Optional, Callable, List
from pathlib import Path

from memos.mem_os.product import MOSProduct
from memos.memories.textual.item import TextualMemoryItem

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
                logger.warning(f"CocoroAIシステムプロンプト取得エラー: {e}")
        
        # フォールバック: CocoroAIプロンプトが取得できない場合は元のMemOSプロンプトを使用
        if not cocoro_prompt:
            logger.info("CocoroAIプロンプトが未設定のため、MemOSデフォルトプロンプトを使用")
            return super()._build_enhance_system_prompt(user_id, memories_all)
        
        # メモリ情報の追加処理（MemOSの標準フォーマットに従う）
        if memories_all:
            personal_memory_context = "\n\n## Available ID and PersonalMemory Memories:\n"
            outer_memory_context = "\n\n## Available ID and OuterMemory Memories:\n"
            
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
                else:
                    # OuterMemoryの場合は改行を除去
                    memory_content = memory_content.replace("\n", " ")
                    outer_memory_context += f"{memory_id}: {memory_content}\n"
            
            # CocoroAIプロンプト + メモリ情報
            result_prompt = cocoro_prompt + personal_memory_context + outer_memory_context
            logger.info(f"システムプロンプト構築完了: CocoroAI + メモリ情報 (メモリ数: {len(memories_all)})")
            return result_prompt
        
        # メモリがない場合はCocoroAIプロンプトのみ
        logger.info("システムプロンプト構築完了: CocoroAIプロンプトのみ")
        return cocoro_prompt