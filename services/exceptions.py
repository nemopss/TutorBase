"""Custom exceptions for service layer."""


class ServiceError(Exception):
    """Base class for all service-level errors."""


class NotFoundError(ServiceError):
    """Raised when an entity was not found."""


class ValidationError(ServiceError):
    """Raised when provided input data is invalid."""

