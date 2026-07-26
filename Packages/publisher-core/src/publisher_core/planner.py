"""Create a medium-neutral plan by reference; do not render or rewrite knowledge."""

from knowledge_contracts.exam_v10 import ExamMetadataRecord, MemorizationPriority
from knowledge_contracts.registry_v10 import ClaimRegistryEntry, RegistryStatus

from publisher_core.catalog import ResolvedTemplate, TemplateRegistry
from publisher_core.diagram_taxonomy import DiagramTaxonomyProfile
from publisher_core.models import (
    ClaimOrderingStrategy,
    ClaimReference,
    ContentSection,
    ContentSource,
    DiagramIntentProfile,
    EducationProfile,
    ExamEmphasisBand,
    ExamMetadataField,
    LearningSequenceStep,
    LearningTargetKind,
    PlacementKind,
    PlannedComparisonPriority,
    PlannedContentSection,
    PlannedDiagramIntent,
    PlannedDiagramTaxonomy,
    PlannedEducationBlock,
    PlannedExamPriority,
    PlannedLearningStep,
    PlannedPlacement,
    PlannedVisual,
    PlannedVisualGrammar,
    PlannedVisualPriority,
    ProfileReference,
    PublicationPlan,
    PublicationRequest,
    VisualGrammarProfile,
    VisualSpec,
)
from publisher_core.source import (
    PublicationSourceBundle,
    publication_source_fingerprint,
)


class PublisherPlanError(ValueError):
    """Raised when approved source facts cannot satisfy a selected Template."""


class PublisherPlanner:
    """Shared planner used before PDF, note, video or exam-specific rendering."""

    def __init__(self, registry: TemplateRegistry) -> None:
        self._registry = registry

    def build_plan(
        self, source: PublicationSourceBundle, request: PublicationRequest
    ) -> PublicationPlan:
        if request.knowledge_id != source.knowledge.knowledge_id:
            raise PublisherPlanError("request knowledge_id does not match source")
        resolved = self._registry.resolve(request.template_ref)
        education = self._resolve_education(resolved, request)
        visual_grammar = self._resolve_visual_grammar(resolved, request)
        diagram_intent = self._resolve_diagram_intent(resolved, request)
        diagram_taxonomy = resolved.diagram_taxonomy
        self._validate_diagram_taxonomy_selection(
            diagram_taxonomy,
            visual_grammar,
            diagram_intent,
        )
        approved_claims = _approved_claim_index(source)
        sections = tuple(
            self._plan_content_section(
                section,
                approved_claims,
                source.exam_metadata,
                education,
            )
            for section in resolved.content_profile.sections
            if self._section_is_available(
                section,
                approved_claims,
                source.exam_metadata,
                education,
            )
        )
        sections = _order_content_sections(sections, education)

        required_visual_types = _required_visual_types(education)
        visuals = tuple(
            planned
            for visual in resolved.visual_profile.visuals
            if _include_visual(visual, education, required_visual_types)
            if (
                planned := self._plan_visual(
                    visual,
                    approved_claims,
                    required_override=visual.visual_type in required_visual_types,
                )
            )
            is not None
        )
        visuals = _order_visuals(visuals, education)
        visual_grammar_bindings = self._plan_visual_grammar(
            visual_grammar,
            visuals,
        )
        diagram_intent_bindings = self._plan_diagram_intents(
            diagram_intent,
            visual_grammar_bindings,
        )
        diagram_taxonomy_bindings = self._plan_diagram_taxonomy(
            diagram_taxonomy,
            diagram_intent_bindings,
        )
        education_blocks = self._plan_education_blocks(
            education,
            sections,
            source.exam_metadata,
        )
        comparison_priority = self._plan_comparison_priority(
            education,
            sections,
            visuals,
        )
        exam_priority = self._plan_exam_priority(education, source)
        visual_priority = self._plan_visual_priority(
            education,
            visuals,
            resolved,
        )
        learning_sequence = self._plan_learning_sequence(
            education,
            sections,
            education_blocks,
            visuals,
        )
        placements = self._plan_placements(
            resolved,
            sections,
            education_blocks,
            visuals,
        )
        education_ref = (
            ProfileReference(profile_id=education.profile_id, version=education.version)
            if education is not None
            else None
        )
        visual_grammar_ref = (
            ProfileReference(
                profile_id=visual_grammar.profile_id,
                version=visual_grammar.version,
            )
            if visual_grammar is not None
            else None
        )
        diagram_intent_ref = (
            ProfileReference(
                profile_id=diagram_intent.profile_id,
                version=diagram_intent.version,
            )
            if diagram_intent is not None
            else None
        )
        diagram_taxonomy_ref = (
            ProfileReference(
                profile_id=diagram_taxonomy.profile_id,
                version=diagram_taxonomy.version,
            )
            if diagram_taxonomy is not None
            else None
        )
        return PublicationPlan(
            plan_schema_version=(
                "1.4"
                if diagram_taxonomy is not None
                else "1.3"
                if diagram_intent is not None
                else "1.2"
                if visual_grammar is not None
                else "1.1"
                if education is not None
                else "1.0"
            ),
            request_id=request.request_id,
            output_kind=resolved.template.output_kind,
            knowledge_id=source.knowledge.knowledge_id,
            knowledge_content_revision=source.knowledge.content_revision,
            registry_knowledge_version=source.registry.knowledge.knowledge_version,
            exam_metadata_revision=(
                source.exam_metadata.metadata_revision if source.exam_metadata is not None else None
            ),
            template_ref=request.template_ref,
            content_profile_ref=resolved.template.content_profile_ref,
            education_profile_ref=education_ref,
            visual_profile_ref=resolved.template.visual_profile_ref,
            visual_grammar_profile_ref=visual_grammar_ref,
            diagram_intent_profile_ref=diagram_intent_ref,
            diagram_taxonomy_ref=diagram_taxonomy_ref,
            layout_profile_ref=resolved.template.layout_profile_ref,
            theme_ref=resolved.template.theme_ref,
            design_system_ref=resolved.template.design_system_ref,
            media_profile_ref=resolved.template.media_profile_ref,
            content_sections=sections,
            learning_purposes=(education.learning_purposes if education is not None else ()),
            difficulty_level=(
                education.level_policy.difficulty_level if education is not None else None
            ),
            learning_sequence=learning_sequence,
            education_blocks=education_blocks,
            visual_priority=visual_priority,
            visual_grammar_bindings=visual_grammar_bindings,
            diagram_intent_bindings=diagram_intent_bindings,
            diagram_taxonomy_bindings=diagram_taxonomy_bindings,
            illustration_library_hook=(
                visual_grammar.illustration_library_hook if visual_grammar is not None else None
            ),
            comparison_priority=comparison_priority,
            exam_priority=exam_priority,
            visuals=visuals,
            placements=placements,
            source_fingerprint=publication_source_fingerprint(source),
        )

    def _resolve_education(
        self,
        resolved: ResolvedTemplate,
        request: PublicationRequest,
    ) -> EducationProfile | None:
        if request.education_profile_ref is None:
            return resolved.education_profile
        return self._registry.resolve_education(
            request.education_profile_ref,
            output_kind=resolved.template.output_kind,
        )

    def _resolve_visual_grammar(
        self,
        resolved: ResolvedTemplate,
        request: PublicationRequest,
    ) -> VisualGrammarProfile | None:
        if request.visual_grammar_profile_ref is None:
            return resolved.visual_grammar_profile
        return self._registry.resolve_visual_grammar(
            request.visual_grammar_profile_ref,
            output_kind=resolved.template.output_kind,
        )

    def _resolve_diagram_intent(
        self,
        resolved: ResolvedTemplate,
        request: PublicationRequest,
    ) -> DiagramIntentProfile | None:
        if request.diagram_intent_profile_ref is None:
            return resolved.diagram_intent_profile
        return self._registry.resolve_diagram_intent(
            request.diagram_intent_profile_ref,
            output_kind=resolved.template.output_kind,
        )

    @staticmethod
    def _validate_diagram_taxonomy_selection(
        taxonomy: DiagramTaxonomyProfile | None,
        grammar: VisualGrammarProfile | None,
        intent: DiagramIntentProfile | None,
    ) -> None:
        if taxonomy is None:
            if (grammar is not None and grammar.taxonomy_ref is not None) or (
                intent is not None and intent.taxonomy_ref is not None
            ):
                raise PublisherPlanError(
                    "Taxonomy-aware Profile cannot be used without Template Taxonomy"
                )
            return
        expected = ProfileReference(
            profile_id=taxonomy.profile_id,
            version=taxonomy.version,
        )
        if grammar is None or intent is None:
            raise PublisherPlanError("Template Taxonomy requires Visual Grammar and Diagram Intent")
        if grammar.taxonomy_ref != expected or intent.taxonomy_ref != expected:
            raise PublisherPlanError(
                "selected Visual Grammar and Diagram Intent must use Template Taxonomy"
            )

    def _section_is_available(
        self,
        section: ContentSection,
        approved_claims: dict[str, ClaimRegistryEntry],
        exam_metadata: ExamMetadataRecord | None,
        education: EducationProfile | None,
    ) -> bool:
        if (
            education is not None
            and not education.level_policy.include_optional_content
            and not section.is_required
        ):
            return False
        claim_refs = _select_claims(section, approved_claims)
        exam_fields = _select_exam_fields(section, exam_metadata)
        registry_fields = section.selector.registry_fields
        is_available = bool(claim_refs or exam_fields or registry_fields)
        if section.is_required and not is_available:
            raise PublisherPlanError(
                f"required Content section has no approved source: {section.section_id}"
            )
        return is_available

    def _plan_content_section(
        self,
        section: ContentSection,
        approved_claims: dict[str, ClaimRegistryEntry],
        exam_metadata: ExamMetadataRecord | None,
        education: EducationProfile | None,
    ) -> PlannedContentSection:
        claims = _select_claims(section, approved_claims)
        if education is not None:
            claims = _order_claims(claims, exam_metadata, education.claim_ordering)
        limit = section.max_items
        if education is not None:
            limit = min(limit, education.level_policy.max_claims_per_section)
        return PlannedContentSection(
            section_id=section.section_id,
            content_role=section.content_role,
            source=section.source,
            claim_refs=claims[:limit],
            exam_fields=_select_exam_fields(section, exam_metadata),
            registry_fields=section.selector.registry_fields,
        )

    def _plan_visual(
        self,
        visual: VisualSpec,
        approved_claims: dict[str, ClaimRegistryEntry],
        *,
        required_override: bool,
    ) -> PlannedVisual | None:
        selected = tuple(
            _claim_reference(approved_claims[key])
            for key in visual.claim_keys
            if key in approved_claims
        )
        if len(selected) != len(visual.claim_keys):
            if visual.is_required or required_override:
                raise PublisherPlanError(
                    f"required Visual has missing approved claims: {visual.visual_id}"
                )
            return None
        return PlannedVisual(
            visual_id=visual.visual_id,
            visual_type=visual.visual_type,
            claim_refs=selected,
            priority=visual.priority,
            display_size=visual.display_size,
            representation=visual.representation,
            caption=visual.caption,
            generation=visual.generation,
        )

    def _plan_education_blocks(
        self,
        education: EducationProfile | None,
        sections: tuple[PlannedContentSection, ...],
        exam_metadata: ExamMetadataRecord | None,
    ) -> tuple[PlannedEducationBlock, ...]:
        if education is None:
            return ()
        blocks: list[PlannedEducationBlock] = []
        for rule in sorted(education.education_blocks, key=lambda item: item.order):
            if (
                not education.level_policy.include_optional_education_blocks
                and not rule.is_required
            ):
                continue
            claims = _claims_for_content_roles(rule.content_roles, sections)
            exam_fields = tuple(
                field
                for field in rule.exam_fields
                if exam_metadata is not None and _exam_field_has_value(exam_metadata, field)
            )
            is_available = bool(claims or exam_fields or rule.requires_generation)
            if rule.is_required and not is_available:
                raise PublisherPlanError(f"required Education block has no source: {rule.block_id}")
            if not is_available:
                continue
            limit = min(
                rule.max_items,
                education.level_policy.max_items_per_education_block,
            )
            blocks.append(
                PlannedEducationBlock(
                    block_id=rule.block_id,
                    block_type=rule.block_type,
                    order=rule.order,
                    is_required=rule.is_required,
                    claim_refs=claims[:limit],
                    exam_fields=exam_fields[:limit],
                    max_items=limit,
                    generation_required=rule.requires_generation,
                )
            )
        return tuple(blocks)

    def _plan_visual_grammar(
        self,
        grammar: VisualGrammarProfile | None,
        visuals: tuple[PlannedVisual, ...],
    ) -> tuple[PlannedVisualGrammar, ...]:
        if grammar is None:
            return ()
        rules_by_visual_type = {
            visual_type: rule for rule in grammar.rules for visual_type in rule.visual_types
        }
        planned: list[PlannedVisualGrammar] = []
        for visual in visuals:
            rule = rules_by_visual_type.get(visual.visual_type)
            if rule is None:
                raise PublisherPlanError(
                    f"Visual Grammar is missing for visual_type: {visual.visual_type}"
                )
            planned.append(
                PlannedVisualGrammar(
                    visual_id=visual.visual_id,
                    visual_type=visual.visual_type,
                    grammar_rule_id=rule.grammar_rule_id,
                    diagram_type=rule.diagram_type,
                    taxonomy_ids=rule.taxonomy_ids,
                    composition=rule.composition,
                    nodes=rule.nodes,
                    connectors=rule.connectors,
                    label_rule=rule.label_rule,
                    highlights=rule.highlights,
                    density=rule.density,
                    illustration_slots=rule.illustration_slots,
                )
            )
        return tuple(planned)

    def _plan_diagram_intents(
        self,
        intent_profile: DiagramIntentProfile | None,
        grammar_bindings: tuple[PlannedVisualGrammar, ...],
    ) -> tuple[PlannedDiagramIntent, ...]:
        if intent_profile is None:
            return ()
        if not grammar_bindings:
            raise PublisherPlanError("Diagram Intent requires planned Visual Grammar")
        intents_by_visual_type = {
            visual_type: intent
            for intent in intent_profile.intents
            for visual_type in intent.visual_types
        }
        planned: list[PlannedDiagramIntent] = []
        for grammar in grammar_bindings:
            intent = intents_by_visual_type.get(grammar.visual_type)
            if intent is None:
                raise PublisherPlanError(
                    f"Diagram Intent is missing for visual_type: {grammar.visual_type}"
                )
            if grammar.grammar_rule_id not in intent.compatible_grammar_rule_ids:
                raise PublisherPlanError(
                    "Diagram Intent is incompatible with planned Visual Grammar: "
                    f"{grammar.grammar_rule_id}"
                )
            planned.append(
                PlannedDiagramIntent(
                    visual_id=grammar.visual_id,
                    visual_type=grammar.visual_type,
                    grammar_rule_id=grammar.grammar_rule_id,
                    intent_id=intent.intent_id,
                    intent_type=intent.intent_type,
                    taxonomy_id=intent.taxonomy_id,
                    educational_goals=intent.educational_goals,
                    concepts=intent.concepts,
                    semantic_sequences=intent.semantic_sequences,
                    claim_mapping_strategy=intent.claim_mapping_strategy,
                    illustration_requirements=intent.illustration_requirements,
                )
            )
        return tuple(planned)

    def _plan_diagram_taxonomy(
        self,
        taxonomy: DiagramTaxonomyProfile | None,
        intents: tuple[PlannedDiagramIntent, ...],
    ) -> tuple[PlannedDiagramTaxonomy, ...]:
        if taxonomy is None:
            return ()
        planned: list[PlannedDiagramTaxonomy] = []
        for intent in intents:
            if intent.taxonomy_id is None:
                raise PublisherPlanError(
                    f"Diagram Intent is missing taxonomy_id: {intent.intent_id}"
                )
            try:
                path = taxonomy.lineage_ids(intent.taxonomy_id)
            except KeyError as error:
                raise PublisherPlanError(
                    f"Diagram Intent references unknown taxonomy_id: {intent.taxonomy_id}"
                ) from error
            planned.append(
                PlannedDiagramTaxonomy(
                    visual_id=intent.visual_id,
                    taxonomy_id=intent.taxonomy_id,
                    taxonomy_path=path,
                    root_taxonomy_id=path[0],
                    root_intent_type=taxonomy.root_intent_type(intent.taxonomy_id),
                )
            )
        return tuple(planned)

    def _plan_comparison_priority(
        self,
        education: EducationProfile | None,
        sections: tuple[PlannedContentSection, ...],
        visuals: tuple[PlannedVisual, ...],
    ) -> PlannedComparisonPriority | None:
        if education is None:
            return None
        policy = education.comparison_policy
        section_ids = tuple(
            item.section_id for item in sections if item.content_role in policy.content_roles
        )
        visual_ids = tuple(
            item.visual_id for item in visuals if item.visual_type in policy.visual_types
        )
        if policy.is_required:
            missing_content = policy.content_roles and not section_ids
            missing_visual = policy.visual_types and not visual_ids
            if missing_content or missing_visual:
                raise PublisherPlanError("required comparison content or visual is not available")
        return PlannedComparisonPriority(
            is_required=policy.is_required,
            content_section_ids=section_ids,
            visual_ids=visual_ids,
            show_related_tests=policy.show_related_tests,
        )

    def _plan_exam_priority(
        self,
        education: EducationProfile | None,
        source: PublicationSourceBundle,
    ) -> PlannedExamPriority | None:
        if education is None or not education.exam_emphasis.is_enabled:
            return None
        metadata = source.exam_metadata
        score = (
            metadata.importance.importance_score
            if metadata is not None and metadata.importance is not None
            else None
        )
        frequency_count = metadata.frequency.appearance_count if metadata is not None else 0
        band = _select_exam_band(education, score, frequency_count)
        claims_by_id = _approved_claim_id_index(source)
        priority_claims: tuple[ClaimReference, ...] = ()
        if metadata is not None:
            ranked = sorted(
                metadata.priority_claims,
                key=lambda item: _memorization_priority_rank(item.priority),
            )
            priority_claims = tuple(
                _claim_reference(claims_by_id[item.claim_id])
                for item in ranked
                if item.claim_id in claims_by_id
            )
        return PlannedExamPriority(
            importance_score=score,
            frequency_count=frequency_count,
            emphasis_level=band.emphasis_level,
            label=band.label,
            priority_claim_refs=priority_claims,
        )

    def _plan_visual_priority(
        self,
        education: EducationProfile | None,
        visuals: tuple[PlannedVisual, ...],
        resolved: ResolvedTemplate,
    ) -> tuple[PlannedVisualPriority, ...]:
        if education is None:
            return ()
        rules = {item.visual_type: item for item in education.visual_priority}
        required_specs = {
            item.visual_type for item in resolved.visual_profile.visuals if item.is_required
        }
        return tuple(
            PlannedVisualPriority(
                visual_id=visual.visual_id,
                visual_type=visual.visual_type,
                rank=(rules[visual.visual_type].rank if visual.visual_type in rules else 1000),
                is_required=(
                    visual.visual_type in required_specs
                    or (visual.visual_type in rules and rules[visual.visual_type].is_required)
                ),
            )
            for visual in visuals
        )

    def _plan_learning_sequence(
        self,
        education: EducationProfile | None,
        sections: tuple[PlannedContentSection, ...],
        blocks: tuple[PlannedEducationBlock, ...],
        visuals: tuple[PlannedVisual, ...],
    ) -> tuple[PlannedLearningStep, ...]:
        if education is None:
            return ()
        planned: list[PlannedLearningStep] = []
        for step in sorted(education.learning_sequence, key=lambda item: item.order):
            item_ids, claims = _resolve_learning_target(step, sections, blocks, visuals)
            if not item_ids:
                if step.is_required:
                    raise PublisherPlanError(
                        f"required learning step cannot be resolved: {step.step_id}"
                    )
                continue
            planned.append(
                PlannedLearningStep(
                    step_id=step.step_id,
                    target_kind=step.target_kind,
                    target_key=step.target_key,
                    order=step.order,
                    resolved_item_ids=item_ids,
                    claim_refs=claims,
                )
            )
        return tuple(planned)

    def _plan_placements(
        self,
        resolved: ResolvedTemplate,
        sections: tuple[PlannedContentSection, ...],
        education_blocks: tuple[PlannedEducationBlock, ...],
        visuals: tuple[PlannedVisual, ...],
    ) -> tuple[PlannedPlacement, ...]:
        known_by_kind = {
            PlacementKind.CONTENT: {item.section_id for item in sections},
            PlacementKind.EDUCATION_BLOCK: {item.block_id for item in education_blocks},
            PlacementKind.VISUAL: {item.visual_id for item in visuals},
        }
        planned: list[PlannedPlacement] = []
        for placement in resolved.layout_profile.placements:
            if placement.item_id not in known_by_kind[placement.item_kind]:
                if placement.is_optional:
                    continue
                raise PublisherPlanError(
                    f"required Layout item is not available: {placement.item_id}"
                )
            planned.append(
                PlannedPlacement(
                    placement_id=placement.placement_id,
                    item_kind=placement.item_kind,
                    item_id=placement.item_id,
                    region_id=placement.region_id,
                    order=placement.order,
                )
            )
        return tuple(planned)


def _select_claims(
    section: ContentSection, approved_claims: dict[str, ClaimRegistryEntry]
) -> tuple[ClaimReference, ...]:
    if section.source != ContentSource.KNOWLEDGE_CLAIMS:
        return ()
    selected: list[ClaimRegistryEntry] = []
    for key in section.selector.claim_keys:
        if key in approved_claims:
            selected.append(approved_claims[key])
    for claim in sorted(approved_claims.values(), key=lambda item: item.claim_key):
        if any(
            claim.field_path.startswith(prefix) for prefix in section.selector.field_path_prefixes
        ):
            selected.append(claim)
    unique = {item.claim_id: item for item in selected}
    return tuple(_claim_reference(item) for item in unique.values())


def _approved_claim_index(
    source: PublicationSourceBundle,
) -> dict[str, ClaimRegistryEntry]:
    active_by_id = _approved_claim_id_index(source)
    indexed = {item.claim_key: item for item in active_by_id.values()}
    for redirect in source.registry.merge_redirects:
        target = active_by_id.get(redirect.target_claim_id)
        if target is not None:
            indexed[redirect.source_claim_key] = target
    return indexed


def _approved_claim_id_index(
    source: PublicationSourceBundle,
) -> dict[str, ClaimRegistryEntry]:
    active_by_id = {
        item.claim_id: item
        for item in source.registry.claims
        if item.status == RegistryStatus.APPROVED and not item.is_deleted
    }
    for redirect in source.registry.merge_redirects:
        target = active_by_id.get(redirect.target_claim_id)
        if target is not None:
            active_by_id[redirect.source_claim_id] = target
    return active_by_id


def _select_exam_fields(
    section: ContentSection, exam_metadata: ExamMetadataRecord | None
) -> tuple[ExamMetadataField, ...]:
    if section.source != ContentSource.EXAM_METADATA or exam_metadata is None:
        return ()
    return tuple(
        field
        for field in section.selector.exam_fields
        if _exam_field_has_value(exam_metadata, field)
    )


def _exam_field_has_value(exam_metadata: ExamMetadataRecord, field: ExamMetadataField) -> bool:
    value = getattr(exam_metadata, field.value)
    return value is not None and (not hasattr(value, "__len__") or len(value) > 0)


def _claim_reference(claim: ClaimRegistryEntry) -> ClaimReference:
    return ClaimReference(
        claim_id=claim.claim_id,
        claim_key=claim.claim_key,
        claim_version=claim.claim_version,
    )


def _include_visual(
    visual: VisualSpec,
    education: EducationProfile | None,
    required_visual_types: set[str],
) -> bool:
    if education is None or education.level_policy.include_optional_visuals:
        return True
    return visual.is_required or visual.visual_type in required_visual_types


def _required_visual_types(education: EducationProfile | None) -> set[str]:
    if education is None:
        return set()
    required = {item.visual_type for item in education.visual_priority if item.is_required}
    if education.comparison_policy.is_required:
        required.update(education.comparison_policy.visual_types)
    return required


def _order_content_sections(
    sections: tuple[PlannedContentSection, ...],
    education: EducationProfile | None,
) -> tuple[PlannedContentSection, ...]:
    if education is None:
        return sections
    order = {
        item.target_key: item.order
        for item in education.learning_sequence
        if item.target_kind == LearningTargetKind.CONTENT_ROLE
    }
    original = {item.section_id: index for index, item in enumerate(sections)}
    return tuple(
        sorted(
            sections,
            key=lambda item: (
                order.get(item.content_role, 10_000),
                original[item.section_id],
            ),
        )
    )


def _order_visuals(
    visuals: tuple[PlannedVisual, ...],
    education: EducationProfile | None,
) -> tuple[PlannedVisual, ...]:
    if education is None:
        return visuals
    order = {item.visual_type: item.rank for item in education.visual_priority}
    return tuple(
        sorted(
            visuals,
            key=lambda item: (order.get(item.visual_type, 1000), -item.priority),
        )
    )


def _order_claims(
    claims: tuple[ClaimReference, ...],
    exam_metadata: ExamMetadataRecord | None,
    strategy: ClaimOrderingStrategy,
) -> tuple[ClaimReference, ...]:
    if strategy != ClaimOrderingStrategy.EXAM_PRIORITY_THEN_EDUCATION:
        return claims
    priority_order = (
        {item.claim_id: index for index, item in enumerate(exam_metadata.priority_claims)}
        if exam_metadata is not None
        else {}
    )
    original = {item.claim_id: index for index, item in enumerate(claims)}
    return tuple(
        sorted(
            claims,
            key=lambda item: (
                priority_order.get(item.claim_id, 10_000),
                original[item.claim_id],
            ),
        )
    )


def _claims_for_content_roles(
    content_roles: tuple[str, ...],
    sections: tuple[PlannedContentSection, ...],
) -> tuple[ClaimReference, ...]:
    selected = [
        claim
        for section in sections
        if section.content_role in content_roles
        for claim in section.claim_refs
    ]
    unique = {item.claim_id: item for item in selected}
    return tuple(unique.values())


def _select_exam_band(
    education: EducationProfile,
    score: int | None,
    frequency_count: int,
) -> ExamEmphasisBand:
    bands = sorted(
        education.exam_emphasis.bands,
        key=lambda item: item.minimum_score,
        reverse=True,
    )
    selected = next(item for item in bands if (score or 0) >= item.minimum_score)
    if frequency_count >= education.exam_emphasis.frequent_min_appearances:
        frequent = next(
            (item for item in bands if item.band_id.endswith(".frequent")),
            None,
        )
        if frequent is not None and frequent.emphasis_level > selected.emphasis_level:
            selected = frequent
    return selected


def _memorization_priority_rank(priority: MemorizationPriority) -> int:
    return {
        MemorizationPriority.HIGHEST: 1,
        MemorizationPriority.IMPORTANT: 2,
        MemorizationPriority.SUPPLEMENTARY: 3,
    }[priority]


def _resolve_learning_target(
    step: LearningSequenceStep,
    sections: tuple[PlannedContentSection, ...],
    blocks: tuple[PlannedEducationBlock, ...],
    visuals: tuple[PlannedVisual, ...],
) -> tuple[tuple[str, ...], tuple[ClaimReference, ...]]:
    if step.target_kind == LearningTargetKind.CONTENT_ROLE:
        matching = tuple(item for item in sections if item.content_role == step.target_key)
        item_ids = tuple(item.section_id for item in matching)
        claims = tuple(claim for item in matching for claim in item.claim_refs)
    elif step.target_kind == LearningTargetKind.EDUCATION_BLOCK:
        matching_blocks = tuple(item for item in blocks if item.block_id == step.target_key)
        item_ids = tuple(item.block_id for item in matching_blocks)
        claims = tuple(claim for item in matching_blocks for claim in item.claim_refs)
    else:
        matching_visuals = tuple(item for item in visuals if item.visual_type == step.target_key)
        item_ids = tuple(item.visual_id for item in matching_visuals)
        claims = tuple(claim for item in matching_visuals for claim in item.claim_refs)
    unique = {item.claim_id: item for item in claims}
    return item_ids, tuple(unique.values())
