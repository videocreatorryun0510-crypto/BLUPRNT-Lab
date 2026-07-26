# knowledge-contracts

BLUPRNT Labの各システムが共通利用する、版付きKnowledge JSON契約です。このパッケージには画面、AI接続、PDF生成などを入れません。

## 提供する版

- **Version 0.2**：移行前データを読むために残す旧プロトタイプ契約
- **Version 0.3**：既存カテゴリとOpenAI出力を保持する移行元契約
- **Version 1.0**：旧検査項目と正式`staining_method`、`specimen`、`reagent`、`biological_structure`、`disease`、`laboratory_test_item` Categoryを持つCategory Union契約
- **Exam Metadata Version 1.0**：Knowledge JSONへIDで紐付く独立した国家試験情報契約
- **Exam Import Version 1.0**：CSVとExam Metadataの間で使う正規化レコード、検証、差分レポートの契約
- **Knowledge Registry Version 1.0**：Knowledge・Claimの安定ID、意味キー、版、状態、承認、別名、変更履歴を管理する台帳契約
- **Approval Contract Version 1.0**：承認状態、差し戻し可能な遷移、公開・外部AI送信可否を共有する契約
- **Disease Relation Vocabulary Version 1.0**：疾患から他Knowledgeへ向かうRelation Typeの意味、方向、Category範囲を管理する契約
- **Knowledge Relation Version 1.2**：1.0／1.1を不変に保ちながらDisease Relation Vocabulary 7語を追加した将来Relation契約

Version 0.2とVersion 0.3は削除せず、既存データの読込とVersion 1.0への段階的移行に使用します。Version 1.0が対応するカテゴリは`test_item`、`staining_method`、`specimen`、`reagent`、`biological_structure`、`disease`、`laboratory_test_item`です。`test_item`はAST・HbA1cの既存AI生成経路、`laboratory_test_item`はPhase 5.11からの正式Knowledge Categoryです。両者は移行期間だけ並存し、量産前に統合方針を確定します。

```python
from knowledge_contracts.v10 import (
    KnowledgeRecord,
    evaluate_biological_structure_completeness,
    evaluate_disease_completeness,
    evaluate_knowledge_completeness,
    evaluate_laboratory_test_item_completeness,
    evaluate_reagent_completeness,
    evaluate_specimen_completeness,
    evaluate_staining_method_completeness,
    evaluate_test_item_completeness,
    knowledge_record_json_schema,
    validate_knowledge_record,
)

from knowledge_contracts.exam_v10 import (
    ExamMetadataRecord,
    evaluate_exam_completeness,
    validate_exam_metadata_for_knowledge,
)

from knowledge_contracts.registry_v10 import (
    RegistrySnapshot,
    RegistryStatus,
    validate_registry_snapshot,
)

from knowledge_contracts.approval_v10 import (
    ApprovalGateAction,
    approval_contract,
    evaluate_approval_gate,
)

from knowledge_contracts.relation_v12 import (
    RelationType,
    disease_relation_vocabulary,
)
```

## Version 1.0 MVPの原則

- Knowledge JSONは医学的事実と出典を保持する
- 国家試験情報は独立したExam Metadataとして`knowledge_id`と`claim_id`で結ぶ
- 語呂合わせ、完成文章、図解、動画台本、問題本文などは保存しない
- 医学的事実を`claim_id`付きの小さな単位として管理する
- 出典は`claim_id`を参照し、どの事実を支えるかを明示する
- Publisherは本文ではなく、優先利用する`claim_id`だけを保持する
- Knowledge Schema、Exam Metadata Schema、2種類のCompletenessを分離する
- 空欄を許容してSchemaを通し、不足は完全性スコアと改善候補で示す

旧`test_item`では、検査目的、検体、測定方法、測定原理、標準化、報告方式、基準範囲、高値・低値、干渉物質、解釈上の注意などを別々の事実として保持します。正式`laboratory_test_item` MVPでは、定義、概要、測定対象、臨床的意義、高値・低値の病態、主な測定法、出典に限定しています。染色法では、目的、対象構造、標本、固定法、染色原理、試薬、工程、判定、精度管理、誤りの原因、限界、関連法を保持します。検体・標本では概要、用途、採取・作製、保存、注意を、試薬では用途、使用対象、使用工程、注意、保管を別々の事実として保持します。生体構造MVPでは概要、主な機能、主な構成要素、存在する生物を保持します。疾患MVPでは概要、病態、原因、症状、主な検査所見、鑑別、国家試験で優先するClaim参照を保持します。微生物・寄生虫等は未実装です。

Version 0.3の設計とSchema例も移行履歴として残しています。自動テスト用データとOpenAI出力はいずれも医学監修前であり、承認済み医学知識ではありません。

Exam Metadata Version 1.0は、出題履歴をCSVの1行へ対応する`source_row_id`単位で保持します。現在のAST・HbA1cデータは`manual_dummy`であり、実際の国家試験出題実績として使用できません。

Exam Import Version 1.0は、CSV列名を直接Exam Metadataへ持ち込みません。列名Mapping後の`NormalizedExamRecord`、Knowledge・claim関連付け後の`MappedExamRecord`、Import Validation・差分・画像関連付け件数を共通契約として提供します。画像はJSONへ埋め込まず、版・ハッシュ付きファイル参照だけをExam Metadataへ保存します。

Knowledge JSON Version 1.0内の旧`exam_metadata`欄はVersion 0.3互換のため空のまま残しています。新規機能は独立したExam Metadata Version 1.0を正として利用し、次回のKnowledge JSONメジャー更新時に旧欄を廃止します。

Knowledge Registry Version 1.0では、`claim_key`を`ast.ifcc`のような意味で固定される公開キー、`claim_id`を保存先内部で利用する不透明なIDとして扱います。JSON配列の順番やAIの生成順はID決定に使いません。Registry SchemaはID・キーの重複、別名の循環、KnowledgeとClaimの版整合性、履歴の参照整合性を検証します。

Phase 2.8では`ClaimMergeRedirect`を追加しました。統合元Claimは`deprecated`として残し、統合先の`claim_id`は作り直しません。Schemaは重複、孤立Claim、Version逆転、History欠落、deprecated参照、統合循環、統合先欠落を検出します。文章類似による候補は人の判断を助けるだけで、自動統合しません。

Approval Contract Version 1.0は`draft → owner_review → medical_review → approved → published`
を正式経路とし、隣接段階への差し戻しも履歴付きで許可します。`deprecated`は承認段階では
なくRegistry互換の廃止状態です。公開と外部AI送信は`approved`だけを許可します。
