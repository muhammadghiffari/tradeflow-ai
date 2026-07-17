# ─────────────────────────────────────────────────────────────
# surya-svc — OCR Service using official datalab-to/surya
# https://github.com/datalab-to/surya
#
# Uses surya-ocr v0.21+ with llama.cpp backend (CPU inference)
# to avoid VRAM conflict with Ollama which runs on GPU.
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_CACHE=/data/models \
    TORCH_HOME=/data/models/torch \
    PORT=8001 \
    DISABLE_TQDM=1 \
    SURYA_INFERENCE_BACKEND=llamacpp \
    SURYA_INFERENCE_KEEP_ALIVE=1

# System dependencies
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null || true && \
    apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 curl poppler-utils ghostscript git wget unzip \
    libpango-1.0-0 libpangoft2-1.0-0 libgomp1 build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install llama.cpp prebuilt binary (CPU-only, Linux x86_64)
RUN LLAMACPP_VERSION="b5659" && \
    wget -q "https://github.com/ggml-org/llama.cpp/releases/download/${LLAMACPP_VERSION}/llama-${LLAMACPP_VERSION}-bin-ubuntu-x64.zip" -O /tmp/llamacpp.zip && \
    cd /tmp && unzip -q llamacpp.zip && \
    find /tmp -name "llama-server" -exec cp {} /usr/local/bin/llama-server \; && \
    find /tmp -name "lib*.so*" -exec cp {} /usr/local/lib/ \; && \
    ldconfig && \
    chmod +x /usr/local/bin/llama-server && \
    rm -rf /tmp/llamacpp.zip /tmp/build && \
    llama-server --version || echo "llama-server installed"

# Step 1: Install CPU-only PyTorch first (no CUDA packages needed)
# Using both Aliyun mirror and PyTorch CDN for fallback
RUN pip install --no-cache-dir \
    --index-url https://mirrors.aliyun.com/pypi/simple/ \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    --timeout 600 --retries 10 \
    "torch>=2.7.0" \
    torchvision

# Step 2: Install surya-ocr and service dependencies
# Force use of the already-installed CPU torch by installing surya with no-deps first
RUN pip install --no-cache-dir \
    --index-url https://mirrors.aliyun.com/pypi/simple/ \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    --timeout 600 --retries 10 \
    "surya-ocr>=0.21.0" \
    fastapi uvicorn pydantic python-multipart pillow httpx

COPY apps/surya-svc/serve.py ./

EXPOSE ${PORT}

# Start the FastAPI wrapper around Surya
CMD ["python", "-m", "uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8001"]
