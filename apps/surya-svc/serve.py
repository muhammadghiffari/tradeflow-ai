"""
TradeFlow AI — Surya 2 OCR Service (T-024)
Official implementation using datalab-to/surya >= 0.21.0
https://github.com/datalab-to/surya

Architecture:
  - SuryaInferenceManager → wraps llama.cpp backend (CPU) to avoid VRAM
    conflict with Ollama which owns the GPU.
  - LayoutPredictor → detects text blocks + layout elements
  - RecognitionPredictor → runs OCR on each block

POST /extract → { text_blocks, layout, confidence, page_count }
GET  /health  → { status, model }
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
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Surya OCR Service (official)", version="2.0.0")

# Global state
_manager = None
_layout_predictor = None
_rec_predictor = None


@app.on_event("startup")
async def load_models() -> None:
    global _manager, _layout_predictor, _rec_predictor

    # Force CPU-only inference via llama.cpp; Ollama owns the GPU
    os.environ.setdefault("SURYA_INFERENCE_BACKEND", "llamacpp")
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")  # hide GPU from Surya
    os.environ.setdefault("SURYA_INFERENCE_KEEP_ALIVE", "1")  # keep server up

    logger.info("Initializing Surya v2 with llama.cpp backend (CPU)…")
    try:
        from surya.inference import SuryaInferenceManager
        from surya.layout import LayoutPredictor
        from surya.recognition import RecognitionPredictor

        _manager = SuryaInferenceManager()
        _layout_predictor = LayoutPredictor(_manager)
        _rec_predictor = RecognitionPredictor(_manager)

        logger.info("Surya v2 models loaded ✓ (CPU/llama.cpp backend)")
    except Exception as e:
        logger.error(f"Surya startup failed: {e}")
        # Service stays up but returns 503 on /extract


class OCRRequest(BaseModel):
    images_b64: list[str]
    doc_type: str = "bill_of_lading"
    languages: list[str] = ["en", "id"]


def _b64_to_pil(b64_str: str):
    from PIL import Image
    data = base64.b64decode(b64_str)
    return Image.open(io.BytesIO(data)).convert("RGB")


def _resize_if_needed(img, max_dim: int = 2048):
    """Resize large images to prevent OOM."""
    w, h = img.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)))
    return img


@app.post("/extract")
async def extract(request: OCRRequest) -> dict:
    """
    Run Surya v2 layout detection + OCR on the provided page images.
    Returns text blocks with bounding boxes and confidence scores.
    """
    if _rec_predictor is None:
        raise HTTPException(status_code=503, detail="Surya models not loaded — check startup logs")
    if not request.images_b64:
        raise HTTPException(status_code=400, detail="No images provided")

    try:
        images = [_resize_if_needed(_b64_to_pil(b)) for b in request.images_b64]

        # Step 1: Layout detection (identifies blocks: text, table, figure, etc.)
        layout_results = _layout_predictor(images)

        # Step 2: OCR on each block using layout as guide
        ocr_results = _rec_predictor(images, layout_results)

        # Build response
        text_blocks = []
        all_confidences = []

        for page_result in ocr_results:
            page_blocks = []
            for block in getattr(page_result, "blocks", []):
                confidence = getattr(block, "confidence", 1.0) or 1.0
                all_confidences.append(confidence)
                page_blocks.append({
                    "text": getattr(block, "text", "") or "",
                    "html": getattr(block, "html", "") or "",
                    "confidence": round(float(confidence), 3),
                    "bbox": getattr(block, "bbox", None),
                    "polygon": getattr(block, "polygon", None),
                    "label": getattr(block, "label", "text"),
                })
            text_blocks.append(page_blocks)

        # Layout bboxes
        layout_bboxes = []
        for lpred in layout_results:
            page_layout = []
            for bbox in getattr(lpred, "bboxes", []):
                page_layout.append({
                    "label": getattr(bbox, "label", ""),
                    "bbox": getattr(bbox, "bbox", None),
                    "polygon": getattr(bbox, "polygon", None),
                    "score": round(float(getattr(bbox, "score", 1.0)), 3),
                })
            layout_bboxes.append(page_layout)

        avg_confidence = (
            round(sum(all_confidences) / len(all_confidences), 3)
            if all_confidences else 0.0
        )

        return {
            "text_blocks": text_blocks,
            "layout": layout_bboxes,
            "confidence": avg_confidence,
            "page_count": len(images),
        }
    except Exception as e:
        logger.exception(f"Surya extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health() -> JSONResponse:
    loaded = _rec_predictor is not None
    return JSONResponse({
        "status": "ok" if loaded else "loading",
        "model": "surya-ocr-v2-official",
        "backend": os.environ.get("SURYA_INFERENCE_BACKEND", "llamacpp"),
    })
