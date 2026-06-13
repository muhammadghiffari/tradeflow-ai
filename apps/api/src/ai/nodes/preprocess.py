"""
TradeFlow AI — Preprocessing Node (Step 2.1)
"""

import structlog

from ...services.ingest_svc import get_storage_service
from ...services.ocr_engine_svc import ocr_engine_service
from ..state import ExtractionGraphState

log = structlog.get_logger()

async def preprocess_documents_node(state: ExtractionGraphState) -> dict:
    """
    Step 2.1: Document Preprocessing Node
    - Checks document quality
    - Converts PDFs to images if necessary
    - Sets quality score
    """
    log.info("Running preprocess_documents_node", batch_id=state["batch_id"])

    updated_docs = []
    for doc in state["documents"]:
        storage_path = doc.get("storage_path")
        if not storage_path:
            updated_docs.append({
                **doc,
                "quality_score": 0.0,
                "pages": [],
                "ocr_candidates": {},
                "error": "Document missing storage_path",
            })
            continue

        try:
            file_bytes = await get_storage_service().download_document(storage_path)
            prepared = await ocr_engine_service.prepare_document(
                doc_id=doc["doc_id"],
                storage_path=storage_path,
                filename=doc.get("original_name") or storage_path,
                file_bytes=file_bytes,
            )
        except Exception as exc:
            log.exception(
                "Document preprocessing/OCR failed",
                batch_id=state["batch_id"],
                doc_id=doc.get("doc_id"),
                error=str(exc),
            )
            updated_docs.append({
                **doc,
                "quality_score": 0.0,
                "pages": [],
                "ocr_candidates": {},
                "error": str(exc),
            })
            continue

        updated_docs.append({
            **doc,
            **prepared,
            "ocr_method": "+".join(prepared["ocr_candidates"].keys()) or None,
        })

    return {
        "documents": updated_docs,
        "steps": ["preprocess"]
    }
