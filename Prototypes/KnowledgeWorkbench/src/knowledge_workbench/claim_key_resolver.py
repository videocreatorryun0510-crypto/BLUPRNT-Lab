"""Assign semantic claim_key values without depending on AI list order."""

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any


@dataclass
class ClaimCandidate:
    old_claim_ids: list[str]
    claim_key: str
    field_path: str
    assertion: str
    payload: dict[str, Any]
    container: list[object]
    index: int

    @property
    def old_claim_id(self) -> str:
        """Return the primary source ID for backward-compatible callers."""

        return self.old_claim_ids[0]


def registry_key_for_record(raw: dict[str, Any]) -> str:
    term = raw.get("term")
    if not isinstance(term, dict):
        raise ValueError("Knowledge JSON term is missing")
    names = [term.get("canonical_name"), *(term.get("aliases") or [])]
    normalized = {_normalized(str(item)) for item in names if item}
    if "ast" in normalized or "got" in normalized:
        return "ast"
    if "hba1c" in normalized or "ヘモグロビンa1c" in normalized:
        return "hba1c"
    if "gram染色" in normalized or "グラム染色" in normalized or "gram stain" in normalized:
        return "gram.stain"
    if {
        "抗酸菌染色",
        "ziehl-neelsen染色",
        "チール・ネルゼン染色",
        "ziehl-neelsen stain",
    }.intersection(normalized):
        return "acidfast.stain"
    if "塗抹標本" in normalized or "スメア標本" in normalized or "smear specimen" in normalized:
        return "specimen.smear"
    if (
        "細菌細胞壁" in normalized
        or "bacterial cell wall" in normalized
        or "細菌の細胞壁" in normalized
    ):
        return "structure.bacterial_cell_wall"
    if (
        "鉄欠乏性貧血" in normalized
        or "iron deficiency anemia" in normalized
        or "ida" in normalized
    ):
        return "disease.iron_deficiency_anemia"
    if (
        "フェリチン" in normalized
        or "血清フェリチン" in normalized
        or "ferritin" in normalized
        or "fer" in normalized
    ):
        return "laboratory_test.ferritin"
    reagent_registry_keys = {
        "クリスタルバイオレット": "reagent.gram.crystal_violet",
        "グラム染色用ヨウ素液": "reagent.gram.iodine",
        "ヨウ素液": "reagent.gram.iodine",
        "グラム染色用脱色液": "reagent.gram.decolorizer",
        "脱色液": "reagent.gram.decolorizer",
        "グラム染色用サフラニン対比染色液": "reagent.gram.safranin",
        "サフラニン": "reagent.gram.safranin",
        "対比染色液": "reagent.gram.safranin",
    }
    for label, registry_key in reagent_registry_keys.items():
        if _normalized(label) in normalized:
            return registry_key
    canonical = str(term.get("canonical_name") or "knowledge")
    return f"k{_digest(_normalized(canonical))[:12]}"


def extract_claim_candidates(raw: dict[str, Any], registry_key: str) -> list[ClaimCandidate]:
    candidates: list[ClaimCandidate] = []

    def visit(value: object, path: list[str]) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if isinstance(child, list):
                    list_path = [*path, key]
                    for index, item in enumerate(child):
                        if isinstance(item, dict) and isinstance(item.get("claim_id"), str):
                            candidates.append(
                                _candidate(
                                    item,
                                    child,
                                    index,
                                    ".".join(list_path),
                                    registry_key,
                                )
                            )
                        visit(item, list_path)
                elif isinstance(child, dict):
                    visit(child, [*path, key])

    visit(raw, [])
    return collapse_semantic_duplicates(candidates)


def _candidate(
    payload: dict[str, Any],
    container: list[object],
    index: int,
    field_path: str,
    registry_key: str,
) -> ClaimCandidate:
    old_claim_id = str(payload["claim_id"])
    assertion = _assertion(payload)
    claim_key = _known_claim_key(registry_key, field_path, payload, assertion)
    if claim_key is None:
        scope = _scope(field_path)
        identity = _identity(payload, assertion)
        claim_key = f"{registry_key}.{scope}.{identity}"
    return ClaimCandidate(
        old_claim_ids=[old_claim_id],
        claim_key=claim_key,
        field_path=field_path,
        assertion=assertion,
        payload=payload,
        container=container,
        index=index,
    )


def collapse_semantic_duplicates(
    candidates: list[ClaimCandidate],
) -> list[ClaimCandidate]:
    """Keep one fact when AI repeats the same known semantic claim.

    The selected payload is based on content richness and a deterministic tie-break,
    never list position. Every discarded source claim ID is retained so references can
    be rewritten to the Registry-owned claim ID.
    """

    grouped: dict[str, list[ClaimCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.claim_key, []).append(candidate)

    survivors: list[ClaimCandidate] = []
    discarded: list[ClaimCandidate] = []
    for group in grouped.values():
        survivor = max(group, key=_candidate_quality)
        survivor.old_claim_ids = sorted(
            {source_id for item in group for source_id in item.old_claim_ids}
        )
        survivors.append(survivor)
        discarded.extend(item for item in group if item is not survivor)

    removals: dict[int, tuple[list[object], list[int]]] = {}
    for candidate in discarded:
        container_id = id(candidate.container)
        if container_id not in removals:
            removals[container_id] = (candidate.container, [])
        removals[container_id][1].append(candidate.index)
    for container, indexes in removals.values():
        for index in sorted(indexes, reverse=True):
            del container[index]

    for survivor in survivors:
        survivor.index = next(
            index for index, item in enumerate(survivor.container) if item is survivor.payload
        )

    survivor_ids = {id(item) for item in survivors}
    return [item for item in candidates if id(item) in survivor_ids]


def _candidate_quality(candidate: ClaimCandidate) -> tuple[int, int, str]:
    non_empty_fields = sum(
        value not in (None, "", []) for key, value in candidate.payload.items() if key != "claim_id"
    )
    stable_payload = json.dumps(
        candidate.payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return non_empty_fields, len(candidate.assertion), stable_payload


def _known_claim_key(
    registry_key: str,
    field_path: str,
    payload: dict[str, Any],
    assertion: str,
) -> str | None:
    text = _normalized(" ".join(str(value) for value in payload.values()))
    if registry_key == "ast":
        if field_path.endswith("biological_basis") and "逸脱" in text:
            return "ast.is_leakage_enzyme"
        if field_path.endswith("measurement_principles") and "340" in text:
            return "ast.measurement.340nm"
        if field_path.endswith("measurement_methods") and "jscc" in text:
            return "ast.jscc"
        if field_path.endswith("measurement_methods") and "ifcc" in text:
            return "ast.ifcc"
        if field_path.endswith("high.pathophysiologic_states") and ("肝細胞障害" in text):
            return "ast.high.hepatocyte_damage"
        if field_path.endswith("definitions"):
            return "ast.definition.aminotransferase_enzyme"
        if field_path.endswith("interpretation_cautions") and "溶血" in text:
            return "ast.interpretation.hemolysis"
        if field_path.endswith("interpretation_cautions") and "障害臓器" in text:
            return "ast.interpretation.organ_nonspecific"
    if registry_key == "hba1c":
        if field_path.endswith("definitions"):
            return "hba1c.definition.glycated_hemoglobin"
        if field_path.endswith("measurement_methods") and "hplc" in text:
            return "hba1c.measurement.hplc"
        if field_path.endswith("measurement_methods") and "免疫" in text:
            return "hba1c.measurement.immunoassay"
        if field_path.endswith("measurement_methods") and "酵素" in text:
            return "hba1c.measurement.enzymatic"
        if field_path.endswith("measurement_principles"):
            return "hba1c.measurement.principle"
        if field_path.endswith("interpretation_cautions") and "赤血球寿命" in text:
            return "hba1c.interpretation.shortened_rbc_lifespan"
        if field_path.endswith("interpretation_cautions") and "輸血" in text:
            return "hba1c.interpretation.transfusion"
    if registry_key == "gram.stain":
        if field_path.endswith("definitions"):
            return "gram.stain.definition.differential_stain"
        if field_path.endswith("biological_basis") and "細胞壁" in text:
            return "gram.stain.basis.cell_wall"
        if field_path.endswith("target_structures") and "細胞壁" in text:
            return "gram.stain.basis.cell_wall"
        if field_path.endswith("purposes"):
            return "gram.stain.purpose.gram_reaction_morphology"
        if field_path.endswith("specimens") and "塗抹" in text:
            return "gram.stain.specimen.smear"
        if field_path.endswith("applicable_specimens") and "塗抹" in text:
            return "gram.stain.specimen.smear"
        if field_path.endswith("fixation_requirements"):
            return "gram.stain.fixation.smear"
        if field_path.endswith("reagents"):
            role = str(payload.get("reagent_role") or "other")
            return f"gram.stain.reagent.{role}"
        if field_path.endswith("procedure_steps"):
            step_order = payload.get("step_order")
            step_keys = {
                1: "gram.stain.procedure.step1_primary_stain",
                2: "gram.stain.procedure.step2_mordant",
                3: "gram.stain.procedure.step3_decolorization",
                4: "gram.stain.procedure.step4_counterstain",
            }
            if step_order in step_keys:
                return step_keys[step_order]
        if field_path.endswith("measurement_methods"):
            if "工程1" in text or "一次染色" in text:
                return "gram.stain.procedure.step1_primary_stain"
            if "工程2" in text or "媒染" in text:
                return "gram.stain.procedure.step2_mordant"
            if "工程4" in text or "対比染色" in text:
                return "gram.stain.procedure.step4_counterstain"
            if "工程3" in text or "脱色" in text:
                return "gram.stain.procedure.step3_decolorization"
        if field_path.endswith("measurement_principles"):
            if "複合体" in text and "形成" in text:
                return "gram.stain.principle.dye_iodine_complex"
            if "保持性" in text or "細胞壁構造" in text:
                return "gram.stain.principle.differential_retention"
        if field_path.endswith("staining_principles"):
            if "複合体" in text and "形成" in text:
                return "gram.stain.principle.dye_iodine_complex"
            if "保持性" in text or "細胞壁構造" in text:
                return "gram.stain.principle.differential_retention"
        if field_path.endswith("analyte_characteristics"):
            if "gram陽性" in text and "紫色" in text:
                return "gram.stain.result.gram_positive_purple"
            if "gram陰性" in text and ("赤色" in text or "赤桃色" in text):
                return "gram.stain.result.gram_negative_red"
        if field_path.endswith("result_interpretations"):
            if "gram陽性" in text and "紫色" in text:
                return "gram.stain.result.gram_positive_purple"
            if "gram陰性" in text and ("赤色" in text or "赤桃色" in text):
                return "gram.stain.result.gram_negative_red"
        if field_path.endswith("quality_controls"):
            if "gram陽性" in text:
                return "gram.stain.quality_control.gram_positive"
            if "gram陰性" in text:
                return "gram.stain.quality_control.gram_negative"
        if field_path.endswith("interpretation_cautions"):
            if "過脱色" in text:
                return "gram.stain.error.over_decolorization"
            if "脱色不足" in text:
                return "gram.stain.error.under_decolorization"
            if "抗酸菌" in text:
                return "gram.stain.limitation.acid_fast_bacteria"
            if "マイコプラズマ" in text:
                return "gram.stain.limitation.mycoplasma"
        if field_path.endswith("error_causes"):
            if "過脱色" in text or payload.get("error_type") == "over_decolorization":
                return "gram.stain.error.over_decolorization"
            if "脱色不足" in text or payload.get("error_type") == "under_decolorization":
                return "gram.stain.error.under_decolorization"
        if field_path.endswith("limitations"):
            if "抗酸菌" in text:
                return "gram.stain.limitation.acid_fast_bacteria"
            if "マイコプラズマ" in text:
                return "gram.stain.limitation.mycoplasma"
        if field_path.endswith("related_methods") and "抗酸" in text:
            return "gram.stain.related_method.acid_fast"
    if registry_key == "acidfast.stain":
        if field_path.endswith("definitions"):
            return "acidfast.stain.definition"
        if field_path.endswith("purposes"):
            return "acidfast.stain.purpose.detect_acid_fast_bacteria"
        if field_path.endswith("target_structures"):
            return "acidfast.stain.target.lipid_rich_cell_wall"
        if field_path.endswith("applicable_specimens"):
            return "acidfast.stain.specimen.sputum_smear"
        if field_path.endswith("fixation_requirements"):
            return "acidfast.stain.fixation.smear"
        if field_path.endswith("staining_principles"):
            if "加温" in text:
                return "acidfast.stain.principle.heat_assisted_penetration"
            if "酸アルコール" in text:
                return "acidfast.stain.principle.acid_fast_retention"
        if field_path.endswith("reagents"):
            role = str(payload.get("reagent_role") or "other")
            return f"acidfast.stain.reagent.{role}"
        if field_path.endswith("procedure_steps"):
            step_order = payload.get("step_order")
            step_keys = {
                1: "acidfast.stain.procedure.step1_primary_stain_and_heat",
                2: "acidfast.stain.procedure.step2_decolorization",
                3: "acidfast.stain.procedure.step3_counterstain",
                4: "acidfast.stain.procedure.step4_microscopy",
            }
            if step_order in step_keys:
                return step_keys[step_order]
        if field_path.endswith("result_interpretations"):
            if payload.get("target_name") == "抗酸菌":
                return "acidfast.stain.result.acid_fast_red"
            return "acidfast.stain.result.background_blue"
        if field_path.endswith("quality_controls"):
            if "陽性" in text:
                return "acidfast.stain.quality_control.positive"
            if "陰性" in text:
                return "acidfast.stain.quality_control.negative"
        if field_path.endswith("error_causes"):
            error_type = str(payload.get("error_type") or "other")
            return f"acidfast.stain.error.{error_type}"
        if field_path.endswith("limitations"):
            return "acidfast.stain.limitation.technique_dependent"
        if field_path.endswith("safety_considerations"):
            return "acidfast.stain.safety.heat_phenol_infectious_specimen"
    if registry_key == "specimen.smear":
        if field_path.endswith("definitions"):
            return "specimen.smear.definition"
        if field_path.endswith("overview"):
            return "specimen.smear.overview"
        if field_path.endswith("uses"):
            return "specimen.smear.use.microscopy"
        if field_path.endswith("collection_methods"):
            return "specimen.smear.preparation.thin_uniform"
        if field_path.endswith("storage_conditions"):
            return "specimen.smear.storage.follow_sop"
        if field_path.endswith("cautions"):
            return "specimen.smear.caution.fixation_not_inactivation"
    if registry_key.startswith("reagent.gram."):
        if field_path.endswith("definitions"):
            return f"{registry_key}.definition"
        if field_path.endswith("purposes"):
            return f"{registry_key}.purpose.gram_stain"
        if field_path.endswith("targets"):
            return f"{registry_key}.target.smear"
        if field_path.endswith("usage_steps"):
            usage_phase = str(payload.get("usage_phase") or "other")
            return f"{registry_key}.usage.{usage_phase}"
        if field_path.endswith("cautions"):
            return f"{registry_key}.caution.handling_and_quality"
        if field_path.endswith("storage_conditions"):
            return f"{registry_key}.storage.follow_ifu"
    if registry_key == "structure.bacterial_cell_wall":
        if field_path.endswith("definitions"):
            return "structure.bacterial_cell_wall.definition"
        if field_path.endswith("overview"):
            return "structure.bacterial_cell_wall.overview.gram_differentiation"
        if field_path.endswith("main_functions"):
            return "structure.bacterial_cell_wall.function.shape_and_protection"
        if field_path.endswith("main_components"):
            return "structure.bacterial_cell_wall.component.peptidoglycan"
        if field_path.endswith("organisms_present"):
            return "structure.bacterial_cell_wall.organism.distribution"
    if registry_key == "disease.iron_deficiency_anemia":
        if field_path.endswith("definitions"):
            return "disease.iron_deficiency_anemia.definition"
        if field_path.endswith("overview"):
            return "disease.iron_deficiency_anemia.overview"
        if field_path.endswith("pathophysiology"):
            process_name = str(payload.get("process_name") or "other")
            pathophysiology_keys = {
                "貯蔵鉄の枯渇": "iron_store_depletion",
                "ヘモグロビン合成障害": "impaired_hemoglobin_synthesis",
            }
            return (
                "disease.iron_deficiency_anemia.pathophysiology."
                + pathophysiology_keys.get(process_name, _key_segment(process_name))
            )
        if field_path.endswith("causes"):
            cause_name = str(payload.get("cause_name") or "other")
            cause_keys = {
                "慢性出血による鉄喪失": "chronic_blood_loss",
                "鉄需要の増加": "increased_demand",
                "鉄摂取不足または吸収障害": "inadequate_intake_or_absorption",
            }
            return (
                "disease.iron_deficiency_anemia.cause."
                + cause_keys.get(cause_name, _key_segment(cause_name))
            )
        if field_path.endswith("main_symptoms"):
            finding_name = str(payload.get("finding_name") or "other")
            symptom_keys = {
                "一般的な貧血症状": "general_anemia_symptoms",
                "組織鉄欠乏に関連する所見": "tissue_iron_deficiency_findings",
            }
            return (
                "disease.iron_deficiency_anemia.symptom."
                + symptom_keys.get(finding_name, _key_segment(finding_name))
            )
        if field_path.endswith("main_laboratory_findings"):
            test_name = str(payload.get("test_name") or "other")
            laboratory_keys = {
                "血算・赤血球指数": "cbc.microcytic_hypochromic",
                "血清フェリチン": "ferritin.low",
                "血清鉄": "serum_iron.low",
                "総鉄結合能（TIBC）": "tibc.high",
                "トランスフェリン飽和度": "transferrin_saturation.low",
                "末梢血塗抹標本": "blood_smear.microcytic_hypochromic",
            }
            return (
                "disease.iron_deficiency_anemia.laboratory."
                + laboratory_keys.get(test_name, _key_segment(test_name))
            )
        if field_path.endswith("differential_points"):
            disease_name = str(payload.get("compared_disease_name") or "other")
            differential_keys = {
                "慢性炎症に伴う貧血": "anemia_of_inflammation",
                "サラセミア": "thalassemia",
            }
            return (
                "disease.iron_deficiency_anemia.differential."
                + differential_keys.get(disease_name, _key_segment(disease_name))
            )
    if registry_key == "laboratory_test.ferritin":
        if field_path.endswith("definitions"):
            return "labtest.ferritin.definition"
        if field_path.endswith("overview"):
            return "labtest.ferritin.overview"
        if field_path.endswith("measured_targets"):
            return "labtest.ferritin.target.serum_or_plasma_ferritin"
        if field_path.endswith("clinical_significance"):
            significance_name = str(payload.get("significance_name") or "other")
            significance_keys = {
                "貯蔵鉄の評価": "iron_store",
                "炎症を考慮した解釈": "inflammation_interpretation",
            }
            return (
                "labtest.ferritin.clinical_significance."
                + significance_keys.get(
                    significance_name, _key_segment(significance_name)
                )
            )
        if field_path.endswith("high_conditions"):
            condition_name = str(payload.get("condition_name") or "other")
            high_keys = {
                "鉄過剰": "iron_overload",
                "炎症": "inflammation",
                "マクロファージ活性化を伴う病態": "macrophage_activation",
            }
            return (
                "labtest.ferritin.high."
                + high_keys.get(condition_name, _key_segment(condition_name))
            )
        if field_path.endswith("low_conditions"):
            condition_name = str(payload.get("condition_name") or "other")
            if condition_name == "鉄欠乏":
                return "labtest.ferritin.low.iron_deficiency"
        if field_path.endswith("measurement_methods"):
            method_name = str(payload.get("method_name") or "other")
            method_keys = {
                "ラテックス凝集比濁法": "ltia",
                "化学発光酵素免疫測定法": "cleia",
            }
            return (
                "labtest.ferritin.method."
                + method_keys.get(method_name, _key_segment(method_name))
            )
    del assertion
    return None


def _scope(field_path: str) -> str:
    known = {
        "core_facts.definitions": "definition",
        "category_content.test_item.biological_basis": "biological_basis",
        "category_content.test_item.analyte_characteristics": "characteristic",
        "category_content.test_item.purposes": "purpose",
        "category_content.test_item.specimens": "specimen",
        "category_content.test_item.measurement_methods": "measurement.method",
        "category_content.test_item.measurement_principles": "measurement.principle",
        "category_content.test_item.reference_ranges": "reference_range",
        "category_content.test_item.value_associations.high.pathophysiologic_states": (
            "high.state"
        ),
        "category_content.test_item.value_associations.high.representative_diseases": (
            "high.disease"
        ),
        "category_content.test_item.value_associations.high.interpretive_notes": (
            "high.interpretation"
        ),
        "category_content.test_item.value_associations.low.pathophysiologic_states": ("low.state"),
        "category_content.test_item.value_associations.low.representative_diseases": (
            "low.disease"
        ),
        "category_content.test_item.value_associations.low.interpretive_notes": (
            "low.interpretation"
        ),
        "category_content.test_item.related_test_combinations": "combination",
        "category_content.test_item.interpretation_cautions": "interpretation",
        "category_content.staining_method.purposes": "purpose",
        "category_content.staining_method.target_structures": "target_structure",
        "category_content.staining_method.applicable_specimens": "specimen",
        "category_content.staining_method.fixation_requirements": "fixation",
        "category_content.staining_method.staining_principles": "principle",
        "category_content.staining_method.reagents": "reagent",
        "category_content.staining_method.procedure_steps": "procedure",
        "category_content.staining_method.result_interpretations": "result",
        "category_content.staining_method.quality_controls": "quality_control",
        "category_content.staining_method.error_causes": "error",
        "category_content.staining_method.limitations": "limitation",
        "category_content.staining_method.safety_considerations": "safety",
        "category_content.staining_method.related_methods": "related_method",
        "category_content.specimen.overview": "overview",
        "category_content.specimen.uses": "use",
        "category_content.specimen.collection_methods": "collection",
        "category_content.specimen.storage_conditions": "storage",
        "category_content.specimen.cautions": "caution",
        "category_content.reagent.purposes": "purpose",
        "category_content.reagent.targets": "target",
        "category_content.reagent.usage_steps": "usage",
        "category_content.reagent.cautions": "caution",
        "category_content.reagent.storage_conditions": "storage",
        "category_content.biological_structure.overview": "overview",
        "category_content.biological_structure.main_functions": "function",
        "category_content.biological_structure.main_components": "component",
        "category_content.biological_structure.organisms_present": "organism",
        "category_content.disease.overview": "overview",
        "category_content.disease.pathophysiology": "pathophysiology",
        "category_content.disease.causes": "cause",
        "category_content.disease.main_symptoms": "symptom",
        "category_content.disease.main_laboratory_findings": "laboratory",
        "category_content.disease.differential_points": "differential",
        "category_content.laboratory_test_item.overview": "overview",
        "category_content.laboratory_test_item.measured_targets": "target",
        "category_content.laboratory_test_item.clinical_significance": (
            "clinical_significance"
        ),
        "category_content.laboratory_test_item.high_conditions": "high",
        "category_content.laboratory_test_item.low_conditions": "low",
        "category_content.laboratory_test_item.measurement_methods": "method",
    }
    return known.get(field_path, f"fact.{_digest(field_path)[:8]}")


def _identity(payload: dict[str, Any], assertion: str) -> str:
    preferred = (
        "method_name",
        "specimen",
        "state_name",
        "disease_name",
        "interference_name",
        "event_or_condition",
        "isoenzyme_name",
        "system_name",
        "limit_name",
        "target_name",
        "reagent_name",
        "fixative_or_method",
        "control_material",
        "scope_or_target",
        "use_case",
        "function_name",
        "component_name",
        "organism_name",
        "process_name",
        "cause_name",
        "finding_name",
        "test_name",
        "compared_disease_name",
        "analyte_name",
        "significance_name",
        "condition_name",
    )
    for key in preferred:
        value = payload.get(key)
        if value:
            return _key_segment(str(value))
    if payload.get("measured_quantity"):
        value = f"{payload['measured_quantity']}:{payload.get('wavelength_or_endpoint') or ''}"
        return _key_segment(value)
    if payload.get("related_test_names"):
        return _key_segment(":".join(str(v) for v in payload["related_test_names"]))
    if payload.get("population") or payload.get("unit"):
        value = ":".join(
            str(payload.get(key) or "")
            for key in ("population", "specimen", "unit", "qualitative_value")
        )
        return _key_segment(value)
    return f"fact_{_digest(_normalized(assertion))[:12]}"


def _assertion(payload: dict[str, Any]) -> str:
    for key in (
        "assertion",
        "handling",
        "conditions",
        "traceability",
        "reaction_sequence",
        "distribution_or_property",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:800]
    meaningful = [
        str(value)
        for key, value in payload.items()
        if key != "claim_id" and value not in (None, "", [])
    ]
    return " / ".join(meaningful)[:800] or "構造化された医学的事実"


def _key_segment(value: str) -> str:
    normalized = _normalized(value)
    ascii_tokens = re.findall(r"[a-z0-9]+", normalized)
    if ascii_tokens:
        readable = "_".join(ascii_tokens)[:48].strip("_")
        if readable:
            return readable
    return f"key_{_digest(normalized)[:12]}"


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).strip().casefold().split())


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
