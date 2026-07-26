"""Resolve a shared Publication Plan into an immutable PDF render plan."""

from pathlib import Path

from knowledge_contracts.exam_v10 import ExamSection
from knowledge_contracts.registry_v10 import RegistryStatus
from publisher_core import (
    ExamMetadataField,
    OutputKind,
    PublicationPlan,
    PublicationSourceBundle,
    RegistryMetadataField,
    ResolvedTemplate,
    publication_source_fingerprint,
)

from pdf_publisher.models import (
    PdfRenderPlan,
    RenderContentBlock,
    RenderPlacement,
    RenderVisualBlock,
)


class PublicationPlanReadError(ValueError):
    """Raised when a Plan and its immutable source snapshot do not match."""


ROLE_TITLES = {
    "role.definition": "ASTをひとことで",
    "role.measurement_method": "測定法",
    "role.measurement_principle": "測定原理",
    "role.exam_points": "国家試験ポイント",
    "role.comparison": "関連検査との比較",
    "role.cautions": "解釈時の注意",
}

VISUAL_TITLES = {
    "diagram.reaction": "Reaction Diagram",
    "diagram.organ_distribution": "Organ Distribution",
    "table.comparison": "Comparison Table",
    "diagram.flowchart": "Flowchart",
}


class PublicationPlanReader:
    def load(self, path: Path) -> PublicationPlan:
        try:
            return PublicationPlan.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise PublicationPlanReadError(f"Publication Planを読み込めません: {error}") from error

    def resolve(
        self,
        plan: PublicationPlan,
        source: PublicationSourceBundle,
        profiles: ResolvedTemplate,
    ) -> PdfRenderPlan:
        self._validate_plan(plan, source, profiles)
        claims_by_id = {item.claim_id: item for item in source.registry.claims}
        content_blocks: list[RenderContentBlock] = []
        for section in plan.content_sections:
            items: list[str] = []
            claim_ids: list[str] = []
            for claim_ref in section.claim_refs:
                claim = claims_by_id.get(claim_ref.claim_id)
                if claim is None or claim.status != RegistryStatus.APPROVED:
                    raise PublicationPlanReadError(
                        f"承認済みClaimを解決できません: {claim_ref.claim_id}"
                    )
                if claim.claim_version != claim_ref.claim_version:
                    raise PublicationPlanReadError(
                        f"Claim Versionが一致しません: {claim_ref.claim_id}"
                    )
                items.append(claim.assertion)
                claim_ids.append(claim.claim_id)
            items.extend(self._exam_items(section.exam_fields, source))
            items.extend(self._registry_items(section.registry_fields, source))
            if not items:
                continue
            content_blocks.append(
                RenderContentBlock(
                    block_id=section.section_id,
                    title=ROLE_TITLES.get(
                        section.content_role, section.content_role.replace("role.", "")
                    ),
                    items=tuple(items),
                    source_claim_ids=tuple(claim_ids),
                )
            )
        visual_blocks = tuple(
            RenderVisualBlock(
                block_id=visual.visual_id,
                visual_type=visual.visual_type,
                title=VISUAL_TITLES.get(visual.visual_type, visual.visual_type),
                caption=visual.caption,
                representation=visual.representation,
                claim_keys=tuple(item.claim_key for item in visual.claim_refs),
                requires_ai_generation=visual.generation.requires_ai_generation,
            )
            for visual in plan.visuals
        )
        return PdfRenderPlan(
            render_plan_version="1.0",
            request_id=plan.request_id,
            title=source.registry.knowledge.canonical_name,
            subtitle=(
                "臨床検査技師国家試験対策 / "
                f"Knowledge v{source.registry.knowledge.knowledge_version} / "
                f"Template {profiles.template.version}"
            ),
            review_badge="PDF構造レビュー用 / 医学監修前",
            content_blocks=tuple(content_blocks),
            visual_blocks=visual_blocks,
            placements=tuple(
                RenderPlacement(
                    placement_id=item.placement_id,
                    item_kind=item.item_kind,
                    item_id=item.item_id,
                    region_id=item.region_id,
                    order=item.order,
                )
                for item in plan.placements
            ),
            layout_profile_ref=plan.layout_profile_ref,
            theme_ref=plan.theme_ref,
            design_system_ref=plan.design_system_ref,
            source_fingerprint=plan.source_fingerprint,
        )

    def _validate_plan(
        self,
        plan: PublicationPlan,
        source: PublicationSourceBundle,
        profiles: ResolvedTemplate,
    ) -> None:
        if plan.output_kind != OutputKind.PDF:
            raise PublicationPlanReadError("PDF AdapterにはPDF用Planが必要です。")
        if plan.education_profile_ref is not None:
            raise PublicationPlanReadError(
                "Phase 3.2のEducation PlanはPDF未対応です。教育ブロックを欠落させず、"
                "次Phaseの接続まで生成を停止します。"
            )
        if plan.source_fingerprint != publication_source_fingerprint(source):
            raise PublicationPlanReadError(
                "Publication PlanとKnowledge SourceのFingerprintが一致しません。"
            )
        expected = (
            profiles.template.content_profile_ref,
            profiles.template.visual_profile_ref,
            profiles.template.layout_profile_ref,
            profiles.template.theme_ref,
            profiles.template.design_system_ref,
        )
        actual = (
            plan.content_profile_ref,
            plan.visual_profile_ref,
            plan.layout_profile_ref,
            plan.theme_ref,
            plan.design_system_ref,
        )
        if actual != expected:
            raise PublicationPlanReadError(
                "Publication PlanとTemplate RegistryのProfile Versionが一致しません。"
            )
        if profiles.design_system.consistency_mode != "strict":
            raise PublicationPlanReadError("strict Design Systemが必要です。")

    def _exam_items(
        self,
        fields: tuple[ExamMetadataField, ...],
        source: PublicationSourceBundle,
    ) -> tuple[str, ...]:
        metadata = source.exam_metadata
        if metadata is None:
            return ()
        items: list[str] = []
        for field in fields:
            if field == ExamMetadataField.IMPORTANCE and metadata.importance is not None:
                items.append(f"国家試験重要度: {metadata.importance.importance_score}/100")
            elif field == ExamMetadataField.FREQUENCY:
                frequency = metadata.frequency
                items.append(
                    "出題履歴: "
                    f"{frequency.appearance_count}回 / "
                    f"初出 第{frequency.first_session_number}回 / "
                    f"最新 第{frequency.latest_session_number}回"
                )
            elif field == ExamMetadataField.HISTORY:
                items.extend(
                    f"第{entry.session_number}回 "
                    f"{_section_label(entry.section)} 問{entry.question_number}"
                    for entry in metadata.history[:5]
                )
            elif field == ExamMetadataField.PRIORITY_CLAIMS:
                items.append(f"国家試験重要Claim: {len(metadata.priority_claims)}件")
            elif field == ExamMetadataField.QUESTION_PATTERNS:
                items.extend(
                    f"出題形式: {_pattern_label(entry.pattern.value)}"
                    for entry in metadata.question_patterns
                )
            elif field == ExamMetadataField.RELATED_TERMS:
                items.extend(f"関連用語: {entry.term}" for entry in metadata.related_terms)
            elif field == ExamMetadataField.COMMON_ERRORS:
                items.extend(
                    f"よくある誤り: {entry.misconception}" for entry in metadata.common_errors
                )
        return tuple(items)

    def _registry_items(
        self,
        fields: tuple[RegistryMetadataField, ...],
        source: PublicationSourceBundle,
    ) -> tuple[str, ...]:
        items: list[str] = []
        for field in fields:
            if field == RegistryMetadataField.KNOWLEDGE_VERSION:
                items.append(f"Knowledge Version: {source.registry.knowledge.knowledge_version}")
            elif field == RegistryMetadataField.APPROVAL_STATUS:
                items.append(f"承認状態: {source.registry.knowledge.status.value}")
        return tuple(items)


def _section_label(section: ExamSection) -> str:
    return {
        ExamSection.MORNING: "午前",
        ExamSection.AFTERNOON: "午後",
        ExamSection.UNSPECIFIED: "区分未指定",
    }[section]


def _pattern_label(pattern: str) -> str:
    return {
        "standalone_knowledge": "単独知識",
        "differential": "鑑別問題",
        "image": "画像問題",
        "calculation": "計算問題",
        "elimination": "消去法",
        "combination": "組み合わせ問題",
    }.get(pattern, pattern)
