"""Base domain exceptions.

Requirements: 5.1
"""


class DomainException(Exception):
    """Base exception for all domain-level errors."""

    def __init__(self, message: str = "Domain error occurred"):
        self.message = message
        super().__init__(self.message)


class EntityNotFoundError(DomainException):
    """Raised when an entity is not found."""

    def __init__(self, entity_type: str, entity_id: str | int):
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"{entity_type} with id '{entity_id}' not found")


class ValidationError(DomainException):
    """Raised when validation fails."""

    def __init__(self, message: str, field: str | None = None):
        self.field = field
        prefix = f"Field '{field}': " if field else ""
        super().__init__(f"{prefix}{message}")
