# ─────────────────────────────────────────────────────────────
# paddleocr-svc — Agent B + FAST_PATH (PP-StructureV3 + PP-ChatOCRv4)
# CPU-capable. Models downloaded at startup.
# Invariant #5: Code-only image.
#
# NOTE: paddlepaddle pinned to 3.2.2 — version 3.3.x has a known bug:
#   NotImplementedError: ConvertPirAttribute2RuntimeAttribute not support
#   [pir::ArrayAttribute<pir::DoubleAttribute>] (onednn_instruction.cc:116)
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_CACHE=/data/models \
    PORT=8002 \
    FLAGS_use_mkldnn=1 \
    PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT=1 \
    FLAGS_enable_pir_api=0

RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null || true && \
    apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 curl poppler-utils ghostscript \
    libpango-1.0-0 libpangoft2-1.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Pin paddlepaddle to 3.2.2 (stable, no PIR+oneDNN CPU bug)
RUN pip install --no-cache-dir \
    --index-url https://mirrors.aliyun.com/pypi/simple/ \
    --timeout 600 --retries 10 \
    "paddlepaddle==3.2.2" \
    "paddleocr>=2.9.0" \
    fastapi uvicorn pydantic python-multipart numpy httpx opencv-python-headless

COPY apps/paddleocr-svc/serve.py ./

EXPOSE ${PORT}

CMD ["python", "-m", "uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8002"]
