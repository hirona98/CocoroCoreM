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
    
    # CocoroAI専用記憶機能指示プロンプト
    COCORO_MEMORY_INSTRUCTION = """
        "\n"
        "## 記憶機能について\n"
        "私は過去の会話や情報を記憶する機能を持っています。関連する記憶がある場合は、自然な会話の中で参照します。\n"
        "\n"
        "### 記憶の参照方法\n"
        "- 記憶を参照する際は `[番号:記憶ID]` の形式で記載します\n"
        "- 例: [1:abc123]、[2:def456]\n"
        "- 複数の記憶を参照する場合: [1:abc123][2:def456]（連続して記載）\n"
        "\n"
        "### 記憶の種類\n"
        "- **PersonalMemory**: ユーザーとの過去の会話や個人的な情報、体験した出来事\n"
        "- **OuterMemory**: インターネットや外部から得た一般的な情報\n"
        "\n"
        "### 記憶活用のルール\n"
        "1. 質問や話題に直接関連する記憶のみを参照する\n"
        "2. 自然で親しみやすい会話を心がける\n"
        "3. 記憶を参照することで会話の流れを妨げない\n"
        "4. 個人的な記憶（PersonalMemory）を優先的に活用する\n"
        "5. 通知やデスクトップ監視などの文脈も適切に考慮する\n"
        "\n"
        "記憶を活かして、より豊かで意味のある会話を行います。\n"
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
                logger.error(f"CocoroAIシステムプロンプト取得エラー: {e}")
        
        # フォールバック: CocoroAIプロンプトが取得できない場合は元のMemOSプロンプトを使用
        if not cocoro_prompt:
            logger.error("CocoroAIプロンプト未設定")
            return
        
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
            
            result_prompt = cocoro_prompt + self.COCORO_MEMORY_INSTRUCTION + memory_sections
            logger.info(f"システムプロンプト構築完了: CocoroAI + 記憶指示 + メモリ情報 (PersonalMemory: {personal_memory_count}, OuterMemory: {outer_memory_count})")
            return result_prompt
        
        # メモリがない場合はCocoroAIプロンプトのみ（記憶指示不要）
        logger.info("システムプロンプト構築完了: CocoroAIプロンプトのみ")
        return cocoro_prompt