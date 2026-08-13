# ADR 0016: 医学承認を人のReview Recordと独立Review Versionへ固定する

- Status: Accepted; implemented by Phase 5.31
- Date: 2026-08-06
- Phase: 5.21 Medical Review Governance & Approval Criteria Design

## Context

BLUPRNT Labには`draft → owner_review → medical_review → approved → published`のApproval Stateと、Knowledge–Artifact Dual Approval Gateがある。しかし、医学Knowledgeの`approved`が誰のどの確認を保証するか、CompletenessやSchema Validationとどう違うか、Knowledge Versionと再レビュー回数をどう分離するかが未確定だった。

このままでは、自由入力の操作者名、Completeness 100%、形式検証だけで医学承認済みに見える危険がある。また、本文を変えずに期限だけ再確認した場合と、医学的意味を改訂した場合の履歴を区別できない。

## Decision

1. `approved`は、定義済みCriteriaを人が満たしたと判断し、対象Version、Reviewer、日時、Evidence、Checklist、Decisionを記録した状態とする。
2. AI、Schema Validation、Completeness、Systemは医学的承認者にならない。
3. Author / Editor、Product Owner、Medical Reviewer、Final Approver、SystemのRoleを分ける。
4. Review DecisionをApproval Stateから分離し、`approved`、`approved_with_conditions`、`revision_required`、`rejected`、`not_applicable`、`insufficient_evidence`を持つ。
5. `approved_with_conditions`と`insufficient_evidence`は`medical_review`に留め、既存Approval Gateの`approved`として扱わない。
6. Review VersionをKnowledge Versionとは独立したKnowledge単位の単調増加カウンターにする。Review Recordは特定のKnowledge / Claim VersionとFingerprintへ固定し、上書きしない。
7. Category共通ChecklistとCategory専用ChecklistをVersion管理する。
8. Evidence Priorityと、特定Claimに対するEvidence Level / support判定を分離する。
9. 時点依存情報へvalidity、jurisdiction、method/product scope、review_due_atを持たせる。期限超過は履歴を消さず、将来のGateで`review_required`または`renderer_ineligible`とする。
10. Knowledge、Claim、Relation、Exam Metadata、ArtifactのReviewを独立させ、利用する資産ごとに必要な承認を確認する。

## Reasons

- Completeness 100%と医学的正確性を明確に分離できる
- 誰が、どの資格・範囲で、何を根拠に承認したか再現できる
- 本文を変えない定期再確認でも履歴を残せる
- ガイドライン、添付文書、法令、測定法の期限切れを安全に停止できる
- 国家試験教材と施設研修でReview Profileを分けても同じContractを利用できる
- Dual Approval GateのKnowledge `approved`に明確な意味を与えられる

## Rejected

- Schema Validation成功を医学承認とみなす案
- Category Completeness 100%を自動承認条件とする案
- AIにMedical ReviewerまたはFinal Approverを担当させる案
- Review DecisionをApproval Stateへ追加して状態数を増やす案
- Knowledge VersionをReview回数として兼用する案
- `approved_with_conditions`を外部送信・Renderer利用可能にする案
- RelationとExam Metadataの承認をKnowledge承認へ包含する案
- 自由入力の操作者名だけでProduction承認する案

## Consequences

Review Record、Reviewer Identity、Checklist、Evidence Assessment、Time-sensitive Policyを保存する新しい実装が必要になる。承認操作は単純な状態変更ではなく、CriteriaとRoleを確認するTransactionになる。

一方、既存Knowledge Schema、Category Schema、Artifact Contract、Dual Approval Gateを変更する必要はない。将来Gateは「最新有効Reviewの存在」を追加確認できるが、`Knowledge approved AND Claim approved AND Artifact approved`のAND条件は維持する。

## Implementation Boundary

Phase 5.21では設計文書、Contract例、Checklist、Pilot Gap Reportだけを作成する。実RegistryのKnowledge、Claim、Relation、Artifactの状態は変更しない。Workbench、Database、権限、電子署名、Renderer Eligibilityへの期限判定はProduct Owner承認後の次Phaseとする。

## Follow-up Decisions

- Medical ReviewerとFinal Approverの具体的人選・本人確認方式
- 高リスクCategoryでの職種・専門領域要件
- Review期限の正式値
- `approved_with_conditions`の内部Preview範囲
- 国家試験教材と施設研修のReview Profile差分
- Reviewer資格情報の保存範囲とアクセス制御
