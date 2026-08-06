# Phase 5.21 Pilot Medical Review Gap Report

- Review date: 2026-08-06
- Scope: Gram染色、鉄欠乏性貧血、フェリチン
- Method: 実SQLite Registryと保存済みKnowledge JSONの読取確認
- Important: 医学レビューそのものではなく、正式レビュー開始前の不足調査

## 1. 結論

3件ともSchemaとCategory Completenessの基礎は整い、全active ClaimにEvidence IDの参照がある。一方、KnowledgeとClaimは全件`draft`で、Medical Reviewer、Review Decision、Checklist Version、Evidence Assessment、独立Review Version、次回Review期限が存在しない。

したがって、3件とも`approved`へ進められない。Phase 5.21ではApproval Stateを変更していない。

## 2. Registry Snapshot

| Knowledge | Knowledge ID | Category | Knowledge Version | Knowledge State | Claim | Claim State | Evidence | Evidence参照Claim | Relation |
|---|---|---|---:|---|---:|---|---:|---:|---:|
| Gram染色 | `knw_10000004` | `staining_method` | 1 | draft | 24 | 24件すべてdraft | 4 | 24 / 24 | 7件、すべてdraft |
| 鉄欠乏性貧血 | `knw_10000012` | `disease` | 1 | draft | 17 | 17件すべてdraft | 3 | 17 / 17 | 0 |
| フェリチン | `knw_10000013` | `laboratory_test_item` | 1 | draft | 11 | 11件すべてdraft | 4 | 11 / 11 | 0 |

「Evidence参照Claim 100%」はIDが紐付いていることだけを示す。出典の該当箇所がClaimを十分支持することは、まだ人が確認していない。

## 3. 共通して不足しているReview情報

| 不足 | 影響 | approved前に必要な対応 |
|---|---|---|
| 認証済みReviewer ID | 誰が確認したか保証できない | Reviewer Profileと本人確認 |
| Reviewer専門領域・資格確認 | 対象をレビューできるか不明 | Role assignmentと資格・scope確認 |
| Review Decision | 医学判断が記録されていない | Claim単位とKnowledge全体のDecision |
| Checklist ID / Version | 何を確認したか再現できない | 共通＋Category Checklist Version 1.0実施 |
| Evidence Policy Version | 出典採用基準が再現できない | Evidence Policy Version 1.0で評価 |
| Evidence Assessment | ID参照はあるが直接支持・適用範囲の判定がない | ClaimごとのLevel、locator、support判定 |
| 独立Review Version | Knowledge Versionと再確認回数を分離できない | 最初のReview Record `r1`作成 |
| Review Comment / 日時 | 判断理由と時点が不明 | Reviewer・Final Approverの記録 |
| validity / review_due_at | 古くなった時に停止できない | temporal classと次回期限設定 |
| 利益相反 | Reviewerの中立性を評価できない | COI declaration |

## 4. Gram染色

### 4.1 現在利用できる材料

- `staining_method_v1.0`で定義、目的、対象構造、固定、原理、試薬、工程、判定、QC、エラー、限界、安全を保持
- Category Completeness 100%を既存Phaseで確認
- 24 ClaimすべてにEvidence ID参照
- Evidence 4件：ASM Gram Stain Protocolをprimary、ASM/NCBI資料をsupportingとして登録
- 試薬、検体、関連法、細菌細胞壁へのRelation 7件はKnowledge ID解決済み

### 4.2 不足と確認事項

| 種別 | Gap |
|---|---|
| Reviewer | 微生物検査・染色実務を確認できる臨床検査技師Reviewerが未割当 |
| Evidence Level | 現登録は主に海外学会・教育資料。国内標準法、国内専門団体資料、採用SOPとの位置づけが未評価 |
| Locator | primary protocolが19 Claimを支持するが、章・ページ・工程番号が未記録 |
| Applicability | Manual/automated、試薬、時間、温度、施設SOPの適用範囲がReview記録にない |
| Claim Review | 原理、脱色、判定、QC、エラー、安全の24 Claimを個別確認していない |
| Relation Review | 7 Relationは解決済みだが、Relation Type、方向、Context、根拠Claimの承認記録がない |
| Time | 標準法・SOPのvalidityと次回Review期限がない |
| Exam | Exam Metadataの問題履歴は0件で、国家試験対応のReviewは未実施 |

### 4.3 approvedへ進める残作業

1. 微生物検査領域のMedical ReviewerとFinal Approverを割り当てる。
2. `COMMON-*`と`STAIN-*` Checklistを全件実施する。
3. 国内標準・専門団体資料・施設SOPの採否を確認し、海外資料を使う理由を残す。
4. 24 Claimすべてへ具体的locatorとEvidence Assessmentを記録する。
5. 7 RelationをKnowledgeとは独立してレビューする。
6. Review期限を設定し、全blocker pass後にReview Decisionを記録する。

## 5. 鉄欠乏性貧血

### 5.1 現在利用できる材料

- `disease_v1.0`で定義、病態、原因、症状、検査所見、鑑別、国家試験ポイントを保持
- Category Completeness 100%を既存Phaseで確認
- 17 ClaimすべてにEvidence ID参照
- 日本血液学会、日本臨床検査医学会、NCBI Bookshelfの3資料を登録
- 国内2024年資料を含む

### 5.2 不足と確認事項

| 種別 | Gap |
|---|---|
| Reviewer | 血液疾患を確認できる医師Reviewerが未割当 |
| Locator | 日本血液学会資料は10 Claimを支持するが、Claimごとの具体的箇所確認が未記録 |
| Evidence Level | NCBI資料が8 Claimをsupportする。国内資料で直接確認できる範囲と補助範囲の分離が未評価 |
| Claim Review | 病態、原因、症状、検査所見、鑑別の17 Claimを個別確認していない |
| Threshold | 診断特性や数値を扱う場合の対象集団、単位、method、jurisdiction、validityがReview Recordにない |
| Relations | 現時点でRelation 0件。無理なRelation追加は不要だが、将来接続時のRelation Reviewが必要 |
| Time | 2024年資料の改訂確認日と次回Review期限がない |
| Exam | 国家試験ポイントはあるが、実CSVに基づくExam Metadata Reviewは未実施 |

### 5.3 approvedへ進める残作業

1. 血液領域の医師Medical Reviewerを割り当てる。
2. `COMMON-*`と`DISEASE-*` Checklistを実施する。
3. 17 Claimと資料の具体的箇所を一対一で確認する。
4. 国内資料を主根拠とする範囲、海外資料を補助とする範囲を記録する。
5. 診断・検査所見の時点依存性とReview期限を設定する。
6. Review DecisionとFinal Approvalを、Relation・Exam Metadata承認とは分離して記録する。

## 6. フェリチン

### 6.1 現在利用できる材料

- `laboratory_test_item_v1.0`で定義、測定対象、臨床的意義、高値・低値、主な測定法を保持
- Knowledge Completeness 100%、Exam Completeness 0%を既存Phaseで確認
- 11 ClaimすべてにEvidence ID参照
- 日本臨床衛生検査技師会、日本臨床検査医学会、PMDA添付文書2件の4資料を登録
- 既存Artifactは`education_review`で、KnowledgeがdraftのためRenderer停止中

### 6.2 不足と確認事項

| 種別 | Gap |
|---|---|
| Reviewer | 臨床化学・免疫測定・鉄代謝を確認できる臨床検査技師Reviewerが未割当。疾患解釈は必要に応じ医師確認 |
| Product scope | PMDA添付文書に基づく測定法Claimが、該当製品・版を超えて一般化されていないか未評価 |
| Locator | JAMT資料が8 Claimを支持するが、Claimごとのページ・節の直接確認が未記録 |
| Clinical interpretation | 貯蔵鉄、炎症、高値・低値の11 Claimについて条件・例外・断定強度を未確認 |
| Time | 添付文書の現行性、valid_from/until、製品scope、12か月Review期限が未設定 |
| Reference range | 今回Schema対象外で未実装。将来追加時は方法・単位・対象集団・施設差をCritical Review対象にする |
| Exam | Exam Completeness 0%。医学Knowledge承認とは独立だが、国家試験教材の出題実績表示には別Reviewが必要 |

### 6.3 approvedへ進める残作業

1. 臨床化学・免疫測定領域のMedical Reviewerを割り当てる。
2. `COMMON-*`と`LABTEST-*` Checklistを実施する。
3. 11 ClaimのEvidence locator、Level、support、method/product scopeを記録する。
4. PMDA添付文書の現行版と製品依存範囲を確認する。
5. 炎症時の解釈と高値・低値Claimの条件・例外を確認する。
6. Review期限を設定し、Artifactとは独立したKnowledge Reviewを完了する。

## 7. Pilot比較

| 観点 | Gram染色 | 鉄欠乏性貧血 | フェリチン |
|---|---|---|---|
| 構造的準備 | ○ | ○ | ○ |
| Claim-Evidence ID対応 | ○ | ○ | ○ |
| 国内Level A候補 | △ | ○ | ○ |
| Medical Reviewer | × | × | × |
| Claim個別Review | × | × | × |
| Checklist / Policy Version | × | × | × |
| 独立Review Version | × | × | × |
| Time-sensitive管理 | × | × | × |
| 現時点でapproved可能 | × | × | × |

## 8. 最初の正式Pilot候補

推奨順：

1. **Gram染色** — CategoryとKnowledge Networkが最も成熟し、Review手順とRelation Reviewを同時に検証できる。ただし国内標準・SOPの根拠補強が先。
2. **フェリチン** — 国内専門団体・PMDA資料が揃い、Laboratory Test Itemのtime/product scopeを検証できる。
3. **鉄欠乏性貧血** — 疾患の医学的判断を含むため、医師Reviewerと外部監修ルール確定後に行う。

## 9. Approval State不変確認

Phase 5.21の設計作業では以下を変更していない。

- `knw_10000004`と24 Claim：draft
- `knw_10000012`と17 Claim：draft
- `knw_10000013`と11 Claim：draft
- Gram染色Relation 7件：draft
- フェリチンArtifact：既存のeducation_review

本レポートはRegistryを読み取っただけで、承認・差し戻し操作を行っていない。
