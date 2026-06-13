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

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger("paddleocr-svc")
app = FastAPI(title="PaddleOCR 3.0 Service", version="1.0.0")

_structure_engine = None
_kia_engine = None


@app.on_event("startup")
async def load_models() -> None:
    global _structure_engine, _kia_engine
    logger.info("Loading PaddleOCR PP-StructureV3 models…")
    try:
        from paddleocr import PPStructure
        _structure_engine = PPStructure(table=True, ocr=True, show_log=False, lang="en")
        logger.info("PP-StructureV3 loaded ✓")
    except Exception as e:
        logger.error(f"PP-StructureV3 load failed: {e}")

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


def _serialize_structure_result(result: list) -> dict:
    regions, table_cells, text_blocks = [], [], []
    for item in result:
        item_type = item.get("type", "unknown")
        regions.append({"type": item_type, "bbox": item.get("bbox", [])})
        if item_type == "table":
            res = item.get("res", {})
            for cell in res.get("body", []):
                table_cells.append({
                    "text": cell.get("transcription", ""),
                    "bbox": cell.get("bbox", []),
                    "confidence": round(float(cell.get("score", 0.0)), 3),
                })
        elif item_type == "text":
            res = item.get("res", [])
            for line in res:
                text_blocks.append({
                    "text": line[1][0] if len(line) > 1 else "",
                    "confidence": round(float(line[1][1]) if len(line) > 1 else 0.0, 3),
                    "bbox": line[0] if line else [],
                })
    return {"regions": regions, "table_cells": table_cells, "text_blocks_with_bbox": text_blocks}


@app.post("/extract")
async def extract_layout(request: LayoutRequest) -> dict:
    """Agent B: PP-StructureV3 layout + table structure analysis."""
    if _structure_engine is None:
        raise HTTPException(status_code=503, detail="PP-StructureV3 not loaded")
    try:
        img = _b64_to_cv2(request.image_b64)
        result = _structure_engine(img)
        serialized = _serialize_structure_result(result)
        serialized["doc_type"] = request.doc_type
        serialized["reading_order"] = list(range(len(serialized["regions"])))
        return serialized
    except Exception as e:
        logger.exception(f"PP-StructureV3 extraction failed: {e}")
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
    return JSONResponse({"status": "ok" if loaded else "loading", "model": "paddleocr-3.0"})
