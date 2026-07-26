"""Generate Phase 3.5 AST Semantic Blueprints without render instructions."""

from pathlib import Path

from publisher_core import (
    ClaimMappingResolver,
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
OUTPUT_DIRECTORY = REPOSITORY_ROOT / "output" / "blueprints"
BUNDLE_PATH = OUTPUT_DIRECTORY / "ast_semantic_blueprints_v1.json"


def main() -> None:
    source = PublicationSourceBundle.model_validate_json(SOURCE_PATH.read_text(encoding="utf-8"))
    registry = TemplateRegistry.from_directory(PROFILE_ROOT)
    plan = PublisherPlanner(registry).build_plan(
        source,
        PublicationRequest(
            request_id="request.ast_semantic_blueprints_v1",
            template_ref=ProfileReference(
                profile_id="template.national_exam_pdf",
                version="1.4.0",
            ),
            knowledge_id=source.knowledge.knowledge_id,
        ),
    )
    bundle = ClaimMappingResolver().resolve(plan, source)
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    BUNDLE_PATH.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    for blueprint in bundle.blueprints:
        output_path = OUTPUT_DIRECTORY / f"ast_{blueprint.intent_type.value}_v1.json"
        output_path.write_text(blueprint.model_dump_json(indent=2), encoding="utf-8")
        missing = ", ".join(item.concept_id for item in blueprint.missing_concepts) or "none"
        print(
            f"{blueprint.intent_type.value}: complete={blueprint.is_complete}, "
            f"missing={missing} -> {output_path}"
        )
    print(f"Semantic Blueprint Bundle: {BUNDLE_PATH}")


if __name__ == "__main__":
    main()
