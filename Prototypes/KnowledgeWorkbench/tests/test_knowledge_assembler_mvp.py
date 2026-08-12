"""Phase 5.29 acceptance tests for the lossless Knowledge Assembler boundary."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from pytest import mark, raises

from knowledge_workbench.authoring_models import (
    AddAuthoringClaimRequest,
    AddAuthoringReferenceRequest,
    AuthoringCategory,
    AuthoringExamImportance,
    AuthoringSemanticSlot,
    CreateAuthoringDraftRequest,
    DifficultyLevel,
    EvidenceLevel,
    KnowledgeAuthoringDraft,
    ReferenceRole,
)
from knowledge_workbench.authoring_repository import FileAuthoringDraftRepository
from knowledge_workbench.authoring_service import KnowledgeAuthoringService
from knowledge_workbench.knowledge_assembler import (
    KnowledgeAssembler,
    KnowledgeDraftService,
    KnowledgeDraftValidationError,
    KnowledgeDraftValidator,
)
from knowledge_workbench.knowledge_draft_models import KnowledgeDraft
from knowledge_workbench.knowledge_draft_repository import FileKnowledgeDraftRepository
from knowledge_workbench.main import create_app
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider


def _client() -> TestClient:
    return TestClient(create_app(provider=FixtureKnowledgeProvider()))


def _ready_api_draft(client: TestClient) -> tuple[str, list[dict[str, object]]]:
    created = client.post(
        "/api/authoring/drafts",
        json={
            "category": "laboratory_test_item",
            "title": "フェリチン",
            "aliases": ["Ferritin"],
            "difficulty": "standard",
            "exam_importance": "high",
        },
    ).json()["draft"]
    draft_id = created["draft_id"]
    first = client.post(
        f"/api/authoring/drafts/{draft_id}/claims",
        json={
            "assertion": "フェリチンは鉄を貯蔵する蛋白質である。",
            "semantic_slot": "definition",
        },
    ).json()["draft"]["claims"][0]
    second = client.post(
        f"/api/authoring/drafts/{draft_id}/claims",
        json={
            "assertion": "血清フェリチン低値は貯蔵鉄減少を示唆する。",
            "semantic_slot": "overview",
        },
    ).json()["draft"]["claims"][1]
    response = client.post(
        f"/api/authoring/drafts/{draft_id}/references",
        json={
            "evidence_level": "A",
            "evidence_role": "primary",
            "source_priority_rank": 6,
            "title": "Ferritin and iron stores",
            "issuing_organization": "National Library of Medicine",
            "publication_year": 2025,
            "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
            "pmid": "12345678",
            "supported_claim_ids": [first["claim_id"], second["claim_id"]],
        },
    )
    assert response.status_code == 200
    return draft_id, [first, second]


def test_knowledge_draft_generation_is_lossless_and_read_only() -> None:
    client = _client()
    draft_id, source_claims = _ready_api_draft(client)
    registry_before = client.get("/api/registry").json()
    promotion_log_before = client.get("/api/authoring/promotion/logs").json()

    response = client.post(
        "/api/knowledge-assembler/drafts",
        json={"authoring_draft_id": draft_id},
    )

    assert response.status_code == 200
    payload = response.json()
    draft = KnowledgeDraft.model_validate(payload["draft"])
    assert draft.knowledge_draft_id.startswith("kdr_")
    assert draft.temporary_knowledge_id.startswith("tmp_knw_")
    assert draft.category == AuthoringCategory.LABORATORY_TEST_ITEM
    assert [item.claim_id for item in draft.claims] == [
        item["claim_id"] for item in source_claims
    ]
    assert [item.assertion for item in draft.claims] == [
        item["assertion"] for item in source_claims
    ]
    assert draft.summary == source_claims[0]["assertion"]
    assert draft.summary_source_claim_id == source_claims[0]["claim_id"]
    assert draft.claims[0].reference_ids == (draft.references[0].source_id,)
    assert [item.section_key.value for item in draft.category_structure] == [
        "definition",
        "overview",
    ]
    assert draft.completeness.score == 100
    assert payload["validation"]["save_allowed"] is True
    assert draft.review.approval_state == "draft"
    assert payload["registry_mutated"] is False
    assert payload["promotion_performed"] is False
    assert payload["approval_performed"] is False
    assert client.get("/api/registry").json() == registry_before
    assert client.get("/api/authoring/promotion/logs").json() == promotion_log_before


def test_generated_draft_can_be_reloaded_and_exported_without_rewriting_text() -> None:
    client = _client()
    authoring_draft_id, source_claims = _ready_api_draft(client)
    generated = client.post(
        "/api/knowledge-assembler/drafts",
        json={"authoring_draft_id": authoring_draft_id},
    ).json()["draft"]
    knowledge_draft_id = generated["knowledge_draft_id"]

    loaded = client.get(f"/api/knowledge-assembler/drafts/{knowledge_draft_id}")
    exported_json = client.get(
        f"/api/knowledge-assembler/drafts/{knowledge_draft_id}/export?format=json"
    )
    exported_markdown = client.get(
        f"/api/knowledge-assembler/drafts/{knowledge_draft_id}/export?format=markdown"
    )

    assert loaded.status_code == 200
    assert loaded.json()["draft"] == generated
    assert exported_json.status_code == 200
    assert exported_json.json() == generated
    assert exported_markdown.status_code == 200
    assert "# フェリチン" in exported_markdown.text
    assert source_claims[0]["assertion"] in exported_markdown.text
    assert source_claims[1]["assertion"] in exported_markdown.text
    assert "Approval: `draft`" in exported_markdown.text


def test_validation_failure_never_saves_an_incomplete_draft(tmp_path: Path) -> None:
    authoring = KnowledgeAuthoringService(
        FileAuthoringDraftRepository(tmp_path / "authoring")
    )
    source = authoring.create(
        CreateAuthoringDraftRequest(
            category=AuthoringCategory.LABORATORY_TEST_ITEM,
            title="未完成Knowledge",
            aliases=[],
            difficulty=DifficultyLevel.BASIC,
            exam_importance=AuthoringExamImportance.LOW,
        )
    )
    repository = FileKnowledgeDraftRepository(tmp_path / "knowledge_drafts")
    service = KnowledgeDraftService(
        assembler=KnowledgeAssembler(),
        validator=KnowledgeDraftValidator(),
        repository=repository,
        authoring=authoring,
    )

    with raises(KnowledgeDraftValidationError) as captured:
        service.generate(source.draft_id)

    assert captured.value.report.reference_integrity_valid is False
    assert captured.value.report.summary_traceable is False
    assert captured.value.report.save_allowed is False
    assert repository.list() == []


@mark.parametrize(
    ("mutation", "failed_check"),
    [
        ("claim_order", "claim_order_valid"),
        ("claim_duplicate", "unique_claim_ids_valid"),
        ("reference", "reference_integrity_valid"),
        ("category", "category_valid"),
        ("fingerprint", "fingerprint_valid"),
        ("metadata", "metadata_valid"),
        ("claim_text", "lossless_claims_valid"),
        ("reference_text", "references_unchanged"),
        ("summary", "summary_traceable"),
    ],
)
def test_validator_rejects_every_integrity_boundary(
    tmp_path: Path,
    mutation: str,
    failed_check: str,
) -> None:
    source, draft = _ready_service_draft(tmp_path)
    if mutation == "claim_order":
        changed = draft.model_copy(update={"claims": tuple(reversed(draft.claims))})
    elif mutation == "claim_duplicate":
        changed = draft.model_copy(update={"claims": (draft.claims[0], draft.claims[0])})
    elif mutation == "reference":
        bad_claim = draft.claims[0].model_copy(update={"reference_ids": ("src_missing00",)})
        changed = draft.model_copy(update={"claims": (bad_claim, *draft.claims[1:])})
    elif mutation == "category":
        changed = draft.model_copy(update={"category": AuthoringCategory.DISEASE})
    elif mutation == "fingerprint":
        changed = draft.model_copy(update={"fingerprint": "b" * 64})
    elif mutation == "metadata":
        changed = draft.model_copy(
            update={
                "metadata": draft.metadata.model_copy(
                    update={"source_authoring_draft_id": "kad_missing000"}
                )
            }
        )
    elif mutation == "claim_text":
        changed_claim = draft.claims[0].model_copy(update={"assertion": "書き換えた事実"})
        changed = draft.model_copy(update={"claims": (changed_claim, *draft.claims[1:])})
    elif mutation == "reference_text":
        changed_reference = draft.references[0].model_copy(update={"title": "変更資料"})
        changed = draft.model_copy(update={"references": (changed_reference,)})
    else:
        changed = draft.model_copy(update={"summary": "AIが作った要約"})

    report = KnowledgeDraftValidator().validate(changed, source)

    assert getattr(report, failed_check) is False
    assert report.save_allowed is False


def test_workbench_exposes_preview_without_a_promotion_action() -> None:
    client = _client()
    page = client.get("/")
    status = client.get("/api/status").json()
    schema = client.get("/api/schema/knowledge-draft-1.0")
    panel = page.text.split('id="knowledgeAssemblerPanel"', 1)[1].split(
        'aria-labelledby="promotion-preview-title"', 1
    )[0]

    assert "Knowledge Draft Preview" in panel
    assert 'id="generateKnowledgeDraftButton"' in panel
    assert 'id="exportKnowledgeDraftJsonButton"' in panel
    assert 'id="exportKnowledgeDraftMarkdownButton"' in panel
    assert 'id="returnToAuthoringButton"' in panel
    assert 'id="previewPromotionButton"' not in panel
    assert 'id="commitPromotionButton"' not in panel
    assert status["knowledge_assembler_version"] == "1.0.0"
    assert status["knowledge_draft_contract_version"] == "1.0"
    assert status["knowledge_draft_registry_write_enabled"] is False
    assert status["knowledge_draft_promotion_enabled"] is False
    assert status["knowledge_draft_automatic_approval_enabled"] is False
    assert status["knowledge_draft_provider_neutral"] is True
    assert schema.status_code == 200
    assert schema.json()["title"] == "KnowledgeDraft"


def _ready_service_draft(
    tmp_path: Path,
) -> tuple[KnowledgeAuthoringDraft, KnowledgeDraft]:
    authoring = KnowledgeAuthoringService(
        FileAuthoringDraftRepository(tmp_path / "authoring_ready")
    )
    source = authoring.create(
        CreateAuthoringDraftRequest(
            category=AuthoringCategory.LABORATORY_TEST_ITEM,
            title="フェリチン",
            aliases=["Ferritin"],
            difficulty=DifficultyLevel.STANDARD,
            exam_importance=AuthoringExamImportance.HIGH,
        )
    )
    source = authoring.add_claim(
        source.draft_id,
        AddAuthoringClaimRequest(
            assertion="フェリチンは鉄を貯蔵する蛋白質である。",
            semantic_slot=AuthoringSemanticSlot.DEFINITION,
        ),
    )
    source = authoring.add_claim(
        source.draft_id,
        AddAuthoringClaimRequest(
            assertion="血清フェリチン低値は貯蔵鉄減少を示唆する。",
            semantic_slot=AuthoringSemanticSlot.OVERVIEW,
        ),
    )
    source = authoring.add_reference(
        source.draft_id,
        AddAuthoringReferenceRequest(
            evidence_level=EvidenceLevel.A,
            evidence_role=ReferenceRole.PRIMARY,
            source_priority_rank=6,
            title="Ferritin and iron stores",
            issuing_organization="National Library of Medicine",
            publication_year=2025,
            url="https://pubmed.ncbi.nlm.nih.gov/12345678/",
            pmid="12345678",
            supported_claim_ids=[claim.claim_id for claim in source.claims],
        ),
    )
    return source, KnowledgeAssembler().assemble(source)
