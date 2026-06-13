"""
TradeFlow AI — olmOCR LoRA Adapter Downloader (T-026)

Downloads the fine-tuned CIPL LoRA adapter from HuggingFace Hub
into the shared model_cache volume at container startup.
PRD Invariant #5: Code-only images — weights never baked in.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("olm-inference.download")
logging.basicConfig(level=logging.INFO)

HF_TOKEN = os.environ.get("HF_TOKEN", "")
OLM_BASE_MODEL = os.environ.get("OLM_BASE_MODEL", "allenai/olmOCR-2-7B-1025")
OLM_LORA_ADAPTER = os.environ.get("OLM_LORA_ADAPTER", "your-org/olm-ocr-cipl-v1")
HF_HUB_CACHE = os.environ.get("HF_HUB_CACHE", "/data/models")
ADAPTER_LOCAL_PATH = Path(HF_HUB_CACHE) / "adapters" / "cipl_adapter"


def download_base_model() -> None:
    """Pre-cache the base olmOCR model weights (vLLM will load from cache)."""
    from huggingface_hub import snapshot_download
    model_path = Path(HF_HUB_CACHE) / "models--" + OLM_BASE_MODEL.replace("/", "--")
    if model_path.exists():
        logger.info(f"Base model already cached at {model_path}")
        return
    logger.info(f"Downloading base model {OLM_BASE_MODEL}…")
    snapshot_download(
        repo_id=OLM_BASE_MODEL,
        cache_dir=HF_HUB_CACHE,
        token=HF_TOKEN or None,
        ignore_patterns=["*.msgpack", "flax_model*"],
    )
    logger.info("Base model downloaded ✓")


def download_lora_adapter() -> str:
    """Download the CIPL LoRA adapter. Returns local adapter path."""
    if ADAPTER_LOCAL_PATH.exists() and any(ADAPTER_LOCAL_PATH.iterdir()):
        logger.info(f"LoRA adapter already at {ADAPTER_LOCAL_PATH}")
        return str(ADAPTER_LOCAL_PATH)

    if OLM_LORA_ADAPTER.startswith("your-org/"):
        logger.warning(
            f"OLM_LORA_ADAPTER='{OLM_LORA_ADAPTER}' looks like a placeholder. "
            "Skipping LoRA download. vLLM will run without the adapter."
        )
        return ""

    from huggingface_hub import snapshot_download
    logger.info(f"Downloading LoRA adapter {OLM_LORA_ADAPTER}…")
    ADAPTER_LOCAL_PATH.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=OLM_LORA_ADAPTER,
        local_dir=str(ADAPTER_LOCAL_PATH),
        token=HF_TOKEN or None,
    )
    logger.info(f"LoRA adapter downloaded to {ADAPTER_LOCAL_PATH} ✓")
    return str(ADAPTER_LOCAL_PATH)


if __name__ == "__main__":
    try:
        download_base_model()
        adapter_path = download_lora_adapter()
        # Write adapter path to a temp file so serve.py can read it
        if adapter_path:
            Path("/tmp/adapter_path.txt").write_text(adapter_path)
        logger.info("Download complete — starting vLLM server")
    except Exception as e:
        logger.error(f"Download failed: {e}")
        sys.exit(1)
