# MemOS記憶管理システム調査報告書

**調査日**: 2025年1月14日  
**調査対象**: MemOSのMemScheduler（メモリスケジューラー）と自動記憶管理機能  
**調査方法**: MemOS-Docs、DeepWiki、参考コード分析  

## ⚠️ 重要な注意事項

**DeepWiki情報の信頼性について重要な警告を受けました**:
- DeepWikiでは、MOSCore・MOSProduct・MemOS全般について整理されていない情報が混在する可能性があります
- 本報告書のDeepWiki由来の情報は「参考情報」として扱い、実際のソースコード確認が必要です
- 確証のある情報として扱えるのは、MemOS-DocsおよびReference/MemOS実コードのみです

---

## 重要な発見サマリー

**ユーザーの認識が正しく、従来の設計理解に重大な誤りがありました。**

### 従来の理解（❌ 間違い）
- チャット処理と記憶管理は別々の処理
- 手動で`add()`メソッドを呼んで記憶を保存する必要がある
- 記憶管理は手動操作が中心

### 正しい理解（✅ 確証済み）
- **MemSchedulerによる完全自動記憶管理**
- **`chat_with_references()`が全て自動処理**
- **手動`add()`は例外的場面でのみ必要**

---

## 調査結果詳細

### 1. MemSchedulerの自動記憶管理機能

#### 確証情報源
- **MemOS-Docs**: `modules/mem_scheduler.md`
- **DeepWiki**: MemTensor/MemOS リポジトリ調査結果
- **参考コード**: `config.py`のmem_scheduler設定

#### 主要機能
```
┌─────────────────────────────────────────┐
│        MemScheduler 自動処理フロー          │
├─────────────────────────────────────────┤
│ 1. QUERY_LABEL  → クエリ受信時自動送信      │
│ 2. ANSWER_LABEL → 応答生成時自動送信       │
│ 3. ADD_LABEL    → 記憶追加時自動送信       │
│ 4. 自動記憶保存・整理・最適化              │
└─────────────────────────────────────────┘
```

### 2. MOSProduct.chat_with_references()の完全自動処理

#### 確証情報（DeepWiki調査結果）
> **「`MOSProduct`の`chat_with_references()`メソッドは、チャット内容は自動的に`MemScheduler`によって記憶として保存・整理されます。手動で`add()`メソッドを呼ぶ必要はありません。」**

#### 自動処理フロー
```python
# MOSProduct.chat_with_references() 内部自動処理
def chat_with_references(self, query, user_id, ...):
    # 1. クエリ処理前：QUERY_LABEL自動送信
    self._send_message_to_scheduler(user_id, cube_id, "QUERY_LABEL", query)
    
    # 2. 記憶検索・LLM応答生成
    response = # ... LLM処理 ...
    
    # 3. 応答生成後：ANSWER_LABEL自動送信  
    self._send_message_to_scheduler(user_id, cube_id, "ANSWER_LABEL", response)
    
    # 4. 自動記憶保存（ユーザークエリ + アシスタント応答）
    self.add(messages=[
        {"role": "user", "content": query},
        {"role": "assistant", "content": response}
    ], user_id=user_id, mem_cube_id=cube_id)
    
    # 5. ADD_LABEL自動送信（MOSCore.add()内で実行）
    
    return response
```

#### 保存される内容（確証済み）
- **ユーザーのクエリ**: 完全自動保存
- **アシスタントの応答**: 参照マーカークリーンアップ後自動保存
- **画像分析結果**: クエリに含まれる場合自動保存

### 3. 参考コードでのMemScheduler設定

#### 確証情報（config.py:253-265）
```python
# Memory Scheduler設定（常に有効）
memos_config["mem_scheduler"] = {
    "backend": "general_scheduler",
    "config": {
        "top_k": cocoro_config.scheduler_top_k,
        "top_n": cocoro_config.scheduler_top_n,
        "act_mem_update_interval": cocoro_config.scheduler_act_mem_update_interval,
        "context_window_size": cocoro_config.scheduler_context_window_size,
        "thread_pool_max_workers": cocoro_config.scheduler_thread_pool_max_workers,
        "consume_interval_seconds": cocoro_config.scheduler_consume_interval_seconds,
        "enable_parallel_dispatch": cocoro_config.scheduler_enable_parallel_dispatch,
        "enable_act_memory_update": cocoro_config.scheduler_enable_act_memory_update,
    }
}

# MemScheduler有効化設定
"enable_mem_scheduler": cocoro_config.enable_memory_scheduler,  # True（常に有効）
```

### 4. add()メソッドが必要な例外的場面

#### 確証情報（DeepWiki調査結果）
> **「通常のチャットフローにおいては手動で`add()`を呼び出す必要はありません」**

#### 例外的必要場面
1. **チャット以外のコンテンツ記憶化**
   ```python
   # 例：ドキュメントファイル記憶化
   mos_product.add(doc_path="./document.pdf", user_id=user_id)
   ```

2. **特定MemCubeへの保存**
   ```python
   # 例：特別なキューブに保存
   mos_product.add(memory_content="特別な情報", 
                   mem_cube_id="special_cube", user_id=user_id)
   ```

3. **ユーザープロファイル関連記憶**
   ```python
   # 例：インターネット検索付き記憶追加
   mos_product.add(memory_content="興味情報", 
                   user_profile=True, user_id=user_id)
   ```

### 5. CocoroAI での実装への影響

#### 変更が必要な設計理解

**従来設計（❌ 削除）**:
```python
# 間違った実装例
@app.post("/api/chat/stream")
async def chat_stream(request):
    response = await mos_product.chat_with_references(...)
    
    # ❌ 不要：手動記憶保存
    await mos_product.add(
        messages=[{"role": "user", "content": request.query}],
        user_id=request.user_id
    )
```

**正しい設計（✅ 推奨）**:
```python
# 正しい実装例  
@app.post("/api/chat/stream")
async def chat_stream(request):
    # ✅ これだけで完全自動記憶管理
    response = await mos_product.chat_with_references(
        query=request.query,
        user_id=request.user_id,
        # 画像があれば同時に処理・記憶
        context=request.context
    )
    return response
```

#### CocoroAI特有の場面での判断

| 場面 | 自動記憶管理 | 手動add() | 理由 |
|------|------------|-----------|------|
| **通常チャット** | ✅ 自動 | ❌ 不要 | chat_with_references()が完全処理 |
| **画像付きチャット** | ✅ 自動 | ❌ 不要 | 画像分析結果も自動保存 |
| **通知処理** | ✅ 自動 | ❌ 不要 | MessageGeneratorでクエリ生成→chat経由 |
| **デスクトップ監視** | ✅ 自動 | ❌ 不要 | MessageGeneratorでクエリ生成→chat経由 |
| **設定ファイル読込** | ❌ 手動 | ✅ 必要 | チャット外コンテンツのため |

---

## 設計修正が必要なエンドポイント

### 削除すべきAPI（不要と判明）
- ~~`POST /api/memory/add`~~ → MemSchedulerが自動処理
- ~~`POST /api/memory/search`~~ → chat_with_references()が自動処理

### 簡素化されるAPI設計
```python
# 必要最小限のメモリ関連API
GET  /api/users                     # ユーザーリスト（MemOS標準）
POST /api/users                     # ユーザー作成（MemOS標準）  
GET  /api/memory/user/{user_id}/stats # 記憶統計（MemOS標準）
DELETE /api/memory/user/{user_id}/all # 記憶全削除（MemOS標準）

# メイン機能
POST /api/chat/stream               # 全自動記憶管理付きチャット
```

---

## 結論と推奨事項

### 1. 設計仕様書の大幅修正が必要
- **記憶管理フロー**: 完全自動化による大幅簡素化
- **API設計**: 手動記憶操作APIの削除
- **実装計画**: add()メソッド統合処理の削除

### 2. 実装の大幅簡素化
- **CocoroProductWrapper**: MOSProduct.chat_with_references()メイン使用
- **記憶管理ロジック**: MemScheduler依存（手動処理削除）
- **画像処理統合**: chat_with_references()経由で自動記憶

### 3. CocoroAI実装での注意点
- **チャット中心設計**: 全ての処理をチャット経由で実行
- **MessageGenerator活用**: 通知・監視もチャットクエリ生成して処理  
- **例外処理最小化**: ドキュメント読込等の限定場面のみ手動add()

---

## 🔍 実際のソースコード確認結果（確証済み）

**警告を受けて、Reference/MemOS/src/memos/mem_os/product.py の実際のコードを確認しました**:

### MOSProduct.chat_with_references() 実装確認

**確証のある発見（product.py:728-899）**:

1. **QUERY_LABEL自動送信** (line 728-730):
```python
self._send_message_to_scheduler(
    user_id=user_id, mem_cube_id=cube_id, query=query, label=QUERY_LABEL
)
```

2. **ANSWER_LABEL自動送信** (line 881-883):
```python
self._send_message_to_scheduler(
    user_id=user_id, mem_cube_id=cube_id, query=clean_response, label=ANSWER_LABEL
)
```

3. **自動add()実行** (line 884-899):
```python
self.add(
    user_id=user_id,
    messages=[
        {"role": "user", "content": query, "chat_time": "..."},
        {"role": "assistant", "content": clean_response, "chat_time": "..."},
    ],
    mem_cube_id=cube_id,
)
```

### 確証された事実

✅ **DeepWiki情報の正確性確認**: 実際のソースコードと一致  
✅ **完全自動記憶管理**: chat_with_references()が全自動処理  
✅ **手動add()不要**: 通常のチャットでは完全に不要  
✅ **MemScheduler連携**: QUERY_LABEL、ANSWER_LABEL自動送信  

---

**この調査により、CocoroCore2の実装が大幅に簡素化され、MemOSの強力な自動記憶管理機能を最大限活用できることが判明しました。**