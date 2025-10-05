from fastapi import FastAPI

from api.routes import auth, packages, lessons, templates, reminders, metrics

APP_TITLE = "KSU Applications Bot API"
APP_VERSION = "0.1.0"
API_PREFIX = "/api/v1"

def create_app() -> FastAPI:
    app = FastAPI(title=APP_TITLE, version=APP_VERSION)

    app.include_router(auth.router, prefix=f"{API_PREFIX}/auth", tags=["auth"])
    app.include_router(packages.router, prefix=f"{API_PREFIX}/packages", tags=["packages"])
    app.include_router(lessons.router, prefix=f"{API_PREFIX}/lessons", tags=["lessons"])
    app.include_router(templates.router, prefix=f"{API_PREFIX}/templates", tags=["templates"])
    app.include_router(reminders.router, prefix=f"{API_PREFIX}/reminders", tags=["reminders"])
    app.include_router(metrics.router, prefix=f"{API_PREFIX}/metrics", tags=["metrics"])

    return app
