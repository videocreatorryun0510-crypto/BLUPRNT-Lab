# BLUPRNT Lab 開発ロードマップ

この文書は、BLUPRNT Lab の開発優先順位、フェーズごとの目標と完了条件、将来追加する機能を定義します。

ロードマップは日付ではなく、**前フェーズの品質ゲートを満たしたか**を基準に進めます。医学的安全性、根拠追跡、レビュー可能性を、機能数や開発速度より優先します。

すべての新機能は10年以上の運用を前提とし、NationalExam、TrainingVideo、Medical Knowledge Engine で共通利用できる設計を最初に検討します。共通利用できる場合は、ドメイン実装を始める前に共通ライブラリまたは共通サービスとして提案します。

## 現在のプロトタイプ進捗

| 段階 | 状態 |
|---|---|
| Phase 0：基盤設計 | 完了 |
| Phase 1：AI → Knowledge JSON | 完了 |
| Phase 2：Knowledge JSON 1.0 検査項目MVP | 完了・承認済み |
| Phase 2.5：Exam Metadata 1.0 MVP | 完了・承認済み |
| Phase 2.6：CSV Import & Exam Asset Integration MVP | 完了・承認済み |
| Phase 2.7：Knowledge Registry MVP | 完了・承認済み |
| Phase 2.8：Registry Approval & Claim Merge MVP | 実装済み・確認待ち |
| Phase 3.0：Publisher Architecture & Profile Foundation | 実装済み・確認待ち |
| Phase 3.1：PDF Publisher Adapter MVP | 実装済み・プロダクトオーナー確認待ち |
| Phase 3.2：Education Profile & Learning Strategy | 実装済み・プロダクトオーナー確認待ち |
| Phase 3.3：Visual Grammar & Illustration Specification | 実装済み・プロダクトオーナー確認待ち |
| Phase 3.4：Diagram Intent Layer & Semantic Blueprint Preparation | 実装済み・プロダクトオーナー確認待ち |
| Phase 3.5：Semantic Blueprint & Claim Mapping Resolver MVP | 実装済み・プロダクトオーナー確認待ち |
| Phase 3.6：Diagram Taxonomy | 実装済み・プロダクトオーナー確認待ち |
| Phase 4.0：Cross-Domain Coverage Validation | 検証完了・プロダクトオーナー確認待ち |
| Phase 4.1：Vertical Slice — Gram染色 | 検証実装完了・プロダクトオーナー確認待ち |
| Phase 5.0：Knowledge Domain Architecture | 設計完了・プロダクトオーナー確認待ち |
| Phase 5.1：First Production Category — Staining Method | 実装完了・プロダクトオーナー確認待ち |
| Phase 5.2：Knowledge Relation Foundation | 実装完了・プロダクトオーナー確認待ち |
| Phase 5.3：Production Category — Specimen & Relation Resolution | 実装完了・プロダクトオーナー確認待ち |
| Phase 5.4：Knowledge Growth Engine MVP | 実装完了・プロダクトオーナー確認待ち |
| Phase 5.5：Production Category — Reagent | 実装完了・プロダクトオーナー確認待ち |
| Phase 5.6：Existing Category Expansion — Acid-Fast Stain | 実装完了・プロダクトオーナー確認待ち |
| Phase 5.7：Structure Domain Review | 完了・承認済み |
| Phase 5.8：Production Category — Biological Structure MVP | 実装完了・プロダクトオーナー確認待ち |
| Phase 5.9：Knowledge Platform Stabilization | レビュー完了・プロダクトオーナー確認待ち |
| Phase 5.10：Disease Category MVP | 実装完了・プロダクトオーナー／医学監修確認待ち |
| Phase 5.11：Laboratory Test Item Category MVP | 実装完了・プロダクトオーナー／医学監修確認待ち |
| Phase 5.12：Disease Relation Vocabulary MVP | 実装完了・プロダクトオーナー確認待ち |
| Phase 5.13：Source Bundle Publisher MVP | 実装完了・プロダクトオーナー確認待ち |
| Phase 5.14：Approval Gate MVP | 実装完了・プロダクトオーナー確認待ち |
| Phase 5.15：Presentation Contract MVP | 実装完了・プロダクトオーナー確認待ち |
| Phase 5.16：Presentation Engine Adapter Contract MVP | 実装完了・プロダクトオーナー確認待ち |
| Phase 5.17：Provider Payload Preparation & Response Traceability MVP | 実装完了・プロダクトオーナー確認待ち |
| Phase 5.18：Presentation Prompt Builder & Gemini Adapter Sandbox MVP | 実装完了・実API受入確認待ち |
| Phase 5.18.1：Gemini Sandbox Real API Acceptance Test | 実装完了・ユーザー明示実行待ち |
| Phase 5.19：Presentation Artifact Contract MVP | 実装完了・プロダクトオーナー確認待ち |
| Phase 5.20：Presentation Artifact Registry & Approval MVP | 実装完了・プロダクトオーナー確認待ち |
| Phase 5.20.1：Knowledge–Artifact Dual Approval Gate | 実装完了・GitHub保存済み |
| Phase 5.21：Medical Review Governance & Approval Criteria Design | 設計完了・プロダクトオーナー判断待ち |
| Phase 5.22：Knowledge Authoring Workflow MVP | 実装完了・プロダクトオーナー確認待ち |
| Phase 5.23：Knowledge Promotion Workflow MVP | 実装完了・プロダクトオーナー確認待ち |
| Phase 5.24：AI Knowledge Pipeline MVP | 実装完了・プロダクトオーナー確認待ち |

Exam Metadataは医学知識と独立した版付きコンポーネントとし、`knowledge_id`と`claim_id`で結びます。Phase 2.7では、`claim_key`を医学的な意味の固定キー、`claim_id`を内部IDとして分離した永続Registryを実装しました。Phase 2.8では、人によるClaim統合・承認、旧IDから統合先IDへの転送、全履歴、世代Backup/Restore、Registryを書き換えないCSV Previewを実装しました。Phase 3.0〜3.6ではPublisher Core、PDF Adapter、Education、Visual Grammar、Diagram Intent、Semantic Blueprint、Diagram Taxonomyを段階的に追加しました。Phase 4.0では必須6用語と追加4用語を既存経路で検証しました。Phase 4.1ではKnowledge Schemaを変更せず、Gram染色24 Claimのうち16 Claimを互換投影し、RegistryからPublication PlanとSemantic Blueprintまで通しました。Phase 5.0では国家試験全体を22のKnowledge CategoryとRelationで扱うDomain Mapを設計しました。Phase 5.1〜5.6で染色法、検体、試薬、Relation、索引型Growth Engineを実装しました。Phase 5.7でStructure境界を`biological_structure`へ確定し、Phase 5.8では細菌細胞壁1件を正式登録してGram染色の7 Relationをすべて解決しました。Phase 5.9ではコードを変更せず、基盤の安定領域・変更領域・成熟度をレビューしました。Phase 5.10では既存基盤を変えずに`disease`を6番目のCategory Unionへ追加し、鉄欠乏性貧血17 Claimを正式Registryへ登録しました。Phase 5.11では`laboratory_test_item`を7番目のCategory Unionへ追加し、フェリチン11 Claimを正式Registryへ登録しました。Phase 5.12では疾患用Relation 7語の意味、方向、Category範囲をVersion 1.0 Catalogへ固定し、Relation実体を作らずWorkbenchへ表示しました。Phase 5.13ではKnowledge・Registry・Exam Metadataを変更せず、Gemini等へ渡すSource Bundle JSON 1.0を生成する独立Publisherを追加しました。Phase 5.14では承認状態を共通Approval Contractへ固定し、`approved`以外の公開・外部AI送信をApproval Gateで停止します。Phase 5.15ではAI非依存のPresentation Request、Phase 5.16ではProvider非依存のAdapter Interface、Phase 5.17では承認済み正本のProvider Payload解決、Data Egress Policy、Traceable Responseを追加しました。Phase 5.18ではProvider非依存Prompt BuilderとGemini固有Sandbox Adapterを分離し、Phase 5.19ではProvider・Rendererに依存しないPresentation Artifactを教育成果物の唯一の正本Contractとして追加しました。Phase 5.20ではArtifact専用Registry、独立承認、Immutable approved版、History、Diff、Completeness、approved限定Renderer Gatewayを追加しました。Phase 5.20.1ではKnowledgeとArtifactの両方を確認するDual Approval Gateへ強化し、Phase 5.21ではそのKnowledge `approved`が保証する人の医学レビュー基準、Role、Evidence、Checklist、独立Review Versionを設計しました。Phase 5.22では未完成Knowledgeを正式Registryから分離して、人が5項目からSkeleton、Claim、Referenceを短時間で作成・検証・入出力できるAuthoring Workflowを追加しました。Phase 5.23ではSchema・Category・Claim・Reference・Registry重複・ID・FingerprintをPreviewで確認し、明示確定時だけ安定IDとVersionを維持して正式Registryへ`draft`登録するPromotion Workflowを追加しました。Phase 5.24では、Theme、Evidence、Claim、Reference、Knowledge BuilderをProvider非依存のPipelineとして分離し、実検索・LLMなしのSandboxからAuthoring Draft Previewと明示保存まで接続しました。

### Phase 5.0成果物

- [Knowledge Domain Architecture](knowledge_domain_architecture.md) — Domain Map、22 Categoryの責務、共通/専用属性、Completeness、Publisher接続、実装順
- 国家試験の科目分類とKnowledge Categoryを分離
- 臓器・組織・細胞・微生物構造を`biological_structure`として統合（Phase 5.7で名称・範囲更新）
- 輸血領域を血液型・製剤・検査法・疾患のRelationとして整理
- Category Union実装順をWave 0〜8として定義

### Phase 5.1成果物

- `staining_method_v1.0`のCategory Unionと専用Schema
- 定義、目的、対象構造、固定法、工程、試薬、判定、精度管理、限界、出典を評価するCompleteness
- WorkbenchのGram染色登録・編集・再読込
- SQLite Registryへの最新版Knowledge JSON本文、安定ID、版、履歴、承認状態の保存
- 既存Content Profile設定からSemantic BlueprintとPublication Planへの接続
- ASTとGram染色の回帰テスト
- [Knowledge Category実装ガイド](category_implementation_guide.md)

### Phase 5.2成果物

- Knowledge Relation Version 1.0 ContractとJSON Schema
- `uses_specimen`、`uses_reagent`、`targets_structure`、`related_method`の固定Vocabulary
- AIや曖昧検索を使わないRegistry完全一致Resolver
- Knowledge本文・Claim Registryとは別のRelation台帳と変更履歴
- Gram染色7件の`unresolved_relation`と安定Relation ID
- Workbench「関連Knowledge」閲覧とRelation API
- ASTとGram染色の回帰テスト
- [Knowledge Relation Foundation](knowledge_relation_foundation.md)

### Phase 5.3成果物

- `specimen_v1.0`のCategory Union、専用Schema、Completeness
- 血清、血漿、全血、尿、便、喀痰、髄液、塗抹標本を識別できる`specimen_kind`
- Workbenchの塗抹標本登録・編集・再読込
- Relation Version 1.1のContext
- Specimen登録後の保存済み染色法Relation再評価
- Gram染色`uses_specimen`から塗抹標本`knw_10000005`への解決
- AST・Gram染色の回帰テストとPublisher Core無変更確認
- [Specimen & Relation Resolution](specimen_relation_resolution.md)

### Phase 5.4成果物

- 対象名、Relation Type、Category、解決状態で検索できるRelation Resolution Index
- 末尾一致を先頭検索へ変換する逆順キー
- Knowledge保存時に未解決の索引候補だけを再評価するイベント処理
- 再評価・解決・未解決件数を永続化するResolution Report
- WorkbenchのNetwork SummaryとNetwork Completeness
- AST・Gram染色・Specimen回帰テストとPublisher Core無変更確認
- [Knowledge Growth Engine](knowledge_growth_engine.md)

### Phase 5.5成果物

- `reagent_v1.0`のCategory Union、専用Schema、Completeness
- 一次染色液、媒染液、脱色液、対比染色液を区別する`reagent_kind`
- 4種類のGram染色用試薬の正式Knowledgeと安定`knowledge_id`・`claim_key`
- WorkbenchのReagent選択・登録・編集・再読込
- 4回の保存イベントで各1件だけを再評価・解決するResolution Report
- Gram染色本文を変えないNetwork更新（14.3% → 71.4%）
- AST・Gram染色・Specimen・Reagent回帰テストとPublisher Core無変更確認
- [Reagent Category](reagent_category.md)

### Phase 5.6成果物

- 抗酸菌染色（Ziehl-Neelsen染色）の正式Knowledge下書きと安定`knowledge_id`・`claim_key`
- 既存`staining_method_v1.0`と既存Completenessの再利用
- Workbenchの抗酸菌染色登録・編集・再読込
- 保存イベントで`related_method` 1件だけを再評価・解決するResolution Report
- Gram染色本文を変えないNetwork更新（71.4% → 85.7%）
- AST・Gram染色・抗酸菌染色・Specimen・Reagent回帰テスト
- Knowledge Schema、Category Union、Publisher Core無変更確認
- [Acid-Fast Stain Expansion](acid_fast_stain_expansion.md)

### Phase 5.7成果物

- Structure系Category候補の比較
- `biological_structure`推奨案とCategory境界
- 構造分類とTaxon範囲を分離する設計
- Uberon、Cell Ontology、Gene Ontology、FMA、NCBI Taxonomyとの接続方針
- Gram染色`targets_structure`の互換移行案
- 細菌・細胞壁・ペプチドグリカン・抗菌薬を結ぶKnowledge Network案
- 実装前Architecture Decision案とProduct Owner確認事項
- [Structure Domain Review](structure_domain_review.md)

### Phase 5.8成果物

- `biological_structure_v1.0`のCategory Unionと最小Schema
- 定義、主な機能、出典だけを必須とするMVP Completeness
- 細菌細胞壁`knw_10000011`と安定したClaim Dictionary
- Workbenchの登録・編集・再読込
- `targets_structure`の解決先Categoryを`biological_structure`へ確定
- 索引候補1件だけの再評価とResolution Report保存
- Gram染色本文を変えないNetwork更新（85.7% → 100.0%）
- AST・Gram染色・抗酸菌染色・Specimen・Reagent・Biological Structure回帰
- Publisher Core無変更確認
- [Biological Structure Category](biological_structure_category.md)

### Phase 5.9成果物

- Category、Registry、Relation、Growth Engine、Resolution Index、Publisher Compatibilityの責務レビュー
- 既存CategoryへのKnowledge追加で変更する場所・変更しない場所の整理
- データ追加、設定追加、Platform契約変更の3段階分類
- Claim DictionaryのPythonコード依存と1000件規模でのリスク評価
- Knowledge、Registry、Relation、Growth Engine、Medical Review、Publisherの最新版責務図
- 成熟度を「MVP完成・Production Ready前」と判定
- Production Readyへ進む8つの品質ゲート
- [Knowledge Platform Stabilization](knowledge_platform_stabilization.md)

### Phase 5.10成果物

- `disease_v1.0`のCategory Unionと疾患専用Schema
- 定義、病態、主な検査所見、出典に限定したDisease Completeness
- Workbenchの鉄欠乏性貧血登録・編集・再読込
- 安定Knowledge ID `knw_10000012`と17個の固定Claim
- 関連先が存在しない状態でRelationを推測せず0件に保つGrowth Engine確認
- Registry 11 Knowledge、171 Claim、13 Relation、6対応Categoryへ更新
- Publisher Core無変更と193件の全自動回帰テスト
- [Disease Category MVP](disease_category.md)

### Phase 5.11成果物

- `laboratory_test_item_v1.0`のCategory Unionと検査項目専用Schema
- 定義、臨床的意義、測定対象、出典に限定したCompleteness
- Workbenchのフェリチン登録・編集・保存・再読込
- 安定Knowledge ID `knw_10000013`と11個の固定Claim
- Relationを無理に作らず0件、索引候補だけを評価してResolution Report 0件
- Registry 12 Knowledge、182 Claim、13 Relation、7対応Categoryへ更新
- Publisher Core無変更と198件の全自動回帰テスト
- [Laboratory Test Item Category MVP](laboratory_test_item_category.md)

### Phase 5.12成果物

- `has_high_test_item`、`has_low_test_item`、`diagnosed_by`、`caused_by`、`related_disease`、`affects_structure`、`has_pathophysiology`の固定Vocabulary
- 意味、方向、Source Category、Target Category、例を持つVersion 1.0 Catalog
- Knowledge Relation Version 1.0／1.1を変更せず、Disease Vocabulary対応のVersion 1.2 Contractを追加
- Disease Vocabulary専用JSON Schemaと読取専用API
- Workbenchの7 Vocabularyカード表示
- Knowledge、Registry、Relation、Growth Engine、Publisher Core無変更確認
- 全206件の自動回帰テスト成功
- [Disease Relation Vocabulary MVP](disease_relation_vocabulary.md)

### Phase 5.13成果物

- Source Bundle JSON Version 1.0 ContractとJSON Schema
- Knowledge・Registry・Exam Metadataを読むだけの独立Publisher Adapter
- `claim_key`で重要ClaimとSummaryを選ぶ版付きSource Bundle Profile
- Provider非依存の`diagram_requests`と根拠Claim ID
- フェリチン11 Claim、鉄欠乏性貧血17 ClaimのSource Bundle
- `Publisher Output/source_bundle/`への原子的JSON保存
- Workbench「Source Bundle生成」とJSON全文・保存先・版・状態表示
- Knowledge、Registry、既存Publisher Core無変更の自動回帰テスト
- 全221件の自動テスト、静的解析、画面操作確認に成功
- [Source Bundle Publisher MVP](source_bundle_publisher.md)

### Phase 5.14成果物

- `draft → owner_review → medical_review → approved → published`の共通Approval Contract
- 既存`deprecated`を台帳互換状態として維持
- 隣接段階への差し戻しとRegistry承認履歴
- Source Bundle metadataの`approval_state`、承認者・日時、Review Version、再確認要否
- `can_publish()`と`can_send_to_external_ai()`のProvider非依存Gate
- `approved`だけを許可するVersion 1.0 Policy
- `Publisher Output/logs/approval_gate.jsonl`への判定監査ログ
- WorkbenchのApproval State、公開可否、外部AI送信可否、停止理由表示
- 全227件の自動回帰テスト、静的解析、型検査
- [Approval Gate MVP](approval_gate.md)

### Phase 5.15成果物

- AI非依存のPresentation Contract Version 1.0とJSON Schema
- Presentation Type 6種、Output Format 6種の独立Vocabulary
- `presentation_document`／`structured_json`のMVP生成
- Knowledge固有医学情報を持たない`presentation_document_basic_v1`
- Source BundleからID参照だけを選ぶPresentation Request Builder
- `preview`と`external`の明示的分離
- External生成時の既存`can_send_to_external_ai()`強制
- Knowledge Version、Fingerprint、Approval State、Review VersionのStale検知
- Claim、Key Message、Diagram Request、ReferenceのTraceability Validator
- 原子的JSON保存とClaim本文を含まない監査ログ
- Workbenchの生成・停止理由・JSON全文・コピー表示
- [Presentation Contract MVP](presentation_contract.md)

### Phase 5.16成果物

- Provider非依存のPresentation Engine Adapter Interface Version 1.0
- Provider名・Version・Preview／External対応を表すAdapter Descriptor
- 外部通信を行わないDummy Adapter Version 1.0.0
- Request ID・Fingerprint・件数だけを持つメタデータPayload
- Presentation Result Contract Version 1.0
- Fingerprint・Claim・Diagram Request・Reference・ページ・Provider Version検証
- Previewでも記録し、Externalでは許可を必須にする既存Approval Gate接続
- 本文を保存しないPresentation Engine JSONL監査
- WorkbenchのDummy Adapter実行・Validation・Result表示
- [Presentation Engine Adapter Contract](presentation_engine_adapter_contract.md)
- [ADR-0009](adr/0009-provider-neutral-presentation-engine-adapter.md)

### Phase 5.17成果物

- Provider Payload Resolver Version 1.0.0
- 承認済みClaim本文を無変更で解決するPresentation Payload Contract 1.0
- Key Message、Exam Metadata、Diagram Request、Referenceの安全な解決
- Claim・Diagram・Reference Traceability Map
- 正本・Request・Policy・Claim Versionを固定するPayload Fingerprint
- Secret、`.env`、認証URL、ローカル絶対パス、個人情報候補を止めるData Egress Policy 1.0
- 非同期状態へ拡張可能なTraceable Response Contract 1.0
- PayloadとResponseを分離した本文なしJSONL監査
- WorkbenchのPayload Preview、停止理由、Traceable Dummy Response表示
- [Provider Payload & Response Traceability](provider_payload_and_response_traceability.md)
- [ADR-0010](adr/0010-approved-provider-payload-and-traceability.md)

### Phase 5.18成果物

- Provider非依存のPresentation Prompt Contract 1.0とBuilder Version 1.0.0
- Claim本文を無変更で引き継ぐContent・Layout・Validation Policy
- Gemini固有のPrompt変換、Interactions API通信、Response MapperをAdapter内部へ隔離
- `store=false`、`.env`認証、Timeout、最大1回Retry、構造化応答
- Token、任意の概算Cost、Duration、Fingerprint、ValidationのTraceable Response
- Provider生レスポンス・医学本文・APIキーを保存しないJSONL監査
- WorkbenchのPrompt Preview、Gemini Sandbox、Response Preview
- [Presentation Prompt & Gemini Sandbox](presentation_prompt_and_gemini_sandbox.md)
- [ADR-0011](adr/0011-provider-neutral-prompt-builder-and-gemini-sandbox.md)

### Phase 5.18.1成果物

- 実Registryを変更しない隔離Test Fixtureと一時SQLite
- Workbenchの実通信前Preflightと1回限りの明示実行
- Provider Request ID、構造化JSON、Fingerprint、Claim、Reference、無変更本文の受入検証
- 通信結果と受入結果を分ける`transport_result`／`validation_result`／`final_result`
- Token、Duration、Retry、HTTP Status、Provider Request IDの安全な結果表示
- 本文・Prompt・生Response・Secretを保存しない専用Audit
- [Gemini Real API Acceptance](gemini_real_api_acceptance.md)
- [ADR-0012](adr/0012-isolated-one-shot-gemini-api-acceptance.md)

### Phase 5.19成果物

- Presentation Artifact Contract Version 1.0とJSON Schema
- Claim本文を無変更でページへ配置するArtifact Builder Version 1.0.0
- Page、Claim、Reference、Fingerprint、Diagram、Layoutの保存前Validation
- Validation失敗時の保存禁止と本文なしJSONL Audit
- Provider・API・描画命令を持たない教育成果物の正本
- PowerPoint、PDF、Instagram、HTML、Canvaが共有するRenderer Interface
- 外部AI Draftと正本Artifactを分離するArtifact Mapper Interface
- WorkbenchのPage一覧、件数、Fingerprint、Validation、JSON全文、Copy、保存先表示
- [Presentation Artifact Contract](presentation_artifact_contract.md)
- [ADR-0013](adr/0013-presentation-artifact-as-sole-output-contract.md)

### Phase 5.20成果物

- SQLite Presentation Artifact Registry Version 1.0
- `knowledge_id + profile_id`単位の安定Artifact IDと追記型Version
- Knowledge承認と独立した`draft → owner_review → education_review → approved → published` Flow
- approved版の本文・Claim・Reference・Fingerprintを守るImmutable DB制約
- Version作成・承認・差し戻しの全History
- Headline、Page、Claim、Reference、Diagram、Layoutの構造化Diff
- 8区分のArtifact Completenessと「教育品質保証ではない」明示
- Registry検証とKnowledge Version整合性検証
- approved Artifactだけを既存Rendererへ渡すArtifact Renderer Gateway
- WorkbenchのArtifact一覧、Version、Approval、History、Diff、Completeness、JSON、Renderer利用可否
- [Presentation Artifact Registry & Approval MVP](presentation_artifact_registry.md)
- [ADR-0014](adr/0014-presentation-artifact-registry-and-approval.md)

### Phase 5.20.1成果物

- KnowledgeとArtifactをAND条件で確認するDual Approval Gate
- Artifact approved遷移時のKnowledge・Claim承認検証
- Knowledge Version、Review Version、Source / Artifact Fingerprint検証
- deprecated Claim Redirectと承認後変更の検出
- Artifact承認を変更せず算出するRenderer Eligibility / stale判定
- 承認拒否とRenderer判定のSQLite Gate Audit
- WorkbenchのArtifact承認、Knowledge承認、Renderer利用可否の分離表示
- 実フェリチンKnowledgeをdraftのまま維持し、Artifactを履歴付きでeducation_reviewへ是正
- [Knowledge–Artifact Dual Approval Gate ADR](adr/0015-knowledge-artifact-dual-approval-gate.md)

### Phase 5.21成果物

- Author / Editor、Product Owner、Medical Reviewer、Final Approver、SystemのRole Matrix
- Knowledge、Claim、Relation、Exam Metadataを分離したReview Scope
- Schema、Completeness、Evidence、Version、Reviewer、期限を含むApproval Criteria
- Evidence Level A/B/CとClaim重要度別の最低Evidence要件
- 時点依存情報のvalidity、jurisdiction、method/product scope、Review期限案
- Approval Stateと独立した6種類のReview Decision
- Category共通およびDisease / Laboratory Test Item / Staining Method専用Checklist Version 1.0案
- Knowledge Versionと独立し、対象Fingerprintへ固定するReview Version Contract案
- Gram染色、鉄欠乏性貧血、フェリチンの実Registryを変更しないPilot Gap Report
- [Medical Review Governance](medical_review_governance.md)
- [Medical Review Contract Version 1.0案](medical_review_contract_v1.md)
- [Medical Review Checklist Version 1.0案](medical_review_checklist_v1.md)
- [Pilot Medical Review Gap Report](reviews/medical-review-pilot-2026-08-06/pilot-gap-report.md)
- [ADR-0016](adr/0016-medical-review-governance-and-independent-review-version.md)

### Phase 5.22成果物

- 全7 Category対応のKnowledge WizardとContract-valid Skeleton
- 自動採番されるClaimの追加、編集、削除、並び替え
- Evidence Level、URL、書誌、ページ、DOI、PMID、Claim対応を持つReference Editor
- Schema、作成時Completeness、必須項目、Claim数、Reference整合性の保存前Validation
- JSON Import、JSON / Markdown Export
- 正式Registryを書き換えない独立JSON Draft Repository
- Workbench内の下書き一覧、編集状況、Validation表示
- [Knowledge Authoring Workflow](knowledge_authoring_workflow.md)
- [ADR-0017](adr/0017-pre-registry-authoring-draft-boundary.md)

### Phase 5.23成果物

- Registryを変更しないPromotion Previewと明示Commitの2段階Workflow
- Category別の明示的Claim保存先と、推測を行わないPromotion Mapper
- Schema、Category、Claim、Reference、Registry重複、Knowledge ID、Fingerprint Validation
- 同一Registry Keyの安定Knowledge ID再利用とVersion更新判定
- Promotion後のApproval State `draft`固定と自動承認禁止
- 成功後Draftの保持 / Archived選択（削除禁止）
- 本文を保存しない追記専用Promotion Log
- WorkbenchのPreview、Validation、Registry保存結果、Knowledge ID、Version、Log表示
- [Knowledge Promotion Workflow](knowledge_promotion_workflow.md)
- [ADR-0018](adr/0018-preview-gated-authoring-promotion.md)

### Phase 5.24成果物

- Provider非依存のEvidence Search Provider、Evidence Ranker、Claim Builder Interface
- Title、URL、Publisher、Evidence Level、日付、言語、種別、Snippet、Citationを持つEvidence Search Contract 1.0
- 情報源優先順位とEvidence Levelによる決定的Evidence Ranking
- Evidence IDを必須とするClaim候補とKnowledge Contract互換Reference Builder
- 既存Skeleton、Claim、ReferenceをAuthoring Draftへ組み立てるKnowledge Builder
- Previewと明示保存を分け、Registry・Promotion・Review・Approvalを変更しないApplication Service
- フェリチン、鉄欠乏性貧血、Gram染色のローカルFixture Sandbox
- WorkbenchのAI Knowledge Wizard、Evidence / Claim / Reference / Draft Preview
- [AI Knowledge Pipeline MVP](ai_knowledge_pipeline.md)
- [ADR-0019](adr/0019-provider-neutral-ai-knowledge-pipeline.md)

---

## 1. 開発優先順位

### Priority 0 — プロジェクト基盤

最初に、全システムで守るルールと設計上の判断方法を確立します。

- 上位READMEと共通設計文書
- 医学情報と出典のルール
- AIプロンプトとJSON契約のルール
- コーディング、テスト、レビューのルール
- ADR、用語集、Definition of Done

### Priority 1 — 共通コンテンツ基盤

3システムが共通利用する最小限の概念を先に確定します。

- 原資料と根拠位置
- コンテンツIDと版
- レビュー、修正、承認
- AIジョブとプロンプト版
- 成果物と監査記録
- 医学用語と国家試験分類
- 共通ID、エラー、JSON契約、出典モデルの共有パッケージ
- 外部AI・検索・保存先を交換できる共通アダプター契約
- 共有パッケージの所有者、版、互換性、廃止方針

### Priority 2 — MedicalPDF MVP

入力と出力が明確で、共通基盤の「根拠取得 → AI支援 → 検証 → 成果物生成」を一通り検証できるため、最初の製品MVPとします。

- 疾患名からA4一枚のドラフトPDFを生成
- 根拠、出典、生成日時、版を表示
- PDFのページ数と文字切れを自動検査
- 医療監修とGolden Testを実施

### Priority 3 — NationalExam MVP

MedicalPDFで確立した情報源・根拠・レビュー基盤を使い、国家試験向け問題制作へ拡張します。

- 出題基準と学習目標の管理
- 問題、選択肢、正答、解説、根拠の制作
- 正答一意性、誤答理由、禁忌の確認
- 医学・教育レビュー
- 問題セット出力

### Priority 4 — TrainingVideo MVP

共通コンテンツを台本、絵コンテ、字幕、動画へ展開します。大容量ファイルと長時間処理があるため、PDFと問題制作の基盤確立後に進めます。

- 研修目的と学習目標
- 根拠付き台本と絵コンテ
- 素材、ナレーション、字幕
- 動画レンダリングと品質検査
- 医学・映像レビュー

### Priority 5 — 横断統合と運用

- 統合制作ポータル
- 組織、権限、監査
- コンテンツ間の派生・参照関係
- 原資料改訂時の影響通知
- LMS・外部配信先との連携
- 運用監視、コスト、品質指標

### 新機能の着手ゲート

新機能は、次を設計レビューで確認するまで実装を開始しません。

- 3システムでの利用可能性を検討した
- ドメイン内部・共通ライブラリ・共通サービスの配置理由がある
- 既存の共通部品で実現できない理由がある
- API、データ、イベント、プロンプトの版方針がある
- データ移行、旧版廃止、ロールバックを説明できる
- 外部サービスを将来交換できる
- テスト、監視、バックアップ、障害対応を設計している
- 共通化する場合は所有者と利用予定システムが決まっている

---

## 2. フェーズ計画

## Phase 0 — 基盤文書の完成

### 目標

実装開始前の判断基準を完成させます。

### 成果物

- `README.md`
- `Docs/system.md`
- `Docs/roadmap.md`
- `Docs/coding_rules.md`
- `Docs/medical_rules.md`
- `Docs/prompt_rules.md`
- 各システムの設計README
- 用語集とADRテンプレート

### 完了条件

- 3システムの責務が重複せず説明されている
- 医学情報、AI、レビュー、出典の禁止事項が明文化されている
- 実装時のフォルダ構成と依存方向が定義されている
- 未決定事項が「未決定」として明示されている

## Phase 1 — 要件定義と技術検証

### 目標

技術を本採用する前に、リスクが高い部分を小さく検証します。

### 作業

- 代表ユースケースと利用者シナリオの確定
- 代表疾患、問題、動画テーマのサンプル作成
- AI提供者、PDF生成、動画生成、検索方式の比較
- データ分類、保存期間、権利管理の確定
- 非機能要件とコスト上限の数値化
- ADRによる技術選定

### 完了条件

- 採用技術と不採用理由がADRに記録されている
- 医療監修者が品質評価表を承認している
- AIなしでも検証可能なドメインモデルが定義されている
- 実患者データを使用しないテストデータ方針がある

## Phase 2 — 共通基盤MVP

### 目標

各製品が共有する最小機能を実装します。大規模な汎用プラットフォームを先に作りません。

### 対象

- コンテンツID、版、状態
- 原資料、根拠位置、権利状態
- プロンプト版とAIジョブ
- レビュー、修正依頼、承認
- 成果物メタデータと監査ログ
- 共通エラー形式とJSON契約

### 完了条件

- 1件のコンテンツについて原資料から承認まで追跡できる
- AI出力が承認済み領域へ直接入らない
- 組織・プロジェクト境界をテストできる
- 監査記録から誰が何を変更したか確認できる

## Phase 3 — MedicalPDF MVP

### 目標

疾患名からA4縦・1ページの教育用ドラフトPDFを安全に生成します。

### 対象

- 疾患名の正規化と曖昧性処理
- 信頼済み情報源からの根拠取得
- 固定JSON構造への生成
- HTML/CSSテンプレートとPDF生成
- 1ページ、A4寸法、文字切れ、出典の検査
- 医療監修とGolden Test

### 完了条件

- `MedicalPDF/README.md` のMVP受入基準を満たす
- 代表疾患で医学的重大誤りと出典捏造がない
- 一枚に収まらない場合に安全に失敗できる
- 生成条件とPDFを再現できる

## Phase 4 — NationalExam MVP

### 目標

国家試験向け問題を、出題基準と根拠に沿って制作・レビューできるようにします。

### 対象

- 最新の公式出題基準と分類体系
- Exam Blueprint
- 問題、選択肢、正答、解説、誤答理由
- 根拠と学習目標の対応
- 類似、曖昧、正答一意性、禁忌のチェック
- 問題セットの出力

### 完了条件

- 代表分野の問題セットを一貫した形式で制作できる
- 医学レビューと教育レビューが分離されている
- すべての正答・解説から根拠へ戻れる
- 既存問題の不適切な複製を検出・防止できる

## Phase 5 — TrainingVideo MVP

### 目標

根拠付き台本から、字幕を含む短い研修動画を制作できるようにします。

### 対象

- Training Briefと学習目標
- 台本、絵コンテ、シーン、タイムライン
- 画像、音声、動画素材と権利情報
- ナレーション、文字起こし、字幕
- 動画レンダリングと映像・音声検査
- 動画、字幕、配布資料の出力

### 完了条件

- 代表テーマで一連の制作・レビューを完了できる
- 台本、画面、音声、字幕の不一致を検査できる
- 使用素材のライセンスを追跡できる
- 長時間処理を再実行・監視できる

## Phase 6 — 統合制作ポータル

### 目標

3システムを一つの制作体験として統合します。

### 対象

- 統合プロジェクト画面
- 横断検索
- コンテンツの派生・参照関係
- 共通レビューキュー
- 更新影響通知
- ロールと権限
- 共通テンプレートとブランド管理

### 完了条件

- 同じ原資料からPDF、問題、動画を安全に派生できる
- 元コンテンツ更新時に影響先を特定できる
- ドメイン間で内部DBへ直接依存していない
- 監修者が横断的にレビューできる

## Phase 7 — 本番運用と拡張

### 目標

限定利用から安定した組織利用へ移行します。

### 対象

- 本番監視、アラート、障害対応
- バックアップ、復元、保存・削除
- セキュリティレビューと侵入テスト
- AI品質、コスト、処理時間の継続評価
- 組織別設定、利用量、権限管理
- 外部サービスとLMS連携

### 完了条件

- SLOと運用責任者が定義されている
- 障害・誤情報・権利問題の対応訓練を完了している
- 重要データの復元試験に成功している
- AIモデル更新時の回帰評価を自動化している

---

## 3. フェーズ移行ルール

- 前フェーズの重大な未完了事項を「後で対応」として持ち越さない
- 医学的安全性、個人情報、著作権の未解決事項はフェーズ移行を止める
- 機能追加より、根拠追跡・レビュー・監査を優先する
- プロトタイプをそのまま本番コードとして扱わない
- 新技術はデモの見栄えではなく、再現性、保守性、運用条件で評価する
- 一時的な実装を本番経路へ入れず、必要な場合は期限、置換計画、所有者を明記する
- 新機能ごとに3システムでの共通利用可能性を記録する
- 共通化できる処理は、ドメイン実装の前に共有パッケージまたは共通サービスを提案する
- 共有パッケージには版、互換性、移行、廃止の方針を持たせる
- フェーズ終了時に設計文書とADRを更新する

---

## 4. 将来追加する機能

### 4.1 共通基盤

- 複数組織・複数チーム対応
- 医療監修者の割当てと負荷管理
- コンテンツ間の知識グラフ
- 原資料改訂・失効時の影響通知
- 承認済みコンテンツの再利用カタログ
- 多言語・地域別コンテンツ
- ブランド・テンプレート管理
- 品質、コスト、制作時間のダッシュボード
- 誤り報告、訂正、再公開ワークフロー

### 4.2 MedicalPDF

- 対象者、難易度、専門領域の選択
- 図解、病態フロー、鑑別表
- 疾患比較PDF
- 複数ページ資料と講義ハンドアウト
- テンプレート選択と施設ブランド対応
- タグ付きPDFとアクセシビリティ強化
- ガイドライン改訂時の自動再レビュー

### 4.3 NationalExam

- 出題ブループリントの自動充足確認
- 分野別・難易度別問題セット
- 画像問題、連問、臨床推論問題
- QTI、CSV、LMS出力
- 項目分析、識別力、難易度の統計
- 類似問題・漏えい・著作権リスク検出
- MedicalPDFやTrainingVideoへの学習リンク

### 4.4 TrainingVideo

- 図表・スライドの自動構成支援
- 合成音声と読み方辞書
- 多言語字幕と吹替
- チャプター、確認問題、配布資料
- 動画テンプレートとブランド管理
- SCORM、xAPI、LMS向けパッケージ
- 映像・音声の自動品質検査

### 4.5 AI・評価

- 複数AI提供者の切替
- タスク別モデルルーティング
- 医学領域別の評価データセット
- AI生成差分レビュー
- 引用整合性と矛盾の自動検出
- レッドチームテストとプロンプト攻撃検査
- コスト・品質・遅延を考慮した自動選択

---

## 5. 将来も対象外とする領域

事業方針を変更しない限り、次をBLUPRNT Labの中核機能にはしません。

- 患者個人への診断・治療・処方判断
- 緊急通報やトリアージの代替
- 電子カルテの正本管理
- 医療機器の制御
- 無監修AIコンテンツの公式公開
- 権利確認なしの教材・問題・画像・動画の再利用

対象外領域を追加する場合は、法務・医療安全・セキュリティ評価を行い、上位READMEと本ロードマップを更新します。

---

## 6. ロードマップの更新

- 各フェーズの開始・終了時に更新する
- 優先順位変更の理由を記録する
- 未完了項目を削除せず、延期・中止・代替を明示する
- 技術選定の詳細はADRへ分離する
- 日程、担当者、チケットはプロジェクト管理ツールで管理し、本書には長期方針を残す
