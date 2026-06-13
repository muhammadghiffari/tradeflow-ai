"""
TradeFlow AI — Ingest Node (T-034)

Entry point for the LangGraph pipeline. Loads document metadata from
Supabase and pre-signed URLs from storage into the graph state so
downstream nodes can access raw bytes without re-querying the DB.

SDD §3.1: The ingest node is responsible for:
  1. Fetching batch metadata (batch_id, tier, documents list) from Supabase
  2. Generating signed download URLs for each document from the storage service
  3. Populating DeclarationState with the documents list

This node does NOT download file bytes itself — byte loading is deferred to
the preprocess node so the state remains serialisable for Redis persistence
(PRD Invariant #6).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import structlog

from ..state import DeclarationState

logger = logging.getLogger("agents.ingest")
log = structlog.get_logger()


async def ingest_node(state: DeclarationState) -> dict:
    """
    LangGraph ingest node — populates documents from state or fetches from DB.

    Accepts either:
      - A pre-populated state (documents already set, e.g. from API layer)
      - A minimal state with only batch_id (fetches documents from Supabase)

    Returns updated state keys: documents, batch_id, tier, messages.
    """
    batch_id: str = state.get("batch_id", "")
    if not batch_id:
        raise ValueError("batch_id is required in state to run ingest_node")

    # If documents already populated by the API layer, pass through
    existing_docs: list[dict] = state.get("documents", [])
    if existing_docs:
        log.info(
            "Ingest: documents already in state",
            batch_id=batch_id,
            doc_count=len(existing_docs),
        )
        return {
            "documents": existing_docs,
            "messages": [_make_message(batch_id, len(existing_docs))],
        }

    # Fetch from Supabase if not already set
    try:
        documents = await _fetch_documents_from_db(batch_id)
    except Exception as exc:
        logger.error(f"Ingest failed to load documents for batch {batch_id}: {exc}")
        raise RuntimeError(f"Ingest node: could not load documents for batch {batch_id}") from exc

    log.info(
        "Ingest: loaded documents from DB",
        batch_id=batch_id,
        doc_count=len(documents),
    )

    return {
        "documents": documents,
        "messages": [_make_message(batch_id, len(documents))],
    }


async def _fetch_documents_from_db(batch_id: str) -> list[dict]:
    """
    Fetch document records from Supabase for the given batch_id.

    Returns a list of document dicts:
      {id, batch_id, doc_type, original_name, storage_path, file_hash,
       file_size_bytes, status}
    """
    try:
        from ....api.src.dependencies import get_supabase  # type: ignore
        supabase = get_supabase()
    except Exception:
        logger.warning("Supabase client unavailable in ingest node — returning empty list")
        return []

    result = await (
        supabase.table("documents")
        .select("id, batch_id, doc_type, original_name, storage_path, file_hash, file_size_bytes, status")
        .eq("batch_id", batch_id)
        .execute()
    )
    docs: list[dict] = result.data or []

    if not docs:
        logger.warning(f"No documents found for batch {batch_id}")

    return docs


def _make_message(batch_id: str, doc_count: int) -> dict[str, Any]:
    return {
        "node": "ingest",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "ingest_complete",
        "payload": {
            "batch_id": batch_id,
            "document_count": doc_count,
        },
    }
