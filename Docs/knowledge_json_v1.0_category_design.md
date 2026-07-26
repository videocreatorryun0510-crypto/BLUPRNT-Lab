# Knowledge JSON Version 1.0 カテゴリ設計書

設計状態：Draft  
対象：疾患・病態、微生物、寄生虫、染色法  
設計日：2026-07-16

## 1. この文書の目的

Knowledge JSON Version 1.0で、臨床検査技師国家試験教材に必要な医学的事実を、カテゴリごとに決められた場所へ保存する方法を定義する。

この設計の目標は、PDF、note、TrainingVideo、NationalExamが医学的文章を読んで意味を推測せず、template_id、JSONのパス、claim_idだけで必要な事実を取得できる状態である。

今回は設計だけを行う。Knowledge Workbench、AI接続、プロンプト、画面、Schema、各Publisherは変更しない。

## 2. 最重要原則

1. Knowledge JSONは医学的事実、国家試験との対応、出典、claim参照だけを保持する
2. 読みやすい文章、要約、語呂合わせ、図の構図、動画演出、問題文は保存しない
3. フィールドの場所そのものが医学的意味を表す
4. Publisherはassertionの文章を解析して分類しない
5. 1つのclaimは、1つの出典で独立して確認できる最小の医学的主張とする
6. 数値、診断基準、検査手順、薬剤耐性、感染対策などは、根拠がない場合に空欄を推測で埋めない
7. Schema ValidationとCategory Completeness Validationを分離する
8. Completenessは情報量を評価するもので、医学的正しさや承認を保証しない

## 3. Version 1.0の全体構造

~~~text
KnowledgeRecord 1.0
├── schema_version
├── knowledge_id
├── content_revision
├── term
├── classification
├── core_facts
│   └── definitions
├── category_content
│   ├── disease_condition_v1.0
│   ├── microorganism_v1.0
│   ├── parasite_v1.0
│   └── staining_method_v1.0
├── exam_metadata
├── evidence
└── publish_targets

CompletenessAssessment 1.0（Medical Knowledge Engine管理）
├── assessment_id
├── knowledge_id / content_revision
├── profile_id / profile_version
├── schema_validation
├── score / level
├── requirement_results
├── missing_items
└── improvement_actions
~~~

CompletenessAssessmentはKnowledgeRecordの医学的事実へ混ぜない。Medical Knowledge Engineがknowledge_idとcontent_revisionに結び付けて別に保存する。

理由は、完全性スコアは医学的事実ではなく、評価ルールの版によって変化する品質情報だからである。同じKnowledge JSONでも評価プロファイルが更新されればスコアが変わる可能性がある。

## 4. 全カテゴリ共通項目

| 項目 | 必須 | 役割 | 保存理由 |
|---|---:|---|---|
| schema_version | 必須 | 契約版を識別する | 読み手が正しい構造を選ぶため |
| knowledge_id | 必須 | 用語単位の安定ID | 4つのPublisherと関連Knowledgeから共通参照するため |
| content_revision | 必須 | 内容変更回数 | 出典・承認・成果物が参照した版を固定するため |
| term.canonical_name | 必須 | 標準名称 | 表記揺れを抑えるため |
| term.english_name | 任意 | 英語名称・学名 | 教科書・学術資料・微生物名の照合に使うため |
| term.aliases | 任意 | 略称、旧称、同義語 | 入力検索と過去問照合に使うため |
| classification.term_type | 必須 | カテゴリ識別 | 専用テンプレートを一意に決めるため |
| classification.primary_exam_domain | 必須 | 主国家試験科目 | NationalExamと学習分類で使うため |
| classification.related_exam_domains | 任意 | 関連科目 | 分野横断検索に使うため |
| core_facts.definitions | 必須 | 用語の定義 | すべてのPublisherが最初に参照できる共通事実とするため |
| category_content.template_id | 必須 | 専用テンプレート識別 | Publisherが解釈せず処理を選べるようにするため |
| exam_metadata | 必須キー | 出題基準・過去問分析結果 | 医学的事実と試験上の優先度を分離するため |
| evidence | 必須キー | claimと根拠資料の対応 | 事実単位で根拠を追跡するため |
| publish_targets | 必須キー | 媒体別の優先claim参照 | 本文を保存せず利用順だけ指定するため |

### 4.1 Version 0.3から整理する共通部分

Version 0.3のcore_facts.mechanismsとcore_facts.characteristicsは、Version 1.0ではカテゴリ専用領域へ移す。

定義以外の事実を共通のmechanisms、characteristicsへ入れると、同定試験、生活環、検査所見、染色工程などが混在し、Publisherが意味を判別できないためである。

### 4.2 空値の共通ルール

| 値 | 意味 |
|---|---|
| キーの省略 | Schema違反。Version 1.0では認めない |
| null | 関連Knowledge IDがまだ作成されていないなど、Schemaが明示した場合だけ許可 |
| 空文字 | 原則禁止 |
| 空配列 | 事実が未収集、または適用外。Completeness Validationが理由を判定する |
| not_applicable | Knowledge JSONへ直接書かず、CompletenessAssessmentの例外記録へ理由付きで保存する |
| not_yet_researched | 不足として扱い、得点しない |

適用外を認めるには、評価プロファイルに条件が定義され、理由が記録されている必要がある。単にAIが生成しなかった場合は適用外にしない。

## 5. claim_id設計

### 5.1 基本規則

- claim_idは内容を埋め込まない不透明なIDとする
- AIの文章からハッシュ生成したIDを正式版では採用しない
- Medical Knowledge EngineのID台帳が発行する
- 表現だけを修正し医学的意味が同じ場合は同じclaim_idを維持する
- 医学的意味、対象、方向、条件、因果関係のいずれかが変わった場合は新しいclaim_idを発行する
- 1つのclaimへ「Aであり、Bであり、Cである」のように独立事実を詰め込まない
- 出典、国家試験優先度、Publisher優先度はclaim_idを参照する
- 並び順はclaim_idへ埋め込まず、医学的順序が必要な項目だけorderを別フィールドで持つ

### 5.2 claimを付ける単位

| 事実の種類 | 1 claimの単位 |
|---|---|
| 定義 | 1つの定義上の主張 |
| 病因 | 1つの原因と対象病態の関係 |
| 病態生理 | 1つの因果・変化・機序 |
| 検査所見 | 1検査、1方向、1条件の組み合わせ |
| 形態所見 | 1検体・1観察方法における1所見 |
| 鑑別 | 1比較疾患に対する1つの識別事実 |
| 培地・集落 | 1培地条件における1つの発育・集落所見 |
| 同定試験 | 1試験に対する1結果と解釈 |
| 毒素 | 1毒素と1主要作用の関係 |
| 薬剤耐性 | 1耐性機構と対象薬剤群の関係 |
| 生活環 | 1段階から次段階への1つの遷移 |
| 感染型・診断型 | 1生活期と対象宿主・検体の関係 |
| 染色原理 | 1つの化学的・構造的原理 |
| 染色試薬 | 1試薬と1役割の関係 |
| 染色工程 | 1順序における1操作 |
| 染色結果 | 1対象構造と1観察結果・解釈 |
| 精度管理 | 1対照と1期待結果 |
| エラー原因 | 1操作エラーと1結果への影響 |

### 5.3 assertionと構造化値

各claimは、医学的主張を表すassertionと、カテゴリ専用の構造化値を持てる。

例として同定試験では、test_name、expected_result、interpretationを別フィールドで保持する。Publisherはassertionの文章から試験名や陽性・陰性を抽出しない。

assertionは完成記事の文章ではない。出典と照合できる標準的な医学的主張であり、語調、見出し、文字数、強調、表示順はPublisherが決める。

## 6. 疾患・病態テンプレート

template_id：disease_condition_v1.0

疾患と病態を同じ上位カテゴリで扱い、condition_kindでdisease、syndrome、pathophysiologic_state、deficiency、injury、otherを区別する。

| 項目 | 区分 | 役割 | 保存理由 | 空欄を許容する条件 |
|---|---|---|---|---|
| condition_kind | 必須 | 疾患・症候群・病態などを区別 | 完全性ルールを切り替えるため | 許容しない |
| etiologies | 必須 | 原因・病因 | 原因と病態をPublisherが直接取得するため | 原因不明が医学的事実で、根拠付きで適用外とされた場合 |
| risk_factors | 任意 | 発症・悪化に関連する因子 | 病因と相関を混同しないため | リスク因子が国家試験範囲外、または確立していない場合 |
| pathophysiology | 必須 | 因果関係・機序 | 図解、説明、問題作成で共通利用するため | 許容しない。少なくとも1 claim必要 |
| clinical_findings | 必須 | 症状・身体所見 | 検査所見と臨床所見を分離するため | 無症候性状態では理由付き適用外 |
| laboratory_findings | 必須・最重要 | CBC、生化学、免疫、微生物などの所見 | 臨床検査技師国家試験の中心情報だから | 検査所見を持たない概念に限り理由付き適用外 |
| morphologic_findings | 条件付き必須 | 末梢血、骨髄、組織、細胞などの形態 | 病理・血液分野で画像教材へ接続するため | 形態所見が診断・試験範囲に関係しない場合 |
| diagnostic_tests | 必須 | 診断・支持・除外に使う検査 | 検査名と診断上の役割を直接取得するため | 許容しない |
| differential_diagnoses | 必須 | 比較疾患と識別点 | 国家試験の比較問題に使うため | 鑑別対象が定義できない基礎病態に限り理由付き適用外 |
| complications | 任意・推奨 | 主要合併症 | 疾患理解と関連知識に使うため | 主要合併症がない、または国家試験範囲外の場合 |
| associated_conditions | 任意 | 原因疾患、併存病態、続発状態 | Knowledge間の医学的関係を明示するため | 関連が確認できない場合 |

### 6.1 疾患・病態claimの構造

- EtiologyClaim：cause_name、cause_kind、related_knowledge_id、assertion
- RiskFactorClaim：factor_name、related_knowledge_id、assertion
- PathophysiologyClaim：process_name、upstream_claim_ids、assertion
- ClinicalFindingClaim：finding_kind、finding_name、assertion
- LaboratoryFindingClaim：test_name、test_knowledge_id、direction_or_result、specimen、conditions、assertion
- MorphologicFindingClaim：specimen、observation_method、feature_name、assertion
- DiagnosticTestClaim：test_name、test_knowledge_id、diagnostic_role、expected_result、assertion
- DifferentialDiagnosisClaim：compared_condition_name、compared_knowledge_id、distinguishing_feature、assertion
- ConditionRelationClaim：related_condition_name、related_knowledge_id、relation_type、assertion

詳細な治療法はVersion 1.0の必須構造にしない。臨床検査技師国家試験の知識基盤を一般医学百科事典へ拡大しすぎるためである。

## 7. 微生物テンプレート

template_id：microorganism_v1.0

organism_groupでbacterium、fungus、virus、prion、otherを区別し、培養可能性などの条件付きルールを切り替える。

| 項目 | 区分 | 役割 | 保存理由 | 空欄を許容する条件 |
|---|---|---|---|---|
| organism_group | 必須 | 細菌・真菌・ウイルスなどを区別 | 培養・染色・同定ルールを切り替えるため | 許容しない |
| taxonomy | 必須 | 分類学的位置 | 類似微生物との整理に使うため | 少なくとも主要分類1件が必要 |
| morphology_and_staining | 必須 | 形態、配列、染色性 | 顕微鏡所見と鑑別の基礎だから | プリオンなど形態・染色が非適用の場合のみ理由付き適用外 |
| growth_requirements | 条件付き必須 | 酸素要求、温度、栄養、宿主細胞など | 培養条件を文章解析せず取得するため | 培養を行わない対象では理由付き適用外 |
| culture_media | 条件付き必須 | 選択・分離・確認培地と発育 | 培地問題に直接利用するため | 日常的に培養しない対象では適用外 |
| colony_characteristics | 条件付き必須 | 集落の色、形状、溶血など | 培地と集落所見を分離するため | 培養非適用の場合 |
| identification_tests | 必須・最重要 | 生化学、抗原、分子、質量分析などの同定 | 国家試験の同定問題に使うため | 許容しない。培養不能でも別の検出・同定法が必要 |
| virulence_factors | 任意・推奨 | 付着、侵入、免疫回避など | 病原性の理解に使うため | 確立した主要因子がない場合 |
| toxins | 条件付き必須 | 毒素名と作用 | 毒素産生菌を独立して扱うため | 毒素を産生しない場合は適用外 |
| associated_diseases | 必須 | 代表疾患 | 微生物と疾患Knowledgeを結ぶため | 許容しない |
| diagnostic_specimens | 必須 | 検査材料・採取部位 | 検査法と材料を結ぶため | 許容しない |
| detection_methods | 必須 | 培養、抗原、核酸、顕微鏡など | 診断工程を直接取得するため | 許容しない |
| antimicrobial_resistance | 条件付き必須 | 耐性名、機構、対象薬剤 | MRSAなど国家試験頻出の耐性を扱うため | 臨床的耐性概念が非適用、または主要耐性がない場合 |
| transmission_routes | 任意・推奨 | 感染経路 | 感染症理解に使うため | 非感染性・環境由来で経路を定義しない場合 |
| infection_control | 任意 | 消毒、隔離、届出などの事実 | 研修教材と国家試験で利用するため | 高リスク情報なので根拠がない場合は空欄のまま要監修 |

### 7.1 微生物claimの構造

- TaxonomyClaim：rank、taxon_name、assertion
- MorphologyClaim：observation_method、shape、arrangement、staining_result、assertion
- GrowthRequirementClaim：factor_name、condition、assertion
- CultureMediumClaim：medium_name、incubation_conditions、expected_growth、assertion
- ColonyCharacteristicClaim：medium_name、incubation_conditions、colony_finding、assertion
- IdentificationTestClaim：test_name、expected_result、interpretation、assertion
- VirulenceFactorClaim：factor_name、effect、assertion
- ToxinClaim：toxin_name、toxin_type、major_effect、assertion
- DiseaseAssociationClaim：disease_name、disease_knowledge_id、relation、assertion
- DiagnosticSpecimenClaim：specimen、collection_site、conditions、assertion
- DetectionMethodClaim：method_name、target、expected_result、assertion
- ResistanceClaim：resistance_name、mechanism、affected_agent_classes、assertion
- MicroorganismTransmissionClaim：route、source、entry_site、assertion
- InfectionControlClaim：measure、target_or_situation、assertion

カタラーゼ、コアグラーゼなどはmechanismsへ入れず、identification_testsへ保存する。毒素と薬剤耐性も別配列にする。

## 8. 寄生虫テンプレート

template_id：parasite_v1.0

parasite_groupでprotozoan、nematode、cestode、trematode、arthropod、otherを区別する。

| 項目 | 区分 | 役割 | 保存理由 | 空欄を許容する条件 |
|---|---|---|---|---|
| parasite_group | 必須 | 原虫・線虫・条虫・吸虫などを区別 | 生活環・形態のルールを切り替えるため | 許容しない |
| taxonomy | 必須 | 分類学的位置 | 類似寄生虫との整理に使うため | 少なくとも主要分類1件が必要 |
| hosts | 必須 | 終宿主、中間宿主、保虫宿主など | 生活環をPublisherが直接扱うため | 中間宿主が不要な場合でも終宿主は必要 |
| vectors | 条件付き必須 | 媒介動物 | 媒介と宿主を混同しないため | 媒介動物を必要としない場合 |
| habitats | 必須 | 寄生部位・発育部位 | 検体と症状の理解に使うため | 許容しない |
| life_cycle_steps | 必須・最重要 | 発育段階と遷移順序 | 生活環図を意味解釈なしで作れるようにするため | 許容しない |
| infective_stages | 必須 | ヒトなど対象宿主への感染型 | 国家試験頻出情報だから | 許容しない |
| diagnostic_stages | 必須 | 検体中で検出する生活期 | 検査法と直接結び付けるため | 許容しない |
| transmission_routes | 必須 | 経口、経皮、媒介など | 感染型と侵入経路を分離するため | 許容しない |
| morphology | 必須 | 虫卵、幼虫、成虫、栄養型などの形態 | 顕微鏡・鑑別問題に使うため | 許容しない |
| specimens | 必須 | 検査材料、採取時期、条件 | 診断型と採取法を結ぶため | 許容しない |
| diagnostic_methods | 必須 | 鏡検、集卵、抗原、核酸など | 検査技師国家試験の中心情報だから | 許容しない |
| clinical_findings | 任意・推奨 | 主要症状・病態 | 疾患Knowledgeが未作成でも最低限の関係を保つため | 無症候性が中心の場合 |
| prevention | 任意 | 感染予防の医学的事実 | 公衆衛生・研修へ利用するため | 根拠未確認時は空欄 |
| epidemiology | 任意 | 地域、流行、リスク集団 | 地域性が重要な寄生虫に使うため | 国家試験上の関連が低い場合 |

### 8.1 寄生虫claimの構造

- TaxonomyClaim：rank、taxon_name、assertion
- HostClaim：host_role、host_name、host_knowledge_id、assertion
- VectorClaim：vector_name、vector_knowledge_id、transmitted_stage、assertion
- HabitatClaim：life_stage、host_name、anatomical_site、assertion
- LifeCycleStepClaim：step_order、stage_name、host_name、location、transition、assertion
- InfectiveStageClaim：stage_name、target_host、entry_route、assertion
- DiagnosticStageClaim：stage_name、specimen、assertion
- TransmissionClaim：route、source、entry_site、assertion
- ParasiteMorphologyClaim：life_stage、observation_method、size、shape、distinctive_features、assertion
- ParasiteSpecimenClaim：specimen、collection_timing、collection_conditions、assertion
- ParasiteDiagnosticMethodClaim：method_name、target_stage、expected_finding、assertion
- ParasiteClinicalFindingClaim：finding_name、assertion
- PreventionClaim：preventive_measure、assertion
- EpidemiologyClaim：population_or_region、epidemiologic_fact、assertion

生活環のstep_orderは動画の演出順ではなく、生物学的な発育順序である。したがって医学的事実としてKnowledge JSONへ保存できる。

## 9. 染色法テンプレート

template_id：staining_method_v1.0

細菌染色、血液染色、病理染色などを同じ基本構造で扱い、対象構造、原理、試薬、工程、結果を明確に分離する。

| 項目 | 区分 | 役割 | 保存理由 | 空欄を許容する条件 |
|---|---|---|---|---|
| purposes | 必須 | 染色の目的 | 適用場面を直接取得するため | 許容しない |
| target_structures | 必須 | 細胞壁、核、糖質などの対象 | 原理と判定を結ぶため | 許容しない |
| applicable_specimens | 必須 | 喀痰、組織、塗抹など | 検体・標本条件を明示するため | 許容しない |
| fixation_requirements | 条件付き必須 | 熱固定、アルコール固定など | 染色前処理を工程から独立させるため | 固定不要の方法では適用外 |
| staining_principles | 必須・最重要 | 化学的・構造的原理 | 暗記ではなく理由を扱うため | 許容しない |
| reagents | 必須 | 試薬名と役割 | 操作手順と試薬を結ぶため | 許容しない |
| procedure_steps | 必須・最重要 | 医学的に定義された操作順 | 研修動画・PDFで共通利用するため | 許容しない |
| result_interpretations | 必須 | 対象、色、判定 | 結果を文章解析せず取得するため | 許容しない |
| quality_controls | 任意・推奨 | 対照と期待結果 | 精度管理教材に使うため | 標準的対照が定義できない場合 |
| error_causes | 必須 | 過染色、脱色、固定不良など | 誤判定防止と国家試験問題に使うため | 許容しない |
| limitations | 必須 | 適用限界、染まりにくい対象 | 誤った一般化を防ぐため | 許容しない |
| safety_considerations | 任意 | 試薬・検体の安全事項 | 研修教材へ利用するため | 根拠確認前は空欄 |
| related_methods | 任意 | 類似・代替染色法 | 比較学習に使うため | 関連法がない場合 |

### 9.1 染色法claimの構造

- PurposeClaim：use_case、assertion
- TargetStructureClaim：target_name、target_kind、assertion
- ApplicableSpecimenClaim：specimen、preparation、assertion
- FixationClaim：fixative_or_method、conditions、assertion
- StainingPrincipleClaim：mechanism、affected_target、resulting_effect、assertion
- ReagentClaim：reagent_name、reagent_role、assertion
- ProcedureStepClaim：step_order、action、reagent_claim_ids、duration、conditions、assertion
- ResultInterpretationClaim：target_name、observed_color_or_pattern、interpretation、assertion
- QualityControlClaim：control_material、expected_result、assertion
- ErrorCauseClaim：error_type、cause、observed_effect、assertion
- LimitationClaim：scope_or_target、limitation、assertion
- SafetyConsiderationClaim：hazard_or_situation、safe_handling_fact、assertion
- RelatedMethodClaim：method_name、method_knowledge_id、relation_type、assertion

色は表示デザインではなく観察される医学的結果なので保存する。一方、PDFで何色の見出しを使うか、動画でどの順に見せるかは保存しない。

## 10. 必須・任意・空欄の共通判定

Version 1.0では項目を次の4段階で管理する。

| 区分 | Schema | Completeness | 空欄 |
|---|---|---|---|
| Critical Required | キー必須 | 不足時は重大欠落、最終スコア上限49 | 原則不可 |
| Required | キー必須 | 不足時は減点、最終スコア上限79 | 条件付き適用外のみ |
| Recommended Optional | キー必須、空配列可 | 不足時は小幅減点、スコア上限制限なし | 許容 |
| Optional | キー必須、空配列可 | 得点対象外 | 許容 |

Schemaはキーと型を確認し、Completenessは配列内の有効claim数、必要な属性、出典、条件付き必須を確認する。

単にclaim数を増やしても得点は増えない。各requirementに設定したtarget_countまでを評価し、重複・同義反復は1件として扱う。

## 11. Category Completeness Score

### 11.1 目的

Category Completeness Scoreは「JSONの形が正しいか」ではなく、「臨床検査技師国家試験の教材へ進めるために必要な種類の情報が揃っているか」を0〜100で示す。

このスコアが評価しないもの：

- 医学的正しさ
- 出典内容とclaimの一致
- 医学監修の完了
- 文章の読みやすさ
- PDFや動画の完成度
- 公開可否

### 11.2 基本配点

| 評価領域 | 配点 |
|---|---:|
| カテゴリ固有の医学的事実 | 75 |
| claimへの出典付与 | 15 |
| 国家試験メタデータ | 10 |
| 合計 | 100 |

カテゴリ固有部分は各テンプレートの評価プロファイルで配点する。出典15点は、得点対象claimのうち承認可能な出典へ結び付いた割合で計算する。国家試験10点はpriority_claim_ids、重要度、キーワード、過去問・頻度情報の充足率で計算する。

国家試験頻出ポイントは新しい説明文章として保存しない。exam_metadata.priority_claim_idsへ、重要な医学的事実のclaim_idを登録する。

### 11.3 採点式

~~~text
requirement_coverage =
  min(有効な非重複claim数 / target_count, 1.0)
  × 必須属性の充足率

category_points =
  Σ(requirement_weight × requirement_coverage)

completeness_score =
  category_points
  + evidence_points
  + exam_metadata_points
~~~

小数は内部では保持し、表示時に整数へ四捨五入する。

### 11.4 不足による減点と上限

- Critical Requiredが1つでも不足：不足項目の配点を失い、最終スコアを49以下に制限
- Requiredが1つでも不足：不足項目の配点を失い、最終スコアを79以下に制限
- Recommended Optionalが不足：その項目の小配点だけを失い、上限は設けない
- Optionalが不足：減点しない
- 未確認claim、空文字、重複claim：有効claimとして数えない
- 出典なしclaim：カテゴリ内容点は得られるが出典点は得られない
- 国家試験分析未実施：医学的事実点は得られるが国家試験点は得られない

### 11.5 スコアレベル

| スコア | レベル | 意味 |
|---:|---|---|
| 90〜100 | complete_for_review | 医学レビューへ渡せる情報量 |
| 75〜89 | mostly_complete | 主情報はあるが補完が必要 |
| 50〜74 | incomplete | 教材利用前に重要項目の追加が必要 |
| 0〜49 | critically_incomplete | カテゴリ専用情報が大きく不足 |

90点以上でも医学監修・承認済みを意味しない。

## 12. カテゴリごとの評価配点

すべて「カテゴリ75点＋出典15点＋国家試験10点」とする。

### 12.1 疾患・病態

| 評価項目 | 点 |
|---|---:|
| 定義・condition_kind | 5 |
| 病因・誘因 | 8 |
| 病態生理 | 10 |
| 臨床所見 | 5 |
| 検査所見 | 15 |
| 形態所見 | 8 |
| 診断検査 | 10 |
| 鑑別疾患 | 6 |
| 合併症 | 3 |
| 関連病態・リスク因子 | 5 |
| 小計 | 75 |

### 12.2 微生物

| 評価項目 | 点 |
|---|---:|
| 分類・organism_group | 5 |
| 形態・染色性 | 8 |
| 発育条件 | 6 |
| 培地・集落性状 | 10 |
| 同定試験 | 12 |
| 病原因子・毒素 | 8 |
| 代表疾患 | 8 |
| 検体・検出法 | 10 |
| 薬剤耐性 | 5 |
| 感染経路・感染対策 | 3 |
| 小計 | 75 |

### 12.3 寄生虫

| 評価項目 | 点 |
|---|---:|
| 分類・parasite_group | 5 |
| 宿主・媒介動物 | 8 |
| 寄生部位 | 4 |
| 生活環 | 14 |
| 感染型 | 8 |
| 診断型 | 8 |
| 感染経路 | 7 |
| 形態 | 8 |
| 検体・診断法 | 9 |
| 臨床所見・予防 | 4 |
| 小計 | 75 |

### 12.4 染色法

| 評価項目 | 点 |
|---|---:|
| 目的 | 5 |
| 対象構造 | 5 |
| 検体・固定 | 8 |
| 染色原理 | 12 |
| 試薬 | 10 |
| 操作工程 | 15 |
| 結果判定 | 10 |
| 精度管理 | 5 |
| エラー原因・限界 | 5 |
| 小計 | 75 |

## 13. Completeness Validation

### 13.1 Schema Validationとの違い

~~~text
Schema Validation
  → キー、型、列挙値、ID参照が正しいか

Completeness Validation
  → カテゴリに必要な情報の種類と量が揃っているか

Medical Review
  → 医学的に正しいか、出典と一致するか
~~~

例：

~~~text
Schema OK
Completeness 38%
Critical missing:
- identification_tests
- diagnostic_specimens
- detection_methods
~~~

この状態はJSONとして保存できるが、教材制作へは進めない。

### 13.2 評価プロファイル

評価ルールはカテゴリごとにVersion付きプロファイルとしてMedical Knowledge Engineが管理する。

~~~text
profile_id: completeness.microorganism
profile_version: 1.0
template_id: microorganism_v1.0
requirements:
  - requirement_id
  - json_path
  - label
  - severity
  - weight
  - minimum_count
  - target_count
  - required_attributes
  - applicability_condition
  - evidence_required
~~~

新カテゴリを追加する場合は、Schema検証エンジンや採点式を変更せず、新しいtemplate_idと評価プロファイルを追加する。

### 13.3 条件付き必須

例：

- microorganism.organism_groupがbacteriumで培養可能ならculture_mediaを必須にする
- microorganismが毒素非産生ならtoxinsを適用外にできる
- parasiteが直接生活環ならintermediate_hostを適用外にできる
- staining_methodが固定不要ならfixation_requirementsを適用外にできる
- disease_conditionで形態所見が試験範囲にない場合、morphologic_findingsを適用外にできる

適用外の配点は、同じカテゴリ内の他の必須項目へ比率で再配分する。適用外を利用して得点を不当に上げないよう、評価プロファイルに事前定義された条件だけを認める。

## 14. 改善レポート

Completeness Validationは点数だけでなく、AI、開発者、医学監修者が次に行う作業を判断できるレポートを返す。

### 14.1 レポート項目

| 項目 | 内容 |
|---|---|
| assessment_id | 評価結果ID |
| knowledge_id / content_revision | 評価対象 |
| profile_id / profile_version | 使用した採点基準 |
| evaluated_at / evaluation_engine_version | 評価日時と評価エンジン版 |
| schema_status | Schema結果 |
| completeness_score | 0〜100 |
| completeness_level | 4段階評価 |
| requirement_results | 各項目の配点、獲得点、状態 |
| missing_required | 必須不足 |
| missing_recommended | 推奨不足 |
| not_applicable | 適用外と理由 |
| evidence_gaps | 出典がないclaim |
| exam_metadata_gaps | 国家試験対応不足 |
| improvement_actions | 改善候補、優先度、担当候補 |

### 14.2 改善候補の担当

| 担当候補 | 対象 |
|---|---|
| AI | 与えられた承認済み根拠に該当情報があるが、構造化されていない |
| 開発者 | JSONパス、変換、列挙値、ID参照、評価ルールの技術的不具合 |
| 医学監修者 | 適用外判断、資料間矛盾、数値、診断、耐性、感染対策などの判断 |
| コンテンツ所有者 | 国家試験上の優先度、対象範囲、教材へ含める方針 |

改善レポートはAIへ「不足を自由に埋める」よう指示しない。まず必要な出典を確認し、根拠が与えられた場合だけ構造化する。

KnowledgeRecordのcontent_revision、evidence、exam_metadata、評価プロファイルのいずれかが変わった場合は再評価する。古いcontent_revisionに対するスコアを現在のレコードへ流用しない。

改善例：

~~~text
改善候補
- [Critical][医学監修者] 同定試験不足
- [Required][AI] 承認済み資料に記載された培地情報の構造化
- [Required][コンテンツ所有者] 国家試験優先claim未設定
- [Evidence][医学監修者] 薬剤耐性claimの主根拠不足
~~~

## 15. JSON設計サンプル

次のファイルはVersion 1.0の構造を確認するための設計例であり、Schema実装済みデータでも医学監修済みデータでもない。

- examples/knowledge-json-v1.0/disease-condition.example.json
- examples/knowledge-json-v1.0/microorganism.example.json
- examples/knowledge-json-v1.0/parasite.example.json
- examples/knowledge-json-v1.0/staining-method.example.json
- examples/knowledge-json-v1.0/completeness-assessment.example.json

## 16. Version 0.3からの移行原則

Version 1.0はcategory_contentの意味を明確化するためのメジャー変更であり、Version 0.3をその場で書き換えない。

1. Version 0.3は読取可能な旧契約として保存する
2. core_facts.definitionsは、医学的意味が同じ場合にclaim_idを維持して移行する
3. core_facts.mechanismsとcharacteristicsは、内容を疾患・微生物・寄生虫・染色法の専用欄へ分類する
4. 1つの旧claimに複数事実が含まれる場合は、複数の新claimへ分割する
5. 分割したclaimには新しいclaim_idを発行し、ID Registryへ派生関係を記録する
6. 自動分類結果は医学レビューなしで正本にしない
7. 移行前後のclaim数、参照、出典、Publisher優先指定を比較する
8. Version 1.0のCompleteness Validationを通し、不足レポートを残す

generic_facts_v0.3から専用テンプレートへの移行は、文章の移動ではなく医学的意味の再分類である。したがって、完全自動移行ではなく、AIによる候補分類と人の確認を組み合わせる。

## 17. Version 2以降で検討する項目

| 将来候補 | Version 1.0へ入れない理由 |
|---|---|
| ICD、LOINC、SNOMED CT、NCBI Taxonomyなどの外部コード | ライセンス、国内運用、更新責任を先に決める必要がある |
| 全カテゴリ横断の医学Knowledge Graph | relation_typeが増えすぎる前に4カテゴリの実利用を確認する必要がある |
| claim単位の有効期間・地域・対象集団 | ガイドライン差や時点差を扱う運用がまだない |
| 多言語の正本claim | 当面は日本の国家試験向けであり、翻訳を医学的事実と混在させないため |
| 顕微鏡画像・標本領域のアノテーション | 画像権利、保存、レビューを別設計にする必要がある |
| 抗菌薬ブレイクポイントの版別テーブル | 更新頻度と高リスク性が高く、専用データ契約が必要 |
| 遺伝子変異・分子異常の詳細モデル | 対象範囲が大きく、まず国家試験上の必要性を評価するため |
| 確率付き因果関係・診断性能の統計モデル | 感度・特異度などの条件と出典を厳密に扱う別設計が必要 |
| 学年・習熟度別の知識プロファイル | 医学的事実ではなく利用方針なので、Knowledge Use Profile側で扱うべき |
| claim廃止・統合・分割の履歴台帳 | Knowledge JSON本体ではなくID Registry・監査層で管理すべき |

次の項目はVersion 2以降にもKnowledge JSONへ入れない。

- PDFレイアウト
- note本文
- 動画台本・演出
- 国家試験問題文・選択肢・解説
- 語呂合わせ
- AIプロンプトとモデル実行履歴
- 医学レビュー・承認ワークフロー
- 患者個別の診断・治療推奨

## 18. Version 1.0へ進む前の設計判断

実装前にプロダクトオーナーが決める事項：

1. 4カテゴリの必須・任意項目が国家試験教材として妥当か
2. 詳細な治療情報を必須にしない方針でよいか
3. 完全性スコアへ出典15点、国家試験メタデータ10点を含めるか
4. 教材制作へ進める最低スコアを何点にするか
5. 条件付き適用外を誰が承認できるか

Codexが実装時に技術的に決める事項：

- JSON Schema Draft 2020-12での表現
- 型、列挙値、最大件数、参照整合性
- 評価プロファイルの読込方法
- ID Registryとの接続境界
- 契約テスト、移行テスト、回帰テスト

## 19. 今回変更しないもの

- Knowledge Workbench
- OpenAI接続
- AIプロンプト
- Version 0.3 Schemaとモデル
- PDF Publisher
- note Publisher
- TrainingVideo
- NationalExam
- 出典自動取得
- 医学レビュー・承認
- 画面

本設計が承認されるまで、Version 1.0 Schema実装とAIプロンプト変更へ進まない。
