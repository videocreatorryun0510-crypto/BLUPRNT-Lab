"""Generate the Phase 3.2 AST Publication Plan for product-owner review."""

from pathlib import Path

from publisher_core import (
    ProfileReference,
    PublicationRequest,
    PublicationSourceBundle,
    PublisherPlanner,
    TemplateRegistry,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = REPOSITORY_ROOT / "Packages" / "publisher-core" / "profiles"
SOURCE_PATH = (
    REPOSITORY_ROOT / "Publishers" / "PDFPublisher" / "samples" / "ast_publication_source.json"
)
OUTPUT_PATH = REPOSITORY_ROOT / "output" / "plans" / "ast_national_exam_education_v1.plan.json"


def main() -> None:
    source = PublicationSourceBundle.model_validate_json(SOURCE_PATH.read_text(encoding="utf-8"))
    registry = TemplateRegistry.from_directory(PROFILE_ROOT)
    plan = PublisherPlanner(registry).build_plan(
        source,
        PublicationRequest(
            request_id="request.ast_education_v1_review",
            template_ref=ProfileReference(
                profile_id="template.national_exam_pdf",
                version="1.1.0",
            ),
            knowledge_id=source.knowledge.knowledge_id,
        ),
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    print(f"Education Publication Plan: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
