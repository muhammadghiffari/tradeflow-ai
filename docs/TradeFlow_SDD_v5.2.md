# System Design Document (SDD)
## TradeFlow AI — Predictive Customs Intelligence Platform v5.1
**Document:** SDD-TF-001  
**Status:** Approved for Build  
**Date:** June 2026

---

## 1. Architecture Overview

### 1.1 Monorepo Structure

```
tradeflow-ai/
├── apps/
│   ├── api/                      # FastAPI backend (Uvicorn + Celery)
│   ├── web/                      # Next.js 16 frontend
│   ├── surya-svc/                # Surya 2 via vLLM (Agent A)
│   ├── olm-inference/            # olmOCR-2-7B-CIPL via vLLM (Agent D)
│   ├── paddleocr-svc/            # PaddleOCR 3.0 + PP-ChatOCRv4 (Agent B + fast path)
│   ├── mineru-svc/               # MinerU 2.5 preprocessing
│   └── simulator/                # CEISA 4.0 PIA Simulator
├── packages/
│   ├── agents/                   # LangGraph agent definitions + nodes
│   ├── shared-types/             # Zod schemas (shared Next.js ↔ FastAPI via tRPC)
│   └── db/                       # Migrations, seeds, validation_rules.json
├── contracts/                    # Solidity smart contracts (Hardhat)
├── tools/                        # Synthetic data generator, eval scripts
├── .github/workflows/            # CI/CD
├── docker-compose.yml
├── turbo.json
└── pnpm-workspace.yaml
```

### 1.2 Request Flow (Standard Batch)

```
1. Browser → POST /api/v1/batches (multipart) → FastAPI
2. FastAPI → upload files to Supabase Storage → create batch row → return {batch_id}
3. FastAPI → Celery.delay(process_batch, batch_id)
4. Celery worker → LangGraph.invoke(state, thread_id=batch_id)
5. LangGraph:
   a. PreprocessorAgent → POST http://mineru-svc:8003/preprocess
   b. Fan-out: [SuryaAgent, LayoutAgent, AzureDIAgent, OlmAgent] via asyncio.gather
   c. ReconciliationAgent → merge per-field
   d. VesselValidationAgent → query PostgreSQL maritime tables
   e. ValidationAgent → load rules.json → evaluate CV001-CV011
   f. HSCodeAgent (conditional) → ChromaDB → Gemini reranker
   g. RiskAgent → XGBoost.predict (or fallback heuristics)
   h. BlockchainAgent (parallel branch) → web3.py → Polygon Amoy
   i. LangGraph CHECKPOINT (interrupt_before=["submit"])
   j. → Supabase Realtime CDC → browser (batch.status = REVIEW_READY)
6. Operator reviews → PATCH /api/v1/batches/{id}/fields
7. Operator approves → POST /api/v1/batches/{id}/submit
8. SubmissionAgent → INSW check → PIB build → POST /openapi/document
9. StatusPollerAgent (Celery beat) → GET /openapi/document/status/{aju} every 30s
10. Terminal state → notify → learning outcome recorded
```

---

## 2. Service Specifications

### 2.1 apps/api — FastAPI Backend

**Runtime:** Python 3.13, FastAPI 0.115, Uvicorn 0.34 (4 workers)  
**Package manager:** uv  

#### Directory Layout

```
apps/api/
├── src/
│   ├── main.py                   # FastAPI app factory, lifespan
│   ├── config.py                 # pydantic-settings (ALL env vars — no bare os.getenv)
│   ├── auth/
│   │   ├── keycloak.py           # JWT validation, JWKS fetch + cache
│   │   └── dependencies.py      # FastAPI Depends(get_current_user)
│   ├── routers/
│   │   ├── batches.py            # /api/v1/batches CRUD + submit + stream
│   │   ├── hs_recommend.py       # /api/v1/hs-recommend
│   │   ├── blockchain.py         # /api/v1/blockchain/{id}/verify
│   │   └── vessel.py             # /api/v1/vessel/validate
│   ├── services/
│   │   ├── ceisa_auth.py         # CEISAAuthClient (OAuth 2.0 token manager)
│   │   ├── ceisa_client.py       # H2H submission, status polling
│   │   ├── insw_check_svc.py     # INSW lartas validation
│   │   ├── blockchain_svc.py     # web3.py + Pinata
│   │   ├── notification_svc.py   # Resend + WhatsApp
│   │   └── azure_quota_svc.py    # Azure DI page counter (Redis)
│   ├── tasks/
│   │   ├── celery_app.py         # Celery app factory
│   │   ├── batch_tasks.py        # process_batch, cleanup_expired
│   │   ├── ceisa_poll_tasks.py   # poll_ceisa_status (Celery beat)
│   │   └── learning_tasks.py     # retrain_xgboost, check_model_drift
│   ├── db/
│   │   ├── database.py           # SQLAlchemy async engine + session factory
│   │   └── models.py             # SQLAlchemy ORM models
│   └── schemas/                  # Pydantic request/response models
│       ├── batch.py
│       ├── ceisa.py
│       └── vessel.py
├── Dockerfile
├── pyproject.toml
└── requirements.txt
```

#### Key Pydantic Schemas

```python
# src/schemas/batch.py

class BatchCreateResponse(BaseModel):
    batch_id: UUID
    documents: list[DocumentInfo]
    expires_at: datetime
    langgraph_thread_id: str

class BatchDetailResponse(BaseModel):
    batch_id: UUID
    status: BatchStatus
    aju_number: str | None
    documents: list[DocumentDetail]
    extracted_fields: list[ExtractedFieldDetail]
    validation_results: list[ValidationResultDetail]
    hs_recommendations: list[HSRecommendation]
    crs: CRSDetail
    rejection_prediction: RejectionPrediction
    vessel_validation: VesselValidationDetail
    blockchain: BlockchainDetail
    agent_agreement_rate: float | None

class FieldCorrectionRequest(BaseModel):
    corrections: list[FieldCorrection]

class FieldCorrection(BaseModel):
    field_name: str
    corrected_value: str
    correction_reason: Literal[
        "ocr_error", "outdated_info", "data_entry_error",
        "calculation_error", "hs_code_change", "other"
    ]

class SubmitBatchRequest(BaseModel):
    confirmed: bool = Field(..., description="Must be True to proceed")

    @validator("confirmed")
    def must_be_true(cls, v):
        if not v:
            raise ValueError("confirmed must be True")
        return v
```

#### Config (pydantic-settings)

```python
# src/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "staging", "production"] = "development"
    
    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    
    # Keycloak
    keycloak_url: str
    keycloak_realm: str
    keycloak_client_id: str
    keycloak_client_secret: str
    
    # Redis
    redis_url: str
    celery_broker_url: str
    celery_result_backend: str
    
    # AI services
    surya_inference_url: str = "http://surya-svc:8001"
    olm_inference_url: str = "http://olm-inference:8000"
    paddleocr_svc_url: str = "http://paddleocr-svc:8002"
    mineru_svc_url: str = "http://mineru-svc:8003"
    olm_base_model: str = "allenai/olmOCR-2-7B-1025"
    olm_lora_adapter: str = "your-org/olm-ocr-cipl-v1"
    
    # Azure DI
    azure_di_endpoint: str
    azure_di_key: str
    azure_di_free_limit: int = 5000
    
    # CEISA
    ceisa_base_url: str = "http://ceisa-simulator:8001"
    ceisa_client_id: str
    ceisa_client_secret: str
    ceisa_request_timeout_seconds: int = 30
    ceisa_poll_interval_seconds: int = 30
    
    # Blockchain
    polygon_rpc_url: str = "https://rpc-amoy.polygon.technology"
    contract_address: str
    operator_wallet_private_key: str
    pinata_jwt: str
    enable_blockchain: bool = True
    
    # Feature flags
    enable_surya_agent: bool = True
    enable_azure_di_agent: bool = True
    enable_vessel_validation: bool = True
    enable_maritime_data_features: bool = True
    enable_rejection_prediction: bool = True
    enable_hs_rag: bool = True
    enable_ai_copilot: bool = True
    enable_insw_check: bool = True
    enable_notifications_whatsapp: bool = True
    enable_status_polling: bool = True
    
    # Thresholds
    ocr_reconciliation_disagreement_threshold: float = 0.20
    ocr_fast_path_quality_threshold: float = 0.95
    llm_confidence_review_threshold: float = 0.70
    rejection_risk_block_threshold: float = 0.70
    crs_min_submit_threshold: int = 55
    max_resubmit_attempts: int = 5
    hs_confidence_rag_threshold: float = 0.75
    xgb_min_samples_for_model: int = 500

settings = Settings()
```

### 2.2 packages/agents — LangGraph Agents

#### Directory Layout

```
packages/agents/
├── src/
│   ├── graph.py                  # LangGraph graph definition + compile
│   ├── state.py                  # DeclarationState TypedDict
│   ├── nodes/
│   │   ├── supervisor.py         # Route to sub-graphs
│   │   ├── ingest.py             # DocIngestAgent + TypeClassifierSubAgent
│   │   ├── preprocess.py         # PreprocessorSubAgent (calls mineru-svc)
│   │   ├── multi_ocr_agent.py    # Fan-out: 4 agents via asyncio.gather
│   │   ├── reconciliation_agent.py  # Confidence reconciliation per field
│   │   ├── vessel_validation_agent.py  # VesselValidationAgent
│   │   ├── validation_agent.py   # CrossDocValidator + SchemaValidator
│   │   ├── hs_code_agent.py      # RAG + Gemini reranker
│   │   ├── risk_agent.py         # XGBoost + CRS calculation
│   │   ├── blockchain_agent.py   # Polygon anchor (parallel branch)
│   │   ├── submission_agent.py   # PIB builder + INSW + H2H submit
│   │   ├── status_poller.py      # Celery beat task (polls CEISA)
│   │   └── learning_agent.py     # Outcome recorder + retraining trigger
│   ├── ocr/
│   │   ├── surya_client.py       # HTTP client → surya-svc:8001
│   │   ├── olm_client.py         # HTTP client → olm-inference:8000
│   │   ├── paddleocr_client.py   # HTTP client → paddleocr-svc:8002
│   │   └── azure_di_client.py    # azure-ai-documentintelligence SDK
│   ├── validators/
│   │   ├── rule_engine.py        # Hot-reload validation_rules.json
│   │   ├── field_validators.py   # NPWP checksum, NIB, UN/LOCODE, ISO date
│   │   └── ceisa_schema.py       # PIB JSON schema validator
│   └── utils/
│       ├── normalization.py      # Value normalization for comparison
│       └── pib_builder.py        # Assemble full PIB JSON from state
├── pyproject.toml
└── requirements.txt
```

#### State Definition

```python
# src/state.py
from __future__ import annotations
from typing import Annotated, TypedDict
import operator

class DeclarationState(TypedDict):
    batch_id: str
    tier: str                           # "enterprise" | "sme"
    documents: list[dict]               # [{id, type, storage_path, quality_score}]
    preprocessed: list[dict]            # [{page_images, text_layer, quality_score, route}]
    
    # Multi-agent OCR outputs
    surya_output: list[dict]            # Agent A: {html, tables, key_values, confidence}
    layout_analysis: list[dict]         # Agent B: {regions, table_cells, reading_order, bboxes}
    azure_di_output: list[dict]         # Agent C: {fields, confidence_scores, page_words}
    extraction_results: list[dict]      # Agent D: {fields: {field: {value, confidence}}}
    reconciled_fields: list[dict]       # Merged: {field: ReconciledField}
    
    # Vessel validation
    vessel_validation: dict             # {passed, status, issues, vessel_confirmed, ais_eta}
    
    # Validation
    validation_results: list[dict]      # [{rule_id, severity, passed, error_message}]
    schema_validation: dict             # {valid, errors[]}
    
    # HS recommendations
    hs_recommendations: list[dict]      # per line item: [{hs_code, confidence, duty_rate...}]
    
    # Risk
    rejection_prediction: dict          # {probability, risk_level, top_features}
    crs: dict                           # {score, grade, components}
    
    # HitL
    operator_corrections: list[dict]
    
    # Blockchain
    blockchain_tx: dict                 # {tx_hash, block_number, ipfs_cid, status}
    
    # CEISA
    ceisa_payload: dict                 # Full PIB JSON
    ceisa_aju: str
    ceisa_response: dict
    insw_status: dict                   # {passed, issues[]}
    submission_attempt: int             # current attempt number
    
    # Learning
    learning_feedback: dict
    
    error: str | None
    messages: Annotated[list, operator.add]  # LangGraph message accumulator
```

#### Graph Definition

```python
# src/graph.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.redis import RedisSaver
from .state import DeclarationState
from .nodes import *

def build_graph() -> StateGraph:
    builder = StateGraph(DeclarationState)
    
    # Nodes
    builder.add_node("ingest", ingest_node)
    builder.add_node("preprocess", preprocess_node)
    builder.add_node("multi_ocr", multi_ocr_node)         # fan-out: 4 agents parallel
    builder.add_node("reconcile", reconcile_node)
    builder.add_node("vessel_validate", vessel_validate_node)
    builder.add_node("validate", validate_node)
    builder.add_node("hs_recommend", hs_recommend_node)
    builder.add_node("risk_assess", risk_assess_node)
    builder.add_node("blockchain_anchor", blockchain_anchor_node)  # parallel
    builder.add_node("review_ready", review_ready_node)   # sets status, triggers Realtime
    builder.add_node("build_payload", build_payload_node)
    builder.add_node("insw_check", insw_check_node)
    builder.add_node("submit", submit_node)               # HitL: interrupt_before=["submit"]
    builder.add_node("poll_status", poll_status_node)
    builder.add_node("record_outcome", record_outcome_node)
    
    # Edges
    builder.set_entry_point("ingest")
    builder.add_edge("ingest", "preprocess")
    builder.add_edge("preprocess", "multi_ocr")
    builder.add_edge("multi_ocr", "reconcile")
    builder.add_edge("reconcile", "vessel_validate")
    builder.add_edge("vessel_validate", "validate")
    builder.add_conditional_edges(
        "validate",
        route_after_validation,
        {"hs_needed": "hs_recommend", "skip_hs": "risk_assess"}
    )
    builder.add_edge("hs_recommend", "risk_assess")
    builder.add_edge("risk_assess", "review_ready")
    # Blockchain runs in parallel (send to both blockchain_anchor and review_ready from risk)
    builder.add_edge("review_ready", END)  # graph pauses here — HitL
    
    # Post-approval flow (resumed after operator submit)
    builder.add_edge("build_payload", "insw_check")
    builder.add_conditional_edges(
        "insw_check",
        route_after_insw,
        {"pass": "submit", "fail": "review_ready"}
    )
    builder.add_edge("submit", "poll_status")
    builder.add_conditional_edges(
        "poll_status",
        route_after_ceisa,
        {"terminal": "record_outcome", "pending": "poll_status"}
    )
    builder.add_edge("record_outcome", END)
    
    # Checkpointer: Redis (not in-memory — supports worker restarts)
    memory = RedisSaver.from_conn_string(settings.redis_url)
    return builder.compile(
        checkpointer=memory,
        interrupt_before=["submit"]
    )
```

### 2.3 apps/surya-svc — Surya 2 Inference

```
apps/surya-svc/
├── serve.py                      # FastAPI wrapper around Surya 2
├── Dockerfile
└── requirements.txt              # surya-ocr, fastapi, httpx
```

```python
# serve.py
from fastapi import FastAPI, UploadFile, File
from surya.ocr import run_ocr
from surya.model.detection import load_model as load_det_model
from surya.model.recognition import load_model as load_rec_model
from surya.layout import batch_layout_detection
from surya.postprocessing.heatmap import draw_polys_on_image
import base64, io
from PIL import Image

app = FastAPI(title="Surya 2 OCR Service")

# Load models at startup (cached — not in Docker image)
@app.on_event("startup")
async def load_models():
    app.state.det_model = load_det_model()
    app.state.det_processor = load_det_model.get_processor()
    app.state.rec_model = load_rec_model()
    app.state.rec_processor = load_rec_model.get_processor()

@app.post("/extract")
async def extract(request: OCRRequest):
    """Extract text + layout from document images. Returns HTML + structured data."""
    images = [base64_to_pil(img) for img in request.images_b64]
    
    # Layout detection
    layout_predictions = batch_layout_detection(
        images, app.state.det_model, app.state.det_processor
    )
    
    # OCR
    predictions = run_ocr(
        images,
        [["en", "id"]] * len(images),
        app.state.det_model,
        app.state.det_processor,
        app.state.rec_model,
        app.state.rec_processor
    )
    
    return {
        "text_blocks": [p.text_lines for p in predictions],
        "layout": [l.bboxes for l in layout_predictions],
        "html": render_as_html(predictions, layout_predictions),
        "confidence": compute_avg_confidence(predictions)
    }

@app.get("/health")
async def health():
    return {"status": "ok", "model": "surya-2"}
```

### 2.4 apps/olm-inference — olmOCR-2-7B-CIPL

```
apps/olm-inference/
├── serve.py                      # vLLM server launch + health check
├── download_adapter.py           # Pull LoRA adapter from HuggingFace Hub at startup
├── Dockerfile
└── requirements.txt              # vllm, peft, huggingface_hub, fastapi
```

```python
# serve.py — vLLM OpenAI-compatible server
import subprocess, sys, os

def download_lora_adapter():
    """Pull fine-tuned LoRA adapter from HuggingFace Hub."""
    from huggingface_hub import snapshot_download
    adapter_path = "/data/adapters/cipl_adapter"
    if not os.path.exists(adapter_path):
        snapshot_download(
            repo_id=os.environ["OLM_LORA_ADAPTER"],
            local_dir=adapter_path,
            token=os.environ.get("HF_TOKEN")
        )
    return adapter_path

if __name__ == "__main__":
    adapter_path = download_lora_adapter()
    subprocess.run([
        sys.executable, "-m", "vllm.entrypoints.openai.api_server",
        "--model", os.environ["OLM_BASE_MODEL"],
        "--enable-lora",
        "--lora-modules", f"cipl_adapter={adapter_path}",
        "--dtype", "bfloat16",
        "--gpu-memory-utilization", "0.85",
        "--max-model-len", "4096",
        "--port", "8000",
        "--host", "0.0.0.0"
    ])
```

### 2.5 apps/paddleocr-svc — PaddleOCR 3.0

```python
# apps/paddleocr-svc/serve.py
from fastapi import FastAPI
from paddleocr import PPStructure, PaddleOCR
import numpy as np, cv2, base64

app = FastAPI(title="PaddleOCR 3.0 Service")

@app.on_event("startup")
async def load_models():
    # PP-StructureV3 for layout + table structure (Agent B)
    app.state.structure_engine = PPStructure(table=True, ocr=True, show_log=False, lang="en")
    # PP-ChatOCRv4 for KIE fast path
    from paddleocr import ChatOCR
    app.state.kia_engine = ChatOCR()  # PP-ChatOCRv4

@app.post("/extract")
async def extract_layout(request: LayoutRequest):
    """Agent B: bounding boxes + table cells + reading order."""
    image = b64_to_cv2(request.image_b64)
    result = app.state.structure_engine(image)
    return {
        "regions": serialize_regions(result),
        "table_cells": extract_table_cells(result),
        "reading_order": extract_reading_order(result),
        "text_blocks_with_bbox": extract_text_blocks(result)
    }

@app.post("/kia")
async def key_info_extraction(request: KIARequest):
    """Fast path: PP-ChatOCRv4 for clean digital PDFs."""
    image = b64_to_cv2(request.image_b64)
    result = app.state.kia_engine.chat(
        structure_model=app.state.structure_engine,
        user_prompt=request.extraction_schema_prompt,
        node_name=request.doc_type
    )
    return {"fields": result, "confidence": 0.97, "method": "pp_chat_ocr_v4"}

@app.get("/health")
async def health():
    return {"status": "ok", "model": "paddleocr-3.0"}
```

### 2.6 apps/mineru-svc — MinerU 2.5

```python
# apps/mineru-svc/serve.py
from fastapi import FastAPI, UploadFile
from magic_pdf.data.data_reader_writer import FileBasedDataWriter
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
import io, base64

app = FastAPI(title="MinerU 2.5 Preprocessing Service")

@app.post("/preprocess")
async def preprocess(file: UploadFile):
    """PDF → clean images + text layer detection + quality scoring."""
    pdf_bytes = await file.read()
    
    # Text layer detection via PyMuPDF
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    has_text_layer = any(len(page.get_text("text").strip()) > 50 for page in doc)
    
    # Quality scoring
    images = []
    quality_scores = []
    for page_num, page in enumerate(doc):
        mat = fitz.Matrix(300/72, 300/72)  # 300 DPI
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        images.append(base64.b64encode(img_bytes).decode())
        quality_scores.append(compute_quality_score(pix))
    
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
    
    # Determine processing route
    if has_text_layer and avg_quality >= float(os.environ.get("OCR_FAST_PATH_QUALITY_THRESHOLD", 0.95)):
        route = "FAST_PATH"
    elif avg_quality < 0.50:
        route = "DEGRADED"
    else:
        route = "STANDARD"
    
    # Apply preprocessing if needed
    if route != "FAST_PATH":
        images = [apply_image_preprocessing(b64) for b64 in images]
    
    return {
        "images_b64": images,
        "text_layer": has_text_layer,
        "quality_score": avg_quality,
        "page_quality_scores": quality_scores,
        "processing_route": route,
        "page_count": len(images)
    }
```

---

## 3. Complete Database DDL

```sql
-- ─────────────────────────────────────────────────────────
-- MIGRATION: 20260501_001_init_schema.sql
-- ─────────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Enum types
CREATE TYPE batch_status AS ENUM (
    'uploaded', 'preprocessing', 'ocr_running', 'ocr_complete',
    'vessel_validating', 'validating', 'validated',
    'review_ready', 'reviewing', 'approved',
    'submitting', 'insw_check', 'submitted',
    'ceisa_processing', 'accepted', 'rejected', 'error'
);

CREATE TYPE doc_type AS ENUM ('bill_of_lading', 'packing_list', 'invoice');
CREATE TYPE confidence_level AS ENUM ('HIGH', 'MEDIUM', 'LOW', 'MISSING');
CREATE TYPE risk_level AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');
CREATE TYPE validation_severity AS ENUM ('CRITICAL', 'WARNING', 'INFO');
CREATE TYPE vessel_validation_status AS ENUM ('passed', 'warning', 'info', 'critical');
CREATE TYPE processing_route AS ENUM ('FAST_PATH', 'STANDARD', 'DEGRADED');

-- Profiles
CREATE TABLE profiles (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    keycloak_id TEXT UNIQUE NOT NULL,
    email       TEXT NOT NULL,
    full_name   TEXT,
    role        TEXT NOT NULL DEFAULT 'operator',
    company_id  UUID,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Companies
CREATE TABLE companies (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL,
    npwp                TEXT,
    nib                 TEXT,
    ceisa_company_code  TEXT,              -- registered DJBC company code for AJU
    tier                TEXT DEFAULT 'sme',
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Batches
CREATE TABLE batches (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_by                  UUID REFERENCES profiles(id),
    company_id                  UUID REFERENCES companies(id),
    status                      batch_status DEFAULT 'uploaded',
    customs_readiness_score     DECIMAL(5,2),
    crs_grade                   CHAR(1),
    crs_components              JSONB,
    rejection_probability       DECIMAL(5,4),
    risk_level                  risk_level,
    agent_agreement_rate        DECIMAL(4,3),
    vessel_validation_status    vessel_validation_status,
    vessel_validation_details   JSONB,
    ceisa_aju_number            TEXT UNIQUE,
    ceisa_submission_id         UUID,
    ceisa_reference             TEXT,
    ocr_model_version           TEXT DEFAULT 'olm-ocr-cipl-v1',
    blockchain_tx_hash          TEXT,
    blockchain_block_number     BIGINT,
    ipfs_cid                    TEXT,
    langgraph_thread_id         TEXT UNIQUE,
    expires_at                  TIMESTAMPTZ DEFAULT NOW() + INTERVAL '48 hours',
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_batches_company_status ON batches(company_id, status);
CREATE INDEX idx_batches_status ON batches(status);
ALTER PUBLICATION supabase_realtime ADD TABLE batches;

-- Documents
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id        UUID REFERENCES batches(id) ON DELETE CASCADE,
    doc_type        doc_type NOT NULL,
    original_name   TEXT,
    storage_path    TEXT NOT NULL,
    file_size_bytes BIGINT,
    page_count      INTEGER,
    quality_score   DECIMAL(4,3),
    processing_route processing_route,
    language        TEXT DEFAULT 'en',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_documents_batch ON documents(batch_id);
ALTER PUBLICATION supabase_realtime ADD TABLE documents;

-- Extracted Fields
CREATE TABLE extracted_fields (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id            UUID REFERENCES batches(id) ON DELETE CASCADE,
    document_id         UUID REFERENCES documents(id) ON DELETE CASCADE,
    ceisa_field         TEXT NOT NULL,
    raw_ocr_value       TEXT,
    extracted_value     TEXT,
    normalized_value    TEXT,
    confidence          DECIMAL(4,3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    confidence_level    confidence_level GENERATED ALWAYS AS (
        CASE WHEN confidence >= 0.90 THEN 'HIGH'::confidence_level
             WHEN confidence >= 0.70 THEN 'MEDIUM'::confidence_level
             WHEN confidence > 0     THEN 'LOW'::confidence_level
             ELSE 'MISSING'::confidence_level END
    ) STORED,
    extraction_method   TEXT,
    agent_outputs       JSONB,            -- {"agent_a": v, "agent_b": v, "agent_c": v, "agent_d": v}
    agent_disagreement  BOOLEAN DEFAULT FALSE,
    source_page         INTEGER,
    bounding_box        JSONB,            -- {x, y, w, h} from Agent B
    is_corrected        BOOLEAN DEFAULT FALSE,
    corrected_value     TEXT,
    correction_reason   TEXT,
    corrected_by        UUID REFERENCES profiles(id),
    corrected_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_fields_batch ON extracted_fields(batch_id);
CREATE INDEX idx_fields_ceisa_field ON extracted_fields(batch_id, ceisa_field);
ALTER PUBLICATION supabase_realtime ADD TABLE extracted_fields;

-- Validation Results
CREATE TABLE validation_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id        UUID REFERENCES batches(id) ON DELETE CASCADE,
    rule_id         TEXT NOT NULL,
    severity        validation_severity NOT NULL,
    passed          BOOLEAN NOT NULL,
    error_message   TEXT,
    field_context   JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_validation_batch ON validation_results(batch_id);
ALTER PUBLICATION supabase_realtime ADD TABLE validation_results;

-- HS Code Recommendations
CREATE TABLE hs_recommendations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id        UUID REFERENCES batches(id) ON DELETE CASCADE,
    line_item_seq   INTEGER NOT NULL,
    product_desc    TEXT,
    recommendations JSONB NOT NULL,    -- [{hs_code, description_id, confidence, duty_rate, ...}]
    selected_hs     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- CEISA Submissions
CREATE TABLE ceisa_submissions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id                UUID REFERENCES batches(id),
    aju_number              TEXT NOT NULL UNIQUE,
    idempotency_key         UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    payload_hash            CHAR(64),
    payload_encrypted       BYTEA,
    ceisa_reference         TEXT,
    status                  TEXT DEFAULT 'pending',
    attempt_number          INTEGER DEFAULT 1 CHECK (attempt_number <= 5),
    submitted_at            TIMESTAMPTZ,
    ceisa_responded_at      TIMESTAMPTZ,
    insw_status             TEXT,
    insw_reject_reason      TEXT,
    ceisa_error_code        TEXT,
    ceisa_error_message     TEXT,
    error_classification    TEXT CHECK (error_classification IN (
                                'AUTO_RECOVERABLE', 'OPERATOR_REQUIRED', 'ADMIN_ESCALATION')),
    auto_fixed              BOOLEAN DEFAULT FALSE,
    parent_submission_id    UUID REFERENCES ceisa_submissions(id),
    created_at              TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_submissions_batch ON ceisa_submissions(batch_id);
ALTER PUBLICATION supabase_realtime ADD TABLE ceisa_submissions;

-- Audit Log (IMMUTABLE)
CREATE TABLE audit_log (
    id          BIGSERIAL PRIMARY KEY,
    batch_id    UUID,
    document_id UUID,
    actor_id    UUID,
    actor_type  TEXT CHECK (actor_type IN ('operator','system','ceisa','admin','blockchain')),
    action      TEXT NOT NULL,
    before_state JSONB,
    after_state  JSONB,
    metadata    JSONB,
    ip_address  INET,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "audit_insert_only" ON audit_log FOR INSERT WITH CHECK (true);
REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM PUBLIC;

-- Learning Outcomes
CREATE TABLE learning_outcomes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id    UUID REFERENCES batches(id),
    features    JSONB NOT NULL,          -- 32 XGBoost features snapshot
    label       BOOLEAN,                 -- true=accepted, false=rejected
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Model Drift Alerts
CREATE TABLE model_drift_alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    field_name      TEXT NOT NULL,
    correction_count INTEGER NOT NULL,
    window_days     INTEGER DEFAULT 30,
    alert_sent      BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────
-- MIGRATION: 20260522_004_add_maritime_tables.sql
-- ─────────────────────────────────────────────────────────

CREATE TABLE ais_vessel_positions (
    id              BIGSERIAL PRIMARY KEY,
    vessel_name     TEXT,
    imo             TEXT,
    mmsi            TEXT,
    lat             DECIMAL(10,6),
    lon             DECIMAL(10,6),
    speed           DECIMAL(5,2),
    destination     TEXT,
    eta             TIMESTAMPTZ,
    shiptype        TEXT,
    nav_status      INTEGER,
    recorded_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_ais_imo ON ais_vessel_positions(imo);
CREATE INDEX idx_ais_name ON ais_vessel_positions(LOWER(vessel_name));
CREATE INDEX idx_ais_recorded_at ON ais_vessel_positions(recorded_at DESC);

CREATE TABLE vessel_characteristics (
    id                  BIGSERIAL PRIMARY KEY,
    imo_number          TEXT UNIQUE,
    vessel_name         TEXT,
    call_sign           TEXT,
    vessel_type_code    TEXT,
    subtype_code        TEXT,
    flag_code           TEXT,
    built_year          INTEGER,
    dead_year           INTEGER,
    trading_status      TEXT,
    registered_owner    TEXT,
    raw_data            JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_vc_imo ON vessel_characteristics(imo_number);
CREATE INDEX idx_vc_name ON vessel_characteristics(LOWER(vessel_name));

CREATE TABLE vessel_ownership (
    id                          BIGSERIAL PRIMARY KEY,
    imo_number                  TEXT,
    commercial_owner            TEXT,
    commercial_owner_country    TEXT,
    effective_control           TEXT,
    technical_manager           TEXT,
    financial_owner             TEXT,
    flag                        TEXT,
    created_at                  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_vo_imo ON vessel_ownership(imo_number);

CREATE TABLE port_lineup (
    id              BIGSERIAL PRIMARY KEY,
    imo             TEXT,
    vessel_name     TEXT,
    eta             DATE,
    port_code       TEXT,
    port_name       TEXT,
    unlocode        TEXT,
    country         TEXT,
    activity        TEXT,
    cargo           TEXT,
    quantity        DECIMAL,
    uom             TEXT,
    modified_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_lineup_imo ON port_lineup(imo);
CREATE INDEX idx_lineup_unlocode ON port_lineup(unlocode);
CREATE INDEX idx_lineup_eta ON port_lineup(eta);

-- ─────────────────────────────────────────────────────────
-- MIGRATION: 20260529_005_add_agent_outputs.sql
-- ─────────────────────────────────────────────────────────
-- (already included in base schema above)

-- RLS Policies
ALTER TABLE batches ENABLE ROW LEVEL SECURITY;
CREATE POLICY "company_isolation" ON batches
    USING (company_id = (SELECT company_id FROM profiles WHERE keycloak_id = auth.uid()));

ALTER TABLE extracted_fields ENABLE ROW LEVEL SECURITY;
CREATE POLICY "batch_company_isolation" ON extracted_fields
    USING (batch_id IN (
        SELECT id FROM batches WHERE company_id = (
            SELECT company_id FROM profiles WHERE keycloak_id = auth.uid()
        )
    ));
```

---

## 4. API Design — Full Endpoint Specifications

### 4.1 Internal Pydantic Schemas

```python
# packages/shared-types equivalent in Python (Pydantic)

class ReconciledField(BaseModel):
    value: Any
    confidence: float = Field(ge=0, le=1)
    level: Literal["HIGH", "MEDIUM", "LOW", "MISSING"]
    source: str = "ensemble"   # "ensemble" | "rule" | "fast_path" | "manual"
    agent_disagreement: bool = False
    all_agent_values: dict[str, Any] | None = None  # only when disagreement=True
    flag_reason: str | None = None

class VesselIssue(BaseModel):
    severity: Literal["CRITICAL", "WARNING", "INFO"]
    code: str   # V001, V002, V003, V004
    message: str

class VesselValidationResult(BaseModel):
    passed: bool
    status: Literal["passed", "warning", "info", "critical"]
    issues: list[VesselIssue]
    vessel_confirmed: bool
    ais_eta: datetime | None = None
    lineup_confirmed: bool = False

class PIBPayload(BaseModel):
    """Full CEISA PIB JSON v0.5.7.20 — all fields required before submission."""
    kodeDokumen: str = "20"
    ajuNumber: str
    tglPendaftaran: str       # ISO 8601 date
    tglBl: str
    tglArrival: str
    fob: float
    freight: float
    asuransi: float
    cif: float
    metodePenentuanNilai: str = "1"
    entitas: list[EntitasItem]
    namaKapal: str
    voyageNumber: str
    kodePelabuhanMuat: str
    kodePelabuhanBongkar: str = "IDJBK"
    kodePelabuhanTujuan: str = "IDJBK"
    jumlahKemasan: int
    kodeJenisKemasan: str
    beratBersih: float
    beratKotor: float
    nomorBl: str
    barang: list[BarangItem]

class EntitasItem(BaseModel):
    kodeEntitas: str = "1"
    namaEntitas: str
    alamatEntitas: str
    nibEntitas: str = Field(..., min_length=13, max_length=13, pattern=r"^\d{13}$")
    nomorIdentitas: str    # NPWP
    kodeJenisIdentitas: str = "5"
    kodeJenisApi: str = Field(..., pattern=r"^0[12]$")
    kodeStatus: str = "01"
    seriEntitas: int = 1

class BarangItem(BaseModel):
    seriBarang: int
    uraian: str
    posTarif: str = Field(..., pattern=r"^\d{8}$")
    jumlahSatuan: float
    kodeSatuanBarang: str
    jumlahKemasan: int
    kodeJenisKemasan: str
    barangTarif: list[BarangTarif]
    barangVd: list[BarangVd]
```

### 4.2 REST Endpoints Table

| Method | Path | Handler | Auth | Description |
|---|---|---|---|---|
| POST | `/api/v1/batches` | `batches.create` | operator, sme | Upload documents, create batch |
| GET | `/api/v1/batches` | `batches.list` | operator, sme | List batches for user's company |
| GET | `/api/v1/batches/{id}` | `batches.get` | operator, sme | Full batch detail |
| PATCH | `/api/v1/batches/{id}/fields` | `batches.update_fields` | operator | Operator corrections |
| POST | `/api/v1/batches/{id}/approve` | `batches.approve` | operator | Approve for submission |
| POST | `/api/v1/batches/{id}/submit` | `batches.submit` | operator | Trigger CEISA submission |
| GET | `/api/v1/batches/{id}/ceisa-status` | `batches.ceisa_status` | operator | Poll CEISA status |
| GET | `/api/v1/batches/{id}/stream` | `batches.stream` | operator, sme | SSE: agent progress |
| POST | `/api/v1/hs-recommend` | `hs_recommend.recommend` | operator | HS code recommendation |
| GET | `/api/v1/blockchain/{id}/verify` | `blockchain.verify` | operator | Verify blockchain record |
| GET | `/api/v1/vessel/validate` | `vessel.validate` | operator | Ad-hoc vessel validation |
| GET | `/api/v1/health` | `health.check` | none | Health check |
| GET | `/api/v1/metrics` | `metrics.prometheus` | internal | Prometheus metrics |

---

## 5. Multi-Agent OCR Node Design

### 5.1 multi_ocr_agent.py — Complete Implementation

```python
# packages/agents/src/nodes/multi_ocr_agent.py
import asyncio, httpx, base64
from ..state import DeclarationState
from ...api.src.services.azure_quota_svc import AzureQuotaService

AGENT_TIMEOUT = 20.0  # seconds per agent

async def multi_ocr_node(state: DeclarationState) -> DeclarationState:
    """Run all OCR agents in parallel. Failures don't abort pipeline."""
    results = {
        "surya_output": [],
        "layout_analysis": [],
        "azure_di_output": [],
        "extraction_results": []
    }
    
    for doc in state["preprocessed"]:
        if doc["processing_route"] == "FAST_PATH":
            # Only PP-ChatOCRv4 — skip all heavy agents
            kia_result = await run_pp_chat_ocr(doc)
            results["extraction_results"].append(kia_result)
            continue
        
        # Standard / Degraded: all 4 agents in parallel
        tasks = [
            run_agent_a_surya(doc),
            run_agent_b_paddleocr(doc),
            run_agent_c_azure_di(doc),
            run_agent_d_olm(doc)
        ]
        
        agent_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        surya_out, paddle_out, azure_out, olm_out = agent_results
        
        # Handle failures gracefully
        if isinstance(surya_out, Exception):
            logger.warning(f"Agent A (Surya) failed: {surya_out}")
            surya_out = None
        if isinstance(paddle_out, Exception):
            logger.warning(f"Agent B (PaddleOCR) failed: {paddle_out}")
            paddle_out = None
        if isinstance(azure_out, Exception):
            logger.warning(f"Agent C (Azure DI) failed: {azure_out}")
            azure_out = None
        if isinstance(olm_out, Exception):
            logger.error(f"Agent D (olmOCR) failed: {olm_out}")
            olm_out = None
        
        # Count failures
        failures = sum(1 for x in [surya_out, paddle_out, azure_out, olm_out] if x is None)
        if failures >= 3:
            raise RuntimeError(f"Critical: {failures}/4 OCR agents failed for doc {doc['id']}")
        
        results["surya_output"].append(surya_out)
        results["layout_analysis"].append(paddle_out)
        results["azure_di_output"].append(azure_out)
        results["extraction_results"].append(olm_out)
    
    return {**state, **results}


async def run_agent_a_surya(doc: dict) -> dict:
    async with httpx.AsyncClient(timeout=AGENT_TIMEOUT) as client:
        resp = await client.post(
            f"{settings.surya_inference_url}/extract",
            json={"images_b64": doc["images_b64"], "doc_type": doc["doc_type"]}
        )
        resp.raise_for_status()
        return resp.json()

async def run_agent_b_paddleocr(doc: dict) -> dict:
    async with httpx.AsyncClient(timeout=AGENT_TIMEOUT) as client:
        resp = await client.post(
            f"{settings.paddleocr_svc_url}/extract",
            json={"image_b64": doc["images_b64"][0], "doc_type": doc["doc_type"]}
        )
        resp.raise_for_status()
        return resp.json()

async def run_agent_c_azure_di(doc: dict) -> dict | None:
    if not settings.enable_azure_di_agent:
        return None
    quota = AzureQuotaService()
    if not await quota.check_available(len(doc.get("images_b64", []))):
        logger.warning("Azure DI quota near limit, skipping for this doc")
        return None
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.core.credentials import AzureKeyCredential
    client = DocumentIntelligenceClient(settings.azure_di_endpoint, AzureKeyCredential(settings.azure_di_key))
    model = "prebuilt-invoice" if doc["doc_type"] == "invoice" else "prebuilt-document"
    # Build URL list from Supabase Storage signed URLs
    poller = client.begin_analyze_document(model, {"urlSource": doc["signed_url"]})
    result = poller.result()
    await quota.increment(doc.get("page_count", 1))
    return serialize_azure_result(result)

async def run_agent_d_olm(doc: dict) -> dict:
    """Call olmOCR-2-7B-CIPL via vLLM OpenAI-compatible endpoint."""
    async with httpx.AsyncClient(timeout=AGENT_TIMEOUT) as client:
        messages = build_olm_extraction_prompt(doc)
        resp = await client.post(
            f"{settings.olm_inference_url}/v1/chat/completions",
            json={
                "model": "cipl_adapter",   # LoRA adapter name registered in vLLM
                "messages": messages,
                "temperature": 0.0,
                "max_tokens": 2048
            }
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return parse_olm_json_output(content)
```

### 5.2 reconciliation_agent.py

```python
# packages/agents/src/nodes/reconciliation_agent.py
from collections import Counter
from ..state import DeclarationState
from ..validators.field_validators import (
    validate_npwp_checksum, validate_nib_format,
    validate_hs_8digit, validate_unlocode, validate_iso_date, validate_iso_4217
)
from ..utils.normalization import normalize_value

RULE_VALIDATED_FIELDS = {
    "buyer_npwp": validate_npwp_checksum,
    "buyer_nib": validate_nib_format,
    "hs_code": validate_hs_8digit,
    "port_loading_code": validate_unlocode,
    "port_discharge_code": validate_unlocode,
    "bl_date": validate_iso_date,
    "invoice_date": validate_iso_date,
    "currency": validate_iso_4217,
}

async def reconcile_node(state: DeclarationState) -> DeclarationState:
    reconciled_per_doc = []
    
    for idx, doc in enumerate(state["preprocessed"]):
        agent_outputs = {
            "agent_a": extract_fields_from_surya(state["surya_output"][idx], doc["doc_type"]),
            "agent_b": extract_fields_from_paddle(state["layout_analysis"][idx], doc["doc_type"]),
            "agent_c": extract_fields_from_azure(state["azure_di_output"][idx], doc["doc_type"]),
            "agent_d": state["extraction_results"][idx],
        }
        # Remove None agents
        agent_outputs = {k: v for k, v in agent_outputs.items() if v is not None}
        
        reconciled = reconcile_all_fields(agent_outputs, doc["doc_type"])
        reconciled_per_doc.append(reconciled)
    
    # Compute agreement rate
    all_fields = [f for doc_fields in reconciled_per_doc for f in doc_fields.values()]
    agreement_rate = sum(1 for f in all_fields if not f.agent_disagreement) / max(len(all_fields), 1)
    
    return {
        **state,
        "reconciled_fields": reconciled_per_doc,
        # Store agreement rate — will be saved to batches table
        "messages": state["messages"] + [{"agent_agreement_rate": agreement_rate}]
    }

def reconcile_all_fields(agent_outputs: dict, doc_type: str) -> dict:
    field_names = get_ceisa_fields_for_doc_type(doc_type)
    reconciled = {}
    for field in field_names:
        values = {
            agent: out.get("fields", {}).get(field, {}).get("value")
            for agent, out in agent_outputs.items()
        }
        values = {k: v for k, v in values.items() if v is not None}
        reconciled[field] = reconcile_single_field(field, values)
    return reconciled

def reconcile_single_field(field: str, values: dict) -> dict:
    if not values:
        return {"value": None, "confidence": 0.0, "level": "MISSING",
                "agent_disagreement": False, "source": "ensemble"}
    
    # Rule-validated fields
    if field in RULE_VALIDATED_FIELDS:
        validator = RULE_VALIDATED_FIELDS[field]
        for val in values.values():
            if val and validator(val):
                return {"value": val, "confidence": 0.98, "level": "HIGH",
                        "source": "rule", "agent_disagreement": False}
        return {"value": list(values.values())[0], "confidence": 0.40,
                "level": "LOW", "agent_disagreement": True,
                "flag_reason": "No agent produced valid value for rule-validated field",
                "all_agent_values": values}
    
    # Majority vote
    normalized = {a: normalize_value(v) for a, v in values.items()}
    vote_counts = Counter(normalized.values())
    top_value, top_count = vote_counts.most_common(1)[0]
    
    if top_count >= 3:
        return {"value": top_value, "confidence": 0.94, "level": "HIGH",
                "agent_disagreement": False, "source": "ensemble"}
    
    if top_count == 2:
        agreeing = [a for a, v in normalized.items() if v == top_value]
        conf = 0.85 if "agent_d" in agreeing else 0.78
        return {"value": top_value, "confidence": conf, "level": "MEDIUM",
                "agent_disagreement": False, "source": "ensemble"}
    
    # All disagree
    fallback = normalized.get("agent_d", list(normalized.values())[0])
    return {"value": fallback, "confidence": 0.55, "level": "LOW",
            "agent_disagreement": True, "all_agent_values": values, "source": "ensemble"}
```

---

## 6. Security Architecture

### 6.1 Authentication Flow

```
Browser
  │ GET /login
  ↓
Next.js → next-auth → redirect to Keycloak /auth (PKCE)
  │
Keycloak authenticates user → redirects back with code
  │
next-auth exchanges code → RS256 JWT (sub, realm_access.roles, company_id)
  │
Browser stores session in httpOnly cookie (next-auth default)
  │
API calls: next-auth session → extract JWT → forward as Authorization: Bearer
  │
FastAPI: python-jose validates JWT signature against Keycloak JWKS
JWKS URL: {KEYCLOAK_URL}/auth/realms/{REALM}/protocol/openid-connect/certs
  │
Supabase: JWT passed → RLS evaluates company_id claim
```

### 6.2 Data Encryption

```python
# Encrypt PIB payload before DB storage
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os, base64

def encrypt_payload(payload_json: str) -> bytes:
    key = base64.b64decode(settings.document_encryption_key)  # 32 bytes
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, payload_json.encode(), None)
    return nonce + ciphertext  # prepend nonce for decryption

def decrypt_payload(encrypted: bytes) -> str:
    key = base64.b64decode(settings.document_encryption_key)
    aesgcm = AESGCM(key)
    nonce, ciphertext = encrypted[:12], encrypted[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode()
```

---

## 7. Frontend Architecture (Next.js 16)

### 7.1 Directory Layout

```
apps/web/
├── src/
│   ├── app/
│   │   ├── (auth)/login/page.tsx
│   │   ├── (dashboard)/
│   │   │   ├── batches/
│   │   │   │   ├── new/page.tsx             # Upload wizard
│   │   │   │   ├── [id]/page.tsx            # Batch detail
│   │   │   │   ├── [id]/review/page.tsx     # Operator review
│   │   │   │   └── [id]/status/page.tsx     # Submission status
│   │   │   ├── analytics/page.tsx
│   │   │   ├── simulator/page.tsx           # Admin: simulator control
│   │   │   └── blockchain/page.tsx
│   │   └── api/auth/[...nextauth]/route.ts  # next-auth route handler
│   ├── components/
│   │   ├── review/
│   │   │   ├── DocumentViewer.tsx           # PDF.js + bbox canvas overlay
│   │   │   ├── FieldsPanel.tsx             # All extracted fields
│   │   │   ├── FieldRow.tsx               # Single field: badge + edit + tooltip
│   │   │   ├── LineItemsGrid.tsx          # TanStack Table for line items
│   │   │   ├── HSCodeWizard.tsx           # Inline HS recommendation
│   │   │   ├── CRSWidget.tsx              # Live CRS gauge
│   │   │   ├── RejectionRiskWidget.tsx
│   │   │   ├── VesselValidationWidget.tsx  # NEW
│   │   │   ├── BlockchainStatusWidget.tsx
│   │   │   ├── INSWStatusWidget.tsx
│   │   │   ├── AICopilotPanel.tsx
│   │   │   └── PreSubmitChecklist.tsx
│   │   ├── wizard/
│   │   │   ├── UploadStep.tsx
│   │   │   ├── ReviewStep.tsx (simplified)
│   │   │   └── ConfirmStep.tsx
│   │   └── shared/
│   │       ├── ConfidenceBadge.tsx
│   │       ├── AgentDisagreementTooltip.tsx
│   │       └── StatusTimeline.tsx
│   ├── lib/
│   │   ├── supabase.ts                    # Supabase client (Realtime)
│   │   ├── socket.ts                      # Socket.io client
│   │   └── api.ts                         # tRPC or fetch wrapper
│   └── hooks/
│       ├── useBatchRealtime.ts            # Supabase Realtime subscription
│       ├── useAgentStream.ts              # Socket.io streaming
│       └── useCRSCalculation.ts           # Client-side CRS live update
├── Dockerfile
└── package.json
```

### 7.2 Real-time Subscription Pattern

```typescript
// hooks/useBatchRealtime.ts
import { createClient } from '@supabase/supabase-js'
import { useEffect, useState } from 'react'

export function useBatchRealtime(batchId: string) {
  const [batch, setBatch] = useState(null)
  const supabase = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, 
                                process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!)
  
  useEffect(() => {
    // Initial fetch
    supabase.from('batches').select('*').eq('id', batchId).single()
      .then(({ data }) => setBatch(data))
    
    // Realtime subscription
    const channel = supabase
      .channel(`batch:${batchId}`)
      .on('postgres_changes', {
        event: 'UPDATE', schema: 'public', table: 'batches',
        filter: `id=eq.${batchId}`
      }, (payload) => setBatch(payload.new))
      .on('postgres_changes', {
        event: 'INSERT', schema: 'public', table: 'extracted_fields',
        filter: `batch_id=eq.${batchId}`
      }, (payload) => updateFields(payload.new))
      .subscribe()
    
    return () => { supabase.removeChannel(channel) }
  }, [batchId])
  
  return batch
}
```

---

## 8. Docker Compose (Complete)

```yaml
# docker-compose.yml
version: "3.9"

x-model-cache: &model-cache
  volumes:
    - model_cache:/data/models       # shared model cache — weights downloaded once
  environment:
    - HF_HUB_CACHE=/data/models
    - HF_TOKEN=${HF_TOKEN}

services:
  # ─── Supabase local stack ───────────────────────────────
  supabase-db:
    image: supabase/postgres:15.1.1.78
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: postgres
    ports: ["5432:5432"]
    volumes:
      - supabase_data:/var/lib/postgresql/data
      - ./packages/db/migrations:/docker-entrypoint-initdb.d

  supabase-realtime:
    image: supabase/realtime:v2.28.32
    depends_on: [supabase-db]
    environment:
      DB_HOST: supabase-db
      DB_PASSWORD: ${POSTGRES_PASSWORD}

  supabase-storage:
    image: supabase/storage-api:v0.46.4
    depends_on: [supabase-db]

  supabase-kong:
    image: kong:2.8.1
    depends_on: [supabase-db]
    # Internal routing only — never exposed externally

  # ─── Auth ────────────────────────────────────────────────
  keycloak:
    image: quay.io/keycloak/keycloak:26.1
    command: start-dev --import-realm
    environment:
      KEYCLOAK_ADMIN: admin
      KEYCLOAK_ADMIN_PASSWORD: ${KEYCLOAK_ADMIN_PASSWORD}
    ports: ["8080:8080"]
    volumes:
      - ./infra/keycloak/realm-export.json:/opt/keycloak/data/import/realm.json

  # ─── Queue + cache ────────────────────────────────────────
  redis:
    image: redis/redis-stack:8.0.0-M03
    ports: ["6379:6379"]
    volumes:
      - redis_data:/data

  # ─── API ─────────────────────────────────────────────────
  api:
    build:
      context: ./apps/api
      dockerfile: Dockerfile
    environment:
      - APP_ENV=development
      - DATABASE_URL=postgresql+asyncpg://postgres:${POSTGRES_PASSWORD}@supabase-db/postgres
    env_file: .env
    depends_on: [supabase-db, redis, keycloak]
    ports: ["8000:8000"]
    command: uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

  worker:
    build:
      context: ./apps/api
      dockerfile: Dockerfile
    env_file: .env
    depends_on: [supabase-db, redis]
    command: celery -A src.tasks.celery_app worker -l info -Q celery,high_priority -c 4

  worker-beat:
    build:
      context: ./apps/api
      dockerfile: Dockerfile
    env_file: .env
    depends_on: [redis]
    command: celery -A src.tasks.celery_app beat -l info --scheduler celery.beat.PersistentScheduler

  langgraph:
    build:
      context: ./packages/agents
      dockerfile: Dockerfile
    env_file: .env
    depends_on: [redis, supabase-db]

  # ─── AI Inference Services ────────────────────────────────
  surya-svc:
    build:
      context: ./apps/surya-svc
      dockerfile: Dockerfile
    <<: *model-cache
    ports: ["8001:8001"]
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      - PORT=8001

  olm-inference:
    build:
      context: ./apps/olm-inference
      dockerfile: Dockerfile
    <<: *model-cache
    ports: ["8002:8000"]
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      - OLM_BASE_MODEL=allenai/olmOCR-2-7B-1025
      - OLM_LORA_ADAPTER=${OLM_LORA_ADAPTER}
      - PORT=8000

  paddleocr-svc:
    build:
      context: ./apps/paddleocr-svc
      dockerfile: Dockerfile
    <<: *model-cache
    ports: ["8003:8002"]
    environment:
      - PORT=8002
    # PaddleOCR 3.0 can run on CPU for layout analysis; GPU preferred
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  mineru-svc:
    build:
      context: ./apps/mineru-svc
      dockerfile: Dockerfile
    ports: ["8004:8003"]
    environment:
      - PORT=8003
      - OCR_FAST_PATH_QUALITY_THRESHOLD=0.95
    # MinerU runs on CPU

  # ─── Vector DB + Object Storage ──────────────────────────
  chromadb:
    image: chromadb/chroma:0.6.0
    ports: ["8005:8000"]
    volumes:
      - chroma_data:/chroma/.chroma

  minio:
    image: minio/minio:RELEASE.2025-01-20T22-07-31Z
    command: server /data --console-address ":9001"
    ports: ["9000:9000", "9001:9001"]
    environment:
      - MINIO_ROOT_USER=${MINIO_ROOT_USER}
      - MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}
    volumes:
      - minio_data:/data

  # ─── Simulator ───────────────────────────────────────────
  ceisa-simulator:
    build:
      context: ./apps/simulator
      dockerfile: Dockerfile
    ports: ["8006:8001"]
    environment:
      - PORT=8001
      - INITIAL_SCENARIO=S06

  # ─── Frontend ────────────────────────────────────────────
  web:
    build:
      context: ./apps/web
      dockerfile: Dockerfile
    ports: ["3000:3000"]
    env_file: .env.local
    depends_on: [api]

  # ─── Proxy ───────────────────────────────────────────────
  traefik:
    image: traefik:v3.2
    command:
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
    ports: ["80:80", "443:443"]
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./infra/traefik/traefik.yml:/etc/traefik/traefik.yml

volumes:
  supabase_data:
  redis_data:
  chroma_data:
  minio_data:
  model_cache:    # SHARED across all inference services — weights downloaded once
```

---

## 9. Deployment Architecture (Production — Railway)

```
Railway Project: tradeflow-ai
├── Service: api          (Dockerfile: apps/api, 2 vCPU, 4 GB RAM)
├── Service: worker       (Dockerfile: apps/api, CMD=celery worker, 2 vCPU, 4 GB)
├── Service: worker-beat  (Dockerfile: apps/api, CMD=celery beat, 0.5 vCPU, 512 MB)
├── Service: surya-svc    (Dockerfile: apps/surya-svc, GPU T4 instance)
├── Service: olm-inference (Dockerfile: apps/olm-inference, GPU T4 instance)
├── Service: paddleocr-svc (Dockerfile: apps/paddleocr-svc, 2 vCPU, 4 GB)
├── Service: mineru-svc   (Dockerfile: apps/mineru-svc, 1 vCPU, 2 GB)
├── Service: simulator    (Dockerfile: apps/simulator, 0.5 vCPU, 512 MB)
├── Service: chromadb     (chromadb/chroma:0.6.0, 1 vCPU, 2 GB)
├── Service: redis        (redis/redis-stack:8.0, 1 vCPU, 2 GB, persistent volume)
├── Service: keycloak     (quay.io/keycloak/keycloak:26.1, 1 vCPU, 2 GB)
└── Plugin: PostgreSQL    (Supabase-hosted or Railway Postgres)

Vercel Project: tradeflow-web
└── apps/web (Next.js 16, Edge Runtime)

Model weights: HuggingFace Hub
├── allenai/olmOCR-2-7B-1025 (base)
└── your-org/olm-ocr-cipl-v1 (LoRA adapter)

Secrets: Doppler (synced to Railway environment)
Container Registry: ghcr.io/{org}/tradeflow-ai/*
```

---

## AMENDMENT v5.2 — Carrier-Specific Implementation
**Date:** June 2026 | **Basis:** 8 real filled B/L documents analyzed

---

## 10. Carrier Profiles System (NEW — v5.2)

### 10.1 carrier_profiles.json

```json
{
  "version": "1.0",
  "profiles": {
    "HLCU": {
      "carrier_name": "Hapag-Lloyd Aktiengesellschaft",
      "layout": "two_column_split",
      "bl_number_pattern": "^HLCU[A-Z0-9]{12,15}$",
      "bl_number_position": "right_header",
      "date_formats": ["DD/MON/YYYY", "MON-DD-YYYY"],
      "watermarks": ["DRAFT", "ORIGINAL"],
      "container_format": "space_separated",
      "hs_code_in_bl": false,
      "typical_pages": [1, 2],
      "page_types": {
        "1": "MAIN",
        "2": "ATTACHMENT_OR_MAIN",
        "3": "DEMURRAGE_SCHEDULE"
      },
      "field_labels": {
        "nomorBl": ["B/L-No.", "B/L No."],
        "namaKapal": ["Vessel(s)"],
        "voyageNumber": ["Voyage-No."],
        "kodePelabuhanMuat": ["Port of Loading"],
        "kodePelabuhanBongkar": ["Port of Discharge"],
        "namaShipper": ["Shipper:"],
        "namaKonsignee": ["Consignee"],
        "beratKotor": ["Gross Weight:"],
        "measurement_cbm": ["Measurement:"],
        "tglBl": ["Place and date of issue:"],
        "num_original_bl": ["Number of original Bs/L:"]
      }
    },
    "MSCU": {
      "carrier_name": "MSC Mediterranean Shipping Company S.A.",
      "layout": "standard_grid",
      "bl_number_pattern": "^MSC[A-Z0-9]+$",
      "bl_number_position": "bottom_left",
      "date_formats": ["DD/MM/YYYY"],
      "watermarks": ["ORIGINAL"],
      "container_format": "no_space",
      "hs_code_in_bl": false,
      "typical_pages": [1],
      "page_types": {"1": "MAIN"},
      "field_labels": {
        "nomorBl": ["BILL OF LADING No."],
        "namaKapal": ["VESSEL & VOYAGE NO."],
        "kodePelabuhanMuat": ["PORT OF LOADING"],
        "kodePelabuhanBongkar": ["PORT OF DISCHARGE"],
        "namaShipper": ["SHIPPER:"],
        "namaKonsignee": ["CONSIGNEE:"],
        "tglBl": ["PLACE AND DATE OF ISSUE"],
        "tglShippedOnBoard": ["SHIPPED ON BOARD DATE"]
      }
    },
    "MAEU": {
      "carrier_name": "Maersk Line A/S",
      "layout": "structured_table",
      "bl_number_pattern": "^MAEU-[A-Z]{2}-\\d+$",
      "bl_number_position": "top_right",
      "date_formats": ["DD-MM-YYYY"],
      "watermarks": ["ORIGINAL"],
      "container_format": "no_space",
      "hs_code_in_bl": false,
      "typical_pages": [1],
      "page_types": {"1": "MAIN"},
      "weight_thousand_separator": true,
      "field_labels": {
        "nomorBl": ["B/L No."],
        "namaKapal": ["Vessel"],
        "voyageNumber": ["Voyage No."],
        "kodePelabuhanMuat": ["Port of Loading"],
        "kodePelabuhanBongkar": ["Port of Discharge"],
        "namaShipper": ["Shipper"],
        "namaKonsignee": ["Consignee"],
        "beratKotor": ["Weight"],
        "measurement_cbm": ["Measurement"],
        "tglBl": ["Date of issue of BL"],
        "tglShippedOnBoard": ["Shipped on Board Date"]
      }
    },
    "EGLV": {
      "carrier_name": "Evergreen Line",
      "layout": "numbered_fields",
      "bl_number_pattern": "^EGLV\\d{12,16}$",
      "bl_number_position": "field_25",
      "date_formats": ["MON.DD,YYYY", "DD.MM.YYYY", "DD.MM.YYYY"],
      "watermarks": ["ORIGINAL", "PROOFREAD", "READ"],
      "container_format": "no_space",
      "hs_code_in_bl": true,
      "hs_location": "description_field",
      "typical_pages": [1, 2],
      "page_types": {
        "1": "MAIN",
        "2": "ATTACHMENT"
      },
      "weight_unit": "MTS",
      "field_numbers": {
        "2": "namaShipper",
        "3": "namaKonsignee",
        "4": "notify_party",
        "5": "nomorBl",
        "12": "pre_carriage",
        "13": "place_of_receipt",
        "14": "namaKapal",
        "15": "kodePelabuhanMuat",
        "16": "kodePelabuhanBongkar",
        "17": "place_of_delivery",
        "18": "container_and_seal",
        "19": "quantity_packages",
        "20": "description_goods",
        "21": "measurement_and_weight",
        "22": "total_containers",
        "25": "nomorBl",
        "26": "service_type",
        "27": "num_original_bl",
        "28": "place_date_issue",
        "33": "laden_on_board"
      }
    },
    "CSLU": {
      "carrier_name": "Cordelia Container Shipping Line",
      "layout": "numbered_fields",
      "bl_number_pattern": "^CSX\\d{2}[A-Z]{3,6}\\d+$",
      "bl_number_position": "top_right",
      "date_formats": ["DD-MON-YYYY"],
      "watermarks": ["DRAFT", "ORIGINAL"],
      "container_format": "no_space",
      "hs_code_in_bl": true,
      "hs_location": "description_field",
      "typical_pages": [1, 2],
      "page_types": {
        "1": "MAIN",
        "2": "TERMS_AND_CONDITIONS"
      },
      "tc_detection_signal": "1. DEFINITIONS",
      "field_labels": {
        "nomorBl": ["B/L No :"],
        "namaKapal": ["Vessel & Voyage"],
        "kodePelabuhanMuat": ["Port of Loading"],
        "kodePelabuhanBongkar": ["Port of Discharge"],
        "tglBl": ["Date of Issue"],
        "num_original_bl": ["No.of Original Bills of Lading"]
      }
    }
  }
}
```

### 10.2 Watermark Removal Implementation

```python
# packages/agents/src/preprocessing/watermark_remover.py
import cv2
import numpy as np
from PIL import Image

WATERMARK_PATTERNS = {
    "DRAFT":     {"color_range": [(180, 180, 180), (240, 240, 255)], "min_area": 5000},
    "ORIGINAL":  {"color_range": [(180, 190, 180), (235, 255, 235)], "min_area": 3000},
    "PROOFREAD": {"color_range": [(180, 180, 200), (230, 230, 255)], "min_area": 3000},
    "READ":      {"color_range": [(180, 180, 200), (230, 230, 255)], "min_area": 2000},
}

def remove_watermarks(image: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """
    Detect and remove carrier watermarks via inpainting.
    Returns cleaned image + list of detected watermark types.
    """
    detected = []
    mask = np.zeros(image.shape[:2], dtype=np.uint8)

    # Convert to HSV for better color range detection
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    for wm_type, params in WATERMARK_PATTERNS.items():
        lo = np.array([0, 0, params["color_range"][0][0]], dtype=np.uint8)
        hi = np.array([180, 40, params["color_range"][1][0]], dtype=np.uint8)
        candidate_mask = cv2.inRange(hsv, lo, hi)

        # Keep only regions large enough to be a watermark
        contours, _ = cv2.findContours(candidate_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            if cv2.contourArea(c) >= params["min_area"]:
                cv2.drawContours(mask, [c], -1, 255, -1)
                detected.append(wm_type)

    if detected:
        # cv2.inpaint reconstructs covered regions from surroundings
        cleaned = cv2.inpaint(image, mask, inpaintRadius=7, flags=cv2.INPAINT_TELEA)
        return cleaned, list(set(detected))
    
    return image, []


def detect_page_type(text: str, page_num: int, carrier_scac: str) -> str:
    """Classify page type based on content signals."""
    text_upper = text.upper().strip()

    # T&C detection (Cordelia pattern)
    if any(text_upper.startswith(s) for s in ["1. DEFINITIONS", "DEFINITIONS\n", "1\nDEFINITIONS"]):
        return "TERMS_AND_CONDITIONS"

    # Demurrage schedule (Hapag pattern)
    demurrage_signals = ["DEMURRAGE CLAUSE", "SSHINC", "USD/TEU/DAY", "DETENTION PERIOD"]
    if sum(1 for s in demurrage_signals if s in text_upper) >= 2:
        return "DEMURRAGE_SCHEDULE"

    # Attachment page (Evergreen pattern — container list continuation)
    if "ATTACHED LIST PAGE" in text_upper or (
        page_num > 1 and bool(__import__("re").search(r"[A-Z]{4}\d{7}", text)) and
        len(text_upper) < 2000
    ):
        return "ATTACHMENT"

    return "MAIN"
```

### 10.3 Field Normalization Implementations

```python
# packages/agents/src/validators/field_normalizers.py
import re
from datetime import datetime

# ── Container Number ────────────────────────────────────────────────────────

def normalize_container_number(raw: str) -> str | None:
    """ISO 6346: 4 alpha owner code + 6 digits + 1 check digit = XXXX1234567"""
    if not raw:
        return None
    cleaned = re.sub(r'[^A-Z0-9]', '', raw.upper())
    match = re.match(r'^([A-Z]{4})(\d{7})$', cleaned)
    if match:
        return match.group(1) + match.group(2)
    # Try with space: "HLXU 2382861"
    match2 = re.match(r'^([A-Z]{4})\s+(\d{7})$', raw.upper())
    if match2:
        return match2.group(1) + match2.group(2)
    return None

def validate_iso6346_check_digit(container_no: str) -> bool:
    """Validate ISO 6346 check digit (modulo 11)."""
    if not container_no or len(container_no) != 11:
        return False
    ALPHA = {c: i+10 for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}
    ALPHA.update({'A':10,'B':12,'C':13,'D':14,'E':15,'F':16,'G':17,'H':18,
                  'I':19,'J':20,'K':21,'L':23,'M':24,'N':25,'O':26,'P':27,
                  'Q':28,'R':29,'S':30,'T':31,'U':32,'V':34,'W':35,'X':36,
                  'Y':37,'Z':38})
    try:
        total = sum(
            (ALPHA.get(c, int(c)) * (2 ** i))
            for i, c in enumerate(container_no[:10])
        )
        check = total % 11
        check = 0 if check == 10 else check
        return check == int(container_no[10])
    except (ValueError, KeyError):
        return False


# ── HS Code ─────────────────────────────────────────────────────────────────

def normalize_hs_code(raw: str) -> list[str]:
    """
    Handle all HS code formats found in real carrier documents.
    Returns list of 8-digit normalized codes.
    """
    if not raw:
        return []
    results = []
    # Split on comma or semicolon for multiple codes
    for part in re.split(r'[,;]', raw):
        part = part.strip()
        # Remove dots: 8482.10.00 -> 84821000
        digits_only = re.sub(r'[^\d]', '', part)
        if len(digits_only) >= 8:
            results.append(digits_only[:8])
        elif len(digits_only) == 6:
            # Some docs use 6-digit: pad to 8
            results.append(digits_only + '00')
    return [c for c in results if re.match(r'^\d{8}$', c)]


# ── Date ────────────────────────────────────────────────────────────────────

DATE_PATTERNS = [
    # From real carrier docs
    (r'(\d{2})/([A-Z]{3})/(\d{4})',   '%d/%b/%Y'),   # 27/FEB/2013  (HLCU)
    (r'([A-Z]{3})-(\d{2})-(\d{4})',   '%b-%d-%Y'),   # FEB-20-2012  (HLCU)
    (r'(\d{2})/(\d{2})/(\d{4})',      '%d/%m/%Y'),   # 14/09/2016   (MSCU)
    (r'(\d{2})-(\d{2})-(\d{4})',      '%d-%m-%Y'),   # 03-06-2024   (MAEU)
    (r'([A-Z]{3})\.(\d{2}),(\d{4})',  '%b.%d,%Y'),   # APR.15,2015  (EGLV)
    (r'(\d{2})\.(\d{2})\.(\d{4})',    '%d.%m.%Y'),   # 18.09.2021   (EGLV)
    (r'(\d{2})-([A-Z]{3})-(\d{4})',   '%d-%b-%Y'),   # 29-MAR-2023  (CSLU)
    (r'(\d{4})-(\d{2})-(\d{2})',      '%Y-%m-%d'),   # ISO 8601 already
]

def normalize_date(raw: str) -> str | None:
    """
    Parse all 7 confirmed carrier date formats -> ISO 8601 YYYY-MM-DD.
    Handles redacted day (FEB-XX-2012) by defaulting to 01.
    """
    if not raw:
        return None
    cleaned = raw.strip().upper()
    # Handle redacted day: FEB-XX-2012 -> FEB-01-2012
    cleaned = re.sub(r'-XX-', '-01-', cleaned)
    cleaned = re.sub(r'/XX/', '/01/', cleaned)
    for pattern, fmt in DATE_PATTERNS:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            try:
                date_str = match.group(0)
                return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
    return None


# ── Weight ──────────────────────────────────────────────────────────────────

WEIGHT_CONVERSIONS = {
    'KGS': 1.0, 'KG': 1.0, 'KGM': 1.0,
    'MTS': 1000.0, 'MT': 1000.0, 'T': 1000.0, 'TONNE': 1000.0,
    'LBS': 0.453592, 'LB': 0.453592,
    'GRS': 1.0,  # "GRS WT" = gross weight in KGS
}

def normalize_weight_to_kg(raw: str) -> float | None:
    """Convert any weight format to KGS for CEISA."""
    if not raw:
        return None
    # Remove thousand separators
    cleaned = re.sub(r',(?=\d{3})', '', raw.strip())
    match = re.match(r'([\d.]+)\s*([A-Z]+)', cleaned.upper())
    if match:
        value = float(match.group(1))
        unit = match.group(2).rstrip('S')  # MTS->MT, KGS->KG
        multiplier = WEIGHT_CONVERSIONS.get(match.group(2), 
                     WEIGHT_CONVERSIONS.get(unit, None))
        if multiplier:
            return round(value * multiplier, 3)
    # Number only, assume KGS
    try:
        return float(re.sub(r'[^\d.]', '', cleaned))
    except ValueError:
        return None


# ── Port ────────────────────────────────────────────────────────────────────

PORT_LOOKUP = {
    # From real carrier documents
    "TILBURY, ESSEX": "GBTIL", "TILBURY": "GBTIL",
    "NHAVA SHEVA": "INNSA",
    "JEBEL ALI": "AEJEA", "JEBEL ALI, U.A.E.": "AEJEA",
    "ODESSA": "UAODS", "ODESSA, UKRAINE": "UAODS",
    "GUANGZHOU PORT, CHINA": "CNGZH", "GUANGZHOU": "CNGZH",
    "ONNE PORT": "NGAPP",
    "HAMBURG": "DEHAM",
    "MUNDRA, INDIA": "INMUN", "MUNDRA": "INMUN",
    "HO CHI MINH CITY PORT, VIETNAM": "VNSGN", "HO CHI MINH": "VNSGN",
    "KUANTAN, MALAYSIA": "MYKUA", "KUANTAN": "MYKUA",
    "JAKARTA, INDONESIA": "IDJKT", "JAKARTA": "IDJKT",
    "SHEKOU, CHINA": "CNSHK", "SHEKOU": "CNSHK",
    # CDP-specific (always hardcoded)
    "CIKARANG DRY PORT": "IDJBK", "CDP": "IDJBK",
    "IDJBK": "IDJBK",
}

async def resolve_port_to_unlocode(port_name: str) -> str | None:
    """Resolve port name to UN/LOCODE. Table first, Gemini fallback."""
    if not port_name:
        return None
    normalized = port_name.upper().strip()
    # Direct lookup
    if normalized in PORT_LOOKUP:
        return PORT_LOOKUP[normalized]
    # Partial match
    for key, code in PORT_LOOKUP.items():
        if key in normalized or normalized in key:
            return code
    # Gemini fallback for unknown ports
    prompt = (
        f"What is the UN/LOCODE (5-character code) for this port: '{port_name}'? "
        f"Respond with ONLY the 5-character code, nothing else."
    )
    try:
        result = await gemini_client.generate(prompt, max_tokens=10)
        code = result.strip().upper()
        if re.match(r'^[A-Z]{5}$', code):
            PORT_LOOKUP[normalized] = code  # cache for session
            return code
    except Exception:
        pass
    return None
```

### 10.4 Preprocessing Pipeline v5.2 (Full Updated)

```python
# packages/agents/src/nodes/preprocess.py (updated)
async def preprocess_node(state: DeclarationState) -> DeclarationState:
    preprocessed = []
    for doc in state["documents"]:
        raw_bytes = await storage.download(doc["storage_path"])
        
        # Step 1: PDF → images (MinerU 2.5)
        mineru_result = await mineru_client.preprocess(raw_bytes, doc["original_name"])
        
        # Step 2: Carrier SCAC detection
        full_text = "\n".join(mineru_result.get("text_per_page", []))
        carrier_scac = detect_carrier_scac(full_text, doc["original_name"])
        carrier_profile = load_carrier_profile(carrier_scac)
        
        # Step 3: Page type classification (multi-page handling)
        classified_pages = []
        for i, (img_b64, page_text) in enumerate(zip(
            mineru_result["images_b64"],
            mineru_result.get("text_per_page", [""] * len(mineru_result["images_b64"]))
        )):
            page_type = detect_page_type(page_text, i + 1, carrier_scac)
            classified_pages.append({
                "page_num": i + 1,
                "page_type": page_type,
                "img_b64": img_b64,
                "text": page_text
            })
        
        # Step 4: Filter — only MAIN and ATTACHMENT
        active_pages = [p for p in classified_pages
                        if p["page_type"] in ("MAIN", "ATTACHMENT")]
        skipped = [p["page_num"] for p in classified_pages
                   if p["page_type"] not in ("MAIN", "ATTACHMENT")]
        if skipped:
            logger.info(f"Skipped pages {skipped} (T&C / demurrage)")
        
        # Step 5: Watermark removal on active pages
        cleaned_images = []
        all_watermarks = []
        for page in active_pages:
            img = b64_to_cv2(page["img_b64"])
            cleaned, detected_wm = remove_watermarks(img)
            all_watermarks.extend(detected_wm)
            cleaned_images.append(cv2_to_b64(cleaned))
        
        # Step 6: Image enhancement (CLAHE, deskew, denoise)
        enhanced_images = [apply_image_preprocessing(img) for img in cleaned_images]
        
        # Step 7: Quality scoring and route decision
        quality_scores = [compute_quality_score(b64_to_cv2(img)) for img in enhanced_images]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
        
        has_text_layer = mineru_result.get("text_layer", False)
        if has_text_layer and avg_quality >= settings.ocr_fast_path_quality_threshold:
            route = "FAST_PATH"
        elif avg_quality < 0.50:
            route = "DEGRADED"
        else:
            route = "STANDARD"
        
        preprocessed.append({
            "doc_id": doc["id"],
            "doc_type": doc["doc_type"],
            "carrier_scac": carrier_scac,
            "carrier_profile": carrier_profile,
            "images_b64": enhanced_images,
            "page_count": len(enhanced_images),
            "quality_score": avg_quality,
            "processing_route": route,
            "text_layer": has_text_layer,
            "watermarks_detected": list(set(all_watermarks)),
            "skipped_pages": skipped,
            "signed_url": doc.get("signed_url")
        })
        
        # Update document record
        await db.execute(
            "UPDATE documents SET quality_score=$1, processing_route=$2, carrier_scac=$3 WHERE id=$4",
            avg_quality, route, carrier_scac, doc["id"]
        )
    
    return {**state, "preprocessed": preprocessed}
```

---

## 11. Ground Truth Annotation Schema (NEW — v5.2)

The 8 real carrier documents are the primary evaluation fixtures. Full annotations are stored at `eval/fixtures/real_bl_ground_truth.json`. Extract below shows the critical CDP-relevant document:

```json
{
  "Evergreen_Filled_1": {
    "file": "Evergreen_Filled_1.pdf",
    "carrier": "Evergreen Line",
    "scac": "EGLV",
    "pages": 2,
    "processing_route": "STANDARD",
    "watermarks": ["ORIGINAL", "PROOFREAD", "READ"],
    "priority": "HIGHEST",
    "cdp_relevant": true,
    "insw_flag": true,
    "insw_reason": "Caustic Soda HS 28151110 - UN 1813 Class 8 Dangerous Goods",
    "ceisa_fields": {
      "nomorBl": "EGLV100150418716",
      "namaKonsignee": "PT. KEMINDO CAO RESOURCES, JAKARTA UTARA, DKI JAKARTA",
      "kodePelabuhanMuat": "INMUN",
      "kodePelabuhanBongkar": "IDJKT",
      "hs_code": "28151110",
      "un_number": "1813",
      "dangerous_goods_class": "8",
      "beratKotor": 301920.0,
      "tglBl": "2021-09-18",
      "jumlah_kontainer": 12
    }
  }
}
```

Full ground truth JSON: `eval/fixtures/real_bl_ground_truth.json` (committed to repo).

---

## 12. Updated Eval Dataset (v5.2)

The 20-document eval set is updated. Fixtures 1–8 are now the real carrier documents:

| # | File | Carrier | Challenge | CDP Relevant | INSW |
|---|---|---|---|---|---|
| 1 | Hapag_Filled_1.pdf | HLCU | DRAFT watermark, no HS, household goods | No | No |
| 2 | Hapag_Filled_2.pdf | HLCU | 3 pages, HS dot format, KGM unit | No | No |
| 3 | MSC_Filled_1.pdf | MSCU | Largely blank — DAPT only, unfilled fields | No | No |
| 4 | Maersk_Filled_1.pdf | MAEU | 12-container table, comma weight, ORIGINAL wm | No | No |
| 5 | Evergreen_Filled_1.pdf | EGLV | **Indonesian route, HS 28151110 DG, 3 watermarks** | **YES** | **YES** |
| 6 | Evergreen_Filled_2.pdf | EGLV | MON.DD,YYYY date, negotiable B/L, 15 containers | No | No |
| 7 | Evergreen_Filled_3.pdf | EGLV | Industrial components, multi-item attachment | No | No |
| 8 | Cordelia_Filled_1.pdf | CSLU | T&C page 2, DD-MON-YYYY, lesser-known carrier | No | No |
| 9–20 | synthetic_*.pdf | Mixed | Generated from real carrier templates + Faker | — | — |

Fixtures 9–20 SHALL be generated using real carrier template PDFs (downloaded from carrier websites) with Faker-injected values — NOT from reportlab from scratch (see PRD §10.2).
