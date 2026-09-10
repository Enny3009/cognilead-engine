from datetime import datetime, timezone
import structlog
import redis.asyncio as aioredis

logger = structlog.get_logger()


class CircuitBreaker:
    """
    Distributed Circuit Breaker:
    - CLOSED: Normal requests permitted.
    - OPEN: If 5 consecutive failures occur, circuit trips; outbound calls deferred for 5 minutes.
    - HALF_OPEN: Canary request tested. Success -> CLOSED, Failure -> OPEN.
    """

    FAILURE_THRESHOLD = 5
    COOLDOWN_SECONDS = 300  # 5 minutes

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client

    async def get_state(self, endpoint_id: str) -> str:
        state = await self.redis.get(f"cb:endpoint:{endpoint_id}:state")
        if not state:
            return "CLOSED"
        return state.decode("utf-8") if isinstance(state, bytes) else str(state)

    async def record_success(self, endpoint_id: str) -> None:
        state = await self.get_state(endpoint_id)
        if state in ("HALF_OPEN", "OPEN"):
            logger.info("circuit_breaker.reset", endpoint_id=endpoint_id, from_state=state, to_state="CLOSED")
        await self.redis.set(f"cb:endpoint:{endpoint_id}:state", "CLOSED")
        await self.redis.delete(f"cb:endpoint:{endpoint_id}:failures")

    async def record_failure(self, endpoint_id: str) -> str:
        fail_key = f"cb:endpoint:{endpoint_id}:failures"
        failures = await self.redis.incr(fail_key)
        await self.redis.expire(fail_key, self.COOLDOWN_SECONDS * 2)

        if failures >= self.FAILURE_THRESHOLD:
            await self.redis.set(
                f"cb:endpoint:{endpoint_id}:state",
                "OPEN",
                ex=self.COOLDOWN_SECONDS,
            )
            logger.error("circuit_breaker.tripped", endpoint_id=endpoint_id, failures=failures, state="OPEN")
            return "OPEN"
        return "CLOSED"

    async def allow_request(self, endpoint_id: str) -> bool:
        state = await self.get_state(endpoint_id)
        if state == "CLOSED":
            return True
        elif state == "HALF_OPEN":
            return True
        return False  # OPEN: Block request immediately