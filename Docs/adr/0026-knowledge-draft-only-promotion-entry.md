# ADR 0026: Knowledge DraftをPromotion唯一の入口にする

- Status: Accepted
- Phase: 5.30 Knowledge Draft Promotion Integration MVP

## Context

Phase 5.29でAuthoring Draftから内容を変えずにKnowledge Draftを生成できるようになった一方、Phase 5.23のAuthoring Draft直結Promotionが残っていました。このままではKnowledge Draftの確認・Fingerprint・Validationを迂回できます。

## Decision

1. Promotionの正式入力はKnowledge Draft IDだけとする。
2. Knowledge Draft ValidationとRegistry Diffを含む読み取り専用Previewを必須とする。
3. Preview後のDraft・Registry・Knowledge・対象Version変更を検出して保存を停止する。
4. Promotion後のApproval Stateは必ず`draft`とする。
5. 旧Authoring Promotion APIは削除せず、Deprecatedとして書き込みを拒否する。
6. Knowledge、Claim、Evidence、Approval、Publisher、Artifact、RendererのContractは変更しない。

## Reasons

- 編集中データと登録候補の責務を混ぜないため
- 人が確認したKnowledge DraftとRegistryへ保存される内容を一致させるため
- Version更新と差分を保存前に判断できるようにするため
- 既存クライアントへ明確な移行エラーを返しつつ、危険な互換経路を残さないため

## Rejected alternatives

- Authoring Draftからの直接Promotionを継続する
- Knowledge Draft生成直後に自動Promotionする
- Previewを省略する
- Promotion時に自動承認する
- 旧APIを即時削除する

## Consequences

正式登録にはKnowledge Draft生成とPreviewの2段階が増えます。一方、内容・差分・版を登録前に確認でき、Authoringの変更が登録をすり抜けません。旧API利用者にはHTTP 410を返すため、新しいKnowledge Draft経路への移行が必要です。
