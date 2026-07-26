# Phase 5.10 — Disease Category MVP

## 1. 目的

鉄欠乏性貧血1件を使い、疾患Knowledgeでも既存のCategory Union、Registry、Completeness、承認、履歴、Growth Engineをそのまま利用できることを確認した。

Disease全体の分類体系を完成させるフェーズではない。ICD、SNOMED CT、重症度、治療ガイドライン、AI診断は扱わない。

## 2. Disease Category

正式Category IDは`disease`、テンプレートIDは`disease_v1.0`とする。

| 保存領域 | 役割 |
|---|---|
| `core_facts.definitions` | 疾患の定義 |
| `overview` | 最小限の全体像 |
| `pathophysiology` | 病態の段階と上流Claim参照 |
| `causes` | 原因・背景 |
| `main_symptoms` | 代表的な臨床所見 |
| `main_laboratory_findings` | 検査名、方向・結果、検体、条件、医学的主張 |
| `differential_points` | 比較対象と区別する事実 |
| `national_exam_point_claim_ids` | 国家試験で優先する既存の医学Claim参照 |
| `evidence` | 各Claimを支える資料 |

国家試験向けの説明文をKnowledgeへ重複保存せず、重要な医学的事実のClaim IDだけを参照する。実際の出題履歴、頻度、誤答傾向は独立したExam Metadataへ保存する。

## 3. Completeness

正式登録に必要な最小4項目だけを評価する。

| 項目 | 配点 | 不足時 |
|---|---:|---|
| 定義 | 25 | 79点以下へ制限 |
| 病態 | 30 | 49点以下へ制限 |
| 主な検査所見 | 30 | 49点以下へ制限 |
| 出典Claim対応率 | 15 | 対応率に応じて減点 |

鉄欠乏性貧血は17 Claimすべてに出典参照があり、Knowledge Completenessは100%となった。この点数は情報欄が揃っていることを示し、医学的承認済みであることは示さない。

## 4. 鉄欠乏性貧血Knowledge

- Knowledge ID：`knw_10000012`
- Registry Key：`disease.iron_deficiency_anemia`
- Knowledge Version：1
- Status：`draft`
- Claim：17件
- Relation：0件
- Resolution Report：再評価0件、解決0件、未解決0件

主な検査所見として、小球性低色素性、血清フェリチン低値、血清鉄低値、TIBC高値、トランスフェリン飽和度低値、末梢血塗抹所見を別Claimで保存した。慢性炎症に伴う貧血とサラセミアの鑑別も別Claimで保持する。

医学的根拠は[日本血液学会「鉄欠乏性貧血の診断と鉄剤治療」](https://www.jstage.jst.go.jp/article/rinketsu/65/6/65_503/_article/-char/ja/)、[日本臨床検査医学会 JSLM 2024](https://www.jslm.org/books/guideline/2024/GL2024_05.pdf)、[NCBI Bookshelf](https://www.ncbi.nlm.nih.gov/books/NBK560876/)を参照した。国家試験範囲との対応は[厚生労働省「令和7年版臨床検査技師国家試験出題基準」](https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000088793_00004.html)で確認した。

## 5. Relationを追加しなかった判断

鉄欠乏性貧血からは、検査項目、検体、生体物質、他疾患への接続候補を考えられる。しかし現在のRegistryには対応Knowledgeが揃っておらず、既存Relation Vocabularyにも疾患用の意味型がない。

件数を増やすために文字列Relationや不適切な`uses_specimen`を作ると、将来の意味変更が必要になる。そのため今回はRelation 0件を正しい結果とした。Growth EngineはDisease保存イベントで該当する未解決索引候補だけを検索し、0件のResolution Reportを保存した。既存Knowledgeの全文走査は行っていない。

## 6. Platform変化

| 指標 | Phase 5.9 | Phase 5.10 |
|---|---:|---:|
| Category Union | 5 | 6 |
| Registry Knowledge | 10 | 11 |
| Claim | 154 | 171 |
| Relation | 13 | 13 |
| 永続Knowledge JSON | 8 | 9 |
| 永続データ内Category | 4 | 5 |

`test_item`はCategory Unionに含まれるが、AST・HbA1cのKnowledge JSON本文はまだ旧生成経路から正式永続化されていないため、永続データ内Category数は5である。

## 7. Workbench確認

1. `http://127.0.0.1:8000/`を開く。
2. 「正式Knowledgeを登録・編集」で「鉄欠乏性貧血を開く」を押す。
3. `Schema OK`、`Disease Completeness 100%`、Knowledge IDを確認する。
4. JSON編集欄で病態、主な検査所見、鑑別、出典を確認する。
5. RegistryのKnowledge一覧で「鉄欠乏性貧血」を選び「表示」を押す。
6. Version 1、Claim Dictionary 17件、Relation 0件、未承認を確認する。

## 8. Architecture Decision

採用したのは、共通Envelopeと疾患専用内容を分けたCategory Union、医学的事実ごとの固定Claim、医学CompletenessとExam Completenessの分離である。

採用しなかったのは、単一の巨大な全Category Schema、治療情報、疾患分類Ontology、表示用国家試験文章、Relationの強制追加である。MVPの疾患1件で必要性が証明されていない要素を入れると、今後の疾患追加時に不要な移行が増えるためである。

## 9. 検証結果

- 全自動テスト：193件成功
- 型検査：63 source files、問題なし
- コード品質検査：問題なし
- JavaScript構文検査：問題なし
- Publisher Core：9ファイルのハッシュがPhase 5.8基準と一致
- Registry Backup：`registry_20260719_182701.db`

## 10. 残課題

- 鉄欠乏性貧血は`draft`で、Owner Review・Medical Review・Approvedが未実施
- 12年分CSVからのDisease Exam Metadata取込が未実施
- Claim DictionaryがPythonコード内にあり、1000 Knowledge規模では外部設定・管理UIが必要
- 文章類似によるMerge候補に、血清鉄・TIBC・TSATの別Claimが誤候補として表示される
- Disease用Relation Vocabularyは実データが増えてから決定する
- AST・HbA1cのKnowledge JSON本文を正式Registryへ移行していない
- 負荷、同時編集、権限、監査、障害復旧試験はProduction Ready前の品質ゲートとして残る
