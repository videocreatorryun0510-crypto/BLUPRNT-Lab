from dataclasses import replace

import pytest
from pydantic import ValidationError

from publisher_core import (
    OutputKind,
    ProfileReference,
    TemplateRegistry,
    TemplateRegistryError,
    load_profile_catalog,
)


def test_template_registry_loads_all_shared_output_families(
    template_registry: TemplateRegistry,
) -> None:
    templates = template_registry.list_templates()

    assert len(templates) == 10
    assert {item.output_kind for item in templates} == set(OutputKind)
    assert template_registry.latest("template.national_exam_pdf").version == "1.5.0"
    assert template_registry.latest("template.gram_stain_national_exam_pdf").version == (
        "1.0.0"
    )


def test_template_resolves_seven_independent_publisher_layers(
    template_registry: TemplateRegistry,
) -> None:
    resolved = template_registry.resolve(
        ProfileReference(profile_id="template.national_exam_pdf", version="1.1.0")
    )

    assert resolved.content_profile.profile_id == "content.national_exam_pdf"
    assert resolved.education_profile is not None
    assert resolved.education_profile.profile_id == "education.national_exam"
    assert resolved.visual_profile.profile_id == "visual.ast_learning"
    assert resolved.layout_profile.profile_id == "layout.national_exam_pdf"
    assert resolved.theme.profile_id == "theme.bluprnt_exam"
    assert resolved.design_system.profile_id == "design_system.clinical_exam"
    assert resolved.template.media_profile_ref is None


def test_template_resolves_visual_grammar_as_an_independent_layer(
    template_registry: TemplateRegistry,
) -> None:
    resolved = template_registry.resolve(
        ProfileReference(profile_id="template.national_exam_pdf", version="1.2.0")
    )

    assert resolved.education_profile is not None
    assert resolved.visual_grammar_profile is not None
    assert resolved.visual_grammar_profile.profile_id == "visual_grammar.ast_learning"
    assert resolved.visual_grammar_profile.version == "1.0.0"
    assert resolved.template.media_profile_ref is None


def test_template_resolves_diagram_intent_as_an_independent_layer(
    template_registry: TemplateRegistry,
) -> None:
    resolved = template_registry.resolve(
        ProfileReference(profile_id="template.national_exam_pdf", version="1.3.0")
    )

    assert resolved.visual_grammar_profile is not None
    assert resolved.diagram_intent_profile is not None
    assert resolved.diagram_intent_profile.profile_id == "diagram_intent.ast_learning"
    assert resolved.diagram_intent_profile.version == "1.0.0"


def test_phase_31_template_remains_without_education_profile(
    template_registry: TemplateRegistry,
) -> None:
    resolved = template_registry.resolve(
        ProfileReference(profile_id="template.national_exam_pdf", version="1.0.0")
    )

    assert resolved.education_profile is None
    assert resolved.visual_grammar_profile is None
    assert resolved.diagram_intent_profile is None


def test_design_system_rejects_theme_drift(profile_root) -> None:
    catalog = load_profile_catalog(profile_root)
    theme = next(
        item
        for item in catalog.themes
        if item.profile_id == "theme.bluprnt_exam" and item.version == "1.0.0"
    )
    alternate_theme = theme.model_copy(update={"version": "1.1.0"})
    template = next(
        item
        for item in catalog.templates
        if item.template_id == "template.national_exam_pdf" and item.version == "1.0.0"
    )
    drifting_template = template.model_copy(
        update={
            "version": "9.1.0",
            "theme_ref": ProfileReference(
                profile_id=alternate_theme.profile_id, version=alternate_theme.version
            ),
        }
    )
    invalid_catalog = replace(
        catalog,
        themes=(*catalog.themes, alternate_theme),
        templates=(*catalog.templates, drifting_template),
    )

    with pytest.raises(TemplateRegistryError, match="Theme must be the Theme locked"):
        TemplateRegistry(invalid_catalog)


def test_profile_models_are_immutable(template_registry: TemplateRegistry) -> None:
    resolved = template_registry.resolve(
        ProfileReference(profile_id="template.note_article", version="1.0.0")
    )

    with pytest.raises(ValidationError, match="frozen"):
        resolved.theme.name = "その場で変更してはいけないTheme"
