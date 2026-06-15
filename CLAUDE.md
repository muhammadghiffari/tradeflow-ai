# TradeFlow AI — Agent Instructions
> This file is the single entry point for every AI coding agent working on this repo.
> Read this file completely before touching any code. Do not skip sections.

---

## 0. What You Are Building

**TradeFlow AI** — a customs declaration automation platform for Cikarang Dry Port (CDP), Indonesia.
It reads CIPL shipping documents (Bill of Lading, Packing List, Commercial Invoice), extracts structured data via a multi-agent OCR ensemble, validates against CEISA 4.0 schema, and submits PIB import declarations to the Indonesian customs system via H2H API.

**Authoritative spec files (read in this order for any task):**
```
docs/TradeFlow_PRD_v5.2.md   — WHAT to build and WHY (product requirements)
docs/TradeFlow_SRS_v5.2.md   — HOW it must behave (testable requirements FR-001 to FR-127)
docs/TradeFlow_SDD_v5.2.md   — HOW to implement it (architecture, schemas, code patterns)
docs/TradeFlow_GroundTruth_v5.2.json — ground truth for the 8 real carrier B/L documents
TASKS.md                     — task checklist (mark [x] as you complete each task)
```

**Before starting any task:** open `TASKS.md`, find the task, read the SRS requirement numbers it references, read those requirements in the SRS, read the corresponding SDD section, then implement.

---

## 1. Non-Negotiable Invariants

These are enforced at PR review. Breaking any of them means the PR is rejected:

1. **No bare `os.getenv()`** — all env vars through `apps/api/src/config.py` (pydantic-settings)
2. **No model weights in Docker images** — weights download at container startup from HuggingFace Hub
3. **Audit log is append-only** — never add UPDATE/DELETE on `audit_log` table
4. **Keycloak is the only auth provider** — never use Supabase Auth for login
5. **LangGraph must pause at `interrupt_before=["submit"]`** — HitL is mandatory
6. **CEISA submission requires NIB (13 digits) + NPWP** — both fields mandatory, no exceptions
7. **Validation rules load from `packages/db/validation_rules.json`** — never hardcode CV rules in Python
8. **All OCR agent failures are non-fatal** — pipeline continues with remaining agents (FR-015, FR-016)
9. **Azure DI free tier quota tracked in Redis** — key: `azure_di:pages_used:{YYYY-MM}` (FR-018)
10. **T&C and demurrage pages are skipped** — never pass to OCR agents (FR-116)

---

## 2. Monorepo Structure

```
tradeflow-ai/
├── CLAUDE.md                     ← you are here
├── TASKS.md                      ← your checklist
├── docs/                         ← spec files (read-only for agent)
├── apps/
│   ├── api/                      ← FastAPI backend
│   ├── web/                      ← Next.js 16 frontend
│   ├── surya-svc/                ← Surya 2 OCR (Agent A)
│   ├── olm-inference/            ← olmOCR-2-7B-CIPL (Agent D)
│   ├── paddleocr-svc/            ← PaddleOCR 3.0 (Agent B + fast path)
│   ├── mineru-svc/               ← MinerU 2.5 preprocessing
│   └── simulator/                ← CEISA 4.0 PIA simulator
├── packages/
│   ├── agents/                   ← LangGraph nodes and graph
│   ├── shared-types/             ← Zod schemas (shared Next.js ↔ FastAPI)
│   └── db/                       ← Migrations, seeds, validation_rules.json, carrier_profiles.json
├── contracts/                    ← Solidity (DocumentRegistry.sol)
├── eval/
│   └── fixtures/                 ← 8 real B/L docs + ground truth JSON
├── tools/                        ← synthetic data generator, eval scripts
├── .github/workflows/            ← CI/CD
└── docker-compose.yml
```

---

## 3. Technology Decisions (Final — Do Not Deviate)

| Layer | Choice | Version | Notes |
|---|---|---|---|
| API | FastAPI | 0.115.x | Python 3.13, Uvicorn |
| Package mgr (Python) | uv | 0.5.x | Use `uv add`, never `pip install` directly in app code |
| Package mgr (JS) | pnpm | 9.x | Use pnpm workspaces |
| Auth | Keycloak 26 | 26.1.x | Only OIDC provider |
| Database | Supabase PostgreSQL 17 | — | RLS via Keycloak JWT |
| Queue | Celery 5.5 + Redis 8 | — | RESP3 native, NOT Upstash |
| Agents | LangGraph 0.3+ | — | Redis checkpointer (not in-memory) |
| OCR Agent A | Surya 2 | latest | via vLLM |
| OCR Agent B | PaddleOCR 3.0 | 3.0.x | PP-StructureV3 + PP-ChatOCRv4 |
| OCR Agent C | Azure DI 4.0 | 1.0.x | Parallel agent, NOT fallback only |
| OCR Agent D | olmOCR-2-7B-CIPL | fine-tuned | via vLLM + LoRA |
| Frontend | Next.js 16 | 16.2.x | App Router, Turbopack |
| Styling | Tailwind CSS 4.1 | — | |
| Real-time | Supabase Realtime (CDC) + Socket.io 4.8 | — | Both required |
| Blockchain | Polygon Amoy testnet | — | ethers 6.x, web3.py 7.x |
| Vector DB | ChromaDB 0.6 | — | HS code RAG |
| ML | XGBoost 2.1 | — | Rejection predictor |

---

## 4. Environment Variables

Never hardcode secrets. All env vars are defined in `apps/api/src/config.py` (pydantic-settings).
For local dev, copy `.env.example` to `.env`. For production, use Doppler.

Key variables the agent must reference (never invent new names):
```
# AI services
SURYA_INFERENCE_URL          # http://surya-svc:8001
OLM_INFERENCE_URL            # http://olm-inference:8000
OLM_BASE_MODEL               # allenai/olmOCR-2-7B-1025
OLM_LORA_ADAPTER             # muhammadghiffari/olm-ocr-cipl-v1
PADDLEOCR_SVC_URL            # http://paddleocr-svc:8002
MINERU_SVC_URL               # http://mineru-svc:8003
AZURE_DI_ENDPOINT
AZURE_DI_KEY
AZURE_DI_FREE_LIMIT          # 5000

# CEISA (competition: simulator URL)
CEISA_BASE_URL               # http://ceisa-simulator:8001
CEISA_CLIENT_ID
CEISA_CLIENT_SECRET

# Feature flags
ENABLE_SURYA_AGENT           # true
ENABLE_AZURE_DI_AGENT        # true
ENABLE_VESSEL_VALIDATION     # true
ENABLE_BLOCKCHAIN            # true
ENABLE_INSW_CHECK            # true
```

Full list in `docs/TradeFlow_PRD_v5.2.md §22`.

---

## 5. Database Rules

- All migrations go in `packages/db/migrations/` with format `YYYYMMDD_NNN_description.sql`
- Never modify existing migration files — create new ones
- RLS policies are mandatory on all tables containing company data
- The `audit_log` table has `REVOKE UPDATE, DELETE, TRUNCATE` — never remove this
- `validation_rules.json` is the source of truth for CV001–CV011 and XGBoost fallback rules

Schema is fully defined in `docs/TradeFlow_SDD_v5.2.md §3`.

---

## 6. API Contract Rules

All endpoints match the specification in `docs/TradeFlow_SRS_v5.2.md` and `docs/TradeFlow_SDD_v5.2.md §4`.
Never add endpoints not in the spec without updating TASKS.md first.
Response schemas use Pydantic models from `apps/api/src/schemas/`.
Shared types (used by both FastAPI and Next.js) live in `packages/shared-types/` as Zod schemas.

---

## 7. LangGraph Agent Graph

The full graph definition is in `docs/TradeFlow_SDD_v5.2.md §2.2`.
Node execution order:
```
ingest → preprocess → multi_ocr → reconcile → vessel_validate
→ validate → [hs_recommend] → risk_assess → review_ready
→ [CHECKPOINT] → build_payload → insw_check → submit
→ poll_status → record_outcome
```
`blockchain_anchor` runs as a parallel branch from `risk_assess` (not sequential).
The graph MUST compile with `interrupt_before=["submit"]`. Test this in CI.

---

## 8. OCR Agent Rules

All four agents run via `asyncio.gather` — parallel, not sequential.
Agent failure handling (from FR-015, FR-016):
- 1–2 agents fail → log warning, continue with remaining
- 3+ agents fail → raise RuntimeError → batch status = ERROR → admin alert
- Azure DI near quota → skip gracefully, do not crash

Confidence reconciliation rules are in `docs/TradeFlow_SDD_v5.2.md §5.2`.
The reconciliation logic is deterministic — never randomize confidence scores.

---

## 9. Carrier-Specific Rules (v5.2)

The 8 real carrier documents revealed patterns the agent MUST handle:

| Issue | Rule |
|---|---|
| Container numbers with spaces | Normalize to ISO 6346 (4α+7d, no space) |
| HS codes with dots (8482.10.00) | Strip dots, take 8 digits → 84821000 |
| 7 different date formats | All normalize to YYYY-MM-DD (see normalizers.py) |
| Weight in MTS (Evergreen) | Multiply ×1000 to get KGS |
| Weight with comma separator (Maersk) | Strip comma before parsing |
| T&C pages (Cordelia page 2) | Detect by "1. DEFINITIONS" signal → skip |
| Demurrage pages (Hapag page 3) | Detect by "SSHINC"+"USD/TEU/DAY" → skip |
| Watermarks (DRAFT/ORIGINAL/PROOFREAD/READ) | Remove via cv2.inpaint before OCR |

All normalizers implemented in `packages/agents/src/validators/field_normalizers.py`.
Carrier profiles in `packages/db/carrier_profiles.json` (5 SCACs: HLCU, MSCU, MAEU, EGLV, CSLU).

---

## 10. How to Use This File With AI Agents

### Claude Code
```bash
# Start a session pointing to this repo
claude --project /path/to/tradeflow-ai

# Agent reads CLAUDE.md automatically on startup
# For specific tasks, reference TASKS.md directly:
claude "Complete task T-024 from TASKS.md"
```

### Cursor / Windsurf
Add to `.cursorrules` or `.windsurfrules`:
```
Always read CLAUDE.md before starting any task.
Always read TASKS.md and mark tasks complete as you finish them.
Always reference the SRS requirement number in your commit message.
```

### Any agent via system prompt
```
You are a senior engineer building TradeFlow AI.
Before any task: read CLAUDE.md completely.
Check TASKS.md for what needs to be done.
For each task, read the referenced SRS requirement numbers before writing code.
Mark tasks [x] in TASKS.md when complete.
Write tests that reference the SRS requirement ID in the test name.
```

---

## 11. Testing Rules

- Unit tests: `pytest` for Python, `vitest` for TypeScript
- Test naming convention: `test_FR{requirement_number}_{description}`
  - Example: `test_FR120_container_number_normalization_removes_space`
- Every SRS functional requirement (FR-001 to FR-127) must have at least one test
- CI gate: tests must pass before any merge to main
- Eval gate: `tools/run_eval.py` must pass all metrics in `docs/TradeFlow_SRS_v5.2.md §23`

---

## 12. Commit Message Format

```
[TASK-ID] Brief description (FR-XXX)

- What was implemented
- Which SRS requirements are now satisfied
- Any deviations from spec and why
```

Example:
```
[T-031] Add watermark removal to preprocessing pipeline (FR-111, FR-112, FR-113)

- Implemented remove_watermarks() in field_normalizers.py
- Handles DRAFT, ORIGINAL, PROOFREAD, READ watermark types
- Uses cv2.inpaint(INPAINT_TELEA, radius=7)
- All 8 real carrier docs pass watermark removal test
```
