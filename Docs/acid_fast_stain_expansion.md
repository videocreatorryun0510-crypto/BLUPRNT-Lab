# Phase 5.6 — Existing Category Expansion: Acid-Fast Stain

## 目的

既存の`staining_method_v1.0`へ抗酸菌染色（Ziehl-Neelsen染色）を追加し、SchemaやCategory Unionを変更せずにKnowledge Networkが成長することを確認する。

抗酸菌染色は`knw_10000010`、意味台帳は`acidfast.stain`を使用する。登録時の状態は`draft`であり、医学監修・承認済みを意味しない。

## 実装範囲

- Gram染色と同じ`staining_method_v1.0`で、定義、目的、対象構造、固定、原理、試薬、工程、判定、精度管理、誤差、限界、安全、出典を保持
- Workbenchから下書きを開き、登録、編集、再読込
- 安定した`knowledge_id`、`claim_key`、`claim_id`、Knowledge VersionをRegistryで管理
- Knowledge保存イベントで、Resolution Indexにある`related_method`候補だけを再評価
- Resolution ReportをSQLiteへ保存
- Gram染色本文を変更せず、既存Relationの接続先だけを更新

Knowledge Schema、Category Union、Publisher Coreは変更していない。

## Relation Resolution結果

| 指標 | 実装前 | 実装後 |
|---|---:|---:|
| Gram染色 Relation総数 | 7 | 7 |
| Resolved | 5 | 6 |
| Unresolved | 2 | 1 |
| Network Completeness | 71.4% | 85.7% |

抗酸菌染色の保存イベントでは、`staining_method` Categoryと正式名・別名に対応する索引候補1件だけを読み、1件を解決した。全Knowledge本文の走査は行っていない。

```text
Gram染色（knw_10000004）
├── uses_specimen ──→ 塗抹標本（knw_10000005）
├── uses_reagent ───→ クリスタルバイオレット（knw_10000006）
├── uses_reagent ───→ グラム染色用ヨウ素液（knw_10000007）
├── uses_reagent ───→ グラム染色用脱色液（knw_10000008）
├── uses_reagent ───→ グラム染色用サフラニン対比染色液（knw_10000009）
├── related_method ─→ 抗酸菌染色（knw_10000010）
└── targets_structure → 細菌細胞壁（未解決）
```

## Workbenchでの確認

1. 「抗酸菌染色を開く」を押す。
2. `Schema OK`、`staining_method_v1.0`、染色法Completeness 100%を確認する。
3. JSON本文と出典を確認し、「Registryへ保存」を押す。
4. Resolution Reportが「再評価1件・解決1件・未解決0件」であることを確認する。
5. RegistryでGram染色を開き、`related_method`の接続先が`knw_10000010`であることを確認する。
6. Gram染色のNetwork SummaryがResolved 6件、Unresolved 1件、85.7%であることを確認する。

Completeness 100%は必要欄と出典の対応が揃ったことを示し、医学的正しさの承認ではない。公開前にOwner Review、Medical Review、Approvalが必要である。

## 既存Categoryの再利用性

今回の追加は、新規Categoryで必要となるSchema、Completeness、Union、Relation Vocabulary、Publisher接続の実装を必要としなかった。再利用したものは次のとおり。

- Category Envelopeと`staining_method_v1.0`
- 染色法Completeness
- Registry、Claim Dictionary、Version、承認フロー
- Relation Contract、Resolution Index、Resolution Report
- Workbenchの共通JSON編集・保存・Relation表示

Knowledge固有の追加は、初期Knowledge JSON、意味が固定されたClaim Dictionary、Workbenchの選択導線、テストである。この構成により、同じCategory内の知識追加はCategory新設より小さい変更で繰り返せる。

## 医学情報の扱い

初期下書きはAmerican Society for MicrobiologyのAcid-Fast Stain ProtocolsとWorld Health Organizationの結核菌検査マニュアルを根拠として構造化した。国内の出題基準、標準作業書、試薬添付文書との照合は未完了である。特に固定条件、試薬組成、時間、加温、安全、精度管理は採用法と施設手順により確認する。

## 残る課題

- `targets_structure`の「細菌細胞壁」は正式Knowledgeへ未解決
- 抗酸菌染色自身から出る検体・試薬・対象構造Relationは、対応Knowledge未登録のものを推測せず未解決として保持
- 国家試験CSV実績、国内出典、医学監修、承認は未実施
- 同名異義語や別表記の追加時に、人が確認できるAlias Reviewが必要
- 複数プロセス同時保存、イベントQueue、再試行は未実装

