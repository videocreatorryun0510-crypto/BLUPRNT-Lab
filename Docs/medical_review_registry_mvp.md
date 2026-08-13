# Phase 5.31 — Medical Review Registry MVP

## 1. 目的

Knowledge Registryへ`draft`登録されたKnowledgeを、人がClaimとEvidence単位で確認し、結果を独立したReview Registryへ追記保存する。Reviewは医学的判断の記録であり、Knowledge本文、Claim本文、Registry Approval Stateを自動変更しない。

```text
Knowledge Registry（draft / 正本）
        ↓ 読み取り専用Snapshot
Medical Review Queue
        ↓
Claim Review + Evidence Assessment
        ↓
Knowledge Review + Checklist
        ↓
Medical Review Registry（追記型）
        ↓
Final Approval Eligibility（派生判定のみ）
```

## 2. Review Registry

- 保存先はKnowledge Registryと別の`medical_review_registry.sqlite3`。
- `review_id`はReview Recordの永続ID。
- `review_version`はKnowledgeごとに1から単調増加し、Knowledge Versionとは独立する。
- SQLiteは`review_id`と`knowledge_id + review_version`を一意制約で守る。
- Adapterは`append / get / list / latest / next_version`だけを公開し、更新・削除操作を持たない。
- 再Reviewは既存行の上書きではなく、新しいReview Versionの追加で行う。

Review Recordには対象Knowledge Version/Fingerprint、Reviewer ID/Role、Review Scope、Checklist/Policy Version、各ClaimのVersion/Fingerprint/Decision、Evidence Assessment、Knowledge Review、Final Decision、Comment、日時、期限を保存する。医学本文は複製しない。

## 3. Claim ReviewとEvidence Assessment

現行の全active Claimを個別に表示し、次を人が判断する。

- Claim Decision：`approved` / `revision_required` / `insufficient_evidence` / `rejected` / `not_applicable`
- Evidence実在確認
- Evidence現行性確認
- Claimを直接支持するか
- Evidence Level A/B/C
- `supports` / `partially_supports` / `conflicts` / `does_not_support`
- 章、ページ、表番号等のLocator
- PMID / DOI / 発行元
- コメント

AI Confidenceは保存せず、Evidence Assessmentの代用にしない。同じEvidenceでもClaimごとに別Assessmentを作れる。

## 4. Knowledge ReviewとApproval Eligibility

Knowledge全体についてCategory、定義有無、Schema、Completeness、active Claim数、Review済み数、approved数、Evidence支持数、Version、Fingerprint、期限を固定する。

次がすべて成立した場合だけ`eligible_for_final_approval=true`になる。

1. Schema Validation OK
2. Category Completeness基準を達成
3. 対象Reviewが最新版
4. Knowledge Version/Fingerprintが現行と一致
5. 現行active Claim集合をすべてReview
6. Claim Version/Fingerprintが現行と一致
7. 全Claim Decisionが`approved`
8. 各Claimに実在・現行・直接支持・`supports`のEvidence Assessmentがある
9. blocker/required Checklistがすべて`pass`
10. Checklist VersionとEvidence Policy Versionが現行
11. Reviewer ID、Role、専門CategoryがReviewer Registryと一致
12. Review期限内
13. Final Decisionが`approved`

`approved_with_conditions`はこの条件を満たさない。EligibilityはRegistry状態変更ではなく、将来のFinal Approval Transactionへ渡す読み取り専用の判定である。

## 5. Stale・期限切れ

Knowledge Version、Knowledge Fingerprint、active Claim集合、Claim Version/Fingerprint、Checklist Version、Evidence Policy Versionが変わった場合、過去Reviewを`stale`と派生判定する。期限を過ぎた場合は`expired`とする。いずれもReview Record自体を書き換えず、履歴を保持する。

Evidence本文・Evidence対応が変わるとKnowledge Fingerprintが変わる。さらにAssessmentに保存したEvidence Fingerprintも現在値と比較するため、古い根拠を支持済みとして扱わない。

## 6. Reviewer Identity

`ReviewerRegistry`をInterfaceとし、MVPは3つのFixture Reviewer IDを提供する。自由入力名はReview正本にならない。各FixtureはRoleと専門Categoryを持つ。

Fixture IDは本人確認済みの実運用IDではない。隔離Test RegistryでのみFixture IDをFinal Approval候補判定へ利用できる。実RegistryではFixture IDの`reviewer_identity`検査が失敗し、既存の承認操作も停止する。正式運用前にAuth/Identity Provider、資格確認、利益相反、権限管理へ交換する。

## 7. Workbench

Medical Review QueueにはKnowledge名、Category、Knowledge/Review Version、Claim進捗、Evidence Coverage、Completeness、現在Decision、期限、Validity、Eligibilityを表示する。

Knowledge Review画面では、Claim本文をRegistryから読み取り、Evidence、PMID/DOI、Level、Decision、Comment、Checklist、Final Decision、期限を入力する。保存後はReview Versionだけが増え、Knowledge Registryの本文とApproval Stateは変わらない。

## 8. Pilot結果

隔離されたフェリチンFixtureで次を自動確認する。

| 条件 | 結果 |
|---|---|
| 全Claim approved、全Evidence/Checklist/Version/期限が一致 | Final Approval候補 |
| 1 Claimがrevision_required | 承認不可 |
| 1 ClaimのEvidence Assessment不足 | 承認不可 |
| approved_with_conditions | 承認不可 |
| Review後にKnowledge/Claimを改訂 | stale・承認不可 |
| Review期限超過 | expired・承認不可 |

実RegistryのGram染色、鉄欠乏性貧血、フェリチンは`draft`のまま維持する。

## 9. Product Owner確認事項

- 11〜24件程度のClaimを1件ずつ確認する操作量が現実的か
- 根拠資料、PMID/DOI、Locatorを同じClaimカード内で確認しやすいか
- Claim CommentとKnowledge Review Commentの粒度を分ける運用が分かりやすいか
- Review期限の初期値90日が教材運用に適切か
- 全blocker/requiredを毎回passにする基準が国家試験教材として重すぎないか
- Fixture Reviewer表記が実Reviewerと誤認されないか

## 10. CTOレビュー

責務分離は長期運用に適する。Knowledgeは医学的事実、Review Registryは人の判断履歴、Eligibilityは現時点の利用可否という三層になり、履歴を破壊せず再Reviewできる。Provider固有処理、AI判断、Publisher、Artifactは混入していない。Dual Approval Gateも変更しておらず、医学ReviewのないKnowledgeを自動approvedへ進める経路は追加していない。

最大の残課題は、Final Approval Transactionと実Identity/Authorizationが未実装なことである。現時点ではEligibilityがtrueでもKnowledgeは`draft`のままであり、これは意図した安全側のMVPである。

## 11. Technical Debt

優先度順：

1. 実ReviewerのAuth/Identity Provider、資格・専門領域・利益相反確認
2. Review Eligibilityを必須入力にする原子的Final Approval Transaction
3. Review Registry Backup/Restore、署名、改ざん検知、アクセス制御
4. Category別Review期限とEvidence鮮度Policy
5. Relation / Exam Metadata専用Review Series
6. 多数Claim向けの差分Review、前版Assessmentの安全な参照支援
7. Review通知、担当割当、期限超過通知
8. Review DBのサーバDB移行と同時編集制御

## 12. 非変更範囲

Knowledge Contract、Promotion Contract、Evidence Contract、Discovery Contract、Claim Candidate Contract、Artifact Contract、Renderer、Gemini Adapter、PubMed Provider、Publisher Coreは変更していない。
