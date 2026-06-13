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

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 \
    poppler-utils \
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

COPY serve.py ./

EXPOSE ${PORT}

HEALTHCHECK --interval=20s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD ["uv", "run", "uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8003"]
