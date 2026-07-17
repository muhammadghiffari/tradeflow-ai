"""
TradeFlow AI — olmOCR-2-7B-CIPL vLLM Server (T-027)

Launches vLLM in OpenAI-compatible mode with the CIPL LoRA adapter.
Agent D in the 4-agent ensemble.

The vLLM server exposes:
  POST /v1/chat/completions   (used by multi_ocr_agent.py)
  GET  /health                (used by docker-compose healthcheck)
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("olm-inference.serve")
logging.basicConfig(level=logging.INFO)

OLM_BASE_MODEL = os.environ.get("OLM_BASE_MODEL", "allenai/olmOCR-2-7B-1025")
HF_HUB_CACHE = os.environ.get("HF_HUB_CACHE", "/data/models")
PORT = os.environ.get("PORT", "8000")

ADAPTER_PATH_FILE = Path("/tmp/adapter_path.txt")


def detect_dtype() -> str:
    """Auto-detect the best dtype for the current GPU.

    T4 GPUs (compute capability 7.5) do NOT support bfloat16.
    Only GPUs with compute capability >= 8.0 (A100, A10G, H100, etc.)
    support bfloat16.
    """
    try:
        import torch
        if torch.cuda.is_available():
            cap = torch.cuda.get_device_capability(0)
            if cap[0] >= 8:
                logger.info(f"GPU compute capability {cap[0]}.{cap[1]} — using bfloat16")
                return "bfloat16"
            else:
                logger.info(f"GPU compute capability {cap[0]}.{cap[1]} — using float16 (T4/V100)")
                return "half"
    except ImportError:
        pass
    # Fallback: float16 is universally supported
    logger.warning("Could not detect GPU capability — defaulting to float16")
    return "half"


def get_adapter_path() -> str | None:
    if ADAPTER_PATH_FILE.exists():
        p = ADAPTER_PATH_FILE.read_text().strip()
        return p if p else None
    return None


def build_vllm_cmd(adapter_path: str | None) -> list[str]:
    dtype = detect_dtype()
    cmd = [
        sys.executable, "-m", "vllm.entrypoints.openai.api_server",
        "--model", OLM_BASE_MODEL,
        "--dtype", dtype,
        "--gpu-memory-utilization", "0.85",
        "--max-model-len", "4096",
        "--port", PORT,
        "--host", "0.0.0.0",
        "--download-dir", HF_HUB_CACHE,
    ]
    if adapter_path and Path(adapter_path).exists():
        cmd += [
            "--enable-lora",
            "--lora-modules", f"cipl_adapter={adapter_path}",
            "--max-lora-rank", "64",
        ]
        logger.info(f"Starting vLLM with LoRA adapter: {adapter_path}")
    else:
        logger.warning("Starting vLLM WITHOUT LoRA adapter (base model only)")

    return cmd


if __name__ == "__main__":
    adapter_path = get_adapter_path()
    cmd = build_vllm_cmd(adapter_path)
    logger.info(f"Launching: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)
