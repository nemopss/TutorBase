"""Centralized error handling for FastAPI application.

This module provides exception handlers for consistent error responses across
all API endpoints. All errors are returned in a standardized JSON format with
appropriate HTTP status codes.

Error response format:
    {
        "error": "error_type",
        "message": "Human-readable error description",
        "details": [...] (optional, for validation errors)
    }

Exception handlers:
    - validation_exception_handler: Pydantic validation errors (422)
    - not_found_exception_handler: Resource not found errors (404)
    - service_validation_exception_handler: Business validation errors (400)
    - service_error_exception_handler: General service errors (400)
    - generic_exception_handler: Unexpected errors (500)

Usage:
    Register handlers in FastAPI app:
    
    from api.errors import register_exception_handlers
    
    app = FastAPI()
    register_exception_handlers(app)
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from services.exceptions import NotFoundError, ValidationError as ServiceValidationError, ServiceError


async def validation_exception_handler(
    request: Request,
    exc: PydanticValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors.
    
    Triggered when request data fails Pydantic schema validation.
    Returns 422 Unprocessable Entity with detailed field-level errors.
    
    Args:
        request: FastAPI request object
        exc: Pydantic validation exception
        
    Returns:
        JSONResponse with error details and 422 status code
        
    Response format:
        {
            "error": "validation_error",
            "message": "Invalid input data",
            "details": [
                {
                    "loc": ["body", "field_name"],
                    "msg": "field required",
                    "type": "value_error.missing"
                }
            ]
        }
    """
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "validation_error",
            "message": "Invalid input data",
            "details": exc.errors()
        }
    )


async def not_found_exception_handler(
    request: Request,
    exc: NotFoundError
) -> JSONResponse:
    """Handle resource not found errors.
    
    Triggered when a requested entity doesn't exist in the database.
    Returns 404 Not Found with error message.
    
    Args:
        request: FastAPI request object
        exc: NotFoundError exception from service layer
        
    Returns:
        JSONResponse with error message and 404 status code
        
    Response format:
        {
            "error": "not_found",
            "message": "Lesson with ID 123 not found"
        }
    """
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": "not_found",
            "message": str(exc)
        }
    )


async def service_validation_exception_handler(
    request: Request,
    exc: ServiceValidationError
) -> JSONResponse:
    """Handle business validation errors.
    
    Triggered when data fails business logic validation rules.
    Returns 400 Bad Request with error message.
    
    Args:
        request: FastAPI request object
        exc: ValidationError exception from service layer
        
    Returns:
        JSONResponse with error message and 400 status code
        
    Response format:
        {
            "error": "validation_error",
            "message": "Start date cannot be in the past"
        }
    """
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "validation_error",
            "message": str(exc)
        }
    )


async def service_error_exception_handler(
    request: Request,
    exc: ServiceError
) -> JSONResponse:
    """Handle general service layer errors.
    
    Triggered when a service operation fails for business logic reasons.
    Returns 400 Bad Request with error message.
    
    Args:
        request: FastAPI request object
        exc: ServiceError exception from service layer
        
    Returns:
        JSONResponse with error message and 400 status code
        
    Response format:
        {
            "error": "service_error",
            "message": "Operation failed due to business constraint"
        }
    """
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "service_error",
            "message": str(exc)
        }
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """Handle unexpected errors.
    
    Catches all unhandled exceptions to prevent exposing internal details.
    Returns 500 Internal Server Error with generic message.
    Logs full exception details for debugging.
    
    Args:
        request: FastAPI request object
        exc: Any unhandled exception
        
    Returns:
        JSONResponse with generic error message and 500 status code
        
    Response format:
        {
            "error": "internal_server_error",
            "message": "An unexpected error occurred"
        }
    """
    # TODO: Add structured logging here when implemented
    # logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred"
        }
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers with FastAPI app.
    
    This function should be called during app initialization to register
    all custom exception handlers. Handlers are registered in order of
    specificity (most specific first).
    
    Args:
        app: FastAPI application instance
        
    Example:
        >>> app = FastAPI()
        >>> register_exception_handlers(app)
    """
    # Pydantic validation errors (most specific)
    app.add_exception_handler(PydanticValidationError, validation_exception_handler)
    
    # Service layer exceptions (specific)
    app.add_exception_handler(NotFoundError, not_found_exception_handler)
    app.add_exception_handler(ServiceValidationError, service_validation_exception_handler)
    app.add_exception_handler(ServiceError, service_error_exception_handler)
    
    # Generic exception handler (catch-all, least specific)
    app.add_exception_handler(Exception, generic_exception_handler)


__all__ = [
    'validation_exception_handler',
    'not_found_exception_handler',
    'service_validation_exception_handler',
    'service_error_exception_handler',
    'generic_exception_handler',
    'register_exception_handlers',
]
