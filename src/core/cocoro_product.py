"""
CocoroCore2 MOSProduct統合ラッパー

MemOS MOSProductのラッパークラス実装
"""

import asyncio
import logging
from typing import AsyncIterator, Dict, List, Optional
from pathlib import Path

from memos.mem_os.product import MOSProduct
from memos import GeneralMemCube

from .config_manager import CocoroAIConfig, generate_memos_config_from_setting, get_mos_config

logger = logging.getLogger(__name__)


class CocoroProductWrapper:
    """MOSProductのラッパークラス（確証：参考コード設計）"""
    
    def __init__(self, cocoro_config: CocoroAIConfig):
        """
        初期化
        
        Args:
            cocoro_config: CocoroAI設定オブジェクト
        """
        self.cocoro_config = cocoro_config
        self.logger = logger
        
        # MOSConfig動的生成（確証：config.py実装済み）
        mos_config = get_mos_config(cocoro_config)
        
        # MOSProduct初期化（確証：MemOS product.py仕様）
        self.mos_product = MOSProduct(
            default_config=mos_config,
            max_user_instances=1  # シングルユーザー
        )
        
        # 画像・メッセージ生成器は後で初期化（循環参照回避）
        self.image_analyzer = None
        self.message_generator = None
        
        # 現在のユーザーIDを設定
        current_character = cocoro_config.current_character
        self.current_user_id = current_character.userId if current_character else "user"
        
        # システムプロンプトのパスを取得
        self.system_prompt_path = None
        if current_character and current_character.systemPromptFilePath:
            # UserData2ディレクトリからの相対パス
            base_dir = Path(__file__).parent.parent.parent / "UserData2"
            self.system_prompt_path = base_dir / current_character.systemPromptFilePath
    
    async def initialize(self):
        """非同期初期化処理"""
        try:
            # ユーザーが未登録の場合は登録
            users = self.mos_product.list_users()
            # usersはUserオブジェクトのリストなので属性でアクセス
            user_ids = [u.user_id if hasattr(u, 'user_id') else str(u) for u in users]
            if self.current_user_id not in user_ids:
                self.register_current_user()
            
            logger.info(f"CocoroProductWrapper初期化完了: ユーザー={self.current_user_id}")
            
        except Exception as e:
            logger.error(f"CocoroProductWrapper初期化エラー: {e}")
            raise
    
    def register_current_user(self):
        """現在のキャラクターをユーザーとして登録"""
        try:
            current_character = self.cocoro_config.current_character
            if not current_character:
                raise ValueError("現在のキャラクターが設定されていません")
            
            # ユーザー登録
            self.mos_product.user_register(
                user_id=self.current_user_id,
                user_name=current_character.modelName,
                config=get_mos_config(self.cocoro_config)
            )
            
            logger.info(f"ユーザー登録完了: {self.current_user_id} ({current_character.modelName})")
            
        except Exception as e:
            logger.error(f"ユーザー登録エラー: {e}")
            raise
    
    async def chat_with_references(
        self,
        query: str,
        user_id: Optional[str] = None,
        cube_id: Optional[str] = None,
        history: Optional[List] = None,
        internet_search: bool = False
    ) -> AsyncIterator[str]:
        """
        完全自動記憶管理付きストリーミングチャット
        
        Args:
            query: ユーザークエリ
            user_id: ユーザーID（省略時は現在のユーザー）
            cube_id: メモリキューブID（省略時はデフォルト）
            history: 会話履歴
            internet_search: インターネット検索を有効にするか
            
        Yields:
            str: ストリーミングレスポンス
        """
        if user_id is None:
            user_id = self.current_user_id
        
        try:
            # MOSProduct.chat_with_references による完全自動処理
            async for chunk in self.mos_product.chat_with_references(
                query=query,
                user_id=user_id,
                cube_id=cube_id,
                history=history,
                internet_search=internet_search and self.cocoro_config.enable_internet_retrieval
            ):
                yield chunk
                
        except Exception as e:
            logger.error(f"チャット処理エラー: {e}")
            raise
    
    def get_user_list(self) -> List[Dict]:
        """ユーザーリスト取得"""
        try:
            return self.mos_product.list_users()
        except Exception as e:
            logger.error(f"ユーザーリスト取得エラー: {e}")
            raise
    
    def get_user_info(self, user_id: str) -> Dict:
        """ユーザー情報取得"""
        try:
            return self.mos_product.get_user_info(user_id)
        except Exception as e:
            logger.error(f"ユーザー情報取得エラー: {e}")
            raise
    
    def get_memory_stats(self, user_id: str) -> Dict:
        """記憶統計取得"""
        try:
            # 記憶統計を取得
            all_memories = self.mos_product.get_all(user_id=user_id)
            
            stats = {
                "total_memories": len(all_memories),
                "memory_types": {},
                "cube_stats": {}
            }
            
            # メモリタイプ別統計
            for mem in all_memories:
                mem_type = mem.get("memory_type", "unknown")
                stats["memory_types"][mem_type] = stats["memory_types"].get(mem_type, 0) + 1
                
                # キューブ別統計
                cube_id = mem.get("mem_cube_id", "default")
                stats["cube_stats"][cube_id] = stats["cube_stats"].get(cube_id, 0) + 1
            
            return stats
            
        except Exception as e:
            logger.error(f"記憶統計取得エラー: {e}")
            raise
    
    def delete_all_memories(self, user_id: str) -> bool:
        """ユーザーの全記憶削除"""
        try:
            # ユーザーのメモリキューブを取得
            user_info = self.mos_product.get_user_info(user_id)
            accessible_cubes = user_info.get("accessible_cubes", [])
            
            # 各キューブの記憶を削除
            for cube_id in accessible_cubes:
                try:
                    # キューブ内の記憶をクリア
                    cube = self.mos_product.user_instances.get(user_id, {}).get("mem_cubes", {}).get(cube_id)
                    if cube:
                        cube.clear_all_memories()
                        logger.info(f"メモリキューブ {cube_id} の記憶をクリアしました")
                except Exception as e:
                    logger.warning(f"メモリキューブ {cube_id} のクリアに失敗: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"全記憶削除エラー: {e}")
            raise
    
    def get_system_prompt(self) -> Optional[str]:
        """システムプロンプトを取得"""
        if self.system_prompt_path and self.system_prompt_path.exists():
            try:
                with open(self.system_prompt_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"システムプロンプト読み込みエラー: {e}")
        return None
    
    async def shutdown(self):
        """シャットダウン処理 - MemOS公式手順に従った適切なクリーンアップ（非同期）"""
        try:
            logger.info("CocoroProductWrapperシャットダウン開始")
            
            # MemOS公式シャットダウン手順（非同期実行）
            # メモリスケジューラー停止
            if hasattr(self.mos_product, 'mem_scheduler_off'):
                logger.info("メモリスケジューラーを停止中...")
                # エグゼキューターで非同期実行
                success = await asyncio.get_event_loop().run_in_executor(
                    None, self.mos_product.mem_scheduler_off
                )
                if success:
                    logger.info("メモリスケジューラー停止完了")
                else:
                    logger.warning("メモリスケジューラー停止に失敗")
            
            # メモリ再編成機能停止
            if hasattr(self.mos_product, 'mem_reorganizer_off'):
                logger.info("メモリ再編成機能を停止中...")
                # エグゼキューターで非同期実行
                await asyncio.get_event_loop().run_in_executor(
                    None, self.mos_product.mem_reorganizer_off
                )
                logger.info("メモリ再編成機能停止完了")
            
            logger.info("CocoroProductWrapperシャットダウン完了")
            
        except Exception as e:
            logger.error(f"シャットダウンエラー: {e}")
            # エラーが発生してもプロセス終了を阻害しない