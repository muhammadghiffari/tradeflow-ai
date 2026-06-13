# ─────────────────────────────────────────────────────────────
# olm-inference — Agent D (olmOCR-2-7B-CIPL via vLLM + LoRA)
# GPU required. Weights + LoRA adapter downloaded at startup.
# Invariant #5: Code-only image.
# ─────────────────────────────────────────────────────────────
FROM vllm/vllm-openai:latest

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    HF_HUB_CACHE=/data/models \
    PORT=8000

COPY download_adapter.py serve.py ./

EXPOSE ${PORT}

# Entrypoint: download LoRA adapter then launch vLLM OpenAI-compatible server
CMD ["sh", "-c", "python download_adapter.py && python serve.py"]
