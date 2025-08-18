# CocoroCore2 メモリ管理API実装仕様書

## 実装概要

設計書 `MEMORY_API_DESIGN.md` に基づき、キャラクター別記憶管理APIの具体的な実装手順を定義します。

## 実装ファイル一覧

### 修正対象ファイル
- `src/core/cocoro_product.py` - 新しい内部APIメソッド追加
- `src/models/api_models.py` - レスポンスモデル拡張
- `src/main.py` - ルーター追加

### 新規作成ファイル  
- `src/api/memory.py` - メモリ管理APIルーター

## 実装手順

### Step 1: 内部API拡張（CocoroProductWrapper）

**ファイル**: `src/core/cocoro_product.py`

**追加内容** (ファイル末尾、`get_system_prompt()`メソッドの前に追加):

```python
    def get_character_list(self) -> List[Dict]:
        """キャラクター（キューブ）一覧取得"""
        try:
            # ユーザー情報からアクセス可能なキューブを取得
            user_info = self.mos_product.get_user_info("user")
            accessible_cubes = user_info.get("accessible_cubes", [])
            
            characters = []
            for cube_id in accessible_cubes:
                # キューブIDからmemoryIdを抽出
                # "user_user_{memoryId}_cube" → memoryId
                if cube_id.startswith("user_user_") and cube_id.endswith("_cube"):
                    memory_id = cube_id[10:-5]  # "user_user_"と"_cube"を除去
                    
                    characters.append({
                        "memory_id": memory_id,
                        "memory_name": memory_id.capitalize(),  # 基本的な大文字化
                        "role": "character", 
                        "created": True
                    })
            
            logger.info(f"キャラクター一覧取得: {len(characters)}件")
            return characters
            
        except Exception as e:
            logger.error(f"キャラクター一覧取得エラー: {e}")
            raise

    def get_character_memory_stats(self, memory_id: str) -> Dict:
        """特定キャラクターの記憶統計取得"""
        try:
            # キューブIDを生成
            cube_id = f"user_user_{memory_id}_cube"
            
            # 全記憶を取得してキューブ別にフィルタリング
            all_memories = self.mos_product.get_all(user_id="user")
            
            # 特定のキューブの記憶のみをフィルタリング
            cube_memories = [mem for mem in all_memories 
                            if mem.get("mem_cube_id") == cube_id]
            
            # 記憶タイプ別統計計算
            text_memories = len([m for m in cube_memories 
                               if m.get("memory_type") == "PersonalMemory"])
            activation_memories = len([m for m in cube_memories 
                                     if m.get("memory_type") == "ActivationMemory"])
            parametric_memories = len([m for m in cube_memories 
                                     if m.get("memory_type") == "ParametricMemory"])
            
            # 最終更新日時を取得（最新の記憶から）
            last_updated = None
            if cube_memories:
                # 記憶リストから最新のタイムスタンプを取得
                timestamps = []
                for mem in cube_memories:
                    if hasattr(mem, 'timestamp') and mem.timestamp:
                        timestamps.append(mem.timestamp)
                    elif hasattr(mem, 'created_at') and mem.created_at:
                        timestamps.append(mem.created_at)
                
                if timestamps:
                    last_updated = max(timestamps)
            
            stats = {
                "total_memories": len(cube_memories),
                "text_memories": text_memories,
                "activation_memories": activation_memories,
                "parametric_memories": parametric_memories,
                "last_updated": last_updated,
                "cube_id": cube_id
            }
            
            logger.info(f"キャラクター記憶統計取得: {memory_id}, 総数: {stats['total_memories']}")
            return stats
            
        except Exception as e:
            logger.error(f"キャラクター記憶統計取得エラー: {memory_id}, {e}")
            raise

    def delete_character_memories(self, memory_id: str) -> Dict:
        """特定キャラクターの記憶削除"""
        try:
            # キューブIDを生成
            cube_id = f"user_user_{memory_id}_cube"
            
            # 削除前の統計を取得
            stats_before = self.get_character_memory_stats(memory_id)
            
            # 特定のキューブの記憶をクリア
            cube = self.mos_product.user_instances.get("user", {}).get("mem_cubes", {}).get(cube_id)
            if cube:
                cube.clear_all_memories()
                logger.info(f"キャラクター '{memory_id}' のメモリキューブ {cube_id} の記憶をクリアしました")
                
                # 削除結果を返す
                return {
                    "success": True,
                    "deleted_count": stats_before["total_memories"],
                    "details": {
                        "text_memories": stats_before["text_memories"],
                        "activation_memories": stats_before["activation_memories"],
                        "parametric_memories": stats_before["parametric_memories"]
                    }
                }
            else:
                logger.warning(f"キャラクター '{memory_id}' のメモリキューブが見つかりません: {cube_id}")
                raise ValueError(f"キャラクター '{memory_id}' のメモリキューブが見つかりません")
                
        except Exception as e:
            logger.error(f"キャラクター記憶削除エラー: {memory_id}, {e}")
            raise
```

### Step 2: APIレスポンスモデル拡張

**ファイル**: `src/models/api_models.py`

**追加内容** (ファイル末尾に追加):

```python
# ===========================================
# キャラクター別メモリ管理API用モデル定義
# ===========================================

class CharacterMemoryInfo(BaseModel):
    """キャラクターメモリ情報"""
    memory_id: str = Field(..., description="メモリID（キャラクターのmemoryId）")  
    memory_name: str = Field(..., description="キャラクター名")
    role: str = Field("character", description="役割（character固定）")
    created: bool = Field(True, description="作成状態")


class CharacterListResponse(BaseModel):
    """キャラクター一覧レスポンス - CocoroDock互換"""
    status: str = Field("success", description="ステータス")
    message: str = Field("キャラクター一覧を取得しました", description="メッセージ")
    data: List[CharacterMemoryInfo] = Field(default_factory=list, description="キャラクター一覧")


class CharacterMemoryStatsResponse(BaseModel):
    """キャラクター記憶統計レスポンス - CocoroDock互換"""
    memory_id: str = Field(..., description="メモリID")
    total_memories: int = Field(0, description="総記憶数")
    text_memories: int = Field(0, description="テキスト記憶数") 
    activation_memories: int = Field(0, description="アクティベーション記憶数")
    parametric_memories: int = Field(0, description="パラメトリック記憶数")
    last_updated: Optional[datetime] = Field(None, description="最終更新日時")
    cube_id: str = Field("", description="キューブID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="取得時刻")


class CharacterMemoryDeleteResponse(BaseModel):
    """キャラクター記憶削除レスポンス - CocoroDock互換"""
    status: str = Field("success", description="ステータス")
    message: str = Field("記憶を削除しました", description="メッセージ")
    deleted_count: int = Field(0, description="削除された記憶総数")
    details: MemoryDeleteDetails = Field(default_factory=MemoryDeleteDetails, description="削除詳細")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="削除時刻")
```

### Step 3: メモリAPI実装

**ファイル**: `src/api/memory.py` (新規作成)

**完全な実装コード**:

```python
"""
CocoroCore2 メモリ管理API

MemOS統合メモリ管理機能へのREST APIインターフェース
キャラクター別記憶管理に対応（CocoroDock互換）
"""

import logging
from typing import Dict, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import JSONResponse

from models.api_models import (
    CharacterListResponse,
    CharacterMemoryInfo,
    CharacterMemoryStatsResponse,
    CharacterMemoryDeleteResponse,
    MemoryDeleteDetails,
    ErrorResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["memory"])

# グローバルアプリケーションインスタンス（既存パターン準拠）
_app_instance = None


def get_core_app():
    """CoreAppの依存性注入 - 遅延初期化対応"""
    global _app_instance
    if _app_instance is None:
        from main import get_app_instance
        _app_instance = get_app_instance()
    return _app_instance


def _convert_character_list_to_response(characters_data: List[Dict]) -> CharacterListResponse:
    """内部キャラクターリストデータを外部APIレスポンスに変換"""
    character_infos = []
    
    for char in characters_data:
        character_infos.append(CharacterMemoryInfo(
            memory_id=char.get("memory_id", ""),
            memory_name=char.get("memory_name", char.get("memory_id", "")),
            role=char.get("role", "character"),
            created=char.get("created", True)
        ))
    
    return CharacterListResponse(data=character_infos)


def _convert_character_stats_to_response(stats_data: Dict, memory_id: str) -> CharacterMemoryStatsResponse:
    """内部統計データを外部APIレスポンスに変換"""
    return CharacterMemoryStatsResponse(
        memory_id=memory_id,
        total_memories=stats_data.get("total_memories", 0),
        text_memories=stats_data.get("text_memories", 0),
        activation_memories=stats_data.get("activation_memories", 0),
        parametric_memories=stats_data.get("parametric_memories", 0),
        last_updated=stats_data.get("last_updated"),
        cube_id=stats_data.get("cube_id", ""),
        timestamp=datetime.utcnow()
    )


def _convert_character_delete_result_to_response(delete_result: Dict, memory_id: str) -> CharacterMemoryDeleteResponse:
    """削除結果データを削除レスポンスに変換"""
    details = MemoryDeleteDetails(
        text_memories=delete_result.get("details", {}).get("text_memories", 0),
        activation_memories=delete_result.get("details", {}).get("activation_memories", 0),
        parametric_memories=delete_result.get("details", {}).get("parametric_memories", 0)
    )
    
    return CharacterMemoryDeleteResponse(
        status="success",
        message="記憶を削除しました",
        deleted_count=delete_result.get("deleted_count", 0),
        details=details,
        timestamp=datetime.utcnow()
    )


@router.get("/memory/characters", response_model=CharacterListResponse)
async def get_memory_characters(app=Depends(get_core_app)):
    """
    キャラクター一覧取得
    
    CocoroDockからの記憶管理対象キャラクター一覧を取得
    
    Returns:
        CharacterListResponse: キャラクター一覧
    """
    try:
        logger.debug("キャラクター一覧取得開始")
        
        # CocoroProductWrapperから内部キャラクターリストを取得
        characters_data = app.product_wrapper.get_character_list()
        
        # 外部APIレスポンス形式に変換
        response = _convert_character_list_to_response(characters_data)
        
        logger.info(f"キャラクター一覧取得成功: {len(response.data)}件")
        return response
        
    except Exception as e:
        logger.error(f"キャラクター一覧取得エラー: {e}")
        error_response = ErrorResponse(
            error="character_list_failed",
            message="キャラクター一覧の取得に失敗しました",
            details={"error": str(e)}
        )
        return JSONResponse(status_code=500, content=error_response.dict())


@router.get("/memory/character/{memory_id}/stats", response_model=CharacterMemoryStatsResponse)
async def get_character_memory_stats(
    memory_id: str = Path(..., description="キャラクターのメモリID"),
    app=Depends(get_core_app)
):
    """
    キャラクター記憶統計情報取得
    
    指定されたキャラクター（メモリID）の記憶統計情報を取得
    
    Args:
        memory_id: 統計取得対象のキャラクターメモリID
        
    Returns:
        CharacterMemoryStatsResponse: キャラクター記憶統計情報
    """
    try:
        logger.debug(f"キャラクター記憶統計取得開始: {memory_id}")
        
        # CocoroProductWrapperから統計データを取得
        stats_data = app.product_wrapper.get_character_memory_stats(memory_id)
        
        # 外部APIレスポンス形式に変換
        response = _convert_character_stats_to_response(stats_data, memory_id)
        
        logger.info(f"キャラクター記憶統計取得成功: {memory_id}, 総記憶数: {response.total_memories}")
        return response
        
    except Exception as e:
        logger.error(f"キャラクター記憶統計取得エラー: {memory_id}, {e}")
        
        # 特殊ケース: キャラクターが存在しない場合は空の統計を返す（CocoroDock互換）
        if "not found" in str(e).lower() or "見つかりません" in str(e) or "存在しない" in str(e):
            logger.info(f"キャラクターが存在しないため空の統計を返します: {memory_id}")
            empty_stats = CharacterMemoryStatsResponse(
                memory_id=memory_id,
                cube_id=f"user_user_{memory_id}_cube"
            )
            return empty_stats
        
        error_response = ErrorResponse(
            error="character_memory_stats_failed",
            message=f"キャラクター記憶統計の取得に失敗しました: {memory_id}",
            details={"memory_id": memory_id, "error": str(e)}
        )
        return JSONResponse(status_code=500, content=error_response.dict())


@router.delete("/memory/character/{memory_id}/all", response_model=CharacterMemoryDeleteResponse)
async def delete_character_memories(
    memory_id: str = Path(..., description="キャラクターのメモリID"),
    app=Depends(get_core_app)
):
    """
    キャラクターの全記憶削除
    
    指定されたキャラクター（メモリID）の全記憶を削除
    
    Args:
        memory_id: 削除対象のキャラクターメモリID
        
    Returns:
        CharacterMemoryDeleteResponse: 削除結果
    """
    try:
        logger.info(f"キャラクター全記憶削除開始: {memory_id}")
        
        # CocoroProductWrapperで記憶削除実行
        delete_result = app.product_wrapper.delete_character_memories(memory_id)
        
        # 削除結果レスポンス生成
        response = _convert_character_delete_result_to_response(delete_result, memory_id)
        
        logger.info(f"キャラクター全記憶削除成功: {memory_id}, 削除数: {response.deleted_count}")
        return response
        
    except Exception as e:
        logger.error(f"キャラクター全記憶削除エラー: {memory_id}, {e}")
        
        # 特殊ケース: キャラクターが存在しない場合
        if "not found" in str(e).lower() or "見つかりません" in str(e) or "存在しない" in str(e):
            error_response = ErrorResponse(
                error="character_not_found",
                message=f"キャラクターが見つかりません: {memory_id}",
                details={"memory_id": memory_id}
            )
            return JSONResponse(status_code=404, content=error_response.dict())
        
        error_response = ErrorResponse(
            error="character_memory_delete_failed",
            message=f"キャラクター記憶削除に失敗しました: {memory_id}",
            details={"memory_id": memory_id, "error": str(e)}
        )
        return JSONResponse(status_code=500, content=error_response.dict())
```

### Step 4: メインアプリケーションにルーター追加

**ファイル**: `src/main.py`

**変更箇所1**: インポート追加（146行目付近）
```python
from api.health import router as health_router
from api.control import router as control_router
from api.websocket_chat import router as websocket_router
from api.memory import router as memory_router  # 追加
```

**変更箇所2**: ルーター登録（220行目付近）
```python
# APIルーター追加
self.app.include_router(health_router)
self.app.include_router(control_router)
self.app.include_router(websocket_router)
self.app.include_router(memory_router)  # 追加
```

**変更箇所3**: インスタンス更新メソッド（166行目付近）
```python
def _update_router_instances(self):
    """各ルーターのグローバルインスタンスを更新"""
    try:
        # control.pyのインスタンス更新
        from api import control
        control._app_instance = self
        
        # memory.pyのインスタンス更新（追加）
        from api import memory
        memory._app_instance = self
        
        logger.debug("ルーターインスタンス更新完了")
        
    except ImportError as e:
        logger.warning(f"ルーターインスタンス更新で一部スキップ: {e}")
```

## テスト・検証方法

### 手動テスト手順

#### 1. APIサーバー起動確認
```bash
cd CocoroCore2
python -X utf8 src/main.py
```

起動ログでメモリルーターが正常に登録されることを確認:
```
INFO - APIルーター追加完了: health, control, websocket_chat, memory
```

#### 2. エンドポイント疎通確認

**キャラクター一覧取得**
```bash
curl -X GET "http://localhost:55601/api/memory/characters"
```

**キャラクター記憶統計取得** 
```bash
curl -X GET "http://localhost:55601/api/memory/character/listy/stats"
```

**キャラクター記憶削除（注意: 実際にデータが削除されます）**
```bash
curl -X DELETE "http://localhost:55601/api/memory/character/listy/all"
```

#### 3. CocoroDock連携テスト

1. CocoroCore2を起動
2. CocoroDockを起動  
3. CocoroDockの「システム設定」→「記憶管理」タブを開く
4. キャラクター一覧が表示されることを確認
5. 特定キャラクターの記憶統計が正常に表示されることを確認
6. 記憶削除機能が正常に動作することを確認

### 期待される動作

#### キャラクター一覧レスポンス例
```json
{
  "status": "success",
  "message": "キャラクター一覧を取得しました",
  "data": [
    {
      "memory_id": "listy",
      "memory_name": "Listy",
      "role": "character",
      "created": true
    }
  ]
}
```

#### キャラクター統計レスポンス例
```json
{
  "memory_id": "listy",
  "total_memories": 850,
  "text_memories": 600,
  "activation_memories": 150,
  "parametric_memories": 100,
  "last_updated": "2024-01-15T10:30:00Z",
  "cube_id": "user_user_listy_cube",
  "timestamp": "2024-01-15T10:35:00Z"
}
```

## エラーケーステスト

#### 存在しないキャラクターでのアクセス
```bash
curl -X GET "http://localhost:55601/api/memory/character/nonexistent/stats"
```
→ 空の統計が返されることを確認

#### CocoroCore2未起動状態でのCocoroDockアクセス
→ CocoroDockのエラーハンドリングが適切に動作することを確認

## 実装チェックリスト

### Phase 1: 内部API拡張
- [ ] `src/core/cocoro_product.py`に新メソッド追加
- [ ] 内部メソッドの動作確認（単体テスト）

### Phase 2: 外部API実装
- [ ] `src/models/api_models.py`にレスポンスモデル追加
- [ ] `src/api/memory.py`作成・実装
- [ ] `src/main.py`にルーター追加
- [ ] 基本動作確認（サーバー起動、エンドポイント疎通）

### Phase 3: 機能テスト
- [ ] キャラクター一覧取得API動作確認
- [ ] キャラクター記憶統計取得API動作確認  
- [ ] キャラクター記憶削除API動作確認
- [ ] エラーケース確認（存在しないキャラクター等）

### Phase 4: 統合テスト
- [ ] CocoroDockとの連携確認
- [ ] 記憶管理UI全機能動作確認
- [ ] エラーハンドリング確認
- [ ] パフォーマンス確認

---

この実装仕様書に従って段階的に実装することで、CocoroAIの実際のアーキテクチャに合致したキャラクター別記憶管理APIが完成します。