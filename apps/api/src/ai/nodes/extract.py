"""
TradeFlow AI — Primary LLM Extraction Node (Step 2.2)

Uses Gemini 2.0 Flash Exp for multimodal extraction.
"""

import asyncio
import inspect

import structlog
from pydantic import BaseModel, Field

# Optional production LLM — may be absent in lightweight test environments
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except Exception:  # pragma: no cover - optional dependency
    ChatGoogleGenerativeAI = None

from ...config import settings
from ..state import ExtractionGraphState

# Deterministic stub for tests/E2E
if settings.DETERMINISTIC_E2E:
    try:
        from ..mock_llm import DeterministicLLM as DeterministicLLM  # type: ignore
    except Exception:
        DeterministicLLM = None
else:
    DeterministicLLM = None

log = structlog.get_logger()

# Structured output schema
class CEISAFields(BaseModel):
    importer_name: str | None = Field(description="Name of the importing company")
    importer_npwp: str | None = Field(description="NPWP tax ID of the importer")
    total_packages: int | None = Field(description="Total number of packages/koli")
    gross_weight: float | None = Field(description="Total gross weight in KGM")
    cif_value: float | None = Field(description="Total CIF value")
    currency: str | None = Field(description="Currency code (e.g. USD, IDR)")

async def llm_extraction_node(state: ExtractionGraphState) -> dict:
    """
    Step 2.2: Primary LLM Extraction using Gemini 2.0 Flash Exp.

    Args:
        state: ExtractionGraphState with documents list containing doc_id, storage_path, pages

    Returns:
        dict with:
            - documents: Updated docs with extracted_data or error flag
            - combined_data: Merged field values across docs
            - steps: Execution trace

    Raises:
        Specific exceptions (GoogleAPIError, ValueError) — does NOT catch all exceptions
    """
    log.info("Running llm_extraction_node", batch_id=state["batch_id"])

    # Lazy LLM setup: only instantiate the LLM when we encounter the first document
    # that actually needs LLM extraction (has pages). This keeps unit tests lightweight
    # when LLM dependencies are not installed.
    structured_llm = None

    updated_docs = []
    combined_data = {}

    for doc in state["documents"]:
        # Validate document state before processing
        if not doc.get("doc_id") or not doc.get("pages"):
            log.error(
                "Invalid document state — missing required fields",
                doc_id=doc.get("doc_id"),
                batch_id=state["batch_id"]
            )
            updated_docs.append({
                **doc,
                "error": "Document missing required fields (doc_id, pages)",
                "fallback_required": True,
                "ocr_method": "failed"
            })
            continue

        # Initialize LLM on first real document that needs extraction
        if structured_llm is None:
            if settings.DETERMINISTIC_E2E:
                if DeterministicLLM is None:
                    raise RuntimeError("DETERMINISTIC_E2E enabled but DeterministicLLM not available")
                llm = DeterministicLLM()
            else:
                if ChatGoogleGenerativeAI is None:
                    raise RuntimeError("Production LLM dependency 'langchain_google_genai' is not installed")
                llm = ChatGoogleGenerativeAI(
                    model=settings.GEMINI_MODEL_PRIMARY,
                    temperature=0,
                    api_key=settings.GEMINI_API_KEY
                )

            structured_llm = llm.with_structured_output(CEISAFields)
            # Support both synchronous return and awaitable (coroutine/AsyncMock)
            if asyncio.iscoroutine(structured_llm) or inspect.isawaitable(structured_llm):
                structured_llm = await structured_llm
        # Validate document state before processing
        if not doc.get("doc_id") or not doc.get("pages"):
            log.error(
                "Invalid document state — missing required fields",
                doc_id=doc.get("doc_id"),
                batch_id=state["batch_id"]
            )
            updated_docs.append({
                **doc,
                "error": "Document missing required fields (doc_id, pages)",
                "fallback_required": True,
                "ocr_method": "failed"
            })
            continue

        try:
            # Avoid importing heavy langchain Core in deterministic/test mode
            if settings.DETERMINISTIC_E2E:
                messages = [{"type": "text", "text": "deterministic"}]
            else:
                try:
                    from langchain_core.messages import HumanMessage as _HumanMessage
                except Exception:
                    class _HumanMessage:  # lightweight fallback so tests don't require langchain_core
                        def __init__(self, content):
                            self.content = content

                # Real LLM call with multimodal content
                # Pass pages as base64-encoded images for extraction
                messages = [
                    _HumanMessage(
                        content=[
                            {"type": "text", "text": "Extract all CEISA fields (importer name, NPWP, packages, weight, CIF value) from this document."},
                            {"type": "image_url", "image_url": {"url": doc["pages"][0]}} if doc["pages"] else {"type": "text", "text": "No pages available"}
                        ]
                    )
                ]

            result = await structured_llm.ainvoke(messages)

            # Convert Pydantic model to dict
            raw_extracted = result.model_dump(exclude_none=True) if hasattr(result, 'model_dump') else result
            if asyncio.iscoroutine(raw_extracted):
                raw_extracted = await raw_extracted
            extracted = raw_extracted

            candidates = dict(doc.get("ocr_candidates") or {})
            candidates[settings.GEMINI_MODEL_PRIMARY] = {
                "fields": extracted,
                "confidence": 0.82,
            }

            updated_docs.append({
                **doc,
                "extracted_data": extracted,
                "ocr_method": settings.GEMINI_MODEL_PRIMARY,
                "ocr_candidates": candidates,
                "field_confidences": dict.fromkeys(extracted, 0.82),
            })

            combined_data.update(extracted)

        except (ValueError, KeyError) as e:
            # Expected errors — likely malformed input
            log.exception(
                "Gemini extraction failed — will retry with fallback",
                doc_id=doc.get("doc_id"),
                batch_id=state["batch_id"],
                error_type=type(e).__name__
            )
            updated_docs.append({
                **doc,
                "error": str(e),
                "fallback_required": True,
                "ocr_method": "failed"
            })
        except Exception as e:
            # Unexpected errors — log and re-raise to fail the batch
            log.critical(
                "Unexpected error in LLM extraction — batch will fail",
                doc_id=doc.get("doc_id"),
                batch_id=state["batch_id"],
                error_type=type(e).__name__
            )
            raise

    return {
        "documents": updated_docs,
        "combined_data": combined_data,
        "steps": ["llm_extraction"]
    }
