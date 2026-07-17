# ─────────────────────────────────────────────────────────────
# mineru-svc — PDF preprocessing (MinerU 2.5)
# CPU-capable. Handles watermark removal, page classification,
# SCAC detection, image enhancement before OCR.
# Invariant #5: Code-only image.
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_CACHE=/data/models \
    PORT=8003

RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null || true && \
    apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 curl poppler-utils ghostscript \
    libpango-1.0-0 libpangoft2-1.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install -i https://mirrors.aliyun.com/pypi/simple/ --default-timeout=1000 --retries 15 uv

ENV UV_HTTP_TIMEOUT=300
ENV UV_REQUEST_RETRIES=10
RUN uv venv && uv pip install -i https://mirrors.aliyun.com/pypi/simple/ pdf2image fastapi uvicorn pydantic python-multipart pillow opencv-python-headless httpx numpy pdfplumber

COPY apps/mineru-svc/serve.py ./

EXPOSE ${PORT}

HEALTHCHECK --interval=20s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD ["uv", "run", "uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8003"]
