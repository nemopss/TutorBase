"""Domain interfaces - repository and service protocols."""
from src.domain.interfaces.cache import ICacheService
from src.domain.interfaces.repository import IRepository

__all__ = ["IRepository", "ICacheService"]
