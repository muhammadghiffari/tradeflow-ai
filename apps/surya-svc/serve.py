"""
TradeFlow AI — Surya 2 OCR Service (T-024)

Agent A in the 4-agent ensemble. Wraps Surya 2's OCR and layout
detection into a FastAPI HTTP service.

POST /extract → OCR text + layout + HTML for all pages
GET  /health  → {"status": "ok"}

Weights are downloaded at container startup from HuggingFace Hub
via download_models.py (HF_HUB_CACHE=/data/models).
"""
from __future__ import annotations

import base64
import io
import logging
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger("surya-svc")
app = FastAPI(title="Surya 2 OCR Service", version="1.0.0")

_det_model = None
_det_processor = None
_rec_model = None
_rec_processor = None


@app.on_event("startup")
async def load_models() -> None:
    global _det_model, _det_processor, _rec_model, _rec_processor
    logger.info("Loading Surya 2 models from HF cache…")
    from surya.model.detection.model import load_model as load_det
    from surya.model.detection.processor import load_processor as load_det_proc
    from surya.model.recognition.model import load_model as load_rec
    from surya.model.recognition.processor import load_processor as load_rec_proc

    _det_model, _det_processor = load_det(), load_det_proc()
    _rec_model, _rec_processor = load_rec(), load_rec_proc()
    logger.info("Surya 2 models loaded ✓")


class OCRRequest(BaseModel):
    images_b64: list[str]
    doc_type: str = "bill_of_lading"
    languages: list[str] = ["en", "id"]


def _b64_to_pil(b64_str: str):
    from PIL import Image
    data = base64.b64decode(b64_str)
    return Image.open(io.BytesIO(data)).convert("RGB")


def _avg_confidence(predictions: list) -> float:
    confidences = []
    for pred in predictions:
        for line in getattr(pred, "text_lines", []):
            confidences.append(getattr(line, "confidence", 0.0))
    return round(sum(confidences) / max(len(confidences), 1), 3)


@app.post("/extract")
async def extract(request: OCRRequest) -> dict:
    """
    Run Surya 2 OCR + layout detection on the provided page images.
    Returns text blocks, layout bounding boxes, and estimated confidence.
    """
    if _det_model is None:
        raise HTTPException(status_code=503, detail="Models not loaded yet")
    if not request.images_b64:
        raise HTTPException(status_code=400, detail="No images provided")

    try:
        from surya.layout import batch_layout_detection
        from surya.ocr import run_ocr

        images = [_b64_to_pil(b) for b in request.images_b64]
        langs = [request.languages] * len(images)

        # Layout detection
        layout_preds = batch_layout_detection(images, _det_model, _det_processor)

        # OCR
        ocr_preds = run_ocr(
            images, langs,
            _det_model, _det_processor,
            _rec_model, _rec_processor,
        )

        text_blocks = []
        for pred in ocr_preds:
            text_blocks.append([
                {
                    "text": line.text,
                    "confidence": round(line.confidence, 3),
                    "bbox": line.bbox,
                }
                for line in getattr(pred, "text_lines", [])
            ])

        layout_bboxes = []
        for lpred in layout_preds:
            layout_bboxes.append([
                {
                    "label": bbox.label,
                    "bbox": bbox.bbox,
                    "score": round(bbox.score, 3),
                }
                for bbox in getattr(lpred, "bboxes", [])
            ])

        return {
            "text_blocks": text_blocks,
            "layout": layout_bboxes,
            "confidence": _avg_confidence(ocr_preds),
            "page_count": len(images),
        }
    except Exception as e:
        logger.exception(f"Surya extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health() -> JSONResponse:
    loaded = _det_model is not None
    return JSONResponse({"status": "ok" if loaded else "loading", "model": "surya-2"})
