from dataclasses import dataclass
from datetime import datetime, timezone
import uuid
import httpx
import structlog

logger = structlog.get_logger()


@dataclass
class CRMDispatchResult:
    success: bool
    status_code: int
    external_id: str | None = None
    response_body: str = ""
    error_message: str | None = None


class MockCRMClient:
    """
    High-throughput asynchronous connection-pooled client.
    Can deliver to external webhooks or execute simulated CRM transactions.
    """

    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout

    async def sync_lead(
        self,
        endpoint_url: str,
        lead_payload: dict,
        simulate_failure: bool = False,
    ) -> CRMDispatchResult:
        if simulate_failure:
            return CRMDispatchResult(
                success=False,
                status_code=500,
                response_body='{"error": "Downstream CRM Service Unavailable (Simulated)"}',
                error_message="HTTP 500 Internal Server Error",
            )

        # If endpoint_url starts with http, perform real outbound dispatch via HTTPX
        if endpoint_url.startswith("http://") or endpoint_url.startswith("https://"):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    res = await client.post(endpoint_url, json=lead_payload)
                    return CRMDispatchResult(
                        success=res.is_success,
                        status_code=res.status_code,
                        external_id=f"crm_rec_{uuid.uuid4().hex[:12]}",
                        response_body=res.text[:1000],
                    )
            except Exception as e:
                return CRMDispatchResult(
                    success=False,
                    status_code=504,
                    error_message=str(e),
                )

        # Standard simulated CRM response
        simulated_id = f"ext_lead_{uuid.uuid4().hex[:10]}"
        return CRMDispatchResult(
            success=True,
            status_code=201,
            external_id=simulated_id,
            response_body=f'{{"status": "SUCCESS", "crm_id": "{simulated_id}"}}',
        )