"""
CocoroCoreM MOSProduct統合ラッパー

MemOS MOSProductのラッパークラス実装
"""

import asyncio
import logging
import os
import re
from typing import AsyncIterator, Dict, List, Optional
from pathlib import Path

# MemOSインポート前にMOS_CUBE_PATH環境変数を設定（重要）
def _setup_mos_cube_path():
    """MemOSのCUBE_PATHを設定（絶対パス使用でMemOS内部処理を確実に）"""
    # プロジェクトルートからの絶対パス計算
    project_root = Path.cwd()  # main.pyで作業ディレクトリをCocoroAIに設定済み
    cubes_dir = project_root / "UserDataM" / "Memory" / "cubes"
    cubes_dir.mkdir(parents=True, exist_ok=True)
    
    # MemOSには絶対パスを設定（内部処理を確実に）
    absolute_cubes_path = str(cubes_dir)
    os.environ["MOS_CUBE_PATH"] = absolute_cubes_path
    
    return absolute_cubes_path

# MemOSインポート前にパス設定を実行
_cube_path = _setup_mos_cube_path()

from memos.mem_os.product import MOSProduct
from memos import GeneralMemCube
from memos.configs.mem_cube import GeneralMemCubeConfig

from .config_manager import CocoroAIConfig, generate_memos_config_from_setting, get_mos_config
from .cocoro_mos_product import CocoroMOSProduct

logger = logging.getLogger(__name__)


class CocoroProductWrapper:
    """MOSProductのラッパークラス"""
    
    def __init__(self, cocoro_config: CocoroAIConfig):
        """
        初期化
        
        Args:
            cocoro_config: CocoroAI設定オブジェクト
        """
        self.cocoro_config = cocoro_config
        self.logger = logger
        
        # MOSConfig動的生成（確証：config.py実装済み）
        # 相対パス使用でフォルダ移動に対応
        mos_config = get_mos_config(cocoro_config, use_relative_paths=True)
        
        logger.info(f"MOS_CUBE_PATH設定: {_cube_path}")
        
        # LiteLLM設定取得（常に使用）
        current_character = cocoro_config.current_character
        litellm_config = None
        
        if current_character:
            # APIキー決定（専用キーがあれば使用、なければ既存のapiKeyを使用）
            api_key = getattr(current_character, 'liteLLMApiKey', '') or current_character.apiKey
            
            litellm_config = {
                'model': getattr(current_character, 'liteLLMModel', 'gpt-4o-mini'),
                'api_key': api_key,
                'max_tokens': 1024,
                'extra_config': getattr(current_character, 'liteLLMConfig', {})
            }
            
            logger.info(f"🎯 LiteLLM設定: model={litellm_config['model']}")
        
        # CocoroMOSProduct初期化（CocoroAI専用システムプロンプト対応 + LiteLLM統合）
        self.mos_product = CocoroMOSProduct(
            default_config=mos_config,
            max_user_instances=1,  # シングルユーザー
            system_prompt_provider=self.get_system_prompt,  # CocoroAIシステムプロンプト取得関数を渡す
            litellm_config=litellm_config  # LiteLLM設定辞書
        )
        
        # 画像・メッセージ生成器は後で初期化（循環参照回避）
        self.image_analyzer = None
        self.message_generator = None
        
        # 現在のユーザーID（MemOSのuser_idパラメータ用）
        current_character = cocoro_config.current_character
        if not current_character or not current_character.memoryId:
            raise RuntimeError("キャラクターのmemoryIdが設定されていません")
        self.current_user_id = current_character.memoryId
        
        # 現在のキャラクターのキューブID（起動時に確定）
        self.current_cube_id: str = ""
        
        # システムプロンプトのパスを取得
        self.system_prompt_path = None
        current_character = cocoro_config.current_character
        if current_character and current_character.systemPromptFilePath:
            # UserDataM/SystemPromptsディレクトリからUUID部分でマッチング
            user_data_dir = self._get_user_data_directory()
            self.system_prompt_path = self._find_system_prompt_file(
                user_data_dir / "SystemPrompts", 
                current_character.systemPromptFilePath
            )
    
    def _get_user_data_directory(self) -> Path:
        """UserDataMディレクトリを取得（config_manager.pyと同じロジック）"""
        base_dir = Path(__file__).parent.parent
        user_data_paths = [
            base_dir.parent / "UserDataM",  # CocoroCoreM/../UserDataM/
            base_dir.parent.parent / "UserDataM",  # CocoroAI/UserDataM/
        ]
        
        for path in user_data_paths:
            if path.exists():
                return path
        
        # デフォルトは一つ上のディレクトリに作成
        return base_dir.parent / "UserDataM"
    
    def _extract_uuid_from_filename(self, filename: str) -> Optional[str]:
        """
        ファイル名からUUID部分を抽出
        
        Args:
            filename: ファイル名（例: "つくよみちゃん_50e3ba63-f0f1-ecd4-5a54-3812ac2cc863.txt"）
            
        Returns:
            str: UUID部分（例: "50e3ba63-f0f1-ecd4-5a54-3812ac2cc863"）またはNone
        """
        # UUID パターン: 8-4-4-4-12 文字のハイフン区切り
        uuid_pattern = r'([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})'
        match = re.search(uuid_pattern, filename)
        return match.group(1) if match else None
    
    def _find_system_prompt_file(self, prompts_dir: Path, target_filename: str) -> Optional[Path]:
        """
        UUID部分でマッチするシステムプロンプトファイルを検索
        
        Args:
            prompts_dir: SystemPromptsディレクトリのパス
            target_filename: 設定ファイルで指定されたファイル名
            
        Returns:
            Path: マッチしたファイルのパスまたはNone
        """
        if not prompts_dir.exists():
            logger.warning(f"SystemPromptsディレクトリが存在しません: {prompts_dir}")
            return None
        
        # 設定ファイルのファイル名からUUIDを抽出
        target_uuid = self._extract_uuid_from_filename(target_filename)
        if not target_uuid:
            logger.warning(f"設定ファイル名からUUIDを抽出できませんでした: {target_filename}")
            # フォールバック: 元のファイル名で直接検索
            fallback_path = prompts_dir / target_filename
            if fallback_path.exists():
                logger.info(f"フォールバック: 直接ファイル名でマッチしました: {fallback_path}")
                return fallback_path
            return None
        
        # SystemPromptsディレクトリ内の全.txtファイルを検索
        for file_path in prompts_dir.glob("*.txt"):
            file_uuid = self._extract_uuid_from_filename(file_path.name)
            if file_uuid and file_uuid.lower() == target_uuid.lower():
                logger.info(f"UUID部分でマッチしたファイルを発見: {file_path}")
                return file_path
        
        logger.warning(f"UUID '{target_uuid}' にマッチするファイルが見つかりませんでした")
        return None
    
    async def initialize(self):
        """非同期初期化処理"""
        try:
            # ユーザーが未登録の場合は登録
            users = self.mos_product.list_users() # キャラクター固有のユーザーIDを確認
            # usersはUserオブジェクトのリストなので属性でアクセス
            user_ids = [u.user_id if hasattr(u, 'user_id') else str(u) for u in users]
            if self.current_user_id not in user_ids:
                self.register_current_user()
            
            # 現在のキャラクターのMemCubeを作成・設定
            self._setup_current_character_cube()
            
            # トークナイザーを無効化して文字ベースチャンクに切り替え（パフォーマンス最適化）
            if hasattr(self.mos_product, 'tokenizer'):
                logger.info(f"トークナイザーを無効化（パフォーマンス最適化）: {self.mos_product.tokenizer is not None}")
                self.mos_product.tokenizer = None
                logger.info("文字ベースチャンクに切り替え完了")
            
            logger.info(f"CocoroProductWrapper初期化完了: ユーザー={self.current_user_id}")
            
        except Exception as e:
            logger.error(f"CocoroProductWrapper初期化エラー: {e}")
            raise
    
    def _setup_current_character_cube(self):
        """現在のキャラクターのMemCubeを作成・設定（起動時1回のみ）"""
        # 現在のキャラクター情報を確認
        current_character = self.cocoro_config.current_character
        if not current_character:
            raise RuntimeError("現在のキャラクターが設定されていません")
        
        if not current_character.memoryId:
            raise RuntimeError(f"キャラクター '{current_character.modelName}' のmemoryIdが設定されていません")
        
        # キューブIDを生成・設定（MOSProduct標準命名規則）
        self.current_cube_id = f"{current_character.memoryId}_{current_character.memoryId}_cube"
        
        # 既存のキューブリストを取得
        existing_cubes = self.mos_product.user_manager.get_user_cubes(self.current_user_id)
        existing_cube = None
        for cube in existing_cubes:
            cube_id = getattr(cube, 'cube_id', str(cube))
            if cube_id == self.current_cube_id:
                existing_cube = cube
                break
        
        if existing_cube and getattr(existing_cube, 'cube_path', None) is not None:
            # 既存キューブを使用（cube_pathが有効な場合のみ）
            # ただし、MemOSのuser_cube_associationテーブルで権限を再確認
            try:
                # キューブへの登録を強制実行（権限が正しく設定されるように）
                memory_types = ["text_mem"]
                if self.cocoro_config.enable_activation_memory:
                    memory_types.append("act_mem")
                
                # 既存キューブパスを絶対パスに変換（MemOS処理確実性のため）
                existing_path = existing_cube.cube_path
                if existing_path and not Path(existing_path).is_absolute():
                    # 相対パスの場合は絶対パスに変換
                    existing_absolute_path = str(Path.cwd() / existing_path)
                else:
                    existing_absolute_path = existing_path
                
                # MemOSの内部権限システムで正しく関連付けられるように再登録
                self.mos_product.register_mem_cube(
                    mem_cube_name_or_path_or_object=existing_absolute_path,
                    mem_cube_id=self.current_cube_id,
                    user_id=self.current_user_id,
                    memory_types=memory_types,
                    default_config=None
                )
                logger.info(f"既存キューブを再登録して使用: {self.current_cube_id} (キャラクター: {current_character.modelName})")
            except Exception as re_register_error:
                logger.warning(f"既存キューブの再登録に失敗、新規作成します: {re_register_error}")
                self._create_cube(current_character)
        else:
            # 新規作成またはcube_pathがNoneの場合は再作成
            if existing_cube:
                logger.warning(f"既存キューブのcube_pathがNullのため再作成: {self.current_cube_id}")
            else:
                logger.info(f"新規キューブを作成: {self.current_cube_id} (キャラクター: {current_character.modelName})")
            self._create_cube(current_character)
    
    def _create_cube(self, character):
        """キューブ作成処理"""
        cube_name = f"{character.memoryId}_cube"
        
        # プロジェクトルートからの絶対パス計算
        project_root = Path.cwd()
        cube_path_dir = project_root / "UserDataM" / "Memory" / "cubes" / self.current_cube_id
        cube_path_dir.mkdir(parents=True, exist_ok=True)
        
        # MemOS用絶対パス（内部処理を確実に）
        cube_absolute_path = str(cube_path_dir)
        
        # データベース保存用相対パス（ポータビリティ確保）
        cube_relative_path = f"UserDataM/Memory/cubes/{self.current_cube_id}"
        
        # 1. データベースにキューブレコードを作成（相対パスで保存）
        created_cube_id = self.mos_product.create_cube_for_user(
            cube_name=cube_name,
            owner_id=self.current_user_id,
            cube_id=self.current_cube_id,
            cube_path=cube_relative_path  # データベースには相対パス保存
        )
        
        # 2. MemOS標準フローに従ったキューブ初期化
        
        # 現在のキャラクター設定からAPIキーを取得
        current_character = self.cocoro_config.current_character
        api_key = current_character.apiKey if current_character and current_character.apiKey else ""
        
        # 最小限のconfig.jsonを作成（MemOSの標準フロー）
        import json
        
        # Neo4j設定を取得（Community Edition対応）
        # 設定ファイルから動的にポート番号を取得
        neo4j_port = self.cocoro_config.cocoroMemoryDBPort
        neo4j_config = {
            "uri": f"bolt://localhost:{neo4j_port}",
            "user": "neo4j", 
            "password": "password",
            "db_name": "neo4j",
            "use_multi_db": False,  # Community Editionでは必須
            "user_name": self.current_user_id,  # キャラクター別論理的分離
            "auto_create": False,
            "embedding_dimension": 1536  # text-embedding-3-small の次元
        }
        
        config_data = {
            "model_schema": "memos.configs.mem_cube.GeneralMemCubeConfig",
            "user_id": self.current_user_id,
            "cube_id": self.current_cube_id,
            "text_mem": {
                "backend": "tree_text",
                "config": {
                    "cube_id": self.current_cube_id,
                    "extractor_llm": {
                        "backend": "openai",
                        "config": {
                            "model_name_or_path": "gpt-4o-mini",
                            "api_key": api_key,
                            "api_base": "https://api.openai.com/v1"
                        }
                    },
                    "dispatcher_llm": {
                        "backend": "openai", 
                        "config": {
                            "model_name_or_path": "gpt-4o-mini",
                            "api_key": api_key,
                            "api_base": "https://api.openai.com/v1"
                        }
                    },
                    "graph_db": {
                        "backend": "neo4j",
                        "config": neo4j_config
                    },
                    "embedder": {
                        "backend": "universal_api",
                        "config": {
                            "model_name_or_path": "text-embedding-3-small",
                            "provider": "openai",
                            "api_key": api_key,
                            "base_url": "https://api.openai.com/v1"
                        }
                    }
                }
            },
            "act_mem": {
                "backend": "uninitialized",
                "config": {}
            },
            "para_mem": {
                "backend": "uninitialized", 
                "config": {}
            }
        }
        
        config_file_path = cube_path_dir / "config.json"
        with open(config_file_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
        
        # 3. MemOS標準メカニズムでキューブを登録（パス指定）
        memory_types = ["text_mem"]
        if self.cocoro_config.enable_activation_memory:
            memory_types.append("act_mem")
        
        # MemOSの標準フローに従い、絶対パス指定でregister_mem_cube
        # init_from_dirが自動実行され、text_memが適切に初期化される
        self.mos_product.register_mem_cube(
            mem_cube_name_or_path_or_object=cube_absolute_path,  # 絶対パスで確実に処理
            mem_cube_id=self.current_cube_id,
            user_id=self.current_user_id,
            memory_types=memory_types,
            default_config=None
        )
        
        logger.info(f"キューブ作成完了: {self.current_cube_id}")
    
    def get_current_cube_id(self) -> str:
        """現在のキューブIDを取得"""
        return self.current_cube_id
    
    def register_current_user(self):
        """ユーザーを登録"""
        try:
            # キャラクター別ユーザー登録
            current_character = self.cocoro_config.current_character
            self.mos_product.user_register(
                user_id=self.current_user_id,
                user_name=self.current_user_id,  # ユーザーIDと同じ値を使用
                config=get_mos_config(self.cocoro_config, use_relative_paths=True)
            )
            
            logger.info(f"ユーザー登録完了: {self.current_user_id}")
            
        except Exception as e:
            logger.error(f"ユーザー登録エラー: {e}")
            raise
    
    async def chat_with_references(
        self,
        query: str,
        cube_id: str, # CocoroAIではキャラクター指定のために必須
        user_id: Optional[str] = None,
        history: Optional[List] = None,
        internet_search: bool = False
    ) -> AsyncIterator[str]:
        """
        完全自動記憶管理付きストリーミングチャット
        - ストリーミング終了シグナル（"type": "end"）を検出したら即時に終了
        - MemOSの記憶保存処理（約2秒）を待たずに応答を返す
        - 記憶保存はMemOS内部で非同期に継続される
        - 会話履歴はMemOSの自動履歴管理(user_chat_histories)を使用
        
        Args:
            query: ユーザークエリ
            cube_id: メモリキューブID
            user_id: ユーザーID（省略時は現在のユーザー）
            history: 会話履歴（注意: このパラメータは無視され、MemOSの自動管理が使用される）
            internet_search: インターネット検索を有効にするか
            
        Yields:
            str: ストリーミングレスポンス
        """
        if user_id is None:
            user_id = self.current_user_id
        
        try:
            # CocoroMOSProduct.chat_with_referencesによる非同期記憶保存処理
            # 記憶保存はバックグラウンドで実行され、レスポンス遅延なし
            # 注意: historyパラメータは無視し、MemOSの自動履歴管理(user_chat_histories)を使用
            for chunk in self.mos_product.chat_with_references(
                query=query,
                user_id=user_id,
                cube_id=cube_id,
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
    
    def get_character_list(self) -> List[Dict]:
        """キャラクター（キューブ）一覧取得 - 記憶を持つ全MemoryIDを返す"""
        try:
            # MOSProductから記憶を持つ全ユーザー（MemoryID）を取得
            users = self.mos_product.list_users()
            
            characters = []
            for user in users:
                # ユーザーIDを取得（Userオブジェクトの場合はuser_id属性、文字列の場合はそのまま）
                user_id = user.user_id if hasattr(user, 'user_id') else str(user)
                
                # rootユーザーは除外
                if user_id == "root":
                    continue
                
                # MemoryIDとして使用（記憶管理でキャラクター名ではなくMemoryIDを表示）
                characters.append({
                    "memory_id": user_id,
                    "memory_name": user_id,  # MemoryIDをそのまま名前として使用
                    "role": "character", 
                    "created": True
                })
            
            logger.info(f"記憶を持つMemoryID一覧取得: {len(characters)}件")
            return characters
            
        except Exception as e:
            logger.error(f"キャラクター一覧取得エラー: {e}")
            raise


    def delete_character_memories(self, memory_id: str) -> None:
        """特定キャラクターの完全削除（記憶データ + 設定ファイル + SQLiteレコード + default_cube含む全キューブ）"""
        try:
            # user_idはmemory_idと同じ
            user_id = memory_id
            
            # 該当ユーザーの全キューブを取得
            user_cubes = self.mos_product.user_manager.get_user_cubes(user_id)
            deleted_cubes = []
            
            for cube in user_cubes:
                cube_id = getattr(cube, 'cube_id', str(cube))
                
                # MemOSの記憶削除（Neo4jから削除）
                try:
                    self.mos_product.delete_all(mem_cube_id=cube_id, user_id=user_id)
                    logger.info(f"Neo4jから記憶削除完了: {cube_id}")
                except Exception as neo4j_error:
                    if "does not exist" in str(neo4j_error) or "not found" in str(neo4j_error).lower():
                        logger.warning(f"キューブが既に存在しません: {cube_id} - 物理削除を続行")
                    else:
                        logger.error(f"Neo4j削除エラー({cube_id}): {neo4j_error}")
                        # Neo4jエラーでも物理削除は続行
                
                # キューブディレクトリとconfig.jsonファイルの物理削除
                self._delete_cube_files(cube_id)
                deleted_cubes.append(cube_id)
            
            # SQLiteデータベース（memos_users.db）からユーザー・全キューブレコードを完全削除
            self._delete_user_and_all_cubes_from_database(user_id)
            
            logger.info(f"キャラクター '{memory_id}' の完全削除完了: 削除キューブ={deleted_cubes}")
                
        except Exception as e:
            logger.error(f"キャラクター記憶削除エラー: {memory_id}, {e}")
            raise
    
    def _delete_cube_files(self, cube_id: str) -> None:
        """キューブのファイル・ディレクトリを物理削除"""
        import shutil
        
        try:
            user_data_dir = self._get_user_data_directory()
            cube_path = user_data_dir / "Memory" / "cubes" / cube_id
            
            if cube_path.exists():
                shutil.rmtree(cube_path)
                logger.info(f"キューブディレクトリ削除完了: {cube_path}")
            else:
                logger.warning(f"キューブディレクトリが見つかりません: {cube_path}")
                
        except Exception as e:
            logger.error(f"キューブファイル削除エラー: {cube_id}, {e}")
            raise
    
    def _delete_user_and_all_cubes_from_database(self, user_id: str) -> None:
        """SQLiteデータベースからユーザー・全キューブレコードを完全削除"""
        import sqlite3
        
        try:
            user_data_dir = self._get_user_data_directory()
            db_path = user_data_dir / "Memory" / "memos_users.db"
            
            if db_path.exists():
                with sqlite3.connect(str(db_path)) as conn:
                    # 該当ユーザーの全キューブを削除
                    conn.execute("DELETE FROM cubes WHERE owner_id = ?", (user_id,))
                    # user_cube_associationテーブルからも関連レコード削除
                    conn.execute("DELETE FROM user_cube_association WHERE user_id = ?", (user_id,))
                    # usersテーブルからユーザー削除（rootユーザーは除外）
                    conn.execute("DELETE FROM users WHERE user_id = ? AND user_id != 'root'", (user_id,))
                    # user_configsテーブルからユーザー設定削除
                    conn.execute("DELETE FROM user_configs WHERE user_id = ?", (user_id,))
                    conn.commit()
                    logger.info(f"SQLiteからユーザー・全キューブレコード完全削除完了: user_id={user_id}")
            else:
                logger.warning(f"SQLiteデータベースが見つかりません: {db_path}")
                
        except Exception as e:
            logger.error(f"SQLiteユーザー・全キューブレコード削除エラー: user_id={user_id}, {e}")
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