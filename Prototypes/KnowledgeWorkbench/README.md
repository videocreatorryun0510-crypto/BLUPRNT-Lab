# Knowledge Workbench — Phase 5.22

医療用語を1つ入力し、OpenAIの医学的事実を**Knowledge JSON Version 1.0**へ、国家試験情報を独立した**Exam Metadata Version 1.0**へ変換・検証・表示する画面です。正式Category `staining_method`、`specimen`、`reagent`、`biological_structure`、`disease`、`laboratory_test_item`を登録・編集できます。AI生成はASTとHbA1c、正式Category編集はGram染色、抗酸菌染色、塗抹標本、Gram染色用試薬、細菌細胞壁、鉄欠乏性貧血、フェリチンが対象です。PDFは生成しません。

Phase 5.15ではPresentation Contract Version 1.0を追加しました。Source Bundle生成後、成果物の種類、対象者、使用Claim、媒体条件、安全条件だけを持つPresentation Requestを生成できます。Previewはレビュー途中でも作れますが、Externalは`approved`だけが許可されます。Gemini APIやPDF等の描画は行いません。

Phase 5.16ではProvider非依存のPresentation Engine Adapter ContractとDummy Adapterを追加しました。Presentation Request生成後に、Approval Gate、Request Fingerprint、Claim・図解・出典件数、Provider Version、Presentation Resultを外部通信なしで確認できます。

Phase 5.17では、Presentation Requestの参照IDを承認済み正本へ解決するProvider Payload Resolverを追加しました。未承認Claim、Stale、Secret、ローカルパス、個人情報候補をPayload生成前に停止し、Dummy Responseでは使用Claim・図解・出典IDとFingerprintを追跡できます。Provider Payload Previewも安全側の初期Policyとして`approved`だけが対象です。

Phase 5.18では、Provider非依存のPresentation Prompt BuilderとGemini Sandbox Adapterを追加しました。Prompt PreviewにはProvider固有情報を含めず、Gemini固有の変換・認証・通信・Response MappingはAdapter内部だけで処理します。未承認Knowledge、Stale、Fingerprint不一致、APIキー未設定では外部通信しません。

Phase 5.18.1では、実Knowledgeを使わないGemini実API受入テストを追加しました。画面上部の専用欄で「送信前確認を作成」を押し、隔離Test Fixture、承認、Egress、Secret、Stale、Fingerprint、件数、送信量、Token、Retry、Timeoutを確認します。すべてOKの場合だけ「Test FixtureをGeminiへ1回送信」を押せます。ページ読込やKnowledge保存では自動送信されません。

Phase 5.22では、AIを使わず人がKnowledgeを素早く作るKnowledge Wizardを追加しました。Category、Title、Alias、Difficulty、Exam Importanceの5項目から、既存Knowledge Contract 1.0に適合する空のSkeletonを作ります。ClaimとReferenceを追加・編集し、JSONまたはMarkdownへ出力できます。未完成データは正式Registryから分離したAuthoring Draftとして保存され、Approval、Artifact、Publisherは変更しません。

## できること

1. 医療用語を1つ入力する
2. OpenAIへ構造化された回答を依頼する
3. OpenAIの医学的事実をVersion 0.3で受け取り、Knowledge JSON 1.0へマッピングする
4. Claim Dictionaryを参照し、既存の`knowledge_id`、`claim_key`、`claim_id`を再利用する
5. JSON Schema Draft 2020-12で形式とID参照を検証する
6. 医学知識だけのKnowledge Completenessを計算する
7. ダミー出題履歴をExam Metadataへ結び、Exam Completenessを計算する
8. 重要claim、出題履歴、2種類のスコア、改善候補、JSON全文を画面で確認する
9. 設定・通信・AI回答・Schemaのエラーを安全な文章で表示する
10. CSV列を版付きMappingで共通形式へ変換する
11. GOTなどの別名を`knowledge_id`へ、出題内容を`claim_id`へ関連付ける
12. 出題履歴からimportance_scoreを再計算する
13. `ExamImages/`の画像を命名規則で関連付け、画像不足はWarningにする
14. CSVをRegistryへ反映せずに検証・Previewし、確認後だけImportする
15. Knowledge Registry、Claim Dictionary、版、状態、承認情報、変更履歴を画面表示する
16. 未承認Claimをまとめて次の承認段階へ進める
17. 同義と判断したClaimを、統合先IDを変えずに統合する
18. 統合元をdeprecatedにし、旧IDから統合先へのRedirectと履歴を残す
19. SQLite Registryを世代名付きでBackupし、選んだ世代からRestoreする
20. RegistryのID・Key重複、別名循環、孤立Claim、履歴欠落、統合後の参照切れなどを検証する
21. Gram染色の正式下書きを開き、Schemaと染色法Completenessを確認する
22. Gram染色をRegistryへ保存し、再起動後もKnowledge JSON本文を再読込・編集する
23. 固定法、試薬、工程、判定、精度管理、限界、出典を染色法専用構造で管理する
24. Gram染色の検体、試薬、対象構造、関連法をKnowledge本文とは別のRelation台帳へ保存する
25. 未登録KnowledgeをAIで補完せず`unresolved_relation`として表示する
26. 同じRelationを再保存しても安定した`relation_id`とVersionを維持する
27. 塗抹標本を`specimen_v1.0`の正式Knowledgeとして登録・編集する
28. 定義、概要、用途、採取・作製、保存、注意、出典をSpecimen Completenessで評価する
29. Specimen登録後にGram染色本文を変えず、`uses_specimen` Relationだけを再解決する
30. 「細菌を含む」「薄く均一に塗抹する」をRelation Contextとして表示する
31. 未解決Relationを対象名、Relation Type、Categoryから索引検索する
32. Knowledge保存時に索引候補だけを再評価する
33. 再評価・解決・未解決件数をResolution Reportへ保存する
34. Knowledge別Network Completenessを画面表示する
35. 4種類のGram染色用試薬を`reagent_v1.0`の正式Knowledgeとして登録・編集する
36. 定義、用途、使用対象、使用工程、注意、保管、出典をReagent Completenessで評価する
37. Reagent保存時に該当する未解決`uses_reagent`だけを索引から再評価する
38. Gram染色本文を変えず、4件のRelationを安定Knowledge IDへ解決する
39. 抗酸菌染色を既存`staining_method_v1.0`の正式Knowledgeとして登録・編集する
40. 抗酸菌染色保存時に未解決`related_method` 1件だけを索引から再評価する
41. Gram染色本文を変えず、Network Completenessを85.7%へ更新する
42. 細菌細胞壁を`biological_structure_v1.0`の正式Knowledgeとして登録・編集する
43. 定義、主な機能、出典をBiological Structure Completenessで評価する
44. 細菌細胞壁保存時に未解決`targets_structure` 1件だけを索引から再評価する
45. Gram染色本文を変えず、Relation 7/7、Network Completeness 100.0%を表示する
46. 鉄欠乏性貧血を`disease_v1.0`の正式Knowledgeとして登録・編集する
47. 定義、病態、主な検査所見、出典をDisease Completenessで評価する
48. 疾患の医学的事実17件を生成順に依存しないClaim IDとKeyで保存する
49. 接続先がないRelationを無理に作らず、Growth Engineの再評価0件を記録する
50. フェリチンを`laboratory_test_item_v1.0`の正式Knowledgeとして登録・編集する
51. 定義、臨床的意義、測定対象、出典をLaboratory Test Item Completenessで評価する
52. 検査項目の医学的事実11件を生成順に依存しないClaim IDとKeyで保存する
53. 疾患とのRelationを作らず、Growth Engineの再評価0件を記録する
54. Disease Relation Vocabulary 7語の意味・方向・利用Category・例を表示する
55. Vocabulary閲覧ではRegistry・Relation・Resolution Reportを書き換えない
56. フェリチンと鉄欠乏性貧血の保存済み正本からSource Bundle JSONを生成する
57. Source BundleのClaims、重要Claim、図解要求、出典、版、承認状態を確認する
58. Knowledge画面でApproval StateとReview Versionを確認する
59. Source Bundle生成時に公開可否・外部AI送信可否と停止理由を確認する
60. Gate判定をProvider非依存のPublisher監査ログへ保存する
61. Source Bundleから`presentation_document`／`structured_json`のPresentation Requestを生成する
62. PreviewとExternalを選び、未承認Externalを停止する
63. Knowledge Version、Fingerprint、Approval State、Review Versionの不一致を検出する
64. Claim、Key Message、Diagram Request、Referenceの追跡IDを確認する
65. Presentation Requestの生成条件、停止理由、保存先、JSON全文、監査ログを確認する
66. Dummy AdapterでPreviewまたは承認済みExternalの実行フローを検証する
67. Adapter、Provider Version、Request Fingerprint、Claim・図解・出典件数を確認する
68. Presentation Result Validation、Result JSON、監査ログを確認する
69. Dummy実行で外部AIが呼ばれず、KnowledgeとRegistryが変更されないことを確認する
70. 承認済みClaimだけを無変更の`exact_text`としてProvider Payloadへ解決する
71. 未承認・Stale・Secret・ローカル絶対パスをData Egress Policyで停止する
72. Payload FingerprintとClaim・Diagram・Reference Trace Mapを確認する
73. Traceable Dummy Responseで使用IDとFingerprint一致を検証する
74. Payload・Response監査ログに医学本文が保存されないことを確認する
75. Provider PayloadからGemini等に依存しないPresentation Promptを生成する
76. Prompt内で承認済みClaim本文が言い換えられていないことを確認する
77. Gemini Sandboxで認証・Timeout・Retry・構造化Response Mappingを確認する
78. Token・任意Cost・Duration・Fingerprint・停止理由を本文なし監査で確認する
79. 実Registryとは別の一時SQLiteで、2 Claimの承認済みGemini受入Fixtureを作る
80. 外部通信前にFixture、承認、Egress、Secret、Stale、Fingerprint、送信量を確認する
81. 明示操作1回だけでGemini実APIを呼び、構造化Responseを厳格に検証する
82. 実Registry不変、Claim・Reference追跡、Token・Duration・Audit保存を確認する
83. 5項目のKnowledge Wizardから全7 Categoryの空Skeletonを作る
84. Claimを安定ID付きで追加・編集・削除・並び替えする
85. Evidence Level、URL、書誌情報、ページ、DOI、PMIDとClaim対応を保存する
86. Schema、作成時Completeness、必須項目、Claim数、Reference整合性を保存前に確認する
87. 下書きをJSON・Markdownへ出力し、JSONを新しい下書きとして取り込む
88. 未完成下書きの保存で正式Registry・Approval・Publisherが変わらないことを保証する

画面へ表示する医学知識はAIによる医学監修前の下書きです。Exam Metadataの出題回・年度・問題番号は画面確認用ダミーであり、実際の出題実績ではありません。どちらの完全性スコアも情報の揃い具合であり、正確性や承認の点数ではありません。

Knowledge JSON内に残る旧`exam_metadata`欄はVersion 0.3互換用です。画面と今後のPublisherは、API直下の独立した`exam_metadata`を使用します。

## はじめて使うとき

ターミナルでリポジトリの一番上へ移動し、次を実行します。

```bash
./Prototypes/KnowledgeWorkbench/setup.sh
```

次に `.env.example` を `.env` という名前でコピーし、OpenAIのAPIキーを設定します。

```bash
cp Prototypes/KnowledgeWorkbench/.env.example Prototypes/KnowledgeWorkbench/.env
```

AIでKnowledgeを生成する場合は`.env`の`OPENAI_API_KEY=`へOpenAI APIキーを入力します。承認済みKnowledgeをGemini Sandboxへ送信する場合だけ、`GEMINI_API_KEY=`へGemini APIキーを入力します。このファイルはGitの管理対象外で、共有しません。

起動します。

```bash
./Prototypes/KnowledgeWorkbench/start.sh
```

ブラウザで `http://127.0.0.1:8000` を開きます。終了するときはターミナルで `Control + C` を押します。

## Knowledge Wizardで新しい下書きを作る

1. 「Knowledge Wizard」でCategory、Title、Difficulty、Exam Importanceを選びます。Aliasは任意です。
2. 「Skeletonを作成」を押します。Claim、Reference、Relationが空で、Reviewが`draft`の下書きが保存されます。
3. 「Claim Authoring」で、確認可能な医学的事実を1件ずつ追加します。文章の編集、順番変更、削除ができます。
4. 「Reference Authoring」で資料名、Evidence Level、URL、書誌情報、ページ、DOIなどを入力し、その資料が支えるClaimを選びます。
5. 「保存前Validation」で形式、入力数、ReferenceとClaimの対応を確認します。これは医学的正確性の判定や医学監修ではありません。
6. 続きは「保存済み下書き」から開きます。JSON Exportは再取込用、Markdown Exportは人が読みやすい確認・共有用です。

下書きは`data/authoring_drafts/`へ1件ずつ保存されます。このフォルダはGit管理対象外です。正式Registryへの登録はPhase 5.22の対象外であり、誤って未完成Knowledgeが承認経路へ入ることはありません。詳しい責務と運用は[Knowledge Authoring Workflow](../../Docs/knowledge_authoring_workflow.md)を参照してください。

## 国家試験CSVをPreviewして取り込む

画面の「国家試験CSVを安全に取り込む」で、まず「サンプルをPreview」を押します。AST・HbA1c各2件、動作確認用画像2件が変換され、Import Validation、ID Mapping、重要度、画像件数が表示されます。この時点ではRegistryを変更しません。内容に問題がない場合だけ「Preview内容をImport」を押します。この操作はOpenAI APIを使用しません。

自分のCSVを試す場合は「CSVファイル」でファイルを選び、「選択したCSVをPreview」を押します。列名の対応は`imports/mappings/exam_csv_v1.json`で管理します。列名が変わった場合はプログラムではなく、このMappingへ別名を追加します。Preview後にRegistryが別操作で変更された場合は、古いPreviewをImportできないため、もう一度Previewします。

画像問題は`ExamImages/`へ`73-AM-06.png`のような名前で保存します。画像が見つからなくてもImportは止まらず、Warningになります。現在は`.png`、`.jpg`、`.jpeg`、`.webp`、`.svg`を検索します。同梱のSVGは医学画像ではなく、関連付け確認用です。

毎年の更新は、次の順で行う想定です。

1. 新しい回を含むCSVを用意する
2. 列名が変わった場合だけMappingへ別名を追加する
3. 画像問題のファイルを`ExamImages/`へ置く
4. WorkbenchでCSVを選び、Previewする
5. 新規・更新Knowledge、Unknown用語、Mapping不能、画像不足、Claim未対応を確認する
6. Errorがなく、内容に問題がなければImportする
7. Import後のExam MetadataとRegistry履歴を確認する

Import済みExam Metadata全体の永続保存と承認はまだ未実装です。Workbenchを再起動すると前回Import結果は消えるため、現段階では取込基盤の動作確認用として使用します。RegistryのID、統合、承認、履歴はSQLiteへ永続保存されます。

Import結果全体の正式保存は未実装ですが、Knowledge RegistryのID台帳と変更履歴は再起動後も保持されます。そのため、CSVを再Importしても同じ`claim_key`は同じ`claim_id`へ関連付けられます。

## Gram染色・抗酸菌染色・塗抹標本・試薬・細菌細胞壁・鉄欠乏性貧血・フェリチンを正式Knowledgeとして登録する

1. 「Gram染色を開く」を押します。この時点ではRegistryを書き換えません。
2. 染色法CompletenessとJSONを確認します。
3. 操作者と変更理由を入力します。
4. 「Registryへ保存」を押します。
5. Schema OK、Completeness、Knowledge Version、Claim Dictionaryを確認します。
6. 修正時は保存済みJSONを編集し、再保存します。医学的事実が変わるとKnowledge Versionが上がり、同じ意味の`claim_key`と`claim_id`は維持されます。
7. 内容確認後、既存の承認画面でClaimとKnowledgeを`owner_review → medical_review → approved`の順に進めます。
8. 「塗抹標本を開く」を押し、Specimen JSONとCompletenessを確認して保存します。
9. RegistryでGram染色を開き、「関連Knowledge」を確認します。
10. 塗抹標本、`knw_10000005`、`resolved`、Context、Relation Versionを確認します。
11. 試薬選択欄から4種類を1つずつ開き、JSONとReagent Completenessを確認して保存します。
12. 各保存後のResolution Reportが「再評価1件・解決1件・未解決0件」であることを確認します。
13. RegistryでGram染色を再度開き、Resolved 5件、Unresolved 2件、Network Completeness 71.4%を確認します。
14. 「抗酸菌染色を開く」を押し、同じ染色法Schema、Completeness、JSON、出典を確認して保存します。
15. Resolution Reportが「再評価1件・解決1件・未解決0件」であることを確認します。
16. Gram染色を再度開き、Resolved 6件、Unresolved 1件、Network Completeness 85.7%を確認します。
17. 「細菌細胞壁を開く」を押し、Biological Structure JSONとCompletenessを確認して保存します。
18. Resolution Reportが「再評価1件・解決1件・未解決0件」であることを確認します。
19. Gram染色を再度開き、Resolved 7件、Unresolved 0件、Network Completeness 100.0%を確認します。
20. 「鉄欠乏性貧血を開く」を押し、Disease JSONとCompleteness 100%を確認します。
21. Registryへ保存後、Knowledge ID `knw_10000012`、17 Claim、Version 1、Relation 0件を確認します。
22. 「フェリチンを開く」を押し、Laboratory Test Item JSONとCompleteness 100%を確認します。
23. Registryへ保存後、Knowledge ID `knw_10000013`、11 Claim、Version 1、Relation 0件を確認します。

Completeness 100%は「必要項目と出典欄が揃っている」という意味で、医学的に承認済みという意味ではありません。公開にはClaimとKnowledgeの承認が必要です。

## Knowledge Registryを確認する

医療用語を生成するか、「サンプルをPreview」を押すと、画面下部にKnowledge Registryが表示されます。Registry選択欄からASTまたはHbA1cを直接開くこともできます。

- **Knowledge Version**：ASTという知識全体の医学的な版
- **Claim Version**：個々の医学的事実の版
- **claim_key**：`ast.ifcc`のように、医学的な意味で固定される名前
- **claim_id**：システム内部で使う不透明なID
- **status**：`draft`、`owner_review`、`medical_review`、`approved`、`deprecated`
- **history**：追加、更新、削除、統合、deprecated、状態変更の記録
- **aliases**：GOTとASTのような別名
- **merge redirect**：統合元の旧IDから、維持された統合先IDへの案内

台帳は既定で`data/knowledge_registry.sqlite3`へ保存されます。このファイルにはAPIキーは入りません。画面の「Registry Backup / Restore」から、`registry_20260716_120000.db`のような世代名で安全にBackupできます。Restore前には現在状態の安全Backupも自動作成します。保存場所を変更する場合は`.env`の`KNOWLEDGE_REGISTRY_PATH`、Backup先は`KNOWLEDGE_REGISTRY_BACKUP_DIR`へ絶対パスを設定します。

重要なのは、`claim001`のような生成順ではなく、`ast.measurement.340nm`のような意味で対応を決めることです。AIが昨日と今日で項目を並べ替えても、同じ医学的事実は同じKeyとIDへ戻ります。

AIが1回の回答内で同じ意味を重複して書いた場合は、情報量が多い方を順番に依存しない規則で1件へ整理してからRegistryへ保存します。既存Dictionaryで意味を確定できない文章は、誤って別の事実と統合しないよう新しい下書きClaimとして残します。

Workbenchでは、機械的な文章類似度による「同じ意味の可能性がある候補」だけを表示します。最終判断は人が行い、統合先Claimを1件、統合元を1件以上選びます。統合先`claim_id`は作り直さず、統合元はdeprecatedにしてRedirectを保存するため、古いCSV参照を追跡できます。AIによる自動統合は行いません。

承認は`draft → owner_review → medical_review → approved → deprecated`の順です。Workbenchで操作者名とコメントを入力してから状態を進めると、日時・操作者・コメントが履歴へ保存されます。順番を飛ばす変更は拒否されます。

## APIキーなしで2テーマを確認する

画面・JSON・検証処理だけを固定データで確認できます。このモードはAIへ接続しません。

```bash
KNOWLEDGE_PROVIDER=fixture ./Prototypes/KnowledgeWorkbench/start.sh
```

Version 1.0画面で確認できるテーマ：`AST`、`HbA1c`

正式Category編集と自動テストで確認するテーマ：`Gram染色`、`抗酸菌染色`、`塗抹標本`、4種類のGram染色用試薬、`細菌細胞壁`、`鉄欠乏性貧血`、`フェリチン`

Version 0.3の5テーマ用fixtureと検証テストは移行確認のため残しています。微生物・寄生虫はVersion 1.0の正式Categoryとしてはまだ画面へ出せません。

固定データも医学監修前であり、医学的な正解データではなく動作確認用です。

## 自動テスト

```bash
.venv/bin/pytest Prototypes/KnowledgeWorkbench/tests
```

テストはOpenAIを呼ばず、API料金も発生しません。

## 設計上の境界

```text
画面
  ↓
GenerateKnowledge（AI会社を知らない生成手順）
  ↓
KnowledgeProvider（共通の接続口）
  ├── OpenAIKnowledgeProvider  ← 今回実装
  ├── GeminiKnowledgeProvider  ← 将来追加
  └── ClaudeKnowledgeProvider  ← 将来追加
  ↓
knowledge-contracts（共通のKnowledge JSON 1.0、Schema、完全性評価）
  ↑ knowledge_id / claim_id
KnowledgeRegistry（安定ID・意味キー・版・承認・履歴）
  └── SQLiteKnowledgeRegistry  ← MVPの永続保存
      ├── Claim Merge Redirect
      └── Generation Backup / Restore
KnowledgeRelationResolver（登録済みKnowledgeだけを決定的に解決）
  ↓
KnowledgeRelationService（Knowledge保存イベントから索引候補だけを再評価）
  ↓
KnowledgeRelationRepository（Knowledge本文とは別の版付きRelation台帳）
  └── SQLiteKnowledgeRelationRepository
      ├── Relation Resolution Index
      └── Resolution Report
ExamMetadataProvider（同じ接続口）
  ├── DummyExamMetadataProvider
  ├── CsvExamMetadataProvider
  └── DatabaseExamMetadataProvider  ← 将来追加
  ↓
Exam Metadata 1.0、Exam Completeness
```

- `Packages/knowledge-contracts/`：5つの将来クライアントが共通利用するJSON契約
- `src/knowledge_workbench/application.py`：AIの種類に依存しない処理順序
- `src/knowledge_workbench/providers/`：AI会社ごとの差を閉じ込める場所
- `prompts/`：国家試験向けの指示を版付きで管理
- `web/`：試験用入力画面
- `fixtures/`：Version 0.3からの変換にも使うオフライン動作確認用データ
- `imports/mappings/`：毎年のCSV列名、別名、claim、重要度計算の版付き設定
- `ExamImages/`：画像問題の外部ファイル（Knowledge JSONへ画像を保存しない）
- `data/knowledge_registry.sqlite3`：再起動後もID、履歴、最新版Knowledge JSON本文、独立Relation台帳を維持するローカル正本
- `data/registry_backups/`：画面から作成したSQLite世代Backup
- `tests/`：Schema、AI交換境界、画面APIを自動確認

## Prototype Phase 1で意図的に行わないこと

- PDF、note、動画、国家試験問題の生成
- 出典の自動取得と引用確認
- 12年分国家試験CSVの本番取込、Exam Metadata全体の永続保存・承認
- Excel埋込画像の抽出、OCR、画像解析
- 医学監修の自動化、AIによるClaim統合
- ロール別権限、操作者の本人確認、複数利用者の同時編集
- Exam Metadata本文の正式スナップショット保存・検索
- ログイン、複数利用者、クラウド公開
- 患者情報の入力・処理

これらはKnowledge JSON 1.0とExam Metadata 1.0のMVPを確認・承認してから進めます。

## Version 1.0 MVPで確認すること

- ASTやHbA1cが「検査項目」に分類されるか
- 「検査項目」と「臨床化学などの国家試験科目」が混同されていないか
- 測定方法と測定原理が別々の医学的事実として書かれているか
- 高値・低値で病態と代表疾患が分かれているか
- `claim_id`が各事実に付き、Schema検証に成功しているか
- Schemaが通っていても、情報不足なら各完全性スコアが低く表示されるか
- 不足項目が改善候補として具体的に表示されるか
- Exam Metadataが医学知識と独立し、`knowledge_id`と`claim_id`で結ばれているか
- ダミー出題履歴が正式CSVデータと明確に区別されているか
- `evidence`、`publish_targets`がAIによって作られていないか
- 疾患・微生物・寄生虫・染色法がVersion 1.0 MVPの対象外として安全に拒否されるか
