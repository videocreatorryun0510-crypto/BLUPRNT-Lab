"""Stable Provider-neutral Adapter interface."""

from typing import Protocol, runtime_checkable

from presentation_request_builder import PresentationRequest

from presentation_engine_adapter.models import (
    AdapterValidationReport,
    PresentationEnginePayload,
    PresentationEngineResponse,
)


@runtime_checkable
class PresentationEngineAdapter(Protocol):
    @property
    def provider_name(self) -> str: ...

    @property
    def provider_version(self) -> str: ...

    @property
    def supports_preview(self) -> bool: ...

    @property
    def supports_external(self) -> bool: ...

    def validate_request(
        self,
        request: PresentationRequest,
    ) -> AdapterValidationReport: ...

    def build_payload(
        self,
        request: PresentationRequest,
    ) -> PresentationEnginePayload: ...

    def execute(
        self,
        payload: PresentationEnginePayload,
    ) -> PresentationEngineResponse: ...

    def validate_response(
        self,
        request: PresentationRequest,
        payload: PresentationEnginePayload,
        response: PresentationEngineResponse,
    ) -> AdapterValidationReport: ...
