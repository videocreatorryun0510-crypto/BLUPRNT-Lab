# Phase 4.0 Cross-Domain Coverage Report

- 実施日: 2026-07-18
- 対象: Knowledge RegistryからPublication Plan／Semantic Blueprintまで
- 方針: 不足を補完せず、既存Schema・Profile・データのまま検証
- 非対象: Taxonomy Governance、Blueprint Review、Render Blueprint、Renderer、SVG、AI画像、PDF Adapter変更

## 1. 結論

現在の共通基盤は、**検査項目カテゴリのASTでは最後まで動作**します。HbA1cではKnowledge、Registry、Exam Metadataまで再利用できましたが、Publisher ProfileがASTの`claim_key`とVisualを直接指定しているためContent Profileで停止しました。

染色法、微生物、寄生虫、疾患にはKnowledge JSON 1.0の設計サンプルがありますが、実装済み`KnowledgeRecord`は`term_type=test_item`と`test_item_v1.0`だけを受理します。このため4カテゴリはRegistryより前で停止します。追加4件はKnowledge資産自体がありません。

したがって、現時点の設計は「Publisher Coreの層分離」には成功していますが、「異なる医学カテゴリを実際に通す共通実装」には未到達です。Render Blueprintへ進む品質ゲートは満たしていません。

## 2. 判定記号

| 記号 | 意味 |
|---|---|
| ○ | 現在の実装と資産で実行・検証に成功 |
| △ | 構造またはデータは存在するが、不完全・未承認・Dummy・カテゴリ適合不足 |
| × | 現在の実装または資産では実行不能 |

「Schemaとして正しい」と「教材として十分」は別に評価しています。

## 3. 実行順に関する確認

依頼文ではSemantic Blueprintの後にPublication Planが記載されていますが、現在の実装上の実行順は次のとおりです。

```text
Knowledge + Registry + Exam Metadata
        ↓
Content / Education / Visual / Grammar / Intent / Taxonomy
        ↓
Publication Plan
        ↓
Claim Mapping Resolver
        ↓
Semantic Blueprint
```

Semantic Blueprint ResolverがPublication Planを入力として使うためです。本レポートは現行実装順で両方を検証しています。設計変更は行っていません。

## 4. Coverage Matrix

### 4.1 Knowledge基盤

| 用語 | カテゴリ | Knowledge | Registry | Exam Metadata |
|---|---|---:|---:|---:|
| AST | 検査項目 | △ | ○ | △ |
| HbA1c | 検査項目 | △ | △ | △ |
| Gram染色 | 染色法 | △ | × | × |
| 黄色ブドウ球菌 | 微生物 | △ | × | × |
| 蟯虫 | 寄生虫 | △ | × | × |
| 巨赤芽球性貧血 | 疾患 | △ | × | × |
| ABO | 輸血 | × | × | × |
| PCR | 遺伝子検査 | × | × | × |
| 尿沈渣 | 一般検査 | × | × | × |
| MDS | 疾患 | × | × | × |

### 4.2 Publisher基盤

| 用語 | Content | Education | Visual | Grammar | Intent | Taxonomy | Semantic Blueprint | Publication Plan |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| AST | ○ | ○ | ○ | ○ | ○ | ○ | △ | ○ |
| HbA1c | × | △ | × | × | × | △ | × | × |
| Gram染色 | × | △ | × | × | × | ○ | × | × |
| 黄色ブドウ球菌 | × | △ | × | × | × | × | × | × |
| 蟯虫 | × | △ | × | × | × | × | × | × |
| 巨赤芽球性貧血 | × | △ | × | × | × | △ | × | × |
| ABO | × | △ | × | × | × | × | × | × |
| PCR | × | △ | × | × | × | × | × | × |
| 尿沈渣 | × | △ | × | × | × | × | × | × |
| MDS | × | △ | × | × | × | △ | × | × |

Educationの△は、国家試験重要度・履歴・比較を扱う共通方針は再利用できる一方、必須学習順が`role.measurement_method`、`diagram.reaction`、`table.comparison`等の検査項目向け構成に固定されていることを表します。

## 5. 実測結果

### 5.1 AST（検査項目）

問題なく通過したもの:

- Knowledge JSON Schema 1.0
- 承認済みRegistryを含むPublication Source Bundle
- Content、Education、Visual、Visual Grammar、Diagram Intent、Diagram Taxonomy
- Publication Plan 1.4
- Semantic Blueprint 1.1の生成

不足:

- Publisher検証用Knowledge Completeness: 27%
- Exam Completeness: 37%
- Knowledge不足: 検体、試薬、目的、基準範囲、高値・低値、干渉、注意点、出典等
- Semantic Blueprint不足: MeasurementのSample・Reagent、Disease MechanismのCause・Tissue
- Exam不足: CSV由来、十分な出題履歴、重要Claim、出題パターン、関連用語、誤答情報

補足:

- 実Workbench Registry内のASTは`draft`です。
- 最後まで通ったASTはPublisher用固定サンプル内の承認済みRegistryを利用しています。
- 「処理が通る」ことは「教材として十分」を意味しません。

### 5.2 HbA1c（検査項目）

問題なく通過したもの:

- WorkbenchからKnowledge JSON 1.0生成
- SQLite Registryへの18 Claim登録
- Dummy Exam Metadata生成
- 診断用一時DBで承認遷移を再現したPublication Source Bundle

実測値:

- Knowledge Completeness: 60%
- Exam Completeness: 79%
- 実Workbench Registry: Knowledge・18 Claimとも`draft`

停止地点:

```text
PublisherPlanError:
required Content section has no approved source: section.definition
```

原因:

- Content Profileが`ast.definition.aminotransferase_enzyme`等を直接指定
- Visual Profileが`ast.jscc`、`ast.measurement.340nm`、`ast.combination.alt`を直接指定
- HbA1c用Visual、Grammar、Intentがない
- TaxonomyにHPLC、免疫法、糖化過程、時間軸の分類がない

### 5.3 Gram染色（染色法）

存在する資産:

- Knowledge JSON 1.0設計サンプル
- 24個のClaim設計
- `taxonomy.workflow.staining.gram`

停止地点:

- 現行Knowledge Schemaが`term_type=staining_method`を拒否
- 実装Schemaは`test_item`のみ受理

不足:

- Staining Methodの実装済みModel／Validation／Completeness
- Registry登録可能な実装済みKnowledge Record
- Exam Metadataデータ
- 染色工程用Content、Visual、Grammar、Intent
- 設計サンプルのEvidenceは0件

Taxonomyは通過できますが、上流Knowledgeと接続ProfileがないためBlueprintは生成できません。

### 5.4 黄色ブドウ球菌（微生物）

存在する資産:

- Knowledge JSON 1.0設計サンプル
- 16個のClaim設計

停止地点:

- 現行Knowledge Schemaが`term_type=microorganism`を拒否

不足:

- Microorganismの実装済みModel／Validation／Completeness
- 培地、同定、毒素、耐性を選択するContent Profile
- 微生物形態・同定Workflow用Visual、Grammar、Intent
- Microorganism／Identification／ResistanceのTaxonomy
- Exam MetadataとEvidence

### 5.5 蟯虫（寄生虫）

存在する資産:

- Knowledge JSON 1.0設計サンプル
- 17個のClaim設計

停止地点:

- 現行Knowledge Schemaが`term_type=parasite`を拒否

不足:

- Parasiteの実装済みModel／Validation／Completeness
- 生活環、虫卵形態、採取法を扱うContent Profile
- Life Cycle／Morphology用Visual、Grammar、Intent
- Parasite／Life Cycle／Egg MorphologyのTaxonomy
- Exam MetadataとEvidence

### 5.6 巨赤芽球性貧血（疾患）

存在する資産:

- Knowledge JSON 1.0設計サンプル
- 16個のClaim設計
- Disease MechanismのRoot Taxonomy

停止地点:

- 現行Knowledge Schemaが`term_type=disease_condition`を拒否

不足:

- Disease Conditionの実装済みModel／Validation／Completeness
- 原因、病態、血算、末梢血像、骨髄像、鑑別用Content Profile
- DNA合成障害、無効造血、血球形態用Visual、Grammar、Intent
- `DNA Synthesis Impairment → Ineffective Hematopoiesis`相当のTaxonomy Leaf
- Exam MetadataとEvidence

`taxonomy.disease.bone_marrow_failure`は存在しますが、巨赤芽球性貧血の正確な分類としてそのまま採用できるとは判定していません。

### 5.7 ABO・PCR・尿沈渣・MDS

リポジトリ内に、これら4件のKnowledge JSON、Registry、Exam Metadataはありませんでした。そのためKnowledge Registryより前で停止します。

| 用語 | 追加で確認できた部分 | 主な不足 |
|---|---|---|
| ABO | 共通Transfusion Exam Domainのみ | Knowledge、輸血Taxonomy、反応・判定Visual一式 |
| PCR | 共通モデルに検査工程の概念のみ | Knowledge、遺伝子増幅Taxonomy、Workflow Intent一式 |
| 尿沈渣 | なし | Knowledge、顕微鏡・形態Taxonomy、Visual一式 |
| MDS | Disease／Bone Marrow Failureの上位Taxonomy | Knowledge、MDS固有Taxonomy、形態・病態Intent一式 |

## 6. Category別不足集計

| カテゴリ | 不足Knowledge | 不足Claim | Taxonomy不足 | Intent不足 | Grammar不足 | Education不足 |
|---|---|---|---|---|---|---|
| 検査項目 AST | 検体・試薬・疾患機序・出典 | Sample、Reagent、Cause、Tissue | なし | なし | なし | 内容は通るがKnowledge不足を強く制限していない |
| 検査項目 HbA1c | 出典・標準化・基準・干渉 | Registryは18件あるが全件draft | HPLC、免疫、糖化、時間軸 | HbA1c用なし | 糖化・時間軸なし | AST測定順に固定 |
| 染色法 | 実装Schema・Evidence | 設計24件をRegistryへ登録不能 | なし | 染色工程なし | 染色工程なし | 測定法順に固定 |
| 微生物 | 実装Schema・Evidence | 設計16件をRegistryへ登録不能 | 形態・培養・同定・毒素・耐性 | 微生物同定なし | 培養・同定なし | 微生物学習順なし |
| 寄生虫 | 実装Schema・Evidence | 設計17件をRegistryへ登録不能 | 生活環・虫卵形態・採取 | Life Cycleなし | Life Cycleなし | 寄生虫学習順なし |
| 疾患 | 実装Schema・Evidence | 設計16件をRegistryへ登録不能 | 疾患固有機序 | 疾患固有なし | 血球形態・病態なし | 疾患学習順なし |

## 7. 十分に機能した設計

- Registryの`knowledge_id`、`claim_id`、`claim_key`分離はHbA1cでも利用できた
- Exam Metadata Provider境界はASTとHbA1cで交換・生成できた
- Publication Source BundleはKnowledge／Registry／Examの版不一致を検出できた
- Profile、Template、TaxonomyのVersion固定と参照検証は機能した
- ASTではContentからSemantic Blueprintまで責務分離を維持できた
- Resolverは不足Conceptを推測で補完せず報告した
- Knowledge JSONをPublisherが変更しない境界は維持された

## 8. 共通設計が不足した箇所（Technical Debt）

1. Knowledge JSON 1.0実装が検査項目専用
2. Content Profileが意味RoleではなくAST固有Claim Keyを直接指定
3. Visual ProfileがAST固有Claim Key、Caption、Visual構成へ固定
4. Education Profileの必須順が検査項目・AST向けVisual Typeへ固定
5. Visual GrammarとDiagram IntentがAST用Profileしかない
6. Diagram Taxonomyの初期範囲が測定法・染色の一部・病態の一部・比較だけ
7. Exam Metadataの実データ接続がなく、AST／HbA1c Dummyに限定
8. Live RegistryのAST／HbA1cがdraftで、Publisher用承認済みサンプルと分離
9. Category Completenessが検査項目だけ実装済み

## 9. 既存設計をどう改善すべきか

新しい層を追加するのではなく、既存コンポーネントを次の方向へ改善する必要があります。

1. **Knowledge Models**
   - 承認済みカテゴリ設計を既存`KnowledgeRecord`のCategory Unionとして実装する
   - カテゴリごとのValidationとCompletenessを同じ契約群へ追加する

2. **Content Profile**
   - `ast.*`の完全一致だけでなく、カテゴリのSemantic Field PathとRoleで選べるようにする
   - Knowledge固有Claim KeyはProfile変数またはKnowledge Namespaceとして解決する

3. **Education Profile**
   - 国家試験共通方針と、検査項目・染色・微生物・寄生虫・疾患の学習順を同じEducation Profile契約内の別Version／別Profileにする
   - `diagram.reaction`を全カテゴリ必須にしない

4. **Visual／Grammar／Intent**
   - 既存Registryへカテゴリ別Profileを追加し、モデルや新層は増やさない
   - GrammarはAST固有素材IDと再利用可能な図解文法を分ける

5. **Diagram Taxonomy**
   - 既存台帳へMicroorganism、Parasite、Transfusion、Molecular Test、Microscopy、Disease MechanismのLeafを追加する
   - 医学監修前にTaxonomy IDを確定しない

6. **Registry／Publisher接続**
   - Workbenchの承認済みRegistry ViewからPublication Source Bundleを作る既存境界を正式経路にする
   - Publisher固定サンプルとLive Registryの二重管理を解消する

7. **Exam Metadata**
   - 既存Provider構造のままCSV Provider対象を全カテゴリへ広げる
   - Dummyを正式な出題根拠として扱わない

## 10. 次の品質ゲート

Render Blueprintへ進む前に、最低限次を満たす必要があります。

- 検査項目以外の1カテゴリが実装Knowledge Schemaを通る
- そのKnowledgeがRegistryで承認可能
- Category用Content・Education・Visual・Grammar・Intentが既存Registryで解決される
- Taxonomy IDが医学的に妥当
- Semantic Blueprintが不足を含めて生成される
- Publication PlanがAST固有Claim Keyなしで生成される

推奨する最初の横断対象はGram染色です。Knowledge設計サンプルと正確なTaxonomy IDが既にあり、染色工程というASTとは異なる図解構造を検証できるためです。

## 11. 検証証跡

- 全リポジトリ自動テスト: 161件成功
- AST Publication Plan 1.4生成: 成功
- AST Semantic Blueprint 1.1生成: 成功、3件中2件に不足
- HbA1c Knowledge 1.0生成: 成功
- HbA1c Registry登録: 成功、18 Claim
- HbA1c Dummy Exam Metadata: 成功
- HbA1c診断用承認Source Bundle: 成功
- HbA1c Publication Plan: Content Profileで意図どおり停止
- 4カテゴリ設計JSONの現行Schema Validation: 全件`term_type`で停止
- 追加4件のリポジトリ資産検索: 該当Knowledgeなし
- 既存PDFの非回帰Hash: `89afd8c3bd4d744a46784d179634776e076fe1cfc30d2f66c668714e707d4153`
