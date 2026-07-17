# ─────────────────────────────────────────────────────────────
# olm-inference — Agent D (olmOCR-2-7B-CIPL via vLLM + LoRA)
# GPU required. Weights + LoRA adapter downloaded at startup.
# Invariant #5: Code-only image.
#
# IMPORTANT: Uses CUDA 12.1 base image for GPU inference.
# python:3.11-slim does NOT include CUDA runtime — vLLM will
# fail to initialize without it.
# ─────────────────────────────────────────────────────────────
FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    HF_HUB_CACHE=/data/models \
    PORT=8000 \
    DEBIAN_FRONTEND=noninteractive

# Install Python 3.11 + system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-venv python3-pip \
    libgl1 libglib2.0-0 curl poppler-utils ghostscript \
    libpango-1.0-0 libpangoft2-1.0-0 libgomp1 \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && ln -sf /usr/bin/python3.11 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies from requirements.txt (pinned versions)
COPY requirements.txt ./
RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

COPY download_adapter.py serve.py ./

EXPOSE ${PORT}

CMD ["sh", "-c", "python download_adapter.py && python serve.py"]
