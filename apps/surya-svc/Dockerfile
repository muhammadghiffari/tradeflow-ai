# ─────────────────────────────────────────────────────────────
# surya-svc — Agent A OCR Service (Surya 2)
# Invariant #5: Code-only image. Weights downloaded at startup
# via HF_HUB_CACHE=/data/models (shared model_cache volume).
# ─────────────────────────────────────────────────────────────
FROM nvidia/cuda:12.3.1-cudnn9-runtime-ubuntu22.04

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_CACHE=/data/models \
    PORT=8001

# System dependencies for Surya 2 (Pillow, poppler, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-dev python3-pip \
    libgl1-mesa-glx libglib2.0-0 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

COPY serve.py ./

EXPOSE ${PORT}

# download_models.py runs at startup to pull weights from HF Hub
CMD ["sh", "-c", "uv run python download_models.py && uv run uvicorn serve:app --host 0.0.0.0 --port ${PORT}"]
