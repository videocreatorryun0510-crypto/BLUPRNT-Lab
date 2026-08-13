# ADR 0018: Authoring Draftの正式登録をPreview付きPromotion境界に限定する

> Superseded by [ADR 0026](0026-knowledge-draft-only-promotion-entry.md). Authoring Draft直結APIは互換用に残るが、書き込みを拒否する。

- Status: Accepted
- Date: 2026-08-10
- Phase: 5.23 Knowledge Promotion Workflow MVP

## Context

Phase 5.22で、入力途中のKnowledgeを正式Registryから分離できた。一方、ExportしたJSONを人が正式Knowledgeへ転記すると、ID競合、Claim保存先の誤り、Reference切れ、承認状態の誤設定が起きる可能性がある。

Knowledge ContractやRegistryへAuthoring都合の項目を追加せず、安全に接続する境界が必要である。

## Decision

1. Authoring DraftとKnowledge Registryの間に、独立した`KnowledgePromotionService`を置く。
2. PromotionをPreviewとCommitの2段階に分け、PreviewはRegistryを変更しない。
3. Claimの保存先はAuthorが明示し、Promotion Mapperは医学的意味を推測しない。
4. Schema、Category、Claim、Reference、Registry重複、Fingerprint、Knowledge IDをCommit前に検証する。
5. Preview時のDraft FingerprintとRegistry FingerprintをCommit直前に再検証する。
6. 既存Registry Keyがある場合は安定Knowledge IDを再利用し、Version更新として扱う。
7. Promotion後のKnowledge Approval Stateを必ず`draft`とし、自動承認を禁止する。
8. 成功後のAuthoring Draftは保持またはArchivedを選択できるが、削除しない。
9. Promotion Logは本文を持たない追記専用JSONLとする。

## Not selected

- Authoring DraftをRegistryへ直接保存する案：未完成データと正式正本の境界が失われる。
- Titleだけで自動的にClaimの保存先を推測する案：医学的事実の誤分類を招く。
- Previewなしの1クリック登録：競合と変換結果をProduct Ownerが確認できない。
- Promotion時の自動approved：Medical Review GovernanceとApproval Gateを迂回する。
- 成功後のDraft削除：Authoring経緯と再現可能性が失われる。

## Consequences

安全性のため、AuthorはClaim保存先とReference接続を入力する必要がある。構造化属性を必要とするCategory ClaimはMVPではPromotionできる範囲が限られる。

現RegistryはClaim変更をKnowledge Version更新の起点にしているため、Referenceだけの版更新は停止する。将来、Evidence変更も独立したVersionイベントとして扱えるRegistry Contractが必要になる可能性がある。

## Compatibility

Knowledge Contract、Registry Contract、Approval、Relation、Source Bundle、Presentation Artifact、Publisher Coreに破壊的変更はない。Authoring Draftには後方互換な`lifecycle_state`と`semantic_slot`選択肢を追加した。
