# Phase 5.4 — Knowledge Growth Engine MVP

## 目的

Knowledgeが保存されたとき、関係する未解決Relationだけを再評価し、Knowledge Networkを差分更新します。Knowledge JSON本文とPublisher Coreは変更しません。

```text
Knowledge保存イベント
        ↓
canonical_name / aliases / Category
        ↓
Relation Resolution Index
        ↓ 該当する未解決Relationだけ
決定的なRelation照合
        ↓
Relation台帳更新 + Resolution Report
        ↓
Network Summary
```

## Resolution Index

`knowledge_relation_resolution_index`はRelation台帳から再生成できる派生索引です。次のキーを持ちます。

| キー | 役割 |
|---|---|
| `target_key` | Unicode正規化した対象名の完全一致検索 |
| `target_reverse_key` | 末尾名を先頭検索へ変換する逆順キー |
| `relation_type` | `uses_specimen`などRelationの意味を限定 |
| `target_category` | 接続先Categoryを限定 |
| `resolution_status` | 未解決Relationだけを選択 |
| `relation_status` | deprecatedを除外 |

「細菌を含む塗抹標本」は逆順キーで「塗抹標本」に一致させます。これにより先頭ワイルドカード検索やKnowledge本文の全件読込を行いません。索引はRelation追加・更新・廃止と同じトランザクションで同期し、既存SQLiteは起動時Migrationで再構築します。

## Knowledge保存イベント

`KnowledgeRelationService.resolve_for_target`は、保存されたKnowledgeのCategory、正式名、aliasを索引へ渡します。索引から返った未解決Relationだけを決定的に確認し、一致したRelationの`target_knowledge_id`、Version、Context、履歴だけを更新します。

- AIや曖昧検索を使わない
- 全Knowledgeの`record_json`を順番に読まない
- Knowledge本文を更新しない
- 該当しないRelationは更新しない
- 解決済みRelationを再評価しない

## Resolution Report

処理ごとに`knowledge_relation_resolution_reports`へ次を永続保存します。

- 対象`knowledge_id`とCategory
- 再評価件数
- 解決件数
- 未解決のままの件数
- 評価・解決・未解決Relation ID
- 日時、操作者、理由

候補が0件でもReportを残します。これにより「保存イベントは動いたが、対象Relationがなかった」ことと「処理が動かなかった」ことを区別できます。

## Network Completeness

Knowledgeから出る有効なRelationについて、次で計算します。

```text
Network Completeness = Resolved ÷ Relation総数 × 100
```

Phase 5.4時点のGram染色は`1 ÷ 7 = 14.3%`です。Phase 5.5で4種類のReagentを登録すると`5 ÷ 7 = 71.4%`、Phase 5.6で抗酸菌染色を登録すると`6 ÷ 7 = 85.7%`になります。Relationが0件の場合は、Networkが未形成であることを明確にするため`0.0%`とします。この数値は医学的正確性やKnowledge Completenessではなく、RelationのID解決率です。

Phase 5.5では`reagent` Categoryでも同じ索引処理を変更せず再利用できました。4件のReagent保存イベントは各1件だけを再評価し、全Knowledgeの`record_json`を読みませんでした。これによりGrowth EngineがSpecimen専用実装ではないことを確認しました。

Phase 5.6では既存`staining_method` CategoryへKnowledgeを1件追加するだけで、Gram染色の未解決`related_method` 1件を同じ索引処理で解決しました。Schema、Category Union、Relation Vocabulary、Growth Engineを変更せず、Knowledge追加がNetworkの価値向上へ直結することを確認しました。

## WorkbenchとAPI

- RegistryでKnowledgeを開くと、Relation総数、解決済み、未解決、Network Completeness、履歴を表示
- Knowledge保存後に今回のResolution Reportを表示
- `GET /api/knowledge-relations/{knowledge_id}`：RelationとNetwork Summary
- `GET /api/relation-resolution-reports/{knowledge_id}`：Knowledge保存イベント別Report

## 長期運用上の境界

IndexとReportは`KnowledgeRelationRepository`の契約を通して利用します。SQLite固有SQLはAdapter内に閉じ込めているため、将来Database Providerへ交換できます。Indexは正本ではなくRelation台帳から再構築可能、Resolution Reportは監査資産として永続保存します。Publisher Coreはこれらの書込処理へ依存しません。

## MVPの制約

- 単一SQLiteプロセスを前提とし、並行イベントのQueue・再試行は未実装
- alias追加だけを独立イベントとして再解決する機能は未実装
- 新しいRelation元を登録した時、既存接続先との末尾照合を行うTarget Knowledge Indexは未実装
- Network Completenessは承認状態やRelation重要度を重み付けしない
- Index整合性の運用監視と再構築コマンドは未実装
