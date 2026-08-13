# Medical Review Checklist Version 1.0 — Design Proposal

- Checklist ID: `medical_review_checklist_v1`
- Phase: 5.21
- Status: Implemented by Phase 5.31
- Result vocabulary: `pass` / `fail` / `not_applicable` / `not_reviewed`
- Severity: `blocker` / `required` / `advisory`

## 1. 使用ルール

1. 共通Checklistと対象Category Checklistの両方を使用する。
2. `blocker`が1件でも`pass`以外ならReview Decisionを`approved`にできない。
3. `required`の未達は原則`revision_required`または`insufficient_evidence`とする。
4. `not_applicable`には理由、判断者、日時を記録する。
5. Systemの自動検査結果とMedical Reviewerの判断を別々に記録する。
6. Checklist結果は特定のKnowledge / Claim VersionとFingerprintへ固定する。
7. Completeness 100%でもChecklistを省略しない。

## 2. Category共通Checklist

| ID | Severity | 確認項目 | 主担当 | 合格条件 |
|---|---|---|---|---|
| `COMMON-001` | blocker | 対象Version固定 | System | Knowledge Version、全Claim Version、FingerprintがRegistry最新版と一致 |
| `COMMON-002` | blocker | Schema Validation | System | 対象Category Schemaに適合 |
| `COMMON-003` | blocker | Category Completeness | System + Reviewer | Category閾値以上かつblocker項目が充足 |
| `COMMON-004` | blocker | Category適合 | Medical Reviewer | Knowledgeの責務がCategory境界に合う |
| `COMMON-005` | blocker | 定義の正確性 | Medical Reviewer | 対象範囲を過不足なく定義し、Evidenceが直接支持 |
| `COMMON-006` | blocker | Claim原子性 | Medical Reviewer | 各Claimが独立した1つの医学的事実 |
| `COMMON-007` | blocker | Claim Evidence | Medical Reviewer | 全active Claimに適切なEvidenceと具体的locatorがある |
| `COMMON-008` | blocker | 断定の強さ | Medical Reviewer | Evidenceより強い断定、一般化、因果推測がない |
| `COMMON-009` | blocker | 条件・例外 | Medical Reviewer | 対象集団、方法、時点、地域、例外が失われていない |
| `COMMON-010` | blocker | 矛盾 | Medical Reviewer + System | 重大な内部矛盾・現行Knowledgeとの矛盾がない |
| `COMMON-011` | blocker | deprecated参照 | System | 未解決deprecated Claim、Redirect切れがない |
| `COMMON-012` | blocker | Evidence実在 | Medical Reviewer | 資料、版、発行元、該当箇所を確認済み |
| `COMMON-013` | required | Evidence優先順位 | Medical Reviewer | より上位の国内公的・学会資料を検討し、採否理由を記録 |
| `COMMON-014` | blocker | Evidence適用範囲 | Medical Reviewer | jurisdiction、対象集団、method/product scopeがClaimと一致 |
| `COMMON-015` | blocker | 時点依存性 | Medical Reviewer + System | 必要なvalidityとreview_due_atがある。期限内 |
| `COMMON-016` | required | 用語・表記 | Medical Reviewer | 正式名称、略語、単位、表記が一貫 |
| `COMMON-017` | required | 重複 | Medical Reviewer + System | 重複Claimを統合・区別し、意味の衝突がない |
| `COMMON-018` | blocker | Reviewer適格性 | Final Approver | 本人ID、Role、専門領域、資格確認、利益相反が記録済み |
| `COMMON-019` | blocker | Review記録 | Final Approver | Checklist版、Policy版、Decision、Comment、日時が完全 |
| `COMMON-020` | blocker | 未解決条件 | Final Approver | `approved`時に未解決conditionがない |
| `COMMON-021` | required | 教育用途の境界 | Product Owner | 国家試験教材か施設研修かを明記し、用途外の断定をしない |
| `COMMON-022` | advisory | 読みやすさ | Product Owner | 医学的意味を損なわず対象者が理解できる |

## 3. Disease Checklist

| ID | Severity | 確認項目 | 合格条件 |
|---|---|---|---|
| `DISEASE-001` | blocker | 疾患定義 | 診断概念、対象範囲、類義語が現行資料と一致 |
| `DISEASE-002` | blocker | 病態 | 原因と病態生理を混同せず、因果の強さが根拠に一致 |
| `DISEASE-003` | required | 原因 | 原因、リスク因子、関連を区別 |
| `DISEASE-004` | required | 主な症状 | 代表性と非特異性を適切に表現 |
| `DISEASE-005` | blocker | 主な検査所見 | 高値・低値、形態、条件、例外が資料と一致 |
| `DISEASE-006` | blocker | 診断基準・閾値 | 掲載する場合は最新版、単位、対象、jurisdiction、validityを確認 |
| `DISEASE-007` | required | 鑑別 | 鑑別対象と比較軸が医学的に妥当 |
| `DISEASE-008` | blocker | 治療情報 | 掲載する場合は国内最新版と医師Reviewerを必須とする |
| `DISEASE-009` | required | 国家試験ポイント | 医学的事実と出題頻度・学習優先度を分離 |
| `DISEASE-010` | required | 疾患名の標準化 | 略称・旧称・病型を混同しない |

## 4. Laboratory Test Item Checklist

| ID | Severity | 確認項目 | 合格条件 |
|---|---|---|---|
| `LABTEST-001` | blocker | 測定対象 | analyte、検体、測定対象が明確 |
| `LABTEST-002` | blocker | 臨床的意義 | 検査の目的と解釈限界がEvidenceに一致 |
| `LABTEST-003` | blocker | 高値・低値 | 疾患と病態を区別し、代表性・例外・干渉を確認 |
| `LABTEST-004` | blocker | 測定法 | 方法名、原理、method/product scope、版を確認 |
| `LABTEST-005` | blocker | 基準範囲 | 掲載する場合は単位、対象集団、施設・方法依存、validityを明示 |
| `LABTEST-006` | required | 検体条件 | 血清・血漿等、採取・保存・前処理条件を確認 |
| `LABTEST-007` | required | 干渉・注意 | 炎症、溶血、薬剤、測定干渉など必要な注意を確認 |
| `LABTEST-008` | required | 他検査との比較 | 比較軸と解釈が承認済みClaimに基づく |
| `LABTEST-009` | blocker | 製品添付文書 | 製品固有Claimは該当製品・版・参照日の範囲を超えない |
| `LABTEST-010` | required | 標準化コード | 未導入時は無理に推測せず、将来対応として記録 |

## 5. Staining Method Checklist

| ID | Severity | 確認項目 | 合格条件 |
|---|---|---|---|
| `STAIN-001` | blocker | 目的・対象構造 | 染色目的、対象、鑑別対象が明確 |
| `STAIN-002` | blocker | 固定 | 固定法、条件、安全上の注意が標準法と一致 |
| `STAIN-003` | blocker | 試薬 | 正式名称、役割、順序、製品依存性を確認 |
| `STAIN-004` | blocker | 工程 | 順序、時間、温度、洗浄、脱色等の必要条件が欠けていない |
| `STAIN-005` | blocker | 染色原理 | 機序を過度に単純化せず、対象構造との関係を確認 |
| `STAIN-006` | blocker | 判定 | 陽性・陰性、色、形態、背景、判定限界を確認 |
| `STAIN-007` | blocker | 精度管理 | 陽性・陰性対照、期待結果、失敗時対応を確認 |
| `STAIN-008` | blocker | エラー原因 | 過染色、脱色、厚い塗抹等の原因と影響が妥当 |
| `STAIN-009` | blocker | 限界 | 染色だけで確定できない事項、適用外対象を明示 |
| `STAIN-010` | blocker | 安全 | 感染性検体、加温、化学物質等の安全範囲を確認 |
| `STAIN-011` | required | Relation | 試薬、検体、対象構造、関連法とのRelationを独立レビュー |
| `STAIN-012` | required | 標準法 | 国内標準または採用SOPとの差異を記録 |

## 6. Relation Checklist

| ID | Severity | 確認項目 | 合格条件 |
|---|---|---|---|
| `REL-001` | blocker | Vocabulary | Relation Typeが承認済みVocabularyに存在 |
| `REL-002` | blocker | 方向 | Source / Target Categoryと方向が契約どおり |
| `REL-003` | blocker | 接続先 | Target Knowledgeが存在し、安定ID・現行Version |
| `REL-004` | blocker | Context | 文脈がKnowledge本文ではなくRelation利用条件として適切 |
| `REL-005` | blocker | 根拠 | 根拠Claimがapprovedかつ現行 |
| `REL-006` | blocker | Version / Redirect | Relation Version、deprecated、Redirectが整合 |

## 7. Exam Metadata Checklist

| ID | Severity | 確認項目 | 合格条件 |
|---|---|---|---|
| `EXAM-001` | blocker | 原資料 | 実CSV・原問題・真正なデータソースに基づく |
| `EXAM-002` | blocker | 問題識別 | 試験回、年度、午前午後、問題番号が一致 |
| `EXAM-003` | blocker | Claim対応 | Tested Claimが現行ID・Version |
| `EXAM-004` | blocker | Import追跡 | Import Batch、Source File、Row IDを追跡可能 |
| `EXAM-005` | required | 出題パターン | 付与根拠が確認できる |
| `EXAM-006` | blocker | Importance Score | 計算式Version、対象期間、入力件数が固定 |
| `EXAM-007` | blocker | 画像 | Image ID、ファイル、問題ID、欠損Warningが一致 |
| `EXAM-008` | required | 更新期限 | 最新回追加後に再計算・再レビュー済み |

## 8. Final Approver Checklist

- Medical Reviewerの専門領域が対象Categoryと合う
- 全blockerがpass
- 全active Claimがapprovedかつ現行
- Evidence Policy Version 1.0を満たす
- 期限超過・未解決条件・重大な矛盾がない
- Review Decisionが`approved`
- Review Versionと対象Fingerprintを固定
- Review Commentに承認範囲と除外事項を記載
- 次回Review期限を設定
- 状態遷移とAuditを同一Transactionで保存
