"""Versioned Profile catalog and Template Registry."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from publisher_core.diagram_taxonomy import (
    DiagramTaxonomyProfile,
    TaxonomyNodeStatus,
)
from publisher_core.models import (
    ContentProfile,
    DesignSystem,
    DiagramIntentProfile,
    EducationProfile,
    LayoutProfile,
    OutputKind,
    ProfileReference,
    ProfileStatus,
    TemplateDefinition,
    ThemeProfile,
    VisualGrammarProfile,
    VisualProfile,
)


class TemplateRegistryError(ValueError):
    """Raised when versioned Publisher Profiles cannot be composed safely."""


@dataclass(frozen=True)
class ProfileCatalog:
    content_profiles: tuple[ContentProfile, ...]
    education_profiles: tuple[EducationProfile, ...]
    visual_profiles: tuple[VisualProfile, ...]
    visual_grammar_profiles: tuple[VisualGrammarProfile, ...]
    diagram_intent_profiles: tuple[DiagramIntentProfile, ...]
    diagram_taxonomies: tuple[DiagramTaxonomyProfile, ...]
    layout_profiles: tuple[LayoutProfile, ...]
    themes: tuple[ThemeProfile, ...]
    design_systems: tuple[DesignSystem, ...]
    templates: tuple[TemplateDefinition, ...]


@dataclass(frozen=True)
class ResolvedTemplate:
    template: TemplateDefinition
    content_profile: ContentProfile
    education_profile: EducationProfile | None
    visual_profile: VisualProfile
    visual_grammar_profile: VisualGrammarProfile | None
    diagram_intent_profile: DiagramIntentProfile | None
    diagram_taxonomy: DiagramTaxonomyProfile | None
    layout_profile: LayoutProfile
    theme: ThemeProfile
    design_system: DesignSystem


ProfileT = TypeVar(
    "ProfileT",
    ContentProfile,
    EducationProfile,
    VisualProfile,
    VisualGrammarProfile,
    DiagramIntentProfile,
    DiagramTaxonomyProfile,
    LayoutProfile,
    ThemeProfile,
    DesignSystem,
)
ModelT = TypeVar("ModelT", bound=BaseModel)


class TemplateRegistry:
    """Resolve versioned templates without embedding a medium-specific renderer."""

    def __init__(self, catalog: ProfileCatalog) -> None:
        self._catalog = catalog
        self._content = _index_profiles(catalog.content_profiles)
        self._education = _index_profiles(catalog.education_profiles)
        self._visual = _index_profiles(catalog.visual_profiles)
        self._visual_grammar = _index_profiles(catalog.visual_grammar_profiles)
        self._diagram_intent = _index_profiles(catalog.diagram_intent_profiles)
        self._diagram_taxonomy = _index_profiles(catalog.diagram_taxonomies)
        self._layout = _index_profiles(catalog.layout_profiles)
        self._themes = _index_profiles(catalog.themes)
        self._design_systems = _index_profiles(catalog.design_systems)
        self._templates = _index_templates(catalog.templates)
        self._validate_catalog()

    @classmethod
    def from_directory(cls, root: Path) -> "TemplateRegistry":
        return cls(load_profile_catalog(root))

    def resolve(self, template_ref: ProfileReference) -> ResolvedTemplate:
        template = self._templates.get(_ref_key(template_ref))
        if template is None:
            raise TemplateRegistryError(
                f"template is not registered: {template_ref.profile_id}@{template_ref.version}"
            )
        if template.status != ProfileStatus.ACTIVE:
            raise TemplateRegistryError("only active templates can be used")
        return ResolvedTemplate(
            template=template,
            content_profile=_require_profile(self._content, template.content_profile_ref),
            education_profile=(
                _require_profile(self._education, template.education_profile_ref)
                if template.education_profile_ref is not None
                else None
            ),
            visual_profile=_require_profile(self._visual, template.visual_profile_ref),
            visual_grammar_profile=(
                _require_profile(
                    self._visual_grammar,
                    template.visual_grammar_profile_ref,
                )
                if template.visual_grammar_profile_ref is not None
                else None
            ),
            diagram_intent_profile=(
                _require_profile(
                    self._diagram_intent,
                    template.diagram_intent_profile_ref,
                )
                if template.diagram_intent_profile_ref is not None
                else None
            ),
            diagram_taxonomy=(
                _require_profile(
                    self._diagram_taxonomy,
                    template.diagram_taxonomy_ref,
                )
                if template.diagram_taxonomy_ref is not None
                else None
            ),
            layout_profile=_require_profile(self._layout, template.layout_profile_ref),
            theme=_require_profile(self._themes, template.theme_ref),
            design_system=_require_profile(self._design_systems, template.design_system_ref),
        )

    def resolve_education(
        self,
        profile_ref: ProfileReference,
        *,
        output_kind: OutputKind | None = None,
    ) -> EducationProfile:
        profile = _require_profile(self._education, profile_ref)
        if output_kind is not None:
            _require_output_support(output_kind, profile.supported_outputs)
        return profile

    def resolve_visual_grammar(
        self,
        profile_ref: ProfileReference,
        *,
        output_kind: OutputKind | None = None,
    ) -> VisualGrammarProfile:
        profile = _require_profile(self._visual_grammar, profile_ref)
        if output_kind is not None:
            _require_output_support(output_kind, profile.supported_outputs)
        return profile

    def resolve_diagram_intent(
        self,
        profile_ref: ProfileReference,
        *,
        output_kind: OutputKind | None = None,
    ) -> DiagramIntentProfile:
        profile = _require_profile(self._diagram_intent, profile_ref)
        if output_kind is not None:
            _require_output_support(output_kind, profile.supported_outputs)
        return profile

    def resolve_diagram_taxonomy(
        self,
        profile_ref: ProfileReference,
    ) -> DiagramTaxonomyProfile:
        return _require_profile(self._diagram_taxonomy, profile_ref)

    def latest(self, template_id: str) -> TemplateDefinition:
        candidates = [
            template
            for (registered_id, _), template in self._templates.items()
            if registered_id == template_id and template.status == ProfileStatus.ACTIVE
        ]
        if not candidates:
            raise TemplateRegistryError(f"active template is not registered: {template_id}")
        return max(candidates, key=lambda item: _version_tuple(item.version))

    def list_templates(
        self,
        *,
        output_kind: OutputKind | None = None,
        template_family: str | None = None,
    ) -> tuple[TemplateDefinition, ...]:
        templates = tuple(
            item
            for item in self._catalog.templates
            if item.status == ProfileStatus.ACTIVE
            and (output_kind is None or item.output_kind == output_kind)
            and (template_family is None or item.template_family == template_family)
        )
        return tuple(sorted(templates, key=lambda item: (item.template_id, item.version)))

    def _validate_catalog(self) -> None:
        for template in self._catalog.templates:
            content = _require_profile(self._content, template.content_profile_ref)
            education = (
                _require_profile(self._education, template.education_profile_ref)
                if template.education_profile_ref is not None
                else None
            )
            visual = _require_profile(self._visual, template.visual_profile_ref)
            visual_grammar = (
                _require_profile(
                    self._visual_grammar,
                    template.visual_grammar_profile_ref,
                )
                if template.visual_grammar_profile_ref is not None
                else None
            )
            diagram_intent = (
                _require_profile(
                    self._diagram_intent,
                    template.diagram_intent_profile_ref,
                )
                if template.diagram_intent_profile_ref is not None
                else None
            )
            diagram_taxonomy = (
                _require_profile(
                    self._diagram_taxonomy,
                    template.diagram_taxonomy_ref,
                )
                if template.diagram_taxonomy_ref is not None
                else None
            )
            layout = _require_profile(self._layout, template.layout_profile_ref)
            theme = _require_profile(self._themes, template.theme_ref)
            design_system = _require_profile(self._design_systems, template.design_system_ref)
            _require_output_support(template.output_kind, content.supported_outputs)
            if education is not None:
                _require_output_support(template.output_kind, education.supported_outputs)
            _require_output_support(template.output_kind, visual.supported_outputs)
            if visual_grammar is not None:
                _require_output_support(
                    template.output_kind,
                    visual_grammar.supported_outputs,
                )
                _validate_visual_grammar_coverage(visual, visual_grammar)
            if diagram_intent is not None:
                if visual_grammar is None:
                    raise TemplateRegistryError("Diagram Intent requires a Visual Grammar Profile")
                _require_output_support(
                    template.output_kind,
                    diagram_intent.supported_outputs,
                )
                _validate_diagram_intent_coverage(
                    visual,
                    visual_grammar,
                    diagram_intent,
                )
            _validate_diagram_taxonomy_connections(
                visual,
                visual_grammar,
                diagram_intent,
                diagram_taxonomy,
            )
            _require_output_support(template.output_kind, layout.supported_outputs)
            if template.series_id != design_system.series_id:
                raise TemplateRegistryError("template series_id must match its Design System")
            if template.theme_ref != design_system.theme_ref:
                raise TemplateRegistryError(
                    "template Theme must be the Theme locked by its Design System"
                )
            rule = next(
                (
                    item
                    for item in design_system.composition_rules
                    if item.output_kind == template.output_kind
                ),
                None,
            )
            if rule is None or rule.layout_ref != template.layout_profile_ref:
                raise TemplateRegistryError(
                    "template Layout must match the series composition rule"
                )
            component_variants = {
                f"{item.component}.{item.variant}" for item in theme.component_styles
            }
            missing_components = set(rule.required_component_variants) - component_variants
            if missing_components:
                raise TemplateRegistryError(
                    "Theme is missing Design System component variants: "
                    + ", ".join(sorted(missing_components))
                )
            _validate_layout_items(content, education, visual, layout)


def load_profile_catalog(root: Path) -> ProfileCatalog:
    """Load human-editable JSON Profiles; field order never has semantic meaning."""

    if not root.is_dir():
        raise TemplateRegistryError(f"Profile directory does not exist: {root}")
    try:
        return ProfileCatalog(
            content_profiles=_load_models(root / "content", ContentProfile),
            education_profiles=_load_models(root / "education", EducationProfile),
            visual_profiles=_load_models(root / "visual", VisualProfile),
            visual_grammar_profiles=_load_models(
                root / "visual_grammar",
                VisualGrammarProfile,
            ),
            diagram_intent_profiles=_load_models(
                root / "diagram_intent",
                DiagramIntentProfile,
            ),
            diagram_taxonomies=_load_models(
                root / "diagram_taxonomy",
                DiagramTaxonomyProfile,
            ),
            layout_profiles=_load_models(root / "layout", LayoutProfile),
            themes=_load_models(root / "themes", ThemeProfile),
            design_systems=_load_models(root / "design_systems", DesignSystem),
            templates=_load_models(root / "templates", TemplateDefinition),
        )
    except (OSError, json.JSONDecodeError, ValidationError) as error:
        raise TemplateRegistryError(f"Publisher Profileを読み込めません: {error}") from error


def _load_models(directory: Path, model: type[ModelT]) -> tuple[ModelT, ...]:
    if not directory.is_dir():
        raise TemplateRegistryError(f"Profile subdirectory does not exist: {directory}")
    return tuple(
        model.model_validate(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(directory.glob("*.json"))
    )


def _index_profiles(profiles: tuple[ProfileT, ...]) -> dict[tuple[str, str], ProfileT]:
    indexed: dict[tuple[str, str], ProfileT] = {}
    for profile in profiles:
        key = (profile.profile_id, profile.version)
        if key in indexed:
            raise TemplateRegistryError(
                f"duplicate Profile version: {profile.profile_id}@{profile.version}"
            )
        indexed[key] = profile
    return indexed


def _index_templates(
    templates: tuple[TemplateDefinition, ...],
) -> dict[tuple[str, str], TemplateDefinition]:
    indexed: dict[tuple[str, str], TemplateDefinition] = {}
    for template in templates:
        key = (template.template_id, template.version)
        if key in indexed:
            raise TemplateRegistryError(
                f"duplicate Template version: {template.template_id}@{template.version}"
            )
        indexed[key] = template
    return indexed


def _require_profile(
    profiles: dict[tuple[str, str], ProfileT], reference: ProfileReference
) -> ProfileT:
    profile = profiles.get(_ref_key(reference))
    if profile is None:
        raise TemplateRegistryError(
            f"referenced Profile is not registered: {reference.profile_id}@{reference.version}"
        )
    if profile.status != ProfileStatus.ACTIVE:
        raise TemplateRegistryError("templates can only reference active Profiles")
    return profile


def _require_output_support(
    output_kind: OutputKind, supported_outputs: tuple[OutputKind, ...]
) -> None:
    if output_kind not in supported_outputs:
        raise TemplateRegistryError(f"Profile does not support output kind: {output_kind.value}")


def _validate_layout_items(
    content: ContentProfile,
    education: EducationProfile | None,
    visual: VisualProfile,
    layout: LayoutProfile,
) -> None:
    content_ids = {item.section_id for item in content.sections}
    education_ids = (
        {item.block_id for item in education.education_blocks} if education is not None else set()
    )
    visual_ids = {item.visual_id for item in visual.visuals}
    for placement in layout.placements:
        known = {
            "content": content_ids,
            "education_block": education_ids,
            "visual": visual_ids,
        }[placement.item_kind.value]
        if placement.item_id not in known:
            raise TemplateRegistryError(
                f"Layout references an unknown {placement.item_kind.value} item: "
                f"{placement.item_id}"
            )


def _validate_visual_grammar_coverage(
    visual: VisualProfile,
    grammar: VisualGrammarProfile,
) -> None:
    grammar_visual_types = {
        visual_type for rule in grammar.rules for visual_type in rule.visual_types
    }
    missing = {
        item.visual_type for item in visual.visuals if item.visual_type not in grammar_visual_types
    }
    if missing:
        raise TemplateRegistryError(
            "Visual Grammar does not cover Visual Profile types: " + ", ".join(sorted(missing))
        )


def _validate_diagram_intent_coverage(
    visual: VisualProfile,
    grammar: VisualGrammarProfile,
    intent: DiagramIntentProfile,
) -> None:
    intent_by_visual_type = {
        visual_type: item for item in intent.intents for visual_type in item.visual_types
    }
    grammar_by_visual_type = {
        visual_type: rule for rule in grammar.rules for visual_type in rule.visual_types
    }
    missing = {
        item.visual_type for item in visual.visuals if item.visual_type not in intent_by_visual_type
    }
    if missing:
        raise TemplateRegistryError(
            "Diagram Intent does not cover Visual Profile types: " + ", ".join(sorted(missing))
        )
    for visual_item in visual.visuals:
        intent_item = intent_by_visual_type[visual_item.visual_type]
        grammar_rule = grammar_by_visual_type[visual_item.visual_type]
        if grammar_rule.grammar_rule_id not in intent_item.compatible_grammar_rule_ids:
            raise TemplateRegistryError(
                "Diagram Intent is incompatible with Visual Grammar rule: "
                f"{visual_item.visual_type} -> {grammar_rule.grammar_rule_id}"
            )


def _validate_diagram_taxonomy_connections(
    visual: VisualProfile,
    grammar: VisualGrammarProfile | None,
    intent: DiagramIntentProfile | None,
    taxonomy: DiagramTaxonomyProfile | None,
) -> None:
    taxonomy_refs = {
        reference
        for reference in (
            grammar.taxonomy_ref if grammar is not None else None,
            intent.taxonomy_ref if intent is not None else None,
        )
        if reference is not None
    }
    if taxonomy is None:
        if taxonomy_refs:
            raise TemplateRegistryError(
                "Taxonomy-aware Profiles require a Diagram Taxonomy on the Template"
            )
        return
    expected_ref = ProfileReference(
        profile_id=taxonomy.profile_id,
        version=taxonomy.version,
    )
    if grammar is None or intent is None:
        raise TemplateRegistryError(
            "Diagram Taxonomy requires Visual Grammar and Diagram Intent Profiles"
        )
    if grammar.taxonomy_ref != expected_ref or intent.taxonomy_ref != expected_ref:
        raise TemplateRegistryError(
            "Visual Grammar and Diagram Intent must reference the Template Taxonomy"
        )
    active_ids = {
        item.taxonomy_id for item in taxonomy.nodes if item.status == TaxonomyNodeStatus.ACTIVE
    }
    grammar_by_visual_type = {
        visual_type: rule for rule in grammar.rules for visual_type in rule.visual_types
    }
    intent_by_visual_type = {
        visual_type: item for item in intent.intents for visual_type in item.visual_types
    }
    for visual_item in visual.visuals:
        grammar_rule = grammar_by_visual_type[visual_item.visual_type]
        intent_item = intent_by_visual_type[visual_item.visual_type]
        if intent_item.taxonomy_id is None:
            raise TemplateRegistryError("Taxonomy-aware Diagram Intent is missing taxonomy_id")
        if intent_item.taxonomy_id not in active_ids:
            raise TemplateRegistryError(
                "Diagram Intent references unknown or deprecated Taxonomy ID: "
                f"{intent_item.taxonomy_id}"
            )
        unknown_grammar_ids = set(grammar_rule.taxonomy_ids) - active_ids
        if unknown_grammar_ids:
            raise TemplateRegistryError(
                "Visual Grammar references unknown or deprecated Taxonomy IDs: "
                + ", ".join(sorted(unknown_grammar_ids))
            )
        if not any(
            taxonomy.is_ancestor_or_self(grammar_id, intent_item.taxonomy_id)
            for grammar_id in grammar_rule.taxonomy_ids
        ):
            raise TemplateRegistryError(
                "Visual Grammar Taxonomy is incompatible with Diagram Intent: "
                f"{visual_item.visual_type} -> {intent_item.taxonomy_id}"
            )


def _ref_key(reference: ProfileReference) -> tuple[str, str]:
    return reference.profile_id, reference.version


def _version_tuple(version: str) -> tuple[int, int, int]:
    major, minor, patch = version.split(".")
    return int(major), int(minor), int(patch)
