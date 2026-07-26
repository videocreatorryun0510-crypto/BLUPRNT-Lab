# Phase 4.1 Vertical Slice Report — Gram染色

- 実施日: 2026-07-18
- 目的: 検査項目以外でも既存BLUPRNT Labが成立する範囲を実データで確認する
- 方針: Knowledge Schemaを変更せず、既存契約の範囲を最大限利用する
- 非対象: Render Blueprint、Renderer、SVG、AI画像、PDF Adapter変更

## 1. 結論

Gram染色は、**互換性検証用の`test_item`投影**を使うことで、SQLite Knowledge Registry、Dummy Exam Metadata、Content、Education、Visual、Visual Grammar、Diagram Intent、既存Diagram Taxonomy、Publication Plan 1.4、Semantic Blueprintまで到達しました。

ただし、この投影は正式なSingle Source of Truthにはできません。Gram染色を検査項目として分類し、染色固有の構造を文章へ平坦化しているためです。

この検証で、次を証明できました。

1. Registry以降の共通基盤は、検査項目以外でも再利用できる
2. Publisher Coreモデルや新しいレイヤーは不要
3. Content・Education・Visual・Grammar・IntentはProfile追加で対応できる
4. `taxonomy.workflow.staining.gram`は既存のままで利用できる
5. 正式運用に必要なSchema拡張は、染色法の医学的事実を損失なく保存する部分に限定できる

## 2. 到達結果

| コンポーネント | 結果 | 実測内容 |
|---|---:|---|
| Knowledge | △ | 現行`test_item`へ16/24 Claimを互換投影してSchema通過 |
| Registry | ○ | 16 ClaimをSQLiteへ登録・承認、並び替え後もID維持 |
| Exam Metadata | △ | 既存Schemaで生成成功、Dummy 2件、Exam Completeness 79% |
| Content Profile | ○ | 定義・工程・原理・比較・注意を選択 |
| Education Profile | ○ | 定義→頻出→工程図→工程→原理→比較→注意の順に解決 |
| Visual Profile | ○ | 染色工程図とGram陽性/陰性比較を選択 |
| Visual Grammar | ○ | 4工程と2列比較を既存Grammar契約で表現 |
| Diagram Intent | ○ | Laboratory WorkflowとComparisonを既存Intent契約で表現 |
| Diagram Taxonomy | ○ | 既存`workflow → staining → gram`と`comparison`を利用 |
| Publication Plan | ○ | Plan Schema 1.4を生成 |
| Semantic Blueprint | △ | Comparisonは完全、WorkflowはReagent不足を報告 |

実装上は、Publication PlanをClaim Mapping Resolverが入力に使うため、Publication Planの後にSemantic Blueprintを生成します。依頼文の表示順は変更せず、現行実装順で検証しました。

## 3. 既存Knowledgeで表現できたもの

設計サンプル24 Claimのうち、16 Claimを現行Schemaへ通せました。

| 医学的事実 | 既存の保存先 | 保持できた内容 | 制約 |
|---|---|---|---|
| 定義 | `core_facts.definitions` | 鑑別染色法であること | 問題なし |
| 目的 | `test_item.purposes` | Gram反応・形態・配列の観察 | 項目名は検査目的のまま |
| 対象構造 | `test_item.biological_basis` | 細胞壁構造との関係 | `target_name`・`target_kind`を失う |
| 検体 | `test_item.specimens` | 塗抹標本と薄く塗抹すること | 染色標本としての専用意味はない |
| 染色工程4件 | `test_item.measurement_methods` | 一次染色・媒染・脱色・対比染色 | `step_order`・試薬参照・条件を構造化できない |
| 染色原理2件 | `test_item.measurement_principles` | 複合体形成・色素保持性 | 測定原理という名称へ無理に投影 |
| Gram陽性/陰性結果 | `test_item.analyte_characteristics` | 紫色・赤色から赤桃色 | 対象・色・解釈を別フィールドにできない |
| 過脱色・脱色不足 | `test_item.interpretation_cautions` | 誤判定の原因と結果 | `error_type`・cause・effectを失う |
| 抗酸菌・マイコプラズマ | `test_item.interpretation_cautions` | 適用限界 | limitationの対象と理由を分離できない |

事実の文章は保持できますが、染色法としての意味構造が一部失われます。そのため「Schema OK」であっても正式な正本とは判定しません。

## 4. 表現できなかったもの

次の8 Claimは、意味を偽らず保存できる場所がないため投影しませんでした。

| Claim | 内容 | 保存しなかった理由 |
|---|---|---|
| `clm_40000005` | 固定法・固定条件 | 固定専用構造がない |
| `clm_40000008` | クリスタルバイオレット／一次染色液 | 試薬名と役割の構造がない |
| `clm_40000009` | ヨウ素液／媒染剤 | 試薬名と役割の構造がない |
| `clm_40000010` | 脱色液／脱色剤 | 試薬名と役割の構造がない |
| `clm_40000011` | サフラニン等／対比染色液 | 試薬名と役割の構造がない |
| `clm_40000018` | 既知Gram陽性菌の精度管理 | Controlと期待結果の構造がない |
| `clm_40000019` | 既知Gram陰性菌の精度管理 | Controlと期待結果の構造がない |
| `clm_40000024` | 抗酸菌染色との関係 | 関連「検査」でなく関連「染色法」であるため |

## 5. Schema変更が本当に必要な箇所

正式なKnowledge JSONとしてGram染色を保持するには、既存`KnowledgeRecord`の共通部分を変えるのではなく、Category Unionへ承認済み`staining_method`モデルを追加する必要があります。

最低限必要な専用構造は次です。

- `classification.term_type = staining_method`
- `category_content.template_id = staining_method_v1.0`
- 対象構造と対象種別
- 固定法と条件
- 試薬名と役割
- 染色工程の順番、使用試薬、時間、条件
- 結果対象、観察色、解釈
- 精度管理物質と期待結果
- エラー種別、原因、観察結果
- 適用限界の対象と理由
- 関連染色法と関係種別
- 染色法専用Completeness Profile

一方、次は変更不要です。

- Knowledge共通ID、Evidence、Publish Targets
- Registry Schema、Approval、History、SQLite
- Exam Metadata SchemaとProvider Interface
- Publisher CoreのProfileモデル
- Publication Planモデル
- Semantic Blueprintモデル
- Layout、Theme、Design System

## 6. Profile追加だけで解決できた箇所

次はCoreモデルを変更せず、版付きJSON Profileの追加だけで解決しました。

- Content Profile: `content.gram_stain_national_exam_pdf@1.0.0`
- Education Profile: `education.gram_stain_national_exam@1.0.0`
- Visual Profile: `visual.gram_stain_learning@1.0.0`
- Visual Grammar Profile: `visual_grammar.gram_stain_learning@1.0.0`
- Diagram Intent Profile: `diagram_intent.gram_stain_learning@1.0.0`
- Template: `template.gram_stain_national_exam_pdf@1.0.0`

既存のA4 Layout、Theme、Design Systemはそのまま再利用しました。

既存Layoutが`section.measurement_method`、`section.measurement_principle`、`visual.reaction_diagram`というAST由来のItem IDを固定参照しているため、Gram染色ProfileもItem IDだけは互換名を使用しました。医学的な役割は`role.staining_workflow`、`role.staining_principle`、`diagram.laboratory_workflow`として分離できています。正式版ではGram染色用Layout Profileを追加するか、既存LayoutのRole解決を見直す余地がありますが、Knowledge Schema変更とは無関係です。

## 7. Taxonomy追加だけで解決する箇所

今回、Taxonomy追加は**0件**です。

既存の次の分類で十分でした。

```text
taxonomy.workflow
└── taxonomy.workflow.staining
    └── taxonomy.workflow.staining.gram

taxonomy.comparison
```

染色工程の各試薬や各手順は医学的事実であり、図解分類ではありません。Taxonomyへ追加しない判断としました。

## 8. Visual Grammar追加だけで解決できた箇所

既存Visual Grammar契約で次を表現できました。

- 塗抹標本から4工程、結果へ進む左から右のWorkflow
- 一次染色、媒染、脱色、対比染色のNode
- 工程間のArrow
- 脱色工程のWarning強調
- Gram陽性／陰性を比較する2列構成
- 色そのものではなくPositive／Negativeという意味的強調

色、フォント、線幅は追加していません。引き続きThemeの責務です。

## 9. Education追加だけで解決できた箇所

AST用Education Profileを流用せず、同じEducation契約でGram染色用の教育順を追加しました。

```text
定義
↓
国家試験頻出情報
↓
染色工程図
↓
4工程
↓
染色原理
↓
Gram陽性／陰性比較
↓
注意点・誤答・出題履歴
```

学習目的、試験重要度、比較必須、教育ブロックの仕組みは共通のままです。

## 10. RegistryとExam Metadataの確認

### Registry

- 16 ClaimをSQLiteへ永続登録
- `gram.stain.*`の意味Keyを使用
- 4工程の入力順を逆転しても`claim_id`と`claim_key`を維持
- `draft → owner_review → medical_review → approved`を通過
- Registry Schema変更なし

`gram_stain.*`は既存Claim Key規則で先頭名前空間にアンダースコアを使えないため、`gram.stain.*`を採用しました。既存規則の変更は不要でした。

### Exam Metadata

- 既存Dummy ProviderへGram染色の検証データを追加
- 出題履歴2件
- Exam Completeness: 79%
- 実データではなく`manual_dummy`として識別

正式運用ではCSV Providerによる実データへ置き換える必要があります。

## 11. Completenessの評価

現行Test Item Completenessでの結果は58%でしたが、この数値はGram染色の完成度として利用できません。

不足扱いになった項目:

- 標準化・トレーサビリティ
- 報告単位・報告方式
- 基準範囲
- 高値・低値との関連
- 他検査との組み合わせ
- 干渉物質・分析上の影響
- 出典

基準範囲や高値・低値はGram染色に本来不要です。これは「Knowledgeが不足」ではなく「Completeness Profileがカテゴリ不適合」であることを示します。

## 12. Publication PlanとSemantic Blueprint

### Publication Plan

- Plan Schema: 1.4
- Content: 定義1、工程4、原理2、比較2、注意4
- Visual: Laboratory Workflow、Gram Reaction Comparison
- Taxonomy: `workflow → staining → gram`、`comparison`
- Education順: 全14 Stepを解決
- Knowledge本文をPlanへ複製しない境界を維持

### Semantic Blueprint

| Blueprint | 結果 | Mapping |
|---|---:|---|
| Gram Stain Workflow | △ | 9 Mapping、Reagent 4件不足 |
| Gram Reaction Comparison | ○ | 6 Mapping、不足なし |

WorkflowのReagent不足は、Knowledge Schemaに試薬専用保存先がないことをResolverが推測せず報告した結果です。

## 13. Architecture Decision

### 採用した設計

- 正式Schemaを変更せず、検証専用`test_item`投影を作る
- 失われるClaimを無理に別フィールドへ保存しない
- Registry Claim Dictionaryだけを既存機構へ追加する
- Publisher対応はCore変更でなくProfile追加で行う
- 既存Taxonomy、Layout、Theme、Design Systemを再利用する
- Semantic Blueprintに不足Reagentを残す

### 採用しなかった設計

- `test_item`を正式なGram染色Schemaとして扱う
- 試薬を検査対象の特徴として保存する
- 精度管理を高値・低値へ保存する
- 関連染色法を関連検査として保存する
- 染色工程をTaxonomy Nodeへする
- 不足ConceptをAIや本文推測で補う

### 理由

一時的に全項目を通すことより、どこで医学的意味が失われるかを明確にすることを優先したためです。

## 14. CTOレビュー

Publisher側の共通設計は、Gram染色でも十分機能しました。新しいレイヤーは不要です。最小の正式拡張点はKnowledge Category ModelとCategory Completenessです。

最大の注意点は、互換性投影がSchema Validationを通ることです。Schema OKだけを見ると正式データに見えるため、このFixtureを本番Knowledgeとして利用してはいけません。

次の段階では、既に承認済みの`staining_method_v1.0`設計をCategory Unionへ最小実装し、同じ16 Claimではなく24 Claimすべてを損失なくRegistryへ流します。その際もPublisher Profileは今回のものを基本的に再利用できます。

残る技術的負債は、染色法専用Schema／Completeness、Dummy Exam Metadata、検証用投影と正式Knowledgeの分離、AST由来Layout Item IDの互換利用です。いずれも新しいレイヤーを必要としません。

## 15. 検証証跡

- 正式染色法サンプル: 現行Schemaで安全に拒否
- 互換性投影: Knowledge Schema 1.0通過
- 設計Claim: 24件
- 投影Claim: 16件
- 意図的に未投影: 8件
- Registry並び替え非依存: 成功
- Approval: 成功
- Exam Metadata: 成功
- Profile Catalog: 成功
- Publication Plan 1.4: 成功
- Semantic Blueprint: 2件生成
- 新規Vertical Sliceテスト: 3件
- 全リポジトリ自動テスト: 164件成功
- Ruff静的検査: 成功
- 変更したRegistry／Exam Provider 2ファイルのmypy型検査: 成功
- Knowledge Schema変更: なし
- Diagram Taxonomy変更: なし
- Publisher Coreモデル変更: なし

Profile追加により、既存テストが「最初に読み込まれるPDF TemplateはAST」とファイル順へ依存していることも判明しました。テストをProfile IDとVersionの明示選択へ修正し、今後カテゴリが増えても順番で壊れないようにしました。製品コードの選択ロジックは変更していません。
