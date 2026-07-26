# Knowledge Relation Foundation Version 1.1

## 1. 目的

Knowledge Relationは、Knowledge本文を変更せず、登録済みKnowledge同士を意味付きで接続する独立資産です。Phase 5.2では未解決Relationの最小基盤を実装し、Phase 5.3では`specimen` Category登録後に同じRelationを正式Knowledgeへ解決できることを実証しました。Phase 5.4では未解決Relationの索引と保存イベントを追加し、全Knowledge再評価を廃止しました。

```text
staining_method Knowledge
        ↓ 明示された文字列だけを抽出
Relation Resolver
        ↓ Registryの正式名称・aliasと一致
Knowledge Relation Ledger
        ├── resolved：target_knowledge_idあり
        └── unresolved_relation：文字列は保持、IDは作らない
```

AI、類似度検索、Publisherはこの解決処理へ参加しません。対象Knowledgeが存在しない場合に仮のKnowledgeを作成することもありません。

## 2. Relation Contract

| 項目 | 役割 |
|---|---|
| `relation_id` | 同じ意味の接続で維持する内部ID |
| `source_knowledge_id` | Relation元のKnowledge |
| `target_knowledge_id` | Registryで完全一致した接続先。未解決時は`null` |
| `target_label` | Knowledge本文に明記されていた接続先の名称 |
| `relation_type` | 固定Vocabularyから選ぶ関係の意味 |
| `claim_id` | Relationを主張している元Knowledgeの根拠Claim |
| `resolution_status` | `resolved`または`unresolved_relation` |
| `status` | `draft`、レビュー中、承認済み、`deprecated` |
| `version` | Relation自体の版。接続先や根拠が変わったときに更新 |
| `context` | Knowledge本文へ属さない接続条件。修飾語と前処理を保持 |
| `created_at` / `updated_at` | 作成・更新日時 |

Relationの追加、更新、廃止は、Relation専用履歴へ操作者、理由、変更前後Versionとともに保存します。

## 3. Relation Vocabulary

Phase 5.2で実装したRelation Typeは次の4種類だけです。自由入力はSchemaで拒否します。

| Relation Type | 意味 | Gram染色での例 |
|---|---|---|
| `uses_specimen` | 検体・標本を使用する | 細菌を含む塗抹標本 |
| `uses_reagent` | 試薬を使用する | クリスタルバイオレット、ヨウ素液など |
| `targets_structure` | 構造を対象にする | 細菌細胞壁 |
| `related_method` | 関連する検査法・染色法 | 抗酸菌染色 |

Phase 5.12でDisease Categoryの実データ上の必要性を確認し、疾患専用の`has_high_test_item`、`has_low_test_item`、`diagnosed_by`、`caused_by`、`related_disease`、`affects_structure`、`has_pathophysiology`を追加しました。`detects`、`measures`、`produced_by`、`located_in`、`has_life_cycle_stage`は引き続き将来候補であり、対応Categoryと実データが揃うまで追加しません。

## 4. Resolver規則

1. `staining_method`の`applicable_specimens`、`reagents`、`target_structures`、`related_methods`だけを読む
2. Registryの`canonical_name`と`aliases`をUnicode正規化して完全一致させる
3. `uses_specimen`だけは、登録済みSpecimen名が元文字列の末尾に一意に存在する場合も解決する
4. 末尾より前の文字列はKnowledge aliasにせず、Relation Contextの`qualifiers`へ保存する
5. 一意に一致した場合だけ`target_knowledge_id`を設定する
6. 一致しない、複数候補で曖昧、または自分自身を指す場合は`unresolved_relation`にする
7. AI、一般的な部分一致、曖昧検索、医学的推測は行わない
8. 元の明示文字列を使って安定した`relation_id`を作る

このため、後から対象Knowledgeが正式登録されてもRelation IDは変わりません。再同期すると、同じRelationの接続先が埋まり、Relation Versionだけが上がります。

## 5. 永続保存

MVPでは既存の`knowledge_registry.sqlite3`内に、次の独立テーブルを追加しています。

- `knowledge_relations`
- `knowledge_relation_history`
- `knowledge_relation_resolution_index`（再構築可能な派生索引）
- `knowledge_relation_resolution_reports`（保存イベントの監査記録）

同じSQLiteファイルを使う理由は、Knowledge・Claim・Relationを一つの世代Backupで復元でき、外部キーで参照切れを防げるためです。Knowledge本文の`knowledge_records`、ID台帳の`knowledge_registry`・`claim_registry`とは別テーブルであり、Relationを追加してもKnowledge JSONは書き換えません。

アプリケーションは`KnowledgeRelationRepository`という共通接続口へ依存します。将来Database Providerへ移行するときは、SQLite Adapterだけを交換できます。

## 6. Gram染色の解決結果

Gram染色から7件のRelationを登録しました。

- `uses_specimen`：1件
- `uses_reagent`：4件
- `targets_structure`：1件
- `related_method`：1件

`specimen` Categoryとして塗抹標本（`knw_10000005`）を登録した結果、同じ7件は次の状態になりました。

- 解決済み：1件（Gram染色 `uses_specimen` 塗抹標本）
- 未解決：6件（試薬4件、対象構造1件、関連法1件）
- Relation Context：`細菌を含む`、`薄く均一に塗抹する。`
- Gram染色Knowledge Version：v1のまま
- 対象Relation Version：v1からv2へ更新

Context追加に伴うVersion 1.1移行では、既存Relation IDと履歴を維持しています。

## 7. WorkbenchとAPI

WorkbenchのRegistryでGram染色を開くと、「関連Knowledge」にRelation Type、Specimen名、Knowledge ID、解決状態、Context、根拠`claim_id`、Relation Versionが表示されます。閲覧のみで、手動編集は行いません。

- `GET /api/knowledge-relations/{knowledge_id}`：Knowledge別Relation一覧
- `GET /api/schema/knowledge-relation-1.0`：Version 1.0 JSON Schema
- `GET /api/schema/knowledge-relation-1.1`：Contextを含むVersion 1.1 JSON Schema
- `GET /api/relation-resolution-reports/{knowledge_id}`：対象Knowledge保存時の解決レポート

Gram染色を保存するとRelationを同期します。さらにSpecimenを正式登録すると、Resolution Indexから`uses_specimen`候補だけを取り出し、Knowledge本文を書き換えずRelationだけを更新します。ASTは対象外なのでRelation 0件のまま正常動作します。Network CompletenessはGram染色14.3%、Relation未形成のASTは0.0%です。

## 8. Publisherとの境界

Publisher Coreは変更していません。現在どおりKnowledge、Exam Metadata、Registryから組み立てたSource Bundleを受け取ります。将来Relationを教材構成に使う場合も、Knowledge本文を改変せず、Source Bundleへ承認済みRelationの読取専用Viewを追加する方針です。Phase 5.2ではその変更を先行実装しません。

## 9. 運用上の注意

- Relationが`resolved`でも、医学的に承認済みとは限りません
- `unresolved_relation`を減らすために、仮KnowledgeやAI補完を作らないでください
- Knowledgeを保存すると、その名称・Categoryに関係する未解決Relationだけを再評価します
- Vocabulary追加は実データで必要性を確認し、既存語との重複をレビューしてから行います
- Relation削除は物理削除せず`deprecated`と履歴で残します

## 10. 次の発展

次の推奨は`reagent` Categoryです。Gram染色に残る未解決6件のうち4件を同じ仕組みで解決でき、Relation Resolution率を1/7から5/7へ改善できます。新しいPublisher層やGraph Databaseは追加しません。
