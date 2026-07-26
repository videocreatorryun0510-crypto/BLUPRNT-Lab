"""JSON Schema helpers for Approval Contract Version 1.0."""

from knowledge_contracts.approval_v10.models import ApprovalContractDescriptor


def approval_contract_json_schema() -> dict[str, object]:
    schema = ApprovalContractDescriptor.model_json_schema(mode="serialization")
    schema["$id"] = "https://bluprnt-lab.local/schema/approval-contract/1.0"
    return schema
