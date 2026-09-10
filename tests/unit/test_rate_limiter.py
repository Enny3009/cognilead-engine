import pytest
import redis.asyncio as aioredis
from app.core.config import settings
from app.services.rate_limiter import TokenBucketRateLimiter


@pytest.mark.asyncio
async def test_token_bucket_limit() -> None:
    redis_client = aioredis.from_url(str(settings.REDIS_URI), decode_responses=False)
    try:
        limiter = TokenBucketRateLimiter(redis_client)
        ep_id = "test-rate-limit-endpoint"
        await redis_client.delete(f"rl:endpoint:{ep_id}:tokens")

        # Cap limit at 3 requests
        assert await limiter.acquire_token(ep_id, limit_per_minute=3) is True
        assert await limiter.acquire_token(ep_id, limit_per_minute=3) is True
        assert await limiter.acquire_token(ep_id, limit_per_minute=3) is True
        # 4th request must be blocked
        assert await limiter.acquire_token(ep_id, limit_per_minute=3) is False
    finally:
        await redis_client.aclose()