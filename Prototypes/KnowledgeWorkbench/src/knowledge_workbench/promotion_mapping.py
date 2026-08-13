"""Shared, explicit mapping from author-selected semantic slots to Knowledge 1.0."""

from knowledge_workbench.authoring_models import (
    AuthoringCategory,
    AuthoringSemanticSlot,
)

CATEGORY_SLOTS: dict[AuthoringCategory, set[AuthoringSemanticSlot]] = {
    AuthoringCategory.TEST_ITEM: {
        AuthoringSemanticSlot.DEFINITION,
        AuthoringSemanticSlot.BIOLOGICAL_BASIS,
        AuthoringSemanticSlot.ANALYTE_CHARACTERISTIC,
        AuthoringSemanticSlot.PURPOSE,
        AuthoringSemanticSlot.INTERPRETATION_CAUTION,
    },
    AuthoringCategory.STAINING_METHOD: {
        AuthoringSemanticSlot.DEFINITION,
        AuthoringSemanticSlot.SAFETY_CONSIDERATION,
    },
    AuthoringCategory.SPECIMEN: {
        AuthoringSemanticSlot.DEFINITION,
        AuthoringSemanticSlot.OVERVIEW,
        AuthoringSemanticSlot.CAUTION,
    },
    AuthoringCategory.REAGENT: {
        AuthoringSemanticSlot.DEFINITION,
        AuthoringSemanticSlot.CAUTION,
    },
    AuthoringCategory.BIOLOGICAL_STRUCTURE: {
        AuthoringSemanticSlot.DEFINITION,
        AuthoringSemanticSlot.OVERVIEW,
    },
    AuthoringCategory.DISEASE: {
        AuthoringSemanticSlot.DEFINITION,
        AuthoringSemanticSlot.OVERVIEW,
    },
    AuthoringCategory.LABORATORY_TEST_ITEM: {
        AuthoringSemanticSlot.DEFINITION,
        AuthoringSemanticSlot.OVERVIEW,
    },
}

SLOT_PATHS: dict[tuple[AuthoringCategory, AuthoringSemanticSlot], tuple[str, ...]] = {
    **{
        (category, AuthoringSemanticSlot.DEFINITION): ("core_facts", "definitions")
        for category in AuthoringCategory
    },
    (AuthoringCategory.TEST_ITEM, AuthoringSemanticSlot.BIOLOGICAL_BASIS): (
        "category_content",
        "test_item",
        "biological_basis",
    ),
    (AuthoringCategory.TEST_ITEM, AuthoringSemanticSlot.ANALYTE_CHARACTERISTIC): (
        "category_content",
        "test_item",
        "analyte_characteristics",
    ),
    (AuthoringCategory.TEST_ITEM, AuthoringSemanticSlot.PURPOSE): (
        "category_content",
        "test_item",
        "purposes",
    ),
    (AuthoringCategory.TEST_ITEM, AuthoringSemanticSlot.INTERPRETATION_CAUTION): (
        "category_content",
        "test_item",
        "interpretation_cautions",
    ),
    (AuthoringCategory.STAINING_METHOD, AuthoringSemanticSlot.SAFETY_CONSIDERATION): (
        "category_content",
        "staining_method",
        "safety_considerations",
    ),
    (AuthoringCategory.SPECIMEN, AuthoringSemanticSlot.OVERVIEW): (
        "category_content",
        "specimen",
        "overview",
    ),
    (AuthoringCategory.SPECIMEN, AuthoringSemanticSlot.CAUTION): (
        "category_content",
        "specimen",
        "cautions",
    ),
    (AuthoringCategory.REAGENT, AuthoringSemanticSlot.CAUTION): (
        "category_content",
        "reagent",
        "cautions",
    ),
    (AuthoringCategory.BIOLOGICAL_STRUCTURE, AuthoringSemanticSlot.OVERVIEW): (
        "category_content",
        "biological_structure",
        "overview",
    ),
    (AuthoringCategory.DISEASE, AuthoringSemanticSlot.OVERVIEW): (
        "category_content",
        "disease",
        "overview",
    ),
    (AuthoringCategory.LABORATORY_TEST_ITEM, AuthoringSemanticSlot.OVERVIEW): (
        "category_content",
        "laboratory_test_item",
        "overview",
    ),
}


def promotion_semantic_slots() -> dict[str, list[str]]:
    """Return explicit author choices supported by the lossless mapper."""

    return {
        category.value: sorted(slot.value for slot in slots)
        for category, slots in CATEGORY_SLOTS.items()
    }
