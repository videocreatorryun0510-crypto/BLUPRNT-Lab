# Phase 5.28 Evidence-Grounded Claim Builder MVP

## 目的

人が採用したFormal Evidenceだけから、追跡可能なClaim候補をAIで抽出します。AIは医学的な正解を決めず、候補・根拠・支持度を提示します。正式Claim、Promotion、Approvalは作りません。

```text
医療用語
  ↓
PubMed Formal Evidence
  ↓ 人が採用
Formal Evidence Selection Set
  ↓
Provider-neutral Claim Generation Request
  ↓
LLM Claim Adapter
  ↓
Claim Candidate + Support Assessment + Source Locator
  ↓ Validation
Human Claim Review
  ↓ accepted かつ direct のみ
Authoring Draft
```

Discovery Candidate、除外Evidence、保留Evidence、未確認URLは入力できません。

## Claim Candidate Contract 1.0

Candidateは正式Claimと明確に分離します。

- `candidate_claim_id`：候補専用の一時ID
- `knowledge_term`、`claim_text`、`claim_type`
- `supporting_evidence_ids`
- `source_locators`：Abstract内の短い抜粋、PMID、DOI
- `support_level`、`support_scope`、`support_assessment`
- `confidence`：AI自身の確信度。Evidenceの支持度とは別
- `generator_id`、`generator_version`、`generated_at`
- `candidate_fingerprint`
- `duplicate_assessment`

`formal_claim_id_issued`は常に`false`です。正式Claim IDは、人の判断後にAuthoring Draftへ採用する段階で別途発行します。

## Evidence入力Gate

Claim生成へ入るのは次をすべて満たすEvidenceだけです。

1. PubMed Formal Evidenceである
2. Evidence Bundle内に存在する
3. 人の最新判断が`include`である
4. Bundle Fingerprintが維持されている

Selection SetにはDiscovery、excluded、pendingを含まないことを固定値と指紋で保証します。AIに渡すEvidenceは最大10件です。

## Claim Support Assessment

| Level | 意味 | MVPのDraft採用 |
|---|---|---|
| direct | Claim全体をEvidenceが直接支持 | 人が採用した場合のみ可 |
| partial | Claimの一部だけ支持 | 不可 |
| indirect | 関連するが直接断定できない | 不可 |
| unsupported | 支持できない | 不可・候補として隔離 |
| conflicting | Evidence間に相違がある | 不可・人へ相違を表示 |

AI Confidenceは抽出結果へのAIの自己評価であり、Evidence Supportでも医学承認でもありません。

## Source Locatorと引用

PubMed MVPではAbstract内の位置、PMID、DOI、必要最小限の短い抜粋を保持します。抜粋は最大25語・240文字です。長い引用や全文はKnowledge、Registry、Auditへ保存しません。

Validatorは次を検査します。

- 選択されていないEvidence IDの参照
- 抜粋がAbstractに存在するか
- LocatorのPMID・DOIがEvidenceと一致するか
- Support LevelとScopeの整合性
- Candidate ID重複とFingerprint
- Provider固有フィールドの混入

通信成功とValidation成功は別です。架空Evidence ID、Locator不一致、Fingerprint不一致は保存前に停止します。

## 重複と矛盾

同一Candidate Setおよび既存Registry Claimを、完全一致と保守的な文字列類似でPreviewします。

- `exact_duplicate`
- `possible_duplicate`
- `distinct`

自動Mergeは行いません。`conflicting`もAIが解決せず、Evidence IDと相違点を人へ提示します。

## Human Claim Review

WorkbenchからCandidateごとに採用・修正・除外・保留を記録します。操作者、日時、コメント、確認時間、AI原文、人の修正文を追記専用JSONLへ保存します。修正したClaimは、MVPでは支持度の再評価がないためDraftへ自動採用しません。

## Authoring Draft接続

最新の人判断が`accepted`かつSupportが`direct`のCandidateだけを既存Authoring Draftへ保存します。Referenceは既存Reference Builderを再利用し、PubMed Metadataからだけ生成します。架空Referenceは作れません。

この操作はPromotion、Registry登録、医学レビュー、Approvalを実行しません。

## Provider Neutral境界

Prompt Builder、Claim Generation Request、Candidate、Support Assessment、Validator、WorkbenchはProviderに依存しません。Gemini固有の処理はAdapter内だけです。

- Interactions API RequestとStructured Output Schema
- `store=false`
- Token Usage
- Timeout、認証、429、5xx、Network、JSON Errorの変換
- 最大1回のRetry

将来ClaudeまたはOpenAIを追加する場合は、同じAdapter Interfaceを実装します。後段ContractとWorkbenchは変更しません。

## AuditとKPI

Claim Generation AuditにはID、件数、Provider、Model、所要時間、Token Usage、Error Codeだけを保存します。医学本文、Abstract、短い抜粋、API Keyは保存しません。

測定項目はEvidence取得時間、Claim生成時間、Candidate数、Direct率、Unsupported率、人の修正率・除外率、確認時間です。MVPでは後半3項目を個別Review履歴から集計できる状態までとし、集約表示は今後の課題です。

## Workbenchの確認順

1. 医療用語を入力
2. PubMed正式Evidence検索
3. 使用するEvidenceを「採用」
4. 「選択EvidenceからClaim候補生成」
5. Claim、PMID/DOI、Locator、Support、Confidence、重複、Validationを確認
6. 採用・修正・除外・保留を記録
7. 採用済みDirect ClaimだけをAuthoring Draftへ保存

画面では常に`AI Generated Candidate: Yes / Medical Approval: No / Registry Changed: No / Promotion: No`を表示します。

## 実装しないもの

- DiscoveryからのClaim生成
- Evidence自動採用
- 自動Category分類
- 自動Promotion・Approval
- AI Medical Review
- PMC全文、PMDA、MHLW、J-STAGE Provider
- Renderer、Notion連携
