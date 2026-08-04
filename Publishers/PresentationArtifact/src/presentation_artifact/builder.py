"""Deterministic page composer for Presentation Artifact Version 1.0."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from knowledge_contracts.v10 import KnowledgeRecord
from presentation_request_builder import PresentationRequest
from source_bundle_publisher import SourceBundle

from presentation_artifact.audit import JsonlArtifactAuditLogger
from presentation_artifact.fingerprint import (
    artifact_fingerprint,
    source_bundle_id,
    stable_block_id,
)
from presentation_artifact.models import (
    ArtifactAuditRecord,
    ArtifactBodyBlock,
    ArtifactBuildResult,
    ArtifactClaim,
    ArtifactDiagramItem,
    ArtifactIdentity,
    ArtifactMetadata,
    ArtifactPresentationProfile,
    ArtifactReference,
    ArtifactSource,
    BodyBlockType,
    DiagramInstruction,
    LayoutComposition,
    LayoutDensity,
    LayoutHint,
    PageType,
    PresentationArtifact,
    PresentationPage,
)
from presentation_artifact.validator import PresentationArtifactValidator
from presentation_artifact.writer import PresentationArtifactJsonWriter


class PresentationArtifactBuilder:
    """Compose pages while copying medical facts exactly from the Source Bundle."""

    builder_version: Literal["1.0.0"] = "1.0.0"

    def __init__(
        self,
        writer: PresentationArtifactJsonWriter,
        audit_logger: JsonlArtifactAuditLogger,
        validator: PresentationArtifactValidator | None = None,
    ) -> None:
        self._writer = writer
        self._audit_logger = audit_logger
        self._validator = validator or PresentationArtifactValidator()

    @classmethod
    def from_directories(
        cls,
        output_directory: Path,
        audit_log_path: Path,
    ) -> "PresentationArtifactBuilder":
        return cls(
            PresentationArtifactJsonWriter(output_directory),
            JsonlArtifactAuditLogger(audit_log_path),
        )

    @property
    def audit_log_path(self) -> Path:
        return self._audit_logger.output_path

    def build(
        self,
        request: PresentationRequest,
        source_bundle: SourceBundle,
        knowledge: KnowledgeRecord,
        *,
        created_at: datetime | None = None,
    ) -> ArtifactBuildResult:
        timestamp = created_at or datetime.now(UTC)
        artifact_id = f"art_{uuid4().hex}"
        artifact = self._compose(
            artifact_id,
            request,
            source_bundle,
            timestamp,
        )
        validation = self._validator.validate(
            artifact,
            request,
            source_bundle,
            knowledge,
        )
        if not validation.is_valid:
            self._audit(artifact, timestamp, "failed", False)
            return ArtifactBuildResult(
                status="validation_failed",
                artifact=artifact,
                output_path=None,
                validation=validation,
                audit_log_path=str(self.audit_log_path),
            )
        output_path = self._writer.write(artifact)
        self._audit(artifact, timestamp, "passed", True)
        return ArtifactBuildResult(
            status="success",
            artifact=artifact,
            output_path=str(output_path),
            validation=validation,
            audit_log_path=str(self.audit_log_path),
        )

    def _compose(
        self,
        artifact_id: str,
        request: PresentationRequest,
        source_bundle: SourceBundle,
        timestamp: datetime,
    ) -> PresentationArtifact:
        selected_ids = request.content_policy.selected_claim_ids
        bundle_claims = {item.claim_id: item for item in source_bundle.claims}
        missing = [claim_id for claim_id in selected_ids if claim_id not in bundle_claims]
        if missing:
            raise ValueError("Source BundleにないClaimが選択されています: " + ", ".join(missing))

        references_by_claim: dict[str, list[str]] = {}
        for reference in source_bundle.references:
            for claim_id in reference.supported_claim_ids:
                references_by_claim.setdefault(claim_id, []).append(reference.source_id)
        claim_catalog = tuple(
            ArtifactClaim(
                claim_id=claim_id,
                claim_key=bundle_claims[claim_id].claim_key,
                exact_text=bundle_claims[claim_id].assertion,
                field_path=bundle_claims[claim_id].field_path,
                reference_ids=tuple(
                    item
                    for item in references_by_claim.get(claim_id, [])
                    if item in request.content_policy.reference_ids
                ),
            )
            for claim_id in selected_ids
        )
        reference_catalog = tuple(
            ArtifactReference(
                reference_id=reference.source_id,
                title=reference.title,
                issuing_organization=reference.issuing_organization,
                edition=reference.edition,
                publication_year=reference.publication_year,
                url=str(reference.url) if reference.url is not None else None,
                doi=reference.doi,
                pmid=reference.pmid,
                chapter=reference.chapter,
                pages=reference.pages,
                supported_claim_ids=tuple(reference.supported_claim_ids),
            )
            for reference in source_bundle.references
            if reference.source_id in request.content_policy.reference_ids
        )
        profile = ArtifactPresentationProfile(
            profile_id=request.metadata.profile_id,
            profile_version=request.metadata.profile_version,
            presentation_type=request.presentation.presentation_type.value,
            output_format=request.presentation.output_format.value,
            target_audience=request.presentation.target_audience,
            learning_objective=request.presentation.learning_objective,
            language=request.presentation.language,
            page_or_slide_count=request.layout_policy.page_or_slide_count,
            aspect_ratio=request.layout_policy.aspect_ratio,
            orientation=request.layout_policy.orientation.value,
            information_density=request.layout_policy.information_density.value,
            visual_priority=request.layout_policy.visual_priority.value,
            text_amount=request.layout_policy.text_amount.value,
        )
        pages = self._build_pages(request, source_bundle, claim_catalog)
        identity = ArtifactIdentity(
            artifact_id=artifact_id,
            artifact_version=1,
            request_id=request.identity.presentation_request_id,
            source_bundle_id=source_bundle_id(source_bundle.metadata.source_fingerprint),
            presentation_profile=request.metadata.profile_id,
        )
        source = ArtifactSource(
            knowledge_id=source_bundle.metadata.knowledge_id,
            knowledge_version=source_bundle.metadata.version,
            source_bundle_schema_version=source_bundle.schema_version,
            source_fingerprint=source_bundle.metadata.source_fingerprint,
        )
        unsigned = PresentationArtifact(
            identity=identity,
            source=source,
            presentation_profile=profile,
            claim_catalog=claim_catalog,
            reference_catalog=reference_catalog,
            pages=pages,
            metadata=ArtifactMetadata(
                fingerprint="0" * 64,
                created_at=timestamp,
                builder_version=self.builder_version,
                artifact_version=1,
            ),
        )
        return unsigned.model_copy(
            update={
                "metadata": unsigned.metadata.model_copy(
                    update={"fingerprint": artifact_fingerprint(unsigned)}
                )
            }
        )

    def _build_pages(
        self,
        request: PresentationRequest,
        source_bundle: SourceBundle,
        claims: tuple[ArtifactClaim, ...],
    ) -> tuple[PresentationPage, ...]:
        count = request.layout_policy.page_or_slide_count
        claim_groups: list[list[ArtifactClaim]] = [[] for _ in range(count)]
        for index, claim in enumerate(claims):
            claim_groups[min(index * count // max(len(claims), 1), count - 1)].append(claim)
        diagrams_by_page: list[list[ArtifactDiagramItem]] = [[] for _ in range(count)]
        diagrams = [
            ArtifactDiagramItem(
                request_id=item.request_id,
                diagram_type=item.diagram_type,
                title=item.title,
                learning_goal=item.learning_goal,
                source_claim_ids=tuple(item.source_claim_ids),
            )
            for item in source_bundle.diagram_requests
            if item.request_id in request.content_policy.diagram_request_ids
        ]
        for index, diagram in enumerate(diagrams):
            target = min(index + (1 if count > 1 else 0), count - 1)
            diagrams_by_page[target].append(diagram)

        key_ids = set(request.content_policy.key_message_claim_ids)
        exam_ids = {item.claim_id for item in source_bundle.exam_points}
        pages: list[PresentationPage] = []
        for index in range(count):
            number = index + 1
            page_claims = claim_groups[index]
            page_diagrams = diagrams_by_page[index]
            supporting = list(dict.fromkeys(
                [item.claim_id for item in page_claims]
                + [claim_id for diagram in page_diagrams for claim_id in diagram.source_claim_ids]
            ))
            page_references = list(dict.fromkeys(
                reference_id
                for claim in page_claims
                for reference_id in claim.reference_ids
            ))
            body_blocks = tuple(
                ArtifactBodyBlock(
                    block_id=stable_block_id(
                        request.identity.presentation_request_id,
                        str(number),
                        claim.claim_id,
                    ),
                    block_type=(
                        BodyBlockType.EXAM_POINT
                        if claim.claim_id in exam_ids
                        else BodyBlockType.KEY_MESSAGE
                        if claim.claim_id in key_ids
                        else BodyBlockType.CLAIM
                    ),
                    claim_id=claim.claim_id,
                    exact_text=claim.exact_text,
                )
                for claim in page_claims
            )
            if number == 1:
                page_type = PageType.TITLE
                headline = request.presentation.title
                composition = LayoutComposition.TITLE
            elif number == count:
                page_type = PageType.SUMMARY
                headline = "まとめ"
                composition = LayoutComposition.SUMMARY
            else:
                page_type = PageType.CONTENT
                headline = f"学習ポイント {number - 1}"
                composition = LayoutComposition.SINGLE_COLUMN
            if page_diagrams:
                page_type = PageType.DIAGRAM
                headline = page_diagrams[0].title
                composition = LayoutComposition.DIAGRAM_FOCUS
            diagram_instruction = (
                DiagramInstruction(items=tuple(page_diagrams)) if page_diagrams else None
            )
            density = LayoutDensity(request.layout_policy.information_density.value)
            region_order: list[
                Literal["headline", "learning_goal", "body", "diagram", "references"]
            ] = ["headline", "learning_goal"]
            if body_blocks:
                region_order.append("body")
            if diagram_instruction is not None:
                region_order.append("diagram")
            if page_references:
                region_order.append("references")
            pages.append(
                PresentationPage(
                    page_number=number,
                    page_type=page_type,
                    headline=headline,
                    learning_goal=(
                        page_diagrams[0].learning_goal
                        if page_diagrams
                        else request.presentation.learning_objective
                    ),
                    supporting_claim_ids=tuple(supporting),
                    body_blocks=body_blocks,
                    diagram_instruction=diagram_instruction,
                    speaker_note="",
                    reference_ids=tuple(page_references),
                    layout_hint=LayoutHint(
                        composition=composition,
                        density=density,
                        region_order=tuple(region_order),
                    ),
                )
            )
        return tuple(pages)

    def _audit(
        self,
        artifact: PresentationArtifact,
        timestamp: datetime,
        validation_result: Literal["passed", "failed"],
        saved: bool,
    ) -> None:
        self._audit_logger.write(
            ArtifactAuditRecord(
                artifact_id=artifact.identity.artifact_id,
                request_id=artifact.identity.request_id,
                knowledge_id=artifact.source.knowledge_id,
                artifact_version=artifact.identity.artifact_version,
                validation_result=validation_result,
                saved=saved,
                timestamp=timestamp,
            )
        )
