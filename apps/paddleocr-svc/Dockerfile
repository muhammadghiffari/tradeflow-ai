# ─────────────────────────────────────────────────────────────
# paddleocr-svc — Agent B + FAST_PATH (PP-StructureV3 + PP-ChatOCRv4)
# CPU-capable. Models downloaded at startup.
# Invariant #5: Code-only image.
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_CACHE=/data/models \
    PORT=8002

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    libpango-1.0-0 libpangoft2-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY apps/api/pyproject.toml apps/api/uv.lock* ./
RUN uv sync --frozen --no-dev

COPY apps/paddleocr-svc/serve.py ./

EXPOSE ${PORT}

CMD ["sh", "-c", "uv run uvicorn serve:app --host 0.0.0.0 --port ${PORT}"]
