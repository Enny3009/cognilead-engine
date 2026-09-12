# tests/integration/test_webhook_ingestion.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_health_probes(client: AsyncClient) -> None:
    res = await client.get("/health/live")
    assert res.status_code == 200
    assert res.json() == {"status": "alive"}