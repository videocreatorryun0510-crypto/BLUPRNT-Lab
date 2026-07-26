"""Generate the Phase 3.6 AST Diagram Taxonomy sample without rendering."""

import json
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
OUTPUT_DIRECTORY = REPOSITORY_ROOT / "output" / "taxonomy"
SAMPLE_PATH = OUTPUT_DIRECTORY / "ast_diagram_taxonomy_v1.json"
PLAN_PATH = OUTPUT_DIRECTORY / "ast_taxonomy_publication_plan_v1.json"


def main() -> None:
    source = PublicationSourceBundle.model_validate_json(SOURCE_PATH.read_text(encoding="utf-8"))
    registry = TemplateRegistry.from_directory(PROFILE_ROOT)
    plan = PublisherPlanner(registry).build_plan(
        source,
        PublicationRequest(
            request_id="request.ast_taxonomy_v1",
            template_ref=ProfileReference(
                profile_id="template.national_exam_pdf",
                version="1.5.0",
            ),
            knowledge_id=source.knowledge.knowledge_id,
        ),
    )
    if plan.diagram_taxonomy_ref is None:
        raise RuntimeError("AST Publication Plan did not resolve Diagram Taxonomy")
    taxonomy = registry.resolve_diagram_taxonomy(plan.diagram_taxonomy_ref)
    intents_by_visual = {item.visual_id: item for item in plan.diagram_intent_bindings}
    classifications = []
    for binding in plan.diagram_taxonomy_bindings:
        intent = intents_by_visual[binding.visual_id]
        classifications.append(
            {
                "visual_id": binding.visual_id,
                "intent_id": intent.intent_id,
                "taxonomy_id": binding.taxonomy_id,
                "root_intent_type": binding.root_intent_type.value,
                "hierarchy": [
                    {
                        "taxonomy_id": taxonomy_id,
                        "canonical_name": taxonomy.node(taxonomy_id).canonical_name,
                    }
                    for taxonomy_id in binding.taxonomy_path
                ],
            }
        )
    sample = {
        "schema_version": "1.0",
        "knowledge_id": plan.knowledge_id,
        "taxonomy_ref": plan.diagram_taxonomy_ref.model_dump(mode="json"),
        "classifications": classifications,
    }
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    SAMPLE_PATH.write_text(
        json.dumps(sample, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    PLAN_PATH.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    print(f"Diagram Taxonomy sample: {SAMPLE_PATH}")
    print(f"Publication Plan 1.4: {PLAN_PATH}")


if __name__ == "__main__":
    main()
