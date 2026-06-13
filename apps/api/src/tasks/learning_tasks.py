"""
TradeFlow AI — Learning & Maintenance Tasks
"""

import structlog

from ..config import settings
from ..services.predictor_svc import FEATURE_NAMES, rejection_predictor
from .celery_app import celery_app

log = structlog.get_logger()


def _run_async(coro):
    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task(bind=True, queue="low")
def retrain_predictor(self):
    """Retrain XGBoost from labeled CEISA outcomes and promote only if quality holds."""
    async def _retrain():
        import asyncpg
        import numpy as np

        conn = await asyncpg.connect(settings.DATABASE_URL)
        try:
            rows = await conn.fetch(
                """
                SELECT id, outcome, feature_snapshot, predicted_rejection_prob
                FROM submission_outcomes
                WHERE feature_snapshot IS NOT NULL
                ORDER BY created_at ASC
                """
            )
            if len(rows) < settings.RETRAIN_MIN_TOTAL_SAMPLES:
                return {"trained": False, "reason": "not_enough_total_samples", "samples": len(rows)}

            X = np.array(
                [[float((row["feature_snapshot"] or {}).get(feature, 0.0)) for feature in FEATURE_NAMES] for row in rows],
                dtype=np.float32,
            )
            y = np.array([1 if row["outcome"] == "rejected" else 0 for row in rows], dtype=np.int32)
            version = str(int(__import__("time").time()))
            result = rejection_predictor.train_and_upload(X, y, version)
            if result.get("promoted"):
                await conn.execute(
                    "UPDATE submission_outcomes SET used_in_training = TRUE WHERE feature_snapshot IS NOT NULL"
                )
            return {"trained": bool(result.get("promoted")), **result, "samples": len(rows)}
        finally:
            await conn.close()

    log.info("Retraining rejection predictor")
    return _run_async(_retrain())

@celery_app.task(bind=True, queue="low")
def refresh_btki_embeddings(self):
    log.info("Task stub: refresh_btki_embeddings")

@celery_app.task(bind=True, queue="low")
def check_retrain_trigger(self):
    """Schedule retraining and flag extraction drift from recent corrections."""
    async def _check():
        import asyncpg

        conn = await asyncpg.connect(settings.DATABASE_URL)
        try:
            new_samples = await conn.fetchval(
                "SELECT COUNT(*) FROM submission_outcomes WHERE used_in_training = FALSE"
            )
            drift_rows = await conn.fetch(
                """
                SELECT field_name, COUNT(*) AS correction_count
                FROM learning_samples
                WHERE created_at >= NOW() - ($1::int * INTERVAL '1 day')
                GROUP BY field_name
                HAVING COUNT(*) >= $2
                ORDER BY correction_count DESC
                """,
                settings.DRIFT_LOOKBACK_DAYS,
                settings.DRIFT_CORRECTION_THRESHOLD,
            )
            drift_alerts = [
                {"field_name": row["field_name"], "correction_count": row["correction_count"]}
                for row in drift_rows
            ]

            should_retrain = (
                settings.ENABLE_ADAPTIVE_LEARNING
                and int(new_samples or 0) >= settings.RETRAIN_MIN_NEW_SAMPLES
            )
            if should_retrain:
                retrain_predictor.apply_async(queue="low")

            if drift_alerts:
                log.warning("Field-level extraction drift detected", drift_alerts=drift_alerts)

            return {
                "new_samples": int(new_samples or 0),
                "scheduled_retrain": should_retrain,
                "drift_alerts": drift_alerts,
            }
        finally:
            await conn.close()

    log.info("Checking adaptive learning retrain trigger")
    return _run_async(_check())
