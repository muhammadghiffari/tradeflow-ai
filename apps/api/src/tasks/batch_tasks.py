"""
TradeFlow AI — Batch Processing Tasks (T-072)
"""
from __future__ import annotations

import contextlib
import logging

logger = logging.getLogger("tasks.batch")


def process_batch(batch_id: str) -> dict:
    """
    Main Celery task: invoke the LangGraph pipeline for a batch.
    Called by POST /api/v1/batches after file upload.
    """
    try:
        import asyncio

        from packages.agents.src.graph import get_graph  # type: ignore

        from ..config import settings  # type: ignore

        graph = get_graph()
        config = {"configurable": {"thread_id": batch_id}}

        # Fetch batch documents from DB
        state = _load_initial_state(batch_id, settings)

        # Run the graph synchronously from Celery worker
        result = asyncio.run(graph.ainvoke(state, config=config))
        logger.info(f"Batch {batch_id} pipeline complete. Status: {result.get('ceisa_response', {}).get('status')}")
        return {"batch_id": batch_id, "status": "complete"}
    except Exception as e:
        logger.error(f"Batch {batch_id} pipeline failed: {e}")
        _mark_batch_failed(batch_id, str(e))
        raise


def cleanup_expired_batches() -> int:
    """Delete batches older than 7 days (Celery beat hourly)."""
    import asyncio
    try:
        return asyncio.run(_cleanup_async())
    except Exception as e:
        logger.error(f"Batch cleanup failed: {e}")
        return 0


async def _cleanup_async() -> int:
    from ..db.database import get_async_session  # type: ignore
    async with get_async_session() as db:
        result = await db.execute(
            "DELETE FROM batches WHERE created_at < NOW() - INTERVAL '7 days' "
            "AND status NOT IN ('ACCEPTED', 'REJECTED') RETURNING id"
        )
        deleted = result.rowcount if hasattr(result, "rowcount") else 0
        logger.info(f"Cleaned up {deleted} expired batches")
        return deleted


def _load_initial_state(batch_id: str, settings) -> dict:
    """Load initial DeclarationState from database."""
    import asyncio

    async def _fetch():
        from ..db.database import get_async_session  # type: ignore
        async with get_async_session() as db:
            rows = await db.execute(
                "SELECT id, doc_type, storage_path, original_name FROM documents WHERE batch_id = $1",
                batch_id,
            )
            docs = [dict(r) for r in rows]
            tier_row = await db.execute(
                "SELECT tier FROM batches WHERE id = $1", batch_id
            )
            tier = "sme"
            if tier_row:
                tier = tier_row[0].get("tier", "sme")
        return {
            "batch_id": batch_id,
            "tier": tier,
            "documents": docs,
            "messages": [],
            "operator_corrections": [],
            "submission_attempt": 0,
            "error": None,
        }

    return asyncio.run(_fetch())


def _mark_batch_failed(batch_id: str, error: str) -> None:
    import asyncio

    async def _update():
        from ..db.database import get_async_session  # type: ignore
        async with get_async_session() as db:
            await db.execute(
                "UPDATE batches SET status = 'FAILED', error_message = $1 WHERE id = $2",
                error[:500], batch_id,
            )

    with contextlib.suppress(Exception):
        asyncio.run(_update())
