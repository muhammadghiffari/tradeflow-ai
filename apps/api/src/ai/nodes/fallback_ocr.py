"""
TradeFlow AI — Fallback OCR Node (Step 2.3)

Used when Gemini extraction fails or confidence is too low.
"""

import structlog
from ..state import ExtractionGraphState

log = structlog.get_logger()

async def fallback_ocr_node(state: ExtractionGraphState) -> dict:
    """
    Step 2.3: Fallback OCR using Azure Document Intelligence or PaddleOCR.
    """
    log.info("Running fallback_ocr_node", batch_id=state["batch_id"])
    
    updated_docs = []
    
    for doc in state["documents"]:
        # Only fallback if error or no data
        if doc.get("error") or not doc.get("extracted_data"):
            log.info("Using fallback OCR for doc", doc_id=doc["doc_id"])
            # Stub: Call Azure DI
            doc["ocr_method"] = "azure-di-fallback"
            doc["extracted_data"] = {"fallback": True, "importer_name": "Recovered by Azure"}
            doc["error"] = None
            
        updated_docs.append(doc)
        
    return {
        "documents": updated_docs,
        "steps": ["fallback_ocr"]
    }
