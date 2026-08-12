"""Health and deployment probe endpoints."""
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_session

from redis.asyncio import Redis
from config import config

router = APIRouter()
redis_client = Redis.from_url(
    config.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
)


@router.get("/health")
async def health_check(response: Response, session: AsyncSession = Depends(get_session)):
    """
    Health check endpoint.
    Returns 200 if all systems are operational.
    """
    health_status = {
        "status": "healthy",
        "services": {}
    }
    
    # Check database
    try:
        await session.execute(text("SELECT 1"))
        health_status["services"]["database"] = "connected"
    except Exception:
        health_status["status"] = "unhealthy"
        health_status["services"]["database"] = "error"
    
    # Check Redis (if available)
    try:
        await redis_client.ping()
        health_status["services"]["redis"] = "connected"
    except Exception:
        health_status["status"] = "unhealthy"
        health_status["services"]["redis"] = "error"

    if health_status["status"] != "healthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    return health_status


@router.head("/health", include_in_schema=False)
async def health_check_head(
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """HEAD variant used by lightweight load-balancer probes."""
    return await health_check(response=response, session=session)


@router.get("/ready")
async def readiness_check(response: Response, session: AsyncSession = Depends(get_session)):
    """
    Readiness check for Kubernetes/Docker healthcheck.
    """
    services: dict[str, str] = {}
    try:
        await session.execute(text("SELECT 1"))
        services["database"] = "connected"
    except Exception:
        services["database"] = "error"

    try:
        await redis_client.ping()
        services["redis"] = "connected"
    except Exception:
        services["redis"] = "error"

    ready = all(value == "connected" for value in services.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if ready else "not_ready", "services": services}


@router.get("/live")
async def liveness_check():
    """
    Liveness check for Kubernetes/Docker healthcheck.
    """
    return {"status": "alive"}
