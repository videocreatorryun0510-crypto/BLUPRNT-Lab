# ADR 0027 — Immutable Independent Medical Review Registry

- Status: Accepted
- Date: 2026-08-13
- Phase: 5.31

## Context

Knowledge Registryへ`draft`登録する正式経路は完成したが、Schema/Completeness/AI生成成功と、人による医学判断を区別して保存する実装がなかった。既存RegistryのApproval履歴だけへ判断結果を詰め込むと、対象Claim・Evidence・Checklist・期限を固定できず、Knowledge改訂後も古い判断が有効に見える危険がある。

## Decision

1. Medical Review RegistryをKnowledge Registryから独立させる。
2. Review Recordは追記専用とし、訂正・再Reviewは独立`review_version`を増やす。
3. Knowledge/Claim/Evidenceの本文を複製せず、ID、Version、Fingerprint、Assessment、Decisionだけを固定する。
4. Approval EligibilityはReview Recordと現在Registryの比較から派生させる。
5. `stale`と`expired`は履歴を書き換えず派生判定する。
6. Reviewerは自由入力名ではなく交換可能なReviewer RegistryのIDを必須とする。
7. AIはReview Decisionを作成せず、MVPでも自動Approvalを行わない。
8. Final Approval Transactionは実装せず、Phase 5.31は`eligible_for_final_approval`までとする。

## Rejected alternatives

- Knowledge JSONへReview結果を埋め込む：医学本文のVersionと人の判断履歴が同時に変わる。
- Knowledge RegistryのApproval Commentだけで代用する：Claim/Evidence/Checklistの監査情報が不足する。
- 最新Reviewを上書きする：過去判断と再Review理由を失う。
- AI ConfidenceをEvidence Assessmentとして扱う：根拠資料の実在・現行性・直接支持を保証しない。
- `approved_with_conditions`をapproved相当とする：未解決条件をRendererや外部AIへ流す。
- Fixture Reviewから自動approvedへ進める：本人確認と権限のないMVP IDが正式承認を作れる。

## Consequences

Reviewの対象版、判断者、根拠評価、期限を長期追跡できる。Knowledge改訂後も旧記録を残したまま安全にstaleと判断できる。一方、正式Approvalへ進めるには、実Identity ProviderとReview Eligibilityを検証する原子的Transactionが別Phaseで必要になる。
