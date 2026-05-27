"""
TradeFlow AI — Preprocessing Node (Step 2.1)
"""

import structlog
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
        # Stub: normally we would use PyMuPDF or pdf2image here
        quality = 0.95 # Mock high quality
        updated_docs.append({
            **doc,
            "quality_score": quality,
            # In a real impl, pages would be paths to the converted images
            "pages": ["mock_page_1_base64"] 
        })
        
    return {
        "documents": updated_docs,
        "steps": ["preprocess"]
    }
