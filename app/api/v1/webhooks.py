from datetime import datetime, timezone
import json
from typing import Any
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.encryption import encryptor
from app.core.redis import get_redis_client
from app.core.security import verify_webhook_signature
from app.models.campaign import LeadSource
from app.services.idempotency import IdempotencyService
from app.workers.lead_tasks import ingest_raw_lead_task

router = APIRouter(prefix="/webhooks", tags=["Inbound Webhooks"])


@router.post(
    "/{source_slug}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Cryptographically Verified Webhook Ingestion Gateway",
)
async def ingest_webhook(
    source_slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    x_tiktok_signature: str | None = Header(default=None, alias="X-TikTok-Signature"),
    x_signature_sha256: str | None = Header(default=None, alias="X-Signature-SHA256"),
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
) -> dict[str, Any]:
    # 1. Resolve Lead Source
    stmt = select(LeadSource).where(LeadSource.webhook_slug == source_slug)
    result = await db.execute(stmt)
    source = result.scalar_one_or_none()

    if not source or not source.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook endpoint does not exist or has been disabled",
        )

    # 2. Read raw binary body (required for bit-exact HMAC calculation)
    raw_body = await request.body()
    if not raw_body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty payload")

    # 3. Decrypt stored secret key
    stored_secret = encryptor.decrypt(bytes.fromhex(source.webhook_secret_hash))

    # 4. Cryptographic Signature Verification
    is_valid = False
    if source.source_type == "META_ADS":
        if not x_hub_signature_256:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-Hub-Signature-256 header",
            )
        is_valid = verify_webhook_signature(
            raw_payload=raw_body,
            secret=stored_secret,
            signature_header=x_hub_signature_256,
            signature_prefix="sha256=",
        )
    elif source.source_type == "TIKTOK_ADS":
        if not x_tiktok_signature:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-TikTok-Signature header",
            )
        is_valid = verify_webhook_signature(
            raw_payload=raw_body,
            secret=stored_secret,
            signature_header=x_tiktok_signature,
            signature_prefix="",
        )
    else:
        # WEBSITE_FORM, LANDING_PAGE, API
        if x_signature_sha256:
            is_valid = verify_webhook_signature(
                raw_payload=raw_body,
                secret=stored_secret,
                signature_header=x_signature_sha256,
                signature_prefix="sha256=",
            )
        elif x_webhook_secret:
            # Constant-time token match
            import hmac
            is_valid = hmac.compare_digest(x_webhook_secret, stored_secret)

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cryptographic signature verification failed: invalid signature",
        )

    # 5. Idempotency Check via Redis
    idempotency_service = IdempotencyService(redis_client)
    fingerprint = idempotency_service.compute_fingerprint(source_slug, raw_body)
    is_duplicate = await idempotency_service.acquire_lock_or_is_duplicate(fingerprint)

    if is_duplicate:
        # Return 200 OK immediately to satisfy upstream retry mechanisms without re-processing
        return {
            "status": "DUPLICATE_IGNORED",
            "fingerprint": fingerprint,
            "message": "Payload already ingested and verified within the idempotency window",
        }

    # 6. Parse JSON Payload
    try:
        json_payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        json_payload = {"raw_content": raw_body.decode("utf-8", errors="replace")}

    # 7. Asynchronously Enqueue to Celery (q.leads.ingest)
    task = ingest_raw_lead_task.apply_async(
        kwargs={
            "organization_id": str(source.organization_id),
            "source_id": str(source.id),
            "raw_payload": json_payload,
            "headers": dict(request.headers),
            "received_at": datetime.now(timezone.utc).isoformat(),
        },
        queue="q.leads.ingest",
    )

    return {
        "status": "QUEUED",
        "task_id": task.id,
        "fingerprint": fingerprint,
    }