"""Health check endpoint."""
from fastapi import APIRouter, Depends
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


@router.api_route("/health", methods=["GET", "HEAD"])
async def health_check(session: AsyncSession = Depends(get_session)):
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
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["services"]["database"] = f"error: {str(e)}"
    
    # Check Redis (if available)
    try:
        await redis_client.ping()
        health_status["services"]["redis"] = "connected"
    except Exception:
        # Redis is optional
        health_status["services"]["redis"] = "not configured"
    
    return health_status


@router.get("/ready")
async def readiness_check():
    """
    Readiness check for Kubernetes/Docker healthcheck.
    """
    return {"status": "ready"}


@router.get("/live")
async def liveness_check():
    """
    Liveness check for Kubernetes/Docker healthcheck.
    """
    return {"status": "alive"}
