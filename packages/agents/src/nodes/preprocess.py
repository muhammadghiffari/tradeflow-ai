"""
TradeFlow AI — Preprocessing Node (T-035)

Calls mineru-svc for PDF/image preprocessing: rasterization,
enhancement, watermark removal, page classification, SCAC detection,
and FAST_PATH/STANDARD/DEGRADED routing.
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone

import httpx

from ..state import DeclarationState

logger = logging.getLogger("agents.preprocess")

MINERU_TIMEOUT = 60.0  # seconds


async def preprocess_node(state: DeclarationState) -> dict:
    """
    For each document in state['documents'], call mineru-svc/preprocess.
    Updates state with preprocessed list and logs events to messages.
    """
    from ....api.src.config import settings  # type: ignore

    mineru_url = str(settings.MINERU_SVC_URL).rstrip("/")
    preprocessed = []
    messages = []

    for doc in state["documents"]:
        doc_id = doc["id"]
        doc_type = doc["doc_type"]
        storage_path = doc.get("storage_path", "")

        # Fetch document bytes from Supabase Storage (signed URL or service role)
        try:
            content_b64 = await _fetch_document_b64(storage_path, settings)
        except Exception as e:
            logger.error(f"Failed to fetch document {doc_id}: {e}")
            preprocessed.append({
                "id": doc_id,
                "doc_type": doc_type,
                "processing_route": "DEGRADED",
                "error": str(e),
                "images_b64": [],
                "has_text_layer": False,
                "quality_score": 0.0,
                "page_count": 0,
            })
            continue

        try:
            async with httpx.AsyncClient(timeout=MINERU_TIMEOUT) as client:
                resp = await client.post(
                    f"{mineru_url}/preprocess",
                    json={
                        "document_id": doc_id,
                        "doc_type": doc_type,
                        "content_b64": content_b64,
                        "filename": doc.get("original_name", ""),
                    },
                )
                resp.raise_for_status()
                result = resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"mineru-svc HTTP error for {doc_id}: {e}")
            result = {
                "processing_route": "DEGRADED",
                "error": str(e),
                "pages": [],
                "has_text_layer": False,
                "overall_quality": 0.0,
                "page_count": 0,
            }
        except Exception as e:
            logger.error(f"mineru-svc connection error for {doc_id}: {e}")
            result = {
                "processing_route": "DEGRADED",
                "error": str(e),
                "pages": [],
                "has_text_layer": False,
                "overall_quality": 0.0,
                "page_count": 0,
            }

        # Extract page images (MAIN pages only for OCR)
        pages = result.get("pages", [])
        main_pages = [p for p in pages if p.get("page_type") in ("MAIN", "ATTACHMENT")]
        images_b64 = [p["image_b64"] for p in main_pages]

        preprocessed.append({
            "id": doc_id,
            "doc_type": doc_type,
            "processing_route": result.get("processing_route", "STANDARD"),
            "carrier_scac": result.get("carrier_scac"),
            "images_b64": images_b64,
            "has_text_layer": result.get("has_text_layer", False),
            "quality_score": result.get("overall_quality", 0.0),
            "page_count": result.get("page_count", len(pages)),
            "signed_url": doc.get("signed_url"),
        })

        messages.append({
            "node": "preprocess",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "document_preprocessed",
            "payload": {
                "document_id": doc_id,
                "route": result.get("processing_route"),
                "quality": result.get("overall_quality"),
            },
        })

    return {
        "preprocessed": preprocessed,
        "messages": messages,
    }


async def _fetch_document_b64(storage_path: str, settings) -> str:
    """
    Fetch document bytes from Supabase Storage and return as base64.
    Uses service role key for server-side access.
    """
    supabase_url = settings.SUPABASE_URL.rstrip("/")
    bucket = "tradeflow-documents"
    url = f"{supabase_url}/storage/v1/object/{bucket}/{storage_path}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            url,
            headers={
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
                "apikey": settings.SUPABASE_SERVICE_KEY,
            },
        )
        resp.raise_for_status()
        return base64.b64encode(resp.content).decode()
