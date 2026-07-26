# Phase 5.11 — Laboratory Test Item Category MVP

## 1. 結論

`laboratory_test_item`を7番目のKnowledge Categoryとして追加し、フェリチン1件を`knw_10000013`としてSQLite Registryへ正式登録した。

今回の「正式登録」は、安定ID、版、履歴、編集、Backupを利用できるKnowledge Platform上の登録を意味する。医学的承認を意味しない。フェリチンと11 Claimの状態は`draft`であり、公開前にプロダクトオーナー確認と医学監修が必要である。

## 2. Categoryの責務

| 識別子 | 値 |
|---|---|
| Category ID | `laboratory_test_item` |
| Template ID | `laboratory_test_item_v1.0` |
| 最初のKnowledge | フェリチン |
| Knowledge ID | `knw_10000013` |
| Registry Key | `laboratory_test.ferritin` |
| Knowledge Version | 1 |
| Claim | 11件 |
| Relation | 0件 |

このCategoryは、疾患や測定手順そのものではなく、「何を測る検査項目か」「結果を臨床的にどう解釈するか」を表す。

### MVPで保持する医学的事実

- 定義
- 概要
- 測定対象
- 臨床的意義
- 高値となる主な病態
- 低値となる主な病態
- 主な測定法
- 出典

Reference Range、単位、測定原理、測定装置、地域差、LOINC、JLAC10は今回の契約へ入れていない。検査項目の正本を1件運用できる最小範囲を先に完成させ、方法依存・施設依存の値を普遍的事実へ誤って固定しないためである。

## 3. Completeness

Schema Validationと情報量評価を分ける。MVPの100点は次の4項目だけで算出する。

| 評価項目 | 重み | 扱い |
|---|---:|---|
| 定義 | 20 | 必須 |
| 臨床的意義 | 30 | 重要必須 |
| 測定対象 | 35 | 重要必須 |
| 出典 | 15 | 推奨 |

重要必須が欠けた場合は49点以下へ制限する。100%は「このMVPが求めた情報欄と根拠の対応が揃った」ことを意味し、医学的正確性、国家試験情報、承認状態を表さない。

フェリチンはKnowledge Completeness 100%、Exam Completeness 0%である。国家試験CSVをまだ紐付けていないため、この差は正しい。

## 4. フェリチンKnowledge

フェリチンは貯蔵鉄を評価する指標である一方、炎症などでも上昇し得るため、鉄欠乏の事実と炎症時の解釈を別Claimとして保存した。高値の病態は鉄過剰、炎症、マクロファージ活性化を伴う病態に分け、低値は鉄欠乏として保持した。測定法はラテックス凝集比濁法と化学発光酵素免疫測定法を別Claimにした。

医学的下書きの根拠は、日本臨床衛生検査技師会の報告、日本臨床検査医学会ガイドライン、PMDA電子添文へClaim単位で関連付けている。

- 日本臨床衛生検査技師会：測定範囲を拡大した「イアトロ フェリチン」の性能評価
- 日本臨床検査医学会：臨床検査のガイドライン JSLM 2024
- PMDA：LT オートワコー フェリチン 電子添文
- PMDA：化学発光酵素免疫測定法によるフェリチン測定試薬の電子添文

## 5. RegistryとGrowth Engine

固定Claim Keyは`labtest.ferritin.definition`、`labtest.ferritin.target.serum_or_plasma_ferritin`、`labtest.ferritin.method.ltia`のように意味で決める。JSON配列の順番はID決定に使用しない。同じKnowledgeを内容変更なしで再保存しても、Knowledge Version 1と11個のClaim ID・Claim Keyを維持する。

フェリチン登録ではRelationを作成していない。鉄欠乏性貧血本文に「血清フェリチン低値」というClaimは存在するが、今回の要求どおり、十分な接続方針と関連Knowledgeが揃うまで独立資産のままにする。

保存イベント時のResolution Reportは次のとおりである。

| 指標 | 件数 |
|---|---:|
| 再評価 | 0 |
| 解決 | 0 |
| 未解決のまま | 0 |

全文走査は行わず、索引に候補がないため0件で終了した。

## 6. Platform集計の変化

| 指標 | Phase 5.10 | Phase 5.11 |
|---|---:|---:|
| Category Union | 6 | 7 |
| Registry Knowledge | 11 | 12 |
| Claim | 171 | 182 |
| Relation | 13 | 13 |
| 保存済みKnowledge JSON | 9 | 10 |
| 保存済みデータのCategory | 5 | 6 |

Category Unionには旧AI生成経路の`test_item`も含む。AST・HbA1cのKnowledge JSON本文はまだ新しい`laboratory_test_item`へ移行していないため、保存済みデータのCategory数とCategory Union数は一致しない。

## 7. Workbench確認手順

1. `http://127.0.0.1:8000/`を開く。
2. 「フェリチンを開く」を押す。
3. `保存済みの正本を開きました`、Schema OK、Laboratory Test Item Completeness 100%を確認する。
4. JSONで`knw_10000013`、`laboratory_test_item`、`laboratory_test_item_v1.0`を確認する。
5. Registry一覧で「フェリチン · v1 · 下書き」を選び、「表示」を押す。
6. Claim Dictionary 11件、Relation 0件、Knowledge Version v1を確認する。
7. 修正する場合は操作者と理由を入力して保存する。内容を変えず再保存しても版とIDは変わらない。

事前Backupは`registry_20260720_070922.db`として作成済みである。

## 8. Architecture Decision

### 採用した設計

- 旧`test_item`を書き換えず、正式Categoryとして`laboratory_test_item`をCategory Unionへ追加する。
- 共通Envelopeと検査項目専用内容を分離する。
- Completenessを4項目のMVPに限定する。
- 疾患とのRelationを今回は作らない。
- Publisher Coreを変更せず、Knowledge Platform側だけを拡張する。

### 採用しなかった設計

- AST用の大きな`test_item_v1.0`をそのままフェリチンへ必須適用する設計。
- Reference Rangeや単位を普遍的な単一値として保存する設計。
- 文字列一致だけで鉄欠乏性貧血とのRelationを自動作成する設計。
- Categoryごとに別Registry・別保存APIを作る設計。

### 判断理由

既存データの互換性を守りながら、今後の血清鉄、TIBC、UIBC、TSAT、CRP、HbA1c、AST、ALTを同じ最小契約へ追加できる。Category固有なのはSchema、Completeness、Claim Policy、Workbench表示だけで、Registry、版、Backup、Growth Engineは再利用できた。

## 9. CTOレビュー

今回の範囲では既存Platformを壊さず新Categoryを追加でき、Publisher CoreのファイルハッシュもPhase 5.10から不変である。198件の自動テスト、静的解析、型検査は成功した。Category追加の再現性は維持できている。

最大の手戻りリスクは、従来の`test_item`と新しい`laboratory_test_item`が並存している点である。これは互換性確保のため意図的に残した移行状態であり、永続的に二重運用してはいけない。AST・HbA1cを移行する前に、次のどちらを正式方針とするかADRで確定する必要がある。

1. `laboratory_test_item`を今後の正本とし、旧`test_item`を段階的に移行・読取専用化する。
2. 両者の責務を明確に分ける。例：検査項目の普遍的知識と、詳細な測定法プロファイルを別Categoryまたは別関連資産にする。

現時点では1を推奨する。ただしReference Range、単位、原理、装置の配置を決めずにAST・HbA1cを一括移行すると再設計になりやすいため、次Phaseは大量データ追加ではなく移行方針の小さな設計判断を優先する。

## 10. Technical Debt

- `test_item`と`laboratory_test_item`の移行方針が未確定。
- Claim DictionaryがPythonコード内にあり、大量Knowledge登録前に外部設定化が必要。
- フェリチンは`draft`で、プロダクトオーナー確認・医学監修・承認が未完了。
- Exam Metadataは未接続でExam Completeness 0%。
- Reference Range、単位、測定原理、装置、標準コードは意図的に未実装。
- Relationは未登録。Diseaseとの接続ルール確定後に追加する。
- 類似文章によるClaim統合候補には誤検出があり、人の判断が必要。
- テスト基盤に`httpx`移行予定の非推奨警告が1件残る。
