# Medical Review Contract Version 1.0 — Design Proposal

- Phase: 5.21
- Status: Implemented by Phase 5.31
- Contract ID: `medical_review_contract_v1`

## 1. 責務

このContractは、特定のKnowledge VersionとClaim Version集合に対して、人がどの範囲を、どのChecklistとEvidence Policyで確認し、どのDecisionを出したかを表す。

Knowledge本文、Claim本文、Relation本文、Exam Metadata本文は保持しない。ID、Version、Fingerprint、判断、根拠評価、操作者情報だけを保持する。

## 2. Review Record

| 項目 | 必須 | 役割 |
|---|:---:|---|
| `contract_version` | ○ | Contract互換性。初期値`1.0` |
| `review_record_id` | ○ | Review記録の永続ID |
| `knowledge_id` | ○ | 対象Knowledge |
| `knowledge_version` | ○ | 対象の医学本文Version |
| `knowledge_fingerprint` | ○ | Review時点の改変検出 |
| `review_version` | ○ | Knowledge単位で単調増加する独立Review版 |
| `review_scope` | ○ | Knowledge、Claim、Category、利用目的、対象媒体 |
| `claim_snapshots` | ○ | 対象Claim ID、Key、Version、Fingerprint、Review結果 |
| `checklist` | ○ | Checklist ID、Version、各項目結果 |
| `evidence_policy` | ○ | Evidence Policy ID、Version |
| `evidence_assessments` | ○ | ClaimとEvidenceの支持関係、Level、適用範囲 |
| `temporal_assessment` | ○ | 有効期間、次回Review期限、時点依存性 |
| `reviewers` | ○ | 認証済みUser ID、Role、専門領域、資格確認 |
| `decision` | ○ | 独立Review Decision |
| `conditions` | ○ | 条件付き承認等の未解決条件。なければ空配列 |
| `comments` | ○ | 判断理由と修正指示 |
| `reviewed_at` | ○ | Review完了日時 |
| `valid_from` | ○ | Reviewの利用開始日時 |
| `review_due_at` | 条件付き | 時点依存または定期Review対象では必須 |
| `supersedes_review_version` | 任意 | 置き換えるReview Version |
| `created_at` / `created_by` | ○ | 監査情報 |

## 3. Review Scope

```json
{
  "scope_type": "knowledge_and_claims",
  "category": "staining_method",
  "purpose": "national_exam_education",
  "target_audience": "clinical_laboratory_technologist_candidates",
  "included_claim_ids": ["clm_example_001"],
  "excluded_claims": [],
  "relation_ids": [],
  "exam_metadata_version": null
}
```

Knowledgeを`approved`へ進めるReviewでは、現在版の全active Claimを`included_claim_ids`へ含める。`excluded_claims`があるReviewは部分Reviewであり、Knowledge全体のapprovedには使用できない。

## 4. Claim Snapshot

各Claimは次へ固定する。

- `claim_id`
- `claim_key`
- `claim_version`
- `claim_fingerprint`
- `decision`
- `evidence_assessment_ids`
- `reviewer_id`
- `reviewed_at`
- `comments`

Claim本文はReview Recordへ複製しない。Registryの該当Versionを参照する。

## 5. Checklist Result

各項目の結果は次のいずれかとする。

- `pass`
- `fail`
- `not_applicable`
- `not_reviewed`

`not_applicable`には理由を必須とする。`blocker`項目が`pass`以外ならReview全体を`approved`にできない。`required`項目の未達も原則として`revision_required`または`insufficient_evidence`とする。

## 6. Evidence Assessment

```text
Claim Snapshot
   ↓ evidence_assessment_id
Evidence Assessment
   ├─ evidence_id / evidence_version
   ├─ level: A / B / C
   ├─ support: supports / partially_supports / conflicts / does_not_support
   ├─ locator
   ├─ jurisdiction
   ├─ population_scope
   ├─ method_or_product_scope
   └─ verified_by / verified_at
```

Evidence AssessmentはEvidence本文の複製ではなく、特定Claimに対する評価である。同じ資料でもClaimごとに評価が異なり得る。

## 7. Reviewer Identity

自由入力名ではなく、将来のIdentity Providerで検証可能なIDを前提とする。

| 項目 | 意味 |
|---|---|
| `user_id` | 認証済みUser ID |
| `display_name` | 表示名。本人確認の正本ではない |
| `roles_performed` | `medical_reviewer`、`final_approver`等 |
| `professional_credentials` | 資格種別、登録確認情報、確認日 |
| `specialty_scope` | Review可能な医学領域 |
| `organization` | 所属 |
| `conflict_of_interest` | 利益相反の有無と説明 |
| `identity_verified_at` | 本人確認日時 |

資格番号等の機微情報をAudit Logへ平文で複製しない。保存範囲とアクセス権は実装Phaseで別途定義する。

## 8. DecisionとApproval Stateの対応

| Review Decision | 許可される最大Approval State |
|---|---|
| `approved` | Final Approverの確認後`approved` |
| `approved_with_conditions` | `medical_review` |
| `revision_required` | `owner_review`または`draft`へ差し戻し |
| `rejected` | `draft`または`deprecated`を運用判断 |
| `insufficient_evidence` | `medical_review` |
| `not_applicable` | Review全体には使用不可 |

Review DecisionだけでRegistryのApproval Stateを自動更新しない。状態遷移は権限、Criteria、Version整合性を再確認するTransactionとして行う。

## 9. Version規則

1. `review_version`はKnowledge単位で1から単調増加し、再利用しない。
2. Review Recordは作成後Immutableとする。訂正は新Review Versionで行う。
3. 同じKnowledge Versionの定期ReviewでもReview Versionを増やす。
4. Knowledge、Claim、Evidence、Checklist、PolicyのVersionまたはFingerprintが変われば旧ReviewはStale候補になる。
5. Review期限超過はApproval履歴を削除せず、`review_required`を派生させる。
6. 新Reviewが`approved`になるまで、旧Reviewの履歴を残す。

## 10. Validation案

- `review_record_id`と`knowledge_id + review_version`の重複禁止
- Knowledge / Claim VersionとFingerprintの存在・一致
- Review対象に全active Claimが含まれること
- Checklist VersionとEvidence Policy Versionの存在
- blocker項目の全pass
- ClaimごとのEvidence Assessment存在
- ReviewerのRoleとspecialty scope適合
- `reviewed_at <= valid_from <= review_due_at`の時系列整合性
- `approved`で未解決conditionがないこと
- `supersedes_review_version`の循環・未来参照禁止
- Review History欠落禁止

## 11. 独立コンポーネントとの接続

| コンポーネント | 接続方法 |
|---|---|
| Knowledge Registry | `knowledge_id`、Knowledge Version、Fingerprint |
| Claim Registry | Claim ID、Key、Version、Fingerprint、Approval State |
| Evidence Catalog | Evidence ID、Version。AssessmentはReview側 |
| Relation Registry | Relation Review Recordを別Seriesで管理 |
| Exam Metadata | Exam Review Recordを別Seriesで管理 |
| Approval Gate | 最新有効Review VersionとDecisionを確認 |
| Artifact Registry | Artifact作成時の`source_review_version`へ固定 |

## 12. 今回の非実装範囲

- Database / JSON Schema実装
- Workbench Review UI
- Reviewer認証、資格確認、電子署名
- Approval Gateへの期限判定追加
- 実Knowledge・Claimの状態変更
