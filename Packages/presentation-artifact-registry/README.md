# Presentation Artifact Registry

The Artifact Registry is the persistent Single Source of Truth for educational
Presentation Artifacts. It manages stable artifact IDs, append-only versions,
independent education approval, history, structured diffs, and completeness.

Renderers must obtain an approved Artifact through `ArtifactRendererGateway`.
They must not read builder output JSON directly.
