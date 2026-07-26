import base64

from fastapi.testclient import TestClient

from knowledge_workbench.main import create_app
from knowledge_workbench.providers.fixture_provider import FixtureKnowledgeProvider
from knowledge_workbench.settings import Settings


def test_workbench_api_returns_visible_valid_json() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))

    response = client.post("/api/generate", json={"term": "AST"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["schema_valid"] is True
    assert payload["completeness_valid"] is True
    assert payload["knowledge_completeness_valid"] is True
    assert payload["exam_completeness_valid"] is True
    assert payload["data"]["schema_version"] == "1.0"
    assert payload["data"]["term"]["canonical_name"] == "アスパラギン酸アミノトランスフェラーゼ"
    assert payload["data"]["category_content"]["template_id"] == "test_item_v1.0"
    assert 0 <= payload["knowledge_completeness"]["score"] <= 100
    assert payload["knowledge_completeness"]["improvement_candidates"]
    assert payload["exam_metadata"]["schema_version"] == "1.0"
    assert payload["exam_metadata"]["knowledge_id"] == payload["data"]["knowledge_id"]
    assert payload["exam_metadata"]["frequency"]["appearance_count"] == 2
    assert payload["exam_metadata"]["priority_claims"]
    assert payload["exam_completeness"]["score"] == 79
    assert payload["registry"]["knowledge"]["registry_key"] == "ast"
    assert payload["registry"]["knowledge"]["knowledge_version"] == 1
    assert payload["registry"]["validation"]["is_valid"] is True
    assert "ast.is_leakage_enzyme" in {item["claim_key"] for item in payload["registry"]["claims"]}
    assert payload["relations"]["relations"] == []
    assert payload["relations"]["validation"]["is_valid"] is True
    assert payload["relations"]["network_summary"]["relation_count"] == 0
    assert payload["relations"]["network_summary"]["network_completeness"] == 0
    assert payload["resolution_report"]["evaluated_count"] == 0


def test_status_and_schema_endpoints_report_v10_and_keep_v03() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))

    status = client.get("/api/status")
    schema_v10 = client.get("/api/schema/knowledge-1.0")
    schema_v03 = client.get("/api/schema/knowledge-0.3")
    exam_schema_v10 = client.get("/api/schema/exam-metadata-1.0")
    registry_schema_v10 = client.get("/api/schema/knowledge-registry-1.0")
    relation_schema_v10 = client.get("/api/schema/knowledge-relation-1.0")
    relation_schema_v11 = client.get("/api/schema/knowledge-relation-1.1")
    relation_schema_v12 = client.get("/api/schema/knowledge-relation-1.2")
    disease_vocabulary_schema = client.get(
        "/api/schema/relation-vocabulary-disease-1.0"
    )

    assert status.json()["schema_version"] == "1.0"
    assert status.json()["supported_schema_versions"] == ["0.3", "1.0"]
    assert status.json()["exam_metadata_version"] == "1.0"
    assert status.json()["exam_import_version"] == "1.0"
    assert status.json()["exam_metadata_providers"] == ["dummy", "csv"]
    assert status.json()["knowledge_registry_version"] == "1.0"
    assert status.json()["knowledge_registry_storage"] == "sqlite"
    assert status.json()["supported_categories"] == [
        "test_item",
        "staining_method",
        "specimen",
        "reagent",
        "biological_structure",
        "disease",
        "laboratory_test_item",
    ]
    assert status.json()["production_categories"] == [
        "staining_method",
        "specimen",
        "reagent",
        "biological_structure",
        "disease",
        "laboratory_test_item",
    ]
    assert status.json()["knowledge_relation_version"] == "1.1"
    assert status.json()["supported_knowledge_relation_versions"] == [
        "1.0",
        "1.1",
        "1.2",
    ]
    assert status.json()["knowledge_relation_vocabulary"] == [
        "uses_specimen",
        "uses_reagent",
        "targets_structure",
        "related_method",
    ]
    assert status.json()["disease_relation_vocabulary_version"] == "1.0"
    assert status.json()["relation_growth_version"] == "1.0"
    assert status.json()["relation_resolution_strategy"] == "indexed_unresolved_only"
    assert schema_v10.status_code == 200
    assert schema_v10.json()["$id"].endswith("/1.0")
    assert schema_v03.status_code == 200
    assert schema_v03.json()["$id"].endswith("/0.3")
    assert exam_schema_v10.status_code == 200
    assert exam_schema_v10.json()["$id"].endswith("/1.0")
    assert registry_schema_v10.status_code == 200
    assert registry_schema_v10.json()["$id"].endswith("/1.0")
    assert relation_schema_v10.status_code == 200
    assert relation_schema_v10.json()["$id"].endswith("/1.0")
    assert relation_schema_v11.status_code == 200
    assert relation_schema_v11.json()["$id"].endswith("/1.1")
    assert relation_schema_v12.status_code == 200
    assert relation_schema_v12.json()["$id"].endswith("/1.2")
    assert disease_vocabulary_schema.status_code == 200
    assert disease_vocabulary_schema.json()["$id"].endswith(
        "/relation-vocabulary/disease/1.0"
    )


def test_workbench_page_labels_version_10() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))

    response = client.get("/")

    assert response.status_code == 200
    assert "KNOWLEDGE JSON 1.0" in response.text
    assert "医学的事実テンプレート 1.0" in response.text
    assert "Knowledge Completeness" in response.text
    assert "Exam Completeness" in response.text
    assert "国家試験重要claim" in response.text
    assert "出題履歴" in response.text
    assert "国家試験CSVを安全に取り込む" in response.text
    assert "サンプルをPreview" in response.text
    assert "Preview内容をImport" in response.text
    assert "Importメッセージ" in response.text
    assert "Knowledge Registry" in response.text
    assert "Claim Dictionary" in response.text
    assert "Claim統合" in response.text
    assert "承認操作" in response.text
    assert "Backup / Restore" in response.text
    assert "正式Knowledgeを登録・編集" in response.text
    assert "抗酸菌染色を開く" in response.text
    assert "塗抹標本を開く" in response.text
    assert "選択した試薬を開く" in response.text
    assert "クリスタルバイオレット" in response.text
    assert "フェリチンを開く" in response.text
    assert "Registryへ保存" in response.text
    assert "Source Bundle生成" in response.text
    assert "Presentation Engineへの受け渡しデータ" in response.text
    assert "関連Knowledge" in response.text
    assert "未登録の対象は推測せず" in response.text
    assert "Network Completeness" in response.text


def test_gram_stain_can_be_registered_edited_and_reloaded_as_formal_knowledge() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    before = client.get("/api/registry").json()

    starter_response = client.get("/api/knowledge-templates/staining-method/gram-stain")
    starter = starter_response.json()
    assert starter_response.status_code == 200
    assert starter["data"]["classification"]["term_type"] == "staining_method"
    assert starter["knowledge_completeness"]["score"] == 100
    assert client.get("/api/registry").json() == before

    knowledge_id = starter["data"]["knowledge_id"]
    saved_response = client.put(
        f"/api/knowledge-records/{knowledge_id}",
        json={
            "record": starter["data"],
            "actor": "product_owner",
            "comment": "正式Categoryとして登録",
        },
    )
    saved = saved_response.json()
    assert saved_response.status_code == 200
    assert saved["schema_valid"] is True
    assert saved["knowledge_completeness"]["score"] == 100
    assert saved["registry"]["knowledge"]["knowledge_version"] == 1
    assert len(saved["registry"]["claims"]) == 24
    assert len(saved["relations"]["relations"]) == 7
    assert saved["relations"]["validation"]["resolved_count"] == 0
    assert saved["relations"]["validation"]["unresolved_count"] == 7
    assert {item["relation_type"] for item in saved["relations"]["relations"]} == {
        "uses_specimen",
        "uses_reagent",
        "targets_structure",
        "related_method",
    }
    assert all(
        item["resolution_status"] == "unresolved_relation" and item["target_knowledge_id"] is None
        for item in saved["relations"]["relations"]
    )
    first_ids = {item["claim_key"]: item["claim_id"] for item in saved["registry"]["claims"]}
    reopened = client.get("/api/knowledge-templates/staining-method/gram-stain").json()
    assert reopened["persisted"] is True
    assert reopened["data"]["knowledge_id"] == knowledge_id

    reloaded = client.get(f"/api/knowledge-records/{knowledge_id}")
    assert reloaded.status_code == 200
    edited = reloaded.json()["data"]
    edited["category_content"]["staining_method"]["limitations"][0]["assertion"] += (
        "（オーナー確認）"
    )
    updated = client.put(
        f"/api/knowledge-records/{knowledge_id}",
        json={
            "record": edited,
            "actor": "product_owner",
            "comment": "限界の表現を確認",
        },
    ).json()
    second_ids = {item["claim_key"]: item["claim_id"] for item in updated["registry"]["claims"]}
    assert updated["registry"]["knowledge"]["knowledge_version"] == 2
    assert first_ids == second_ids
    assert updated["data"]["content_revision"] == 2
    assert all(item["version"] == 1 for item in updated["relations"]["relations"])

    relation_response = client.get(f"/api/knowledge-relations/{knowledge_id}")
    assert relation_response.status_code == 200
    assert relation_response.json()["validation"]["is_valid"] is True
    assert len(relation_response.json()["relations"]) == 7


def test_specimen_registration_resolves_gram_relation_without_changing_knowledge() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    gram_starter = client.get("/api/knowledge-templates/staining-method/gram-stain").json()["data"]
    gram_id = gram_starter["knowledge_id"]
    gram_saved = client.put(
        f"/api/knowledge-records/{gram_id}",
        json={
            "record": gram_starter,
            "actor": "product_owner",
            "comment": "Gram染色を登録",
        },
    ).json()
    gram_before = gram_saved["data"]
    assert gram_saved["relations"]["validation"]["resolved_count"] == 0

    specimen_starter_response = client.get("/api/knowledge-templates/specimen/smear-specimen")
    specimen_starter = specimen_starter_response.json()
    assert specimen_starter_response.status_code == 200
    assert specimen_starter["data"]["classification"]["term_type"] == "specimen"
    assert specimen_starter["knowledge_completeness"]["score"] == 100

    specimen_id = specimen_starter["data"]["knowledge_id"]
    specimen_saved_response = client.put(
        f"/api/knowledge-records/{specimen_id}",
        json={
            "record": specimen_starter["data"],
            "actor": "product_owner",
            "comment": "塗抹標本を正式Categoryとして登録",
        },
    )
    specimen_saved = specimen_saved_response.json()
    assert specimen_saved_response.status_code == 200
    assert specimen_saved["schema_valid"] is True
    assert specimen_saved["knowledge_completeness"]["score"] == 100
    assert specimen_saved["registry"]["knowledge"]["knowledge_version"] == 1
    assert len(specimen_saved["registry"]["claims"]) == 6
    assert specimen_saved["resolution_report"]["evaluated_count"] == 1
    assert specimen_saved["resolution_report"]["resolved_count"] == 1
    assert specimen_saved["resolution_report"]["unresolved_count"] == 0

    gram_reloaded = client.get(f"/api/knowledge-records/{gram_id}").json()
    assert gram_reloaded["data"] == gram_before
    relations = gram_reloaded["relations"]
    assert relations["schema_version"] == "1.1"
    assert relations["validation"]["resolved_count"] == 1
    assert relations["validation"]["unresolved_count"] == 6
    assert relations["network_summary"] == {
        "schema_version": "1.0",
        "knowledge_id": gram_id,
        "relation_count": 7,
        "resolved_count": 1,
        "unresolved_count": 6,
        "network_completeness": 14.3,
    }
    specimen_relation = next(
        item for item in relations["relations"] if item["relation_type"] == "uses_specimen"
    )
    assert specimen_relation["target_knowledge_id"] == specimen_id
    assert specimen_relation["target_label"] == "塗抹標本"
    assert specimen_relation["resolution_status"] == "resolved"
    assert specimen_relation["context"] == {
        "qualifiers": ["細菌を含む"],
        "preparation": "薄く均一に塗抹する。",
    }
    reports = client.get(f"/api/relation-resolution-reports/{specimen_id}")
    assert reports.status_code == 200
    assert reports.json()[-1]["resolved_count"] == 1


def test_four_reagents_grow_gram_network_without_rewriting_gram_knowledge() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    gram_starter = client.get(
        "/api/knowledge-templates/staining-method/gram-stain"
    ).json()["data"]
    gram_id = gram_starter["knowledge_id"]
    gram_saved = client.put(
        f"/api/knowledge-records/{gram_id}",
        json={
            "record": gram_starter,
            "actor": "product_owner",
            "comment": "Gram染色を登録",
        },
    ).json()

    specimen = client.get(
        "/api/knowledge-templates/specimen/smear-specimen"
    ).json()["data"]
    specimen_saved = client.put(
        f"/api/knowledge-records/{specimen['knowledge_id']}",
        json={
            "record": specimen,
            "actor": "product_owner",
            "comment": "塗抹標本を登録",
        },
    ).json()
    assert specimen_saved["resolution_report"]["evaluated_count"] == 1
    assert specimen_saved["resolution_report"]["resolved_count"] == 1
    assert specimen_saved["resolution_report"]["unresolved_count"] == 0
    before = client.get(f"/api/knowledge-records/{gram_id}").json()
    assert before["data"] == gram_saved["data"]
    assert before["relations"]["network_summary"]["network_completeness"] == 14.3

    reagent_slugs = [
        "crystal-violet",
        "gram-iodine",
        "gram-decolorizer",
        "gram-safranin",
    ]
    reagent_ids: set[str] = set()
    for slug in reagent_slugs:
        starter_response = client.get(f"/api/knowledge-templates/reagent/{slug}")
        starter = starter_response.json()
        assert starter_response.status_code == 200
        assert starter["data"]["classification"]["term_type"] == "reagent"
        assert starter["data"]["category_content"]["template_id"] == "reagent_v1.0"
        assert starter["knowledge_completeness"]["score"] == 100
        reagent_id = starter["data"]["knowledge_id"]
        reagent_ids.add(reagent_id)
        saved_response = client.put(
            f"/api/knowledge-records/{reagent_id}",
            json={
                "record": starter["data"],
                "actor": "product_owner",
                "comment": "Reagentを正式Categoryとして登録",
            },
        )
        saved = saved_response.json()
        assert saved_response.status_code == 200
        assert saved["schema_valid"] is True
        assert saved["knowledge_completeness"]["score"] == 100
        assert saved["registry"]["knowledge"]["knowledge_version"] == 1
        assert len(saved["registry"]["claims"]) == 6
        registry_key = saved["registry"]["knowledge"]["registry_key"]
        assert registry_key.startswith("reagent.gram.")
        assert all(
            item["claim_key"].startswith(registry_key + ".")
            for item in saved["registry"]["claims"]
        )
        assert saved["resolution_report"]["evaluated_count"] == 1
        assert saved["resolution_report"]["resolved_count"] == 1
        assert saved["resolution_report"]["unresolved_count"] == 0

    after = client.get(f"/api/knowledge-records/{gram_id}").json()
    assert after["data"] == gram_saved["data"]
    relations = after["relations"]
    assert relations["network_summary"] == {
        "schema_version": "1.0",
        "knowledge_id": gram_id,
        "relation_count": 7,
        "resolved_count": 5,
        "unresolved_count": 2,
        "network_completeness": 71.4,
    }
    reagent_relations = [
        item for item in relations["relations"] if item["relation_type"] == "uses_reagent"
    ]
    assert len(reagent_relations) == 4
    assert {item["target_knowledge_id"] for item in reagent_relations} == reagent_ids
    assert all(item["resolution_status"] == "resolved" for item in reagent_relations)
    assert sum(
        len(client.get(f"/api/relation-resolution-reports/{knowledge_id}").json())
        for knowledge_id in reagent_ids
    ) == 4


def test_acid_fast_stain_reuses_staining_schema_and_grows_gram_network() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    gram = client.get(
        "/api/knowledge-templates/staining-method/gram-stain"
    ).json()["data"]
    gram_id = gram["knowledge_id"]
    gram_saved = client.put(
        f"/api/knowledge-records/{gram_id}",
        json={
            "record": gram,
            "actor": "product_owner",
            "comment": "Gram染色を登録",
        },
    ).json()
    specimen = client.get(
        "/api/knowledge-templates/specimen/smear-specimen"
    ).json()["data"]
    client.put(
        f"/api/knowledge-records/{specimen['knowledge_id']}",
        json={"record": specimen, "actor": "product_owner", "comment": "塗抹標本を登録"},
    )
    for slug in [
        "crystal-violet",
        "gram-iodine",
        "gram-decolorizer",
        "gram-safranin",
    ]:
        reagent = client.get(f"/api/knowledge-templates/reagent/{slug}").json()["data"]
        client.put(
            f"/api/knowledge-records/{reagent['knowledge_id']}",
            json={"record": reagent, "actor": "product_owner", "comment": "試薬を登録"},
        )
    assert client.get(f"/api/knowledge-records/{gram_id}").json()["relations"][
        "network_summary"
    ]["network_completeness"] == 71.4

    starter_response = client.get(
        "/api/knowledge-templates/staining-method/acid-fast-stain"
    )
    starter = starter_response.json()
    assert starter_response.status_code == 200
    assert starter["persisted"] is False
    assert starter["schema_valid"] is True
    assert starter["data"]["classification"]["term_type"] == "staining_method"
    assert starter["data"]["category_content"]["template_id"] == "staining_method_v1.0"
    assert starter["knowledge_completeness"]["score"] == 100

    acid_fast_id = starter["data"]["knowledge_id"]
    saved_response = client.put(
        f"/api/knowledge-records/{acid_fast_id}",
        json={
            "record": starter["data"],
            "actor": "product_owner",
            "comment": "抗酸菌染色を既存Categoryへ登録",
        },
    )
    saved = saved_response.json()
    assert saved_response.status_code == 200
    assert saved["schema_valid"] is True
    assert saved["knowledge_completeness"]["score"] == 100
    assert saved["registry"]["knowledge"]["registry_key"] == "acidfast.stain"
    assert saved["registry"]["knowledge"]["knowledge_version"] == 1
    assert all(
        item["claim_key"].startswith("acidfast.stain.")
        for item in saved["registry"]["claims"]
    )
    assert saved["resolution_report"]["evaluated_count"] == 1
    assert saved["resolution_report"]["resolved_count"] == 1
    assert saved["resolution_report"]["unresolved_count"] == 0

    gram_after = client.get(f"/api/knowledge-records/{gram_id}").json()
    assert gram_after["data"] == gram_saved["data"]
    assert gram_after["relations"]["network_summary"] == {
        "schema_version": "1.0",
        "knowledge_id": gram_id,
        "relation_count": 7,
        "resolved_count": 6,
        "unresolved_count": 1,
        "network_completeness": 85.7,
    }
    related_method = next(
        item
        for item in gram_after["relations"]["relations"]
        if item["relation_type"] == "related_method"
    )
    assert related_method["target_knowledge_id"] == acid_fast_id
    assert related_method["target_label"] == "抗酸菌染色"
    assert related_method["resolution_status"] == "resolved"
    reports = client.get(f"/api/relation-resolution-reports/{acid_fast_id}").json()
    assert reports[-1]["evaluated_count"] == 1
    assert reports[-1]["resolved_count"] == 1


def test_acid_fast_stain_can_be_reopened_and_edited_with_stable_claim_identity() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    starter = client.get(
        "/api/knowledge-templates/staining-method/acid-fast-stain"
    ).json()["data"]
    knowledge_id = starter["knowledge_id"]
    first = client.put(
        f"/api/knowledge-records/{knowledge_id}",
        json={
            "record": starter,
            "actor": "product_owner",
            "comment": "抗酸菌染色を登録",
        },
    ).json()
    first_ids = {
        item["claim_key"]: item["claim_id"] for item in first["registry"]["claims"]
    }

    reopened = client.get(
        "/api/knowledge-templates/staining-method/acid-fast-stain"
    ).json()
    assert reopened["persisted"] is True
    edited = reopened["data"]
    edited["category_content"]["staining_method"]["limitations"][0]["assertion"] += (
        " 標準作業書を確認する。"
    )
    second = client.put(
        f"/api/knowledge-records/{knowledge_id}",
        json={
            "record": edited,
            "actor": "product_owner",
            "comment": "限界を医学的に更新",
        },
    ).json()
    second_ids = {
        item["claim_key"]: item["claim_id"] for item in second["registry"]["claims"]
    }
    assert second["registry"]["knowledge"]["knowledge_version"] == 2
    assert second["data"]["content_revision"] == 2
    assert first_ids == second_ids


def test_unknown_reagent_starter_is_not_loaded_from_arbitrary_path() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))

    response = client.get("/api/knowledge-templates/reagent/not-registered")

    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "reagent_starter_not_found"


def test_reagent_can_be_reopened_and_edited_with_stable_claim_identity() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    starter = client.get(
        "/api/knowledge-templates/reagent/crystal-violet"
    ).json()["data"]
    knowledge_id = starter["knowledge_id"]
    first = client.put(
        f"/api/knowledge-records/{knowledge_id}",
        json={
            "record": starter,
            "actor": "product_owner",
            "comment": "Reagentを登録",
        },
    ).json()
    first_claim_ids = {
        item["claim_key"]: item["claim_id"] for item in first["registry"]["claims"]
    }

    reopened = client.get(
        "/api/knowledge-templates/reagent/crystal-violet"
    ).json()
    assert reopened["persisted"] is True
    edited = reopened["data"]
    edited["category_content"]["reagent"]["usage_steps"][0]["assertion"] += (
        " 施設手順を確認する。"
    )
    second = client.put(
        f"/api/knowledge-records/{knowledge_id}",
        json={
            "record": edited,
            "actor": "product_owner",
            "comment": "使用工程を医学的に更新",
        },
    ).json()
    second_claim_ids = {
        item["claim_key"]: item["claim_id"] for item in second["registry"]["claims"]
    }

    assert second["registry"]["knowledge"]["knowledge_version"] == 2
    assert second["data"]["content_revision"] == 2
    assert first_claim_ids == second_claim_ids
    assert client.get(f"/api/knowledge-records/{knowledge_id}").json()["data"] == second["data"]


def test_registry_endpoint_persists_generated_dictionary_for_current_app() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    generated = client.post("/api/generate", json={"term": "AST"}).json()

    response = client.get(f"/api/registry/{generated['data']['knowledge_id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["knowledge"]["registry_key"] == "ast"
    assert payload["validation"]["is_valid"] is True
    assert {item["claim_key"] for item in payload["claims"]} >= {
        "ast.is_leakage_enzyme",
        "ast.measurement.340nm",
        "ast.jscc",
        "ast.ifcc",
    }


def test_workbench_api_shows_provider_error() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))

    response = client.post("/api/generate", json={"term": "任意の用語"})

    assert response.status_code == 503
    assert response.json()["errors"][0]["code"] == "ai_generation_failed"


def test_missing_openai_key_is_shown_as_configuration_error() -> None:
    client = TestClient(
        create_app(
            settings=Settings(
                provider="openai",
                openai_api_key="",
                openai_model="test-model",
            )
        )
    )

    response = client.post("/api/generate", json={"term": "AST"})

    assert response.status_code == 503
    assert response.json()["errors"][0]["code"] == "provider_not_configured"


def test_sample_exam_csv_import_endpoint_returns_report_and_assets() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))

    before = client.get("/api/registry").json()
    response = client.post("/api/import/exam-csv/preview/sample")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["phase"] == "preview"
    assert payload["preview"]["can_commit"] is True
    assert len(payload["preview"]["new_knowledge_ids"]) == 2
    assert payload["report"]["validation"]["can_import"] is True
    assert payload["report"]["mapped_record_count"] == 4
    assert payload["report"]["metadata_record_count"] == 2
    assert payload["report"]["image_mapped_count"] == 2
    assert {item["canonical_theme"] for item in payload["mapped_records"]} == {
        "AST",
        "HbA1c",
    }
    assert len(payload["report"]["diff"]["added_source_row_ids"]) == 4
    assert client.get("/api/registry").json() == before

    imported = client.post(
        "/api/import/exam-csv/commit",
        json={"preview_id": payload["preview"]["preview_id"]},
    ).json()
    assert imported["phase"] == "imported"
    assert len(client.get("/api/registry").json()["knowledge"]) == 2

    repeated = client.post("/api/import/exam-csv/preview/sample").json()
    assert repeated["report"]["diff"]["added_source_row_ids"] == []
    assert len(repeated["report"]["diff"]["unchanged_source_row_ids"]) == 4


def test_uploaded_csv_endpoint_reports_validation_errors_without_crashing() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    invalid_csv = (
        "年度,午前午後,問題番号,テーマ,出題パターン,確認知識\n2027,午前,1,AST,単独知識,定義\n"
    )

    response = client.post(
        "/api/import/exam-csv",
        json={
            "source_file": "invalid.csv",
            "csv_base64": base64.b64encode(invalid_csv.encode()).decode(),
            "import_mode": "replace",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "validation_error"
    assert payload["report"]["validation"]["can_import"] is False
    assert payload["report"]["validation"]["required_columns_missing"] == ["session_number"]


def test_registry_approval_merge_and_backup_endpoints() -> None:
    client = TestClient(create_app(provider=FixtureKnowledgeProvider()))
    generated = client.post("/api/generate", json={"term": "AST"}).json()
    knowledge_id = generated["data"]["knowledge_id"]
    characteristics = [
        item
        for item in generated["registry"]["claims"]
        if item["field_path"].endswith("analyte_characteristics")
    ]
    target, source = characteristics[:2]

    for status in ("owner_review", "medical_review", "approved"):
        response = client.post(
            f"/api/registry/{knowledge_id}/claims/status",
            json={
                "claim_ids": [target["claim_id"]],
                "target_status": status,
                "actor": "API確認者",
                "comment": f"{status}へ進める",
            },
        )
        assert response.status_code == 200

    merge = client.post(
        f"/api/registry/{knowledge_id}/claims/merge",
        json={
            "target_claim_id": target["claim_id"],
            "source_claim_ids": [source["claim_id"]],
            "actor": "API確認者",
            "comment": "同じ意味として統合",
        },
    )
    assert merge.status_code == 200
    merged = merge.json()["registry"]
    assert merged["merge_redirects"][0]["target_claim_id"] == target["claim_id"]
    stored_after_merge = client.get(f"/api/knowledge-records/{knowledge_id}")
    assert stored_after_merge.status_code == 200
    serialized_record = str(stored_after_merge.json()["data"])
    assert source["claim_id"] not in serialized_record
    assert target["claim_id"] in serialized_record

    backup = client.post("/api/registry-backups")
    assert backup.status_code == 200
    filename = backup.json()["backup"]["filename"]
    assert filename.startswith("registry_")
    assert client.get("/api/registry-backups").json()["backups"]

    restore = client.post("/api/registry-backups/restore", json={"filename": filename})
    assert restore.status_code == 200
    assert restore.json()["safety_backup"]["filename"] != filename
