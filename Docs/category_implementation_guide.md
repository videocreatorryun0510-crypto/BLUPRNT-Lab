# Knowledge Category 実装ガイド

この文書は、BLUPRNT Labへ新しいKnowledge Categoryを正式追加する標準手順です。Phase 5.1の`staining_method`、Phase 5.3の`specimen`、Phase 5.5の`reagent`、Phase 5.8の`biological_structure`、Phase 5.10の`disease`、Phase 5.11の`laboratory_test_item`実装を基準にし、今後の`microorganism`、`parasite`、`examination_method`でも同じ品質ゲートを繰り返します。

目的は、カテゴリごとに別システムを作ることではありません。共通のCategory Envelope、Registry、承認、Publisher Coreを維持し、医学的な違いだけを専用SchemaとCompletenessへ閉じ込めます。

## 1. 標準フロー

```text
Category責務を確認
    ↓
Category Unionへ識別子を追加
    ↓
Category専用Schemaを追加
    ↓
Category Completenessを追加
    ↓
Workbenchの登録・編集を接続
    ↓
claim_key辞書を追加
    ↓
Registryへ保存・版管理
    ↓
既存Profileの参照先を設定
    ↓
Semantic Blueprint / Publication Planを確認
    ↓
既存カテゴリとの回帰テスト
    ↓
医学監修・承認後にProduction化
```

## 2. 実装前ゲート

次を説明できるまでSchemaを追加しません。

- Phase 5.0のKnowledge Domain Map上でCategoryの責務が決まっている
- 既存Categoryとの重複がない
- 共通属性では表現できない専用属性が明確である
- 専用属性をPublisherの表示都合ではなく、医学的事実として説明できる
- 正式登録に必要なCompleteness項目が決まっている
- 代表用語1件と、確認可能な出典がある
- 既存Publisher Coreへ新しいレイヤーを追加せず接続できる

## 3. 実装チェックリスト

### Step 1 — Category Union

- `classification.term_type`へCategory IDを追加する
- Category専用Envelopeを判別可能な`template_id`で追加する
- Category IDと`template_id`の不一致を拒否する
- 既存CategoryのJSONを変更しない

### Step 2 — Category専用Schema

- Category Envelopeと専用内容を別モデルにする
- 一つの医学的事実へ一つの`claim_id`を付ける
- 他Claim参照は`*_claim_ids`で明示する
- 順番に意味がある工程は順序番号の重複を拒否する
- 表示文章、色、座標、媒体別表現を保存しない
- 下書き保存のため空配列を許可し、不足はCompletenessで検出する

### Step 3 — Completeness

- Schema Validationと別にCategory Completenessを作る
- 必須、重要必須、推奨任意を区別する
- 正式登録に必要な医学項目を合計85点、出典充足を15点として評価する
- 重要必須が欠ける場合は49点以下へ制限する
- 必須が欠ける場合は79点以下へ制限する
- 不足項目、改善方法、確認担当を返す
- 点数は正確性や承認を表さないことを画面に明記する

### Step 4 — Workbench

- 代表用語の編集可能な正式下書きを用意する
- 下書きを開くだけではRegistryを書き換えない
- 保存前にSchema Validationを行う
- 保存後にCategory Completenessを表示する
- 操作者と変更理由を入力する
- 保存済みKnowledge JSONを再読込・編集できる
- Schemaエラーの位置と内容を表示する

### Step 5 — Claim Dictionary / Registry

- Category固有の安定した`claim_key`規則を定義する
- AIやJSON配列の生成順へ依存しない
- 同じ意味は既存`claim_key`と`claim_id`を再利用する
- 新しい医学的事実だけ新規Claimにする
- JSON本文を再起動後も読める永続保存へ格納する
- 医学的事実の更新でKnowledge Versionを上げる
- 並び替えだけではVersionを上げない
- 承認済みClaimを通常編集で上書きしない

### Step 6 — Publisher接続

- Publisher Coreのコードや層は追加しない
- Content Profileの`field_path_prefixes`と既存`claim_key`で接続する
- Education、Visual、Grammar、Intent、Taxonomyは既存Profileを再利用する
- 不足時はまずProfile・Taxonomy・Knowledge不足を分類する
- Publication Plan生成前後でKnowledge JSONが変化していないことを確認する

### Step 7 — 回帰テスト

最低限、次を自動確認します。

- 代表用語がCategory Schemaを通る
- 主要項目を削るとCompletenessが低下する
- Claim参照切れと順序重複を拒否する
- 2回保存しても同じ`claim_key`と`claim_id`を維持する
- 並び替えだけではKnowledge Versionを変更しない
- 医学的事実の変更ではVersionを上げる
- SQLite再起動後もKnowledge JSONを読める
- `draft → owner_review → medical_review → approved`が動く
- Semantic BlueprintとPublication Planを生成できる
- 既存の代表Categoryが引き続き動く

## 4. Production Definition of Done

Category実装と、個別Knowledgeの承認を分けます。

### Category実装完了

- Category Union、Schema、Completenessが版付き契約として存在する
- Workbenchから登録・編集・再読込できる
- RegistryのID、版、履歴、承認を利用できる
- Publisher Coreを変更せずPublication Planへ到達できる
- 回帰テストが成功する
- 本ガイドだけで次のCategoryを追加できる

### 個別Knowledge公開可能

- Completenessがレビュー基準を満たす
- すべての主要Claimに確認可能な出典がある
- Claimが医学監修を通過している
- Knowledgeが`approved`である
- Exam Metadataの出題実績が実データで確認されている
- Publisher側の媒体別レビューが完了している

Category実装が完了しても、個別Knowledgeが自動的に医学承認済みになるわけではありません。

## 5. 変更してよい場所・避ける場所

| 目的 | 主な変更場所 | 原則変更しない場所 |
|---|---|---|
| 医学的構造 | `knowledge-contracts/v10/models.py` | Publisher Core |
| 情報量評価 | `knowledge-contracts/v10/completeness.py` | Theme、Layout |
| 安定意味ID | `claim_key_resolver.py` | AI生成順 |
| 正本編集 | Workbench API・画面 | PDF Adapter |
| 媒体への接続 | Content Profile | Knowledge JSON本文 |
| 教え方 | Education Profile | Category Schema |
| 図解の意味・構造 | Intent、Taxonomy、Grammar Profile | Knowledge本文 |
| Knowledge間の関係 | Relation Resolver・Relation Repository | Knowledge本文、Publisher Core |

## 6. Phase 5.1で確認した再利用性

`staining_method`で追加した仕組みのうち、Category Union、Category Envelope、Completenessの採点器、Workbench保存API、SQLite文書保存、Registry承認、Publisher Source Bundle、Publication Planは次Categoryでも再利用できます。

次Categoryで新たに作る主な部分は次の4点です。

1. 専用Schema
2. 専用Completeness要件
3. 代表用語の`claim_key`辞書
4. 既存Publisher Profileへの接続設定

Category内に他Knowledgeを示す名称がある場合は、Phase 5.2のRelation Vocabularyへ意味が一致する既存Typeがあるか確認します。対象Knowledgeが未登録なら、仮IDを作らず`unresolved_relation`として保存します。新しいRelation Typeは「便利そう」という理由では増やさず、実データで既存Vocabularyでは表せないことを示してから追加します。

対象Categoryを登録した後は、既存の未解決Relationを再評価します。解決時も元Knowledge本文を変更せず、同じ`relation_id`へ`target_knowledge_id`を設定してRelation Versionと履歴だけを更新します。特定の接続だけに当てはまる修飾語・前処理・条件は、target Knowledgeのaliasや本文ではなくRelation Contextへ保存します。

Phase 5.5では、保存API、Registry、Relation Index、Resolution Report、Network Summaryを変更せず再利用し、新規実装をSchema、Completeness、Claim Dictionary、Workbench表示、初期Knowledgeへ限定できました。共通フローの再利用率は引き続き約70〜80%です。残る20〜30%は医学カテゴリ固有の設計とテストであり、無理に共通化しません。

Phase 5.10の`disease`でも、Category Union、保存API、Registry、承認、履歴、Backup、Growth Engine、Publisher境界を再利用できました。疾患固有の追加はSchema、4項目のCompleteness、固定Claim Dictionary、Workbenchの表示・初期データに限定しています。Relationは件数を増やすことを目的にせず、接続先Knowledgeと適切なVocabularyが揃うまで0件を正しい状態として扱います。

Phase 5.11の`laboratory_test_item`でも同じ共通基盤を再利用し、Category固有の実装を最小Schema、4項目のCompleteness、フェリチンのClaim Dictionary、Workbench表示へ限定できました。Relation 0件とResolution Report 0件は失敗ではなく、無理な接続と全件走査を行っていない証拠です。旧`test_item`との互換性を保つ一方、量産前に移行方針を確定する必要があります。

## 7. 例外時の判断

新Categoryで既存の流れを通せない場合、すぐ新しいArchitecture Layerを追加しません。次の順で原因を分類します。

1. Knowledgeが不足している
2. claim_key辞書が不足している
3. 既存Profileの参照設定が不足している
4. Taxonomyが不足している
5. Completeness基準が不適切である
6. Category Schemaで医学的事実を表現できない
7. 既存共通契約そのものが不足している

上位の原因で解決できる間は、下位の大きな設計変更を行いません。
