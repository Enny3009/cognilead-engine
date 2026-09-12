from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue
from app.core.config import settings

celery_app = Celery(
    "cognilead_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.lead_tasks",
        "app.workers.ai_tasks",
        "app.workers.workflow_tasks",
        "app.workers.dispatch_tasks",
        "app.workers.scheduled_tasks",
    ],
)

default_exchange = Exchange("cognilead", type="direct")
dlx_exchange = Exchange("cognilead.dlx", type="direct")

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_queues=(
        Queue("q.leads.ingest", default_exchange, routing_key="leads.ingest"),
        Queue("q.leads.score", default_exchange, routing_key="leads.score"),
        Queue("q.leads.ai", default_exchange, routing_key="leads.ai"),
        Queue("q.workflows.engine", default_exchange, routing_key="workflows.engine"),
        Queue("q.integrations.dispatch", default_exchange, routing_key="integrations.dispatch"),
        Queue("q.leads.dlx", dlx_exchange, routing_key="leads.dlx"),
    ),
    task_routes={
        "app.workers.lead_tasks.*": {"queue": "q.leads.ingest"},
        "app.workers.ai_tasks.*": {"queue": "q.leads.ai"},
        "app.workers.workflow_tasks.*": {"queue": "q.workflows.engine"},
        "app.workers.dispatch_tasks.*": {"queue": "q.integrations.dispatch"},
        "app.workers.scheduled_tasks.*": {"queue": "q.workflows.engine"},
    },
    beat_schedule={
        # Every 5 minutes: inspect circuit breakers in OPEN state
        "evaluate-circuit-breakers-every-5m": {
            "task": "app.workers.scheduled_tasks.evaluate_circuit_breakers_task",
            "schedule": 300.0,
        },
        # Every 1 hour: aggregate attribution rollups across campaigns
        "refresh-attribution-rollups-hourly": {
            "task": "app.workers.scheduled_tasks.refresh_attribution_rollups_task",
            "schedule": 3600.0,
        },
        # Daily at 00:00 UTC: sweep stale uncontacted leads past SLA
        "flag-stale-leads-daily": {
            "task": "app.workers.scheduled_tasks.flag_stale_leads_task",
            "schedule": crontab(hour=0, minute=0),
        },
    },
)