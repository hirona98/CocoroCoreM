"""
CocoroCoreM 画像処理モジュール

画像の説明生成を提供（自然な日本語テキスト）
"""

import logging
import os
from typing import Optional, List, Dict, Any
import asyncio

logger = logging.getLogger(__name__)


async def generate_image_description(image_data_list: List[Dict[str, str]], cocoro_config) -> Optional[str]:
    """画像の客観的な説明を生成（複数画像対応）
    
    Args:
        image_data_list: 画像データのリスト（Base64 data URL形式）
        cocoro_config: CocoroAI設定オブジェクト
        
    Returns:
        画像の説明テキスト、または失敗時はNone
    """
    try:
        import litellm

        if not image_data_list:
            return None

        # キャラクター設定の検証
        current_character = cocoro_config.current_character
        if not current_character:
            logger.error("❌ キャラクター設定がないため、画像説明の生成をスキップします")
            return None
            
        # visionModelの検証（設定必須）
        if not hasattr(current_character, 'visionModel') or not current_character.visionModel:
            logger.error("❌ visionModelが設定されていません。Setting.jsonでvisionModelを設定してください（例: 'openai/gpt-4o-mini'）")
            return None
            
        # プロバイダー接頭辞の検証（他の設定と一貫性保持）
        if "/" not in current_character.visionModel:
            logger.error(f"❌ visionModelにプロバイダー接頭辞がありません: '{current_character.visionModel}' - 'provider/model' 形式で指定してください（例: openai/gpt-4o-mini）")
            return None
            
        model = current_character.visionModel
        
        # Vision用APIキーの取得
        api_key = current_character.get_vision_api_key()
            
        logger.info(f"🖼️ Vision設定: model={model}")
            
        # 画像説明システムプロンプト
        system_prompt = (
            f"画像{len(image_data_list)}枚を客観的に分析し、詳細に説明してください。\n\n"
            
            "記述要件:\n"
            "• 各画像の種類（写真/イラスト/スクリーンショット/図表など）\n"
            "• 内容や被写体の詳細\n"
            "• 色彩や特徴\n"
            "• 文字情報（あれば記載）\n"
            "• 画像が複数ある場合は画像間の関連性\n"
            "• 説明の最後に「この画像は～といった特徴を持つ。」の形で関連キーワードを含める\n\n"
            
            "出力例:\n"
            "1枚の場合:\n"
            "後楽園遊園地を描いたカラーイラスト。中央に白い観覧車と赤いゴンドラ、右側に青黄ストライプのメリーゴーラウンド。青空の下、来園者が散歩している平和な風景。この画像は風景、楽しい雰囲気、昼の時間帯、遊園地、イラスト、観覧車といった特徴を持つ。\n\n"
            
            "複数枚の場合:\n"
            "1枚目：後楽園遊園地を描いたカラーイラスト。中央に白い観覧車と赤いゴンドラ、右側に青黄ストライプのメリーゴーラウンド。青空の下、来園者が散歩している平和な風景。2枚目：同じ遊園地の夜景写真。ライトアップされた観覧車が夜空に映え、ゴンドラから漏れる光が幻想的。メリーゴーラウンドも煌びやかにライトアップされ、夜の遊園地特有のロマンチックな雰囲気を演出。関連性：同じ後楽園遊園地の昼と夜の風景で、時間帯による雰囲気の違いを対比的に見せている。この画像は風景、楽しい雰囲気、昼夜の時間帯、遊園地、イラスト、写真、観覧車、ライトアップといった特徴を持つ。\n\n"
            
            "キーワード例:\n"
            "カテゴリ: 風景、人物、食事、建物、画面（プログラム）、画面（SNS）、画面（ゲーム）、画面（買い物）、画面（鑑賞）\n"
            "雰囲気: 明るい、楽しい、悲しい、静か、賑やか\n"
            "時間帯: 朝、昼、夕方、夜、不明\n"
            "その他: 具体的な被写体や特徴をキーワードとして含める"
        )
        user_text = f"この{len(image_data_list)}枚の画像を客観的に説明してください。"
        
        # メッセージコンテンツを構築
        user_content = []
        for i, image_data in enumerate(image_data_list):
            # Base64 data URL形式の画像データを使用
            image_url = image_data.get("data", "")
            if image_url:
                user_content.append({
                    "type": "image_url", 
                    "image_url": {"url": image_url}
                })
        user_content.append({"type": "text", "text": user_text})
        
        # LiteLLM Vision APIで画像の説明を生成
        # 環境変数にAPIキーを設定
        provider = model.split("/")[0] if "/" in model else "openai"
        if provider == "openai":
            os.environ["OPENAI_API_KEY"] = api_key
        elif provider == "gemini":
            os.environ["GEMINI_API_KEY"] = api_key
        elif provider == "anthropic":
            os.environ["ANTHROPIC_API_KEY"] = api_key
        elif provider == "xai":
            os.environ["XAI_API_KEY"] = api_key
        
        response = await litellm.acompletion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        full_response = response.choices[0].message.content
        logger.info(f"画像説明を生成しました（{len(image_data_list)}枚）: {full_response[:50]}...")
        return full_response
        
    except Exception as e:
        logger.error(f"画像説明の生成に失敗しました: {e}")
        return None


def format_image_context_for_chat(image_description: str, user_query: str) -> str:
    """画像説明とユーザークエリを結合してチャット用のテキストを生成
    
    Args:
        image_description: LLMからの画像説明
        user_query: ユーザーのメッセージ
        
    Returns:
        結合されたチャット用テキスト
    """
    if not image_description:
        return user_query
    
    # 画像説明部分（先行）
    image_section = f"━━━ 添付画像 ━━━\n{image_description.strip()}"
    
    # ユーザーメッセージがある場合は質問セクションとして追加
    if user_query.strip():
        user_section = f"━━━ ユーザー質問 ━━━\n{user_query.strip()}"
        return f"{image_section}\n\n{user_section}"
    else:
        # 画像のみの場合
        return image_section