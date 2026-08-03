"""Network-free Dummy Presentation Engine Adapter."""

from datetime import UTC, datetime

from presentation_request_builder import PresentationRequest
from provider_payload_resolver import (
    PresentationPayload,
    TraceablePresentationResponse,
    TraceableResponseValidation,
    TraceableResponseValidator,
    build_dummy_traceable_response,
)

from presentation_engine_adapter.fingerprint import presentation_request_fingerprint
from presentation_engine_adapter.models import (
    AdapterValidationReport,
    PresentationEnginePayload,
    PresentationEngineResponse,
)
from presentation_engine_adapter.validator import (
    PresentationEngineRequestValidator,
    PresentationEngineResponseValidator,
)


class DummyPresentationEngineAdapter:
    """Simulate provider execution using metadata only and no network calls."""

    provider_name = "dummy"
    provider_version = "1.0.0"
    supports_preview = True
    supports_external = True

    def __init__(self) -> None:
        self._request_validator = PresentationEngineRequestValidator()
        self._response_validator = PresentationEngineResponseValidator()
        self._traceable_response_validator = TraceableResponseValidator()

    def validate_request(
        self,
        request: PresentationRequest,
    ) -> AdapterValidationReport:
        return self._request_validator.validate(
            request,
            supports_preview=self.supports_preview,
            supports_external=self.supports_external,
        )

    def build_payload(
        self,
        request: PresentationRequest,
    ) -> PresentationEnginePayload:
        validation = self.validate_request(request)
        if not validation.is_valid:
            raise ValueError("Presentation RequestがAdapter Contractに適合しません。")
        return PresentationEnginePayload(
            request_id=request.identity.presentation_request_id,
            request_fingerprint=presentation_request_fingerprint(request),
            request_mode=request.request_mode,
            provider=self.provider_name,
            provider_version=self.provider_version,
            presentation_type=request.presentation.presentation_type,
            output_format=request.presentation.output_format,
            expected_pages=request.layout_policy.page_or_slide_count,
            claim_ids=request.content_policy.selected_claim_ids,
            diagram_request_ids=request.content_policy.diagram_request_ids,
            reference_ids=request.content_policy.reference_ids,
        )

    def execute(
        self,
        payload: PresentationEnginePayload,
    ) -> PresentationEngineResponse:
        return PresentationEngineResponse(
            request_id=payload.request_id,
            request_fingerprint=payload.request_fingerprint,
            provider=self.provider_name,
            provider_version=self.provider_version,
            pages=payload.expected_pages,
            claims_used=len(payload.claim_ids),
            diagram_requests=len(payload.diagram_request_ids),
            references=len(payload.reference_ids),
            output_type=payload.presentation_type,
            created_at=datetime.now(UTC),
        )

    def validate_response(
        self,
        request: PresentationRequest,
        payload: PresentationEnginePayload,
        response: PresentationEngineResponse,
    ) -> AdapterValidationReport:
        return self._response_validator.validate(request, payload, response)

    def execute_traceable_payload(
        self,
        payload: PresentationPayload,
        *,
        executed_at: datetime | None = None,
    ) -> TraceablePresentationResponse:
        """Execute a traceable Payload without external communication."""

        return build_dummy_traceable_response(
            payload,
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            executed_at=executed_at,
        )

    def validate_traceable_response(
        self,
        payload: PresentationPayload,
        response: TraceablePresentationResponse,
    ) -> TraceableResponseValidation:
        return self._traceable_response_validator.validate(payload, response)
