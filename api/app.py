from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from config import config
from api.routes import auth, packages, lessons, templates, reminders, metrics, learners, health
from api.metrics_updater import lifespan_with_metrics

APP_TITLE = "KSU Applications Bot API"
APP_VERSION = "0.1.0"
API_PREFIX = "/api/v1"

def create_app() -> FastAPI:
    app = FastAPI(
        title=APP_TITLE, 
        version=APP_VERSION,
        lifespan=lifespan_with_metrics
    )

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

    return app
