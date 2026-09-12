import pytest
import redis.asyncio as aioredis
from app.core.config import settings
from app.services.circuit_breaker import CircuitBreaker

@pytest.mark.asyncio
async def test_circuit_breaker_state_transitions():
    redis_client = aioredis.from_url(str(settings.REDIS_URI), decode_responses=False)
    cb = CircuitBreaker(redis_client)
    endpoint_id = "test_endpoint_123"
    
    await redis_client.delete(f"cb:endpoint:{endpoint_id}:state")
    await redis_client.delete(f"cb:endpoint:{endpoint_id}:failures")
    
    assert await cb.get_state(endpoint_id) == "CLOSED"
    assert await cb.allow_request(endpoint_id) is True
    
    for _ in range(4):
        await cb.record_failure(endpoint_id)
    assert await cb.get_state(endpoint_id) == "CLOSED"
    
    await cb.record_failure(endpoint_id)
    assert await cb.get_state(endpoint_id) == "OPEN"
    assert await cb.allow_request(endpoint_id) is False
    
    await redis_client.aclose()