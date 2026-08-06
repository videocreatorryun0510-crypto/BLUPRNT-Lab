# Medical Review Governance Version 1.0

- Phase: 5.21
- Status: Product Owner approval pending
- Effective date: 未定
- Owner: BLUPRNT Lab Product Owner
- Related policy: [医学情報ルール](medical_rules.md)

## 1. 目的

この文書は、BLUPRNT LabのKnowledge、Claim、Relation、Exam Metadataについて、誰が、何を、どの基準で確認し、どの状態へ進めるかを定義する。対象は医療教育用Knowledgeであり、個別患者の診断・治療判断ではない。

`approved`は、AI生成、Schema Validation成功、Completeness 100%を意味しない。定義済みの医学レビュー基準を人が満たしたと判断し、操作者、日時、根拠、対象Version、Review Decisionを記録した状態だけを意味する。

```text
Schema / Completeness / 整合性検査
                  │ Systemによる機械検査
                  ▼
draft → owner_review → medical_review → approved → published（将来）
          │                │               │
     Product Owner    Medical Reviewer  Final Approver
```

## 2. 基本原則

1. Systemは医学的承認をしない。
2. AI、Completeness、Schema ValidationはReviewerの補助であり、承認者ではない。
3. 承認は特定のKnowledge Version、Claim Version、Evidence、Checklist Versionへ固定する。
4. 医学的意味が変わればKnowledge Versionを上げ、再レビューする。
5. 同じ本文を再確認した場合もReview Versionと履歴を増やす。
6. 根拠不足、矛盾、期限超過は隠さず、利用停止理由として残す。
7. Knowledge、Claim、Relation、Exam Metadata、Artifactの承認は相互に代用しない。
8. 下書き作成者と医学承認者の役割を記録する。Production運用では同一人物による自己完結を標準にしない。
9. 現在の自由入力による操作者名だけでは、正式な本人確認とみなさない。
10. 承認済み情報の変更、失効、差し戻しは削除せず、履歴と現在の利用可否を分けて管理する。

## 3. Review Role Matrix

### 3.1 Roleの責務

| Role | 主な責務 | できないこと |
|---|---|---|
| Author / Editor | 下書き作成、Claim分割、出典登録、指摘修正 | `approved`への最終移行、自分の執筆だけを根拠に医学承認 |
| Product Owner | 利用目的、国家試験範囲、対象者、情報量、教育上の優先順位を確認し`owner_review`へ進める | 医学的正確性の最終承認 |
| Medical Reviewer | 医学的内容、用語、数値、検査法、病態、適用範囲、Claim粒度、出典との一致を確認する | 教育目的や事業判断だけを根拠に承認 |
| Final Approver | 全Criteria、Review記録、未解決指摘を確認し`approved`を決定する | Criteria未達の黙認、Reviewer不明の承認 |
| System | Schema、Completeness、Version、Fingerprint、参照切れ、重複、矛盾候補、Stale、期限を機械検査する | 医学的妥当性の判断、出典内容の最終解釈 |

MVPではMedical ReviewerとFinal Approverを同一人物にできる。ただし`roles_performed`へ両Roleを明示し、本人確認済みID、資格・専門領域、利益相反、判断理由を残す。高リスク情報では分離を推奨する。

### 3.2 操作権限の基準案

| 操作 | Author / Editor | Product Owner | Medical Reviewer | Final Approver | System |
|---|:---:|:---:|:---:|:---:|:---:|
| draft作成・修正 | ○ | ○ | ○ | ○ | × |
| owner_review移行 | × | ○ | × | ○ | × |
| 医学レビュー記録 | × | × | ○ | ○ | 検査結果のみ |
| Claimのmedical_review完了 | × | × | ○ | ○ | × |
| Claim / Knowledgeのapproved移行 | × | × | 条件付き | ○ | × |
| 差し戻し・根拠不足判定 | ○ | ○ | ○ | ○ | 候補提示 |
| Review期限・Stale判定 | × | × | 判断 | 判断 | ○ |

「条件付き」は、MVPでMedical ReviewerがFinal Approverも兼任する場合だけを指す。

### 3.3 Medical Reviewerの資格想定

| 対象 | 推奨Reviewer |
|---|---|
| 検査項目、染色法、検体、試薬、分析装置、精度管理 | 対象領域の実務経験を持つ臨床検査技師。診断基準や治療へ踏み込むClaimは医師を追加 |
| 疾患、診断、治療、予後 | 当該領域の医師、またはその領域を正式に監修できる医療専門職。治療関連は原則として医師 |
| 公衆衛生、法令、制度 | 該当制度の専門家と医療Reviewer。法的判断が必要なら法務確認を追加 |
| 国家試験範囲・教育優先度 | 臨床検査技師国家試験教育の経験者。ただし医学的事実の承認は別に行う |

資格名だけで自動承認せず、対象領域、実務経験、所属、資格確認日、利益相反をReviewer Profileへ記録する設計とする。

## 4. Review Scope

### 4.1 Knowledge Review

Knowledge全体について次を確認する。

- Categoryが適切で責務が重複していない
- 定義、概要、対象範囲が整合している
- Category必須項目が揃っている
- 全active Claimが現在のKnowledge Versionに属する
- Claim、Evidence、Relation候補の全体に重大な矛盾がない
- 対象者と利用目的に対して過不足がない
- 最新版、Review期限、地域・測定法・製品の適用範囲が明確である

Knowledge Reviewは、内部の一部Claimだけを承認してKnowledge全体を`approved`にする手段ではない。Knowledgeを`approved`へ進める時点では、現在版に含まれる全active Claimが承認済みでなければならない。未採用Claimは削除せず、次Versionで除外または`deprecated`として理由を残す。

### 4.2 Claim Review

1 Claimごとに次を確認する。

- 1つの独立した医学的事実だけを表す
- 主語、対象、条件、例外、時点、地域が必要な範囲で明示される
- 断定の強さが根拠より強くない
- Evidenceの具体的箇所がClaimを直接支持する
- 他Claimとの重複、矛盾、包含関係が整理される
- Claim ID、Claim Key、Claim Versionが現行である
- 時点依存情報では有効期間と再確認日がある

Claim Reviewの結果はClaimごとに保存する。Knowledge Reviewの一括コメントだけで代用しない。

### 4.3 Relation Review

RelationはKnowledge本文と独立した資産として、次を確認する。

- Relation Typeが固定Vocabularyに存在する
- SourceとTargetの方向が定義どおりである
- Target Knowledge IDが現行である
- ContextがRelationの利用条件として適切である
- 根拠Claimがapprovedかつ現行である
- Relation Version、Status、Redirectが整合する

Relation承認はKnowledge承認と独立する。KnowledgeがapprovedでもRelationはdraftになり得る。PublisherやRendererがRelationを利用する将来Phaseでは、利用するRelationの承認も別Gateで確認する。

### 4.4 Exam Metadata Review

Exam Metadataは医学Knowledge承認と独立して、次を確認する。

- 実CSVまたは真正な原資料に基づく
- 試験回、年度、午前午後、問題番号が原資料と一致する
- 問われたClaim IDが現行である
- 出題パターン、関連語、誤答情報が元データから追跡できる
- Importance Scoreの計算式Versionと入力期間が固定される
- Import Batch、Source File、Source Row IDが記録される
- 画像問題ではImage IDと原問題の対応が確認される

Exam Metadataの未承認はKnowledgeの医学的承認を妨げない。ただし、Exam Metadataを掲載する教材ではExam Metadata承認を別途必須とする。

## 5. Approval Criteria

### 5.1 Knowledgeをapprovedへ進める共通必須条件

| 分類 | 必須条件 |
|---|---|
| 構造 | Schema Validation OK。Category ProfileのCompleteness閾値以上。全blocker項目が充足 |
| Claim | 現在版の全active Claimが個別レビュー済み、Final Approverによりapproved、Version現行 |
| Evidence | 必須Claimに直接Evidenceがあり、参照箇所・実在・適用範囲を確認済み |
| 整合性 | 重大な矛盾、重複、未解決deprecated参照、Redirect不整合がない |
| Version | Knowledge VersionがRegistry最新版。Content Fingerprint固定。独立Review Versionが対象版へ固定 |
| 人 | ReviewerとFinal Approverの本人ID・Role・専門領域が記録される |
| 判断 | Review Decisionが`approved`。Review Comment、日時、Checklist版、Evidence Policy版が記録される |
| 時点 | 期限超過がなく、jurisdiction、method/product scope、review_due_atが必要箇所で設定される |
| 監査 | 差し戻し、条件、例外、利益相反を含む履歴が追記方式で保存される |

### 5.2 Category Completeness基準案

Completenessは「欄が揃っているか」の機械評価で、医学的品質の点数ではない。閾値を超えても人のレビューを省略できない。

| Category | Phase 5.21推奨閾値 | 追加条件 |
|---|---:|---|
| `staining_method` | 100% | 定義、目的、対象構造、固定、試薬、工程、判定、QC、限界、出典のblockerがすべてpass |
| `disease` | 90%以上 | 定義、病態、主な検査所見、出典は100%。欠けた任意項目はReview Commentで理由記録 |
| `laboratory_test_item` | 90%以上 | 定義、測定対象、臨床的意義、出典は100%。測定法はscopeと時点を確認 |

本基準はPilot用の提案であり、Product Owner承認後にChecklist Version 1.0の正式値とする。

### 5.3 自動判定と人の判断の境界

Systemが検査できるのは、存在、形式、Version、参照、期限、機械的矛盾候補までである。「この出典がこのClaimを医学的に支持するか」「例外を省略してよいか」はMedical Reviewerが判断する。

## 6. Evidence Policy Version 1.0

### 6.1 Evidence Level

| Level | 主な資料 | 使用方針 |
|---|---|---|
| A | 日本の公的機関、国内学会ガイドライン、標準法、法令・公的基準、承認済み添付文書 | Critical Claimの主根拠として優先 |
| B | 国際学会、WHO、CDC、査読済み総説、標準的教科書 | Aがない領域の主根拠またはAの補助 |
| C | 原著論文、海外教科書、信頼できる教育資料 | 限定的・新規・補助的情報。単独で標準事項を確定しない |

Evidence Levelは既存`source_priority_rank`と同じ意味ではない。Rankは情報取得順、Levelは特定Claimに対する権威性・適用性・直接性を人が評価した結果である。

原則としてEvidenceに使用しないもの：出典不明サイト、AI回答、個人ブログ、二次転載だけのページ、根拠箇所を確認できないまとめ記事。

### 6.2 Claim重要度別の最低要件

| Claim種別 | 最低要件 |
|---|---|
| Critical | 適用可能なLevel Aを1件以上。存在しない場合はLevel Bを複数確認し、`insufficient_evidence`または例外判断をFinal Approverが記録 |
| Required | Level AまたはBを1件以上。Claimを支持する具体的な章・ページ・節・表等を記録 |
| Optional | Level BまたはCを許容。ただし教材へ掲載するならClaim Reviewは必須 |

数値、基準範囲、診断基準、検査法、法令、添付文書、製品依存情報は原則Criticalとして扱う。

### 6.3 Evidence Reviewの必須記録

- Evidence ID、版、発行元、発行年、URL/DOI/PMID等
- 実在確認日、アクセス可否
- 支持するClaim IDとClaim Version
- 具体的な根拠位置
- Evidence Levelとprimary/supportingの役割
- jurisdiction、対象集団、method/product scope
- `supports`、`partially_supports`、`conflicts`、`does_not_support`の判定
- Reviewer、確認日時、コメント

`partially_supports`だけのClaimはそのまま承認せず、Claimの限定、追加Evidence、または`insufficient_evidence`を選ぶ。

## 7. Time-sensitive Information Policy

### 7.1 対象

- 基準範囲、単位、測定法、試薬・装置・製品情報
- 診療・検査ガイドライン、標準法、法令、通知
- 国家試験出題基準、添付文書、施設SOP
- 制度、推奨、診断基準など改訂で意味が変わる情報

### 7.2 必須属性案

| 項目 | 意味 |
|---|---|
| `valid_from` / `valid_until` | 情報または資料の適用期間 |
| `reviewed_at` / `review_due_at` | 最終確認と次回確認期限 |
| `jurisdiction` | 日本、国際、施設等の適用地域 |
| `method_or_product_scope` | 測定法、装置、試薬、製品、施設SOPの範囲 |
| `temporal_class` | `stable`、`periodic`、`event_driven` |
| `superseded_by` | 後継EvidenceまたはReviewへの参照 |

### 7.3 推奨Review期限

| 情報 | 推奨期限 |
|---|---|
| 法令、ガイドライン、出題基準、添付文書、製品依存情報 | 12か月、または改訂通知時の早い方 |
| 基準範囲、単位、測定法、施設研修情報 | 12か月、または方法・SOP変更時 |
| 標準的で時点依存性が低い基礎医学 | 36か月、または重要な改訂検知時 |
| Exam Metadata | 新しい国家試験データ取込ごと、最低年1回 |

期限超過時はKnowledgeや過去承認を削除しない。`review_required=true`とし、正式Renderer経路は`renderer_ineligible`にする設計を次Phaseで実装する。Phase 5.21ではContract案のみとする。

## 8. Review Decision

Review DecisionはApproval Stateと別に保持する。

| Decision | 意味 | Approval Stateへの影響 |
|---|---|---|
| `approved` | 対象ScopeのCriteriaを満たした | Final Approverの確認後に次状態へ進める |
| `approved_with_conditions` | 内容は概ね妥当だが未解決条件がある | `medical_review`に留め、Renderer不可。条件解消後に再レビュー |
| `revision_required` | 修正後に再確認できる | draftまたはowner_reviewへ差し戻す |
| `rejected` | 現版は採用不可 | 承認不可。履歴を残し新Versionまたは廃止を判断 |
| `not_applicable` | 個別Checklist項目が対象外 | 項目単位で理由必須。Review全体の最終Decisionには使用しない |
| `insufficient_evidence` | 根拠不足で医学判断不能 | `medical_review`に留め、公開・外部送信・Renderer不可 |

`approved_with_conditions`を既存Approval Gateの`approved`と同義にしない。条件が残るKnowledgeを正式利用したい場合は、条件を解消した新Reviewを作成する。

## 9. Review Version Contract

Review VersionはKnowledge Versionから独立した、Knowledge単位の単調増加カウンターとする。

```text
Knowledge v3 + Review r2
  ├─ 本文変更なしで期限再確認 → Knowledge v3 + Review r3
  └─ 医学的意味を変更       → Knowledge v4 + Review r4
```

- Review Versionは上書きしない。
- 各Reviewは正確なKnowledge Version、Content Fingerprint、Claim ID/Version集合へ固定する。
- 同じKnowledge Versionを再レビューしても新しいReview Versionを作る。
- 医学的意味、Claim本文、対象範囲が変わればKnowledge Versionも上げる。
- 誤字など医学的意味を変えない修正の版方針は、既存Knowledge Version規則に従い、少なくともFingerprint差異を検出する。
- 現在有効なReviewはRegistryから派生し、古いReviewを削除しない。

詳細は[Review Version Contract案](medical_review_contract_v1.md)と[JSON Example](examples/medical-review/review-version-v1.example.json)に記載する。

## 10. Artifactとの接続

Knowledge ApprovalとArtifact Approvalは独立したまま維持する。Phase 5.20.1のDual Approval Gateを緩和しない。

```text
Knowledge approved
AND Claim approved/current
AND Artifact approved
AND Knowledge / Review Version一致
AND Source / Artifact Fingerprint一致
        ↓
Renderer Eligible
```

Review期限超過、Review Version更新、Knowledge差し戻し、Claim変更が起きた場合は、Artifact Approvalを自動変更せずRenderer Eligibilityだけを停止する。

## 11. Workbench設計案

Phase 5.21では画面を実装しない。次Phaseの候補は次のとおり。

### Review Queue

- Knowledge名、Category、現在State、担当Reviewer
- Knowledge Version / Review Version
- 期限、Evidence不足、Claim未確認数、Stale理由
- 優先度と対象媒体

### Knowledge Review画面

- Knowledge本文とVersion固定表示
- ClaimごとのDecision、Evidence、差分
- 共通・Category専用Checklist
- Evidence Level、参照位置、適用範囲、期限
- Reviewer ProfileとRole
- Review Comment、条件、差し戻し理由
- 次回Review期限

正式承認時は自由入力名ではなく、認証済みUser IDとReviewer Profileを使用する。権限管理と本人確認は次Phase以降の実装対象である。

## 12. 運用フロー

```text
Author / Editor
  ↓ draft・Evidence登録
Product Owner
  ↓ 範囲・教材目的を確認、owner_review
System
  ↓ Schema・Completeness・Version・参照検査
Medical Reviewer
  ↓ Claim・Knowledge・Evidence・時間依存性を確認
Final Approver
  ↓ CriteriaとReview記録を確認、approved
Dual Approval Gate
  ↓ Artifactもapprovedかつ全整合時だけ利用許可
Renderer / External AI（将来）
```

## 13. Product Ownerが決める事項

1. Medical Reviewerを誰にするか。資格、専門領域、本人確認方法を決める。
2. Product Owner本人がAuthor / Editor、Product Owner、Medical Reviewer、Final Approverのどこまで担うか。
3. 疾患・診断・治療・数値・法令・施設研修で外部監修を必須にする範囲。
4. Critical ClaimにLevel Aがない場合、承認を止めるか、複数Level Bと例外記録を許可するか。
5. 12か月・36か月の推奨Review期限を採用するか。
6. `approved_with_conditions`を正式利用不可のまま運用するか。
7. 国家試験教材と医療施設研修でEvidence、期限、Reviewer要件を分けるか。
8. 最初の正式承認PilotをGram染色、鉄欠乏性貧血、フェリチンのどれから始めるか。

推奨は、最初にGram染色を臨床検査技師ReviewerでPilotし、次にフェリチンを検査領域Reviewer、鉄欠乏性貧血を医師Reviewerへ進める順序である。すべて実Knowledgeの承認操作は次Phaseで、Reviewerと運用条件を確定してから行う。

## 14. 今回変更しないもの

- 実Knowledge / Claim / ArtifactのApproval State
- Renderer EligibilityとDual Approval Gate
- Knowledge / Category Schema
- Source Bundle、Presentation Request、Provider Payload
- Gemini Adapter、Renderer、Publisher Core
- Workbench実装
