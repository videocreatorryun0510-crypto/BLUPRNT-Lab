# Phase 5.23 Knowledge Promotion Workflow MVP

> **Phase 5.30で正式経路を更新しました。** この文書はPhase 5.23時点の履歴です。Authoring Draft直結経路は現在Deprecatedで書き込みを拒否します。現行仕様は[Knowledge Draft Promotion Integration](knowledge_draft_promotion_integration.md)を参照してください。

## 目的

Knowledge Promotionは、Workbenchの未完成なAuthoring Draftを、正式Knowledge Registryへ安全に移すための境界です。

```text
Authoring Draft
      ↓
Promotion Validation
      ↓
Promotion Preview（読み取り専用）
      ↓  人が確定
Knowledge Registry（Approval: draft）
```

Previewを表示しただけではRegistryを書き換えません。確定操作の直前に下書きとRegistryのFingerprintを再確認し、Preview後にどちらかが変わっていれば停止します。

## Promotion Preview

Workbenchには次を表示します。

- Knowledge名、Category
- Claim数、Reference数、Authoring Completeness
- Schema / Category / Claim / Reference Validation
- Registry KeyとKnowledge ID
- 新規作成またはVersion更新
- Promotion後のVersion
- Fingerprint検証

`promotion_allowed=false`のPreviewは確定できません。

## Claimの保存先

Promotion Mapperは医学的意味を推測しません。AuthorがClaimごとに、Categoryで許可された保存先を明示します。

例：

- 全Category：`definition`
- Laboratory Test Item / Disease / Specimen / Biological Structure：`overview`
- Test Item：`biological_basis`、`analyte_characteristic`、`purpose`、`interpretation_caution`
- Staining Method：`safety_consideration`
- Specimen / Reagent：`caution`

`unassigned`のClaimはPromotionを停止します。構造化入力が必要な測定法、検体採取法、病態、検査所見などは、事実を単純な概要へ誤分類せず、将来のCategory専用Authoringで対応します。

## Promotion Validation

確定前に次を検査します。

1. Knowledge Schema 1.0
2. CategoryとClaim保存先の整合
3. Claim ID、Claim数、全ClaimへのReference接続
4. Reference ID、参照Claim、必須Reference、情報源の優先順位
5. Registry Key、Knowledge ID、Aliasの重複
6. 新規作成かVersion更新か
7. Fingerprintの決定性
8. DraftがActiveであること

既存KnowledgeのReferenceだけを変更し、Claim変更がない版更新はMVPでは停止します。現RegistryはClaim変更を版更新の起点としているため、承認済みKnowledgeを根拠だけ差し替えて承認状態を維持する危険を避けるためです。

## Registry保存

Promotion成功時は既存Registryの`reconcile()`を使います。

- 新規KnowledgeはDraftのKnowledge IDを使用
- 同一Registry Keyがある場合は既存の安定Knowledge IDを再利用
- Claim Dictionaryにより意味が同じClaimの安定IDを再利用
- 内容変更時はKnowledge Versionを更新
- Knowledge Approval Stateは必ず`draft`
- 自動承認、医学レビュー、Artifact生成は行わない

Evidence Levelと情報源の優先順位は別の意味として入力します。A/B/Cから優先順位を推測しません。DifficultyとAuthoring上のExam Importanceも、根拠のない正式医学・国家試験情報へ変換せず、Authoring Draft側に残します。

## Draftの扱い

成功後は次のどちらかを選べます。

- `keep`：Activeのまま保持
- `archive`：履歴としてArchivedへ変更

削除はしません。Archived Draftを再Promotionする場合は、新しいDraftとしてImportし直して変更履歴を分けます。

## Promotion Log

`data/promotion_logs/promotion.jsonl`へ、PreviewとPromotionの監査情報を追記します。医学本文やReference本文は保存しません。

保存項目は、日時、Draft ID、Preview ID、Registry Key、Knowledge ID、Version、操作、新規/更新、結果、停止理由、操作者です。

## 今回変更していないもの

- Knowledge Contract 1.0
- Knowledge Approval / Medical Review
- Relation / Growth Engine
- Source Bundle / Presentation / Artifact
- Renderer / Gemini

PromotionはAuthoringとRegistryの間だけに追加した独立Application Serviceです。

## 運用手順

1. Wizardで下書きを作成
2. Claim本文と保存先を入力
3. Referenceを追加し、支えるClaimを選択
4. `Promotion Preview`を押す
5. Validationの全項目を確認
6. Draftを保持するかArchivedにするか選ぶ
7. `正式RegistryへPromotion`を押す
8. Knowledge ID、Version、Approval `draft`を確認

Promotion後も、正式利用や外部AI送信には既存Approval Gateと医学レビューが必要です。
