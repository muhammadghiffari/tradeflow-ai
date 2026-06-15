"""
TradeFlow AI — Celery Application

PRD §0.2 Invariant #6: Celery queues must be strictly prioritized.
Queue order: critical > high > default > low
Enterprise tier MUST use critical/high queues.
"""

try:
    from celery import Celery
    from kombu import Exchange, Queue
except Exception:  # pragma: no cover - provide lightweight fallbacks for tests
    class _DummyConf:
        def __init__(self):
            self.task_queues = ()
            self.task_default_queue = None
            self.task_default_exchange = None
            self.task_default_routing_key = None
            self.beat_schedule = {}
            self.task_routes = {}

        def update(self, *a, **k):
            return None

    class Celery:  # minimal stand-in
        def __init__(self, *a, **k):
            self.conf = _DummyConf()
        def task(self, *targs, **tkwargs):
            def _decorator(fn):
                return fn
            return _decorator

    class Exchange:
        def __init__(self, *a, **k):
            pass

    class Queue:
        def __init__(self, *a, **k):
            pass

from ..config import settings
from celery.signals import worker_process_init
import asyncio

@worker_process_init.connect
def init_celery_worker(**kwargs):
    from ..dependencies import init_supabase
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_supabase())

# ── Celery app ────────────────────────────────────────────────────────────────
celery_app = Celery(
    "tradeflow",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "src.tasks.ocr_tasks",
        "src.tasks.submit_tasks",
        "src.tasks.learning_tasks",
    ],
)

# ── Configuration ─────────────────────────────────────────────────────────────
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Jakarta",
    enable_utc=True,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    result_expires=86400,  # 24h
    broker_connection_retry_on_startup=True,
)

# ── Priority Queues ───────────────────────────────────────────────────────────
# INVARIANT: Enterprise tier MUST use critical/high queues
default_exchange = Exchange("tradeflow", type="direct")

celery_app.conf.task_queues = (
    Queue("critical", default_exchange, routing_key="critical"),   # blockchain anchoring
    Queue("high",     default_exchange, routing_key="high"),        # OCR + extraction (enterprise)
    Queue("default",  default_exchange, routing_key="default"),     # standard processing
    Queue("low",      default_exchange, routing_key="low"),         # retraining, reporting
)
celery_app.conf.task_default_queue = "default"
celery_app.conf.task_default_exchange = "tradeflow"
celery_app.conf.task_default_routing_key = "default"

# Dead letter queue for exhausted retries
celery_app.conf.task_queues += (
    Queue("dlq", default_exchange, routing_key="dlq"),
)

# ── Task routes ───────────────────────────────────────────────────────────────
celery_app.conf.task_routes = {
    "src.tasks.ocr_tasks.preprocess_document": {"queue": "high"},
    "src.tasks.ocr_tasks.run_ocr": {"queue": "high"},
    "src.tasks.ocr_tasks.extract_fields": {"queue": "high"},
    "src.tasks.ocr_tasks.validate_fields": {"queue": "default"},
    "src.tasks.ocr_tasks.recommend_hs": {"queue": "default"},
    "src.tasks.ocr_tasks.assess_risk": {"queue": "default"},
    "src.tasks.submit_tasks.submit_to_ceisa": {"queue": "high"},
    "src.tasks.submit_tasks.anchor_blockchain": {"queue": "critical"},
    "src.tasks.submit_tasks.process_ceisa_response": {"queue": "high"},
    "src.tasks.learning_tasks.retrain_predictor": {"queue": "low"},
    "src.tasks.learning_tasks.refresh_btki_embeddings": {"queue": "low"},
}

# ── Celery Beat schedule (periodic tasks) ─────────────────────────────────────
celery_app.conf.beat_schedule = {
    "refresh-btki-monthly": {
        "task": "src.tasks.learning_tasks.refresh_btki_embeddings",
        "schedule": 30 * 24 * 60 * 60,  # 30 days in seconds
        "options": {"queue": "low"},
    },
    "check-retrain-trigger-daily": {
        "task": "src.tasks.learning_tasks.check_retrain_trigger",
        "schedule": 24 * 60 * 60,  # daily
        "options": {"queue": "low"},
    },
}
