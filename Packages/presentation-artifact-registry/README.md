# Presentation Artifact Registry

The Artifact Registry is the persistent Single Source of Truth for educational
Presentation Artifacts. It manages stable artifact IDs, append-only versions,
independent education approval, history, structured diffs, and completeness.

Renderers must obtain an Artifact through `ArtifactRendererGateway`. The gateway
requires both an approved Artifact and a currently approved, version-matched
Knowledge source whose referenced Claims and fingerprints still pass validation.
Artifact approval and current renderer eligibility remain separate facts. Renderers
must not read builder output JSON directly.
