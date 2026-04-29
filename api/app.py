"""FastAPI application factory and configuration.

This module creates and configures the FastAPI application with all necessary
middleware, routers, and instrumentation for the tutoring management system.

Key components:
    - create_app: Factory function to create configured FastAPI instance
    - CORS middleware: Configured for cross-origin requests
    - Rate limiting: SlowAPI limiter for request throttling
    - Prometheus metrics: Automatic endpoint instrumentation
    - API routers: All business logic endpoints under /api/v1

Middleware stack:
    1. CORS: Allows configured origins with credentials
    2. Rate limiter: IP-based request throttling
    3. Prometheus: Automatic metrics collection

API structure:
    - /health: Health check endpoints (no auth required)
    - /metrics: Prometheus metrics endpoint
    - /api/v1/auth: Authentication and authorization
    - /api/v1/lessons: Lesson management
    - /api/v1/packages: Package management
    - /api/v1/templates: Template management
    - /api/v1/reminders: Reminder management
    - /api/v1/learners: Learner management
    - /api/v1/users: User management
    - /api/v1/tenants: Tenant management (multi-tenancy)
    - /api/v1/invitations: User invitation system

Configuration:
    - CORS origins from config.CORS_ORIGINS
    - Rate limits configured per endpoint
    - Lifespan events for metrics updates
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import config
from api.routes import (
    auth,
    billing,
    finance,
    groups,
    health,
    invitations,
    learners,
    lessons,
    metrics,
    notifications,
    packages,
    payments,
    platform,
    reminders,
    templates,
    tenant_access,
    tenants,
    users,
)
from api.metrics_updater import lifespan_with_metrics
from api.errors import register_exception_handlers

APP_TITLE = "App API"
APP_VERSION = "0.1.2"
API_PREFIX = "/api/v1"

# Rate limiter instance
limiter = Limiter(key_func=get_remote_address)

def create_app() -> FastAPI:
    """Create and configure FastAPI application instance.

    Factory function that creates FastAPI app with all middleware, routers,
    and instrumentation configured. This pattern allows for easy testing
    and multiple app instances if needed.

    Configuration steps:
        1. Create FastAPI instance with title, version, and lifespan
        2. Configure rate limiter and exception handlers
        3. Add CORS middleware for cross-origin requests
        4. Instrument with Prometheus for metrics collection
        5. Register health check router (no auth)
        6. Register all API routers under /api/v1 prefix

    Returns:
        Configured FastAPI application instance ready to serve

    Example:
        >>> app = create_app()
        >>> # Run with uvicorn
        >>> import uvicorn
        >>> uvicorn.run(app, host="0.0.0.0", port=8000)
    """
    app = FastAPI(
        title=APP_TITLE, 
        version=APP_VERSION,
        lifespan=lifespan_with_metrics
    )

    # Configure rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Register centralized exception handlers
    register_exception_handlers(app)

    # Add CORS middleware for local development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,  # Configurable via environment variable
        allow_credentials=True,
        allow_methods=["*"],  # Allows all methods
        allow_headers=["*"],  # Allows all headers
    )

    # Prometheus metrics instrumentation
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    # Health checks (no prefix for standard endpoints)
    app.include_router(health.router, tags=["health"])
    
    # API routes
    app.include_router(auth.router, prefix=f"{API_PREFIX}/auth", tags=["auth"])
    app.include_router(billing.router, prefix=f"{API_PREFIX}/billing", tags=["billing"])
    app.include_router(lessons.router, prefix=f"{API_PREFIX}/lessons", tags=["lessons"])
    app.include_router(packages.router, prefix=f"{API_PREFIX}/packages", tags=["packages"])
    app.include_router(templates.router, prefix=f"{API_PREFIX}/templates", tags=["templates"])
    app.include_router(reminders.router, prefix=f"{API_PREFIX}/reminders", tags=["reminders"])
    app.include_router(metrics.router, prefix=f"{API_PREFIX}/metrics", tags=["metrics"])
    app.include_router(learners.router, prefix=f"{API_PREFIX}/learners", tags=["learners"])
    app.include_router(users.router, prefix=f"{API_PREFIX}/users", tags=["users"])
    app.include_router(tenant_access.router, prefix=f"{API_PREFIX}/tenant-access", tags=["tenant-access"])
    app.include_router(tenants.router, prefix=f"{API_PREFIX}/tenants", tags=["tenants"])
    app.include_router(invitations.router, prefix=API_PREFIX, tags=["invitations"])
    app.include_router(payments.router, prefix=f"{API_PREFIX}/payments", tags=["payments"])
    app.include_router(finance.router, prefix=f"{API_PREFIX}/finance", tags=["finance"])
    app.include_router(platform.router, prefix=f"{API_PREFIX}/platform", tags=["platform"])
    app.include_router(groups.router, prefix=f"{API_PREFIX}/groups", tags=["groups"])
    app.include_router(notifications.router, prefix=f"{API_PREFIX}/notifications", tags=["notifications"])

    return app
