from collections.abc import AsyncGenerator
import redis.asyncio as aioredis
from app.core.config import settings

# Global connection pool for Redis 7.2+
redis_pool = aioredis.ConnectionPool.from_url(
    str(settings.REDIS_URI),
    max_connections=50,
    decode_responses=False,  # Keep binary mode for raw token bucket Lua scripts
)


async def get_redis_client() -> AsyncGenerator[aioredis.Redis, None]:
    """Dependency that yields a managed async Redis connection from the pool."""
    client = aioredis.Redis(connection_pool=redis_pool)
    try:
        yield client
    finally:
        await client.aclose()


async def ping_redis() -> bool:
    """Verifies Redis connectivity during readiness probes."""
    client = aioredis.Redis(connection_pool=redis_pool)
    try:
        return bool(await client.ping())
    except Exception:
        return False
    finally:
        await client.aclose()