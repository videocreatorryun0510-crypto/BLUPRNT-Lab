# Phase 5.22 Knowledge Authoring Workflow MVP

## 目的

人が新しいKnowledgeを作る最初の10分を、形式作業ではなく医学的事実と出典の入力へ使えるようにします。AIは利用せず、既存Contractと正式Registryを変更しません。

## 利用者の流れ

```text
Category / Title / Alias / Difficulty / Exam Importance
                         ↓
             Knowledge Skeleton（draft）
                         ↓
              Claimを1事実ずつ入力
                         ↓
          ReferenceをClaimへ関連付け
                         ↓
      Schema / Completeness / 整合性を確認
                         ↓
              JSON / Markdown Export
```

目標時間は、Skeleton 1分、Claim入力5分、Reference入力3分、確認とExport 1分の合計10分以内です。医学知識の調査時間と医学監修時間は、この目標に含めません。

## Skeleton仕様

Wizardは既存Category Unionの7カテゴリを利用します。

- `test_item`
- `laboratory_test_item`
- `disease`
- `staining_method`
- `specimen`
- `reagent`
- `biological_structure`

Skeletonの`knowledge`はKnowledge Contract 1.0に適合します。Category固有欄は空配列、Claim・Reference・Relationは空、Reviewは必ず`draft`です。DifficultyとExam Importanceは作成作業用メタデータであり、根拠のない正式Exam Metadataへ転記しません。

## Claim Authoring

- 1 Claimには確認可能な医学的事実を1つだけ入力する
- `claim_id`は`clm_`から始まるランダムな安定IDとして自動発行する
- 表示順は`position`で管理し、並び替えても`claim_id`を変えない
- Claim削除時はReferenceの参照から同じIDを外し、参照切れを作らない
- Category固有の意味欄への正式配置は、このMVPでは行わない

## Reference Authoring

保持する項目はEvidence Level、主根拠・補助根拠、資料名、発行団体、版、発行年、URL、DOI、PMID、参照日、章、ページ、対応Claim IDです。Reference IDは自動発行します。

Evidence Levelは作成者による整理用です。医学監修のEvidence Assessmentや承認を代替しません。

## 保存前Validation

検査対象は次に限定します。

- Authoring DraftとKnowledge 1.0のSchema
- Wizard必須5項目
- Claim数とReference数
- Referenceが存在するClaimだけを参照していること
- 作成進捗を表すCompleteness

作成時Completenessは、基本情報40点、Claim最大30点、Reference最大20点、全ReferenceのClaim接続10点です。これは作成作業の進み具合であり、Knowledge Category Completeness、医学的正確性、国家試験としての十分性、承認品質を示しません。

## 保存境界

```text
Workbench
  ↓
KnowledgeAuthoringService
  ↓
AuthoringDraftRepository
  ↓
data/authoring_drafts/*.json（Git対象外）

Knowledge Registry ── 書き込みなし
Approval / Publisher / Artifact ── 変更なし
```

ファイル保存はRepository越しに行うため、将来SQLiteやサーバーDBへ交換しても画面とAuthoring Serviceの責務は維持できます。1 Draftを1 JSONへ分け、途中保存の破損を避けるため一時ファイルから置換します。

## Import / Export

- JSON Export：同じAuthoring Draft Contractを完全保存し、再Importできる
- Markdown Export：人による確認・相談用。再Importには使わない
- JSON Import：SchemaとID参照を検証後、新しい`draft_id`を発行して保存する

Import時も正式Registryは変更しません。同じ`knowledge_id`を持つ複数下書きができるため、正式登録前の統合・競合確認は将来のPromotion Workflowで扱います。

## 今回変更していないもの

- Knowledge Contract、Category Schema、Claim Registry
- Knowledge ApprovalとMedical Review
- Relation、Growth Engine
- Source Bundle、Presentation、Artifact、Renderer
- Gemini、OpenAI、その他AI

## Product Owner確認項目

1. 5項目の入力だけで下書きが作れるか
2. Claimを1事実ずつ迷わず入力できるか
3. Claim順変更後もIDが変わらないか
4. ReferenceとClaimの対応を確認しやすいか
5. 10分以内という作成時間目標を実データ3件で測定できるか
6. 「下書き保存」と「正式Registry登録・承認」が画面上で混同されないか

## 次段階候補

最優先は、3件の実Authoring時間を測定し、入力の詰まりを観察することです。その結果が出るまでAI補完、正式Registryへの自動Promotion、複数人同時編集は追加しません。
