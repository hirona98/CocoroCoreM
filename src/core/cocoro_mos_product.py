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
    
    def chat_with_references(
        self,
        query: str,
        user_id: str,
        cube_id: str,
        history=None,
        internet_search: bool = False,
        **kwargs
    ):
        """
        CocoroAI専用chat_with_references - 遅延なし版
        
        親クラスの実装を参考に、最後の同期的なself.addを非同期化
        """
        import json
        import time
        import threading
        from datetime import datetime
        
        logger.info(f"CocoroAI chat_with_references開始: user_id={user_id}, cube_id={cube_id}")
        logger.info("*** 独自実装のchat_with_referencesが呼び出されました ***")
        
        # 親クラスと同じ処理フロー（ただし最後のaddを非同期化）
        self._load_user_cubes(user_id, self.default_config)
        time_start = time.time()
        memories_list = []
        
        # ステータス送信
        yield f"data: {json.dumps({'type': 'status', 'data': '0'})}\n\n"
        
        # 記憶検索
        memories_result = super(MOSProduct, self).search(
            query,
            user_id,
            install_cube_ids=[cube_id] if cube_id else None,
            top_k=kwargs.get('top_k', 10),
            mode="fine",
            internet_search=internet_search
        )["text_mem"]
        
        yield f"data: {json.dumps({'type': 'status', 'data': '1'})}\n\n"
        
        # スケジューラーへ通知
        self._send_message_to_scheduler(
            user_id=user_id, mem_cube_id=cube_id, query=query, label="QUERY"
        )
        
        if memories_result:
            memories_list = memories_result[0]["memories"]
            memories_list = self._filter_memories_by_threshold(memories_list)
        
        # システムプロンプト構築（CocoroAI版使用）
        system_prompt = self._build_enhance_system_prompt(user_id, memories_list)
        
        # チャット履歴管理
        if user_id not in self.chat_history_manager:
            self._register_chat_history(user_id)
        
        chat_history = self.chat_history_manager[user_id]
        if history:
            chat_history.chat_history = history[-10:]
        
        current_messages = [
            {"role": "system", "content": system_prompt},
            *chat_history.chat_history,
            {"role": "user", "content": query},
        ]
        
        yield f"data: {json.dumps({'type': 'status', 'data': '2'})}\n\n"
        
        # LLM応答生成
        logger.info(f"LLM応答生成開始: backend={self.config.chat_model.backend}")
        if self.config.chat_model.backend in ["huggingface", "vllm"]:
            response_stream = self.chat_llm.generate_stream(current_messages)
        else:
            response_stream = self.chat_llm.generate(current_messages)
        
        logger.info("ストリーミング処理開始")
        # ストリーミング処理
        buffer = ""
        full_response = ""
        
        chunk_count = 0
        for chunk in response_stream:
            chunk_count += 1
            if chunk in ["<think>", "</think>"]:
                continue
            buffer += chunk
            full_response += chunk
            
            # バッファ処理（親クラスと同じ）
            from memos.mem_os.utils.reference_utils import process_streaming_references_complete
            processed_chunk, remaining_buffer = process_streaming_references_complete(buffer)
            
            if processed_chunk:
                chunk_data = f"data: {json.dumps({'type': 'text', 'data': processed_chunk}, ensure_ascii=False)}\n\n"
                yield chunk_data
                buffer = remaining_buffer
        
        logger.info(f"ストリーミング処理完了: chunk_count={chunk_count}, full_response_length={len(full_response)}")
        
        # 残りのバッファ処理
        if buffer:
            from memos.mem_os.utils.reference_utils import process_streaming_references_complete
            processed_chunk, _ = process_streaming_references_complete(buffer)
            if processed_chunk:
                chunk_data = f"data: {json.dumps({'type': 'text', 'data': processed_chunk}, ensure_ascii=False)}\n\n"
                yield chunk_data
        
        # 参照データ準備
        reference = []
        for memory in memories_list:
            memory_json = memory.model_dump()
            memory_json["metadata"]["ref_id"] = f"{memory.id.split('-')[0]}"
            memory_json["metadata"]["embedding"] = []
            memory_json["metadata"]["sources"] = []
            memory_json["metadata"]["memory"] = memory.memory
            memory_json["metadata"]["id"] = memory.id
            reference.append({"metadata": memory_json["metadata"]})
        
        yield f"data: {json.dumps({'type': 'reference', 'data': reference})}\n\n"
        
        # タイミング情報
        time_end = time.time()
        speed_improvement = round(float((len(system_prompt) / 2) * 0.0048 + 44.5), 1)
        total_time = round(float(time_end - time_start), 1)
        
        yield f"data: {json.dumps({'type': 'time', 'data': {'total_time': total_time, 'speed_improvement': f'{speed_improvement}%'}})}\n\n"
        yield f"data: {json.dumps({'type': 'end'})}\n\n"
        
        logger.info(f"ストリーミング完了 - 記憶保存処理を開始します: full_response_length={len(full_response)}")
        
        # 参照抽出
        clean_response, extracted_references = self._extract_references_from_response(full_response)
        logger.info(f"参照抽出完了: clean_response_length={len(clean_response)}, extracted_refs={len(extracted_references)}")
        
        # スケジューラーへ応答通知
        self._send_message_to_scheduler(
            user_id=user_id, mem_cube_id=cube_id, query=clean_response, label="ANSWER"
        )
        
        # ========== ここが重要：記憶保存を非同期化 ==========
        def async_memory_save():
            """バックグラウンドで記憶保存"""
            try:
                logger.info(f"非同期記憶保存開始: user_id={user_id}, cube_id={cube_id}")
                
                messages = [
                    {
                        "role": "user",
                        "content": query,
                        "chat_time": str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    },
                    {
                        "role": "assistant",
                        "content": clean_response,
                        "chat_time": str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    },
                ]
                
                logger.info(f"記憶保存データ準備完了: messages={len(messages)}件")
                
                # 正しいaddメソッド呼び出し（MOSCoreクラスの継承チェーン）
                MOSProduct.add(self, 
                    user_id=user_id,
                    messages=messages,
                    mem_cube_id=cube_id
                )
                
                logger.info(f"非同期記憶保存完了: user_id={user_id}, cube_id={cube_id}")
                
            except Exception as e:
                logger.error(f"非同期記憶保存エラー: {e}", exc_info=True)
        
        # 別スレッドで記憶保存実行（daemon=False で安全性向上）
        save_thread = threading.Thread(target=async_memory_save, daemon=False)
        save_thread.start()
        
        # オプション：スレッド参照を保持（デバッグ用）
        if not hasattr(self, '_memory_save_threads'):
            self._memory_save_threads = []
        self._memory_save_threads.append(save_thread)
        
        logger.info(f"chat_with_references完了（記憶保存は非同期実行中）: cube_id={cube_id}")