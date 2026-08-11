# Phase 5.24 AI Knowledge Pipeline MVP

## 目的

AI Knowledge Pipelineは、利用者が入力した「テーマ・医療用語」を、確認・修正できるAuthoring Draftへ変換するための共通経路です。

```text
Theme
  ↓
Evidence Search Provider
  ↓
Evidence Ranking
  ↓
Claim Builder
  ↓
Reference Builder
  ↓
Knowledge Builder
  ↓
Authoring Draft Preview
  ↓ 人が明示的に保存
Authoring Draft Repository
```

このPhaseでは、外部検索APIとLLMは接続しません。既存のローカルKnowledge例をFixtureとして使い、各処理を交換可能なまま最後まで接続できることを確認します。

## 責務の分離

| コンポーネント | 担当 | 担当しないこと |
|---|---|---|
| Evidence Search Provider | 用語に対応するEvidenceを取得 | Claim作成、Knowledge保存 |
| Evidence Ranker | 情報源優先順位とEvidence Levelで並び替え | 医学的正誤の承認 |
| Claim Builder | Evidence IDを伴うClaim候補を返す | Reference変換、Registry登録 |
| Reference Builder | EvidenceをKnowledge Contract互換Referenceへ変換 | Claim本文の言い換え |
| Knowledge Builder | Category、Claim、ReferenceをAuthoring Draftへ組み立てる | Promotion、Approval |
| Workbench | Preview、確認、Authoring Draft保存 | 自動Promotion、自動承認 |

AI会社や検索サービスの固有処理は、Search Providerまたは将来のLLM Claim Builder Adapter内だけに置きます。Workbench、Knowledge Builder、Authoring Draft、Promotion、RegistryはProviderを知りません。

## Evidence Search Contract 1.0

EvidenceはProviderによらず次の共通形式へ変換します。

- `evidence_id`
- `title`
- `url`
- `publisher`
- `source_priority_rank`
- `evidence_level`
- `publication_date`
- `language`
- `evidence_type`
- `snippet`
- `citation`（整形済み書誌、DOI、PMID、版、章、ページ）

検索結果にはProvider名・Version、検索語、正規化された対象名・Category、検索日時、外部検索を行ったか、Warningも含みます。

Evidence Levelは情報源優先順位とは別の値です。今回のFixtureには正式なEvidence Level判定がないため、安全側に`C`としています。

## Evidence Ranking

初期Rankerは、プロジェクトで決めた情報源優先順位を先に見て、同順位の場合だけEvidence Levelと資料名で決定的に並べます。同じ入力で順番が変わらないため、Previewとテストを再現できます。

この点数は医学的正確性の点数ではなく、確認する順番を決めるための機械的な値です。

## Claim Builder Interface

Claim候補は次を返します。

- 安定して再現できる候補`claim_id`
- Evidenceから抽出した本文
- Claim Type
- Authoring上の保存先候補
- 根拠となるEvidence ID
- 抽出Confidence

今回のFixture Claim Builderは、既存Knowledge例のClaim本文をそのまま取り出します。LLMは呼ばず、言い換えや推測も行いません。将来のLLM BuilderもこのInterfaceを満たし、必ずEvidence IDを付けます。

## Reference Builder

Evidenceを既存Authoring Referenceへ変換し、対応Claim IDを保存します。

- Evidence Level
- Primary / Supporting
- 情報源優先順位
- 資料名・発行団体・年・版
- URL・DOI・PMID
- 章・ページ
- 支えるClaim ID

Knowledge Contract、Promotion、Registryの形式は変更していません。

## Knowledge Builder

既存Knowledge WizardのSkeleton生成を再利用し、Providerが返したCategory、正式名、Aliasを設定します。その後、ClaimとReferenceをAuthoring Draft側へ配置します。

生成直後は必ず次の状態です。

- Review：`draft`
- 医学レビュー：未実施
- Registry：未変更
- Promotion：未実施
- Approval：未実施

## Workbenchでの確認方法

1. 「AI Knowledge Wizard」へテーマを入力します。
2. 「Draft Preview生成」を押します。
3. Knowledge名、Category、Evidence、Claim、Reference、Providerを確認します。
4. `External / LLM`と`Registry / Promotion`が`No`であることを確認します。
5. Evidence Preview、Claim Preview、Reference PreviewとJSON全文を確認します。
6. 保存する場合だけ「Authoring Draftへ保存」を押します。
7. 保存後は既存のAuthoring画面で修正できます。正式Registryへは自動で進みません。

## Sandboxで確認できるテーマ

- フェリチン
- 鉄欠乏性貧血
- Gram染色

任意用語の医学情報を生成するには実Search ProviderとLLM Claim Builderが必要です。HbA1c、Howell-Jolly小体など未登録の用語を入力した場合は、Evidenceを捏造せず停止します。

## 保存と安全性

Previewはメモリ上にだけ保持し、Fingerprintを付けます。保存時にFingerprintを再確認し、Authoring Draft Repositoryへだけ保存します。同じPreviewの二重保存は拒否します。

正式Knowledge、Knowledge Registry、Approval Gate、Promotion、Artifact、Presentation、Publisherには変更を加えていません。

## 将来のProvider追加

次Phase以降では次を同じInterfaceへ接続できます。

- 厚生労働省・PMDA専用Provider
- PubMed・J-STAGE Provider
- Google Search Provider
- OpenAI Deep Research Provider
- Gemini Search Provider
- LLM Claim Builder（OpenAI / Gemini / Claude等）

Provider追加時に再利用する部分は、Evidence Contract、Ranker、Reference Builder、Knowledge Builder、Authoring Draft、Workbench保存境界です。追加が必要なのはProvider固有の認証・検索・応答変換と、LLM固有の通信Adapterです。

## 今回実装していないもの

- 実検索API
- LLMによるClaim生成
- Evidenceの医学的評価・自動Evidence Level判定
- 任意用語のCategory自動分類
- Promotion、Registry登録、Review、Approvalの自動化
- Web検索結果のキャッシュ、Rate Limit、Cost管理
