# CocoroCore2 メモリ管理API設計書

## 概要

CocoroCore2のMemOS統合システムに対する外部API（REST API）を実装し、CocoroDockからのキャラクター別記憶管理操作を可能にする。

## 実態分析（調査結果）

### CocoroAIの実際の構造

**シングルユーザー・マルチキャラクター**:
- ユーザーは1人固定（user_id = "user"）
- 複数のキャラクターが存在し、各キャラクターが独自のmemoryIdを持つ
- 各キャラクターが独自のメモリキューブを持つ

**キューブ命名規則**:
```
キューブID = f"user_user_{character.memoryId}_cube"

例:
- memoryId="listy" → キューブID="user_user_listy_cube"  
- memoryId="miku" → キューブID="user_user_miku_cube"
```

**CocoroDockの記憶管理UI**:
- 「キャラクター」選択として実装
- 特定のキャラクターの記憶統計表示・削除を行う

### 問題の根本原因

**既存の内部APIの問題**:
1. `get_user_list()` - "user"のみ返す（キャラクター一覧が必要）
2. `get_memory_stats(user_id)` - 全キューブ統計（特定キューブ統計が必要）
3. `delete_all_memories(user_id)` - 全キューブ削除（特定キューブ削除が必要）

**CocoroDockの期待**:
- キャラクター（キューブ）一覧取得
- 特定キャラクターの記憶統計取得  
- 特定キャラクターの記憶削除

## 修正されたAPI仕様

### エンドポイント定義

#### 1. キャラクター（メモリキューブ）一覧取得
```
GET /api/memory/characters
```
**レスポンス:**
```json
{
  "status": "success",
  "message": "キャラクター一覧を取得しました",
  "data": [
    {
      "memory_id": "listy",
      "memory_name": "リスティー", 
      "role": "character",
      "created": true
    },
    {
      "memory_id": "miku", 
      "memory_name": "初音ミク",
      "role": "character",
      "created": true
    }
  ]
}
```

#### 2. 特定キャラクターの記憶統計取得
```
GET /api/memory/character/{memory_id}/stats
```
**パス例**: `/api/memory/character/listy/stats`

**レスポンス:**
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

#### 3. 特定キャラクターの記憶削除
```
DELETE /api/memory/character/{memory_id}/all
```
**パス例**: `/api/memory/character/listy/all`

**レスポンス:**
```json
{
  "status": "success",
  "message": "記憶を削除しました",
  "deleted_count": 850,
  "details": {
    "text_memories": 600,
    "activation_memories": 150, 
    "parametric_memories": 100
  },
  "timestamp": "2024-01-15T10:40:00Z"
}
```

## 必要な内部API拡張

### CocoroProductWrapperに追加するメソッド

```python
def get_character_list(self) -> List[Dict]:
    """キャラクター（キューブ）一覧取得"""
    # ユーザー情報からアクセス可能なキューブ一覧を取得
    # 各キューブからmemoryIdを抽出してキャラクター情報を構築

def get_character_memory_stats(self, memory_id: str) -> Dict:
    """特定キャラクターの記憶統計取得"""
    # cube_id = f"user_user_{memory_id}_cube" を生成
    # 特定のキューブの記憶のみを統計

def delete_character_memories(self, memory_id: str) -> bool:
    """特定キャラクターの記憶削除"""
    # cube_id = f"user_user_{memory_id}_cube" を生成
    # 特定のキューブの記憶のみを削除
```

### 実装詳細

#### get_character_list() 実装方針
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
                    "memory_name": memory_id.capitalize(),  # とりあえず大文字化
                    "role": "character", 
                    "created": True
                })
        
        return characters
    except Exception as e:
        logger.error(f"キャラクター一覧取得エラー: {e}")
        raise
```

#### get_character_memory_stats() 実装方針
```python
def get_character_memory_stats(self, memory_id: str) -> Dict:
    """特定キャラクターの記憶統計取得"""
    try:
        # キューブIDを生成
        cube_id = f"user_user_{memory_id}_cube"
        
        # 特定のキューブの記憶のみを取得
        # MemOSのget_allにキューブフィルタリング機能があるかチェックが必要
        all_memories = self.mos_product.get_all(user_id="user")
        
        # 特定のキューブの記憶のみをフィルタリング
        cube_memories = [mem for mem in all_memories 
                        if mem.get("mem_cube_id") == cube_id]
        
        # 統計計算
        stats = {
            "total_memories": len(cube_memories),
            "text_memories": len([m for m in cube_memories if m.get("memory_type") == "PersonalMemory"]),
            "activation_memories": len([m for m in cube_memories if m.get("memory_type") == "ActivationMemory"]),
            "parametric_memories": len([m for m in cube_memories if m.get("memory_type") == "ParametricMemory"]),
            "cube_id": cube_id
        }
        
        return stats
    except Exception as e:
        logger.error(f"キャラクター記憶統計取得エラー: {e}")
        raise
```

#### delete_character_memories() 実装方針
```python
def delete_character_memories(self, memory_id: str) -> bool:
    """特定キャラクターの記憶削除"""
    try:
        # キューブIDを生成
        cube_id = f"user_user_{memory_id}_cube"
        
        # 特定のキューブの記憶をクリア
        cube = self.mos_product.user_instances.get("user", {}).get("mem_cubes", {}).get(cube_id)
        if cube:
            cube.clear_all_memories()
            logger.info(f"キャラクター '{memory_id}' のメモリキューブ {cube_id} の記憶をクリアしました")
            return True
        else:
            logger.warning(f"キャラクター '{memory_id}' のメモリキューブが見つかりません: {cube_id}")
            return False
            
    except Exception as e:
        logger.error(f"キャラクター記憶削除エラー: {e}")
        raise
```

## レスポンスモデル設計（修正版）

### CocoroDock互換レスポンスモデル

```python
class CharacterMemoryInfo(BaseModel):
    """キャラクターメモリ情報"""
    memory_id: str = Field(..., description="メモリID（キャラクターのmemoryId）")  
    memory_name: str = Field(..., description="キャラクター名")
    role: str = Field("character", description="役割（character固定）")
    created: bool = Field(True, description="作成状態")

class CharacterListResponse(BaseModel):
    """キャラクター一覧レスポンス"""
    status: str = Field("success", description="ステータス")
    message: str = Field("キャラクター一覧を取得しました", description="メッセージ")
    data: List[CharacterMemoryInfo] = Field(default_factory=list, description="キャラクター一覧")

class CharacterMemoryStatsResponse(BaseModel):
    """キャラクター記憶統計レスポンス"""
    memory_id: str = Field(..., description="メモリID")
    total_memories: int = Field(0, description="総記憶数")
    text_memories: int = Field(0, description="テキスト記憶数") 
    activation_memories: int = Field(0, description="アクティベーション記憶数")
    parametric_memories: int = Field(0, description="パラメトリック記憶数")
    last_updated: Optional[datetime] = Field(None, description="最終更新日時")
    cube_id: str = Field("", description="キューブID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="取得時刻")

class CharacterMemoryDeleteResponse(BaseModel):
    """キャラクター記憶削除レスポンス"""
    status: str = Field("success", description="ステータス")
    message: str = Field("記憶を削除しました", description="メッセージ")
    deleted_count: int = Field(0, description="削除された記憶総数")
    details: MemoryDeleteDetails = Field(default_factory=MemoryDeleteDetails, description="削除詳細")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="削除時刻")
```

## API実装方針

### APIルーター実装 (memory.py)

```python
@router.get("/memory/characters", response_model=CharacterListResponse)
async def get_memory_characters(app=Depends(get_core_app)):
    """キャラクター一覧取得"""
    
@router.get("/memory/character/{memory_id}/stats", response_model=CharacterMemoryStatsResponse)  
async def get_character_memory_stats(memory_id: str, app=Depends(get_core_app)):
    """特定キャラクターの記憶統計取得"""
    
@router.delete("/memory/character/{memory_id}/all", response_model=CharacterMemoryDeleteResponse)
async def delete_character_memories(memory_id: str, app=Depends(get_core_app)):
    """特定キャラクターの記憶削除"""
```

## CocoroDock互換性

### 期待されるAPIマッピング

**CocoroDockのAPIコール → 新しいエンドポイント**:
- `GetMemoryListAsync()` → `GET /api/memory/characters`
- `GetMemoryStatsAsync(memoryId)` → `GET /api/memory/character/{memory_id}/stats` 
- `DeleteUserMemoriesAsync(memoryId)` → `DELETE /api/memory/character/{memory_id}/all`

### データ構造の互換性

CocoroDockが期待する`MemoryInfo`構造:
```csharp
public class MemoryInfo
{
    public string memory_id { get; set; }      // キャラクターのmemoryId
    public string memory_name { get; set; }    // キャラクター表示名  
    public string role { get; set; }           // "character"
    public bool created { get; set; }          // true
}
```

## 実装計画（修正版）

### Phase 1: 内部API拡張
1. CocoroProductWrapperに新メソッド追加
   - `get_character_list()`
   - `get_character_memory_stats(memory_id)`
   - `delete_character_memories(memory_id)`

### Phase 2: 外部API実装
1. `src/models/api_models.py`にレスポンスモデル追加
2. `src/api/memory.py`作成・実装
3. `src/main.py`にルーター追加

### Phase 3: 統合テスト
1. CocoroDockとの連携確認
2. キャラクター別記憶管理の動作確認

## 重要な設計変更点

### 従来の設計からの変更

**変更前（間違った想定）**:
- ユーザー複数、各ユーザーが記憶を持つ
- `/api/memory/users` でユーザー一覧取得
- `/api/memory/user/{user_id}/stats` でユーザー記憶統計

**変更後（正しい構造）**:
- ユーザー1人固定、複数キャラクター（キューブ）
- `/api/memory/characters` でキャラクター一覧取得  
- `/api/memory/character/{memory_id}/stats` でキャラクター記憶統計

### APIパスの変更理由

**意味的な正確性**:
- `user` → `character`: 実際の操作対象を反映
- `memory_id`パラメータ: キャラクターのmemoryIdを直接使用

**CocoroDock互換性**:
- CocoroDockが送信するmemoryIdがそのままAPIパスに対応

---

この設計により、CocoroAIの実際のアーキテクチャに合致した、真に動作するメモリ管理APIが実装できます。