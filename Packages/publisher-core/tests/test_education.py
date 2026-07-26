from dataclasses import replace

import pytest

from publisher_core import (
    DifficultyLevel,
    EducationProfile,
    ProfileReference,
    PublicationRequest,
    PublicationSourceBundle,
    PublisherPlanner,
    TemplateRegistry,
    load_profile_catalog,
)


def _request(
    request_id: str,
    *,
    education_ref: ProfileReference | None = None,
) -> PublicationRequest:
    return PublicationRequest(
        request_id=request_id,
        template_ref=ProfileReference(
            profile_id="template.national_exam_pdf",
            version="1.1.0",
        ),
        knowledge_id="knw_ast_v10_example",
        education_profile_ref=education_ref,
    )


def test_ast_national_exam_education_profile_builds_plan_11(
    template_registry: TemplateRegistry,
    publication_source: PublicationSourceBundle,
) -> None:
    before = publication_source.model_dump(mode="json")

    plan = PublisherPlanner(template_registry).build_plan(
        publication_source,
        _request("request.ast_education_v1"),
    )

    assert publication_source.model_dump(mode="json") == before
    assert plan.plan_schema_version == "1.1"
    assert plan.education_profile_ref == ProfileReference(
        profile_id="education.national_exam",
        version="1.0.0",
    )
    assert plan.difficulty_level == DifficultyLevel.STANDARD
    assert "assertion" not in plan.model_dump_json()

    assert [item.content_role for item in plan.content_sections] == [
        "role.definition",
        "role.comparison",
        "role.measurement_method",
        "role.measurement_principle",
    ]
    assert [item.target_key for item in plan.learning_sequence[:8]] == [
        "role.definition",
        "education.frequent_points",
        "diagram.reaction",
        "table.comparison",
        "education.related_comparison",
        "role.comparison",
        "role.measurement_method",
        "role.measurement_principle",
    ]

    assert plan.exam_priority is not None
    assert plan.exam_priority.importance_score == 90
    assert plan.exam_priority.emphasis_level == 5
    assert plan.exam_priority.label == "最重要"
    assert plan.exam_priority.priority_claim_refs[0].claim_key == (
        "ast.definition.aminotransferase_enzyme"
    )

    assert plan.comparison_priority is not None
    assert plan.comparison_priority.is_required is True
    assert plan.comparison_priority.content_section_ids == ("section.comparison",)
    assert plan.comparison_priority.visual_ids == ("visual.comparison_table",)
    assert [item.visual_type for item in plan.visual_priority] == [
        "diagram.reaction",
        "table.comparison",
        "diagram.flowchart",
        "diagram.organ_distribution",
    ]
    assert [item.rank for item in plan.visual_priority] == [1, 2, 3, 4]

    block_ids = {item.block_id for item in plan.education_blocks}
    assert block_ids == {
        "education.frequent_points",
        "education.related_comparison",
        "education.trick_points",
        "education.common_errors",
        "education.memory_aid",
        "education.exam_history",
        "education.priority_claim_ranking",
    }
    memory = next(item for item in plan.education_blocks if item.block_id == "education.memory_aid")
    assert memory.generation_required is True


def test_phase_31_plan_10_stays_backward_compatible(
    template_registry: TemplateRegistry,
    publication_source: PublicationSourceBundle,
) -> None:
    plan = PublisherPlanner(template_registry).build_plan(
        publication_source,
        PublicationRequest(
            request_id="request.phase31_compatibility",
            template_ref=ProfileReference(
                profile_id="template.national_exam_pdf",
                version="1.0.0",
            ),
            knowledge_id=publication_source.knowledge.knowledge_id,
        ),
    )

    assert plan.plan_schema_version == "1.0"
    assert plan.education_profile_ref is None
    assert plan.learning_sequence == ()
    assert plan.education_blocks == ()


def test_only_education_profile_changes_learning_structure(
    profile_root,
    publication_source: PublicationSourceBundle,
) -> None:
    catalog = load_profile_catalog(profile_root)
    base = next(
        item
        for item in catalog.education_profiles
        if item.profile_id == "education.national_exam" and item.version == "1.0.0"
    )
    swapped_steps = tuple(
        step.model_copy(update={"order": 7})
        if step.target_key == "role.definition"
        else step.model_copy(update={"order": 1})
        if step.target_key == "role.measurement_method"
        else step
        for step in base.learning_sequence
    )
    swapped_visuals = tuple(
        item.model_copy(update={"rank": 2})
        if item.visual_type == "diagram.reaction"
        else item.model_copy(update={"rank": 1})
        if item.visual_type == "table.comparison"
        else item
        for item in base.visual_priority
    )
    changed = base.model_copy(
        update={
            "version": "1.1.0",
            "learning_sequence": swapped_steps,
            "visual_priority": swapped_visuals,
        }
    )
    registry = TemplateRegistry(
        replace(
            catalog,
            education_profiles=(*catalog.education_profiles, changed),
        )
    )
    planner = PublisherPlanner(registry)
    before = publication_source.model_dump(mode="json")
    base_plan = planner.build_plan(
        publication_source,
        _request("request.education_base"),
    )
    changed_plan = planner.build_plan(
        publication_source,
        _request(
            "request.education_changed",
            education_ref=ProfileReference(
                profile_id=changed.profile_id,
                version=changed.version,
            ),
        ),
    )

    assert publication_source.model_dump(mode="json") == before
    assert base_plan.content_profile_ref == changed_plan.content_profile_ref
    assert base_plan.visual_profile_ref == changed_plan.visual_profile_ref
    assert base_plan.layout_profile_ref == changed_plan.layout_profile_ref
    assert base_plan.theme_ref == changed_plan.theme_ref
    assert base_plan.design_system_ref == changed_plan.design_system_ref
    assert base_plan.education_profile_ref != changed_plan.education_profile_ref
    assert base_plan.content_sections != changed_plan.content_sections
    assert base_plan.visuals != changed_plan.visuals
    assert {
        claim.claim_id for section in base_plan.content_sections for claim in section.claim_refs
    } == {
        claim.claim_id for section in changed_plan.content_sections for claim in section.claim_refs
    }


@pytest.mark.parametrize("level", list(DifficultyLevel))
def test_education_profile_supports_three_learning_levels(
    template_registry: TemplateRegistry,
    level: DifficultyLevel,
) -> None:
    base = template_registry.resolve_education(
        ProfileReference(profile_id="education.national_exam", version="1.0.0")
    )
    payload = base.model_dump(mode="json")
    payload["level_policy"]["difficulty_level"] = level.value

    profile = EducationProfile.model_validate(payload)

    assert profile.level_policy.difficulty_level == level


def test_basic_level_reduces_optional_blocks_and_visuals(
    profile_root,
    publication_source: PublicationSourceBundle,
) -> None:
    catalog = load_profile_catalog(profile_root)
    base = next(
        item
        for item in catalog.education_profiles
        if item.profile_id == "education.national_exam" and item.version == "1.0.0"
    )
    basic = base.model_copy(
        update={
            "version": "1.2.0",
            "level_policy": base.level_policy.model_copy(
                update={
                    "difficulty_level": DifficultyLevel.BASIC,
                    "max_claims_per_section": 1,
                    "max_items_per_education_block": 1,
                    "include_optional_content": False,
                    "include_optional_education_blocks": False,
                    "include_optional_visuals": False,
                }
            ),
        }
    )
    registry = TemplateRegistry(
        replace(
            catalog,
            education_profiles=(*catalog.education_profiles, basic),
        )
    )

    plan = PublisherPlanner(registry).build_plan(
        publication_source,
        _request(
            "request.education_basic",
            education_ref=ProfileReference(
                profile_id=basic.profile_id,
                version=basic.version,
            ),
        ),
    )

    assert plan.difficulty_level == DifficultyLevel.BASIC
    assert [item.visual_type for item in plan.visuals] == [
        "diagram.reaction",
        "table.comparison",
    ]
    assert {item.block_id for item in plan.education_blocks} == {
        "education.frequent_points",
        "education.related_comparison",
        "education.exam_history",
        "education.priority_claim_ranking",
    }
    assert all(item.max_items == 1 for item in plan.education_blocks)
