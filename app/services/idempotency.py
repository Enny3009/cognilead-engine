import hashlib
import redis.asyncio as aioredis


class IdempotencyService:
    """
    Prevents duplicate webhook ingestion by hashing (source_slug + raw_payload)
    into Redis with a 24-hour expiration window.
    """

    def __init__(self, redis_client: aioredis.Redis, ttl_seconds: int = 86400) -> None:
        self.redis = redis_client
        self.ttl = ttl_seconds

    def compute_fingerprint(self, source_slug: str, raw_payload: bytes) -> str:
        hasher = hashlib.sha256()
        hasher.update(source_slug.encode("utf-8"))
        hasher.update(raw_payload)
        return hasher.hexdigest()

    async def acquire_lock_or_is_duplicate(self, fingerprint: str) -> bool:
        """
        Returns True if the payload is a DUPLICATE (key already existed).
        Returns False if newly acquired and locked.
        Uses SET key 1 NX EX ttl.
        """
        key = f"idemp:webhook:{fingerprint}"
        acquired = await self.redis.set(key, b"1", ex=self.ttl, nx=True)
        return not bool(acquired)