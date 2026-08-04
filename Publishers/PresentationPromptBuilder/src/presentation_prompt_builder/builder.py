"""Build provider-neutral prompts without rewriting approved medical facts."""

from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar, Literal
from uuid import uuid4

from provider_payload_resolver import (
    DataEgressPolicyValidator,
    PresentationPayload,
    presentation_payload_fingerprint,
)

from presentation_prompt_builder.audit import JsonlPromptAuditLogger
from presentation_prompt_builder.fingerprint import presentation_prompt_fingerprint
from presentation_prompt_builder.models import (
    PresentationPrompt,
    PromptAuditRecord,
    PromptBuildResult,
    PromptClaim,
    PromptContentPolicy,
    PromptDiagramRequest,
    PromptIdentity,
    PromptKeyMessage,
    PromptLayoutPolicy,
    PromptMetadata,
    PromptReference,
    PromptSource,
    PromptValidationIssue,
    PromptValidationPolicy,
    PromptValidationReport,
)
from presentation_prompt_builder.writer import PresentationPromptJsonWriter


class PresentationPromptBuilder:
    builder_id: ClassVar[Literal["bluprnt.presentation_prompt_builder"]] = (
        "bluprnt.presentation_prompt_builder"
    )
    builder_version: ClassVar[Literal["1.0.0"]] = "1.0.0"

    def __init__(
        self,
        writer: PresentationPromptJsonWriter,
        audit_logger: JsonlPromptAuditLogger,
    ) -> None:
        self._writer = writer
        self._audit_logger = audit_logger
        self._egress_validator = DataEgressPolicyValidator()

    @classmethod
    def from_directories(
        cls,
        output_directory: Path,
        audit_log_path: Path,
    ) -> "PresentationPromptBuilder":
        return cls(
            PresentationPromptJsonWriter(output_directory),
            JsonlPromptAuditLogger(audit_log_path),
        )

    @property
    def audit_log_path(self) -> str:
        return str(self._audit_logger.output_path)

    def build(
        self,
        payload: PresentationPayload,
        *,
        built_at: datetime | None = None,
    ) -> PromptBuildResult:
        timestamp = built_at or datetime.now(UTC)
        prompt_id = f"pmt_{uuid4().hex}"
        issues: list[PromptValidationIssue] = []
        approval_state = payload.source.approval_state
        approval_ok = getattr(approval_state, "value", approval_state) == "approved"
        if not approval_ok:
            issues.append(
                _issue(
                    "approval_required",
                    "source.approval_state",
                    "approved以外はPresentation Promptを生成できません。",
                )
            )
        expected_payload_fingerprint = presentation_payload_fingerprint(payload)
        fingerprint_ok = (
            payload.metadata.payload_fingerprint == expected_payload_fingerprint
        )
        if not fingerprint_ok:
            issues.append(
                _issue(
                    "payload_fingerprint_mismatch",
                    "metadata.payload_fingerprint",
                    "Provider PayloadのFingerprintが一致しません。",
                )
            )
        egress = self._egress_validator.validate(payload)
        if not egress.egress_policy_result:
            issues.extend(
                _issue(item.code, item.path, item.message) for item in egress.issues
            )
        exact_claim_ok = all(
            item.approval_state == "approved" and bool(item.exact_text.strip())
            for item in payload.medical_content.selected_claims
        )
        if not exact_claim_ok:
            issues.append(
                _issue(
                    "approved_exact_claim_required",
                    "medical_content.selected_claims",
                    "承認済みClaim本文だけを利用できます。",
                )
            )
        provider_neutral_ok = True
        validation = PromptValidationReport(
            is_valid=not issues,
            approval_result=approval_ok,
            payload_fingerprint_result=fingerprint_ok,
            exact_claim_result=exact_claim_ok,
            provider_neutral_result=provider_neutral_ok,
            issues=tuple(issues),
        )
        if not validation.is_valid:
            error_code = issues[0].code if issues else "prompt_validation_failed"
            self._audit_logger.write(
                PromptAuditRecord(
                    prompt_id=prompt_id,
                    presentation_request_id=(
                        payload.request.presentation_request_id
                    ),
                    payload_id=payload.identity.payload_id,
                    payload_fingerprint=payload.metadata.payload_fingerprint,
                    prompt_fingerprint=None,
                    builder_version=self.builder_version,
                    mode=payload.request.request_mode,
                    status="blocked",
                    error_code=error_code,
                    timestamp=timestamp,
                )
            )
            return PromptBuildResult(
                status="blocked",
                attempted_prompt_id=prompt_id,
                prompt=None,
                output_path=None,
                validation=validation,
                stop_reasons=tuple(item.message for item in issues),
                audit_log_path=self.audit_log_path,
            )

        prompt = self._make_prompt(payload, prompt_id, timestamp)
        fingerprint = presentation_prompt_fingerprint(prompt)
        prompt = prompt.model_copy(
            update={
                "metadata": prompt.metadata.model_copy(
                    update={"prompt_fingerprint": fingerprint}
                )
            }
        )
        output_path = self._writer.write(prompt)
        self._audit_logger.write(
            PromptAuditRecord(
                prompt_id=prompt.identity.prompt_id,
                presentation_request_id=payload.request.presentation_request_id,
                payload_id=payload.identity.payload_id,
                payload_fingerprint=payload.metadata.payload_fingerprint,
                prompt_fingerprint=fingerprint,
                builder_version=self.builder_version,
                mode=payload.request.request_mode,
                status="generated",
                timestamp=timestamp,
            )
        )
        return PromptBuildResult(
            status="success",
            attempted_prompt_id=prompt.identity.prompt_id,
            prompt=prompt,
            output_path=str(output_path),
            validation=validation,
            stop_reasons=(),
            audit_log_path=self.audit_log_path,
        )

    def _make_prompt(
        self,
        payload: PresentationPayload,
        prompt_id: str,
        timestamp: datetime,
    ) -> PresentationPrompt:
        claims = tuple(
            PromptClaim(
                claim_id=item.claim_id,
                claim_key=item.claim_key,
                exact_text=item.exact_text,
                category_role=item.category_role,
                reference_ids=item.source_reference_ids,
                claim_version=item.claim_version,
            )
            for item in payload.medical_content.selected_claims
        )
        key_messages = tuple(
            PromptKeyMessage(
                claim_id=item.claim_id,
                exact_text=item.exact_text,
                priority=item.priority,
            )
            for item in payload.medical_content.key_messages
        )
        diagrams = tuple(
            PromptDiagramRequest(
                diagram_request_id=item.diagram_request_id,
                title=item.title,
                educational_goal=item.educational_goal,
                source_claim_ids=item.source_claim_ids,
                visual_type=item.visual_type,
                priority=item.priority,
                provider_neutral_instruction=item.provider_neutral_instruction,
            )
            for item in payload.visual_content.diagram_requests
        )
        references = tuple(
            PromptReference(
                reference_id=item.reference_id,
                title=item.title,
                organization_or_author=item.organization_or_author,
                publication_year=item.publication_year,
                doi=item.locator.doi,
                pmid=item.locator.pmid,
                chapter=item.locator.chapter,
                pages=item.locator.pages,
                supported_claim_ids=item.supported_claim_ids,
            )
            for item in payload.medical_content.references
        )
        claim_ids = tuple(item.claim_id for item in claims)
        return PresentationPrompt(
            identity=PromptIdentity(prompt_id=prompt_id, created_at=timestamp),
            source=PromptSource(
                presentation_request_id=payload.request.presentation_request_id,
                payload_id=payload.identity.payload_id,
                payload_fingerprint=payload.metadata.payload_fingerprint,
                knowledge_id=payload.source.knowledge_id,
                knowledge_version=payload.source.knowledge_version,
                approval_state="approved",
                request_mode=payload.request.request_mode,
            ),
            title=payload.presentation.title,
            learning_objective=payload.presentation.learning_objective,
            target_audience=payload.presentation.target_audience,
            claims=claims,
            key_messages=key_messages,
            diagram_requests=diagrams,
            references=references,
            content_policy=PromptContentPolicy(
                selected_claim_ids=claim_ids,
                key_message_claim_ids=tuple(item.claim_id for item in key_messages),
                diagram_request_ids=tuple(
                    item.diagram_request_id for item in diagrams
                ),
                reference_ids=tuple(item.reference_id for item in references),
            ),
            layout_policy=PromptLayoutPolicy(
                presentation_type=payload.request.presentation_type,
                output_format=payload.request.output_format,
                language=payload.presentation.language,
                page_or_slide_count=payload.presentation.page_or_slide_count,
                aspect_ratio=payload.presentation.aspect_ratio,
                orientation=payload.presentation.orientation,
                information_density=payload.presentation.information_density,
                visual_priority=payload.presentation.visual_priority,
                text_amount=payload.presentation.text_amount,
            ),
            validation_policy=PromptValidationPolicy(
                expected_payload_fingerprint=payload.metadata.payload_fingerprint,
            ),
            metadata=PromptMetadata(
                builder_id=self.builder_id,
                builder_version=self.builder_version,
                prompt_fingerprint="0" * 64,
            ),
        )


def _issue(code: str, path: str, message: str) -> PromptValidationIssue:
    return PromptValidationIssue(code=code, path=path, message=message)
