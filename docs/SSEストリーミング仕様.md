# SSEストリーミング仕様の詳細説明

## StatusEventとTextEventの配信タイミング

### 基本的な流れ

```
1. [StatusEvent] stage: "processing" 
   → 記憶検索開始

2. [StatusEvent] stage: "analyzing" (画像がある場合のみ)
   → 画像分析開始

3. [StatusEvent] stage: "generating"  
   → LLM応答生成開始

4. [TextEvent] 複数回配信
   → 生成されたテキストを逐次配信
   
5. [ReferenceEvent] (あれば)
   → 参照した記憶情報

6. [StatusEvent] stage: "completed"
   → 処理完了

7. [EndEvent]
   → ストリーム終了
```

### 重要な仕様

1. **StatusEventは各段階の開始時に1回だけ送信**
   - 定期的な送信ではない
   - 処理の進行を通知する役割

2. **TextEventが流れ始めたらStatusEventは送信されない**
   - TextEventの配信が始まる = 応答生成が進行中
   - この間はTextEventのみが流れる

3. **メッセージが生成できない場合**
   - エラーが発生した場合: `ErrorEvent`が送信される
   - タイムアウトした場合: `ErrorEvent`でタイムアウトを通知
   - いずれの場合も最後に`EndEvent`で終了

### 実装例（疑似コード）

```typescript
async function* streamChat(request: ChatRequest) {
  try {
    // 1. 記憶検索開始
    yield { 
      type: "status", 
      data: { 
        stage: "processing", 
        message: "記憶を検索しています..." 
      }
    };
    
    const memories = await searchMemories(request.query);
    
    // 2. 画像分析（画像がある場合）
    if (request.images?.length > 0) {
      yield { 
        type: "status", 
        data: { 
          stage: "analyzing", 
          message: "画像を分析しています..." 
        }
      };
      const analysis = await analyzeImages(request.images);
    }
    
    // 3. 応答生成開始
    yield { 
      type: "status", 
      data: { 
        stage: "generating", 
        message: "応答を生成しています..." 
      }
    };
    
    // 4. テキストストリーミング
    const stream = await generateResponse(request);
    for await (const chunk of stream) {
      yield { 
        type: "text", 
        data: { 
          content: chunk, 
          chunk_id: chunkCounter++ 
        }
      };
    }
    
    // 5. 参照情報（あれば）
    if (memories.length > 0) {
      yield { 
        type: "reference", 
        data: { memories }
      };
    }
    
    // 6. 完了
    yield { 
      type: "status", 
      data: { 
        stage: "completed", 
        message: "処理が完了しました" 
      }
    };
    
  } catch (error) {
    // エラー処理
    yield { 
      type: "error", 
      data: { 
        error_code: "generation_failed",
        message: "応答の生成に失敗しました" 
      }
    };
  } finally {
    // 7. 終了
    yield { type: "end", data: { request_id } };
  }
}
```

## エラー時の動作

### 各段階でのエラー処理

1. **記憶検索でエラー**
   ```
   [StatusEvent] "processing"
   [ErrorEvent] "memory_search_failed"
   [EndEvent]
   ```

2. **画像分析でエラー**
   ```
   [StatusEvent] "processing"
   [StatusEvent] "analyzing"
   [ErrorEvent] "image_analysis_failed"
   [EndEvent]
   ```

3. **応答生成でエラー**
   ```
   [StatusEvent] "processing"
   [StatusEvent] "generating"
   [ErrorEvent] "generation_failed"
   [EndEvent]
   ```

4. **タイムアウト**
   ```
   [StatusEvent] "processing"
   [StatusEvent] "generating"
   [ErrorEvent] "timeout"
   [EndEvent]
   ```

## クライアント側の実装指針

```typescript
const eventSource = new EventSource('/api/chat/stream');

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch(data.type) {
    case 'status':
      // プログレス表示を更新
      updateProgress(data.data.stage, data.data.message);
      break;
      
    case 'text':
      // テキストを追加表示（タイプライター効果など）
      appendText(data.data.content);
      break;
      
    case 'error':
      // エラー表示
      showError(data.data.message);
      break;
      
    case 'end':
      // ストリーム終了処理
      eventSource.close();
      break;
  }
};
```