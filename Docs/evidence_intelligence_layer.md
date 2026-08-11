# Phase 5.25 Evidence Intelligence Layer MVP

## 目的

Evidence Intelligence Layerは、PubMed、J-STAGE、PMDA、厚生労働省、学会、WHOなど、形式の異なる検索元を、Claim Builderが安全に利用できる1つの形式へ変換する境界です。

```text
Search Provider
  ↓ Provider固有・内部限定
Raw Evidence
  ↓
Evidence Normalizer
  ↓ 共通Contract 1.0
Normalized Evidence
  ↓
Evidence Deduplicator
  ↓
Evidence Ranker
  ↓ 唯一の後段入力
Evidence Bundle 1.0
  ↓
Claim Builder / Workbench
```

Raw EvidenceはProvider AdapterとNormalizerの内側だけで扱い、Workbench、Claim Builder、Knowledge Builderへ渡しません。

## 共通Evidence Contract 1.0

NormalizerはProvider固有データを次の共通項目へ変換します。

- 資料名、発行団体、資料種別、Evidence Level
- 発行日、URL、DOI、PMID、言語
- AbstractまたはSnippet、取得日時
- 取得Provider名・版・Provider側Record ID
- Information Priority、整形済みCitation

`evidence_id`はDOI、PMID、正規化URL、資料名等から安定生成します。Providerが変わっても同じ根拠を同じ資産として扱えるようにするためです。

## 重複排除

次の順に同一Evidence候補を照合します。

1. DOI一致
2. PMID一致
3. クエリ等を除いたURL一致
4. 正規化した資料名の一致・高い類似度

統合時は1件を残し、取得元Providerの履歴をすべて保持します。除外したProvider Record IDと統合理由もBundleへ残します。医学的内容が似ているという理由だけでは統合しません。

## 順位付け

第一基準はEvidence Levelです。

```text
Level A → Level B → Level C
```

Information Priorityは別の概念で、同じEvidence Level内の補助基準としてだけ使います。Evidence Levelは根拠の強さ、Information Priorityはプロジェクトが定める情報取得優先順位を表すため、1つの点数へ混ぜません。

## Evidence Bundle 1.0

Evidence BundleはClaim BuilderとWorkbenchへ渡す唯一のEvidence形式です。主に次を保持します。

- Bundle ID、対象用語、Category、生成日時、Fingerprint
- 利用Provider一覧
- 順位付きの標準Evidence
- 入力、標準化、採用、除外件数
- 重複統合結果と除外Record ID
- 外部検索実施有無、処理時間、Warning

Bundle Fingerprintは医学的内容と出典・順位から決定的に作り、取得時刻の違いだけでは変わりません。

## Search Audit

追記専用JSONLへ次だけを保存します。

- Search Query、Provider別取得件数
- 採用Evidence ID、除外Provider Record ID
- 検索日時、所要時間、成功・失敗

資料本文、Snippet、Claim本文、Citation本文は保存しません。監査記録から検索の実行事実と件数は追えますが、医学本文が複製されない設計です。

## Workbenchでの確認

「AI Knowledge Wizard」で対応テーマを入力し、「Draft Preview生成」を押します。

1. Evidence Previewで標準化後の資料を確認する
2. Evidence RankingでA/B/Cと順位を確認する
3. Evidence Bundleで採用・除外件数、Provider、Fingerprint、JSON全文を確認する
4. Raw Evidenceが表示されないことを確認する
5. ClaimとReferenceを確認し、必要な場合だけAuthoring Draftへ保存する

MVPはローカルFixtureだけを使い、外部検索、LLM、Promotion、Registry、Review、Approvalを実行しません。

## 新しいProviderを追加するとき

Providerごとに追加するのは、検索・認証とRaw Evidenceから共通ContractへのNormalizerです。Deduplicator、Ranker、Bundle、Claim Builder境界、Workbenchは再利用します。

Provider追加時は、利用規約、Rate Limit、キャッシュ、取得失敗、失効、引用可能範囲、秘密情報、個人情報を別途確認します。

## 今回実装していないもの

- PubMed、J-STAGE、PMDA、Web検索等の実接続
- Evidence Levelの自動医学評価
- LLMによるClaim生成
- DOI等がない資料に対する高度な同一性判定
- Evidenceの改訂・撤回監視
- Search Auditの長期保存・削除Policy
