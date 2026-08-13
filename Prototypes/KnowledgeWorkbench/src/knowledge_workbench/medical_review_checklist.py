"""Executable catalog for the approved Phase 5.21 medical review criteria."""

from knowledge_workbench.medical_review_models import (
    ChecklistDefinition,
    ChecklistSeverity,
)

CHECKLIST_ID = "medical_review_checklist_v1"
CHECKLIST_VERSION = "1.0"
EVIDENCE_POLICY_VERSION = "1.0"


def checklist_for_category(category: str) -> list[ChecklistDefinition]:
    return [*_COMMON, *_CATEGORY.get(category, [])]


def checklist_by_id(category: str) -> dict[str, ChecklistDefinition]:
    return {item.item_id: item for item in checklist_for_category(category)}


def _item(
    item_id: str,
    severity: ChecklistSeverity,
    label: str,
    category: str | None = None,
) -> ChecklistDefinition:
    return ChecklistDefinition(
        item_id=item_id,
        severity=severity,
        label=label,
        category=category,
    )


B = ChecklistSeverity.BLOCKER
R = ChecklistSeverity.REQUIRED
A = ChecklistSeverity.ADVISORY

_COMMON = [
    _item("COMMON-001", B, "対象Version固定"),
    _item("COMMON-002", B, "Schema Validation"),
    _item("COMMON-003", B, "Category Completeness"),
    _item("COMMON-004", B, "Category適合"),
    _item("COMMON-005", B, "定義の正確性"),
    _item("COMMON-006", B, "Claim原子性"),
    _item("COMMON-007", B, "Claim Evidence"),
    _item("COMMON-008", B, "断定の強さ"),
    _item("COMMON-009", B, "条件・例外"),
    _item("COMMON-010", B, "矛盾"),
    _item("COMMON-011", B, "deprecated参照"),
    _item("COMMON-012", B, "Evidence実在"),
    _item("COMMON-013", R, "Evidence優先順位"),
    _item("COMMON-014", B, "Evidence適用範囲"),
    _item("COMMON-015", B, "時点依存性"),
    _item("COMMON-016", R, "用語・表記"),
    _item("COMMON-017", R, "重複"),
    _item("COMMON-018", B, "Reviewer適格性"),
    _item("COMMON-019", B, "Review記録"),
    _item("COMMON-020", B, "未解決条件"),
    _item("COMMON-021", R, "教育用途の境界"),
    _item("COMMON-022", A, "読みやすさ"),
]

_CATEGORY = {
    "disease": [
        _item("DISEASE-001", B, "疾患定義", "disease"),
        _item("DISEASE-002", B, "病態", "disease"),
        _item("DISEASE-003", R, "原因", "disease"),
        _item("DISEASE-004", R, "主な症状", "disease"),
        _item("DISEASE-005", B, "主な検査所見", "disease"),
        _item("DISEASE-006", B, "診断基準・閾値", "disease"),
        _item("DISEASE-007", R, "鑑別", "disease"),
        _item("DISEASE-008", B, "治療情報", "disease"),
        _item("DISEASE-009", R, "国家試験ポイント", "disease"),
        _item("DISEASE-010", R, "疾患名の標準化", "disease"),
    ],
    "laboratory_test_item": [
        _item("LABTEST-001", B, "測定対象", "laboratory_test_item"),
        _item("LABTEST-002", B, "臨床的意義", "laboratory_test_item"),
        _item("LABTEST-003", B, "高値・低値", "laboratory_test_item"),
        _item("LABTEST-004", B, "測定法", "laboratory_test_item"),
        _item("LABTEST-005", B, "基準範囲", "laboratory_test_item"),
        _item("LABTEST-006", R, "検体条件", "laboratory_test_item"),
        _item("LABTEST-007", R, "干渉・注意", "laboratory_test_item"),
        _item("LABTEST-008", R, "他検査との比較", "laboratory_test_item"),
        _item("LABTEST-009", B, "製品添付文書", "laboratory_test_item"),
        _item("LABTEST-010", R, "標準化コード", "laboratory_test_item"),
    ],
    "test_item": [
        _item("LABTEST-001", B, "測定対象", "test_item"),
        _item("LABTEST-002", B, "臨床的意義", "test_item"),
        _item("LABTEST-003", B, "高値・低値", "test_item"),
        _item("LABTEST-004", B, "測定法", "test_item"),
        _item("LABTEST-005", B, "基準範囲", "test_item"),
        _item("LABTEST-006", R, "検体条件", "test_item"),
        _item("LABTEST-007", R, "干渉・注意", "test_item"),
        _item("LABTEST-008", R, "他検査との比較", "test_item"),
        _item("LABTEST-009", B, "製品添付文書", "test_item"),
        _item("LABTEST-010", R, "標準化コード", "test_item"),
    ],
    "staining_method": [
        _item("STAIN-001", B, "目的・対象構造", "staining_method"),
        _item("STAIN-002", B, "固定", "staining_method"),
        _item("STAIN-003", B, "試薬", "staining_method"),
        _item("STAIN-004", B, "工程", "staining_method"),
        _item("STAIN-005", B, "染色原理", "staining_method"),
        _item("STAIN-006", B, "判定", "staining_method"),
        _item("STAIN-007", B, "精度管理", "staining_method"),
        _item("STAIN-008", B, "エラー原因", "staining_method"),
        _item("STAIN-009", B, "限界", "staining_method"),
        _item("STAIN-010", B, "安全", "staining_method"),
        _item("STAIN-011", R, "Relation", "staining_method"),
        _item("STAIN-012", R, "標準法", "staining_method"),
    ],
}
