"""Generate the Phase 3.1 AST review PDF from versioned Publisher Profiles."""

import json
from pathlib import Path

from publisher_core import (
    ProfileReference,
    PublicationRequest,
    PublicationSourceBundle,
    PublisherPlanner,
    TemplateRegistry,
)

from pdf_publisher import PdfPublisherAdapter, PublicationPlanReader

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = REPOSITORY_ROOT / "Packages" / "publisher-core" / "profiles"
SAMPLE_SOURCE_PATH = (
    REPOSITORY_ROOT / "Publishers" / "PDFPublisher" / "samples" / "ast_publication_source.json"
)
OUTPUT_DIRECTORY = REPOSITORY_ROOT / "output" / "pdf"
PLAN_PATH = OUTPUT_DIRECTORY / "ast_national_exam_v1.plan.json"
RENDER_PLAN_PATH = OUTPUT_DIRECTORY / "ast_national_exam_v1.render-plan.json"
PDF_PATH = OUTPUT_DIRECTORY / "ast_national_exam_v1.pdf"


def main() -> None:
    source = PublicationSourceBundle.model_validate_json(
        SAMPLE_SOURCE_PATH.read_text(encoding="utf-8")
    )
    registry = TemplateRegistry.from_directory(PROFILE_ROOT)
    template_ref = ProfileReference(
        profile_id="template.national_exam_pdf",
        version="1.0.0",
    )
    profiles = registry.resolve(template_ref)
    plan = PublisherPlanner(registry).build_plan(
        source,
        PublicationRequest(
            request_id="request.ast_pdf_v1_review",
            template_ref=template_ref,
            knowledge_id=source.knowledge.knowledge_id,
        ),
    )

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    PLAN_PATH.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    render_plan = PublicationPlanReader().resolve(plan, source, profiles)
    RENDER_PLAN_PATH.write_text(
        json.dumps(render_plan.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    artifact = PdfPublisherAdapter(PDF_PATH).publish_plan_file(
        PLAN_PATH,
        source,
        profiles,
    )

    print(f"Publication Plan: {PLAN_PATH}")
    print(f"PDF Render Plan: {RENDER_PLAN_PATH}")
    print(f"PDF: {artifact.artifact_uri}")
    print(f"SHA-256: {artifact.content_hash}")


if __name__ == "__main__":
    main()
