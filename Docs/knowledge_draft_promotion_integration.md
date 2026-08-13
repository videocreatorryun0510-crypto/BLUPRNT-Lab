# Phase 5.30 — Knowledge Draft Promotion Integration MVP

## 1. 目的

Knowledge Draftを正式Registryへ登録できる唯一の入力にします。Authoring Draftは編集用、Knowledge Draftは登録候補、Registryは正式台帳という境界を固定します。

```text
Authoring Draft
  ↓ Knowledge Assembler（内容を変えない）
Knowledge Draft
  ↓ Promotion Preview（読み取りのみ）
Promotion
  ↓ 明示確定時だけ保存
Knowledge Registry（approval = draft）
```

## 2. 正式経路

1. WorkbenchでAuthoring Draftを編集する
2. `Generate Draft`でKnowledge Draftを生成する
3. Claim、Reference、Summary、Completeness、Fingerprintを確認する
4. `Promotion Preview`でRegistryとの差分と次Versionを確認する
5. Validationがすべて通った場合だけ`Promote`を押す
6. Registryへ`draft`状態で保存される

Authoring Draftから直接Promotionする旧APIは削除していませんが、HTTP 410と`authoring_promotion_path_deprecated`を返し、Registryを書き換えません。Workbenchからも呼び出せません。

## 3. Promotion Preview 2.0

PreviewはKnowledge Draft IDだけを受け取ります。次を表示・返却します。

- Title、Category、Summary
- Claim全文と順序
- Reference全文とClaim対応
- Knowledge Draft Validation、Completeness、Fingerprint
- Registry Key、対象Knowledge ID
- 新規作成またはVersion更新
- 現在VersionとPromotion後Version
- Summary、Claim、Referenceの追加・更新・削除差分

Preview中はRegistryを変更しません。Preview後にKnowledge Draft、Registry、正式Knowledge、対象Versionのいずれかが変わった場合、確定を停止して再Previewを求めます。

## 4. Promotion Validation

Promotion前に以下をすべて確認します。

- Knowledge Draft ValidationがOK
- Claim本文・順序がAuthoring Draftと一致
- Summaryが既存Claim本文の完全一致コピー
- Reference本文とClaim対応が一致
- CategoryとClaim保存先が一致
- Knowledge Draft Fingerprintが一致
- Review状態が`draft`
- Knowledge ID、Alias、対象Versionに競合がない
- Registryとの差分が存在する
- Knowledge Schema 1.0に適合する

Claim削除は履歴と参照を安全に扱う専用操作が必要なため、このMVPではPreviewへ表示したうえでPromotionを停止します。Referenceだけの版更新も、現在のRegistryがClaim変更を版上げの基準にしているため停止します。

## 5. Registry保存

明示確定時だけ既存Knowledge Registry Adapterを呼びます。Registryが発行・維持する`knowledge_id`、`claim_id`、`claim_key`、Version、Historyは従来どおりです。PromotionがApprovalを進めることはなく、保存後のKnowledgeとClaimは`draft`です。

Knowledge Draftそのものは変更・削除せず、入力FingerprintとPromotion Logを追跡できます。

## 6. 互換性

変更していないもの：

- Knowledge Contract 1.0
- Claim ContractとClaim Dictionary
- Evidence Contract
- Approval、Publisher、Artifact、Renderer
- Registry Adapter Interface
- Phase 5.23のPreview/Result 1.0 Schema取得API

変更したもの：

- Promotionの正式入力をKnowledge Draftへ変更
- Preview/Result Contract 2.0を追加
- WorkbenchをKnowledge Draft → Preview → Promoteの3段階へ変更
- 旧Authoring Promotion APIをDeprecated・書込拒否へ変更

## 7. 運用上の注意

- Authoringを修正した後はKnowledge Draftを再生成してください。
- Preview後に別のRegistry更新が入った場合は、もう一度Previewしてください。
- `Completeness 100%`は構造が揃った意味で、医学的に承認された意味ではありません。
- Promotion後も`draft`です。医学レビューとApprovalは別工程です。

## 8. Technical Debt

1. Claim削除を安全に表現する専用Promotion操作は未実装です。
2. Referenceだけを変更したKnowledge Versionの方針は未確定です。
3. Previewの一時状態はプロセスメモリ内で、再起動後は再Previewが必要です。
4. 複数人同時編集時の排他制御は未実装です。
5. Registry Diffは意味差分ではなく、安定Keyと正規化書誌情報による機械的差分です。
