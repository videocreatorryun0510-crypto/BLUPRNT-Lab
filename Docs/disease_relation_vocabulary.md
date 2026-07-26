# Phase 5.12 — Disease Relation Vocabulary MVP

## 1. 目的

Disease Knowledgeを安全に他Categoryへ接続するため、Relation Typeの意味、方向、利用Category、例をVersion 1.0の機械可読Catalogとして固定した。

このPhaseではRelation実体を追加しない。鉄欠乏性貧血とフェリチンは引き続き独立Knowledgeであり、Knowledge JSON、Registry、保存済みRelation、Resolution Reportを変更しない。

## 2. Vocabulary一覧

すべてのRelationは、Relation台帳上では`source_knowledge_id → target_knowledge_id`として保存する。`related_disease`だけは意味を対称として扱う。

| Relation Type | 意味 | 方向 | 利用Category | 例 |
|---|---|---|---|---|
| `has_high_test_item` | 疾患・病態で検査項目が代表的に高値を示す | disease → laboratory_test_item | disease / laboratory_test_item | 鉄過剰症 → フェリチン |
| `has_low_test_item` | 疾患・病態で検査項目が代表的に低値を示す | disease → laboratory_test_item | disease / laboratory_test_item | 鉄欠乏性貧血 → フェリチン |
| `diagnosed_by` | 診断、確定、診断基準上の評価へ直接利用する | disease → 検査・方法 | disease / laboratory_test_item / examination_method / physiological_examination / morphologic_finding | 糖尿病 → HbA1c |
| `caused_by` | 疾患成立へ直接関与する病因・原因を示す | disease → 原因Knowledge | disease / microorganism / parasite / substance / genomic_entity / biological_process | 巨赤芽球性貧血 → ビタミンB12欠乏 |
| `related_disease` | 鑑別、併存、学習上の比較対象を示す。因果は示さない | disease ↔ disease | disease / disease | 鉄欠乏性貧血 ↔ 慢性疾患に伴う貧血 |
| `affects_structure` | 疾患が主に障害・変化・機能低下を及ぼす構造を示す | disease → biological_structure | disease / biological_structure | 心筋梗塞 → 心筋 |
| `has_pathophysiology` | 疾患を成立させる独立した病態生理過程を示す | disease → biological_process | disease / biological_process | 鉄欠乏性貧血 → ヘモグロビン合成低下 |

表中の例はVocabularyの読み方を示すだけで、Registryへ登録済みのRelationではない。

## 3. 命名規則

- 小文字`snake_case`を使用する。
- Diseaseを主語として読める能動的な名前にする。
- 高値と低値は意味が逆であるため別Typeにする。
- `related_*`は因果や診断を断定しない関連に限定する。
- `*_by`はRelationの向きを反転させず、Diseaseから原因・診断手段へ読む。
- 基準範囲、患者測定値、文章表現はRelation Typeへ含めない。
- 新しいTypeは実データ上の必要性、既存Typeとの非重複、方向、対象Categoryを確認してから追加する。

## 4. Contract変更

Relation Typeは自由入力ではない。既存Knowledge Relation Version 1.0／1.1を変更せず、7語を追加したKnowledge Relation Version 1.2を新設した。これにより、過去のSchema IDが後から別の意味になることを防ぐ。

さらに、次を持つ独立Catalogを追加した。

- `schema_version: 1.0`
- `vocabulary_id: relation_vocabulary.disease`
- `relation_contract_version: 1.2`
- Relation Type
- 意味
- 方向
- Source Category
- Target Category候補
- 読み方の例

Catalog自身にもJSON Schemaを用意した。Workbenchは`/api/relation-vocabulary/disease`を読むだけで一覧を表示し、RegistryやGrowth Engineへ書き込まない。

## 5. 既存データへの影響

| 対象 | 結果 |
|---|---|
| Knowledge本文 | 変更なし |
| 鉄欠乏性貧血 | Relation 0件のまま |
| フェリチン | Relation 0件のまま |
| Registry | Knowledge 12件、Claim 182件のまま |
| Relation台帳 | 13件のまま |
| Resolution Report | 既存件数のまま |
| Growth Engine | 索引規則・全件走査禁止を維持 |
| Publisher Core | 変更なし |

## 6. Workbench確認

1. `http://127.0.0.1:8000/`を開く。
2. 「疾患を安全につなぐ共通Vocabulary」を確認する。
3. `7 types · v1.0`を確認する。
4. 各カードでRelation Type、意味、方向、利用Category、例を確認する。
5. Registryの鉄欠乏性貧血とフェリチンがRelation 0件のままであることを確認する。

## 7. Architecture Decision

### 採用した設計

- 既存Relation 1.0／1.1を不変に保ち、Relation 1.2のEnumへ追加する。
- Disease専用の意味CatalogをEnumとは別に持つ。
- DirectionとCategory範囲を文章だけでなく構造化データにする。
- CatalogをVersion管理し、UIはAPIから読み取る。
- Relation実体の作成とVocabulary定義を別Phaseにする。

### 採用しなかった設計

- Relation名の自由入力。
- `abnormal_test_item`へ高値・低値をまとめる設計。
- `related_to`だけで原因、診断、鑑別を表す設計。
- Disease Knowledge本文へKnowledge IDを直接埋め込む設計。
- AIがRelation Typeや方向を推測する設計。

## 8. 次Phase前の品質ゲート

- プロダクトオーナーが7語の意味と例を承認する。
- 医学監修者が`diagnosed_by`を単なる関連検査へ誤用しない基準を確認する。
- `related_disease`の対称Relationを保存・検索する運用を決める。
- 最初の実Relation追加時に、Growth EngineのRelation Type→Target Category索引設定を追加する。

## 9. Technical Debt

- 新しい7語に対応するRelation Resolverは未実装。
- 保存RepositoryはRelation 1.1で稼働中で、Relation 1.2への実データ移行は未実施。
- Growth Engineの索引は既存4語だけに対応している。
- 複数Target Categoryを持つ`diagnosed_by`と`caused_by`の索引方式は未実装。
- `related_disease`の対称検索・重複防止規則は未実装。
- `biological_process`、`examination_method`等の接続先Categoryは未実装。
- Vocabularyの承認状態、変更履歴、廃止・置換先管理は未実装。
