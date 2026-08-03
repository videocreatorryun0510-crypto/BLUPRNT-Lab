"""Provider-common Data Egress and payload safety validation."""

import json
import re
from dataclasses import dataclass

from provider_payload_resolver.fingerprint import presentation_payload_fingerprint
from provider_payload_resolver.models import (
    PayloadValidationIssue,
    PayloadValidationStage,
    PresentationPayload,
)

_SECRET_PATTERNS = (
    re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]"),
    re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]{8,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\.env(?:\b|[\\/])"),
)
_LOCAL_PATH_PATTERNS = (
    re.compile(r"/(?:Users|home|private|var|tmp)/[^\s\"']+"),
    re.compile(r"[A-Za-z]:\\(?:Users|Documents|Desktop)\\[^\s\"']+"),
)
_PERSONAL_DATA_PATTERNS = (
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"(?<!\d)\d{3}-\d{4}-\d{4}(?!\d)"),
)
_AUTH_URL_PATTERN = re.compile(
    r"(?i)https?://[^\s\"']+(?:[?&](?:token|key|signature|auth)=|@)"
)
_DATABASE_FILE_PATTERN = re.compile(r"(?i)\b[a-z0-9_.-]+\.(?:sqlite3?|db)\b")


@dataclass(frozen=True)
class DataEgressScan:
    egress_policy_result: bool
    secret_scan_result: bool
    local_path_scan_result: bool
    personal_data_scan_result: bool
    fingerprint_result: bool
    issues: tuple[PayloadValidationIssue, ...]


class DataEgressPolicyValidator:
    """Deny unsafe data before every Provider-specific adapter."""

    policy_id = "bluprnt.data_egress_policy"
    policy_version = "1.0.0"

    def validate(self, payload: PresentationPayload) -> DataEgressScan:
        serialized = json.dumps(payload.model_dump(mode="json"), ensure_ascii=False)
        issues: list[PayloadValidationIssue] = []
        secret_ok = not any(pattern.search(serialized) for pattern in _SECRET_PATTERNS)
        if not secret_ok:
            issues.append(_issue("secret_detected", "payload", "Secret候補を検出しました。"))
        local_path_ok = not any(
            pattern.search(serialized) for pattern in _LOCAL_PATH_PATTERNS
        )
        if not local_path_ok:
            issues.append(
                _issue(
                    "local_absolute_path_detected",
                    "payload",
                    "ローカル絶対パスを検出しました。",
                )
            )
        personal_data_ok = not any(
            pattern.search(serialized) for pattern in _PERSONAL_DATA_PATTERNS
        )
        if not personal_data_ok:
            issues.append(
                _issue(
                    "personal_data_detected",
                    "payload",
                    "個人情報候補を検出しました。",
                )
            )
        if _AUTH_URL_PATTERN.search(serialized):
            secret_ok = False
            issues.append(
                _issue(
                    "authenticated_url_detected",
                    "medical_content.references",
                    "認証情報付きURL候補を検出しました。",
                )
            )
        if _DATABASE_FILE_PATTERN.search(serialized):
            local_path_ok = False
            issues.append(
                _issue(
                    "database_file_reference_detected",
                    "payload",
                    "Databaseファイル参照候補を検出しました。",
                )
            )
        required_policy_ok = (
            payload.policies.allow_medical_rephrasing is False
            and payload.policies.allow_medical_fact_addition is False
            and payload.policies.require_claim_traceability is True
            and payload.policies.require_reference_traceability is True
            and payload.policies.prohibit_unapproved_medical_additions is True
        )
        if not required_policy_ok:
            issues.append(
                _issue(
                    "required_policy_disabled",
                    "policies",
                    "Provider共通の医学安全Policyが無効です。",
                )
            )
        expected_fingerprint = presentation_payload_fingerprint(payload)
        fingerprint_ok = payload.metadata.payload_fingerprint == expected_fingerprint
        if not fingerprint_ok:
            issues.append(
                _issue(
                    "payload_fingerprint_mismatch",
                    "metadata.payload_fingerprint",
                    "Payload Fingerprintが内容と一致しません。",
                    stage=PayloadValidationStage.FINGERPRINT,
                )
            )
        egress_ok = (
            required_policy_ok
            and secret_ok
            and local_path_ok
            and personal_data_ok
            and fingerprint_ok
        )
        return DataEgressScan(
            egress_policy_result=egress_ok,
            secret_scan_result=secret_ok,
            local_path_scan_result=local_path_ok,
            personal_data_scan_result=personal_data_ok,
            fingerprint_result=fingerprint_ok,
            issues=tuple(issues),
        )


def _issue(
    code: str,
    path: str,
    message: str,
    *,
    stage: PayloadValidationStage = PayloadValidationStage.POLICY,
) -> PayloadValidationIssue:
    return PayloadValidationIssue(stage=stage, code=code, path=path, message=message)
