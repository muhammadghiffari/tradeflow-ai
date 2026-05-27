# AI Agent Build Guide
## TradeFlow AI — Step-by-Step Construction Manual

---

**Guide Version:** 1.0  
**Paired With:** `PRD_TradeFlowAI_v4.md` (read this first, always)  
**Paired With:** `DESIGN.md` (read for all UI/component specs before touching frontend)  
**Date:** May 2026

---

## How to Use This Guide

This document is written **for AI coding agents**. Every step is atomic, ordered, and self-verifying.

### Rules for the Agent

1. **Read PRD v4 + DESIGN.md @D in full before writing a single line of code.** They are your source of truth. If this guide conflicts with the PRD, the PRD wins.
2. **Never skip a verification checkpoint** (`✅ Verify:`). They catch mistakes before they compound.
3. **Never create a file without knowing where it lives.** Full paths are provided for every file.
4. **When a step says "see PRD §N"** — open that section and read it before proceeding.
5. **One step = one commit.** Small, passing commits beats large broken PRs.
6. **If a step is ambiguous**, stop and clarify rather than guess. Guesses compound into refactors.

### PRD Inconsistencies to Be Aware Of (Resolved Here)

The following minor inconsistencies exist in PRD v4. This guide resolves them:

| Location | Inconsistency | Resolution |
|----------|--------------|-----------|
| §2 vs §9.6 | §2 targets "≥85% CEISA acceptance" but §9.6 acknowledges 25–40% real rejection rate | These are separate: §9.6 describes the *problem* (baseline), §2 is the *goal* (after AI intervention). Both are correct. |
| §6 vs §7 | §6 service map says Traefik, §7 docker-compose uses supabase-kong | Use **Traefik 3.x** as the main reverse proxy. supabase-kong is the internal Supabase routing only — do not expose it. |
| §2 & §6 | Some lines still say "Supabase Auth JWT" after Decision 2 mandated Keycloak | **Keycloak 26 is the only auth provider.** Any reference to "Supabase Auth" means "Supabase RLS consuming Keycloak JWT", not Supabase Auth as the provider. |

### Key Invariants (Never Violate)

1. **Audit Log is Append-Only:** The `audit_log` table must never be updated or deleted. Enforce via `REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM PUBLIC`.
2. **Validation Rules are Hot-Reloadable:** Never hardcode cross-document validation rules in Python/TypeScript. Always read dynamically from `validation_rules.json`.
3. **No Bare `os.getenv()`:** All environment variables must be validated through `pydantic-settings` in `config.py` with strict type annotations.
4. **Keycloak is the Only Auth Provider:** Never use Supabase Auth for user login or session management. Use it only for RLS authorization.
5. **Human-in-the-Loop is Mandatory:** The LangGraph pipeline MUST pause at `interrupt_before=["submit"]` for operator review. Do not bypass this.
6. **Async Task Prioritization:** Celery queues must be strictly prioritized (`critical`, `high`, `default`, `low`). Enterprise tier MUST use `critical`/`high`.
7. **Graceful Fallbacks:** If Azure DI, PaddleOCR, or Gemini fails, the system must degrade gracefully (e.g., rule-based fallback or lower confidence flags) without crashing the pipeline.
8. **Single Source of Truth for Types:** Use `packages/shared-types` (Zod schemas) to maintain contract sync between Next.js (tRPC) and FastAPI (Pydantic).

### PRD Cross-Reference Map

Use this map to find exactly what you need in the PRD:

| If you are building... | Read PRD section |
|------------------------|-------------------|
| Multi-Agent workflow or StateGraph | **§5** (Multi-Agent System Design) & **§14** (State Machines) |
| OCR or Document Extraction | **§9.1 - §9.3** (Core AI/ML Modules) |
| HS Code Recommendation | **§9.5** (HS RAG) |
| Rejection Prediction / CRS | **§9.6 - §9.7** (Rejection Prediction & CRS) |
| Database Schema / Supabase Setup | **§12** (Data Models & Database Schema) & **§7** (Infrastructure) |
| Next.js Frontend / UI | **§18** (Dashboard & UI Specifications) |
| Blockchain / Smart Contracts | **§8** (Blockchain Integration) |
| API Endpoints | **§13** (API Contracts) |
| Error Handling / Fallbacks | **§21** (Error Handling & Fallback Logic) |
| Integrations (CEISA / MCP) | **§9** (MCP) & **§16** (CEISA Integration) |

---

## Repository Structure

Create this structure in full before writing any service code. Every path matters.

```
tradeflow-ai/
├── .mcp.json                        # MCP server configs (PRD §5)
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── deploy-staging.yml
│       └── deploy-production.yml
├── docker-compose.yml               # local dev (PRD §7)
├── docker-compose.override.yml      # dev overrides (hot reload etc.)
├── turbo.json                       # Turborepo config
├── pnpm-workspace.yaml
├── package.json                     # root (workspaces)
│
├── apps/
│   ├── api/                         # FastAPI backend (Python 3.13)
│   │   ├── Dockerfile
│   │   ├── pyproject.toml           # managed by uv
│   │   ├── uv.lock
│   │   ├── alembic/                 # ONLY if not using Supabase CLI migrations
│   │   └── src/
│   │       ├── main.py
│   │       ├── config.py            # pydantic-settings, all env vars
│   │       ├── dependencies.py      # auth, db session, tier checks
│   │       ├── routers/
│   │       │   ├── batches.py
│   │       │   ├── hs_recommend.py
│   │       │   ├── blockchain.py
│   │       │   └── admin.py
│   │       ├── services/
│   │       │   ├── ingest_svc.py
│   │       │   ├── ceisa_gateway.py
│   │       │   ├── blockchain_svc.py
│   │       │   └── notification_svc.py
│   │       ├── tasks/               # Celery tasks (one file per task group)
│   │       │   ├── celery_app.py
│   │       │   ├── ocr_tasks.py
│   │       │   ├── submit_tasks.py
│   │       │   └── learning_tasks.py
│   │       └── models/              # Pydantic v2 schemas
│   │           ├── batch.py
│   │           ├── ceisa.py
│   │           └── blockchain.py
│   │
│   ├── web/                         # Next.js 15 frontend
│   │   ├── Dockerfile
│   │   ├── package.json
│   │   ├── next.config.ts
│   │   ├── tailwind.config.ts
│   │   ├── biome.json
│   │   ├── vitest.config.ts
│   │   └── src/
│   │       ├── app/                 # App Router pages
│   │       │   ├── layout.tsx
│   │       │   ├── (dashboard)/
│   │       │   │   ├── page.tsx
│   │       │   │   ├── batches/
│   │       │   │   │   ├── new/page.tsx         # upload wizard
│   │       │   │   │   ├── [id]/page.tsx        # batch detail
│   │       │   │   │   └── [id]/review/page.tsx # operator review
│   │       │   │   ├── analytics/page.tsx
│   │       │   │   └── simulator/page.tsx
│   │       │   └── api/             # Next.js route handlers (tRPC adapter)
│   │       ├── components/
│   │       │   ├── ui/              # shadcn/ui components
│   │       │   ├── review/          # ReviewScreen, DocumentViewer, FieldsPanel
│   │       │   ├── wizard/          # SME upload wizard
│   │       │   ├── dashboard/       # KPI cards, charts
│   │       │   └── simulator/       # CEISA simulator control panel
│   │       ├── lib/
│   │       │   ├── supabase.ts      # Supabase client (Realtime subscription)
│   │       │   ├── auth.ts          # next-auth 5 + Keycloak provider
│   │       │   └── trpc.ts          # tRPC client
│   │       └── stores/              # Zustand stores
│   │
│   └── simulator/                   # CEISA mock API (FastAPI, separate service)
│       ├── Dockerfile
│       ├── pyproject.toml
│       └── src/
│           ├── main.py
│           ├── scenarios.py
│           └── state.py
│
├── packages/
│   ├── agents/                      # LangGraph agent graph (Python)
│   │   ├── pyproject.toml
│   │   └── src/
│   │       ├── graph.py             # main LangGraph StateGraph definition
│   │       ├── state.py             # DeclarationState TypedDict
│   │       ├── nodes/               # one file per agent node
│   │       │   ├── preprocess.py
│   │       │   ├── ocr.py
│   │       │   ├── extract_bl.py
│   │       │   ├── extract_pl.py
│   │       │   ├── extract_invoice.py
│   │       │   ├── validate.py
│   │       │   ├── hs_recommend.py
│   │       │   ├── risk_assess.py
│   │       │   ├── blockchain_anchor.py
│   │       │   ├── submit.py
│   │       │   └── learning.py
│   │       └── prompts/             # versioned prompt templates
│   │           ├── extract_bl_v1.txt
│   │           ├── extract_pl_v1.txt
│   │           ├── extract_invoice_v1.txt
│   │           └── hs_rerank_v1.txt
│   │
│   ├── db/                          # Supabase migrations + seed
│   │   ├── migrations/
│   │   │   └── 20260501_001_init_schema.sql
│   │   ├── seed/
│   │   │   ├── seed_synthetic_data.sql
│   │   │   ├── seed_btki_hs_codes.sql
│   │   │   └── seed_demo_users.sql
│   │   ├── functions/               # Supabase Edge Functions
│   │   │   ├── ceisa-webhook/
│   │   │   ├── npwp-validate/
│   │   │   └── notify-operator/
│   │   └── validation_rules.json    # hot-reloadable validation rules (PRD §9.4)
│   │
│   ├── shared-types/                # Zod schemas shared across TS + Python
│   │   ├── package.json
│   │   └── src/
│   │       ├── batch.ts
│   │       ├── ceisa.ts
│   │       └── index.ts
│   │
│   └── blockchain/                  # Hardhat smart contracts
│       ├── package.json
│       ├── hardhat.config.ts
│       ├── contracts/
│       │   ├── DocumentRegistry.sol  # PRD §8
│       │   └── SubmissionAudit.sol
│       ├── scripts/
│       │   └── deploy.ts
│       └── test/
│           └── DocumentRegistry.test.ts
│
├── eval/                            # AI evaluation framework (PRD §22)
│   ├── run_eval.py
│   ├── fixtures/                    # 15 labeled CIPL sets (PRD Appendix A)
│   │   ├── 01/
│   │   │   ├── docs/invoice.pdf
│   │   │   └── expected.json
│   │   └── ...
│   └── metrics.py
│
└── docs/
    ├── PRD_TradeFlowAI_v4.md        # ← your source of truth
    ├── DESIGN.md                    # ← your UI/component source of truth
    └── AGENT_BUILD_GUIDE.md         # this file
```

---

## Phase 0 — Pre-Build Setup (Do This First, Always)

### Step 0.1 — Read source documents

Before touching code, read these in full:
- `docs/PRD_TradeFlowAI_v4.md` — all 25 sections
- `docs/DESIGN.md` — all UI/component specs

Mark any section you don't understand. Do not proceed past Step 0 with unanswered questions.

### Step 0.2 — Initialize toolchain

```bash
# 1. Node: pnpm 9 + Turborepo
npm install -g pnpm@9
npx create-turbo@latest tradeflow-ai --package-manager pnpm

# 2. Python: uv (replaces pip/poetry — PRD §15)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version  # must be 0.4+

# 3. Confirm versions
node --version    # 22+
pnpm --version    # 9+
python --version  # 3.13+
docker --version  # 27+
```

✅ **Verify:** All version checks pass. `turbo --version` responds.

### Step 0.3 — Initialize .mcp.json

Create `.mcp.json` from PRD §5 exactly. Wire: GitHub, Supabase, Linear, Sentry, Vercel, PostHog.

Do NOT proceed without this file. MCP servers must be configured from Day 1, not retrofitted.

```bash
# Verify MCP configs resolve (no syntax errors)
cat .mcp.json | python -m json.tool
```

✅ **Verify:** JSON is valid. All 6 MCP servers listed with correct `command` and `env` keys.

### Step 0.4 — Create full directory structure

Create every directory in the repo structure above. Use:
```bash
mkdir -p apps/{api/src/{routers,services,tasks,models},web/src/{app,components,lib,stores},simulator/src}
mkdir -p packages/{agents/src/{nodes,prompts},db/{migrations,seed,functions},shared-types/src,blockchain/{contracts,scripts,test}}
mkdir -p eval/fixtures/{01..15}/docs
mkdir -p docs
```

✅ **Verify:** `find . -type d | sort` shows all directories. No missing paths.

---

## Phase 1 — Infrastructure Foundation (Week 1–2)

### Step 1.1 — docker-compose.yml (local dev stack)

**File:** `/docker-compose.yml`

Services to define (see PRD §7 for exact image versions):
- `supabase-db` — postgres:17-alpine
- `supabase-realtime` — supabase/realtime
- `supabase-storage` — supabase/storage-api
- `supabase-kong` — kong (internal routing only, not exposed)
- `redis` — redis/redis-stack:8.0 (full Redis Stack for LangGraph checkpointer)
- `chromadb` — chromadb/chroma:0.6.0 (persist to named volume)
- `traefik` — traefik:v3.2 (reverse proxy, expose :80 and :8080 dashboard)
- `api` — build: ./apps/api, depends_on: [supabase-db, redis]
- `worker` — same image as api, command: `celery -A src.tasks.celery_app worker`
- `simulator` — build: ./apps/simulator, port: 8001
- `frontend` — build: ./apps/web, port: 3000

**Critical:** Mount `packages/db/validation_rules.json` into `api` container at `/app/validation_rules.json`. This enables hot-reload without container restart.

✅ **Verify:** `docker compose up -d` — all containers reach `healthy` state. `docker compose ps` shows no restarts.

### Step 1.2 — Supabase database schema

**File:** `packages/db/migrations/20260501_001_init_schema.sql`

Implement the full schema from PRD §11. Required tables in order (respect foreign key dependencies):
1. `companies`
2. `profiles` (references `auth.users` from Supabase Auth — use `ON DELETE CASCADE`)
3. `batches` (include `langgraph_thread_id TEXT`)
4. `documents`
5. `extracted_fields` (include generated column `confidence_level`)
6. `validation_results`
7. `hs_recommendations`
8. `ceisa_submissions`
9. `blockchain_records`
10. `learning_samples`
11. `submission_outcomes`
12. `audit_log` (BIGSERIAL, then: `REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM PUBLIC`)

After tables: add all indexes. After indexes: enable Supabase Realtime on `batches` and `extracted_fields`.

After tables: add RLS policies from PRD §11. At minimum:
- `batches`: users see own company's batches only
- `extracted_fields`: same as batches
- `audit_log`: SELECT only for admin role, no INSERT via application (use service role key)

```bash
# Apply migration
supabase db push --local
```

✅ **Verify:** `supabase db diff --local` shows no drift. All 12 tables exist. `audit_log` UPDATE is rejected when tested with `psql`.

### Step 1.3 — Keycloak 26 auth setup

**Add to docker-compose.yml:**
```yaml
keycloak:
  image: quay.io/keycloak/keycloak:26
  command: start-dev
  environment:
    KEYCLOAK_ADMIN: admin
    KEYCLOAK_ADMIN_PASSWORD: admin
  ports:
    - "8080:8080"
```

Configure realm `tradeflow` with 4 roles: `operator`, `admin`, `supervisor`, `importer` (see PRD §4 Decision 2).

Export realm config to `infra/keycloak/realm-tradeflow.json` — checked into git. Import on startup via `--import-realm` flag.

See PRD §4 Decision 2 for the integration architecture:
```
Keycloak RS256 JWT → FastAPI (python-jose validates against JWKS endpoint)
Keycloak RS256 JWT → Supabase RLS (configured with Keycloak realm public key)
Keycloak RS256 JWT → Next.js (next-auth 5.x Keycloak provider)
```

✅ **Verify:** POST to Keycloak `/realms/tradeflow/protocol/openid-connect/token` returns JWT. Decode JWT — `realm_access.roles` contains expected role.

### Step 1.4 — FastAPI base setup

**File:** `apps/api/src/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .config import settings
from .routers import batches, hs_recommend, blockchain, admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: init Supabase client, Redis connection, ChromaDB
    yield
    # shutdown: close connections

app = FastAPI(title="TradeFlow AI API", version="1.0.0", lifespan=lifespan)
```

**File:** `apps/api/src/config.py` — implement all env vars from PRD §22 using `pydantic-settings`. Every variable must have a type annotation. No bare `os.getenv()` anywhere in the codebase.

**File:** `apps/api/src/dependencies.py` — implement:
- `get_current_user()` — decode Keycloak JWT via `python-jose`, fetch profile from Supabase
- `require_enterprise()` — raise 403 if user.tier != 'enterprise'
- `require_admin()` — raise 403 if user.role not in ['admin', 'supervisor']

✅ **Verify:** `GET /health` returns `{"status": "ok"}`. Authenticated endpoint with valid Keycloak JWT returns 200. Invalid JWT returns 401.

### Step 1.5 — Celery worker setup

**File:** `apps/api/src/tasks/celery_app.py`

```python
from celery import Celery
from kombu import Queue

app = Celery("tradeflow")
app.config_from_object("apps.api.src.config:CeleryConfig")

# Task queues (priority matters for enterprise tier)
app.conf.task_queues = (
    Queue("critical", routing_key="critical"),   # blockchain anchoring
    Queue("high",     routing_key="high"),        # OCR + extraction (enterprise)
    Queue("default",  routing_key="default"),     # standard processing
    Queue("low",      routing_key="low"),         # retraining, reporting
)
```

Register task stubs (not implemented yet — just `pass` bodies with `@app.task` decorators) for all tasks that will be implemented in later phases:
`preprocess_document`, `run_ocr`, `extract_fields`, `validate_fields`, `recommend_hs`, `assess_risk`, `submit_to_ceisa`, `anchor_blockchain`, `process_ceisa_response`, `retrain_predictor`.

✅ **Verify:** `celery -A src.tasks.celery_app inspect active` returns empty list (no tasks, no errors). Worker starts without import errors.

### Step 1.6 — Document upload endpoint

**File:** `apps/api/src/routers/batches.py`

Implement `POST /api/v1/batches` from PRD §12 (API Contracts):
1. Accept multipart/form-data with `files[]` (max 3) and `tier`
2. Validate each file: type (PDF/JPG/PNG/TIFF/WEBP/XLSX), size (max 50MB)
3. Compute SHA-256 hash of each file
4. Upload to Supabase Storage (or MinIO in dev) under `documents/{batch_id}/{doc_id}/{filename}`
5. Create `batches` record in DB
6. Create `documents` records in DB (one per file)
7. Auto-detect document type (stub: return 'unknown' if confidence < 0.80, accept user override)
8. Enqueue `preprocess_document.apply_async(args=[batch_id], queue='high')`
9. Return 201 with batch_id and document list

**File:** `apps/api/src/services/ingest_svc.py` — storage abstraction:
```python
# Reads STORAGE_BACKEND env var ('supabase' | 'minio')
# Delegates to supabase_storage.py or minio_storage.py
# Single interface: upload_document(batch_id, doc_id, file_bytes, filename) → path
```

✅ **Verify:** POST multipart with a PDF file → 201 response with batch_id. File appears in MinIO/Supabase Storage. `batches` and `documents` rows created in DB. Celery task enqueued (visible in Redis).

### Step 1.7 — Next.js 15 frontend base

**File:** `apps/web/next.config.ts`

Enable: Turbopack, PPR (partial prerendering), Server Components. Configure rewrites for `/api/*` → FastAPI.

**File:** `apps/web/src/app/layout.tsx` — root layout with:
- `next-auth 5` SessionProvider (Keycloak provider configured)
- `TanStack Query` QueryClientProvider
- Sonner `Toaster` for notifications
- Tailwind CSS v4 global styles

**File:** `apps/web/src/lib/auth.ts` — next-auth 5 config:
```typescript
// Keycloak provider pointing to local Keycloak on port 8080
// Map Keycloak JWT claims (realm_access.roles) to next-auth session
// Refresh token handling for 8-hour operator shifts
```

**File:** `apps/web/src/lib/supabase.ts` — Supabase browser client:
```typescript
// createClient() for Realtime subscriptions
// Pass Keycloak access_token as Supabase auth JWT
// subscribeToDocumentStatus(batchId, callback) helper
```

**Page:** `apps/web/src/app/(dashboard)/page.tsx` — dashboard home. Refer to `DESIGN.md` for exact layout spec. Stub content acceptable at this step — structure and routing must work.

✅ **Verify:** `pnpm dev` starts without errors. `/` redirects to Keycloak login. After login, dashboard renders. Supabase Realtime connection established (check browser network tab for WS connection).

### Step 1.8 — GitHub Actions CI

**File:** `.github/workflows/ci.yml`

Implement all jobs from PRD §7 CI/CD section:
- `lint-backend`: `uv run ruff check` + `uv run mypy --strict`
- `lint-frontend`: `pnpm biome check` + `pnpm tsc --noEmit`
- `test-backend`: `uv run pytest --cov=src --cov-fail-under=70`
- `test-frontend`: `pnpm vitest run`
- `db-validate`: `supabase db diff --schema public` (fail if drift detected)

Do NOT add `eval-ai` or `blockchain-test` jobs yet — those come in later phases.

✅ **Verify:** Push to feature branch → all CI jobs pass (tests may be stubs, but no compilation errors).

---

## Phase 2 — OCR & AI Extraction Core (Week 3–4)

> Read PRD §9 (Core AI/ML Modules) in full before starting this phase.

### Step 2.1 — Document preprocessing node

**File:** `packages/agents/src/nodes/preprocess.py`

Implement `preprocess()` per PRD §9.1 exactly:
1. Detect text layer via `pdfplumber 0.11` — if chars exist, extract text, set `confidence=0.98`, skip OCR path
2. For image-only: convert to images via `pymupdf 1.25` at 300 DPI
3. OpenCV pipeline: CLAHE (clip=2.0, tile=(8,8)) → deskew via Hough Transform (correct if |angle| > 0.5°) → denoise → Otsu binarization → border crop
4. Language detection: `lingua-py 2.0` — return one of: `id`, `en`, `zh`, `ja`
5. Quality scoring: Laplacian variance (sharpness) + contrast score + skew angle → float [0,1]
6. Return `PreprocessResult(images, text, language, quality_score, has_text_layer)`

Connect to Celery: `preprocess_document` task calls this, updates `documents.status` to `ocr_running`, enqueues `run_ocr`.

✅ **Verify:** Process test PDF (use `eval/fixtures/01/docs/invoice.pdf`). Assert: `has_text_layer=True` for digital PDF, `quality_score > 0.80` for clear scan. For skewed image (rotate fixture 5°), assert deskew corrects it.

### Step 2.2 — PaddleOCR primary engine

**File:** `packages/agents/src/nodes/ocr.py`

Implement PaddleOCR integration:
```python
from paddleocr import PaddleOCR, PPStructure

# PP-OCRv4: general text
ocr_engine = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False)

# PP-StructureV3: table extraction (Packing List)
table_engine = PPStructure(table=True, ocr=True, show_log=False)
```

OCR result normalization — convert PaddleOCR output to internal format:
```python
# Internal format (same for all OCR engines):
{
  "words": [
    { "text": str, "confidence": float, "bbox": [x, y, w, h], "page": int }
  ],
  "tables": [          # from PP-StructureV3 (Packing List only)
    { "rows": [[cell_text, ...], ...], "bbox": [...], "confidence": float }
  ],
  "page_confidence": float  # average word confidence per page
}
```

Fallback trigger: if `page_confidence < 0.78` OR `quality_score < 0.65` → set `needs_azure_fallback=True` in state.

✅ **Verify:** Run against `eval/fixtures/05/docs/packing_list.pdf` (12-item digital PL). Assert: table extracted with correct row count. Assert: `page_confidence > 0.90` for digital PDF.

### Step 2.3 — Azure Document Intelligence fallback

**File:** `packages/agents/src/nodes/ocr.py` (add to existing file)

```python
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential

# Prebuilt models: 'prebuilt-invoice' for Invoice, 'prebuilt-document' for B/L + PL
```

Map Azure output to same internal format as PaddleOCR output. Ensemble logic: when both engines run → compare field-by-field, take higher confidence. Flag disagreements > 5% on numeric fields.

Feature flag: if `ENABLE_AZURE_DI_FALLBACK=false` → skip Azure, proceed with PaddleOCR only.

✅ **Verify:** Disable PaddleOCR confidence temporarily (mock return 0.50) → Azure fallback triggers. Azure output maps to same format. Feature flag disables Azure correctly.

### Step 2.4 — LangGraph agent graph scaffold

**File:** `packages/agents/src/state.py`

Implement `DeclarationState` TypedDict exactly from PRD §4 Decision 1.

**File:** `packages/agents/src/graph.py`

Build the LangGraph `StateGraph` with all nodes and edges defined (even if most nodes are stubs):

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.redis import RedisSaver

builder = StateGraph(DeclarationState)

# Add all nodes
builder.add_node("preprocess", preprocess_node)
builder.add_node("ocr", ocr_node)
builder.add_node("extract_bl", extract_bl_node)
builder.add_node("extract_pl", extract_pl_node)
builder.add_node("extract_invoice", extract_invoice_node)
builder.add_node("validate", validate_node)
builder.add_node("hs_recommend", hs_recommend_node)
builder.add_node("risk_assess", risk_assess_node)
builder.add_node("blockchain_anchor", blockchain_anchor_node)
builder.add_node("submit", submit_node)
builder.add_node("learning", learning_node)

# Edges
builder.set_entry_point("preprocess")
builder.add_edge("preprocess", "ocr")
builder.add_edge("ocr", "extract_bl")  # parallel extraction handled by conditional edge
# ... all edges per PRD §4 LangGraph graph diagram

# Human-in-the-loop: interrupt after risk_assess → await operator approval
builder.add_edge("risk_assess", "blockchain_anchor")  # parallel branch
builder.add_conditional_edges("risk_assess", route_after_risk, {...})

# Redis checkpointer
checkpointer = RedisSaver.from_conn_string(settings.REDIS_URL)
graph = builder.compile(checkpointer=checkpointer, interrupt_before=["submit"])
```

✅ **Verify:** `graph.get_graph().print_ascii()` renders without missing nodes. Invoke with test state → reaches `interrupt_before="submit"` checkpoint and pauses. Resume after checkpoint → reaches END.

### Step 2.5 — Multimodal LLM extraction agents (per doc type)

**Files:** 
- `packages/agents/src/nodes/extract_bl.py`
- `packages/agents/src/nodes/extract_pl.py`
- `packages/agents/src/nodes/extract_invoice.py`

Each extraction agent follows the same pattern (see PRD §9.3):

```python
import google.generativeai as genai
from pathlib import Path

def extract_bill_of_lading(state: DeclarationState) -> DeclarationState:
    # 1. Load prompt template (versioned): prompts/extract_bl_v1.txt
    # 2. Load CEISA schema: packages/db/ceisa_schema_v4.json (hot-reloadable)
    # 3. Build Gemini API call:
    #    - Model: settings.GEMINI_MODEL_PRIMARY (gemini-3.1-pro)
    #    - System: prompt_template + ceisa_schema + 5 few-shot examples
    #    - User message: OCR JSON + base64 document images
    #    - Response format: JSON (strict)
    # 4. Parse response → extracted_fields dict with per-field confidence
    # 5. Run post-processors (NPWP checksum, date normalization, etc.)
    # 6. LangSmith: tag with doc_id, batch_id, prompt_version
    # 7. Return updated state
```

**Prompt files** (`packages/agents/src/prompts/`): Write initial prompts following the spec in PRD §9.3. Each prompt must include:
- Role definition
- CEISA field schema reference (loaded dynamically, not hardcoded)
- Output JSON format with confidence scores
- Explicit: "If unsure, set confidence < 0.70, never hallucinate"
- 5 few-shot examples (use synthetic data from `eval/fixtures/`)

**Model fallback:** If `gemini-3.1-pro` returns error or `COST_SAVING_MODE=true` → retry with `gemini-2.5-flash`.

**Rule-based fallback** (for when both models fail): regex-based extractor for fixed-format fields (NPWP regex, B/L number pattern, date patterns). Returns lower confidence scores.

✅ **Verify:** Run extraction against `eval/fixtures/01/docs/invoice.pdf`. Compare output to `eval/fixtures/01/expected.json`. Critical fields (NPWP, B/L number, CIF) must match with confidence ≥ 0.85. LangSmith shows the trace.

### Step 2.6 — Cross-document validation engine

**File:** `packages/agents/src/nodes/validate.py`

```python
import json
from pathlib import Path

def validate_fields(state: DeclarationState) -> DeclarationState:
    # 1. Load rules hot-reloadably:
    rules_path = Path("/app/validation_rules.json")  # mounted volume
    rules = json.loads(rules_path.read_text())
    
    # 2. Evaluate each rule against merged extracted_fields
    # 3. Build validation_results list: { rule_id, severity, error_message, affected_fields }
    # 4. PASS / WARNING / CRITICAL_FAIL per rule
    # 5. Return updated state
```

Implement all 7 rules from PRD §9.4. Rule evaluation engine must:
- Handle missing fields gracefully (treat as CRITICAL_FAIL for required fields)
- Produce actionable `error_message` in Bahasa Indonesia
- List `affected_fields` (used by UI to highlight relevant bounding boxes)

✅ **Verify:** Use `eval/fixtures/15` (batch with deliberate cross-doc inconsistency). Assert: CV001 (package count) fires as CRITICAL_FAIL. Use `eval/fixtures/01` (clean batch). Assert: all rules PASS.

### Step 2.7 — XLSX Packing List handler

**File:** `packages/agents/src/nodes/ocr.py` (add xlsx branch)

```python
import openpyxl

def handle_xlsx_packing_list(file_path: str) -> OCRResult:
    # 1. Load workbook via openpyxl 3.2
    # 2. Detect header row: find row with highest match to known PL column names
    # 3. LLM column mapper: map each column header to CEISA field name
    #    (single Gemini call with column names + examples)
    # 4. Extract all data rows as structured list
    # 5. Return same OCRResult format as image OCR (confidence=0.97 for XLSX)
```

Branch in preprocessing: if file extension is `.xlsx` → call `handle_xlsx_packing_list()` → skip OCR entirely.

✅ **Verify:** Process `eval/fixtures/07/docs/packing_list.xlsx` (clean XLSX). Assert row count matches expected.json. Process `eval/fixtures/08` (messy headers) — assert LLM column mapper handles non-standard headers.

---

## Phase 3 — Intelligence Modules (Week 5)

> Read PRD §9.5 (HS RAG), §9.6 (Rejection Prediction), §9.7 (CRS), §9.8 (Adaptive Learning) before starting.

### Step 3.1 — BTKI knowledge base + ChromaDB

**File:** `packages/db/seed/seed_btki_hs_codes.sql` — seed script that populates the `btki_hs_codes` reference table.

**File:** `packages/agents/src/nodes/hs_recommend.py` — ChromaDB setup:

```python
import chromadb
from openai import OpenAI

chroma_client = chromadb.PersistentClient(path="/data/chromadb")
collection = chroma_client.get_or_create_collection(
    name="btki_hs_codes",
    metadata={"hnsw:space": "cosine"}
)

def seed_btki_if_empty():
    # If collection.count() == 0: load from DB, embed via text-embedding-3-small, upsert
    # Run at service startup
```

HS Code entry structure: `{ hs_code, description_id, description_en, duty_rate, vat_rate, pph_rate, active, effective_date }`. Embed `description_en` field.

Monthly refresh: Celery beat task `refresh_btki_embeddings` in `learning_tasks.py`.

✅ **Verify:** After seeding, `collection.count() >= 1000`. Query "laptop computer" → top result has HS code starting with "8471". Query "fresh mangoes" → top result starts with "0804".

### Step 3.2 — HS Code recommendation node

**File:** `packages/agents/src/nodes/hs_recommend.py`

Implement the full RAG pipeline from PRD §9.5:
1. Trigger conditions: confidence < 0.75 OR empty field OR CV006 fails OR operator request
2. Normalize product description (lowercase, remove noise, detect if Indonesian → translate hint to LLM)
3. Embed via `text-embedding-3-small`
4. ChromaDB cosine search: top-10 candidates
5. Gemini re-ranker: single call, returns ranked list with reasoning
6. Output top-3: `{ hs_code, description_id, duty_rate, vat_rate, confidence, reasoning }`
7. Store in `hs_recommendations` table

**API endpoint:** `POST /api/v1/hs-recommend` (see PRD §12) — calls this same pipeline. Used by frontend HS Code Wizard (SME feature F-032).

✅ **Verify:** POST `{ "product_description": "Mesin cetak inkjet warna" }` → top-1 result should be HS 8443.xx (printing machinery). Duty rate returned. Reasoning is in Indonesian.

### Step 3.3 — CEISA Rejection Predictor (XGBoost)

**File:** `packages/agents/src/nodes/risk_assess.py`

**Part A — Feature engineering:**
```python
def extract_features(state: DeclarationState) -> dict:
    # Extract all 25 features from PRD §9.6
    # For cold start (no historical data): return default safe values
    # Flag: "cold_start_mode" = True if < 500 training samples
```

**Part B — Model loading:**
```python
import joblib
from pathlib import Path

def load_model() -> xgb.XGBClassifier | None:
    model_path = Path(settings.MINIO_MODELS_PATH) / "rejection_predictor" / "latest.pkl"
    if not model_path.exists():
        return None  # cold start: use rule-based heuristics
    return joblib.load(model_path)
```

**Part C — Rule-based heuristics (cold start):**
```python
def rule_based_rejection_risk(state: DeclarationState) -> dict:
    # Any CRITICAL_FAIL validation → HIGH risk (probability = 0.65)
    # WARNING + avg_confidence < 0.80 → MEDIUM risk (probability = 0.35)
    # All PASS + avg_confidence >= 0.85 → LOW risk (probability = 0.10)
    # Clearly label output as: "prediction_mode": "rule_based_cold_start"
```

**Part D — CRS computation (same node, see PRD §9.7):**
```python
def compute_crs(state: DeclarationState) -> dict:
    # 4-component weighted formula from PRD §9.7
    # Return: { score: float, grade: str, submit_recommended: bool, ... }
```

**Seeding:** `packages/db/seed/seed_synthetic_data.sql` must create 500+ synthetic `submission_outcomes` rows with realistic feature distributions for initial XGBoost training.

**Training script:** `eval/train_initial_model.py` — reads from DB, trains XGBoost, saves to MinIO.

✅ **Verify:** Load synthetic data → train model → AUC > 0.70 on held-out 20%. Model saved to storage. Prediction on test declaration returns dict with `rejection_probability`, `risk_level`, `top_rejection_reasons`.

### Step 3.4 — Adaptive Learning Engine

**File:** `packages/agents/src/nodes/learning.py`

Implement `AdaptiveLearningEngine` class with methods from PRD §9.8:
- `record_operator_correction()` → insert to `learning_samples`
- `record_ceisa_outcome()` → insert to `submission_outcomes`, trigger retraining if threshold
- `get_similar_past_submissions()` → query past batches by company/HS category, return top-5

Retraining trigger:
```python
def should_retrain() -> bool:
    # Count new submission_outcomes since last training
    # Return True if count >= 100 OR (days since last training >= 7 AND count > 0)
```

Retraining Celery task (`learning_tasks.py`): enqueued to `low` queue.

Model quality gate (see PRD §9.6): new model AUC must exceed `current_model_auc - 0.05`. If gate fails, keep current model, log alert to Sentry.

✅ **Verify:** Insert 10 mock corrections → `learning_samples` has 10 rows. Trigger retrain task manually → new model file appears in storage. Quality gate: mock a bad model (AUC=0.50) → gate rejects it.

---

## Phase 4 — Blockchain + CEISA Integration (Week 6)

> Read PRD §8 (Blockchain) and §16 (CEISA Integration) in full before starting.

### Step 4.1 — Smart contracts

**File:** `packages/blockchain/contracts/DocumentRegistry.sol`

Implement exactly from PRD §8. Key requirements:
- Uses `@openzeppelin/contracts 5.x` (Ownable, MerkleProof)
- `anchorDocument()` — single declaration
- `anchorBatch()` — Merkle batch for enterprise (gas efficient)
- `verifyDocument()` — pure view, returns (valid, timestamp)
- Events: `DocumentAnchored`, `SubmissionOutcomeRecorded`

```bash
cd packages/blockchain
pnpm hardhat compile
pnpm hardhat test    # must pass before deployment
```

✅ **Verify:** `npx hardhat test` — all contract tests pass. Gas estimate for `anchorDocument` < 100,000 units (per PRD §20 NFR).

### Step 4.2 — Deploy to Polygon Amoy

```bash
# Set POLYGON_AMOY_RPC_URL and PRIVATE_KEY in .env
npx hardhat run scripts/deploy.ts --network amoy
# Save deployed address to .env as CONTRACT_ADDRESS
```

GitHub Actions job `deploy-contracts-amoy` runs on `develop` branch push (see PRD §7).

✅ **Verify:** Contract address shows on https://amoy.polygonscan.com. Call `verifyDocument()` with non-existent hash → returns (false, 0).

### Step 4.3 — Blockchain service

**File:** `apps/api/src/services/blockchain_svc.py`

Implement `BlockchainAnchorService` from PRD §8 Python code:
1. Compute SHA-256 of each document (B/L, PL, Invoice payloads)
2. Build Merkle root of the three hashes
3. Compute full payload hash
4. Submit on-chain via contract (Web3.py 7.x, async via `asyncio.to_thread`)
5. Pin metadata to IPFS via Pinata SDK 2.x
6. Return `BlockchainReceipt` dataclass

Feature flag: `ENABLE_BLOCKCHAIN=false` → skip anchoring, return mock receipt. System must not fail if blockchain is down.

Wallet management: private key read from `settings.BLOCKCHAIN_PRIVATE_KEY` (from Doppler). Never log this value.

✅ **Verify:** Call `anchor_declaration()` with test payload → tx_hash returned. Query Polygonscan API → tx confirmed. IPFS CID resolvable via `https://gateway.pinata.cloud/ipfs/{cid}`.

### Step 4.4 — CEISA Simulator

**File:** `apps/simulator/src/main.py`

Implement all 6 scenarios from PRD §17 exactly. Key requirements:
- Scenarios stored in `state.py` (in-memory, reset on restart)
- `PUT /simulator/scenarios/active` — switch scenario in real time (for demo)
- `GET /simulator/logs` — last 100 requests with full detail
- Each submission gets a CDO number: `CDP-2026-{5-digit-zero-padded-counter}`
- For timeout scenario: use `asyncio.sleep(35)` before responding
- For rejection scenarios: randomly select based on probability (use `random.random()`)

✅ **Verify:** Switch to S04 (timeout) → POST submission → response arrives after ~35s. Switch to S02 → POST 10 submissions → ~3 are rejected with E004. `GET /simulator/logs` shows all 10.

### Step 4.5 — CEISA Gateway service

**File:** `apps/api/src/services/ceisa_gateway.py`

Implement H2H client with:
1. Auth: POST to CEISA auth endpoint → cache token (refresh 5min before expiry)
2. Submit: POST declaration payload with `X-Idempotency-Key` header
3. Retry logic: exponential backoff per PRD §16 config (5 attempts, jitter)
4. Circuit breaker: `circuitbreaker` Python library — open after 3 failures, reset after 60s
5. Response parsing: map CEISA error codes to `CEISA_ERROR_CODES` dict (PRD §16)
6. Auto-fix handlers: for `AUTO_RECOVERABLE` errors (E007 date format, E019 country code)
7. Dead letter queue: after max retries → route to `dlq` Celery queue → alert Sentry

**File:** `apps/api/src/tasks/submit_tasks.py`:
```python
@app.task(bind=True, max_retries=5, queue='high')
def submit_to_ceisa(self, batch_id: str, submission_id: str):
    ...
```

✅ **Verify:** Against simulator S01 → submission accepted, `ceisa_submissions.status='accepted'`. Against S04 (timeout) → retry logic fires, all 5 attempts logged, circuit breaker opens after 3rd failure. Against S02 (E004) → OPERATOR_REQUIRED classification, review screen triggered.

---

## Phase 5 — Dashboard & Realtime (Week 7)

> Read `DESIGN.md` in full before starting this phase. All component visual specs come from DESIGN.md. PRD §13 (Dashboard) + §14 (State Machines) cover the logic.

### Step 5.1 — Supabase Realtime subscriptions

**File:** `apps/web/src/lib/supabase.ts`

```typescript
export function subscribeToBatch(batchId: string, onUpdate: (batch: Batch) => void) {
  return supabase
    .channel(`batch:${batchId}`)
    .on('postgres_changes', {
      event: 'UPDATE', schema: 'public', table: 'batches',
      filter: `id=eq.${batchId}`
    }, payload => onUpdate(payload.new as Batch))
    .subscribe()
}

export function subscribeToExtractedFields(batchId: string, onInsert: ...) { ... }
```

**File:** `apps/web/src/stores/batchStore.ts` — Zustand store:
```typescript
// Tracks: currentBatch, extractedFields, validationResults, processingStatus
// subscribeToRealtime(batchId) — starts Supabase subscription, updates store
// cleanup() — unsubscribes on unmount
```

✅ **Verify:** Open review page → start processing → batch status updates live in UI without page refresh. Field confidence badges appear as extraction completes.

### Step 5.2 — Operator Review screen

**Files:**
- `apps/web/src/components/review/ReviewScreen.tsx` — layout container
- `apps/web/src/components/review/DocumentViewer.tsx` — PDF.js wrapper
- `apps/web/src/components/review/BoundingBoxOverlay.tsx` — canvas overlay
- `apps/web/src/components/review/FieldsPanel.tsx` — extracted fields form
- `apps/web/src/components/review/LineItemsGrid.tsx` — TanStack Table for PL rows
- `apps/web/src/components/review/CRSWidget.tsx` — live CRS display
- `apps/web/src/components/review/RejectionRiskWidget.tsx`
- `apps/web/src/components/review/AICopiloPanel.tsx` — streaming AI suggestions
- `apps/web/src/components/review/BlockchainStatusWidget.tsx`

Refer to DESIGN.md for:
- Exact split ratio (60/40)
- Confidence badge colors (must match DESIGN.md spec exactly)
- Tooltip content format
- Submit button disabled state logic
- Bounding box highlight color and animation

Field correction flow:
1. User clicks field → opens inline edit
2. User edits value + selects correction reason
3. `PATCH /api/v1/batches/{id}/fields` called
4. `learning_samples` row created
5. CRS widget re-computes live (optimistic update)
6. Audit log entry created server-side

✅ **Verify:** Load review screen with test batch. Click low-confidence field → document viewer jumps to that region and highlights bounding box. Edit field → CRS score updates. Submit button disabled if any CRITICAL_FAIL unresolved.

### Step 5.3 — SME Upload Wizard

**Files:**
- `apps/web/src/components/wizard/UploadWizard.tsx`
- `apps/web/src/components/wizard/WizardStep.tsx`
- `apps/web/src/components/wizard/HSCodeWizard.tsx`

Refer to DESIGN.md for wizard step visual design and mobile layout.

Each step shows: what the document is, where to find it, example thumbnail, drag-drop zone + camera capture button (mobile).

`HSCodeWizard`: free-text input → call `POST /api/v1/hs-recommend` → display top-3 as selectable cards showing HS code, description, duty rate, VAT rate.

✅ **Verify:** Complete wizard on mobile viewport (375px) — all steps usable without horizontal scroll. HS Code wizard returns and displays 3 suggestions.

### Step 5.4 — CEISA Simulator Control Panel

**File:** `apps/web/src/components/simulator/SimulatorPanel.tsx`

Components:
- Scenario selector (6 buttons, active scenario highlighted)
- Request log table: timestamp, method, status, latency, importir, CDO/error code
- JSON inspector modal: click any log row → full request/response JSON
- Stats bar: total processed, acceptance rate, avg latency
- "Reset" button → `DELETE /simulator/logs`

Polling: `GET /simulator/logs` every 2s when panel is open (or WebSocket if implemented).

✅ **Verify:** Open simulator panel → switch scenario to S02 → process a submission → log entry appears within 3s showing rejection with E004. Click log entry → JSON inspector shows full payload.

### Step 5.5 — Admin Analytics Dashboard

**File:** `apps/web/src/app/(dashboard)/analytics/page.tsx`

Components (see DESIGN.md for chart specs):
- 4 KPI cards: Declarations today, Avg CRS, Success rate, Avg processing time
- `<LineChart>` (Recharts): daily submission volume 30-day trend
- `<BarChart>` (Recharts): top rejection reasons
- Operator performance table (TanStack Table)
- Field accuracy heatmap (each CEISA field vs correction rate)
- Learning engine panel: predictor AUC, training size, drift alerts, manual retrain button

Route guard: `require_admin()` dependency. SME users see 403 page.

✅ **Verify:** Admin user sees all charts with seeded data. Operator user (non-admin) gets 403. "Trigger Retrain" button enqueues Celery task (verify in Redis).

### Step 5.6 — Notification system

**File:** `apps/api/src/services/notification_svc.py`

```python
class NotificationService:
    async def send_ceisa_accepted(self, batch_id, ceisa_reference, user): ...
    async def send_ceisa_rejected(self, batch_id, error_codes, user): ...
    async def send_review_needed(self, batch_id, low_confidence_count, operator): ...

# Email: Resend API (resend-python SDK)
# WhatsApp: WhatsApp Cloud API (direct httpx calls, no SDK)
# WhatsApp message template: pre-approved template "customs_status_update"
```

Supabase Edge Function `notify-operator/index.ts` — triggered by Supabase Realtime on batch status change. Calls FastAPI notification endpoint.

✅ **Verify:** Process a batch to accepted state → email notification sent (check Resend dashboard). WhatsApp notification sent (check WhatsApp test number). Template variables correctly substituted.

---

## Phase 6 — Observability & Evaluation (Week 8 Start)

### Step 6.1 — OpenTelemetry + LangSmith

**File:** `apps/api/src/main.py` — add OTel instrumentation:
```python
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor

FastAPIInstrumentor().instrument_app(app)
CeleryInstrumentor().instrument()
```

LangSmith: set `LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_PROJECT=tradeflow-ai`. Every LLM call auto-traced. Add custom tags per PRD §9.3.

Sentry: `sentry_sdk.init(dsn=..., traces_sample_rate=0.2, profiles_sample_rate=0.1)`.

PostHog: track funnel events (`document_uploaded → ocr_complete → review_started → field_corrected → submission_sent → ceisa_accepted`).

✅ **Verify:** Process test batch → LangSmith shows full LLM trace with token counts. Sentry receives test error. PostHog funnel shows event sequence.

### Step 6.2 — Prometheus metrics + Grafana

Add Prometheus to docker-compose. Expose `/metrics` on FastAPI via `prometheus-fastapi-instrumentator`.

Implement all custom metrics from PRD §22:
```python
tradeflow_ocr_duration_seconds   = Histogram(...)
tradeflow_extraction_confidence  = Histogram(...)
tradeflow_ceisa_submission_total = Counter(...)
tradeflow_rejection_prediction_auc = Gauge(...)
tradeflow_crs_distribution       = Histogram(...)
tradeflow_llm_tokens_total       = Counter(...)
tradeflow_blockchain_tx_duration = Histogram(...)
tradeflow_queue_depth            = Gauge(...)
```

Grafana dashboard: import `infra/grafana/tradeflow-dashboard.json` (create this JSON from Grafana UI, export, commit).

✅ **Verify:** `http://localhost:9090` (Prometheus) — all `tradeflow_*` metrics scraped. Grafana shows non-zero values after test run.

### Step 6.3 — AI evaluation framework

**File:** `eval/run_eval.py`

```python
# Run against all 15 fixtures in eval/fixtures/
# For each fixture: process through full pipeline → compare to expected.json

METRICS = {
    "field_extraction_accuracy": {"target": 0.92, "actual": None},
    "hs_recommendation_top1_accuracy": {"target": 0.75, "actual": None},
    "cross_doc_validation_recall": {"target": 0.95, "actual": None},
    "processing_time_p95_cpu_seconds": {"target": 45, "actual": None}
}

# CI gate: compare actual vs baseline stored in eval/baseline_metrics.json
# If any metric drops > 5% from baseline → sys.exit(1) (blocks PR merge)
```

Add `eval-ai` job to `.github/workflows/ci.yml`:
```yaml
eval-ai:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - run: uv run python eval/run_eval.py
    - run: uv run python eval/check_regression.py
```

✅ **Verify:** Run locally → all 4 metrics computed. Introduce deliberate bug (lower OCR confidence threshold) → regression check fails and exits with code 1.

---

## Phase 7 — Polish & Demo Prep (Week 8 End)

### Step 7.1 — Evaluation dataset (15 synthetic CIPL sets)

Create `eval/fixtures/01` through `eval/fixtures/15` (see PRD Appendix A for the full list).

For each fixture:
- `docs/` — the actual document files (PDF/XLSX/image)
- `expected.json` — ground truth CEISA fields JSON

Use Gemini API to generate synthetic document content. Use Python's `reportlab` or `fpdf2` to generate synthetic PDFs. Ensure fixture 15 has a deliberate cross-doc inconsistency for validation testing.

✅ **Verify:** `eval/run_eval.py` completes without errors against all 15 fixtures. Eval metrics output to stdout.

### Step 7.2 — Demo flow script

**File:** `docs/DEMO_SCRIPT.md`

Document the exact demo flow that takes < 90 seconds:
1. [0:00] Open dashboard as Enterprise Operator
2. [0:05] Upload batch (fixture 01 — clean digital PDFs)
3. [0:07] Processing starts — live progress visible
4. [0:35] Review screen opens — show confidence badges, bounding box highlights
5. [0:45] Show CRS score (A grade), rejection risk (LOW)
6. [0:50] Click submit → show pre-submit checklist → confirm
7. [0:55] Switch simulator to S02 (show rejection), wait for rejection
8. [1:05] Show auto-recovery / operator fix flow
9. [1:15] Switch back to S01, resubmit → accepted
10. [1:20] Show blockchain widget → Polygonscan link

Also prepare: SME wizard demo (2 min), admin analytics demo (1 min), simulator scenario switching demo (30s).

### Step 7.3 — Performance optimization

Profile the following and optimize until P95 targets met (PRD §20):
- OCR pipeline: run PaddleOCR in subprocess pool if CPU-bound
- LLM calls: run B/L, PL, Invoice extraction in parallel (LangGraph parallel edges)
- Database: ensure all FK columns are indexed; add `EXPLAIN ANALYZE` on heavy queries
- Frontend: bundle analyzer (`pnpm build --analyze`) — fix large chunks

✅ **Verify:** Process `eval/fixtures/06` (80-item complex PL) on CPU. Assert P95 < 45s. Run `pnpm build` — largest chunk < 200KB gzipped.

### Step 7.4 — Production deploy

```bash
# Vercel (frontend)
vercel deploy --prod

# Railway (API + worker)
railway up --service api --replicas 2
railway up --service worker --replicas 3

# Supabase (migrations)
supabase db push --project-ref ${PROD_SUPABASE_REF}
```

Verify all env vars in production via Doppler. Verify Keycloak realm imported. Verify ChromaDB BTKI collection seeded. Verify XGBoost initial model deployed to storage.

✅ **Final verify:** Full E2E test against production URL. Upload fixture 01 → process → review → submit → CEISA accepted (simulator). Blockchain anchored. Email notification received.

---

## Quick Reference

### PRD Section Cross-Reference

| You're building... | Read PRD section |
|-------------------|-----------------|
| Auth / JWT flow | §4 Decision 2, §22 env vars |
| LangGraph graph structure | §4 Decision 1 (full graph diagram + DeclarationState) |
| Database schema | §11 (complete SQL) |
| API endpoints | §12 (API Contracts) |
| Batch status transitions | §14 (State Machines) |
| OCR pipeline details | §9.1, §9.2, §9.3 |
| Cross-doc validation rules | §9.4 (JSON rules file) |
| HS Code RAG pipeline | §9.5 |
| Rejection predictor features | §9.6 (25 features, thresholds) |
| CRS formula | §9.7 |
| CEISA retry logic | §16 (Retry Policy Config) |
| CEISA error codes | §16 (Error Code Dictionary) |
| Simulator scenarios | §17 (all 6 scenarios + response formats) |
| UI component tree | §13 (Component Architecture) |
| UI routes | §13 (Routes table) |
| SME vs Enterprise features | §19 (Feature Matrix table) |
| Feature flags | §22 (all env vars) |
| Eval metrics & CI gate | §22 (Automated Evaluation) |
| Smart contracts | §8 (Solidity + Python anchor code) |
| Blockchain service | §8 (blockchain_svc/anchor.py) |
| MCP config | §5 (.mcp.json full config) |
| Docker Compose | §7 |
| CI/CD pipelines | §7 (GitHub Actions yaml) |
| NFRs & latency targets | §20 |

### DESIGN.md Reference Points

Read DESIGN.md for every component before implementing:
- Color system and design tokens
- ReviewScreen layout exact spec
- ConfidenceBadge visual spec (colors, shapes, animation)
- CRS widget visual design
- SME wizard step layout
- Mobile breakpoints
- Chart color palette
- Typography scale

### Key Invariants (Never Break These)

1. **Keycloak is the only auth provider.** Do not use Supabase Auth for login.
2. **audit_log is append-only.** Never issue UPDATE/DELETE on this table from application code.
3. **Every LLM call is traced in LangSmith.** Never call Gemini API without tagging.
4. **Idempotency key is per-attempt.** Each re-submission gets a new UUID.
5. **Feature flags must be respected.** If `ENABLE_BLOCKCHAIN=false`, system runs fully without it.
6. **Validation rules are hot-reloadable.** Never hardcode rule logic — always read from `validation_rules.json`.
7. **CRS must recompute on every operator correction.** UI must feel live.
8. **Simulator must be indistinguishable from CEISA API** from the perspective of `ceisa_gateway.py`.

### Testing Strategy per Layer

| Layer | Framework | Minimum Coverage |
|-------|-----------|-----------------|
| Python unit tests | pytest + pytest-asyncio | 70% (AI modules) |
| Python type checking | mypy --strict | 100% (no `Any` escapes) |
| Frontend unit tests | Vitest | 60% |
| Frontend type checking | tsc --noEmit | 100% |
| Smart contracts | Hardhat + Chai | 100% (all functions) |
| E2E smoke test | Playwright | 1 critical path |
| AI accuracy | Custom eval framework | All 4 metrics ≥ target |

---

*Built against: PRD_TradeFlowAI_v4.md + DESIGN.md*  
*Challenge: AI Open Innovation Challenge 2026 — Cikarang Dry Port Track*
