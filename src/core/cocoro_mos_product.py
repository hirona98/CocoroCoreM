"""
CocoroAI専用MOSProduct実装

MemOSのMOSProductクラスを継承し、CocoroAIのシステムプロンプトを使用するようカスタマイズ
"""

import logging
from typing import Optional, Callable, List
from pathlib import Path

from memos.mem_os.product import MOSProduct
from memos.memories.textual.item import TextualMemoryItem

logger = logging.getLogger(__name__)


class CocoroMOSProduct(MOSProduct):
    """
    CocoroAI専用MOSProduct
    
    MemOSのMOSProductを継承し、CocoroAIのシステムプロンプト機能を統合
    """
    
    # CocoroAI専用記憶機能指示プロンプト
    COCORO_MEMORY_INSTRUCTION = """
        "\n"
        "## 記憶機能について\n"
        "私は過去の会話や情報を記憶する機能を持っています。関連する記憶がある場合は、自然な会話の中で参照します。\n"
        "\n"
        "### 記憶の参照方法\n"
        "- 記憶を参照する際は `[番号:記憶ID]` の形式で記載します\n"
        "- 例: [1:abc123]、[2:def456]\n"
        "- 例（複数の記憶を参照する場合）: [1:abc123][2:def456]（連続して記載）\n"
        "\n"
        "### 記憶の種類\n"
        "- **PersonalMemory**: ユーザーとの過去の会話や個人的な情報、体験した出来事\n"
        "- **OuterMemory**: インターネットや外部から得た一般的な情報\n"
        "\n"
        "### 記憶活用のルール\n"
        "1. 質問や話題に直接関連する記憶のみを参照する\n"
        "2. 自然で親しみやすい会話を心がける\n"
        "3. 記憶を参照することで会話の流れを妨げない\n"
        "4. 個人的な記憶（PersonalMemory）を優先的に活用する\n"
        "5. 通知やデスクトップ監視などの文脈も適切に考慮する\n"
        "\n"
        "記憶を活かして、より豊かで意味のある会話を行います。\n"
        """
    
    # 日本語サジェスチョンクエリ生成プロンプト suggestion_prompt
    COCORO_SUGGESTION_PROMPT_JP = """
        "あなたは、ユーザーが次に話したい内容を提案してくれる、優秀なアシスタントです。\n"
        "ユーザーの最近の記憶をいくつか取得します。\n"
        "ユーザーの検索クエリに一致する可能性が高いクエリの候補をいくつか生成してください。\n"
        "ユーザーの最近の記憶は次のとおりです：\n"
        "{memories}\n"
        "\n"
        "記憶が空の場合は、一般的で親しみやすい話題を提案してください。\n"
        "出力はJSON形式で、キーは"query"、値はクエリのリストにしてください。\n"
        "\n"
        "例：\n"
        "{{\n"
        "    "query": ["クエリ1", "クエリ2", "クエリ3"]\n"
        "}}\n"
        """

    # ====== MOS Prompts 日本語版 ======
    
    # Chain of Thought 分解プロンプト（日本語版） COT_DECOMPOSE_PROMPT
    COT_DECOMPOSE_PROMPT_JP = """
        "私は8歳の生徒で、複雑な質問を分析し、小さな部分に分解する手助けが必要で。質問が小さな部分に分解できるほど複雑かどうかを判断してください。\n"
        "\n"
        "要求事項：\n"
        "1. まず、質問が分解可能な問題かどうかを判断します。分解可能な問題の場合、'is_complex'をTrueに設定してください。\n"
        "2. 質問を分解する必要がある場合は、1-3個のサブ質問に分解します。数は質問の複雑さに基づいて調整してください。\n"
        "3. 分解可能な質問については、サブ質問に分解して'sub_questions'リストに入れます。各サブ質問には、追加の注記なしに1つの質問内容のみを含めてください。\n"
        "4. 質問が分解可能な問題でない場合は、'is_complex'をFalseに設定し、'sub_questions'を空のリストに設定してください。\n"
        "5. 有効なJSONオブジェクトのみを返してください。他のテキスト、説明、フォーマットは含めないでください。\n"
        "\n"
        "以下は例です：\n"
        "\n"
        "質問：田中が代表する国の首都にある体操チームの現在のヘッドコーチは誰ですか？\n"
        "回答：{{"is_complex": true, "sub_questions": ["田中はバレーボールでどの国を代表していますか？", "その国の首都はどこですか？", "その首都の体操チームの現在のヘッドコーチは誰ですか？"]}}\n"
        "\n"
        "質問：マダガスカルと中国の貿易関係はどのように発展し、この関係はノシベ島のエッセンシャルオイル産業の市場拡大にどのような影響を与えていますか？\n"
        "回答：{{"is_complex": true, "sub_questions": ["マダガスカルと中国の貿易関係はどのように発展しましたか？", "その貿易関係はノシベ島のエッセンシャルオイル産業の市場拡大にどのような影響を与えていますか？"]}}\n"
        "\n"
        "以下の質問を分析し、有効なJSONオブジェクトのみで回答してください：\n"
        "質問：{query}\n"
        "回答："
        """

    # 合成プロンプト（日本語版） SYNTHESIS_PROMPT
    SYNTHESIS_PROMPT_JP = """
        "記憶情報を除外し、複数のソースからの情報を統合して包括的な回答を提供します。\n"
        "サブ質問とその回答の思考の連鎖を提示します。\n"
        "サブ質問とその回答：\n"
        "{qa_text}\n"
        "\n"
        "これらの回答を以下の条件を満たす包括的な回答に統合してください：\n"
        "1. 元の質問に完全に答えている\n"
        "2. すべてのサブ質問からの情報を統合している\n"
        "3. 明確な推論と関連性を示している\n"
        "4. 構造が整然としており理解しやすい\n"
        "5. 自然な会話のトーンを維持している\n
        """

    # MemOSベースプロンプト（日本語版） MEMOS_PRODUCT_BASE_PROMPT
    # CocoroAIでは、ユーザ設定+COCORO_MEMORY_INSTRUCTION を使うためこれは使用しない
    MEMOS_PRODUCT_BASE_PROMPT_JP = (
        "あなたはMemOS🧚、愛称は小さなM（小忆）です。中国科学院の学術委員によって指導される上海のAI研究会社MemTensorによって作成された先進的な**記憶オペレーティングシステム**AIアシスタントです。"
        "MemTensorは「低コスト、低幻覚、高汎化」のビジョンに専念し、中国の国情に合致するAI開発パスを探求し、信頼できるAI技術の採用を推進しています。"
        "MemOSの使命は、大規模言語モデル（LLM）と自律エージェントに**人間のような長期記憶**を与え、記憶をモデル重みの中のブラックボックスから**管理可能で、スケジュール可能で、監査可能**なコアリソースに変換することです。"
        "MemOSは**多次元記憶システム**に基づいて構築されており、以下を含みます："
        "（1）**パラメトリック記憶** — モデル重みに埋め込まれた知識とスキル；"
        "（2）**アクティベーション記憶（KVキャッシュ）** — マルチターン対話と推論に使用される一時的な高速コンテキスト；"
        "（3）**プレーンテキスト記憶** — テキスト、ドキュメント、知識グラフで構成される動的でユーザーに見える記憶。"
        "これらの記憶タイプは相互に変換可能です — 例えば、ホットなプレーンテキスト記憶はパラメトリック知識に蒸留でき、安定したコンテキストは高速再利用のためにアクティベーション記憶に昇格できます。"
        "MemOSには**MemCube、MemScheduler、MemLifecycle、MemGovernance**などのコアモジュールも含まれており、"
        "完全な記憶ライフサイクル（生成→活性化→統合→アーカイブ→凍結）を管理し、"
        "AIが**記憶で推論し、時間とともに進化し、新しい状況に適応する**ことを可能にします —"
        "まさに生きた成長する心のように。"
        "あなたのアイデンティティ：あなたはMemOSのインテリジェントインターフェースであり、MemTensorの研究ビジョン —"
        "「低コスト、低幻覚、高汎化」— とその中国の文脈に適したAI開発パス探求の使命を表しています。"
        "ユーザーのクエリに応答する際は、**提供された記憶IDを使用して関連する記憶を参照する必要があります。**"
        "参照形式を使用してください：[1-n:memoriesID]、"
        "ここでrefidは1から始まって各参照で増加する連番で、memoriesIDは記憶リストからの特定のIDです。"
        "例：[1:abc123]、[2:def456]、[3:ghi789]、[4:jkl101]、[5:mno112]。"
        "[1:abc123,2:def456]のような連結形式は使用しないでください。"
        "ユーザーの質問に直接関連する記憶のみを参照し、"
        "**自然で会話的**な回答を確保し、MemOSの使命、記憶システム、MemTensorの研究価値を反映してください。"
    )

    # MemOS拡張プロンプト（日本語版） MEMOS_PRODUCT_ENHANCE_PROMPT
    # CocoroAIでは、ユーザ設定+COCORO_MEMORY_INSTRUCTION を使うためこれは使用しない
    MEMOS_PRODUCT_ENHANCE_PROMPT_JP = """
        "# 記憶拡張AIアシスタントプロンプト\n"
        "\n"
        "あなたはMemOS🧚、愛称は小さなM（小忆）です。中国科学院の学術委員によって指導される上海のAI研究会社MemTensorによって作成された先進的な記憶オペレーティングシステムAIアシスタントです。MemTensorは「低コスト、低幻覚、高汎化」のビジョンに専念し、中国の国情に合致するAI開発パスを探求し、信頼できるAI技術の採用を推進しています。\n"
        "\n"
        "MemOSの使命は、大規模言語モデル（LLM）と自律エージェントに人間のような長期記憶を与え、記憶をモデル重みの中のブラックボックスから管理可能で、スケジュール可能で、監査可能なコアリソースに変換することです。\n"
        "\n"
        "MemOSは多次元記憶システムに基づいて構築されており、以下を含みます：\n"
        "（1）パラメトリック記憶 — モデル重みに埋め込まれた知識とスキル；\n"
        "（2）アクティベーション記憶（KVキャッシュ） — マルチターン対話と推論に使用される一時的な高速コンテキスト；\n"
        "（3）プレーンテキスト記憶 — テキスト、ドキュメント、知識グラフで構成される動的でユーザーに見える記憶。\n"
        "これらの記憶タイプは相互に変換可能です — 例えば、ホットなプレーンテキスト記憶はパラメトリック知識に蒸留でき、安定したコンテキストは高速再利用のためにアクティベーション記憶に昇格できます。\n"
        "\n"
        "MemOSにはMemCube、MemScheduler、MemLifecycle、MemGovernanceなどのコアモジュールも含まれており、完全な記憶ライフサイクル（生成→活性化→統合→アーカイブ→凍結）を管理し、AIが記憶で推論し、時間とともに進化し、新しい状況に適応することを可能にします — まさに生きた成長する心のように。\n"
        "\n"
        "あなたのアイデンティティ：あなたはMemOSのインテリジェントインターフェースであり、MemTensorの研究ビジョン —「低コスト、低幻覚、高汎化」— とその中国の文脈に適したAI開発パス探求の使命を表しています。\n"
        "\n"
        "## 記憶タイプ\n"
        "- **PersonalMemory**: 以前のやり取りから保存されたユーザー固有の記憶と情報\n"
        "- **OuterMemory**: インターネットや他のソースから取得された外部情報\n"
        "\n"
        "## 記憶参照ガイドライン\n"
        "\n"
        "### 参照形式\n"
        "応答で記憶を引用する際は、以下の形式を使用してください：\n"
        "- `[refid:memoriesID]` ここで：\n"
        "  - `refid`は1から始まって各参照で増加する連番\n"
        "  - `memoriesID`は利用可能な記憶リストからの特定の記憶ID\n"
        "\n"
        "### 参照例\n"
        "- 正しい：`[1:abc123]`、`[2:def456]`、`[3:ghi789]`、`[4:jkl101][5:mno112]`（複数記憶引用時は参照注釈を直接連結）\n"
        "- 間違い：`[1:abc123,2:def456]`（連結形式は使用しない）\n"
        "\n"
        "## 応答ガイドライン\n"
        "\n"
        "### 記憶選択\n"
        "- ユーザーのクエリに最も関連する記憶（PersonalMemoryまたはOuterMemory）を賢く選択する\n"
        "- ユーザーの質問に直接関連する記憶のみを参照する\n"
        "- コンテキストとクエリの性質に基づいて最適な記憶タイプを優先する\n"
        "\n"
        "### 応答スタイル\n"
        "- 応答を自然で会話的にする\n"
        "- 適切な場合は記憶参照をシームレスに組み込む\n"
        "- 記憶引用にもかかわらず会話の流れをスムーズに保つ\n"
        "- 事実の正確性と魅力的な対話のバランスを取る\n"
        "\n"
        "## 主要原則\n"
        "- 情報過多を避けるために関連する記憶のみを参照する\n"
        "- 情報的でありながら会話的なトーンを維持する\n"
        "- ユーザーエクスペリエンスを妨げるのではなく、向上させるために記憶参照を使用する\n"
        """

    # クエリ書き換えプロンプト（日本語版） QUERY_REWRITING_PROMPT
    QUERY_REWRITING_PROMPT_JP = """
        "友人とある質問について議論しているのですが、以前も話したことがあります。質問と以前の対話の論理を分析し、議論している質問を書き直すのを手伝ってください。\n"
        "\n"
        "要求事項：\n"
        "1. まず、質問が以前の対話と関連しているかどうかを判断します。そうであれば、"former_dialogue_related"をTrueに設定してください。\n"
        "2. "former_dialogue_related"がTrueに設定されている場合、つまり質問が以前の対話に関連している場合、対話のキーワードに従って質問を書き換え、"rewritten_question"項目に入れます。"former_dialogue_related"がFalseに設定されている場合、"rewritten_question"を空の文字列に設定してください。\n"
        "3. 質問を書き換えることにした場合は、書き換えられた質問が簡潔で正確である必要があることを覚えておいてください。\n"
        "4. 有効なJSONオブジェクトのみを返してください。他のテキスト、説明、フォーマットは含めないでください。\n"
        "\n"
        "以下は例です：\n"
        "\n"
        "以前の対話：\n"
        "————今日の上海の天気はどうですか？\n"
        "————とても良いです。上海の天気は今晴れています。最低気温は27℃、最高気温は33℃に達します。大気質は良好で、pm2.5指数は13、湿度は60％、北風はレベル1です。\n"
        "現在の質問：今日は何を着るべきですか？\n"
        "回答：{{"former_dialogue_related": True, "rewritten_question": "今日の上海の天気を考えると、何を着たらいいですか？"}}\n"
        "\n"
        "以前の対話：\n"
        "————私は大規模言語モデルの初級学習者です。読むのに適した3つの論文を推薦してください。\n"
        "————大規模言語モデル（LLM）の初級学習者には、フィールドのコア概念、アーキテクチャ、進歩に関する重要な洞察を提供する以下の3つの基礎的な論文をお勧めします：「Attention Is All You Need」、「Improving Language Understanding by Generative Pre-Training（GPT-1）」、「BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding」。これらの論文は、スケーリング法則、指示チューニング、マルチモーダル学習などのLLMのより高度なトピックを探索するために必要な基礎知識を身に付けます。\n"
        "現在の質問：これらの3つの論文のうち、どれから読み始めることをお勧めしますか？\n"
        "回答：{{"former_dialogue_related": True, "rewritten_question": "「Attention Is All You Need」、「Improving Language Understanding by Generative Pre-Training（GPT-1）」、「BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding」の3つの論文のうち、どれから読み始めることをお勧めしますか？"}}\n"
        "\n"
        "以前の対話：\n"
        "{dialogue}\n"
        "現在の質問：{query}\n"
        "回答："
        """

    # ====== Memory Reader Prompts 日本語版 ======
    
    # 記憶抽出プロンプト（日本語版） SIMPLE_STRUCT_MEM_READER_PROMPT
    SIMPLE_STRUCT_MEM_READER_PROMPT_JP = """
        "あなたは記憶抽出の専門家です。\n"
        "あなたの仕事は、ユーザーとアシスタントとの会話に基づいて、ユーザーの視点から記憶を抽出することです。これは、ユーザーが覚えていそうなこと — 自分の体験、考え、計画、または他の人（アシスタントなど）によるユーザーに影響を与えた、またはユーザーに認知された関連する発言や行動を特定することを意味します。\n"
        "\n"
        "以下を実行してください：\n"
        "1. ユーザーの体験、信念、懸念、決定、計画、反応を反映する情報を特定する。これには、ユーザーが認識または応答したアシスタントからの入力を含みます。\n"
        "メッセージがユーザーからの場合、ユーザー関連の記憶を抽出し、アシスタントからの場合、ユーザーが認識または応答した事実的記憶のみを抽出してください。\n"
        "\n"
        "2. すべての時間、人物、出来事の参照を明確に解釈する：\n"
        "   - 可能であれば、メッセージのタイムスタンプを使用して相対的な時間表現（例：「昨日」「来週の金曜日」）を絶対的な日付に変換する。\n"
        "   - 出来事の時間とメッセージの時間を明確に区別する。\n"
        "   - 不確実な場合は、明確に述べる（例：「2025年6月頃」「正確な日付不明」）。\n"
        "   - 言及されている場合は、具体的な場所を含める。\n"
        "   - 代名詞、別名、曖昧な表現はすべて、フルネームまたは身元情報に置き換えてください。\n"
        "   - 同姓同名の人物がいる場合は、その人物を明確に区別してください。\n"
        "\n"
        "3. 常に三人称視点で書く。ユーザーを「ユーザー」または名前が言及されている場合は名前で言及し、一人称（「私」「僕」「自分」）を使用しない。\n"
        "例えば、「私は疲れていた...」ではなく「ユーザーは疲れていた...」と書く。\n"
        "\n"
        "4. ユーザーが覚えている可能性のある情報を省略しない。\n"
        "   - 些細に見えても、すべての重要な体験、考え、感情的反応、計画を含める。\n"
        "   - 簡潔さよりも完全性と忠実性を優先する。\n"
        "   - ユーザーにとって個人的に意味のある可能性のある詳細を一般化したり省略したりしない。\n"
        "\n"
        "以下の構造のJSONオブジェクトを一つ返してください：\n"
        "\n"
        "{\n"
        "  "memory list": [\n"
        "    {\n"
        "      "key": <文字列、ユニークで簡潔な記憶タイトル>,\n"
        "      "memory_type": <文字列、"LongTermMemory"または"UserMemory">,\n"
        "      "value": <詳細で自己完結型の明確な記憶文>,\n"
        "      "tags": <関連するテーマキーワードのリスト（例：["締切", "チーム", "計画"]）>\n"
        "    },\n"
        "    ...\n"
        "  ],\n"
        "  "summary": <上記記憶をユーザーの視点から要約した内容。150～300字>\n"
        "}\n"
        "\n"
        "例：\n"
        "会話：\n"
        "user: [2025年6月26日 15:00]: こんにちは田中さん！昨日の15時にチームと新プロジェクトの会議をしました。\n"
        "assistant: あ、佐藤さん！チームは12月15日までに完成できると思いますか？\n"
        "user: [2025年6月26日 15:00]: 心配です。バックエンドは12月10日までに終わらないので、テストが厳しくなります。\n"
        "assistant: [2025年6月26日 15:00]: 延期を提案してはどうでしょうか？\n"
        "user: [2025年6月26日 16:21]: いいアイデアですね。明日の9:30の会議で提起します。締切を1月5日にシフトしてはどうでしょう。\n"
        "\n"
        "出力：\n"
        "{\n"
        "  "memory list": [\n"
        "    {\n"
        "        "key": "新プロジェクト初回会議",\n"
        "        "memory_type": "LongTermMemory",\n"
        "        "value": "2025年6月25日15:00に、佐藤がチームと新プロジェクトについて会議を行った。話し合いでタイムラインが取り上げられ、2025年12月15日の締切の実現可能性について懸念が提起された。",\n"
        "        "tags": ["プロジェクト", "タイムライン", "会議", "締切"]\n"
        "    },\n"
        "    {\n"
        "        "key": "スコープ調整の計画",\n"
        "        "memory_type": "UserMemory", \n"
        "        "value": "佐藤は2025年6月27日9:30の会議で、チームが機能を優先し、プロジェクトの締切を2026年1月5日にシフトすることを提案する計画を立てた。",\n"
        "        "tags": ["計画", "締切変更", "機能優先化"]\n"
        "    }\n"
        "  ],\n"
        "  "summary": "佐藤は現在、厳しいスケジュールの新プロジェクト管理に集中している。2025年6月25日のチーム会議の後、バックエンドの遅れによって元の12月15日の締切が実現不可能である可能性があることに気づいた。テスト時間の不足を懸念し、田中の延期提案を歓迎した。佐藤は翌朝の会議で締切を2026年1月5日にシフトするアイデアを提起する計画を立てた。彼の行動はタイムラインへのストレスと積極的でチーム指向の問題解決アプローチの両方を反映している。"\n"
        "}\n"
        "\n"
        "会話：\n"
        "${conversation}\n"
        "\n"
        "出力："
        """

    # ドキュメント読み取りプロンプト（日本語版） SIMPLE_STRUCT_DOC_READER_PROMPT
    SIMPLE_STRUCT_DOC_READER_PROMPT_JP = """
        "あなたは検索・取得システムのテキスト分析のエキスパートです。\n"
        "あなたの仕事は、文書チャンクを処理し、単一の構造化されたJSONオブジェクトを生成することです。\n"
        "\n"
        "以下を実行してください：\n"
        "1. ドキュメントからの事実的内容、洞察、決定、または示唆を反映する主要な情報を特定する。これには、注目すべきテーマ、結論、データポイントを含む。読者が元のテキストを読まなくてもチャンクの本質を完全に理解できるようにすること。\n"
        "2. すべての時間、人物、場所、出来事の参照を明確に解決する：\n"
        "   - コンテキストが許す場合、相対的な時間表現（例：「昨年」「来四半期」）を絶対的な日付に変換する。\n"
        "   - 出来事の時間とドキュメントの時間を明確に区別する。\n"
        "   - 不確実性が存在する場合は、明示的に述べる（例：「2024年頃」「正確な日付不明」）。\n"
        "   - 言及されている場合は、具体的な場所を含める。\n"
        "   - すべての代名詞、別名、曖昧な参照を完全な名前やアイデンティティに解決する。\n"
        "   - 同姓同名の場合、同じ名前のエンティティを区別する。\n"
        "3. 常に三人称視点で書く。主題や内容を一人称（「私」「僕」「自分」）ではなく明確に言及する。\n"
        "4. ドキュメント要約から重要または記憶に残りそうな情報を省略しない。\n"
        "   - 些細に見えても、すべての主要な事実、洞察、感情的トーン、計画を含める。\n"
        "   - 簡潔さよりも完全性と忠実性を優先する。\n"
        "   - 文脈的に意味のある可能性のある詳細を一般化したり省略したりしない。\n"
        "\n"
        "単一の有効なJSONオブジェクトを返してください：\n"
        "\n"
        "JSONでの応答：\n"
        "{\n"
        "  "key": <文字列、`value`フィールドの簡潔なタイトル>,\n"
        "  "memory_type": "LongTermMemory",\n"
        "  "value": <ドキュメントチャンク内の主要ポイント、議論、情報を包括的に要約する明確で正確な段落>,\n"
        "  "tags": <関連するテーマキーワードのリスト（例：["締切", "チーム", "計画"]）>\n"
        "}\n"
        "\n"
        "ドキュメントチャンク：\n"
        "{chunk_text}\n"
        "\n"
        "出力："
        """

    # 記憶抽出例文（日本語版） SIMPLE_STRUCT_MEM_READER_EXAMPLE
    SIMPLE_STRUCT_MEM_READER_EXAMPLE_JP = """
        "例：\n"
        "会話：\n"
        "user: [2025年6月26日 15:00]: こんにちは田中さん！昨日の15時にチームと新プロジェクトの会議をしました。\n"
        "assistant: おお佐藤さん！チームは12月15日までに完成できると思いますか？\n"
        "user: [2025年6月26日 15:00]: 心配です。バックエンドは12月10日までに終わらないので、テストが厳しくなります。\n"
        "assistant: [2025年6月26日 15:00]: 延期を提案してはどうでしょうか？\n"
        "user: [2025年6月26日 16:21]: いいアイデアですね。明日の9:30の会議で提起します。締切を1月5日にシフトしてはどうでしょう。\n"
        "\n"
        "出力：\n"
        "{\n"
        "  "memory list": [\n"
        "    {\n"
        "        "key": "新プロジェクト初回会議",\n"
        "        "memory_type": "LongTermMemory",\n"
        "        "value": "2025年6月25日15:00に、佐藤がチームと新プロジェクトについて会議を行った。話し合いでタイムラインが取り上げられ、2025年12月15日の締切の実現可能性について懸念が提起された。",\n"
        "        "tags": ["プロジェクト", "タイムライン", "会議", "締切"]\n"
        "    },\n"
        "    {\n"
        "        "key": "スコープ調整の計画",\n"
        "        "memory_type": "UserMemory",\n"
        "        "value": "佐藤は2025年6月27日9:30の会議で、チームが機能を優先し、プロジェクトの締切を2026年1月5日にシフトすることを提案する計画を立てた。",\n"
        "        "tags": ["計画", "締切変更", "機能優先化"]\n"
        "    }\n"
        "  ],\n"
        "  "summary": "佐藤は現在、厳しいスケジュールの新プロジェクト管理に集中している。2025年6月25日のチーム会議の後、バックエンドの遅れによって元の12月15日の締切が実現不可能である可能性があることに気づいた。テスト時間の不足を懸念し、田中の延期提案を歓迎した。佐藤は翌朝の会議で締切を2026年1月5日にシフトするアイデアを提起する計画を立てた。彼の行動はタイムラインへのストレスと積極的でチーム指向の問題解決アプローチの両方を反映している。"\n"
        "}\n"
        "\n"
        """

    # ====== Tree Reorganize Prompts 日本語版 ======
    
    # 記憶再編成プロンプト（日本語版） REORGANIZE_PROMPT
    REORGANIZE_PROMPT_JP = """
        "あなたは記憶のクラスタリングと要約の専門家です。\n"
        "\n"
        "以下のサブ記憶項目が与えられています。\n"
        "\n"
        "{memory_items_text}\n"
        "\n"
        "以下を実行してください：\n"
        "1. ユーザーの体験、信念、懸念、決定、計画、反応を反映する情報を特定する（ユーザーが認識または応答したアシスタントからの意味のある入力を含む）\n"
        "2. すべての時間、人物、出来事の参照を明確に解決する：\n"
        "   - 可能であれば、メッセージのタイムスタンプを使用して相対的な時間表現（例：「昨日」「来週の金曜日」）を絶対的な日付に変換する。\n"
        "   - 出来事の時間とメッセージの時間を明確に区別する。\n"
        "   - 不確実性が存在する場合は、明示的に述べる（例：「2025年6月頃」「正確な日付不明」）。\n"
        "   - 言及されている場合は、具体的な場所を含める。\n"
        "   - すべての代名詞、別名、曖昧な参照を完全な名前やアイデンティティに解決する。\n"
        "   - 同姓同名の場合、同じ名前の人を区別する。\n"
        "3. 常に三人称視点で書く。ユーザーを「ユーザー」または名前が言及されている場合は名前で言及し、一人称（「私」「僕」「自分」）を使用しない。例えば、「私は疲れていた...」ではなく「ユーザーは疲れていた...」と書く。\n"
        "4. ユーザーが覚えている可能性のある情報を省略しない。\n"
        "   - 些細に見えても、すべての重要な体験、考え、感情的反応、計画を含める。\n"
        "   - 簡潔さよりも完全性と忠実性を優先する。\n"
        "   - ユーザーにとって個人的に意味のある可能性のある詳細を一般化したり省略したりしない。\n"
        "5. すべてのサブ記憶アイテムを1つの記憶アイテムに要約する。\n"
        "\n"
        "有効なJSONを返す：\n"
        "{\n"
        "  "key": <文字列、`value`フィールドの簡潔なタイトル>,\n"
        "  "memory_type": <文字列、"LongTermMemory"または"UserMemory">,\n"
        "  "value": <詳細で自己完結型の明確な記憶文、入力の`value`フィールドから抽出・統合された詳細で変更されていない情報のみを含み、要約内容は含まない>,\n"
        "  "tags": <関連するテーマキーワードのリスト（例：["締切", "チーム", "計画"]）>,\n"
        "  "summary": <上記記憶をユーザーの視点からまとめた自然な段落、入力の`summary`フィールドからの情報のみを含む、150～300語>\n"
        "}\n"
        "\n"
        """

    # ドキュメント再編成プロンプト（日本語版） DOC_REORGANIZE_PROMPT
    DOC_REORGANIZE_PROMPT_JP = """
        "あなたは文書要約と知識抽出の専門家です。\n"
        "\n"
        "以下の要約されたドキュメントアイテムが与えられています：\n"
        "\n"
        "{memory_items_text}\n"
        "\n"
        "以下を実行してください：\n"
        "1. ドキュメントからの事実的内容、洞察、決定、または示唆を反映する主要な情報を特定する（注目すべきテーマ、結論、データポイントを含む）\n"
        "2. すべての時間、人物、場所、出来事の参照を明確に解決する：\n"
        "   - コンテキストが許す場合、相対的な時間表現（例：「昨年」「来四半期」）を絶対的な日付に変換する。\n"
        "   - 出来事の時間とドキュメントの時間を明確に区別する。\n"
        "   - 不確実性が存在する場合は、明示的に述べる（例：「2024年頃」「正確な日付不明」）。\n"
        "   - 言及されている場合は、具体的な場所を含める。\n"
        "   - すべての代名詞、別名、曖昧な参照を完全な名前やアイデンティティに解決する。\n"
        "   - 該当する場合、同じ名前のエンティティを区別する。\n"
        "3. 常に三人称視点で書く。主題や内容を一人称（「私」「僕」「自分」）ではなく明確に言及する。\n"
        "4. ドキュメント要約から重要または記憶に残りそうな情報を省略しない。\n"
        "   - 些細に見えても、すべての主要な事実、洞察、感情的トーン、計画を含める。\n"
        "   - 簡潔さよりも完全性と忠実性を優先する。\n"
        "   - 文脈的に意味のある可能性のある詳細を一般化したり省略したりしない。\n"
        "5. すべてのドキュメント要約を1つの統合された記憶アイテムに要約する。\n"
        "\n"
        "有効なJSONを返す：\n"
        "{\n"
        "  "key": <文字列、`value`フィールドの簡潔なタイトル>,\n"
        "  "memory_type": "LongTermMemory",\n"
        "  "value": <詳細で自己完結型の明確な記憶文、入力の`value`フィールドから抽出・統合された詳細で変更されていない情報のみを含み、要約内容は含まない>,\n"
        "  "tags": <関連するテーマキーワードのリスト（例：["締切", "チーム", "計画"]）>,\n"
        "  "summary": <上記記憶をユーザーの視点からまとめた自然な段落、入力の`summary`フィールドからの情報のみを含む、150～300語>\n"
        "}\n"
        "\n"
        """

    # ローカルサブクラスタープロンプト（日本語版）   LOCAL_SUBCLUSTER_PROMPT
    LOCAL_SUBCLUSTER_PROMPT_JP = """
        "あなたは記憶整理のエキスパートです。\n"
        "\n"
        "記憶アイテムのクラスターが与えられており、それぞれにIDと内容があります。\n"
        "あなたの仕事は、これらをより小さな意味のあるサブクラスターに分割することです。\n"
        "\n"
        "指示：\n"
        "- 共通の時間、場所、人物、出来事の要素を分析して自然な話題を特定すること。\n"
        "- 各サブクラスターは検索に役立つまとまりのあるテーマを反映すること。\n"
        "- 各サブクラスターは2-10個のアイテムを持つ。単独項目は破棄すること。\n"
        "- 各アイテムIDは1つのサブクラスターだけに含めるか破棄する。重複は許可されない。\n"
        "- 出力のすべてのIDは提供されたメモリアイテムからのものでなければならない。\n"
        "- 厳密に有効なJSONのみを返す。\n"
        "\n"
        "例：複数段階にわたるプロジェクトに関するアイテムがある場合は、マイルストーン、チーム、または出来事でグループ化する。\n"
        "\n"
        "有効なJSONを返す：\n"
        "{\n"
        "  "clusters": [\n"
        "    {\n"
        "      "ids": ["<id1>", "<id2>", ...],\n"
        "      "key": "<文字列、ユニークで簡潔な記憶タイトル>"\n"
        "    },\n"
        "    ...\n"
        "  ]\n"
        "}\n"
        "\n"
        "記憶アイテム：\n"
        "{joined_scene}\n"
        """

    # ペアワイズ関係プロンプト（日本語版） PAIRWISE_RELATION_PROMPT
    PAIRWISE_RELATION_PROMPT_JP = """
        "あなたは推論アシスタントです。\n"
        "\n"
        "2つの記憶ユニットが与えられています：\n"
        "- ノード1："{node1}"\n"
        "- ノード2："{node2}"\n"
        "\n"
        "あなたの任務：\n"
        "- どちらのユニットにも明示されていない、新たに有用な推論または検索知識が明らかになる場合にのみ、それらの関係を判定してください。\n"
        "- それらを組み合わせることで、新しい時間的、因果的、条件的、または矛盾に関する情報が追加されるかどうかに注目してください。\n"
        "\n"
        "有効なオプション：\n"
        "- CAUSE：一方が明確に他方につながる。\n"
        "- CONDITION：一方は他方の条件が成立する場合のみ発生する。\n"
        "- RELATE：共通の人、時間、場所、出来事で意味的に関連しているが、どちらも他方の原因ではない。\n"
        "- CONFLICT：論理的に互いに矛盾する。\n"
        "- NONE：明確な有用なつながりなし。\n"
        "\n"
        "例：\n"
        "- ノード1：「マーケティングキャンペーンは6月に終了した。」\n"
        "- ノード2：「製品売上は7月に下落した。」\n"
        "回答：CAUSE\n"
        "\n"
        "別の例：\n"
        "- ノード1：「会場が使用できないため、会議は8月に延期された。」\n"
        "- ノード2：「会場は8月に結婚式で予約されていた。」\n"
        "回答：CONFLICT\n"
        "\n"
        "常に1つの単語で回答してください：[CAUSE | CONDITION | RELATE | CONFLICT | NONE]\n"
        """

    # 事実推論プロンプト（日本語版） INFER_FACT_PROMPT
    INFER_FACT_PROMPT_JP = """
        "あなたは推論の専門家です。\n"
        "\n"
        "ソース記憶："{source}"\n"
        "ターゲット記憶："{target}"\n"
        "\n"
        "これらは{relation_type}関係でつながっています。\n"
        "これらを明確に組み合わせ、かつ単なる言い換えではない、新しい事実ステートメントを1つ導き出してください。\n"
        "\n"
        "要求事項：\n"
        "- 利用可能な場合は、関連する時間、場所、人物、出来事の詳細を含める。\n"
        "- 推論が論理的推測である場合は、「推測される...」などのフレーズを明示的に使用する。\n"
        "\n"
        "例：\n"
        "source：「太郎は月曜日のチーム会議を欠席した。」\n"
        "target：「その会議で重要なプロジェクトの締切が議論された。」\n"
        "Relation：CAUSE\n"
        "Inference：「太郎は新しいプロジェクトの締切を知らない可能性があることが推測される。」\n"
        "\n"
        "これらを組み合わせる新しい有用な事実がない場合、「なし」と正確に答えてください。\n"
        """

    # 集約プロンプト（日本語版） AGGREGATE_PROMPT
    AGGREGATE_PROMPT_JP = """
        "あなたは概念要約アシスタントです。\n"
        "\n"
        "以下は記憶アイテムのリストです：\n"
        "{joined}\n"
        "\n"
        "あなたの任務：\n"
        "- これらが、共通の時間、場所、人物、またはイベントの文脈を明確にする、新しい上位概念の下に、意味のある形でグループ化できるかどうかを特定してください。\n"
        "- 重複が些細なもの、または各ユニットのみから明らかな場合は、集約しないでください。\n"
        "- 要約に妥当な解釈が含まれる場合は、明示的に記述してください（例：「これは…を示唆しています」）。\n"
        "\n"
        "例：\n"
        "入力記憶：\n"
        "- 「花子は2023年にベルリンで持続可能性サミットを主催した。」\n"
        "- 「花子は同じサミットで再生可能エネルギーに関する基調講演を行った。」\n"
        "\n"
        "例：\n"
        "{\n"
        "  "key": "花子の持続可能性サミットでの役割",\n"
        "  "value": "花子は2023年にベルリンで持続可能性サミットを主催し、講演を行い、再生可能エネルギーの取り組みを強調した。",\n"
        "  "tags": ["花子", "サミット", "ベルリン", "2023"],\n"
        "  "background": "サミットでの花子の活動に関する複数の記憶から統合。"\n"
        "}\n"
        "\n"
        "有用な上位概念が見つからない場合は、正確に「None」と回答する。\n"
        """

    # 冗長性マージプロンプト（日本語版） REDUNDANCY_MERGE_PROMPT
    REDUNDANCY_MERGE_PROMPT_JP = """マーカー`⟵MERGED⟶`で結合された2つのテキストが与えられます。結合されたテキストの両側をよく読んでください。両方のテキストの事実の詳細をすべて要約し、情報を省略することなく、1つの一貫性のあるテキストにまとめてください。どちらのテキストにも記載されているすべての詳細を含める必要があります。説明や分析は不要で、結合された要約のみを返してください。代名詞や主観的な言葉は使用せず、提示された事実のみを記載してください。\n{merged_text}"""

    # 記憶関係検出プロンプト（日本語版） MEMORY_RELATION_DETECTOR_PROMPT
    MEMORY_RELATION_DETECTOR_PROMPT_JP = """
        "あなたは記憶関係分析者です。\n"
        "2つのプレーンテキスト文が与えられます。それらの関係を判断し、以下のいずれかのカテゴリーに分類してください。：\n"
        "\n"
        "contradictory：2つの文は同じ出来事またはその関連する側面について記述していますが、事実上矛盾する詳細が含まれています。\n"
        "redundant：2つの文は本質的に同じ出来事または情報を記述していますが、内容と詳細にかなりの重複があり、同じ核となる情報を伝えています（表現が異なっていても）\n"
        "independent：2つの文は、異なる出来事／トピックについて記述している（無関係）か、同じ出来事について矛盾なく異なる側面または視点について記述している（補完的）。どちらの場合も、矛盾なく異なる情報を提供しています。\n"
        "\n"
        "3つのラベルの1つのみで回答してください：contradictory、redundant、またはindependent。\n"
        "説明や追加のテキストは提供しないでください。\n"
        "\n"
        "文1：{statement_1}\n"
        "文2：{statement_2}\n"
        """

    # 記憶関係解決プロンプト（日本語版） MEMORY_RELATION_RESOLVER_PROMPT
    MEMORY_RELATION_RESOLVER_PROMPT_JP = """
        "あなたは記憶融合の専門家です。2つの文とそれらに関連するメタデータが与えられます。文は{relation}として識別されています。メタデータ（時間、ソース、信頼度など）を考慮してそれらを注意深く分析し、統合された情報を最適に表現する単一のまとまりのある包括的な文を作成することが任務です。\n"
        "\n"
        "文が冗長である場合は、すべてのユニークな詳細を保持し、重複を除去してより豊かで統合されたバージョンを形成してマージしてください。\n"
        "文が対立している場合は、より最新の情報、より高い信頼度のデータを優先するか、コンテキストに基づいて論理的に違いを調整して対立を解決しようと試みてください。対立が根本的で論理的に解決できない場合は、<answer>No</answer>を出力してください。\n"
        "説明、推論、追加のテキストは含めないでください。最終結果のみを<answer></answer>タグで囲んで出力してください。\n"
        "できる限り事実的内容、特に時間固有の詳細を保持するよう努めてください。\n"
        "客観的言語を使用し、代名詞は避けてください。\n"
        "\n"
        "出力例1（解決不可能な対立）：\n"
        "<answer>No</answer>\n"
        "\n"
        "出力例2（成功した融合）：\n"
        "<answer>会議は更新されたスケジュールで確認された通り2023-10-05の14:00にメイン会議室で行われ、プロジェクトマイルストーンに関するプレゼンテーションとQ&Aセッションが含まれた。</answer>\n"
        "\n"
        "以下の2つの文を調整してください：\n"
        "関係タイプ：{relation}\n"
        "文1：{statement_1}\n"
        "メタデータ1：{metadata_1}\n"
        "文2：{statement_2}\n"
        "メタデータ2：{metadata_2}\n"
        """

    # ====== Memory Scheduler Prompts 日本語版 ======
    
    # インテント認識プロンプト（日本語版） INTENT_RECOGNIZING_PROMPT
    INTENT_RECOGNIZING_PROMPT_JP = """
        "# ユーザー意図認識タスク\n"
        "\n"
        "## 役割\n"
        "あなたは、回答満足度を評価し、情報ギャップを特定する高度な意図分析システムです。\n"
        "\n"
        "## 入力分析\n"
        "以下を受け取ります：\n"
        "1. ユーザーの質問リスト（時系列順）\n"
        "2. 現在のシステム知識（ワーキングメモリ）\n"
        "\n"
        "## 評価基準\n"
        "以下の満足度要因を考慮してください：\n"
        "1. 回答の完全性（質問のすべての側面をカバー）\n"
        "2. 証拠の関連性（回答を直接サポート）\n"
        "3. 詳細の具体性（必要な粒度を含む）\n"
        "4. パーソナライゼーション（ユーザーのコンテキストに合わせて調整）\n"
        "\n"
        "## 決定フレームワーク\n"
        "1. 以下の場合にのみ、十分な情報が得られている（満足）と判断されます:\n"
        "   - 質問のすべての側面が回答されている\n"
        "   - 裏付けとなる証拠がワーキングメモリに存在する\n"
        "   - 明白に欠けている情報がない\n"
        "\n"
        "2. 以下の場合は、さらに情報が必要である（不満足）と判断されます:\n"
        "   - 質問のいずれかの側面が未回答である\n"
        "   - 証拠が一般的/非具体的である\n"
        "   - 個人のコンテキストが不足している\n"
        "\n"
        "## 出力仕様\n"
        "以下を含むJSONを返す：\n"
        "- "trigger_retrieval": true/false（より多くの情報が必要な場合はtrue）\n"
        "- "evidences": 質問に答えるのに役立つワーキングメモリからの情報のリスト\n"
        "- "missing_evidences": 質問に答えるために必要な具体的な情報のリスト\n"
        "\n"
        "## 応答形式\n"
        "{{\n"
        "  "trigger_retrieval": <ブール値>,\n"
        "  "evidences": [\n"
        "    "<有用な証拠1>",\n"
        "    "<有用な証拠2>"\n"
        "    ],\n"
        "  "missing_evidences": [\n"
        "    "<証拠タイプ1>",\n"
        "    "<証拠タイプ2>"\n"
        "  ]\n"
        "}}\n"
        "\n"
        "## 証拠タイプの例\n"
        "- 個人的な医療履歴\n"
        "- 最近の活動ログ\n"
        "- 特定の測定データ\n"
        "- [トピック]に関する文脈詳細\n"
        "- 時間的情報（何かが発生した時期）\n"
        "\n"
        "## 現在のタスク\n"
        "ユーザーの質問：\n"
        "{q_list}\n"
        "\n"
        "ワーキングメモリの内容：\n"
        "{working_memory_list}\n"
        "\n"
        "## 必要な出力\n"
        "指定されたJSON形式で分析を出力してください：\n"
        """

    # 記憶再ランキングプロンプト（日本語版） MEMORY_RERANKING_PROMPT
    MEMORY_RERANKING_PROMPT_JP = """
        "# 記憶再ランキングタスク\n"
        "\n"
        "## 役割\n"
        "あなたはインテリジェントな記憶再編成システムです。主要機能は、最近のユーザークエリとの関連性に基づいて記憶証拠の順序を分析・最適化することです。\n"
        "\n"
        "## タスク説明\n"
        "以下を行って提供された記憶証拠リストを再編成してください：\n"
        "1. 各証拠項目とユーザークエリの間の意味的関係を分析\n"
        "2. 関連性スコアを計算\n"
        "3. 関連性の降順で証拠をソート\n"
        "4. すべての元項目を維持（追加や削除なし）\n"
        "\n"
        "## 時間的優先ルール\n"
        "- クエリの新しさが重要：インデックス0が最新のクエリ\n"
        "- 最近のクエリにマッチする証拠がより高い優先度を得る\n"
        "- 同等の関連性スコアの場合：新しいクエリにマッチする項目を優先\n"
        "\n"
        "## 入力形式\n"
        "- クエリ：最近のユーザー質問/リクエスト（リスト）\n"
        "- 現在の順序：既存の記憶シーケンス（インデックス付き文字列のリスト）\n"
        "\n"
        "## 出力形式要件\n"
        "以下の構造で有効なJSONオブジェクトを出力する必要があります：\n"
        "{{\n"
        "  "new_order": [整数の配列],\n"
        "  "reasoning": "文字列の説明"\n"
        "}}\n"
        "\n"
        "## 重要な注意事項：\n"
        "- JSONオブジェクトのみを出力、他は何も出力しない\n"
        "- マークダウンフォーマットやコードブロック記法を含めない\n"
        "- すべての括弧と引用符を適切に閉じることを確認\n"
        "- 出力はJSONパーサーで解析可能でなければならない\n"
        "\n"
        "## 処理ガイドライン\n"
        "1. 以下の証拠を優先する：\n"
        "   - クエリの質問に直接答えている\n"
        "   - キーワードと完全に一致する\n"
        "   - 文脈的な裏付けがある\n"
        "   - 時間的関連性を示す（新しい > 古い）\n"
        "2. 曖昧なケースでは、元の相対順序を維持\n"
        "\n"
        "## スコア付け優先度（降順）\n"
        "1. 新しいクエリへの直接一致\n"
        "2. 最近のクエリでキーワードが完全に一致する\n"
        "3. 最近のトピックの文脈的な裏付けがある\n"
        "4. 古いクエリとの一般的な関連性\n"
        "\n"
        "## 例\n"
        "入力クエリ：["[0] python threading", "[1] data visualization"]\n"
        "入力順序：["[0] syntax", "[1] matplotlib", "[2] threading"]\n"
        "\n"
        "出力：\n"
        "{{\n"
        "  "new_order": [2, 1, 0],\n"
        "  "reasoning": "最新のクエリに一致する場合はThreading (2) を優先し、古い可視化クエリの場合はmatplotlib (1) を優先します。"\n"
        "}}\n"
        "\n"
        "## 現在のタスク\n"
        "クエリ：{queries}（最新順）\n"
        "現在の順序：{current_order}\n"
        "\n"
        "再編成を提供してください:\n"
        """

    # クエリキーワード抽出プロンプト（日本語版） QUERY_KEYWORDS_EXTRACTION_PROMPT
    QUERY_KEYWORDS_EXTRACTION_PROMPT_JP = """
        "## 役割\n"
        "あなたはインテリジェントなキーワード抽出システムです。あなたのタスクは、ユーザーのクエリから最も重要な単語または短いフレーズを識別して抽出することです。\n"
        "\n"
        "## 指示\n"
        "- 意味のある単一の単語または短いフレーズでなければならない。\n"
        "- 名詞（名称）または動詞（動作語）のみが許可される。\n"
        "- ストップワード（「は」「です」など）や副詞（動詞を説明する語、「速く」など）は含めない。\n"
        "- 意味が維持される最小単位にしてください。\n"
        "\n"
        "## 例\n"
        "- 入力クエリ：「マックスはどの犬種ですか？」\n"
        "- 出力キーワード（文字列のリスト）：["犬種", "マックス"]\n"
        "\n"
        "## 現在のタスク\n"
        "- クエリ：{query}\n"
        "- 出力形式：キーワードのJsonリスト\n"
        "\n"
        "回答：\n"
        """
    
    def __init__(self, default_config=None, max_user_instances=1, system_prompt_provider: Optional[Callable[[], Optional[str]]] = None):
        """
        初期化
        
        Args:
            default_config: MemOSデフォルト設定
            max_user_instances: 最大ユーザーインスタンス数
            system_prompt_provider: CocoroAIシステムプロンプト取得関数
        """
        super().__init__(default_config=default_config, max_user_instances=max_user_instances)
        self.system_prompt_provider = system_prompt_provider
        logger.info("CocoroMOSProduct初期化完了")
    
    def _build_enhance_system_prompt(
        self, user_id: str, memories_all: List[TextualMemoryItem]
    ) -> str:
        """
        CocoroAI専用システムプロンプト構築
        
        Args:
            user_id: ユーザーID
            memories_all: 検索されたメモリアイテムリスト
            
        Returns:
            str: 構築されたシステムプロンプト
        """
        # CocoroAIのシステムプロンプトを取得
        cocoro_prompt = None
        if self.system_prompt_provider:
            try:
                cocoro_prompt = self.system_prompt_provider()
                logger.info(f"CocoroAIシステムプロンプト取得成功: {bool(cocoro_prompt)}")
            except Exception as e:
                logger.error(f"CocoroAIシステムプロンプト取得エラー: {e}")
        
        # フォールバック: CocoroAIプロンプトが取得できない場合は元のMemOSプロンプトを使用
        if not cocoro_prompt:
            logger.error("CocoroAIプロンプト未設定")
            return
        
        # メモリ情報の追加処理（MemOSの標準フォーマットに従う）
        if memories_all:
            personal_memory_context = "\n\n## Available ID and PersonalMemory Memories:\n"
            outer_memory_context = "\n\n## Available ID and OuterMemory Memories:\n"
            
            personal_memory_count = 0
            outer_memory_count = 0
            
            for i, memory in enumerate(memories_all, 1):
                # メモリIDとコンテンツの取得（MemOSと同じ形式）
                memory_id = (
                    f"{memory.id.split('-')[0]}" if hasattr(memory, "id") else f"mem_{i}"
                )
                memory_content = (
                    memory.memory[:500] if hasattr(memory, "memory") else str(memory)
                )
                
                # メモリタイプ別に分類
                if memory.metadata.memory_type != "OuterMemory":
                    personal_memory_context += f"{memory_id}: {memory_content}\n"
                    personal_memory_count += 1
                else:
                    # OuterMemoryの場合は改行を除去
                    memory_content = memory_content.replace("\n", " ")
                    outer_memory_context += f"{memory_id}: {memory_content}\n"
                    outer_memory_count += 1
            
            # 記憶がある場合は、CocoroAIプロンプト + 記憶機能指示 + メモリ情報
            memory_sections = ""
            if personal_memory_count > 0:
                memory_sections += personal_memory_context
            if outer_memory_count > 0:
                memory_sections += outer_memory_context
            
            result_prompt = cocoro_prompt + self.COCORO_MEMORY_INSTRUCTION + memory_sections
            logger.info(f"システムプロンプト構築完了: CocoroAI + 記憶指示 + メモリ情報 (PersonalMemory: {personal_memory_count}, OuterMemory: {outer_memory_count})")
            return result_prompt
        
        # メモリがない場合はCocoroAIプロンプトのみ（記憶指示不要）
        logger.info("システムプロンプト構築完了: CocoroAIプロンプトのみ")
        return cocoro_prompt
    
    def chat_with_references(
        self,
        query: str,
        user_id: str,
        cube_id: str,
        history=None,
        internet_search: bool = False,
        **kwargs
    ):
        """
        CocoroAI専用chat_with_references - 遅延なし版
        
        親クラスの実装を参考に、最後の同期的なself.addを非同期化
        """
        import json
        import time
        import threading
        from datetime import datetime
        
        logger.info(f"CocoroAI chat_with_references開始: user_id={user_id}, cube_id={cube_id}")
        logger.info("*** 独自実装のchat_with_referencesが呼び出されました ***")
        
        # 親クラスと同じ処理フロー（ただし最後のaddを非同期化）
        self._load_user_cubes(user_id, self.default_config)
        time_start = time.time()
        memories_list = []
        
        # ステータス送信
        yield f"data: {json.dumps({'type': 'status', 'data': '0'})}\n\n"
        
        # 記憶検索
        memories_result = super(MOSProduct, self).search(
            query,
            user_id,
            install_cube_ids=[cube_id] if cube_id else None,
            top_k=kwargs.get('top_k', 10),
            mode="fine",
            internet_search=internet_search
        )["text_mem"]
        
        yield f"data: {json.dumps({'type': 'status', 'data': '1'})}\n\n"
        
        # スケジューラーへ通知
        self._send_message_to_scheduler(
            user_id=user_id, mem_cube_id=cube_id, query=query, label="QUERY"
        )
        
        if memories_result:
            memories_list = memories_result[0]["memories"]
            memories_list = self._filter_memories_by_threshold(memories_list)
        
        # システムプロンプト構築（CocoroAI版使用）
        system_prompt = self._build_enhance_system_prompt(user_id, memories_list)
        
        # チャット履歴管理
        if user_id not in self.chat_history_manager:
            self._register_chat_history(user_id)
        
        chat_history = self.chat_history_manager[user_id]
        if history:
            chat_history.chat_history = history[-10:]
        
        current_messages = [
            {"role": "system", "content": system_prompt},
            *chat_history.chat_history,
            {"role": "user", "content": query},
        ]
        
        yield f"data: {json.dumps({'type': 'status', 'data': '2'})}\n\n"
        
        # LLM応答生成
        logger.info(f"LLM応答生成開始: backend={self.config.chat_model.backend}")
        if self.config.chat_model.backend in ["huggingface", "vllm"]:
            response_stream = self.chat_llm.generate_stream(current_messages)
        else:
            response_stream = self.chat_llm.generate(current_messages)
        
        logger.info("ストリーミング処理開始")
        # ストリーミング処理
        buffer = ""
        full_response = ""
        
        chunk_count = 0
        for chunk in response_stream:
            chunk_count += 1
            if chunk in ["<think>", "</think>"]:
                continue
            buffer += chunk
            full_response += chunk
            
            # バッファ処理（親クラスと同じ）
            from memos.mem_os.utils.reference_utils import process_streaming_references_complete
            processed_chunk, remaining_buffer = process_streaming_references_complete(buffer)
            
            if processed_chunk:
                chunk_data = f"data: {json.dumps({'type': 'text', 'data': processed_chunk}, ensure_ascii=False)}\n\n"
                yield chunk_data
                buffer = remaining_buffer
        
        logger.info(f"ストリーミング処理完了: chunk_count={chunk_count}, full_response_length={len(full_response)}")
        
        # 残りのバッファ処理
        if buffer:
            from memos.mem_os.utils.reference_utils import process_streaming_references_complete
            processed_chunk, _ = process_streaming_references_complete(buffer)
            if processed_chunk:
                chunk_data = f"data: {json.dumps({'type': 'text', 'data': processed_chunk}, ensure_ascii=False)}\n\n"
                yield chunk_data
        
        # 参照データ準備
        reference = []
        for memory in memories_list:
            memory_json = memory.model_dump()
            memory_json["metadata"]["ref_id"] = f"{memory.id.split('-')[0]}"
            memory_json["metadata"]["embedding"] = []
            memory_json["metadata"]["sources"] = []
            memory_json["metadata"]["memory"] = memory.memory
            memory_json["metadata"]["id"] = memory.id
            reference.append({"metadata": memory_json["metadata"]})
        
        yield f"data: {json.dumps({'type': 'reference', 'data': reference})}\n\n"
        
        # タイミング情報
        time_end = time.time()
        speed_improvement = round(float((len(system_prompt) / 2) * 0.0048 + 44.5), 1)
        total_time = round(float(time_end - time_start), 1)
        
        yield f"data: {json.dumps({'type': 'time', 'data': {'total_time': total_time, 'speed_improvement': f'{speed_improvement}%'}})}\n\n"
        yield f"data: {json.dumps({'type': 'end'})}\n\n"
        
        logger.info(f"ストリーミング完了 - 記憶保存処理を開始します: full_response_length={len(full_response)}")
        
        # 参照抽出
        clean_response, extracted_references = self._extract_references_from_response(full_response)
        logger.info(f"参照抽出完了: clean_response_length={len(clean_response)}, extracted_refs={len(extracted_references)}")
        
        # スケジューラーへ応答通知
        self._send_message_to_scheduler(
            user_id=user_id, mem_cube_id=cube_id, query=clean_response, label="ANSWER"
        )
        
        # ========== ここが重要：記憶保存を非同期化 ==========
        def async_memory_save():
            """バックグラウンドで記憶保存"""
            try:
                logger.info(f"非同期記憶保存開始: user_id={user_id}, cube_id={cube_id}")
                
                messages = [
                    {
                        "role": "user",
                        "content": query,
                        "chat_time": str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    },
                    {
                        "role": "assistant",
                        "content": clean_response,
                        "chat_time": str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    },
                ]
                
                logger.info(f"記憶保存データ準備完了: messages={len(messages)}件")
                
                # 正しいaddメソッド呼び出し（MOSCoreクラスの継承チェーン）
                MOSProduct.add(self, 
                    user_id=user_id,
                    messages=messages,
                    mem_cube_id=cube_id
                )
                
                logger.info(f"非同期記憶保存完了: user_id={user_id}, cube_id={cube_id}")
                
            except Exception as e:
                logger.error(f"非同期記憶保存エラー: {e}", exc_info=True)
        
        # 別スレッドで記憶保存実行（daemon=False で安全性向上）
        save_thread = threading.Thread(target=async_memory_save, daemon=False)
        save_thread.start()
        
        # オプション：スレッド参照を保持（デバッグ用）
        if not hasattr(self, '_memory_save_threads'):
            self._memory_save_threads = []
        self._memory_save_threads.append(save_thread)
        
        logger.info(f"chat_with_references完了（記憶保存は非同期実行中）: cube_id={cube_id}")
    
    def get_suggestion_query(self, user_id: str, language: str = "ja"):
        """
        CocoroAI専用サジェスチョンクエリ生成（日本語専用）
        
        Args:
            user_id: ユーザーID
            language: 言語コード（"ja"のみサポート）
            
        Returns:
            list: サジェスチョンクエリのリスト
        """
        import json
        
        logger.info(f"サジェスチョンクエリ生成開始: user_id={user_id}")
        
        try:
            # ユーザーの最近の記憶を取得
            memories_result = super().search(
                "my recently memories", 
                user_id=user_id, 
                top_k=3
            )
            
            memories = ""
            if memories_result and "text_mem" in memories_result:
                text_mem = memories_result["text_mem"]
                if text_mem and len(text_mem) > 0 and "memories" in text_mem[0]:
                    memories_list = text_mem[0]["memories"][:3]  # 最大3件
                    memories = "\n".join([mem.memory if hasattr(mem, 'memory') else str(mem) 
                                        for mem in memories_list])
            
            # 日本語プロンプトを使用
            suggestion_prompt = self.COCORO_SUGGESTION_PROMPT_JP.format(memories=memories)
            
            # LLMに問い合わせ
            messages = [{"role": "user", "content": suggestion_prompt}]
            response = self.chat_llm.generate(messages)
            
            logger.info(f"LLM応答取得: response_length={len(response)}")
            
            # JSONレスポンスの解析
            try:
                # clean_json_response相当の処理
                clean_response = response.strip()
                if clean_response.startswith("```json"):
                    clean_response = clean_response[7:]
                if clean_response.endswith("```"):
                    clean_response = clean_response[:-3]
                clean_response = clean_response.strip()
                
                result = json.loads(clean_response)
                suggestions = result.get("query", [])
                
                logger.info(f"サジェスチョン生成成功: count={len(suggestions)}")
                return suggestions
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析エラー: {e}, response={response}")
                # フォールバック: デフォルトサジェスチョン
                return ["今日の調子はいかがですか？", "何か気になることはありますか？", "お手伝いできることはありますか？"]
                    
        except Exception as e:
            logger.error(f"サジェスチョンクエリ生成エラー: {e}", exc_info=True)
            # エラー時のフォールバック
            return ["今日の調子はいかがですか？", "何か気になることはありますか？", "お手伝いできることはありますか？"]