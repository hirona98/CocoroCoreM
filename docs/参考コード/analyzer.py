"""
CocoroCore2 統合画像分析システム
"""

import logging
import os
from typing import Dict, List, Optional

from .models import ImageAnalysisResult

logger = logging.getLogger(__name__)


class ImageAnalyzer:
    """統合画像分析システム"""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = logger

        self.multimodal_enabled = config.get("multimodal_enabled", True)
        self.max_image_size = config.get("max_image_size", 20000000)
        self.analysis_timeout_seconds = config.get("analysis_timeout_seconds", 60)

    async def analyze_image(self, image_urls: List[str]) -> ImageAnalysisResult:
        """
        画像の詳細分析

        Args:
            image_urls: 画像URLのリスト

        Returns:
            ImageAnalysisResult: 分析結果
        """
        if not self.multimodal_enabled:
            self.logger.warning("マルチモーダル機能が無効になっています")
            raise Exception("画像分析に失敗しました")

        if not image_urls:
            self.logger.warning("画像URLが提供されていません")
            raise Exception("画像分析に失敗しました")

        try:
            self._validate_image_sizes(image_urls)

            from openai import AsyncOpenAI

            api_key, model = self._get_vision_config()

            if not api_key:
                self.logger.warning("APIキーが設定されていないため、画像分析をスキップします")
                raise Exception("画像分析に失敗しました")

            client = AsyncOpenAI(api_key=api_key)

            system_prompt, user_text = self._get_prompts(len(image_urls))

            user_content = []
            for image_url in image_urls:
                user_content.append({"type": "image_url", "image_url": {"url": image_url}})
            user_content.append({"type": "text", "text": user_text})

            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                timeout=self.analysis_timeout_seconds,
            )

            full_response = response.choices[0].message.content
            self.logger.info(f"画像分析完了（{len(image_urls)}枚）: {full_response[:50]}...")

            return self._parse_analysis_response(full_response)

        except Exception as e:
            self.logger.error(f"画像分析に失敗: {e}")
            raise Exception("画像分析に失敗しました")

    def _validate_image_sizes(self, image_urls: List[str]):
        """画像サイズの検証"""
        for i, url in enumerate(image_urls):
            if url.startswith("data:") and ";base64," in url:
                base64_data = url.split(";base64,", 1)[1]
                estimated_size = len(base64_data) * 3 // 4

                if estimated_size > self.max_image_size:
                    raise ValueError(
                        f"画像{i+1}のサイズ({estimated_size}bytes)が制限({self.max_image_size}bytes)を超えています"
                    )

    def _get_vision_config(self) -> tuple[Optional[str], str]:
        """画像分析用の設定を取得"""
        character_list = self.config.get("characterList", [])
        current_char_index = self.config.get("currentCharacterIndex", 0)

        if character_list and current_char_index < len(character_list):
            current_char = character_list[current_char_index]
            vision_api_key = current_char.get("visionApiKey")
            api_key = vision_api_key if vision_api_key else current_char.get("apiKey")
            model = current_char.get("visionModel", "gpt-4o-mini")
        else:
            api_key = os.getenv("OPENAI_API_KEY")
            model = "gpt-4o-mini"

        return api_key, model


    def _parse_analysis_response(self, response: str) -> ImageAnalysisResult:
        """分析結果の構造化解析（個別分析のみ）"""
        if not response:
            raise Exception("画像分析に失敗しました")

        # 個別画像の分析結果を解析
        images_data = self._parse_individual_images(response)
        
        if not images_data:
            raise Exception("画像分析に失敗しました")
        
        # 最初の画像の分類を基本情報として使用（下流処理で判断される）
        first_image = images_data[0]
        
        # すべての画像の説明をまとめる
        if len(images_data) == 1:
            description = first_image["description"]
        else:
            descriptions = [f"画像{i+1}: {img['description']}" for i, img in enumerate(images_data)]
            description = '\n'.join(descriptions)
        
        return ImageAnalysisResult(
            description=description,
            category=first_image["category"],
            mood=first_image["mood"],
            time=first_image["time"]
        )
    
    def _parse_individual_images(self, response: str) -> list[dict]:
        """個別画像の分析結果をパース"""
        images_data = []
        current_image_data = {}
        
        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            
            if line.startswith('画像') and ':' in line:
                # 前の画像データを保存
                if current_image_data and current_image_data.get("description"):
                    images_data.append(current_image_data)
                # 新しい画像データを開始
                current_image_data = {"description": "", "category": "", "mood": "", "time": ""}
                
            elif line.startswith('説明:'):
                current_image_data["description"] = line[3:].strip()
                
            elif line.startswith('分類:'):
                metadata_text = line[3:].strip()
                parts = [p.strip() for p in metadata_text.split('/')]
                if len(parts) >= 1:
                    current_image_data["category"] = parts[0]
                if len(parts) >= 2:
                    current_image_data["mood"] = parts[1]
                if len(parts) >= 3:
                    current_image_data["time"] = parts[2]
        
        # 最後の画像データを保存
        if current_image_data and current_image_data.get("description"):
            images_data.append(current_image_data)
        
        return images_data

    def _get_prompts(self, image_count: int) -> tuple[str, str]:
        """画像分析用プロンプトを生成（1枚～複数枚対応）"""
        
        # 画像の個別分析セクションを動的生成
        image_sections = []
        for i in range(1, image_count + 1):
            section = f"画像{i}:\n説明: [この画像の詳細で客観的な説明]\n分類: [カテゴリ] / [雰囲気] / [時間帯]"
            image_sections.append(section)
        
        system_prompt = (
            f"画像（{image_count}枚）を分析し、以下の形式で応答してください：\n\n"
            f"{chr(10).join(image_sections)}\n\n"
            "各説明は客観的かつ的確に、以下を含めてください：\n"
            "- 画像の種類（写真/イラスト/スクリーンショット/図表など）\n"
            "- 内容や被写体\n"
            "- 色彩や特徴\n"
            "- 文字情報があれば記載\n\n"
            "分類の選択肢：\n"
            "- カテゴリ: 風景/人物/食事/建物/画面（プログラム）/画面（SNS）/画面（ゲーム）/画面（買い物）/画面（鑑賞）/[その他任意の分類]\n"
            "- 雰囲気: 明るい/楽しい/悲しい/静か/賑やか/[その他任意の分類]\n"
            "- 時間帯: 朝/昼/夕方/夜/不明"
        )

        user_text = f"{'この画像' if image_count == 1 else f'これら{image_count}枚の画像'}を客観的に説明してください。"
        
        return system_prompt, user_text