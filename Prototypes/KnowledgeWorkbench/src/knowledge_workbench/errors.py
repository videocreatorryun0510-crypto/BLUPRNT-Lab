"""Application errors that are safe to show in the prototype UI."""


class WorkbenchError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class InvalidTermError(WorkbenchError):
    def __init__(self, message: str) -> None:
        super().__init__("invalid_term", message)


class ProviderConfigurationError(WorkbenchError):
    def __init__(self, message: str) -> None:
        super().__init__("provider_not_configured", message)


class ProviderGenerationError(WorkbenchError):
    def __init__(self, message: str) -> None:
        super().__init__("ai_generation_failed", message)


class SchemaValidationError(WorkbenchError):
    def __init__(self, message: str) -> None:
        super().__init__("schema_validation_failed", message)


class KnowledgeMappingError(WorkbenchError):
    def __init__(self, message: str) -> None:
        super().__init__("knowledge_mapping_failed", message)


class ExamMetadataUnavailableError(WorkbenchError):
    def __init__(self, message: str) -> None:
        super().__init__("exam_metadata_unavailable", message)


class RegistryOperationError(WorkbenchError):
    def __init__(self, message: str) -> None:
        super().__init__("knowledge_registry_failed", message)
