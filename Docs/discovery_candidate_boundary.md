# Phase 5.26.1 Discovery Candidate Boundary

## 目的

Discovery（探索候補）とEvidence（正式根拠）を、名称だけでなくContract、Provider Interface、Validation、Workbenchで完全に分離します。

```text
Medical Term
  ↓
Discovery Provider（Gemini Grounding）
  ↓
Discovery Candidate Set
  ↓ 人が候補を選ぶ
Formal Evidence Provider（将来）
  ↓
Raw Evidence → Normalize → Evidence Bundle
  ↓
Claim Builder
```

Gemini経路はDiscovery Candidate Setで必ず停止します。Evidence Normalizer、Evidence Deduplicator、Evidence Ranker、Evidence Bundle Builder、Claim Builderは呼びません。

## Discovery Candidate Contract 1.0

各候補は次を保持します。

- Candidate ID、Provider名・版、検索語
- Title、URL、Publisher、Domain、Snippet
- 取得日時、Citation由来のProvider Metadata
- Discovery Fingerprint

次の安全フラグは`false`以外をSchemaが受け付けません。

```text
claim_eligible = false
evidence_bundle_eligible = false
promotion_allowed = false
registry_allowed = false
approval_allowed = false
```

Candidate Setにも同じ禁止フラグを持たせます。個別候補だけを取り出して誤接続する場合と、Setごと誤接続する場合の両方を停止するためです。

## 型分離

`DiscoveryCandidate`と`DiscoveryCandidateSet`は、`NormalizedEvidence`および`EvidenceBundle`を継承しません。ID Prefixも分離します。

| 資産 | ID Prefix | 用途 |
|---|---|---|
| Discovery Candidate | `dsc_` | 人へ探索候補を提示 |
| Discovery Candidate Set | `dcs_` | 1回の探索結果 |
| Formal Evidence | `evd_` | 正式Providerから取得した根拠 |
| Evidence Bundle | `evb_` | Claim Builderへ渡す正式根拠集合 |

既存Claim Builderは`EvidenceBundle`だけを入力とするため、Discovery型は静的型検査でも渡せません。Pydantic SchemaでもDiscovery JSONをEvidence Bundleとして読み込めません。

## 境界Validation

`DiscoveryBoundaryTarget`は次の禁止先を固定します。

- `evidence_bundle`
- `claim_builder`
- `promotion`
- `registry`
- `approval`

Discovery資産をいずれかへ渡すと`DiscoveryBoundaryValidationError`になり、専用Evidence Providerで正式取得するよう停止理由を返します。型制約に加え、実行時にもFail Closedとする二重防御です。

## Provider Interface

探索用`DiscoveryProvider`は次だけを返します。

```text
discover(DiscoverySearchRequest) → DiscoveryCandidateSet
```

正式取得用`FormalEvidenceProvider`は別Interfaceです。

```text
acquire(FormalEvidenceAcquisitionRequest) → RawEvidenceSearchResult
```

対象Providerの識別子は`pubmed`、`pmc`、`pmda`、`mhlw`、`j_stage`を定義しました。今回はInterfaceだけで、外部接続はありません。

## Workbench

画面表示は次の用語へ変更しました。

- `Gemini Discovery Search`
- `Discovery Results`
- `Discovery Candidate Set`
- `正式Evidenceではありません`

Title、Publisher、Domain、URL、Snippet、Search Queryを表示します。Evidence Level、Evidence Bundle、Claim、Knowledgeは表示しません。

候補ごとの「PubMedで正式Evidence取得」はPhase 5.27で有効になりました。このボタンはCandidateをEvidenceへ変換せず、PMID・DOI・Title等を検索HintとしてPubMedへ再問い合わせします。Geminiから直接Claimを作るボタンはありません。

## Phase 5.26互換性

新しい標準APIは`/api/discovery/gemini`です。Phase 5.26の次のURLも互換Aliasとして残します。

- `/api/evidence-search/gemini`
- `/api/evidence-search/gemini/previews`
- `/api/evidence-search/gemini/audit`
- `/api/schema/grounded-evidence-search-preview-1.0`

旧Preview URLもDiscovery Candidate Setだけを返し、Evidence Bundleは返しません。Migration Headerで新Contractを通知します。Phase 5.26の既存Auditは読み取り時に1.1形式へ変換しますが、Evidenceとして復元しません。

## 変更していないもの

- Knowledge Contract、Promotion、Registry、Approval
- Artifact、Renderer、Publisher Core
- Phase 5.25の正式Evidence BundleとClaim Builder経路
- Gemini認証、Timeout、Retry、`store=false`、Citation抽出

## 次のPhase

Phase 5.27で最初のFormal Evidence ProviderとしてPubMed E-utilitiesを接続しました。次は、選択済みEvidenceだけを入力とするClaim Support Assessment境界を設計します。LLM Claim生成を先に接続してはいけません。
