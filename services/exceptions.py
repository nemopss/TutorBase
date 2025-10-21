"""Custom exceptions for service layer.

This module defines custom exception classes used throughout the service layer
to handle business logic errors, validation failures, and resource not found cases.
All service exceptions inherit from ServiceError base class for consistent error handling.

Exception hierarchy:
    ServiceError (base)
    ├── NotFoundError: Entity lookup failures
    └── ValidationError: Input validation failures

Typical usage example:

    from services.exceptions import NotFoundError, ValidationError

    if not entity:
        raise NotFoundError(f"Lesson with ID {lesson_id} not found")

    if value < 0:
        raise ValidationError("Value must be positive")
"""


class ServiceError(Exception):
    """Base class for all service-level errors.

    Serves as the parent exception for all custom service layer exceptions.
    Allows catching all service-related errors with a single except clause.
    Should not be raised directly - use specific subclasses instead.

    Used when:
        - Never raised directly
        - Used in except clauses to catch all service errors
        - Extended by specific error types (NotFoundError, ValidationError)

    Example:
        try:
            result = await some_service_method()
        except ServiceError as e:
            # Handle any service-level error
            logger.error(f"Service error: {e}")
    """


class NotFoundError(ServiceError):
    """Raised when a requested entity was not found.

    Indicates that a database query for a specific entity (by ID or other criteria)
    returned no results. Typically converted to HTTP 404 responses in API layer.

    Used when:
        - Entity lookup by ID returns None
        - Required related entity doesn't exist
        - Resource not accessible due to tenant filtering

    Example:
        lesson = await get_lesson(session, tenant, lesson_id)
        if not lesson:
            raise NotFoundError(f"Lesson {lesson_id} not found")
    """


class ValidationError(ServiceError):
    """Raised when provided input data is invalid.

    Indicates that input data failed business logic validation rules.
    Different from Pydantic validation errors - this is for business rules
    that can't be expressed in schema validators. Typically converted to
    HTTP 400 responses in API layer.

    Used when:
        - Business rule validation fails (e.g., date in past)
        - Data constraints violated (e.g., duplicate entries)
        - Invalid state transitions (e.g., can't cancel completed lesson)
        - Cross-field validation fails

    Example:
        if start_date < date.today():
            raise ValidationError("Start date cannot be in the past")

        if package.status == "completed":
            raise ValidationError("Cannot modify completed package")
    """

