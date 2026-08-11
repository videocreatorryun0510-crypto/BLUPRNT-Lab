# Phase 5.26 Gemini Grounded Evidence Search Provider MVP

## 目的

Geminiを医学知識の作成者ではなく、Google Searchを利用する検索ProviderとしてEvidence Intelligence Layerへ接続します。採用対象は外部サイトのCitationだけです。Geminiが生成した回答本文は、Evidence、Claim、Knowledge Draft、監査ログのいずれにも保存しません。

```text
医療用語（人が明示入力）
  ↓
Search Query Builder（最大4 Intent）
  ↓
Gemini Grounded Search Provider（1操作、失敗時Retry最大1回）
  ↓ Citationだけ抽出／回答本文は破棄
Raw Evidence（内部限定）
  ↓
Evidence Normalizer → Deduplicator → Ranker
  ↓
Evidence Bundle 1.0
  ↓
Workbench Preview（Knowledge Draftは作らない）
```

## 公式APIとの対応

実装時点では、Gemini Interactions APIへ`google_search` Toolを指定します。状態を外部へ保存しないよう`store=false`を明示し、`model_output`の`url_citation` Annotationだけを外部Sourceとして抽出します。検索実行Queryは`google_search_call`から、TokenはUsage Metadataから取得可能な範囲で記録します。

- [Grounding with Google Search](https://ai.google.dev/gemini-api/docs/google-search)
- [Gemini API reference](https://ai.google.dev/api)
- [Zero Data Retention and `store=false`](https://ai.google.dev/gemini-api/docs/zdr)

モデルは`GEMINI_SEARCH_MODEL`で設定し、Provider内の1か所へ渡します。既定値は`gemini-3.6-flash`ですが、将来の変更は環境設定だけで行えます。

## Search Query Builder

1つの医療用語から次の最大4 Intentを作ります。

1. 定義・一般医学資料
2. ガイドライン・公的資料
3. 臨床検査・測定法
4. 臨床検査技師国家試験との関連

4つのQueryは1回のGrounded Search Requestへまとめます。国家試験Queryは学習資料候補の探索だけに使い、Web上の記述から出題実績を断定しません。入力は300文字、Intentは4件、Citation採用は50件を上限とします。

## Grounding Source抽出

Raw Evidenceへ保存するものは次のCitation Metadataです。

- URL、資料名、Publisher / Domain
- 取得日時、Provider名・版・Provider Result ID
- 生成Query、Citation位置情報
- Providerから明示された場合だけSnippet・発行日

Gemini回答本文、検索候補本文、HTTP Header、API Key、Webページ本文は保存しません。本文未取得の場合、共通Contract上は「Citation Metadataのみ取得」という状態を明示します。

## Domain分類とEvidence Level

ProviderはSourceを返すだけです。Sourceの評価はEvidence Intelligence側の許可リストPolicyで行います。

| Domain Class | 例 | MVPの扱い |
|---|---|---|
| Japan Official / Professional | 厚労省、PMDA、日本臨床検査医学会、日本臨床衛生検査技師会、J-STAGE | 公式ガイドライン相当ならA、それ以外はB |
| International Official | WHO、CDC、NIH、NCBI | 公式ガイドライン相当ならA、それ以外はB |
| Academic | PubMed、PMC、DOI、主要学術出版社 | B |
| Other | 未登録Domain | 安全側のC |

Evidence Levelと情報取得優先順位は混ぜません。Evidence Levelは資料候補としての根拠区分、Information PriorityはBLUPRNT Labの取得元優先順位です。Geminiの評価だけでAまたはBへ昇格することはありません。

## 重複排除

Phase 5.25のDeduplicatorを再利用し、DOI、PMID、正規化URL、資料名類似の順に同一候補を統合します。取得元のProvider Record IDは保持します。同名でも発行日または版が異なる資料は統合しない安全策を追加しました。Contractと呼び出し方法は変更していません。

## Search Audit

`data/search_audit/gemini_grounded_search.jsonl`へ次のMetadataだけを追記します。この場所はGit対象外です。

- Execution ID、入力用語、生成・実行Query
- Provider、Model、開始・完了時刻、Duration
- Raw、採用、除外、重複排除件数、Level A/B/C件数
- Request / Retry回数、取得できたToken Usage、Grounding利用有無
- 成否、Error Code

料金単価は変動し得るためコードへ固定せず、推定不能な場合は`null`です。

## Timeout・Retry・エラー

- Timeout：既定30秒、環境設定で変更可能
- Retry：Timeout、Network、429、5xxだけ最大1回
- Authentication、Request不正、Invalid Response、Citationなし：Retryせず停止
- 1操作あたりAPI Request 1回。上記一時障害時だけ合計2 Attemptまで

Workbenchへは分類済みError Codeと安全な日本語だけを返し、Providerの生エラーやHeaderを返しません。

## Workbenchでの操作

1. AI Knowledge Wizardへ医療用語を入力します。
2. 「実Evidence検索（Gemini）」を押します。この明示操作までは外部通信しません。
3. Provider、Model、Query、件数、Evidence Level、Title、Publisher、Domain、URL、取得日時を確認します。
4. Evidence Bundle JSONを確認します。
5. `External Search: Yes`、`LLM Claim Generation: No`、`Registry / Promotion: No / No`を確認します。

この操作はEvidence候補の探索であり、医学的承認ではありません。Draft Preview生成ボタンは従来のローカルSandboxで、実検索ボタンとは独立しています。

## 環境設定

秘密鍵は`.env`だけへ保存します。

```text
GEMINI_API_KEY=
GEMINI_SEARCH_MODEL=gemini-3.6-flash
GEMINI_SEARCH_TIMEOUT_SECONDS=30
GEMINI_SEARCH_MAX_QUERIES=4
GEMINI_SEARCH_MAX_SOURCES=50
```

`.env`と実Search AuditはGitへ含めません。

## 今回実装していないもの

- Citation先本文の取得・スクレイピング
- LLMによるClaim生成、Category自動分類
- Knowledge Draft、Promotion、Registry、Approvalへの自動接続
- PubMed、J-STAGE、PMDA、厚労省の専用Provider
- 複数Providerの並列検索、検索Cache、改訂・撤回監視
- Evidence候補の医学的承認
