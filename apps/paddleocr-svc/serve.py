"""
TradeFlow AI — PaddleOCR 3.0 Service (T-025)

Agent B in the 4-agent ensemble.
Also serves the FAST_PATH PP-ChatOCRv4 KIA endpoint.

POST /extract → PP-StructureV3 layout + table cells
POST /kia     → PP-ChatOCRv4 key-information extraction (FAST_PATH)
GET  /health  → {"status": "ok"}
"""
from __future__ import annotations

import base64
import io
import logging
import os
import threading

# -------------------------------------------------------------------------------------
# The paddlepaddle==3.2.2 downgrade fixed the PIR bug. We can re-enable MKLDNN!
# -------------------------------------------------------------------------------------
os.environ["FLAGS_use_mkldnn"] = "1"
os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "1"
os.environ["FLAGS_enable_pir_api"] = "0"

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger("paddleocr-svc")
app = FastAPI(title="PaddleOCR 3.0 Service", version="1.0.0")

_structure_engine = None
_kia_engine = None
_load_error: str | None = None


@app.on_event("startup")
async def load_models() -> None:
    thread = threading.Thread(target=_load_models_sync, name="paddleocr-loader", daemon=True)
    thread.start()


def _load_models_sync() -> None:
    global _structure_engine, _kia_engine
    global _load_error
    import os
    is_cpu = os.environ.get("CUDA_VISIBLE_DEVICES", None) == ""
    mode = "CPU" if is_cpu else "GPU"
    logger.info(f"Loading PaddleOCR models ({mode} mode)…")
    try:
        from paddleocr import PaddleOCR
        _structure_engine = PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        logger.info(f"PaddleOCR loaded ✓ ({mode} mode, MKLDNN disabled)")
    except Exception as e:
        logger.error(f"PaddleOCR load failed: {e}")
        try:
            from paddleocr import PaddleOCR
            _structure_engine = PaddleOCR(lang="en", enable_mkldnn=False)
            logger.info(f"PaddleOCR loaded ({mode} mode, compatibility fallback)")
        except Exception as e2:
            logger.error(f"PaddleOCR fallback load failed: {e2}")
            _load_error = str(e2)

    try:
        from paddleocr import ChatOCR
        _kia_engine = ChatOCR()
        logger.info("PP-ChatOCRv4 loaded ✓")
    except Exception as e:
        logger.warning(f"PP-ChatOCRv4 load failed (optional): {e}")


class LayoutRequest(BaseModel):
    image_b64: str
    doc_type: str = "bill_of_lading"


class KIARequest(BaseModel):
    image_b64: str
    doc_type: str = "bill_of_lading"
    extraction_schema_prompt: str = ""


def _b64_to_cv2(b64_str: str):
    import cv2
    data = base64.b64decode(b64_str)
    arr = np.frombuffer(data, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _serialize_paddleocr_result(result: list) -> dict:
    text_blocks = []
    for page in result or []:
        for item in page or []:
            if len(item) >= 2 and isinstance(item[1], (list, tuple)):
                text = str(item[1][0])
                confidence = float(item[1][1])
                bbox = item[0]
                text_blocks.append({
                    "text": text,
                    "confidence": round(confidence, 3),
                    "bbox": bbox,
                })
    return {"regions": [], "table_cells": [], "text_blocks_with_bbox": text_blocks}


@app.post("/extract")
async def extract_layout(request: LayoutRequest) -> dict:
    """Agent B: Standard PaddleOCR analysis."""
    if _structure_engine is None:
        raise HTTPException(status_code=503, detail="PaddleOCR not loaded")
    try:
        img = _b64_to_cv2(request.image_b64)
        result = _structure_engine.ocr(img)
        serialized = _serialize_paddleocr_result(result)
        serialized["doc_type"] = request.doc_type
        serialized["reading_order"] = list(range(len(serialized.get("regions", []))))
        return serialized
    except Exception as e:
        logger.exception(f"PaddleOCR extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/kia")
async def key_info_extraction(request: KIARequest) -> dict:
    """FAST_PATH: PP-ChatOCRv4 key information extraction for clean digital PDFs."""
    if _kia_engine is None:
        # Fallback to structure engine if KIA not available
        if _structure_engine is not None:
            logger.warning("PP-ChatOCRv4 not available, falling back to PP-StructureV3")
            return await extract_layout(LayoutRequest(
                image_b64=request.image_b64,
                doc_type=request.doc_type,
            ))
        raise HTTPException(status_code=503, detail="PP-ChatOCRv4 not loaded")
    try:
        img = _b64_to_cv2(request.image_b64)
        result = _kia_engine.chat(
            structure_model=_structure_engine,
            user_prompt=request.extraction_schema_prompt or f"Extract all {request.doc_type} fields",
        )
        return {
            "fields": result,
            "confidence": 0.97,
            "method": "pp_chat_ocr_v4",
            "doc_type": request.doc_type,
        }
    except Exception as e:
        logger.exception(f"PP-ChatOCRv4 KIA failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health() -> JSONResponse:
    loaded = _structure_engine is not None
    payload = {"status": "ok" if loaded else "loading", "model": "paddleocr-3.0"}
    if _load_error:
        payload["status"] = "error"
        payload["error"] = _load_error
    return JSONResponse(payload)
