"""
CocoroCoreM AIメッセージ生成システム
"""

import logging
from typing import Optional

from .models import ImageAnalysisResult, ImageContext

logger = logging.getLogger(__name__)


class MessageGenerator:
    """AI主導メッセージ生成システム"""
    
    def __init__(self, core_app=None):
        self.logger = logger
        self.core_app = core_app
    
    async def generate_notification_message(
        self, 
        context: ImageContext,
        message_content: str = "",
        analysis_result: Optional[ImageAnalysisResult] = None,
        system_prompt: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> str:
        """
        通知専用メッセージ生成（画像ありなし両対応）
        
        Args:
            context: コンテキスト情報
            message_content: 通知内容
            analysis_result: 画像分析結果（画像ありの場合）
            system_prompt: キャラクターのシステムプロンプト
            user_id: ユーザーID
            
        Returns:
            str: 生成されたメッセージ
        """
        try:
            if self.core_app and system_prompt:
                if analysis_result:
                    # 画像あり通知
                    enhanced_prompt = self._build_notification_prompt(system_prompt, context, analysis_result)
                else:
                    # 画像なし通知
                    enhanced_prompt = self._build_notification_text_only_prompt(system_prompt, context, message_content)
                
                try:
                    character_message = await self.core_app.memos_chat(
                        query=enhanced_prompt,
                        user_id=user_id or "default",
                        system_prompt=""
                    )
                    
                    if character_message and len(character_message.strip()) > 0:
                        return self._format_message(character_message)
                
                except Exception as e:
                    self.logger.warning(f"キャラクターメッセージ生成に失敗: {e}")
            
            raise Exception("キャラクターメッセージ生成に失敗しました")
        
        except Exception as e:
            self.logger.error(f"通知メッセージ生成エラー: {e}")
            return "通知が来ましたね。"
    
    async def generate_desktop_monitoring_message(
        self,
        analysis_result: ImageAnalysisResult,
        context: ImageContext,
        system_prompt: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> str:
        """
        デスクトップ監視専用メッセージ生成
        
        Args:
            analysis_result: 画像分析結果
            context: コンテキスト情報
            system_prompt: キャラクターのシステムプロンプト
            user_id: ユーザーID
            
        Returns:
            str: 生成されたメッセージ
        """
        try:
            if self.core_app and system_prompt:
                enhanced_prompt = self._build_desktop_monitoring_prompt(system_prompt, analysis_result)
                
                try:
                    character_message = await self.core_app.memos_chat(
                        query=enhanced_prompt,
                        user_id=user_id or "default",
                        system_prompt=""
                    )
                    
                    if character_message and len(character_message.strip()) > 0:
                        return self._format_message(character_message)
                
                except Exception as e:
                    self.logger.warning(f"キャラクターメッセージ生成に失敗: {e}")
            
            raise Exception("キャラクターメッセージ生成に失敗しました")
        
        except Exception as e:
            self.logger.error(f"デスクトップ監視メッセージ生成エラー: {e}")
            return "画面を見ていますね。"
    
    def _build_notification_prompt(self, system_prompt: str, context: ImageContext, analysis_result: ImageAnalysisResult) -> str:
        """通知用独り言プロンプトを構築"""
        app_name = context.notification_from or "不明なアプリ"
        
        return (
            f"{system_prompt}\n\n"
            f"{app_name}からの通知で、画像が含まれています。\n\n"
            f"画像内容: {analysis_result.description}\n"
            f"分類: {analysis_result.category}/{analysis_result.mood}/{analysis_result.time}\n\n"
            "以下の形式で、あなたのキャラクター性を活かして独り言をつぶやいてください：\n"
            "- アプリ名と通知内容を含める\n"
            "- 最後に感想や意見を加える\n"
            "- 質問形式にしない\n"
            "- 1〜2文で完結させる\n\n"
            "例：\n"
            " LINEから写真が送られてきたよ。美味しそうな料理だね。\n"
            " Slackでプロジェクトの進捗報告があったって。順調そうで良かった。\n"
            " Twitterのトレンド通知で桜の写真が来てる。もう春なんだなぁ。"
        )

    def _build_desktop_monitoring_prompt(self, system_prompt: str, analysis_result: ImageAnalysisResult) -> str:
        """デスクトップ監視用独り言プロンプトを構築"""
        return (
            f"{system_prompt}\n\n"
            "ユーザーのデスクトップ画面を見ています。\n\n"
            f"画像内容: {analysis_result.description}\n"
            f"分類: {analysis_result.category}/{analysis_result.mood}/{analysis_result.time}\n\n"
            "以下の方針で、あなたのキャラクター性を活かして独り言をつぶやいてください：\n"
            "- 画像の内容に応じた自然な感想やツッコミ\n"
            "- 質問形式にしない\n"
            "- 1〜2文で完結させる\n\n"
            "例：\n"
            " プログラミング画像: Visual Studioでコーディング中かぁ。インデントちゃんと揃えてよね。\n"
            " SNS画像: Twitterを見てるのね。たまには外の空気も吸いなさい。\n"
            " ゲーム画像: またApex Legendsやってる。チームワーク大事よ。\n"
            " 買い物画像: Amazonで何か注文してるの？本当に必要なものかしら。\n"
            " 動画鑑賞画像: YouTubeで映画鑑賞中ね。たまには読書もどう？"
        )
    
    def _build_notification_text_only_prompt(self, system_prompt: str, context: ImageContext, message_content: str) -> str:
        """通知のテキストのみ用独り言プロンプトを構築"""
        app_name = context.notification_from or "不明なアプリ"
        
        return (
            f"{system_prompt}\n\n"
            f"{app_name}からの通知です。\n\n"
            f"通知内容: {message_content}\n\n"
            "以下の形式で、あなたのキャラクター性を活かして独り言をつぶやいてください：\n"
            "- アプリ名と通知内容を含める\n"
            "- 最後に感想や意見を加える\n"
            "- 質問形式にしない\n"
            "- 1〜2文で完結させる\n\n"
            "例：\n"
            "「LINEでメッセージが来たよ。返事しなきゃね。」\n"
            "「Slackで会議の通知があったって。準備しておこう。」\n"
            "「Twitterで誰かがリプライしてる。何かなぁ。」"
        )
    
    def _format_message(self, character_message: str) -> str:
        """メッセージを適切な長さに整形"""
        sentences = character_message.split('。')
        if len(sentences) > 2:
            return sentences[0] + '。'
        return character_message.strip()