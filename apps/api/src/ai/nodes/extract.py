"""
TradeFlow AI — Primary LLM Extraction Node (Step 2.2)

Uses Gemini 2.0 Flash Exp for multimodal extraction, or a local Ollama LLM
when USE_LOCAL_LLM=true.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re

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


# Structured output schema — comprehensive CEISA + B/L fields
class CEISAFields(BaseModel):
    # Importer / Consignee
    importer_name: str | None = Field(description="Name of importing company (consignee)")
    importer_npwp: str | None = Field(description="NPWP tax ID, 15-16 digits, explicitly labeled NPWP")
    importer_address: str | None = Field(description="Address of importer/consignee")
    # Shipper / Exporter
    exporter_name: str | None = Field(description="Name of exporting company (shipper)")
    exporter_address: str | None = Field(description="Address of exporter/shipper")
    # B/L and document references
    bl_number: str | None = Field(description="Bill of Lading number")
    bl_date: str | None = Field(description="Date of B/L issue")
    # Vessel and voyage
    vessel_name: str | None = Field(description="Name of the ocean vessel")
    voyage_number: str | None = Field(description="Voyage number")
    # Ports
    port_of_loading: str | None = Field(description="Port of loading (departure)")
    port_of_discharge: str | None = Field(description="Port of discharge (destination)")
    # Cargo
    total_packages: int | None = Field(description="Total number of packages/koli across ALL containers")
    gross_weight: float | None = Field(description="Total gross weight in KGS/KGM")
    # Container numbers (as a comma-separated string)
    container_numbers: str | None = Field(description="Container numbers, comma-separated")
    description_of_goods: str | None = Field(description="General description of goods")
    hs_code: str | None = Field(description="HS/BTKI tariff code exactly as printed, do not pad or correct")
    # Commercial values (usually from Invoice, may be absent in B/L)
    cif_value: float | None = Field(description="Total CIF value")
    fob_value: float | None = Field(description="Total FOB value")
    freight_value: float | None = Field(description="Freight value")
    insurance_value: float | None = Field(description="Insurance value")
    currency: str | None = Field(description="Currency code (e.g. USD, IDR)")
    importer_nib: str | None = Field(description="Importer NIB business ID exactly as printed")
    # Incoterms
    incoterms: str | None = Field(description="Incoterms (e.g. FOB, CIF, CFR)")
    freight_terms: str | None = Field(description="Freight terms (PREPAID or COLLECT)")


def _parse_json_from_text(text: str) -> dict:
    """
    Robustly extract a JSON object from LLM plain-text output.
    Handles markdown code fences and DeepSeek-style <think> tags.
    """
    # Strip <think>...</think> tags (DeepSeek-R1 style)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # Try JSON inside markdown fences first
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Fall back to bare JSON object
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return {}


def _normalize_for_evidence(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _field_value_has_text_evidence(field: str, value: object, raw_text: str) -> bool:
    normalized_value = _normalize_for_evidence(value)
    normalized_text = _normalize_for_evidence(raw_text)
    if not normalized_value:
        return False
    if normalized_value in normalized_text:
        return True
    if field in {"gross_weight", "cif_value", "fob_value", "freight_value", "insurance_value"}:
        numeric = re.sub(r"[^0-9]", "", str(value))
        return bool(numeric and numeric in normalized_text)
    if field == "total_packages":
        numeric = re.sub(r"[^0-9]", "", str(value))
        return bool(numeric and numeric in normalized_text)
    return False


def _field_format_valid(field: str, value: object) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if field == "importer_npwp":
        return len(re.sub(r"\D", "", text)) in {15, 16}
    if field == "importer_nib":
        return len(re.sub(r"\D", "", text)) == 13
    if field == "hs_code":
        return bool(re.fullmatch(r"\d{8}", text))
    if field == "currency":
        return bool(re.fullmatch(r"[A-Z]{3}", text))
    if field in {"gross_weight", "cif_value", "fob_value", "freight_value", "insurance_value"}:
        try:
            return float(str(value).replace(",", "")) >= 0
        except (TypeError, ValueError):
            return False
    if field == "total_packages":
        try:
            return int(float(str(value).replace(",", ""))) > 0
        except (TypeError, ValueError):
            return False
    return True


def _estimate_field_confidences(extracted: dict, doc: dict) -> dict[str, float]:
    raw_text = doc.get("raw_text") or ""
    candidates = doc.get("ocr_candidates") or {}
    pdf_candidate = candidates.get("pdf_text") or {}
    base = 0.88 if doc.get("document_mode") == "digital_pdf_text" else 0.82
    if pdf_candidate.get("confidence"):
        base = max(base, min(0.96, float(pdf_candidate.get("confidence")) * 0.94))

    confidences: dict[str, float] = {}
    for field, value in extracted.items():
        confidence = base
        has_evidence = _field_value_has_text_evidence(field, value, raw_text)
        format_valid = _field_format_valid(field, value)
        if has_evidence:
            confidence += 0.05
        else:
            confidence -= 0.12
        if not format_valid:
            confidence -= 0.25
        confidences[field] = round(max(0.35, min(0.99, confidence)), 4)
    return confidences


async def llm_extraction_node(state: ExtractionGraphState) -> dict:
    """
    Step 2.2: Primary LLM Extraction.

    - When USE_LOCAL_LLM=true: uses Ollama (text-only, manual JSON parsing).
    - Otherwise: uses Gemini multimodal (with_structured_output).

    Returns:
        dict with documents, combined_data, steps
    """
    log.info("Running llm_extraction_node", batch_id=state["batch_id"])

    # LLM instances — lazily initialized on first document
    llm = None
    structured_llm = None
    use_manual_json = False  # True for Ollama (no function-calling)

    updated_docs = []
    combined_data = {}

    for doc in state["documents"]:
        # ── Guard: document must have doc_id and pages ──────────────────────
        has_extraction_input = bool(doc.get("pages")) or bool((doc.get("raw_text") or "").strip())
        if not doc.get("doc_id") or not has_extraction_input:
            log.error(
                "Invalid document state — missing required fields",
                doc_id=doc.get("doc_id"),
                batch_id=state["batch_id"],
            )
            updated_docs.append({
                **doc,
                "error": "Document missing required fields (doc_id and pages/raw_text)",
                "fallback_required": True,
                "ocr_method": "failed",
            })
            continue

        # ── Initialize LLM once ─────────────────────────────────────────────
        if llm is None:
            if settings.DETERMINISTIC_E2E:
                if DeterministicLLM is None:
                    raise RuntimeError("DETERMINISTIC_E2E enabled but DeterministicLLM not available")
                llm = DeterministicLLM()
                structured_llm = llm.with_structured_output(CEISAFields)
                use_manual_json = False

            elif settings.USE_LOCAL_LLM:
                try:
                    from langchain_openai import ChatOpenAI
                except ImportError:
                    raise RuntimeError("Dependency 'langchain_openai' is required for local LLM support")

                # Supports comma-separated models: "qwen2.5:7b,mistral:7b"
                local_models = [m.strip() for m in settings.LOCAL_LLM_MODEL.split(",") if m.strip()]
                if not local_models:
                    local_models = ["qwen2.5:7b"]

                primary_llm = ChatOpenAI(
                    model=local_models[0],
                    base_url=settings.OLLAMA_BASE_URL,
                    api_key="ollama",
                    temperature=0,
                    max_retries=1,
                )
                log.info("Using primary local LLM", model=local_models[0])

                if len(local_models) > 1:
                    fallback_llms = [
                        ChatOpenAI(
                            model=m,
                            base_url=settings.OLLAMA_BASE_URL,
                            api_key="ollama",
                            temperature=0,
                            max_retries=1,
                        )
                        for m in local_models[1:]
                    ]
                    llm = primary_llm.with_fallbacks(fallback_llms)
                    log.info("Configured local fallback LLMs", models=local_models[1:])
                else:
                    llm = primary_llm

                # Ollama does NOT support function-calling — parse JSON manually
                use_manual_json = True

            else:
                # ── Gemini (multimodal, with_structured_output) ──────────────
                if ChatGoogleGenerativeAI is None:
                    raise RuntimeError("Production LLM dependency 'langchain_google_genai' is not installed")

                primary_llm = ChatGoogleGenerativeAI(
                    model=settings.GEMINI_MODEL_PRIMARY,
                    temperature=0,
                    api_key=settings.GEMINI_API_KEY,
                )
                fallback_llms = []
                try:
                    from langchain_openai import ChatOpenAI
                    olm_llm = ChatOpenAI(
                        model=settings.OLM_BASE_MODEL,
                        base_url=f"{settings.OLM_INFERENCE_URL}/v1",
                        api_key="empty",
                        temperature=0,
                        max_retries=1,
                    )
                    fallback_llms.append(olm_llm)
                except Exception as e:
                    log.warning("Could not setup OLM fallback", error=str(e))

                gemini_fallback = ChatGoogleGenerativeAI(
                    model=settings.GEMINI_MODEL_FALLBACK,
                    temperature=0,
                    api_key=settings.GEMINI_API_KEY,
                )
                fallback_llms.append(gemini_fallback)
                llm = primary_llm.with_fallbacks(fallback_llms)
                structured_llm = llm.with_structured_output(CEISAFields)
                if asyncio.iscoroutine(structured_llm) or inspect.isawaitable(structured_llm):
                    structured_llm = await structured_llm
                use_manual_json = False

        # ── Build prompt messages ───────────────────────────────────────────
        try:
            if settings.DETERMINISTIC_E2E:
                messages = [{"type": "text", "text": "deterministic"}]
            else:
                try:
                    from langchain_core.messages import HumanMessage as _HumanMessage
                except Exception:
                    class _HumanMessage:  # lightweight fallback
                        def __init__(self, content):
                            self.content = content

                if use_manual_json:
                    # Text-only prompt for local Ollama models
                    raw_text = doc.get("raw_text", "")
                    content = (
                        "You are a strictly accurate customs document parser for CEISA 4.0 (Indonesian Customs). "
                        "Extract ALL the following fields from the document.\n"
                        "CRITICAL RULES:\n"
                        "1. If a value is NOT clearly present in the text, return null for that field. DO NOT GUESS.\n"
                        "2. Return ONLY a valid JSON object. No explanation, no markdown.\n"
                        "3. For gross_weight: remove commas used as thousand separators (e.g. '11,603.000' -> 11603.0).\n"
                        "4. For total_packages: sum ALL container package counts (e.g. '20 PACKAGES' + '17 PACKAGES' = 37).\n"
                        "5. For importer_npwp: ONLY extract if the text explicitly says 'NPWP' or 'Tax ID'. DO NOT use B/L numbers.\n\n"
                        "Fields to extract (return as JSON keys):\n"
                        "- importer_name: Consignee / buyer company name\n"
                        "- importer_npwp: NPWP tax ID (15-16 digits, null if not found)\n"
                        "- importer_address: Consignee/importer address\n"
                        "- exporter_name: Shipper / seller company name\n"
                        "- exporter_address: Shipper/exporter address\n"
                        "- bl_number: Bill of Lading number\n"
                        "- bl_date: B/L issue date (ISO 8601 if possible)\n"
                        "- vessel_name: Ocean vessel name\n"
                        "- voyage_number: Voyage number\n"
                        "- port_of_loading: Port of departure\n"
                        "- port_of_discharge: Port of destination\n"
                        "- total_packages: TOTAL packages across ALL containers (integer)\n"
                        "- gross_weight: Total gross weight in KGS as a plain float (no commas)\n"
                        "- container_numbers: All container numbers comma-separated\n"
                        "- description_of_goods: Brief description of cargo\n"
                        "- hs_code: HS/BTKI code exactly as printed; do NOT pad/correct invalid 6-digit codes\n"
                        "- cif_value: CIF value (float, null if not in document)\n"
                        "- fob_value: FOB value (float, null if not in document)\n"
                        "- freight_value: Freight value (float, null if not in document)\n"
                        "- insurance_value: Insurance value (float, null if not in document)\n"
                        "- currency: Currency code (USD/IDR/EUR etc, null if not found)\n"
                        "- importer_nib: NIB exactly as printed, null if not found\n"
                        "- incoterms: Incoterms code (FOB/CIF/CFR etc, null if not found)\n"
                        "- freight_terms: PREPAID or COLLECT (null if not found)\n\n"
                        f"Document Text:\n{raw_text[:12000]}"
                    )
                    messages = [_HumanMessage(content=[{"type": "text", "text": content}])]
                else:
                    # Multimodal prompt for Gemini
                    raw_text = (doc.get("raw_text") or "")[:12000]
                    prompt_text = (
                        "Extract all CEISA fields (importer name, NPWP, packages, weight, CIF value) from this document."
                    )
                    if raw_text:
                        prompt_text += f"\n\nDirect PDF/OCR text:\n{raw_text}"
                    messages = [
                        _HumanMessage(
                            content=[
                                {
                                    "type": "text",
                                    "text": prompt_text,
                                },
                                (
                                    {"type": "image_url", "image_url": {"url": doc["pages"][0]}}
                                    if doc.get("pages")
                                    else {"type": "text", "text": "No pages available"}
                                ),
                            ]
                        )
                    ]

            # ── Invoke LLM ──────────────────────────────────────────────────
            if use_manual_json:
                response = await llm.ainvoke(messages)
                text_response = response.content if hasattr(response, "content") else str(response)
                raw_extracted = _parse_json_from_text(text_response)
                # Coerce through Pydantic for type safety
                try:
                    validated = CEISAFields(**raw_extracted)
                    extracted = validated.model_dump(exclude_none=True)
                except Exception:
                    extracted = {k: v for k, v in raw_extracted.items() if v is not None}
            else:
                result = await structured_llm.ainvoke(messages)
                raw_result = result.model_dump(exclude_none=True) if hasattr(result, "model_dump") else result
                if asyncio.iscoroutine(raw_result):
                    raw_result = await raw_result
                extracted = raw_result

            candidates = dict(doc.get("ocr_candidates") or {})
            field_confidences = _estimate_field_confidences(extracted, doc)
            candidates[settings.GEMINI_MODEL_PRIMARY] = {
                "fields": extracted,
                "confidence": round(sum(field_confidences.values()) / len(field_confidences), 4) if field_confidences else 0.0,
                "field_confidences": field_confidences,
            }

            updated_docs.append({
                **doc,
                "extracted_data": extracted,
                "ocr_method": settings.GEMINI_MODEL_PRIMARY,
                "ocr_candidates": candidates,
                "field_confidences": field_confidences,
            })
            combined_data.update(extracted)

        except Exception as e:
            # Per-document failure — mark for fallback, do NOT crash the batch
            log.exception(
                "LLM extraction failed — marking doc for fallback",
                doc_id=doc.get("doc_id"),
                batch_id=state["batch_id"],
                error_type=type(e).__name__,
                error=str(e),
            )
            updated_docs.append({
                **doc,
                "error": str(e),
                "fallback_required": True,
                "ocr_method": "failed",
            })

    return {
        "documents": updated_docs,
        "combined_data": combined_data,
        "steps": ["llm_extraction"],
    }
