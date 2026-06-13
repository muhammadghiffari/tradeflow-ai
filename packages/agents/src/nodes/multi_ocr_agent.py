"""
TradeFlow AI — Multi-OCR Agent Node (T-036, T-037)

Runs all 4 OCR agents in parallel via asyncio.gather.
Per SDD §5.1 — if 3+ agents fail, raise RuntimeError.
Individual agent failures are tolerated and logged.

Agents:
  A: Surya 2 (surya-svc:8001)
  B: PaddleOCR 3.0 (paddleocr-svc:8002)
  C: Azure DI 4.0 (azure-ai-documentintelligence SDK)
  D: olmOCR-2-7B-CIPL (olm-inference:8000 via vLLM OpenAI endpoint)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from ..state import DeclarationState

logger = logging.getLogger("agents.multi_ocr")

AGENT_TIMEOUT = 30.0  # seconds per agent (per SDD §5.1)


async def multi_ocr_node(state: DeclarationState) -> dict:
    """
    Run all 4 OCR agents in parallel for each preprocessed document.
    FAST_PATH documents skip to PP-ChatOCRv4 only (Agent B /kia endpoint).
    """
    from ....api.src.config import settings  # type: ignore

    surya_outputs: list[dict | None] = []
    layout_analyses: list[dict | None] = []
    azure_di_outputs: list[dict | None] = []
    extraction_results: list[dict | None] = []
    messages = []

    for doc in state["preprocessed"]:
        doc_id = doc.get("id", "unknown")
        route = doc.get("processing_route", "STANDARD")

        if route == "FAST_PATH":
            # Only Agent B KIA (PP-ChatOCRv4) — faster, high quality docs
            logger.info(f"Doc {doc_id}: FAST_PATH → PaddleOCR KIA only")
            kia_result = await _run_agent_b_kia(doc, settings)
            surya_outputs.append(None)
            layout_analyses.append(kia_result)
            azure_di_outputs.append(None)
            extraction_results.append(kia_result)
            messages.append({
                "node": "multi_ocr",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "fast_path_ocr",
                "payload": {"document_id": doc_id, "method": "pp_chat_ocr_v4"},
            })
            continue

        # STANDARD / DEGRADED: run all 4 agents in parallel
        tasks = [
            _run_agent_a_surya(doc, settings),
            _run_agent_b_paddleocr(doc, settings),
            _run_agent_c_azure_di(doc, settings),
            _run_agent_d_olm(doc, settings),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        surya_out, paddle_out, azure_out, olm_out = results

        # Normalize exceptions to None and log
        if isinstance(surya_out, Exception):
            logger.warning(f"Agent A (Surya) failed for {doc_id}: {surya_out}")
            surya_out = None
        if isinstance(paddle_out, Exception):
            logger.warning(f"Agent B (PaddleOCR) failed for {doc_id}: {paddle_out}")
            paddle_out = None
        if isinstance(azure_out, Exception):
            logger.warning(f"Agent C (Azure DI) failed for {doc_id}: {azure_out}")
            azure_out = None
        if isinstance(olm_out, Exception):
            logger.error(f"Agent D (olmOCR) failed for {doc_id}: {olm_out}")
            olm_out = None

        # SDD §5.1: 3 or more failures = critical, abort pipeline
        failures = sum(1 for x in [surya_out, paddle_out, azure_out, olm_out] if x is None)
        if failures >= 3:
            raise RuntimeError(
                f"Critical: {failures}/4 OCR agents failed for document {doc_id}. "
                "Cannot proceed with less than 2 agent results."
            )

        surya_outputs.append(surya_out)
        layout_analyses.append(paddle_out)
        azure_di_outputs.append(azure_out)
        extraction_results.append(olm_out)

        messages.append({
            "node": "multi_ocr",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "multi_ocr_complete",
            "payload": {
                "document_id": doc_id,
                "agents_succeeded": 4 - failures,
                "agents_failed": failures,
            },
        })

    return {
        "surya_output": surya_outputs,
        "layout_analysis": layout_analyses,
        "azure_di_output": azure_di_outputs,
        "extraction_results": extraction_results,
        "messages": messages,
    }


# ─────────────────────────────────────────────────────────────
# Per-agent HTTP clients (T-037)
# ─────────────────────────────────────────────────────────────

async def _run_agent_a_surya(doc: dict, settings: Any) -> dict:
    """Agent A: Surya 2 — text blocks, layout, HTML output."""
    url = str(settings.SURYA_INFERENCE_URL).rstrip("/")
    async with httpx.AsyncClient(timeout=AGENT_TIMEOUT) as client:
        resp = await client.post(
            f"{url}/extract",
            json={
                "images_b64": doc["images_b64"],
                "doc_type": doc["doc_type"],
            },
        )
        resp.raise_for_status()
        return resp.json()


async def _run_agent_b_paddleocr(doc: dict, settings: Any) -> dict:
    """Agent B: PaddleOCR PP-StructureV3 — layout + table cells."""
    url = str(settings.PADDLEOCR_SVC_URL).rstrip("/")
    # Send first image (main page)
    image_b64 = doc["images_b64"][0] if doc["images_b64"] else ""
    async with httpx.AsyncClient(timeout=AGENT_TIMEOUT) as client:
        resp = await client.post(
            f"{url}/extract",
            json={
                "image_b64": image_b64,
                "doc_type": doc["doc_type"],
            },
        )
        resp.raise_for_status()
        return resp.json()


async def _run_agent_b_kia(doc: dict, settings: Any) -> dict:
    """FAST_PATH: PP-ChatOCRv4 KIA endpoint — high-accuracy key info extraction."""
    url = str(settings.PADDLEOCR_SVC_URL).rstrip("/")
    image_b64 = doc["images_b64"][0] if doc["images_b64"] else ""
    async with httpx.AsyncClient(timeout=AGENT_TIMEOUT) as client:
        resp = await client.post(
            f"{url}/kia",
            json={
                "image_b64": image_b64,
                "doc_type": doc["doc_type"],
                "extraction_schema_prompt": _get_kia_prompt(doc["doc_type"]),
            },
        )
        resp.raise_for_status()
        return resp.json()


async def _run_agent_c_azure_di(doc: dict, settings: Any) -> dict | None:
    """
    Agent C: Azure DI 4.0 — prebuilt-invoice or prebuilt-document model.
    Skips automatically if:
      - ENABLE_AZURE_DI_AGENT=False
      - Azure DI monthly quota (5000 pages) is near limit
    """
    if not settings.ENABLE_AZURE_DI_AGENT:
        return None

    from ....api.src.services.azure_quota_svc import AzureQuotaService  # type: ignore

    page_count = doc.get("page_count", 1)
    quota_svc = AzureQuotaService()

    if not await quota_svc.check_available(page_count):
        logger.warning(
            f"Azure DI quota near limit (free tier: {settings.AZURE_DI_FREE_LIMIT} pages/month). "
            "Skipping Agent C for this document."
        )
        return None

    try:
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
        from azure.core.credentials import AzureKeyCredential

        az_client = DocumentIntelligenceClient(
            endpoint=str(settings.AZURE_DI_ENDPOINT),
            credential=AzureKeyCredential(settings.AZURE_DI_KEY.get_secret_value()),
        )

        model_id = (
            "prebuilt-invoice"
            if doc["doc_type"] == "invoice"
            else "prebuilt-document"
        )

        signed_url = doc.get("signed_url")
        if not signed_url:
            logger.warning("No signed_url for Azure DI — skipping Agent C")
            return None

        poller = az_client.begin_analyze_document(
            model_id,
            AnalyzeDocumentRequest(url_source=signed_url),
        )
        result = poller.result()
        await quota_svc.increment(page_count)

        return _serialize_azure_di_result(result)

    except Exception as e:
        logger.error(f"Azure DI SDK error: {e}")
        raise


async def _run_agent_d_olm(doc: dict, settings: Any) -> dict:
    """
    Agent D: olmOCR-2-7B-CIPL — vLLM OpenAI-compatible chat completions.
    Sends all page images as multi-turn messages with extraction schema.
    """
    url = str(settings.OLM_INFERENCE_URL).rstrip("/")
    messages = _build_olm_extraction_messages(doc)

    async with httpx.AsyncClient(timeout=AGENT_TIMEOUT) as client:
        resp = await client.post(
            f"{url}/v1/chat/completions",
            json={
                "model": "cipl_adapter",   # LoRA adapter name registered in vLLM
                "messages": messages,
                "temperature": 0.0,
                "max_tokens": 2048,
            },
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return _parse_olm_json_output(content)


# ─────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────

def _get_kia_prompt(doc_type: str) -> str:
    """Returns the KIA schema prompt for PP-ChatOCRv4 based on doc type."""
    schemas = {
        "bill_of_lading": (
            "Extract the following fields: shipper_name, consignee_name, "
            "notify_party, bl_number, vessel_name, voyage_number, port_of_loading, "
            "port_of_discharge, gross_weight, net_weight, total_packages, "
            "container_numbers, description_of_goods, bl_date, eta"
        ),
        "invoice": (
            "Extract: invoice_number, invoice_date, seller_name, seller_address, "
            "buyer_name, buyer_address, buyer_npwp, currency, total_fob, "
            "freight, insurance, total_cif, payment_terms, "
            "line_items[{description, quantity, unit, unit_price, amount, hs_code}]"
        ),
        "packing_list": (
            "Extract: pl_number, pl_date, shipper_name, consignee_name, "
            "total_packages, total_gross_weight, total_net_weight, "
            "line_items[{description, quantity, package_count, gross_weight, net_weight, marks}]"
        ),
    }
    return schemas.get(doc_type, "Extract all key-value pairs from this shipping document.")


def _build_olm_extraction_messages(doc: dict) -> list[dict]:
    """Build multi-modal messages for olmOCR-2-7B-CIPL extraction."""
    system_prompt = (
        "You are an expert customs document parser specializing in Indonesian import "
        "declarations (PIB CEISA 4.0). Extract all CEISA fields from the provided "
        "document image(s). Return a valid JSON object with field names as keys and "
        '{"value": ..., "confidence": 0.0-1.0} as values. '
        "If a field is not found, set value to null and confidence to 0.0."
    )

    messages = [{"role": "system", "content": system_prompt}]

    # Add each page as an image content block
    for i, img_b64 in enumerate(doc.get("images_b64", [])[:3]):  # max 3 pages
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                },
                {
                    "type": "text",
                    "text": (
                        f"Document type: {doc.get('doc_type', 'unknown')}. "
                        f"Page {i + 1}. Extract all CEISA fields as JSON."
                    ),
                },
            ],
        })

    return messages


def _parse_olm_json_output(content: str) -> dict:
    """Parse olmOCR JSON output, handling markdown code fences."""
    import json
    import re

    # Strip markdown code blocks
    content = re.sub(r"```(?:json)?\s*", "", content).strip()

    try:
        parsed = json.loads(content)
        return {"fields": parsed, "method": "olm_ocr_cipl"}
    except json.JSONDecodeError:
        logger.error(f"olmOCR returned non-JSON: {content[:200]}")
        return {"fields": {}, "method": "olm_ocr_cipl", "parse_error": True}


def _serialize_azure_di_result(result: Any) -> dict:
    """Serialize azure-ai-documentintelligence result to a plain dict."""
    fields = {}
    if hasattr(result, "documents") and result.documents:
        for doc_result in result.documents:
            if hasattr(doc_result, "fields"):
                for field_name, field_value in doc_result.fields.items():
                    if field_value:
                        fields[field_name] = {
                            "value": getattr(field_value, "value_string", None)
                            or str(getattr(field_value, "content", "")),
                            "confidence": getattr(field_value, "confidence", 0.0),
                        }

    return {
        "fields": fields,
        "model": "azure_di_4.0",
        "page_count": len(getattr(result, "pages", [])),
    }
