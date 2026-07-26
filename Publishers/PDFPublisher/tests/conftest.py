from pathlib import Path

import pytest
from publisher_core import (
    ProfileReference,
    PublicationRequest,
    PublicationSourceBundle,
    PublisherPlanner,
    ResolvedTemplate,
    TemplateRegistry,
)


@pytest.fixture
def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


@pytest.fixture
def publication_source(repository_root: Path) -> PublicationSourceBundle:
    source_path = (
        repository_root / "Publishers" / "PDFPublisher" / "samples" / "ast_publication_source.json"
    )
    return PublicationSourceBundle.model_validate_json(source_path.read_text(encoding="utf-8"))


@pytest.fixture
def registry(repository_root: Path) -> TemplateRegistry:
    return TemplateRegistry.from_directory(
        repository_root / "Packages" / "publisher-core" / "profiles"
    )


@pytest.fixture
def resolved_profiles(registry: TemplateRegistry) -> ResolvedTemplate:
    return registry.resolve(
        ProfileReference(
            profile_id="template.national_exam_pdf",
            version="1.0.0",
        )
    )


@pytest.fixture
def publication_plan(
    publication_source: PublicationSourceBundle,
    registry: TemplateRegistry,
):
    return PublisherPlanner(registry).build_plan(
        publication_source,
        PublicationRequest(
            request_id="request.ast_pdf_test",
            template_ref=ProfileReference(
                profile_id="template.national_exam_pdf",
                version="1.0.0",
            ),
            knowledge_id=publication_source.knowledge.knowledge_id,
        ),
    )
