import redis.asyncio as aioredis

TOKEN_BUCKET_LUA_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local current = tonumber(redis.call('get', key) or "0")

if current + 1 > limit then
    return 0
else
    redis.call('incrby', key, 1)
    if current == 0 then
        redis.call('expire', key, 60)
    end
    return 1
end
"""


class TokenBucketRateLimiter:
    """
    Guarantees outbound HTTP calls adhere to downstream API quotas
    (e.g., Salesforce 100 req/min) using an atomic Redis Lua script.
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client
        self._script = self.redis.register_script(TOKEN_BUCKET_LUA_SCRIPT)

    async def acquire_token(self, endpoint_id: str, limit_per_minute: int = 100) -> bool:
        key = f"rl:endpoint:{endpoint_id}:tokens"
        result = await self._script(keys=[key], args=[limit_per_minute])
        return bool(result == 1)