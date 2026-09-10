import pytest
import redis.asyncio as aioredis
from app.core.config import settings
from app.services.circuit_breaker import CircuitBreaker


@pytest.mark.asyncio
async def test_circuit_breaker_trip() -> None:
    redis_client = aioredis.from_url(str(settings.REDIS_URI), decode_responses=False)
    try:
        cb = CircuitBreaker(redis_client)
        ep_id = "test-breaker-endpoint"
        await redis_client.delete(f"cb:endpoint:{ep_id}:state")
        await redis_client.delete(f"cb:endpoint:{ep_id}:failures")

        # Initial state
        assert await cb.get_state(ep_id) == "CLOSED"
        assert await cb.allow_request(ep_id) is True

        # Record 4 failures -> remains CLOSED
        for _ in range(4):
            await cb.record_failure(ep_id)
        assert await cb.get_state(ep_id) == "CLOSED"

        # 5th failure -> trips to OPEN
        state = await cb.record_failure(ep_id)
        assert state == "OPEN"
        assert await cb.allow_request(ep_id) is False
    finally:
        await redis_client.aclose()