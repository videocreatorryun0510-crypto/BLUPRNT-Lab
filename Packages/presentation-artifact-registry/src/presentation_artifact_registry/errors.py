"""Artifact Registry errors."""


class ArtifactRegistryError(ValueError):
    """Base error for invalid or unavailable registry operations."""


class ArtifactNotFoundError(ArtifactRegistryError):
    pass


class ArtifactApprovalError(ArtifactRegistryError):
    def __init__(
        self,
        message: str,
        *,
        reason_codes: tuple[str, ...] = (),
        eligibility: object | None = None,
    ) -> None:
        super().__init__(message)
        self.reason_codes = reason_codes
        self.eligibility = eligibility


class ArtifactImmutableError(ArtifactRegistryError):
    pass
