# simulator/generate_leads.py
import asyncio
import httpx

API_URL = "http://localhost:8000/api/v1"

SAMPLE_LEADS = [
    {
        "source": "website",
        "first_name": "Alexander",
        "last_name": "Vance",
        "email": "alexander.vance@acme-enterprise.io",
        "phone": "+14155552671",
        "company_name": "Acme Enterprise Corp",
        "job_title": "VP of Global Procurement",
        "country": "US",
        "city": "San Francisco",
        "industry": "Software",
        "company_size": "1000+",
        "message": "We need an enterprise-grade AI workflow rollout and want to schedule a demo immediately."
    },
    {
        "source": "facebook",
        "first_name": "Sarah",
        "last_name": "Jenkins",
        "email": "sarah.j@gmail.com",
        "phone": "+442079460912",
        "company_name": "Freelance",
        "job_title": "Consultant",
        "country": "GB",
        "city": "London",
        "industry": "Marketing",
        "company_size": "1-10",
        "message": "Just looking for general pricing information."
    }
]

async def simulate_traffic() -> None:
    async with httpx.AsyncClient(base_url=API_URL, timeout=10.0) as client:
        print("Simulating inbound lead traffic...")
        for lead in SAMPLE_LEADS:
            res = await client.post("/leads/ingest", json=lead, headers={"Idempotency-Key": f"sim_{lead['email']}"})
            print(f"Status: {res.status_code} | Response: {res.json()}")

if __name__ == "__main__":
    asyncio.run(simulate_traffic())