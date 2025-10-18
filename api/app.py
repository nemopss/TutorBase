from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import config
from api.routes import auth, packages, lessons, templates, reminders, metrics, learners, users, health, tenants, invitations
from api.metrics_updater import lifespan_with_metrics

APP_TITLE = "App API"
APP_VERSION = "0.1.1"
API_PREFIX = "/api/v1"

# Rate limiter instance
limiter = Limiter(key_func=get_remote_address)

def create_app() -> FastAPI:
    app = FastAPI(
        title=APP_TITLE, 
        version=APP_VERSION,
        lifespan=lifespan_with_metrics
    )

    # Configure rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
    app.include_router(lessons.router, prefix=f"{API_PREFIX}/lessons", tags=["lessons"])
    app.include_router(packages.router, prefix=f"{API_PREFIX}/packages", tags=["packages"])
    app.include_router(templates.router, prefix=f"{API_PREFIX}/templates", tags=["templates"])
    app.include_router(reminders.router, prefix=f"{API_PREFIX}/reminders", tags=["reminders"])
    app.include_router(metrics.router, prefix=f"{API_PREFIX}/metrics", tags=["metrics"])
    app.include_router(learners.router, prefix=f"{API_PREFIX}/learners", tags=["learners"])
    app.include_router(users.router, prefix=f"{API_PREFIX}/users", tags=["users"])
    app.include_router(tenants.router, prefix=f"{API_PREFIX}/tenants", tags=["tenants"])
    app.include_router(invitations.router, prefix=API_PREFIX, tags=["invitations"])

    return app
