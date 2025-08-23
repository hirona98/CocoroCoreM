"""
CocoroAI専用メモリリーダー

MemOSのSimpleStructMemReaderを継承し、日本語プロンプトを使用して
記憶抽出を実行するカスタマイズされたメモリリーダー
"""

import concurrent.futures
from typing import List, Any

from memos.mem_reader.simple_struct import SimpleStructMemReader
from memos.memories.textual.item import TextualMemoryItem, TreeNodeTextualMemoryMetadata

from .cocoro_prompts import (
    SIMPLE_STRUCT_MEM_READER_PROMPT_JP,
    SIMPLE_STRUCT_DOC_READER_PROMPT_JP,
    SIMPLE_STRUCT_MEM_READER_EXAMPLE_JP
)


class CocoroMemReader(SimpleStructMemReader):
    """
    CocoroAI専用メモリリーダー
    
    SimpleStructMemReaderを継承し、日本語プロンプトを使用して
    記憶抽出を実行するカスタマイズされたメモリリーダー
    """
    
    def _process_chat_data(self, scene_data_info: List[str], info: dict[str, Any]) -> List[TextualMemoryItem]:
        """
        チャットデータから記憶を抽出（日本語プロンプト使用）
        
        Args:
            scene_data_info: チャット会話データ
            info: ユーザーIDやセッションID情報
        
        Returns:
            抽出された記憶アイテムのリスト
        """
        # 日本語プロンプトを使用
        prompt = SIMPLE_STRUCT_MEM_READER_PROMPT_JP.replace(
            "${conversation}", "\n".join(scene_data_info)
        )
        if self.config.remove_prompt_example:
            # 日本語の例文部分を削除
            prompt = prompt.replace(SIMPLE_STRUCT_MEM_READER_EXAMPLE_JP, "")

        messages = [{"role": "user", "content": prompt}]

        response_text = self.llm.generate(messages)
        response_json = self.parse_json_result(response_text)

        chat_read_nodes = []
        for memory_i_raw in response_json.get("memory list", []):
            node_i = TextualMemoryItem(
                memory=memory_i_raw.get("value", ""),
                metadata=TreeNodeTextualMemoryMetadata(
                    user_id=info.get("user_id"),
                    session_id=info.get("session_id"),
                    memory_type=memory_i_raw.get("memory_type", ""),
                    status="activated",
                    tags=memory_i_raw.get("tags", [])
                    if type(memory_i_raw.get("tags", [])) is list
                    else [],
                    key=memory_i_raw.get("key", ""),
                    embedding=self.embedder.embed([memory_i_raw.get("value", "")])[0],
                    usage=[],
                    sources=scene_data_info,
                    background=response_json.get("summary", ""),
                    confidence=0.99,
                    type="fact",
                ),
            )
            chat_read_nodes.append(node_i)

        return chat_read_nodes
    
    def _process_doc_data(self, scene_data_info: dict, info: dict[str, Any]) -> List[TextualMemoryItem]:
        """
        ドキュメントデータから記憶を抽出（日本語プロンプト使用）
        
        Args:
            scene_data_info: ドキュメント情報（fileとtextを含む）
            info: ユーザーIDやセッションID情報
        
        Returns:
            抽出された記憶アイテムのリスト
        """
        chunks = self.chunker.chunk(scene_data_info["text"])
        messages = [
            [
                {
                    "role": "user",
                    "content": SIMPLE_STRUCT_DOC_READER_PROMPT_JP.replace("{chunk_text}", chunk.text),
                }
            ]
            for chunk in chunks
        ]

        processed_chunks = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self.llm.generate, message) for message in messages]
            for future in concurrent.futures.as_completed(futures):
                chunk_result = future.result()
                if chunk_result:
                    processed_chunks.append(chunk_result)

        processed_chunks = [self.parse_json_result(r) for r in processed_chunks]
        doc_nodes = []
        for i, chunk_res in enumerate(processed_chunks):
            if chunk_res:
                node_i = TextualMemoryItem(
                    memory=chunk_res["value"],
                    metadata=TreeNodeTextualMemoryMetadata(
                        user_id=info.get("user_id"),
                        session_id=info.get("session_id"),
                        memory_type="LongTermMemory",
                        status="activated",
                        tags=chunk_res["tags"] if type(chunk_res["tags"]) is list else [],
                        key=chunk_res["key"],
                        embedding=self.embedder.embed([chunk_res["value"]])[0],
                        usage=[],
                        sources=[f"{scene_data_info['file']}_{i}"],
                        background="",
                        confidence=0.99,
                        type="fact",
                    ),
                )
                doc_nodes.append(node_i)
        return doc_nodes