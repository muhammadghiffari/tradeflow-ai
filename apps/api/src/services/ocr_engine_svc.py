"""
Physical OCR engine integration for TradeFlow documents.

This module turns uploaded PDFs/images into measurable OCR candidates from:
- direct PDF text extraction
- PaddleOCR
- Azure Document Intelligence

Each engine returns raw text, field candidates, confidence, and latency so the
LangGraph pipeline can reconcile competing evidence instead of trusting a stub.
"""

from __future__ import annotations

import asyncio
import base64
import io
import mimetypes
import re
import tempfile
import time
from pathlib import Path
from typing import Any

import structlog

from ..config import settings

log = structlog.get_logger()

CEISA_FIELD_PATTERNS = {
    "importer_npwp": [
        r"\b(?:NPWP|Tax\s*ID|TIN)[^\n0-9]*([0-9.\- ]{10,24})",
    ],
    "total_packages": [
        r"\b(?:total\s+packages|packages|jumlah\s+koli|koli)[^\n0-9]*(\d{1,7})",
    ],
    "gross_weight": [
        r"\b(?:gross\s+weight|gross\s+wt|berat\s+kotor)[^\n0-9]*([0-9,.]+)",
    ],
    "cif_value": [
        r"\b(?:CIF|total\s+amount|invoice\s+value|nilai\s+cif)[^\n0-9]*(?:[A-Z]{3})?\s*([0-9,.]+)",
    ],
    "currency": [
        r"\b(?:currency|curr|mata\s+uang)[^\nA-Z]*([A-Z]{3})\b",
        r"\b(USD|IDR|SGD|EUR|JPY|CNY)\b",
    ],
    "importer_name": [
        (
            r"\b(?:importer|consignee|buyer|notify\s+party)[^\n:]*[:\-]\s*"
            r"([A-Z0-9][A-Z0-9 .,&'/-]{3,80})"
        ),
    ],
}


def _as_float(value: str) -> float | None:
    try:
        # Handle European format: "11,603.000" (comma = thousands separator)
        # Detect if comma is used as thousands: e.g., "11,603.000" has comma before 3+ digits before decimal
        cleaned = value.strip()
        if re.search(r"\d,\d{3}(\.|$)", cleaned):
            cleaned = cleaned.replace(",", "")
        else:
            # Could be decimal comma: "11.603,000" -> 11603.0
            cleaned = cleaned.replace(".", "").replace(",", ".")
        return float(cleaned)
    except (ValueError, AttributeError):
        return None


def extract_ceisa_fields_from_text(text: str) -> dict[str, Any]:
    """Lightweight field extraction from OCR text for candidate generation."""
    fields: dict[str, Any] = {}
    for field, patterns in CEISA_FIELD_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue
            value = match.group(1).strip(" :\t\r\n")
            if field in {"gross_weight", "cif_value"}:
                numeric = _as_float(value)
                if numeric is None:
                    continue
                fields[field] = numeric
            elif field == "total_packages":
                fields[field] = int(value.replace(",", ""))
            elif field == "currency":
                fields[field] = value.upper()[:3]
            else:
                fields[field] = re.sub(r"\s+", " ", value).strip()
            break
    return fields


def _data_url(image_bytes: bytes, mime_type: str = "image/png") -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


class OCREngineService:
    def __init__(self) -> None:
        self._paddle = None

    async def prepare_document(
        self,
        *,
        doc_id: str,
        storage_path: str,
        filename: str | None,
        file_bytes: bytes,
    ) -> dict[str, Any]:
        """Render pages, run OCR engines, and return graph-ready document data."""
        started = time.perf_counter()
        suffix = Path(filename or storage_path).suffix.lower()
        mime_type = mimetypes.guess_type(filename or storage_path)[0] or "application/octet-stream"
        is_pdf = suffix == ".pdf" or mime_type == "application/pdf"

        raw_text = ""
        candidates: dict[str, dict[str, Any]] = {}

        if is_pdf:
            direct_candidate = await asyncio.to_thread(self._extract_pdf_text, file_bytes)
            raw_text = direct_candidate.get("text", "")
            if direct_candidate.get("fields") or raw_text.strip():
                candidates["pdf_text"] = direct_candidate

            if self._is_pdf_text_fast_path(direct_candidate):
                latency_ms = round((time.perf_counter() - started) * 1000, 2)
                log.info(
                    "Digital PDF fast path selected",
                    doc_id=doc_id,
                    storage_path=storage_path,
                    text_chars=direct_candidate.get("text_chars"),
                    text_chars_per_page=direct_candidate.get("text_chars_per_page"),
                    fields=list((direct_candidate.get("fields") or {}).keys()),
                    latency_ms=latency_ms,
                )
                return {
                    "pages": [],
                    "raw_text": raw_text,
                    "ocr_candidates": candidates,
                    "quality_score": float(direct_candidate.get("confidence") or 1.0),
                    "document_mode": "digital_pdf_text",
                    "ocr_engine_latencies_ms": {
                        name: candidate.get("latency_ms") for name, candidate in candidates.items()
                    },
                }

        page_images = await asyncio.to_thread(self._render_page_images, file_bytes, suffix)

        if settings.CLOUD_LLM_ONLY:
            page_data_urls = [_data_url(b) for b in page_images[: settings.OCR_MAX_LLM_PAGES]]
            return {
                "pages": page_data_urls,
                "raw_text": "",
                "ocr_candidates": {},
                "quality_score": 1.0,
                "ocr_engine_latencies_ms": {}
            }

        paddle_task = self._run_paddle(page_images)
        surya_task = self._run_surya(page_images) if settings.ENABLE_SURYA_AGENT else None
        azure_task = self._run_azure(file_bytes, mime_type) if settings.ENABLE_DUAL_OCR else None

        gather_tasks = [paddle_task]
        if surya_task is not None:
            gather_tasks.append(surya_task)
        if azure_task is not None:
            gather_tasks.append(azure_task)
        results = await asyncio.gather(*gather_tasks)
        idx = 0

        paddle_candidate = results[idx]
        idx += 1
        if paddle_candidate.get("fields") or paddle_candidate.get("text"):
            candidates["paddleocr"] = paddle_candidate
            raw_text = "\n".join(
                part for part in [raw_text, paddle_candidate.get("text", "")] if part
            )

        if surya_task is not None:
            surya_candidate = results[idx]
            idx += 1
            if surya_candidate.get("fields") or surya_candidate.get("text"):
                candidates["surya"] = surya_candidate
                raw_text = "\n".join(
                    part for part in [raw_text, surya_candidate.get("text", "")] if part
                )

        if azure_task is not None:
            azure_candidate = results[idx]
            if azure_candidate.get("fields") or azure_candidate.get("text"):
                candidates["azure-di"] = azure_candidate
                raw_text = "\n".join(
                    part for part in [raw_text, azure_candidate.get("text", "")] if part
                )

        quality_score = self._estimate_quality(page_images)
        page_data_urls = [
            _data_url(image_bytes) for image_bytes in page_images[: settings.OCR_MAX_LLM_PAGES]
        ]

        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        log.info(
            "Physical OCR engines completed",
            doc_id=doc_id,
            storage_path=storage_path,
            engines=list(candidates.keys()),
            quality_score=quality_score,
            latency_ms=latency_ms,
        )

        return {
            "pages": page_data_urls,
            "raw_text": raw_text,
            "ocr_candidates": candidates,
            "quality_score": quality_score,
            "document_mode": "rendered_ocr",
            "ocr_engine_latencies_ms": {
                name: candidate.get("latency_ms") for name, candidate in candidates.items()
            },
        }

    def _is_pdf_text_fast_path(self, candidate: dict[str, Any]) -> bool:
        """Use direct PDF text when the text layer is dense enough to avoid heavy OCR."""
        text_chars = int(candidate.get("text_chars") or 0)
        page_count = max(1, int(candidate.get("page_count") or 1))
        text_chars_per_page = text_chars / page_count
        confidence = float(candidate.get("confidence") or 0.0)
        return (
            confidence >= settings.OCR_FAST_PATH_QUALITY_THRESHOLD
            and text_chars >= settings.OCR_PDF_TEXT_MIN_CHARS
            and text_chars_per_page >= settings.OCR_PDF_TEXT_MIN_CHARS_PER_PAGE
        )

    def _render_page_images(self, file_bytes: bytes, suffix: str) -> list[bytes]:
        """Call MinerU microservice for preprocessing and rendering."""
        try:
            import httpx
            b64_content = base64.b64encode(file_bytes).decode("ascii")
            payload = {
                "document_id": "temp",
                "doc_type": "invoice",
                "content_b64": b64_content,
                "filename": f"temp{suffix}"
            }
            url = f"{str(settings.MINERU_SVC_URL).rstrip('/')}/preprocess"
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                
            images = []
            for page in data.get("pages", []):
                images.append(base64.b64decode(page["image_b64"]))
            if images:
                return images
        except Exception as exc:
            log.warning("MinerU preprocessing failed, falling back to local PyMuPDF", error=str(exc))

        # Fallback to local rendering
        if suffix == ".pdf":
            try:
                import fitz

                images = []
                with fitz.open(stream=file_bytes, filetype="pdf") as pdf:
                    for page in pdf[: settings.OCR_MAX_RENDERED_PAGES]:
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                        images.append(pix.tobytes("png"))
                return images
            except Exception as exc:
                log.warning("PDF rendering failed", error=str(exc))
                return []

        if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}:
            return [file_bytes]

        return []

    def _extract_pdf_text(self, file_bytes: bytes) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            import pdfplumber

            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                pages = pdf.pages
                text = "\n".join((page.extract_text() or "") for page in pages)
            fields = extract_ceisa_fields_from_text(text)
            text_chars = len(re.sub(r"\s+", "", text))
            page_count = len(pages) or 1
            text_chars_per_page = round(text_chars / page_count, 2)
            confidence = 1.0 if text_chars_per_page >= settings.OCR_PDF_TEXT_MIN_CHARS_PER_PAGE else 0.0
            return {
                "fields": fields,
                "text": text,
                "confidence": confidence,
                "overall_confidence": confidence,
                "page_count": page_count,
                "text_chars": text_chars,
                "text_chars_per_page": text_chars_per_page,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        except Exception as exc:
            log.warning("PDF text extraction failed", error=str(exc))
            return {"fields": {}, "text": "", "confidence": 0.0}

    async def _run_paddle(self, page_images: list[bytes]) -> dict[str, Any]:
        if not page_images:
            return {"fields": {}, "text": "", "confidence": 0.0}
        return await asyncio.to_thread(self._run_paddle_sync, page_images)

    def _run_paddle_sync(self, page_images: list[bytes]) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            import httpx
            images_b64 = [base64.b64encode(img).decode("ascii") for img in page_images]
            url = f"{str(settings.PADDLEOCR_SVC_URL).rstrip('/')}/extract"
            
            lines = []
            confidences = []
            
            with httpx.Client(timeout=300.0) as client:
                for img_b64 in images_b64:
                    payload = {
                        "image_b64": img_b64,
                        "doc_type": "bill_of_lading"
                    }
                    response = client.post(url, json=payload)
                    response.raise_for_status()
                    result = response.json()
                    
                    for text_block in result.get("text_blocks_with_bbox", []):
                        text = text_block.get("text", "")
                        conf = text_block.get("confidence", 0.0)
                        if text.strip():
                            lines.append(text)
                            confidences.append(conf)
                
            text = "\n".join(lines)
            confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            return {
                "fields": extract_ceisa_fields_from_text(text),
                "text": text,
                "confidence": confidence,
                "overall_confidence": confidence,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        except Exception as exc:
            log.warning("PaddleOCR HTTP failed", error=str(exc))
            return {"fields": {}, "text": "", "confidence": 0.0, "error": str(exc)}

    async def _run_surya(self, page_images: list[bytes]) -> dict[str, Any]:
        if not page_images:
            return {"fields": {}, "text": "", "confidence": 0.0}
        return await asyncio.to_thread(self._run_surya_sync, page_images)

    def _run_surya_sync(self, page_images: list[bytes]) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            import httpx
            images_b64 = [base64.b64encode(img).decode("ascii") for img in page_images]
            payload = {
                "images_b64": images_b64,
                "languages": ["en", "id"]
            }
            url = f"{str(settings.SURYA_INFERENCE_URL).rstrip('/')}/extract"
            with httpx.Client(timeout=600.0) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()

            # Surya v2 response: text_blocks is list[list[dict]] (per page, per block)
            # Each block has: { text, html, confidence, bbox, polygon, label }
            lines = []
            confidences = []
            text_blocks = result.get("text_blocks", [])
            for page_blocks in text_blocks:
                if isinstance(page_blocks, list):
                    for block in page_blocks:
                        text = block.get("text", "").strip()
                        conf = float(block.get("confidence", 1.0))
                        if text:
                            lines.append(text)
                            confidences.append(conf)
                elif isinstance(page_blocks, dict):
                    # Fallback: old format where text_blocks is flat list of dicts
                    text = page_blocks.get("text", "").strip()
                    conf = float(page_blocks.get("confidence", 1.0))
                    if text:
                        lines.append(text)
                        confidences.append(conf)

            # Also handle legacy flat "text" field
            if not lines and result.get("text"):
                lines = [result["text"]]
                confidences = [result.get("confidence", result.get("overall_confidence", 0.0))]

            text = "\n".join(lines)
            confidence = sum(confidences) / len(confidences) if confidences else 0.0

            return {
                "fields": extract_ceisa_fields_from_text(text),
                "text": text,
                "confidence": round(confidence, 4),
                "overall_confidence": round(confidence, 4),
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        except Exception as exc:
            log.warning("Surya OCR HTTP failed", error=str(exc))
            return {"fields": {}, "text": "", "confidence": 0.0, "error": str(exc)}


    async def _run_azure(self, file_bytes: bytes, mime_type: str) -> dict[str, Any]:
        if not settings.ENABLE_DUAL_OCR:
            return {"fields": {}, "text": "", "confidence": 0.0}
        if not settings.AZURE_DI_ENDPOINT or not settings.AZURE_DI_KEY:
            log.warning("Azure DI not configured; dual OCR is degraded to PaddleOCR only")
            return {
                "fields": {},
                "text": "",
                "confidence": 0.0,
                "engine_status": "not_configured",
            }
        return await asyncio.to_thread(self._run_azure_sync, file_bytes, mime_type)

    def _run_azure_sync(self, file_bytes: bytes, mime_type: str) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            from azure.ai.documentintelligence import DocumentIntelligenceClient
            from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
            from azure.core.credentials import AzureKeyCredential

            client = DocumentIntelligenceClient(
                endpoint=settings.AZURE_DI_ENDPOINT,
                credential=AzureKeyCredential(settings.AZURE_DI_KEY),
            )
            request = AnalyzeDocumentRequest(bytes_source=file_bytes)
            try:
                poller = client.begin_analyze_document(
                    model_id=settings.AZURE_DI_MODEL_ID,
                    body=request,
                    content_type=mime_type,
                )
            except TypeError:
                poller = client.begin_analyze_document(
                    settings.AZURE_DI_MODEL_ID,
                    request,
                    content_type=mime_type,
                )
            result = poller.result()
            text = getattr(result, "content", "") or ""
            fields = extract_ceisa_fields_from_text(text)
            word_confidences = [
                float(getattr(word, "confidence", 0.0))
                for page in getattr(result, "pages", []) or []
                for word in getattr(page, "words", []) or []
                if getattr(word, "confidence", None) is not None
            ]
            confidence = sum(word_confidences) / len(word_confidences) if word_confidences else 0.0
            return {
                "fields": fields,
                "text": text,
                "confidence": round(confidence, 4),
                "overall_confidence": round(confidence, 4),
                "field_confidences": {field: round(confidence, 4) for field in fields},
                "engine_status": "ok",
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        except Exception as exc:
            log.warning("Azure DI failed", error=str(exc))
            return {"fields": {}, "text": "", "confidence": 0.0, "error": str(exc)}

    def _estimate_quality(self, page_images: list[bytes]) -> float:
        if not page_images:
            return 0.0
        try:
            import cv2
            import numpy as np
            from PIL import Image

            scores = []
            for image_bytes in page_images:
                image = Image.open(io.BytesIO(image_bytes)).convert("L")
                arr = np.array(image)
                sharpness = cv2.Laplacian(arr, cv2.CV_64F).var()
                normalized = min(1.0, sharpness / 500.0)
                scores.append(normalized)
            return round(sum(scores) / len(scores), 4)
        except Exception as exc:
            log.warning("Image quality estimation failed", error=str(exc))
            return 0.8


ocr_engine_service = OCREngineService()
