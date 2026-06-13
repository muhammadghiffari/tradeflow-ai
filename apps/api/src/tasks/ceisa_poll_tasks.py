"""
TradeFlow AI — CEISA Poll Tasks (T-060) + Learning Agent support (T-065, T-066)
"""
from __future__ import annotations

import asyncio
import json
import logging

logger = logging.getLogger("tasks.ceisa_poll")


def poll_active_batches() -> dict:
    """
    Celery Beat (every 30s): poll CEISA for all SUBMITTED batches.
    Resumes LangGraph graph from poll_status node.
    """
    try:
        return asyncio.run(_poll_async())
    except Exception as e:
        logger.error(f"CEISA poll task error: {e}")
        return {"polled": 0, "error": str(e)}


async def _poll_async() -> dict:
    from packages.agents.src.graph import get_graph  # type: ignore

    from ..db.database import get_async_session  # type: ignore

    graph = get_graph()
    polled = 0

    async with get_async_session() as db:
        rows = await db.execute(
            "SELECT id, langgraph_thread_id, ceisa_aju FROM batches "
            "WHERE status = 'SUBMITTED' AND ceisa_aju IS NOT NULL LIMIT 50"
        )
        batches = [dict(r) for r in (rows or [])]

    for batch in batches:
        try:
            config = {"configurable": {"thread_id": batch["langgraph_thread_id"]}}
            await graph.ainvoke(None, config=config)
            polled += 1
        except Exception as e:
            logger.error(f"Poll failed for batch {batch['id']}: {e}")

    return {"polled": polled, "total": len(batches)}


async def record_learning_outcome(
    batch_id: str,
    approved: bool,
    ceisa_status: str,
    corrections: list[dict],
    crs_score: float | None = None,
    rejection_probability: float | None = None,
) -> None:
    """Persist outcome to learning_outcomes for adaptive retraining."""
    from ..db.database import get_async_session  # type: ignore

    async with get_async_session() as db:
        await db.execute(
            """
            INSERT INTO learning_outcomes
              (batch_id, approved, ceisa_status, correction_count,
               corrections_json, crs_score, rejection_probability, created_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,NOW())
            ON CONFLICT (batch_id) DO UPDATE
              SET ceisa_status=EXCLUDED.ceisa_status, approved=EXCLUDED.approved
            """,
            batch_id, approved, ceisa_status,
            len(corrections), json.dumps(corrections),
            crs_score, rejection_probability,
        )


def check_model_drift() -> dict:
    """Celery beat daily: trigger XGBoost retrain if 100+ new samples."""
    try:
        return asyncio.run(_check_drift_async())
    except Exception as e:
        logger.error(f"Drift check failed: {e}")
        return {"triggered_retrain": False}


async def _check_drift_async() -> dict:
    from ..db.database import get_async_session  # type: ignore
    async with get_async_session() as db:
        row = await db.fetchrow(
            "SELECT COUNT(*) AS n FROM learning_outcomes WHERE created_at > NOW() - INTERVAL '24 hours'"
        )
        new_samples = int(row["n"]) if row else 0

    if new_samples >= 100:
        from .celery_app import celery_app  # type: ignore
        celery_app.send_task("src.tasks.ceisa_poll_tasks.retrain_xgboost")
        return {"triggered_retrain": True, "new_samples": new_samples}
    return {"triggered_retrain": False, "new_samples": new_samples}


def retrain_xgboost() -> dict:
    """Retrain XGBoost predictor from labeled outcomes."""
    try:
        return asyncio.run(_retrain_async())
    except Exception as e:
        logger.error(f"XGBoost retrain error: {e}")
        return {"success": False}


async def _retrain_async() -> dict:
    import os

    import numpy as np
    import xgboost as xgb

    from ..config import settings  # type: ignore
    from ..db.database import get_async_session  # type: ignore

    async with get_async_session() as db:
        rows = await db.fetch(
            "SELECT approved, correction_count, crs_score FROM learning_outcomes "
            "WHERE crs_score IS NOT NULL ORDER BY created_at DESC LIMIT 5000"
        )

    data = [dict(r) for r in (rows or [])]
    if len(data) < settings.XGB_MIN_SAMPLES_FOR_MODEL:
        return {"success": False, "reason": "insufficient_samples", "count": len(data)}

    X = np.array([[r["crs_score"], r["correction_count"]] for r in data], dtype=np.float32)
    y = np.array([0 if r["approved"] else 1 for r in data], dtype=np.float32)
    dtrain = xgb.DMatrix(X, label=y)
    model = xgb.train({"objective": "binary:logistic", "eta": 0.1, "max_depth": 4}, dtrain, 100)

    path = getattr(settings, "XGBOOST_MODEL_PATH", "models/rejection_predictor.json")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    model.save_model(path)
    logger.info(f"XGBoost retrained: {len(data)} samples → {path}")
    return {"success": True, "samples": len(data)}
