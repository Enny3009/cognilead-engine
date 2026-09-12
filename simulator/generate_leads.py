import asyncio
import httpx
import hmac
import hashlib
import json

API_URL = "http://localhost:8000/api/v1"
WEBHOOK_SLUG = "src_6390baec60dfabca"  # Keep your generated slug
WEBHOOK_SECRET = "SPT4lISiek5Dh1qmKF7IYe54m8NIjLdQoqxZN1NKxJk"  # Keep your generated secret

SAMPLE_LEAD = {
    "first_name": "Alexander",
    "last_name": "Vance",
    "email": "alexander.vance@acme-enterprise.io",
    "phone": "+14155552671",
    "company_name": "Acme Enterprise Corp",
    "job_title": "VP of Global Procurement",
    "company_size": "1000+",
    "message": "We need an enterprise-grade AI workflow rollout."
}

async def simulate_traffic() -> None:
    # Serialize exactly once to guarantee bit-exact matches
    raw_body = json.dumps(SAMPLE_LEAD).encode("utf-8")
    
    computed_hmac = hmac.new(
        WEBHOOK_SECRET.encode("utf-8"), 
        msg=raw_body, 
        digestmod=hashlib.sha256
    ).hexdigest()
    
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": f"sha256={computed_hmac}",
        "Idempotency-Key": f"sim_{SAMPLE_LEAD['email']}"
    }
    
    async with httpx.AsyncClient(base_url=API_URL, timeout=10.0) as client:
        print("Transmitting encrypted webhook payload...")
        # Transmit raw bytes using content= instead of json=
        res = await client.post(f"/webhooks/{WEBHOOK_SLUG}", content=raw_body, headers=headers)
        print(f"Status: {res.status_code} | Response: {res.text}")

if __name__ == "__main__":
    asyncio.run(simulate_traffic())