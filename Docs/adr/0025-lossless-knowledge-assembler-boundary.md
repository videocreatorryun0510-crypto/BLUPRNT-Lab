# ADR 0025: Lossless Knowledge AssemblerをPromotion前の独立境界にする

- Status: Accepted
- Date: 2026-08-13
- Phase: 5.29 Knowledge Assembler MVP

## Context

Phase 5.28までで、Formal Evidenceから人が採用・修正したClaimとReferenceをAuthoring Draftへ保存できるようになった。これを直接Registry用Knowledgeへ変換すると、構造化とPromotion、ID発行、Approvalの責務が再び混ざる。特に、AssemblerがAI要約や医学知識補完を行うと、人が採用した内容と正式登録候補の間の追跡性が失われる。

## Decision

1. `Knowledge Draft Contract 1.0`をAuthoring DraftとPromotionの間の独立Contractにする。
2. AssemblerはCategory、順序、Reference対応、Metadataだけを決定する。
3. ClaimとReferenceは入力から完全一致コピーし、追加・削除・統合・言い換えを禁止する。
4. Summaryは既存Claim本文の完全一致コピーだけを許可し、出所Claim IDを必須追跡する。
5. Validatorは元Authoring Draftとの差分、ID、順序、Reference、Category、Metadata、Fingerprintを検証する。
6. Validation失敗時はKnowledge Draftを保存しない。
7. 保存先は正式Registryと分離したRepository Interfaceの背後に置く。
8. Reviewは`draft`、Registry変更・Promotion・医学レビューはFalseで固定する。
9. WorkbenchのAssembler欄にはPromotion操作を置かない。
10. Knowledge Contract、Promotion、Approval、Registry、Evidence、Publisher、Artifactを変更しない。

## Not selected

- AIによるKnowledge生成：採用済みClaim以外の医学知識が混入する。
- AIによるSummary生成：新しい表現や意味が追加され、出典追跡が曖昧になる。
- Draft生成時の自動Promotion：人による構造確認を迂回する。
- Draft保存時のRegistry更新：未完成Draftと正式正本が混ざる。
- Knowledge ContractへDraft項目を追加：正式正本の契約を制作途中データで汚す。
- ProviderごとのAssembler：後段ContractがAIベンダーに依存する。

## Consequences

人が採用した内容からPromotion候補までの間に、再現可能で検証可能な確認地点ができる。一方、Summaryは既存Claimのコピーに限られ、教育的な文章編集はこのPhaseでは扱わない。Knowledge DraftからPromotion Previewへの正式接続は次Phase以降の作業となる。

## Compatibility

Knowledge Contract、Promotion、Approval、Registry、Evidence、Publisher、Artifactの既存Contractは不変である。既存Authoring Draft直結Promotionも互換維持し、Phase 5.29の新経路からは呼び出さない。

