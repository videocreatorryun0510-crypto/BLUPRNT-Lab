# Phase 5.29 — Knowledge Assembler MVP

## 1. 目的

Knowledge Assemblerは、人がAuthoring画面で採用・修正したClaimと、人が選択したReferenceを、Promotion前に確認できる`Knowledge Draft 1.0`へ整理します。AIが医学知識を書く機能ではありません。

```text
Authoring Draft
        ↓
Knowledge Assembler（構造化のみ）
        ↓
Knowledge Draft 1.0
        ↓
Knowledge Draft Validator
        ↓
人によるPreview

※ Registry / Promotion / Approvalには接続しない
```

## 2. 責務

Assemblerが行うことは次の5つだけです。

- Authoring Categoryをそのまま設定する
- Claimの順序とCategory内のSection参照を作る
- ClaimとReferenceの対応を双方向に見える形へ整理する
- 入力Draft、難易度、国家試験重要度、Assembler版をMetadataへ記録する
- 完全性とFingerprintを計算する

次の操作は禁止し、Validatorで入力との差分を検出します。

- Claimの追加、削除、統合、要約、言い換え
- Referenceの追加、削除、書誌情報変更、Evidence評価変更
- Registry書込み、Promotion、自動Approval
- Provider固有処理や外部AI通信

## 3. Knowledge Draft Contract 1.0

| 項目 | 役割 |
|---|---|
| `knowledge_draft_id` | Draft自体の一時保存ID |
| `temporary_knowledge_id` | Promotion前だけ使うKnowledge仮ID |
| `category` / `title` | Authoring Draftから無変更で転記 |
| `summary` | 既存のDefinition、Overview、先頭Claimの順に選び、本文を完全一致コピー |
| `summary_source_claim_id` | Summaryの出所となるClaim ID |
| `claims` | ID、本文、順序、Semantic Slotを無変更で保持 |
| `references` | 人が選択したReferenceを無変更で保持 |
| `category_structure` | Semantic SlotごとにClaim IDを順序付きで参照 |
| `metadata` | 元Draft ID/Fingerprint、難易度、重要度、Assembler版、生成日時 |
| `review` | `approval_state=draft`、未Promotion、Registry未変更を固定 |
| `completeness` | 組立てに必要な情報の揃い具合。医学的正確性ではない |
| `fingerprint` | 内容全体の改変検知値 |

Summaryは新しい文章を作りません。定義Claimがあればその本文をそのまま使い、なければOverview、さらに無ければ先頭Claimを使います。Claimが無い場合はValidationで保存を禁止します。

## 4. Completeness

このスコアは医学的品質ではなく、Knowledge Draftとしての組立て状況です。

- 基本Metadata：35点
- Claimあり：25点
- Referenceあり：20点
- 全ClaimがReferenceへ接続：15点
- 全ClaimにCategory内の保存先が指定済み：5点

`unassigned`のClaimがあっても、ClaimとReferenceの対応が安全ならDraft確認用に保存できます。ただし完全性は100%にならず、既存Promotion Validationは引き続き正式登録を停止します。

## 5. Validationと保存条件

保存前に次をすべて確認します。

- Claim位置が1からの連番で、入力順が維持されている
- Claim IDとReference IDが重複していない
- 全Claimが存在するReferenceに対応している
- Category、Title、元Authoring Draftが一致する
- 元Draft FingerprintとKnowledge Draft Fingerprintを再計算できる
- Assembler IDとVersionが固定値と一致する
- Claim本文・ID・順序・Semantic Slotが元入力と完全一致する
- Reference全項目が元入力と完全一致する
- Summaryが`summary_source_claim_id`のClaim本文と完全一致する
- Reviewが`draft`で、Promotion・Registry変更がFalseである

1件でも失敗するとファイルを保存しません。

## 6. 保存とWorkbench

検証済みDraftは正式Registryとは別の`data/knowledge_drafts/`へ、1 Draft 1 JSONとして保存します。

Workbenchの「Knowledge Draft Preview」では次を確認できます。

- Title、Category、Claim数、Reference数
- Summaryと元Claim
- Claim順とReference対応
- Completeness、Validation、Fingerprint
- JSON / Markdown Export
- Authoring画面へ戻る操作

この画面にはPromotionボタンを置きません。既存Promotion Workflowは互換維持のため変更していませんが、Phase 5.29のAssembler経路から自動実行されることはありません。

## 7. Product Owner確認項目

- ClaimがAuthoringで決めた順番のままか
- Summaryが既存Claimと一字一句同じで、新情報を加えていないか
- 各Claimを支えるReferenceが分かるか
- Category Sectionの分け方が自然か
- 不足時に保存されず、Authoringへ戻れるか

## 8. 長期運用レビュー

Assembler、Validator、Repositoryを分けたため、将来保存先をDBへ交換しても組立て規則は変わりません。Provider固有コード、Knowledge Contract、Registryを参照しないため、AIやEvidence Providerの交換にも影響されません。

残る課題は次の通りです。

1. Knowledge Draftから既存Promotion Previewへ進む正式接続は未実装
2. Human Reviewの決定IDをDraft Metadataへ直接記録するContractは未実装
3. Summaryは既存Claimの完全一致コピーであり、複数Claimからの教育的要約は意図的に未実装
4. `unassigned`をCategory Sectionへ割り当てるのは人の作業として残る
5. 複数利用者の同時編集・Draft版管理・認証は未実装

これらは現在の責務分離を壊す問題ではありません。次PhaseではKnowledge Draftを入力にするPromotion Previewを追加し、旧Authoring Draft直結経路の移行計画を作るのが自然です。

