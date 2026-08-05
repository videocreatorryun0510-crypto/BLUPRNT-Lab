"""Artifact Registry errors."""


class ArtifactRegistryError(ValueError):
    """Base error for invalid or unavailable registry operations."""


class ArtifactNotFoundError(ArtifactRegistryError):
    pass


class ArtifactApprovalError(ArtifactRegistryError):
    pass


class ArtifactImmutableError(ArtifactRegistryError):
    pass
