# Knowledge JSON Version 0.3設計書

## 1. 目的

Version 0.3は、BLUPRNT Labで10年以上利用できる医療知識の正本を目指す次期データ契約です。

Knowledge WorkbenchはVersion 0.3へ移行済みです。OpenAIは医学的事実だけを生成し、Workbenchが安定IDとシステム管理領域を追加してからVersion 0.3 Schemaで検証します。各Publisherはまだ接続していません。

`examples/`内のASTは構造検証用であり、承認済み医学知識ではありません。正本として利用する前に、出典追加と別管理の医学レビュー・承認が必要です。

## 2. 保存するもの・保存しないもの

保存するものは次の4種類です。

1. 医学的事実
2. 臨床検査技師国家試験との対応
3. 事実を支える出典
4. Publisherが優先利用する事実ID

次の成果物や表現は保存しません。

- 語呂合わせ、覚え方
- 読みやすく編集した記事本文
- PDFレイアウトや完成原稿
- note向けの表現
- 動画台本、ナレーション、演出
- 国家試験問題、選択肢、解説文
- AI生成時のプロンプトや回答履歴

これらは将来、各Publisherが承認済みKnowledge JSONを入力として生成します。

## 3. 全体構造

```text
KnowledgeRecord 0.3
├── schema_version / knowledge_id / content_revision
├── term                       用語の正式名・英語名・別名
├── classification             カテゴリと国家試験科目
├── core_facts                 全カテゴリ共通の医学的事実
├── category_content           カテゴリ専用の医学的事実
├── exam_metadata              国家試験CSV解析結果の保存先
├── evidence                   出典と事実の対応
└── publish_targets            Publisherごとの利用優先ID
```

## 4. 医学的事実とclaim_id

医学的事実は`FactClaim`として保存します。

```json
{
  "claim_id": "clm_ast_distribution",
  "statement": "ASTは肝臓、心筋、骨格筋、赤血球などに分布する。"
}
```

`claim_id`は、出典、国家試験メタデータ、Publisher指定から同じ事実を参照するための安定したIDです。

- 文章の表記だけを直し、医学的意味が変わらない場合は同じIDを維持する
- 医学的意味を変更した場合は新しいIDを発行する
- 1つのclaimには、原則として1つの検証可能な事実だけを入れる
- 同じKnowledge JSON内でIDを重複させない
- 存在しないclaim IDへの参照はSchema検証で拒否する

## 5. 検査項目テンプレート

検査項目は`test_item_v0.3`を使います。

- 検査目的
- 検体
- 測定方法
- 測定原理
- 基準範囲
- 高値・低値との関連
- 他検査との組み合わせ
- 解釈時の注意点

### 5.1 高値・低値

高値と低値のそれぞれで、次を別々に保持します。

- `pathophysiologic_states`：肝細胞障害、筋障害などの病態
- `representative_diseases`：急性肝炎、横紋筋融解症などの疾患名
- `interpretive_notes`：低値の意義が限定的などの医学的注意

疾患には将来の`disease_knowledge_id`を設定できます。疾患JSONがまだ存在しない段階では`null`を許可します。

### 5.2 測定方法と測定原理

測定方法と測定原理は別のclaimとして保持します。1つの検査に複数の測定方法・原理があることを前提に、どの原理がどの方法に対応するかをclaim IDで結びます。

## 6. 国家試験メタデータ

`exam_metadata`はすべてのカテゴリに共通です。今回は未解析状態として`null`または空配列を保存できます。

| 項目 | 用途 |
|---|---|
| `analysis_batch_id` | どのCSV解析結果から作られたか |
| `importance` | 重要度、任意の生スコア、算出方法 |
| `first_appearance_session` | 初出回 |
| `last_appearance_session` | 最終出題回 |
| `appearance_frequency` | 出題数、解析問題数、頻度、算出方法 |
| `related_questions` | 関連過去問ID、回、問題番号、問われたclaim |
| `comparison_targets` | 比較されやすい知識ID |
| `related_knowledge` | 関連する知識ID |
| `priority_claim_ids` | 国家試験で優先する医学的事実 |
| `keywords` | CSV・過去問検索に使う語句 |

頻度や重要度には`analysis_batch_id`を持たせられるため、将来CSVの集計方法が変わっても由来を追跡できます。

## 7. 出典

`evidence`は次の情報を保持できます。

- 資料名
- 発行団体
- 版
- 発行年
- URL
- DOI
- PMID
- 参照日
- 章
- ページ
- 支えるclaim ID
- 主根拠または補助根拠
- 情報取得優先順位

出典は完成文章ではなく、医学的事実のclaimへ直接結びます。1つの出典が複数のclaimを支えることも、1つのclaimを複数の出典が支えることもできます。

AIは出典として扱いません。AI実行履歴は将来、Knowledge JSONとは別の制作・監査記録で管理します。

## 8. Publisher向け利用情報

`publish_targets`は次の4つを共通構造で保持します。

- `pdf`
- `note`
- `training_video`
- `national_exam`

各項目に保存できるのは、優先する`claim_id`と国家試験メタデータ項目だけです。本文、台本、問題文、レイアウトは保存できません。

## 9. Version 0.2からの主な変更

| Version 0.2 | Version 0.3 |
|---|---|
| 3秒サマリーを保持 | 正本から削除しPublisherで生成 |
| 図解候補を保持 | 正本から削除しPublisherで生成 |
| 重要要点を文章で重複保持 | 重要なclaim IDを参照 |
| 高値・低値を同じ条件リストで保持 | 病態と代表疾患を分離 |
| 出典情報が最小限 | 書誌情報と対応claimを保持 |
| 試験メタデータの保存先なし | 全カテゴリ共通の保存先を追加 |
| Publisher情報なし | 優先claim IDだけを追加 |
| 事実に安定IDがない | すべての出典対象事実にclaim ID |

Version 0.3では、`quick_summary`、`visual_hooks`、`exam_essentials`、AI警告、AI Provider情報、医学レビュー状態を正本データから外します。制作履歴、AI履歴、レビュー・承認状態は、将来別のワークフロー管理層で扱います。

## 10. カテゴリ拡張

`core_facts`、`exam_metadata`、`evidence`、`publish_targets`は、検査項目、疾患、微生物、寄生虫、染色法、病理、輸血、免疫などで共通です。

現在、専用構造を持つカテゴリは検査項目だけです。他カテゴリは`generic_facts_v0.3`を使います。疾患などの専用構造が必要になった場合も、Version 0.3を無断で拡張せず、用途と移行方法を別の設計レビューで決定します。

## 11. 版管理と移行方針

- Version 0.2と0.3は別の契約として共存させる
- Knowledge Workbenchの新規生成はVersion 0.3を使用する
- Version 0.2は旧データの読取互換性と移行比較のため残す
- データ変換は上書きではなく、0.2から0.3への移行処理として行う
- 変換前の0.2データを残し、移行結果を比較できるようにする

## 12. 今回実装していないもの

- CSVの取込・集計
- 出典のWeb検索・自動取得
- 医学レビュー・承認ワークフロー
- PDF、note、TrainingVideo、NationalExamの生成
- Version 0.2データの自動移行

## 12.1 Prototypeでの生成境界

OpenAIへ渡す構造には`claim_id`、`exam_metadata`、`evidence`、`publish_targets`を含めません。OpenAI回答を受け取った後、Workbenchが次の順序で正本形式へ変換します。

1. 医学的事実と分類を受け取る
2. 正式名とカテゴリから`knowledge_id`を付与する
3. 各事実へ`claim_id`を付与する
4. 空の国家試験メタデータ、出典、Publisher優先指定を追加する
5. Knowledge JSON Version 0.3 Schemaで検証する

AIがシステム管理項目や出典を作れない境界を維持します。

## 13. 10年運用に向けた設計上の注意

現時点の0.3は、長期運用の中核となる「事実ID」「出典対応」「版の共存」を備えています。ただし、「このまま何も追加せず10年間運用できる」という段階ではありません。

| 手戻り候補 | 理由 | 改善案 |
|---|---|---|
| ID発行規則 | 人ごとにIDの付け方が変わると重複・再利用が起きる | `knowledge_id`と`claim_id`の発行サービス・変更規則を正式版前に決める |
| 用語と単位の表記揺れ | 同じ検体・疾患・単位を別名で保存すると検索・比較できない | 用語、単位、検体、測定法の管理語彙と外部コード対応を作る |
| 承認状態 | 正本JSON自身には制作・承認履歴を混ぜていない | 承認、差戻し、廃止、監査を管理する別のワークフロー台帳を作る |
| 出典改訂 | ガイドライン改訂時に古いclaimが残る可能性がある | 出典IDから影響するclaimを逆引きし、再レビュー対象を出す |
| CSV再集計 | 試験回追加や集計方法変更で結果が変わる | `analysis_batch_id`ごとに結果を保存し、上書きせず更新履歴を残す |
| Publisher優先度 | 対象読者ごとに優先度が頻繁に変わる可能性がある | 変動が大きくなったら`publish_targets`をclaim参照型の別プロファイルへ分離する |
| Schema廃止 | 古いクライアントが突然読めなくなる | 版ごとのサポート期間と移行ツール提供方針を決める |

特にPublisher優先度は、医学的事実そのものではありません。今回は要件どおり本文を持たない最小のclaim参照としてKnowledge JSON内に置きました。将来、媒体や対象学年ごとに多数の設定が必要になった場合は、医学知識を更新せずに変更できる別の`Knowledge Use Profile`へ分離するのが安全です。
