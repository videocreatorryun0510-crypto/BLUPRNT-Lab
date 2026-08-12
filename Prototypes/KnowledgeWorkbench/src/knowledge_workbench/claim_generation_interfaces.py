"""Replaceable boundaries for evidence-grounded Claim generation."""

from typing import Protocol, runtime_checkable

from knowledge_workbench.claim_candidate_models import (
    ClaimAdapterResult,
    ClaimGenerationErrorCode,
    ClaimGenerationRequest,
)


class ClaimGenerationAdapterError(RuntimeError):
    """Provider-neutral error exposed by every Claim generation adapter."""

    def __init__(
        self,
        code: ClaimGenerationErrorCode,
        message: str,
        *,
        retry_count: int = 0,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retry_count = retry_count


@runtime_checkable
class ClaimGenerationAdapter(Protocol):
    provider_name: str
    provider_version: str
    model: str

    def generate(self, request: ClaimGenerationRequest) -> ClaimAdapterResult:
        """Extract structured Claim candidates from accepted Formal Evidence only."""
