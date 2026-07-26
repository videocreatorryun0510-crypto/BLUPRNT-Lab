"""Versioned, presentation-only contracts for every BLUPRNT Lab Publisher."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from knowledge_contracts.registry_v10 import ClaimKey
from knowledge_contracts.v10.models import ClaimId, KnowledgeId
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=180)]
MediumText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=800)]
StableKey = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$",
        max_length=180,
    ),
]
SemanticVersion = Annotated[str, StringConstraints(pattern=r"^(?:0|[1-9][0-9]*)\.[0-9]+\.[0-9]+$")]
HexColor = Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?$")]


class FrozenModel(BaseModel):
    """Immutable model so Publisher configuration cannot be edited in place."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ProfileStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class OutputKind(StrEnum):
    PDF = "pdf"
    NOTE = "note"
    TRAINING_VIDEO = "training_video"
    NATIONAL_EXAM = "national_exam"


class ProfileReference(FrozenModel):
    profile_id: StableKey
    version: SemanticVersion


class ContentSource(StrEnum):
    KNOWLEDGE_CLAIMS = "knowledge_claims"
    EXAM_METADATA = "exam_metadata"
    REGISTRY_METADATA = "registry_metadata"


class ExamMetadataField(StrEnum):
    IMPORTANCE = "importance"
    FREQUENCY = "frequency"
    HISTORY = "history"
    PRIORITY_CLAIMS = "priority_claims"
    QUESTION_PATTERNS = "question_patterns"
    RELATED_TERMS = "related_terms"
    COMMON_ERRORS = "common_errors"


class RegistryMetadataField(StrEnum):
    KNOWLEDGE_VERSION = "knowledge_version"
    APPROVAL_STATUS = "approval_status"


class ContentSelector(FrozenModel):
    claim_keys: tuple[ClaimKey, ...] = Field(default=(), max_length=200)
    field_path_prefixes: tuple[ShortText, ...] = Field(default=(), max_length=50)
    exam_fields: tuple[ExamMetadataField, ...] = Field(default=(), max_length=7)
    registry_fields: tuple[RegistryMetadataField, ...] = Field(default=(), max_length=2)

    @model_validator(mode="after")
    def require_one_selector(self) -> Self:
        if not any(
            (
                self.claim_keys,
                self.field_path_prefixes,
                self.exam_fields,
                self.registry_fields,
            )
        ):
            raise ValueError("content selector requires at least one source field")
        _require_unique(self.claim_keys, "claim_keys")
        _require_unique(self.field_path_prefixes, "field_path_prefixes")
        _require_unique(self.exam_fields, "exam_fields")
        _require_unique(self.registry_fields, "registry_fields")
        return self


class ContentSection(FrozenModel):
    section_id: StableKey
    content_role: StableKey
    source: ContentSource
    selector: ContentSelector
    priority: int = Field(ge=1, le=100)
    is_required: bool = True
    max_items: int = Field(ge=1, le=200)

    @model_validator(mode="after")
    def keep_source_and_selector_consistent(self) -> Self:
        has_claim_selector = bool(self.selector.claim_keys or self.selector.field_path_prefixes)
        if self.source == ContentSource.KNOWLEDGE_CLAIMS and not has_claim_selector:
            raise ValueError("knowledge claim sections require claim selectors")
        if self.source == ContentSource.EXAM_METADATA and not self.selector.exam_fields:
            raise ValueError("exam metadata sections require exam_fields")
        if self.source == ContentSource.REGISTRY_METADATA and not self.selector.registry_fields:
            raise ValueError("registry metadata sections require registry_fields")
        if self.source != ContentSource.EXAM_METADATA and self.selector.exam_fields:
            raise ValueError("exam_fields can only be used with exam_metadata")
        if self.source != ContentSource.REGISTRY_METADATA and self.selector.registry_fields:
            raise ValueError("registry_fields can only be used with registry_metadata")
        return self


class ContentProfile(FrozenModel):
    schema_version: Literal["1.0"]
    profile_id: StableKey
    version: SemanticVersion
    name: ShortText
    status: ProfileStatus
    supported_outputs: tuple[OutputKind, ...] = Field(min_length=1, max_length=4)
    sections: tuple[ContentSection, ...] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def require_unique_members(self) -> Self:
        _require_unique(self.supported_outputs, "supported_outputs")
        _require_unique(tuple(section.section_id for section in self.sections), "section_id")
        return self


class LearningPurpose(StrEnum):
    NATIONAL_EXAM_PREPARATION = "national_exam_preparation"
    CLINICAL_PRACTICE = "clinical_practice"
    NEW_STAFF_TRAINING = "new_staff_training"
    BEGINNER = "beginner"
    REVIEW = "review"
    MEMORIZATION = "memorization"
    CONCEPTUAL_UNDERSTANDING = "conceptual_understanding"


class DifficultyLevel(StrEnum):
    BASIC = "basic"
    STANDARD = "standard"
    ADVANCED = "advanced"


class ClaimOrderingStrategy(StrEnum):
    CONTENT_PROFILE = "content_profile"
    EDUCATION_SEQUENCE = "education_sequence"
    EXAM_PRIORITY_THEN_EDUCATION = "exam_priority_then_education"


class LearningTargetKind(StrEnum):
    CONTENT_ROLE = "content_role"
    EDUCATION_BLOCK = "education_block"
    VISUAL_TYPE = "visual_type"


class EducationBlockType(StrEnum):
    FREQUENT_POINTS = "frequent_points"
    TRICK_POINTS = "trick_points"
    COMMON_ERRORS = "common_errors"
    MEMORY_AID = "memory_aid"
    RELATED_COMPARISON = "related_comparison"
    EXAM_HISTORY = "exam_history"
    PRIORITY_CLAIM_RANKING = "priority_claim_ranking"


class EducationInputSource(StrEnum):
    KNOWLEDGE_CLAIMS = "knowledge_claims"
    EXAM_METADATA = "exam_metadata"
    PUBLISHER_GENERATED = "publisher_generated"


class LearningLevelPolicy(FrozenModel):
    difficulty_level: DifficultyLevel
    max_claims_per_section: int = Field(ge=1, le=50)
    max_items_per_education_block: int = Field(ge=1, le=100)
    include_optional_content: bool
    include_optional_education_blocks: bool
    include_optional_visuals: bool


class LearningSequenceStep(FrozenModel):
    step_id: StableKey
    target_kind: LearningTargetKind
    target_key: StableKey
    order: int = Field(ge=1, le=300)
    is_required: bool = True


class ExamEmphasisBand(FrozenModel):
    band_id: StableKey
    minimum_score: int = Field(ge=0, le=100)
    emphasis_level: int = Field(ge=1, le=5)
    label: ShortText


class ExamEmphasisPolicy(FrozenModel):
    is_enabled: bool
    frequent_min_appearances: int = Field(ge=1, le=1000)
    show_frequency: bool
    show_importance: bool
    bands: tuple[ExamEmphasisBand, ...] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def require_complete_unique_bands(self) -> Self:
        _require_unique(tuple(item.band_id for item in self.bands), "exam band_id")
        _require_unique(
            tuple(item.minimum_score for item in self.bands),
            "exam minimum_score",
        )
        if not any(item.minimum_score == 0 for item in self.bands):
            raise ValueError("exam emphasis bands require a zero-score fallback")
        return self


class ComparisonPolicy(FrozenModel):
    is_required: bool
    content_roles: tuple[StableKey, ...] = Field(default=(), max_length=20)
    visual_types: tuple[StableKey, ...] = Field(default=(), max_length=20)
    show_related_tests: bool

    @model_validator(mode="after")
    def require_comparison_targets(self) -> Self:
        _require_unique(self.content_roles, "comparison content_roles")
        _require_unique(self.visual_types, "comparison visual_types")
        if self.is_required and not (self.content_roles or self.visual_types):
            raise ValueError("required comparison policy needs content or visual targets")
        return self


class VisualPriorityRule(FrozenModel):
    visual_type: StableKey
    rank: int = Field(ge=1, le=100)
    is_required: bool = False


class EducationBlockRule(FrozenModel):
    block_id: StableKey
    block_type: EducationBlockType
    input_sources: tuple[EducationInputSource, ...] = Field(min_length=1, max_length=3)
    content_roles: tuple[StableKey, ...] = Field(default=(), max_length=20)
    exam_fields: tuple[ExamMetadataField, ...] = Field(default=(), max_length=7)
    order: int = Field(ge=1, le=300)
    is_required: bool
    max_items: int = Field(ge=1, le=100)
    requires_generation: bool = False

    @model_validator(mode="after")
    def keep_inputs_consistent(self) -> Self:
        _require_unique(self.input_sources, "education block input_sources")
        _require_unique(self.content_roles, "education block content_roles")
        _require_unique(self.exam_fields, "education block exam_fields")
        if EducationInputSource.KNOWLEDGE_CLAIMS in self.input_sources and not self.content_roles:
            raise ValueError("knowledge education blocks require content_roles")
        if EducationInputSource.EXAM_METADATA in self.input_sources and not self.exam_fields:
            raise ValueError("exam education blocks require exam_fields")
        if (
            EducationInputSource.PUBLISHER_GENERATED in self.input_sources
            and not self.requires_generation
        ):
            raise ValueError("publisher-generated blocks require generation flag")
        return self


class EducationProfile(FrozenModel):
    schema_version: Literal["1.0"]
    profile_id: StableKey
    version: SemanticVersion
    name: ShortText
    status: ProfileStatus
    supported_outputs: tuple[OutputKind, ...] = Field(min_length=1, max_length=4)
    learning_purposes: tuple[LearningPurpose, ...] = Field(min_length=1, max_length=7)
    level_policy: LearningLevelPolicy
    claim_ordering: ClaimOrderingStrategy
    learning_sequence: tuple[LearningSequenceStep, ...] = Field(min_length=1, max_length=300)
    exam_emphasis: ExamEmphasisPolicy
    comparison_policy: ComparisonPolicy
    visual_priority: tuple[VisualPriorityRule, ...] = Field(default=(), max_length=100)
    education_blocks: tuple[EducationBlockRule, ...] = Field(default=(), max_length=100)

    @model_validator(mode="after")
    def require_unique_education_rules(self) -> Self:
        _require_unique(self.supported_outputs, "education supported_outputs")
        _require_unique(self.learning_purposes, "learning_purposes")
        _require_unique(
            tuple(item.step_id for item in self.learning_sequence),
            "learning step_id",
        )
        _require_unique(
            tuple(item.order for item in self.learning_sequence),
            "learning step order",
        )
        _require_unique(
            tuple(item.visual_type for item in self.visual_priority),
            "education visual_type",
        )
        _require_unique(
            tuple(item.rank for item in self.visual_priority),
            "education visual rank",
        )
        _require_unique(
            tuple(item.block_id for item in self.education_blocks),
            "education block_id",
        )
        return self


class VisualRepresentation(StrEnum):
    SVG = "svg"
    RASTER_IMAGE = "raster_image"
    MERMAID = "mermaid"


class VisualDisplaySize(StrEnum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    FULL_WIDTH = "full_width"


class StructuredVisualPrompt(FrozenModel):
    prompt_schema_version: Literal["1.0"]
    educational_goal: MediumText
    subject: ShortText
    must_show_claim_keys: tuple[ClaimKey, ...] = Field(min_length=1, max_length=50)
    composition_elements: tuple[StableKey, ...] = Field(min_length=1, max_length=30)
    label_claim_keys: tuple[ClaimKey, ...] = Field(default=(), max_length=30)
    style_constraints: tuple[MediumText, ...] = Field(default=(), max_length=30)
    prohibited_elements: tuple[MediumText, ...] = Field(default=(), max_length=30)
    accessibility_goal: MediumText

    @model_validator(mode="after")
    def require_unique_claim_keys(self) -> Self:
        _require_unique(self.must_show_claim_keys, "must_show_claim_keys")
        _require_unique(self.label_claim_keys, "label_claim_keys")
        return self


class VisualGenerationSpec(FrozenModel):
    requires_ai_generation: bool
    capability_id: StableKey | None
    preferred_provider_ids: tuple[StableKey, ...] = Field(default=(), max_length=20)
    structured_prompt: StructuredVisualPrompt | None

    @model_validator(mode="after")
    def require_provider_neutral_prompt(self) -> Self:
        if self.requires_ai_generation and (
            self.capability_id is None or self.structured_prompt is None
        ):
            raise ValueError("AI visual generation requires capability_id and structured_prompt")
        _require_unique(self.preferred_provider_ids, "preferred_provider_ids")
        return self


class VisualSpec(FrozenModel):
    visual_id: StableKey
    visual_type: StableKey
    claim_keys: tuple[ClaimKey, ...] = Field(min_length=1, max_length=100)
    priority: int = Field(ge=1, le=100)
    display_size: VisualDisplaySize
    representation: VisualRepresentation
    caption: ShortText | None
    generation: VisualGenerationSpec
    is_required: bool = False

    @model_validator(mode="after")
    def require_unique_claim_keys(self) -> Self:
        _require_unique(self.claim_keys, "claim_keys")
        if self.generation.structured_prompt is not None:
            prompt_keys = set(self.generation.structured_prompt.must_show_claim_keys)
            if not prompt_keys.issubset(self.claim_keys):
                raise ValueError(
                    "structured prompt must_show_claim_keys must belong to visual claim_keys"
                )
        return self


class VisualProfile(FrozenModel):
    schema_version: Literal["1.0"]
    profile_id: StableKey
    version: SemanticVersion
    name: ShortText
    status: ProfileStatus
    supported_outputs: tuple[OutputKind, ...] = Field(min_length=1, max_length=4)
    visuals: tuple[VisualSpec, ...] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def require_unique_visuals(self) -> Self:
        _require_unique(self.supported_outputs, "supported_outputs")
        _require_unique(tuple(item.visual_id for item in self.visuals), "visual_id")
        return self


class DiagramType(StrEnum):
    REACTION_DIAGRAM = "reaction_diagram"
    COMPARISON_TABLE = "comparison_table"
    FLOWCHART = "flowchart"
    TIMELINE = "timeline"
    ORGAN_DIAGRAM = "organ_diagram"
    CELL_DIAGRAM = "cell_diagram"
    LABORATORY_WORKFLOW = "laboratory_workflow"
    DISEASE_MECHANISM = "disease_mechanism"
    MICROSCOPE_ANNOTATION = "microscope_annotation"


class CompositionPattern(StrEnum):
    LEFT_TO_RIGHT = "left_to_right"
    TOP_TO_BOTTOM = "top_to_bottom"
    CENTERED = "centered"
    RADIAL = "radial"
    COMPARISON_TWO_COLUMN = "comparison_two_column"
    COMPARISON_THREE_COLUMN = "comparison_three_column"
    STEPPED = "stepped"


class NodeType(StrEnum):
    ORGAN = "organ"
    CELL = "cell"
    MOLECULE = "molecule"
    ENZYME = "enzyme"
    SAMPLE = "sample"
    DEVICE = "device"
    DISEASE = "disease"
    LABORATORY_TEST = "laboratory_test"
    PROCESS = "process"
    RESULT = "result"


class ConnectorType(StrEnum):
    ARROW = "arrow"
    BIDIRECTIONAL_ARROW = "bidirectional_arrow"
    DASHED_ARROW = "dashed_arrow"
    GROUP_BOX = "group_box"
    CALLOUT = "callout"


class LabelPosition(StrEnum):
    TOP = "top"
    BOTTOM = "bottom"
    RIGHT = "right"
    CENTER = "center"


class LabelNumbering(StrEnum):
    NONE = "none"
    NUMBERED = "numbered"
    STEP_NUMBERED = "step_numbered"


class HighlightSemantic(StrEnum):
    EXAM_FREQUENT = "exam_frequent"
    IMPORTANT = "important"
    WARNING = "warning"
    POSITIVE = "positive"
    NEGATIVE = "negative"


class HighlightSource(StrEnum):
    KNOWLEDGE_CLAIM = "knowledge_claim"
    EXAM_METADATA = "exam_metadata"
    EDUCATION_PROFILE = "education_profile"


class DiagramDensity(StrEnum):
    COMPACT = "compact"
    STANDARD = "standard"
    DETAILED = "detailed"


class MissingIllustrationPolicy(StrEnum):
    USE_BASIC_SHAPE = "use_basic_shape"
    LABEL_ONLY = "label_only"
    OMIT_OPTIONAL = "omit_optional"


class CompositionRule(FrozenModel):
    pattern: CompositionPattern
    max_primary_tracks: int = Field(ge=1, le=3)
    allow_branching: bool


class NodeRule(FrozenModel):
    node_role: StableKey
    node_type: NodeType
    minimum_count: int = Field(ge=0, le=50)
    maximum_count: int = Field(ge=1, le=50)
    is_required: bool
    claim_binding_required: bool

    @model_validator(mode="after")
    def require_valid_count_range(self) -> Self:
        if self.minimum_count > self.maximum_count:
            raise ValueError("node minimum_count cannot exceed maximum_count")
        if self.is_required and self.minimum_count == 0:
            raise ValueError("required nodes need minimum_count of at least one")
        return self


class ConnectorRule(FrozenModel):
    connector_role: StableKey
    connector_type: ConnectorType
    from_node_role: StableKey
    to_node_role: StableKey
    is_required: bool
    claim_binding_required: bool


class LabelRule(FrozenModel):
    position: LabelPosition
    numbering: LabelNumbering
    allow_supplement: bool
    claim_reference_required: bool


class HighlightRule(FrozenModel):
    highlight_id: StableKey
    semantic: HighlightSemantic
    source: HighlightSource
    target_node_roles: tuple[StableKey, ...] = Field(min_length=1, max_length=30)
    is_required: bool

    @model_validator(mode="after")
    def require_unique_targets(self) -> Self:
        _require_unique(self.target_node_roles, "highlight target_node_roles")
        return self


class DensityRule(FrozenModel):
    level: DiagramDensity
    maximum_nodes: int = Field(ge=1, le=100)
    maximum_connectors: int = Field(ge=0, le=200)
    maximum_highlights: int = Field(ge=0, le=50)


class IllustrationSlot(FrozenModel):
    slot_id: StableKey
    node_role: StableKey
    accepted_asset_namespaces: tuple[StableKey, ...] = Field(min_length=1, max_length=20)
    preferred_asset_ids: tuple[StableKey, ...] = Field(default=(), max_length=20)
    is_required: bool
    missing_asset_policy: MissingIllustrationPolicy

    @model_validator(mode="after")
    def require_unique_asset_hints(self) -> Self:
        _require_unique(
            self.accepted_asset_namespaces,
            "illustration accepted_asset_namespaces",
        )
        _require_unique(self.preferred_asset_ids, "illustration preferred_asset_ids")
        if (
            self.is_required
            and self.missing_asset_policy == MissingIllustrationPolicy.OMIT_OPTIONAL
        ):
            raise ValueError("required illustration slots cannot use omit_optional")
        return self


class IllustrationLibraryHook(FrozenModel):
    contract_version: Literal["1.0"]
    resolver_capability_id: StableKey
    supported_asset_namespaces: tuple[StableKey, ...] = Field(min_length=1, max_length=50)
    default_missing_asset_policy: MissingIllustrationPolicy
    store_assets_in_knowledge: Literal[False]

    @model_validator(mode="after")
    def require_unique_namespaces(self) -> Self:
        _require_unique(self.supported_asset_namespaces, "illustration asset namespaces")
        return self


class DiagramGrammarRule(FrozenModel):
    grammar_rule_id: StableKey
    diagram_type: DiagramType
    visual_types: tuple[StableKey, ...] = Field(min_length=1, max_length=30)
    taxonomy_ids: tuple[StableKey, ...] = Field(default=(), max_length=100)
    composition: CompositionRule
    nodes: tuple[NodeRule, ...] = Field(min_length=1, max_length=50)
    connectors: tuple[ConnectorRule, ...] = Field(default=(), max_length=100)
    label_rule: LabelRule
    highlights: tuple[HighlightRule, ...] = Field(default=(), max_length=30)
    density: DensityRule
    illustration_slots: tuple[IllustrationSlot, ...] = Field(default=(), max_length=30)

    @model_validator(mode="after")
    def validate_internal_grammar(self) -> Self:
        _require_unique(self.visual_types, "grammar visual_types")
        _require_unique(self.taxonomy_ids, "grammar taxonomy_ids")
        node_roles = tuple(item.node_role for item in self.nodes)
        _require_unique(node_roles, "grammar node_role")
        _require_unique(
            tuple(item.connector_role for item in self.connectors),
            "grammar connector_role",
        )
        _require_unique(
            tuple(item.highlight_id for item in self.highlights),
            "grammar highlight_id",
        )
        _require_unique(
            tuple(item.slot_id for item in self.illustration_slots),
            "grammar illustration slot_id",
        )
        known_nodes = set(node_roles)
        for connector in self.connectors:
            if (
                connector.from_node_role not in known_nodes
                or connector.to_node_role not in known_nodes
            ):
                raise ValueError("connector references an unknown node_role")
        for highlight in self.highlights:
            if not set(highlight.target_node_roles).issubset(known_nodes):
                raise ValueError("highlight references an unknown node_role")
        for slot in self.illustration_slots:
            if slot.node_role not in known_nodes:
                raise ValueError("illustration slot references an unknown node_role")
        if sum(item.maximum_count for item in self.nodes) > self.density.maximum_nodes:
            raise ValueError("node rules exceed the diagram density maximum")
        if len(self.connectors) > self.density.maximum_connectors:
            raise ValueError("connector rules exceed the diagram density maximum")
        if len(self.highlights) > self.density.maximum_highlights:
            raise ValueError("highlight rules exceed the diagram density maximum")
        return self


class VisualGrammarProfile(FrozenModel):
    schema_version: Literal["1.0", "1.1"]
    profile_id: StableKey
    version: SemanticVersion
    name: ShortText
    status: ProfileStatus
    supported_outputs: tuple[OutputKind, ...] = Field(min_length=1, max_length=4)
    taxonomy_ref: ProfileReference | None = None
    illustration_library_hook: IllustrationLibraryHook
    rules: tuple[DiagramGrammarRule, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def require_unique_grammar_bindings(self) -> Self:
        _require_unique(self.supported_outputs, "visual grammar supported_outputs")
        _require_unique(
            tuple(item.grammar_rule_id for item in self.rules),
            "visual grammar_rule_id",
        )
        all_visual_types = tuple(
            visual_type for rule in self.rules for visual_type in rule.visual_types
        )
        _require_unique(all_visual_types, "visual grammar visual_type binding")
        has_taxonomy_ids = any(rule.taxonomy_ids for rule in self.rules)
        if self.schema_version == "1.0" and (self.taxonomy_ref is not None or has_taxonomy_ids):
            raise ValueError("Visual Grammar 1.0 cannot contain Diagram Taxonomy data")
        if self.schema_version == "1.1" and (
            self.taxonomy_ref is None or any(not rule.taxonomy_ids for rule in self.rules)
        ):
            raise ValueError("Visual Grammar 1.1 requires a Taxonomy reference on every rule")
        supported_namespaces = set(self.illustration_library_hook.supported_asset_namespaces)
        for rule in self.rules:
            for slot in rule.illustration_slots:
                if not set(slot.accepted_asset_namespaces).issubset(supported_namespaces):
                    raise ValueError("illustration slot uses an unsupported asset namespace")
        return self


class DiagramIntentType(StrEnum):
    MEASUREMENT_PRINCIPLE = "measurement_principle"
    BIOCHEMICAL_REACTION = "biochemical_reaction"
    DISEASE_MECHANISM = "disease_mechanism"
    LABORATORY_WORKFLOW = "laboratory_workflow"
    DIAGNOSTIC_FLOW = "diagnostic_flow"
    CELL_MORPHOLOGY = "cell_morphology"
    ORGAN_RELATIONSHIP = "organ_relationship"
    COMPARISON = "comparison"
    LIFE_CYCLE = "life_cycle"
    SIGNAL_PATHWAY = "signal_pathway"


class DiagramEducationalGoal(StrEnum):
    UNDERSTAND_PRINCIPLE = "understand_principle"
    COMPARE_CONCEPTS = "compare_concepts"
    UNDERSTAND_SEQUENCE = "understand_sequence"
    UNDERSTAND_PATHOPHYSIOLOGY = "understand_pathophysiology"
    UNDERSTAND_EXAM_POINTS = "understand_exam_points"


class SemanticConceptType(StrEnum):
    SAMPLE = "sample"
    ANALYTE = "analyte"
    REAGENT = "reagent"
    REACTION = "reaction"
    DETECTION = "detection"
    RESULT = "result"
    CAUSE = "cause"
    PATHOLOGY = "pathology"
    FINDING = "finding"
    DIAGNOSIS = "diagnosis"
    TISSUE = "tissue"
    DAMAGE = "damage"
    BIOMARKER = "biomarker"
    WORKFLOW_STEP = "workflow_step"
    CELL_FEATURE = "cell_feature"
    ORGAN = "organ"
    SUBJECT = "subject"
    COMPARATOR = "comparator"
    COMPARISON_AXIS = "comparison_axis"
    INTERPRETATION = "interpretation"
    LIFE_CYCLE_STAGE = "life_cycle_stage"
    SIGNAL = "signal"


class ConceptRequirement(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"


class SemanticSequenceKind(StrEnum):
    LINEAR = "linear"
    COMPARISON = "comparison"
    BRANCHING = "branching"


class SemanticRelation(StrEnum):
    PRECEDES = "precedes"
    TRANSFORMS_TO = "transforms_to"
    DETECTED_BY = "detected_by"
    PRODUCES = "produces"
    LEADS_TO = "leads_to"
    COMPARED_WITH = "compared_with"
    ASSOCIATED_WITH = "associated_with"
    CAUSES = "causes"
    MEASURES = "measures"
    CONTAINS = "contains"
    COMPARES = "compares"
    DERIVED_FROM = "derived_from"
    FLOWS_TO = "flows_to"


class IntentConcept(FrozenModel):
    concept_id: StableKey
    concept_type: SemanticConceptType
    requirement: ConceptRequirement


class SemanticSequenceStep(FrozenModel):
    step_id: StableKey
    concept_id: StableKey
    order: int = Field(ge=1, le=100)
    relation_to_next: SemanticRelation | None = None


class SemanticSequence(FrozenModel):
    sequence_id: StableKey
    kind: SemanticSequenceKind
    steps: tuple[SemanticSequenceStep, ...] = Field(min_length=2, max_length=100)

    @model_validator(mode="after")
    def validate_semantic_order(self) -> Self:
        _require_unique(tuple(item.step_id for item in self.steps), "intent sequence step_id")
        _require_unique(tuple(item.order for item in self.steps), "intent sequence order")
        ordered = sorted(self.steps, key=lambda item: item.order)
        expected_orders = list(range(1, len(ordered) + 1))
        if [item.order for item in ordered] != expected_orders:
            raise ValueError("intent sequence order must be contiguous from one")
        if any(item.relation_to_next is None for item in ordered[:-1]):
            raise ValueError("non-final intent sequence steps require relation_to_next")
        if ordered[-1].relation_to_next is not None:
            raise ValueError("final intent sequence step cannot have relation_to_next")
        return self


class ClaimMatchCriterion(StrEnum):
    FIELD_PATH_PREFIX = "field_path_prefix"
    CLAIM_KEY_PREFIX = "claim_key_prefix"
    EXAM_PRIORITY = "exam_priority"


class MissingConceptPolicy(StrEnum):
    REPORT_AND_BLOCK_BLUEPRINT = "report_and_block_blueprint"
    REPORT_AND_ALLOW_PARTIAL = "report_and_allow_partial"


class ConceptClaimMappingRule(FrozenModel):
    concept_id: StableKey
    source_field_path_prefixes: tuple[StableKey, ...] = Field(default=(), max_length=30)
    source_claim_key_prefixes: tuple[StableKey, ...] = Field(default=(), max_length=30)
    minimum_claims: int = Field(ge=0, le=20)
    maximum_claims: int = Field(ge=1, le=100)
    approved_only: Literal[True]

    @model_validator(mode="after")
    def validate_claim_selection_rule(self) -> Self:
        _require_unique(
            self.source_field_path_prefixes,
            "intent source_field_path_prefixes",
        )
        _require_unique(
            self.source_claim_key_prefixes,
            "intent source_claim_key_prefixes",
        )
        if not (self.source_field_path_prefixes or self.source_claim_key_prefixes):
            raise ValueError("intent claim mapping rule requires a source selector")
        if self.minimum_claims > self.maximum_claims:
            raise ValueError("minimum_claims cannot exceed maximum_claims")
        return self


class ClaimMappingStrategy(FrozenModel):
    strategy_id: StableKey
    matching_order: tuple[ClaimMatchCriterion, ...] = Field(min_length=1, max_length=3)
    concept_rules: tuple[ConceptClaimMappingRule, ...] = Field(min_length=1, max_length=100)
    allow_claim_reuse: bool
    missing_required_concept_policy: MissingConceptPolicy

    @model_validator(mode="after")
    def require_unique_mapping_rules(self) -> Self:
        _require_unique(self.matching_order, "intent claim matching_order")
        _require_unique(
            tuple(item.concept_id for item in self.concept_rules),
            "intent claim mapping concept_id",
        )
        return self


class IllustrationCategory(StrEnum):
    ORGAN = "organ"
    CELL = "cell"
    INSTRUMENT = "instrument"
    MOLECULE = "molecule"
    MICROORGANISM = "microorganism"
    PARASITE = "parasite"
    SAMPLE = "sample"
    TUBE = "tube"
    ICON = "icon"


class IntentIllustrationRequirement(FrozenModel):
    concept_id: StableKey
    category: IllustrationCategory
    is_required: bool


class DiagramIntentDefinition(FrozenModel):
    intent_id: StableKey
    intent_type: DiagramIntentType | None = None
    taxonomy_id: StableKey | None = None
    visual_types: tuple[StableKey, ...] = Field(min_length=1, max_length=30)
    compatible_grammar_rule_ids: tuple[StableKey, ...] = Field(min_length=1, max_length=30)
    educational_goals: tuple[DiagramEducationalGoal, ...] = Field(min_length=1, max_length=5)
    concepts: tuple[IntentConcept, ...] = Field(min_length=1, max_length=100)
    semantic_sequences: tuple[SemanticSequence, ...] = Field(min_length=1, max_length=20)
    claim_mapping_strategy: ClaimMappingStrategy
    illustration_requirements: tuple[IntentIllustrationRequirement, ...] = Field(
        default=(), max_length=100
    )

    @model_validator(mode="after")
    def validate_intent_references(self) -> Self:
        if (self.intent_type is None) == (self.taxonomy_id is None):
            raise ValueError("Diagram Intent must use either legacy intent_type or taxonomy_id")
        _require_unique(self.visual_types, "diagram intent visual_types")
        _require_unique(
            self.compatible_grammar_rule_ids,
            "diagram intent compatible_grammar_rule_ids",
        )
        _require_unique(self.educational_goals, "diagram intent educational_goals")
        concept_ids = tuple(item.concept_id for item in self.concepts)
        _require_unique(concept_ids, "diagram intent concept_id")
        _require_unique(
            tuple(item.sequence_id for item in self.semantic_sequences),
            "diagram intent sequence_id",
        )
        _require_unique(
            tuple(
                f"{item.concept_id}:{item.category.value}"
                for item in self.illustration_requirements
            ),
            "diagram intent illustration concept/category",
        )
        known_concepts = set(concept_ids)
        sequence_concepts = {
            step.concept_id for sequence in self.semantic_sequences for step in sequence.steps
        }
        mapping_concepts = {item.concept_id for item in self.claim_mapping_strategy.concept_rules}
        illustration_concepts = {item.concept_id for item in self.illustration_requirements}
        if not sequence_concepts.issubset(known_concepts):
            raise ValueError("semantic sequence references an unknown intent concept")
        if not mapping_concepts.issubset(known_concepts):
            raise ValueError("claim mapping references an unknown intent concept")
        if not illustration_concepts.issubset(known_concepts):
            raise ValueError("illustration requirement references an unknown intent concept")
        required_concepts = {
            item.concept_id
            for item in self.concepts
            if item.requirement == ConceptRequirement.REQUIRED
        }
        if not required_concepts.issubset(mapping_concepts):
            raise ValueError("every required intent concept needs a claim mapping rule")
        mappings_by_concept = {
            item.concept_id: item for item in self.claim_mapping_strategy.concept_rules
        }
        if any(
            mappings_by_concept[concept_id].minimum_claims == 0 for concept_id in required_concepts
        ):
            raise ValueError("required intent concepts need at least one future Claim")
        return self


class DiagramIntentProfile(FrozenModel):
    schema_version: Literal["1.0", "1.1"]
    profile_id: StableKey
    version: SemanticVersion
    name: ShortText
    status: ProfileStatus
    supported_outputs: tuple[OutputKind, ...] = Field(min_length=1, max_length=4)
    taxonomy_ref: ProfileReference | None = None
    intents: tuple[DiagramIntentDefinition, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def require_unique_intent_bindings(self) -> Self:
        _require_unique(self.supported_outputs, "diagram intent supported_outputs")
        _require_unique(
            tuple(item.intent_id for item in self.intents),
            "diagram intent_id",
        )
        all_visual_types = tuple(
            visual_type for intent in self.intents for visual_type in intent.visual_types
        )
        _require_unique(all_visual_types, "diagram intent visual_type binding")
        if self.schema_version == "1.0" and (
            self.taxonomy_ref is not None
            or any(item.taxonomy_id is not None for item in self.intents)
            or any(item.intent_type is None for item in self.intents)
        ):
            raise ValueError("Diagram Intent 1.0 requires legacy intent_type only")
        if self.schema_version == "1.1" and (
            self.taxonomy_ref is None
            or any(item.taxonomy_id is None for item in self.intents)
            or any(item.intent_type is not None for item in self.intents)
        ):
            raise ValueError("Diagram Intent 1.1 requires Taxonomy ID references only")
        return self


class LayoutRegion(FrozenModel):
    region_id: StableKey
    region_role: StableKey
    order: int = Field(ge=1, le=200)
    parent_region_id: StableKey | None = None


class PlacementKind(StrEnum):
    CONTENT = "content"
    EDUCATION_BLOCK = "education_block"
    VISUAL = "visual"


class LayoutPlacement(FrozenModel):
    placement_id: StableKey
    item_kind: PlacementKind
    item_id: StableKey
    region_id: StableKey
    order: int = Field(ge=1, le=200)
    is_optional: bool = False


class LayoutProfile(FrozenModel):
    schema_version: Literal["1.0"]
    profile_id: StableKey
    version: SemanticVersion
    name: ShortText
    status: ProfileStatus
    supported_outputs: tuple[OutputKind, ...] = Field(min_length=1, max_length=4)
    regions: tuple[LayoutRegion, ...] = Field(min_length=1, max_length=100)
    placements: tuple[LayoutPlacement, ...] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_layout_graph(self) -> Self:
        _require_unique(self.supported_outputs, "supported_outputs")
        region_ids = tuple(item.region_id for item in self.regions)
        _require_unique(region_ids, "region_id")
        _require_unique(tuple(item.placement_id for item in self.placements), "placement_id")
        known_regions = set(region_ids)
        for region in self.regions:
            if region.parent_region_id is not None:
                if region.parent_region_id not in known_regions:
                    raise ValueError("layout parent region does not exist")
                if region.parent_region_id == region.region_id:
                    raise ValueError("layout region cannot be its own parent")
        for placement in self.placements:
            if placement.region_id not in known_regions:
                raise ValueError("layout placement points to an unknown region")
        _require_acyclic_regions(self.regions)
        return self


class ColorToken(FrozenModel):
    token: StableKey
    value: HexColor


class FontToken(FrozenModel):
    role: StableKey
    family: ShortText
    fallback_families: tuple[ShortText, ...] = Field(default=(), max_length=10)
    weight: int = Field(ge=100, le=900, multiple_of=100)


class SpacingToken(FrozenModel):
    token: StableKey
    value_rem: float = Field(ge=0, le=20)


class ComponentStyleRule(FrozenModel):
    component: StableKey
    variant: StableKey
    token_refs: tuple[StableKey, ...] = Field(min_length=1, max_length=50)


class CharacterStyle(FrozenModel):
    is_enabled: bool
    asset_family_id: StableKey | None
    position_token: StableKey | None

    @model_validator(mode="after")
    def require_character_tokens_when_enabled(self) -> Self:
        if self.is_enabled and (self.asset_family_id is None or self.position_token is None):
            raise ValueError("enabled character style requires asset and position")
        return self


class ThemeProfile(FrozenModel):
    schema_version: Literal["1.0"]
    profile_id: StableKey
    version: SemanticVersion
    name: ShortText
    status: ProfileStatus
    colors: tuple[ColorToken, ...] = Field(min_length=1, max_length=100)
    fonts: tuple[FontToken, ...] = Field(min_length=1, max_length=30)
    spacing: tuple[SpacingToken, ...] = Field(min_length=1, max_length=50)
    icon_set_id: StableKey
    border_style_id: StableKey
    heading_style_id: StableKey
    caption_style_id: StableKey
    telop_style_id: StableKey
    character: CharacterStyle
    component_styles: tuple[ComponentStyleRule, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def require_unique_tokens(self) -> Self:
        _require_unique(tuple(item.token for item in self.colors), "color token")
        _require_unique(tuple(item.role for item in self.fonts), "font role")
        _require_unique(tuple(item.token for item in self.spacing), "spacing token")
        pairs = tuple(f"{item.component}:{item.variant}" for item in self.component_styles)
        _require_unique(pairs, "component style")
        return self


class SeriesCompositionRule(FrozenModel):
    output_kind: OutputKind
    layout_ref: ProfileReference
    required_component_variants: tuple[StableKey, ...] = Field(min_length=1, max_length=100)


class DesignSystem(FrozenModel):
    schema_version: Literal["1.0"]
    profile_id: StableKey
    version: SemanticVersion
    series_id: StableKey
    name: ShortText
    status: ProfileStatus
    theme_ref: ProfileReference
    consistency_mode: Literal["strict"]
    composition_rules: tuple[SeriesCompositionRule, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def require_one_composition_per_output(self) -> Self:
        _require_unique(
            tuple(rule.output_kind for rule in self.composition_rules),
            "design-system output_kind",
        )
        return self


class TemplateDefinition(FrozenModel):
    schema_version: Literal["1.0"]
    template_id: StableKey
    version: SemanticVersion
    template_family: StableKey
    name: ShortText
    status: ProfileStatus
    output_kind: OutputKind
    series_id: StableKey
    content_profile_ref: ProfileReference
    education_profile_ref: ProfileReference | None = None
    visual_profile_ref: ProfileReference
    visual_grammar_profile_ref: ProfileReference | None = None
    diagram_intent_profile_ref: ProfileReference | None = None
    diagram_taxonomy_ref: ProfileReference | None = None
    layout_profile_ref: ProfileReference
    theme_ref: ProfileReference
    design_system_ref: ProfileReference
    media_profile_ref: ProfileReference | None = None


class PublicationRequest(FrozenModel):
    request_id: StableKey
    template_ref: ProfileReference
    knowledge_id: KnowledgeId
    education_profile_ref: ProfileReference | None = None
    visual_grammar_profile_ref: ProfileReference | None = None
    diagram_intent_profile_ref: ProfileReference | None = None


class ClaimReference(FrozenModel):
    claim_id: ClaimId
    claim_key: ClaimKey
    claim_version: int = Field(ge=1)


class PlannedContentSection(FrozenModel):
    section_id: StableKey
    content_role: StableKey
    source: ContentSource
    claim_refs: tuple[ClaimReference, ...]
    exam_fields: tuple[ExamMetadataField, ...]
    registry_fields: tuple[RegistryMetadataField, ...]


class PlannedVisual(FrozenModel):
    visual_id: StableKey
    visual_type: StableKey
    claim_refs: tuple[ClaimReference, ...]
    priority: int = Field(ge=1, le=100)
    display_size: VisualDisplaySize
    representation: VisualRepresentation
    caption: ShortText | None
    generation: VisualGenerationSpec


class PlannedPlacement(FrozenModel):
    placement_id: StableKey
    item_kind: PlacementKind
    item_id: StableKey
    region_id: StableKey
    order: int = Field(ge=1, le=200)


class PlannedEducationBlock(FrozenModel):
    block_id: StableKey
    block_type: EducationBlockType
    order: int = Field(ge=1, le=300)
    is_required: bool
    claim_refs: tuple[ClaimReference, ...]
    exam_fields: tuple[ExamMetadataField, ...]
    max_items: int = Field(ge=1, le=100)
    generation_required: bool


class PlannedLearningStep(FrozenModel):
    step_id: StableKey
    target_kind: LearningTargetKind
    target_key: StableKey
    order: int = Field(ge=1, le=300)
    resolved_item_ids: tuple[StableKey, ...] = Field(min_length=1, max_length=100)
    claim_refs: tuple[ClaimReference, ...] = Field(default=(), max_length=200)


class PlannedVisualPriority(FrozenModel):
    visual_id: StableKey
    visual_type: StableKey
    rank: int = Field(ge=1, le=1000)
    is_required: bool


class PlannedVisualGrammar(FrozenModel):
    visual_id: StableKey
    visual_type: StableKey
    grammar_rule_id: StableKey
    diagram_type: DiagramType
    taxonomy_ids: tuple[StableKey, ...] = ()
    composition: CompositionRule
    nodes: tuple[NodeRule, ...]
    connectors: tuple[ConnectorRule, ...]
    label_rule: LabelRule
    highlights: tuple[HighlightRule, ...]
    density: DensityRule
    illustration_slots: tuple[IllustrationSlot, ...]


class PlannedDiagramIntent(FrozenModel):
    visual_id: StableKey
    visual_type: StableKey
    grammar_rule_id: StableKey
    intent_id: StableKey
    intent_type: DiagramIntentType | None = None
    taxonomy_id: StableKey | None = None
    educational_goals: tuple[DiagramEducationalGoal, ...]
    concepts: tuple[IntentConcept, ...]
    semantic_sequences: tuple[SemanticSequence, ...]
    claim_mapping_strategy: ClaimMappingStrategy
    illustration_requirements: tuple[IntentIllustrationRequirement, ...]

    @model_validator(mode="after")
    def require_one_classification_source(self) -> Self:
        if (self.intent_type is None) == (self.taxonomy_id is None):
            raise ValueError("planned Diagram Intent needs either intent_type or taxonomy_id")
        return self


class PlannedDiagramTaxonomy(FrozenModel):
    visual_id: StableKey
    taxonomy_id: StableKey
    taxonomy_path: tuple[StableKey, ...] = Field(min_length=1, max_length=30)
    root_taxonomy_id: StableKey
    root_intent_type: DiagramIntentType

    @model_validator(mode="after")
    def validate_path(self) -> Self:
        if self.taxonomy_path[0] != self.root_taxonomy_id:
            raise ValueError("taxonomy path must start at root_taxonomy_id")
        if self.taxonomy_path[-1] != self.taxonomy_id:
            raise ValueError("taxonomy path must end at taxonomy_id")
        if len(self.taxonomy_path) != len(set(self.taxonomy_path)):
            raise ValueError("taxonomy path cannot contain repeated nodes")
        return self


class PlannedComparisonPriority(FrozenModel):
    is_required: bool
    content_section_ids: tuple[StableKey, ...]
    visual_ids: tuple[StableKey, ...]
    show_related_tests: bool


class PlannedExamPriority(FrozenModel):
    importance_score: int | None = Field(default=None, ge=0, le=100)
    frequency_count: int = Field(ge=0, le=1000)
    emphasis_level: int = Field(ge=1, le=5)
    label: ShortText
    priority_claim_refs: tuple[ClaimReference, ...] = Field(default=(), max_length=200)


class PublicationPlan(FrozenModel):
    plan_schema_version: Literal["1.0", "1.1", "1.2", "1.3", "1.4"]
    request_id: StableKey
    output_kind: OutputKind
    knowledge_id: KnowledgeId
    knowledge_content_revision: int = Field(ge=1)
    registry_knowledge_version: int = Field(ge=1)
    exam_metadata_revision: int | None = Field(ge=1)
    template_ref: ProfileReference
    content_profile_ref: ProfileReference
    education_profile_ref: ProfileReference | None = None
    visual_profile_ref: ProfileReference
    visual_grammar_profile_ref: ProfileReference | None = None
    diagram_intent_profile_ref: ProfileReference | None = None
    diagram_taxonomy_ref: ProfileReference | None = None
    layout_profile_ref: ProfileReference
    theme_ref: ProfileReference
    design_system_ref: ProfileReference
    media_profile_ref: ProfileReference | None
    content_sections: tuple[PlannedContentSection, ...]
    learning_purposes: tuple[LearningPurpose, ...] = ()
    difficulty_level: DifficultyLevel | None = None
    learning_sequence: tuple[PlannedLearningStep, ...] = ()
    education_blocks: tuple[PlannedEducationBlock, ...] = ()
    visual_priority: tuple[PlannedVisualPriority, ...] = ()
    visual_grammar_bindings: tuple[PlannedVisualGrammar, ...] = ()
    diagram_intent_bindings: tuple[PlannedDiagramIntent, ...] = ()
    diagram_taxonomy_bindings: tuple[PlannedDiagramTaxonomy, ...] = ()
    illustration_library_hook: IllustrationLibraryHook | None = None
    comparison_priority: PlannedComparisonPriority | None = None
    exam_priority: PlannedExamPriority | None = None
    visuals: tuple[PlannedVisual, ...]
    placements: tuple[PlannedPlacement, ...]
    source_fingerprint: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]

    @model_validator(mode="after")
    def keep_plan_version_compatible(self) -> Self:
        has_education = self.education_profile_ref is not None
        education_payload = any(
            (
                self.learning_purposes,
                self.difficulty_level is not None,
                self.learning_sequence,
                self.education_blocks,
                self.visual_priority,
                self.comparison_priority is not None,
                self.exam_priority is not None,
            )
        )
        has_visual_grammar = self.visual_grammar_profile_ref is not None
        visual_grammar_payload = bool(
            self.visual_grammar_bindings or self.illustration_library_hook is not None
        )
        has_diagram_intent = self.diagram_intent_profile_ref is not None
        diagram_intent_payload = bool(self.diagram_intent_bindings)
        has_diagram_taxonomy = self.diagram_taxonomy_ref is not None
        diagram_taxonomy_payload = bool(self.diagram_taxonomy_bindings)
        if self.plan_schema_version == "1.0" and (
            has_education
            or education_payload
            or has_visual_grammar
            or visual_grammar_payload
            or has_diagram_intent
            or diagram_intent_payload
            or has_diagram_taxonomy
            or diagram_taxonomy_payload
        ):
            raise ValueError("Publication Plan 1.0 cannot contain later Profile data")
        if self.plan_schema_version == "1.1":
            if not has_education or self.difficulty_level is None or not self.learning_sequence:
                raise ValueError("Publication Plan 1.1 requires resolved Education Profile data")
            if (
                has_visual_grammar
                or visual_grammar_payload
                or has_diagram_intent
                or diagram_intent_payload
                or has_diagram_taxonomy
                or diagram_taxonomy_payload
            ):
                raise ValueError("Publication Plan 1.1 cannot contain Visual Grammar data")
        if self.plan_schema_version == "1.2":
            if (
                not has_education
                or self.difficulty_level is None
                or not self.learning_sequence
                or not has_visual_grammar
                or not self.visual_grammar_bindings
                or self.illustration_library_hook is None
            ):
                raise ValueError("Publication Plan 1.2 requires Education and Visual Grammar data")
            if (
                has_diagram_intent
                or diagram_intent_payload
                or has_diagram_taxonomy
                or diagram_taxonomy_payload
            ):
                raise ValueError("Publication Plan 1.2 cannot contain Diagram Intent data")
        if self.plan_schema_version == "1.3":
            if (
                not has_education
                or self.difficulty_level is None
                or not self.learning_sequence
                or not has_visual_grammar
                or not self.visual_grammar_bindings
                or self.illustration_library_hook is None
                or not has_diagram_intent
                or not self.diagram_intent_bindings
            ):
                raise ValueError(
                    "Publication Plan 1.3 requires Education, Visual Grammar "
                    "and Diagram Intent data"
                )
            if has_diagram_taxonomy or diagram_taxonomy_payload:
                raise ValueError("Publication Plan 1.3 cannot contain Diagram Taxonomy data")
        if self.plan_schema_version == "1.4" and (
            not has_education
            or self.difficulty_level is None
            or not self.learning_sequence
            or not has_visual_grammar
            or not self.visual_grammar_bindings
            or self.illustration_library_hook is None
            or not has_diagram_intent
            or not self.diagram_intent_bindings
            or not has_diagram_taxonomy
            or not self.diagram_taxonomy_bindings
        ):
            raise ValueError(
                "Publication Plan 1.4 requires Education, Visual Grammar, "
                "Diagram Intent and Taxonomy data"
            )
        if has_visual_grammar:
            visual_ids = {item.visual_id for item in self.visuals}
            binding_ids = {item.visual_id for item in self.visual_grammar_bindings}
            if visual_ids != binding_ids:
                raise ValueError("every planned Visual requires one Grammar binding")
        if has_diagram_intent:
            visual_ids = {item.visual_id for item in self.visuals}
            intent_visual_ids = {item.visual_id for item in self.diagram_intent_bindings}
            if visual_ids != intent_visual_ids:
                raise ValueError("every planned Visual requires one Diagram Intent binding")
            grammar_by_visual = {
                item.visual_id: item.grammar_rule_id for item in self.visual_grammar_bindings
            }
            if any(
                grammar_by_visual.get(item.visual_id) != item.grammar_rule_id
                for item in self.diagram_intent_bindings
            ):
                raise ValueError("Diagram Intent must reference the planned Visual Grammar rule")
        if has_diagram_taxonomy:
            visual_ids = {item.visual_id for item in self.visuals}
            taxonomy_by_visual = {item.visual_id: item for item in self.diagram_taxonomy_bindings}
            if visual_ids != set(taxonomy_by_visual):
                raise ValueError("every planned Visual requires one Diagram Taxonomy binding")
            intent_by_visual = {item.visual_id: item for item in self.diagram_intent_bindings}
            grammar_binding_by_visual = {
                item.visual_id: item for item in self.visual_grammar_bindings
            }
            if any(
                intent_by_visual[visual_id].taxonomy_id != binding.taxonomy_id
                for visual_id, binding in taxonomy_by_visual.items()
            ):
                raise ValueError("Diagram Intent must reference its planned Taxonomy node")
            if any(
                not set(grammar_binding_by_visual[visual_id].taxonomy_ids).intersection(
                    binding.taxonomy_path
                )
                for visual_id, binding in taxonomy_by_visual.items()
            ):
                raise ValueError("Visual Grammar must reference the planned Taxonomy path")
        return self


class VisualAssetReference(FrozenModel):
    """Provider-neutral pointer returned by a future visual generator."""

    asset_id: StableKey
    visual_id: StableKey
    representation: VisualRepresentation
    provider_id: StableKey
    asset_uri: MediumText
    content_hash: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class PublicationArtifact(FrozenModel):
    """Common result contract for future PDF, note, video and exam adapters."""

    artifact_id: StableKey
    output_kind: OutputKind
    media_type: ShortText
    artifact_uri: MediumText
    content_hash: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    plan_source_fingerprint: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


def _require_unique(values: tuple[object, ...], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} values must be unique")


def _require_acyclic_regions(regions: tuple[LayoutRegion, ...]) -> None:
    parents = {
        item.region_id: item.parent_region_id
        for item in regions
        if item.parent_region_id is not None
    }
    for region_id in parents:
        current: StableKey | None = region_id
        seen: set[str] = set()
        while current is not None and current in parents:
            if current in seen:
                raise ValueError(f"layout region cycle detected: {region_id}")
            seen.add(current)
            current = parents[current]
