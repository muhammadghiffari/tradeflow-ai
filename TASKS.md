# TradeFlow AI — Agent Task Checklist
> **How to use:** Find your task, read the referenced SRS FR numbers, read the corresponding SDD section, implement, mark `[x]`.  
> **Commit format:** `[T-NNN] Description (FR-XXX, FR-YYY)`  
> **Never skip** the FR read — requirements contain edge cases that aren't obvious from the task title alone.

---

## Status Legend
- `[ ]` Not started
- `[~]` In progress  
- `[x]` Complete + tested
- `[!]` Blocked (add reason inline)

---

## Week 1–2: Foundation

### Infrastructure
- [ ] **T-001** Init Turborepo monorepo, pnpm workspaces, `turbo.json` pipeline  
  _SDD §1.1 | No FR — structural_
- [ ] **T-002** Write `docker-compose.yml` — all 14 services, shared `model_cache` volume, no weights baked in images  
  _SDD §8 | Invariant #2_
- [ ] **T-003** Write `.env.example` with all 50+ env vars from PRD §22 (no real secrets)  
  _PRD §22 | Invariant #1_
- [ ] **T-004** Write `apps/api/src/config.py` using pydantic-settings — every env var, no bare `os.getenv()` anywhere  
  _SDD §2.1 | Invariant #1_
- [ ] **T-005** Write `.github/workflows/build-and-push.yml` — GitHub Actions, matrix build for all 8 services, GHCR push  
  _SDD §7 (CI/CD section)_
- [ ] **T-006** Write Dockerfiles for all services — code only, `HF_HUB_CACHE=/data/models`, weights downloaded at startup  
  _SDD §2.3–2.6 | Invariant #2_

### Keycloak + Auth
- [ ] **T-007** Deploy Keycloak 26 in docker-compose, create realm `tradeflow`, client `tradeflow-api`, roles: `operator`, `sme`, `admin`  
  _SDD §6.1 | FR-092_
- [ ] **T-008** Write `apps/api/src/auth/keycloak.py` — JWT validation via JWKS, cache JWKS with 5-minute TTL  
  _SDD §6.1 | FR-093_
- [ ] **T-009** Write `apps/api/src/auth/dependencies.py` — FastAPI `Depends(get_current_user)`, role-based guards  
  _SRS §3.17 | FR-094, FR-095_
- [ ] **T-010** Configure next-auth 5.x in `apps/web` with Keycloak OIDC provider, session in httpOnly cookie  
  _SDD §7.2 | FR-096_

### Database
- [ ] **T-011** Write migration `20260501_001_init_schema.sql` — all enums, all core tables, indexes, RLS policies  
  _SDD §3 | FR-013, DR-001 to DR-012_
- [ ] **T-012** Write migration `20260522_004_add_maritime_tables.sql` — AIS, vessel_characteristics, vessel_ownership, port_lineup  
  _SDD §3 | DR-009 to DR-012_
- [ ] **T-013** Write migration `20260529_005_add_agent_outputs.sql` — `agent_outputs JSONB`, `agent_disagreement BOOL`, `vessel_validation_status` on batches  
  _SDD §3 | FR-023, FR-031_
- [ ] **T-014** Seed maritime data: load `AIS_Data_Sample.csv` → `ais_vessel_positions`, `Website_Vessel_Characteristics_Sample.xlsx` → `vessel_characteristics`, `Ownership_-_Website_Data_Sample.xlsx` → `vessel_ownership`, `Lineup_Data_Sample.csv` → `port_lineup`  
  _PRD §10.8 | FR-025_
- [ ] **T-015** Seed BTKI HS codes: download from djbc.kemenkeu.go.id, insert ~10,000 rows into `btki_hs_codes` table, run OpenAI embeddings, load into ChromaDB collection `btki_hs_codes`  
  _PRD §11.5 | FR-040_
- [ ] **T-016** Write `packages/db/validation_rules.json` — CV001–CV011 + `xgboost_fallback_rules` block  
  _PRD §11.5 | FR-033, FR-034, FR-035, FR-045_
- [ ] **T-017** Write `packages/db/carrier_profiles.json` — 5 SCACs: HLCU, MSCU, MAEU, EGLV, CSLU  
  _SDD §10.1 | FR-118, FR-119_

### MCP Configuration
- [ ] **T-018** Write `mcp.json` — GitHub, Supabase, Linear, Sentry, Vercel, PostHog connectors  
  _PRD §9_

---

## Week 3: OCR Services + Model Training

### MinerU Preprocessing Service
- [ ] **T-019** Write `apps/mineru-svc/serve.py` — FastAPI, PDF→images at 300 DPI (PyMuPDF), text layer detection, quality scoring, `GET /health`  
  _SDD §2.6 | FR-009, FR-010, FR-012_
- [ ] **T-020** Implement image enhancement pipeline in preprocessing — CLAHE, deskew (Hough), denoise, binarization, border removal  
  _SRS §3.2 | FR-011_
- [ ] **T-021** Implement watermark removal — detect DRAFT/ORIGINAL/PROOFREAD/READ via HSV color range, `cv2.inpaint(INPAINT_TELEA, radius=7)`  
  _SRS §9.1 | FR-111, FR-112, FR-113_
- [ ] **T-022** Implement page type classification — MAIN/ATTACHMENT/TERMS_AND_CONDITIONS/DEMURRAGE_SCHEDULE  
  _SRS §9.2 | FR-114, FR-115, FR-116, FR-117_
- [ ] **T-023** Implement carrier SCAC detection — BL number prefix, header text, carrier name  
  _SRS §9.3 | FR-118, FR-119_

### Surya 2 Service (Agent A)
- [x] **T-024** Write `apps/surya-svc/serve.py` — FastAPI, load Surya 2 at startup (models from HF Hub), `POST /extract` → HTML + text blocks + layout, `GET /health`  
  _SDD §2.3 | FR-014 (Agent A)_

### PaddleOCR Service (Agent B + fast path)
- [x] **T-025** Write `apps/paddleocr-svc/serve.py` — PP-StructureV3 for layout+bboxes (`POST /extract`), PP-ChatOCRv4 for fast KIE (`POST /kia`), `GET /health`  
  _SDD §2.5 | FR-014 (Agent B), FR-017_

### olmOCR Inference Service (Agent D)
- [x] **T-026** Write `apps/olm-inference/download_adapter.py` — pull LoRA adapter from HuggingFace Hub at startup if not cached  
  _SDD §2.4 | Invariant #2_
- [x] **T-027** Write `apps/olm-inference/serve.py` — launch vLLM with `--enable-lora`, adapter `cipl_adapter`, `bfloat16`, `gpu_memory_utilization=0.85`  
  _SDD §2.4 | FR-014 (Agent D)_

### Kaggle Training Notebooks (NOT run locally)
- [x] **T-028** Write `tools/kaggle/nb1_synthetic_generator.ipynb` — Faker + real carrier templates, 1,500 CIPL triples, augmentation (blur/skew/noise/stain)  
  _PRD §10.2, §10.4 | Reason 2 fix_
- [x] **T-029** Write `tools/kaggle/nb2_chromadb_index.ipynb` — BTKI embedding + ChromaDB load  
  _PRD §10.6_
- [x] **T-030** Write `tools/kaggle/nb3_olm_finetune.ipynb` — Unsloth + FastVisionModel + olmOCR-2-7B base + QLoRA rank=32 + `hub_strategy=every_save`  
  _PRD §10.4 | NFR-009_
- [x] **T-031** Write `tools/kaggle/nb4_eval.ipynb` — run all 20 eval fixtures, compare zero-shot vs fine-tuned, assert all SRS §23 metrics  
  _PRD §10.5 | NFR-007 to NFR-010_
- [x] **T-032** Write `tools/kaggle/nb5_xgboost.ipynb` — train on 500 synthetic labeled submissions, serialize to `xgboost_rejection_v1.json`  
  _PRD §11.7 | NFR-013_

---

## Week 4: Multi-Agent OCR Core

### LangGraph State + Graph
- [x] **T-033** Write `packages/agents/src/state.py` — `DeclarationState` TypedDict with all fields from SDD §2.2  
  _SDD §2.2_
- [x] **T-034** Write `packages/agents/src/graph.py` — full LangGraph graph, `interrupt_before=["submit"]`, Redis checkpointer  
  _SDD §2.2 | Invariant #5, CN-005_

### Preprocessing Node
- [x] **T-035** Write `packages/agents/src/nodes/preprocess.py` — calls mineru-svc, runs SCAC detection + page classification + watermark removal + image enhancement  
  _SDD §10.4 | FR-009–FR-023_

### Multi-Agent OCR Node
- [x] **T-036** Write `packages/agents/src/nodes/multi_ocr_agent.py` — `asyncio.gather` for Agents A/B/C/D, per-agent timeout=20s, failure counting, Azure quota check  
  _SDD §5.1 | FR-014, FR-015, FR-016, FR-017, FR-018_
- [x] **T-037** Write per-agent HTTP clients: `surya_client.py`, `paddleocr_client.py`, `azure_di_client.py`, `olm_client.py`  
  _SDD §2.2 | FR-014_
- [x] **T-038** Write `apps/api/src/services/azure_quota_svc.py` — Redis counter `azure_di:pages_used:{YYYY-MM}`, check + increment  
  _SRS §3.3 | FR-018_

### Confidence Reconciliation Node
- [x] **T-039** Write `packages/agents/src/nodes/reconciliation_agent.py` — majority vote, rule-validated fields, disagreement flagging, `agent_agreement_rate`  
  _SDD §5.2 | FR-019, FR-020, FR-021, FR-022, FR-023, FR-024_

### Field Validators + Normalizers
- [x] **T-040** Write `packages/agents/src/validators/field_validators.py` — NPWP checksum (modulo-11), NIB 13-digit, UN/LOCODE, ISO 8601, ISO 4217  
  _SRS §3.4 | FR-020_
- [x] **T-041** Write `packages/agents/src/validators/field_normalizers.py` — container ISO 6346, HS dot-notation, 7 date formats, weight unit conversion, port lookup  
  _SRS §9.4 | FR-120, FR-121, FR-122, FR-123, FR-124, FR-125_
- [x] **T-042** Write `packages/agents/src/validators/rule_engine.py` — hot-reload `validation_rules.json` on SIGHUP, evaluate CV001–CV011  
  _SRS §3.6 | FR-033, FR-034, FR-035_

### Vessel Validation Node
- [x] **T-043** Write `packages/agents/src/nodes/vessel_validation_agent.py` — query AIS, vessel_characteristics, port_lineup, produce VesselValidationResult  
  _SDD §2.2, §11.4 | FR-025–FR-032_

### Schema Validator
- [x] **T-044** Write `packages/agents/src/validators/ceisa_schema.py` — validate PIB JSON against `ceisa_schema_v0.5.7.20.json` using `jsonschema`  
  _SRS §3.6 | FR-036_

---

## Week 4 (continued): HS RAG + Risk + CRS

### HS Code Agent
- [x] **T-045** Write `packages/agents/src/nodes/hs_code_agent.py` — trigger conditions, ID→EN translation (Gemini), ChromaDB cosine search top-10, Gemini reranker top-3, CEISA ref API validation  
  _SRS §3.7 | FR-038, FR-039, FR-040, FR-041, FR-042, FR-043_

### Risk + CRS
- [x] **T-046** Write `packages/agents/src/nodes/risk_agent.py` — XGBoost.predict (32 features) OR rule-based fallback, `RejectionPrediction` output  
  _SRS §3.8 | FR-044, FR-045, FR-046, FR-047_
- [x] **T-047** Implement CRS calculation — formula from PRD §11.7, grades A/B/C/D, minimum threshold check  
  _SRS §3.9 | FR-048, FR-049, FR-050, FR-051_

### Blockchain Node
- [x] **T-048** Write `contracts/DocumentRegistry.sol` + Hardhat config, deploy to Polygon Amoy  
  _PRD §8 | FR-079_
- [x] **T-049** Write `packages/agents/src/nodes/blockchain_agent.py` — SHA-256 content hash + Merkle root, Pinata IPFS pin, web3.py `anchorDocument()` call, graceful degradation  
  _SRS §3.14 | FR-079, FR-080, FR-081, FR-082, FR-083_

---

## Week 5: CEISA Integration

### CEISA Auth + Client
- [x] **T-050** Write `apps/api/src/services/ceisa_auth.py` — `CEISAAuthClient`, token cache, 60s pre-expiry refresh  
  _SDD §16.1 | FR-063_
- [x] **T-051** Write `apps/api/src/services/ceisa_client.py` — `POST /openapi/document`, idempotency key header, `X-Source-System` header  
  _SRS §3.12 | FR-065, FR-066_
- [x] **T-052** Implement retry + circuit breaker — exponential backoff 1s/2s/4s/8s/16s, 3 consecutive 5xx → OPEN, 60s → HALF_OPEN  
  _SRS §3.12 | FR-067, FR-068_
- [x] **T-053** Write AJU number generator — format: `{YYYYMMDDHHMMSS}{company_ceisa_code}{seq:06d}`  
  _PRD §15 | FR-062_

### CEISA Error Handling
- [x] **T-054** Implement AUTO_RECOVERABLE handlers — E007 (date normalize + resubmit), E019 (country code), E023 (port code)  
  _SRS §3.12 | FR-071_
- [x] **T-055** Implement OPERATOR_REQUIRED handlers — E004, E015, E031, E001 → set batch REJECTED, highlight fields, notify  
  _SRS §3.12 | FR-072_
- [x] **T-056** Implement ADMIN_ESCALATION handlers — E012, E099 → halt resubmission, notify admin  
  _SRS §3.12 | FR-073_

### INSW Pre-Check
- [x] **T-057** Write `apps/api/src/services/insw_check_svc.py` — check each line item `lartas_flag`, require permit number  
  _SRS §3.12 | FR-064, SRS §9.5, FR-126_

### PIB Builder + Submission Agent
- [x] **T-058** Write `packages/agents/src/utils/pib_builder.py` — assemble full PIB JSON from `DeclarationState`, validate with Pydantic `PIBPayload` model  
  _SDD §4.1 | FR-066_
- [x] **T-059** Write `packages/agents/src/nodes/submission_agent.py` — build payload, encrypt (AES-256-GCM), INSW check, submit, store to `ceisa_submissions`  
  _SRS §3.12 | FR-062–FR-073_
- [x] **T-060** Write `apps/api/src/tasks/ceisa_poll_tasks.py` — Celery task, poll every 30s, terminal states trigger notify + learning  
  _SRS §3.12 | FR-069_

---

## Week 6: Simulator + Learning

### CEISA Simulator
- [x] **T-061** Write `apps/simulator/main.py` — FastAPI, 6 scenarios (S01–S06), real CEISA OAuth2 endpoint, real PIB schema validation  
  _SRS §3.16 | FR-087, FR-088, FR-089_
- [x] **T-062** Implement INSW lartas simulation in simulator — check HS 28151110 and other DG codes  
  _SRS §3.16 | FR-090_
- [x] **T-063** Write simulator admin endpoints — `GET/PUT /simulator/scenario`, `GET /simulator/logs`, `GET /simulator/stats`, `POST /simulator/reset`  
  _SRS §3.16 | FR-091_
- [x] **T-064** Write `validate_pib_schema()` in simulator — NIB 13-digit, NPWP, HS 8-digit, CIF tolerance, all required fields  
  _SDD §17 schema validation code_

### Adaptive Learning
- [x] **T-065** Write `packages/agents/src/nodes/learning_agent.py` — record 32 features + CEISA label to `learning_outcomes`  
  _SRS §3.15 | FR-084_
- [x] **T-066** Write `apps/api/src/tasks/learning_tasks.py` — `retrain_xgboost` Celery task (every 100 outcomes or weekly), `check_model_drift` (>50 corrections in 30 days → alert)  
  _SRS §3.15 | FR-085, FR-086_

---

## Week 6 (continued): API Layer

### FastAPI Routers
- [x] **T-067** Write `apps/api/src/routers/batches.py` — all 8 batch endpoints, multipart upload, Celery dispatch, Supabase storage  
  _SDD §4.2 | FR-001–FR-008_
- [x] **T-068** Write `apps/api/src/routers/hs_recommend.py` — `POST /api/v1/hs-recommend`  
  _SDD §4.2 | FR-038_
- [x] **T-069** Write `apps/api/src/routers/blockchain.py` — `GET /api/v1/blockchain/{id}/verify`  
  _SDD §4.2 | FR-081_
- [x] **T-070** Write `apps/api/src/routers/vessel.py` — `GET /api/v1/vessel/validate`  
  _SDD §4.2 | FR-025_
- [x] **T-071** Write SSE streaming endpoint `GET /api/v1/batches/{id}/stream` — LangGraph node progress events  
  _SRS §5.3 | FR-075_

### Celery Tasks
- [x] **T-072** Write `apps/api/src/tasks/batch_tasks.py` — `process_batch` (dispatches LangGraph), `cleanup_expired` (delete 48h+ batches)  
  _SRS §3.1 | FR-007_
- [x] **T-073** Configure Celery beat schedule — `poll_ceisa_status` every 30s, `retrain_xgboost` weekly, `cleanup_expired` daily  
  _SRS §3.12 | FR-069_

### Notifications
- [x] **T-074** Write `apps/api/src/services/notification_svc.py` — Resend email templates + WhatsApp Cloud API messages for REVIEW_READY, ACCEPTED, REJECTED events  
  _SRS §3.13 | FR-076, FR-077, FR-078_

---

## Week 7: Dashboard + Real-time

### Real-time Layer
- [x] **T-075** Configure Supabase Realtime publications — `batches`, `extracted_fields`, `validation_results`, `ceisa_submissions` tables  
  _SDD §3 | FR-074_
- [x] **T-076** Write `apps/web/src/hooks/useBatchRealtime.ts` — Supabase Realtime CDC subscription  
  _SDD §7.2_
- [x] **T-077** Write `apps/web/src/hooks/useAgentStream.ts` — Socket.io client for LangGraph node streaming  
  _SDD §7_
- [x] **T-078** Configure Socket.io server in `apps/api/src/main.py` — attach to Uvicorn, emit LangGraph progress events  
  _PRD §4 Decision 5_

### Review UI Components
- [x] **T-079** Write `DocumentViewer.tsx` — PDF.js 4.x renderer + canvas overlay for bboxes from Agent B  
  _SRS §3.10 | FR-052, FR-054_
- [x] **T-080** Write `FieldRow.tsx` — confidence badge (HIGH/MEDIUM/LOW/DISAGREEMENT), inline edit, original gray, agent disagreement tooltip  
  _SRS §3.10 | FR-053, FR-057_
- [x] **T-081** Write `LineItemsGrid.tsx` — TanStack Table v8, inline edit, bulk HS apply  
  _SRS §3.10 | FR-055_
- [x] **T-082** Write `CRSWidget.tsx` — live gauge via Supabase Realtime, letter grade, component breakdown  
  _SRS §3.9 | FR-050_
- [x] **T-083** Write `RejectionRiskWidget.tsx` — probability bar, risk level badge, top-3 feature breakdown  
  _SRS §3.8 | FR-046_
- [x] **T-084** Write `VesselValidationWidget.tsx` — AIS status, lineup confirmation, issue list with severity badges  
  _SRS §9.2 | FR-031_
- [x] **T-085** Write `BlockchainStatusWidget.tsx` — tx hash, Polygonscan link, IPFS CID, certificate download  
  _SRS §3.14 | FR-081_
- [x] **T-086** Write `INSWStatusWidget.tsx` — lartas status, issue list, permit requirement alert  
  _SRS §3.12 | FR-064_
- [x] **T-087** Write `PreSubmitChecklist.tsx` — modal, 6 checks from FR-056, blocks submit if any fail  
  _SRS §3.10 | FR-056_
- [x] **T-088** Write `AICopilotPanel.tsx` — Socket.io streamed response, Enterprise full / SME basic  
  _SRS §3.11 | FR-059, FR-060, FR-061_

### SME Wizard
- [x] **T-089** Write SME Upload Wizard — 3-step (B/L → PL → Invoice), mobile camera input, simplified field labels  
  _SRS §3.10 | FR-030, FR-031_
- [x] **T-090** Write `HSCodeWizard.tsx` — inline per line item, top-3 with duty/VAT/lartas  
  _SRS §3.10 | FR-032_

### Analytics + Simulator Control
- [x] **T-091** Write `/analytics` page — Recharts dashboard, CRS trend, rejection rate by carrier/HS chapter, operator correction heatmap  
  _PRD §18_
- [x] **T-092** Write `/simulator` admin page — live scenario switcher (S01–S06), submission log table, stats card  
  _SRS §3.16 | FR-091_

---

## Week 8: Eval + Polish + Deploy

### Evaluation
- [x] **T-093** Write `eval/run_eval.py` — load all 20 fixtures, run through pipeline, compare to ground truth, assert all SRS §23 metrics  
  _SRS §23 | NFR-007 to NFR-013_
- [x] **T-094** Add `eval/fixtures/` — 8 real carrier docs + `real_bl_ground_truth.json` + 12 synthetic fixture files  
  _PRD Appendix A_
- [x] **T-095** Assert eval gate blocks merge if accuracy regresses >5%  
  _SRS §23 | NFR-007_

### Observability
- [x] **T-096** Instrument Prometheus metrics — `tradeflow_ocr_duration_seconds`, `tradeflow_ocr_agent_agreement_rate`, `tradeflow_azure_di_pages_used_month`, all counters from PRD §23  
  _PRD §23_
- [x] **T-097** Wire Sentry SDK to FastAPI + Next.js — `sentry_sdk.init()` in lifespan, source maps in Next config  
  _PRD §9_

### Tests
- [x] **T-098** Write unit tests — all 127 SRS FRs must have at least one test; naming: `test_FR{N}_{description}`  
  _SRS §11 | All FRs_
- [x] **T-099** Write E2E Playwright tests — upload → review → submit flow (S01), INSW rejection flow (S06)  
  _PRD §25 Week 8_

### Deployment
- [x] **T-100** Set up Railway services — GPU instances for `surya-svc` and `olm-inference`, standard for rest  
  _SDD §9_
- [x] **T-101** Set up Vercel project for `apps/web`, env vars from Doppler  
  _SDD §9_
- [x] **T-102** Deploy `DocumentRegistry.sol` to Polygon Amoy, store contract address in Doppler  
  _PRD §8_
- [x] **T-103** Final demo rehearsal — follow `E2E_Runbook.md`, full 3.5-minute demo, assert all 4 deliverables visible  
  _E2E_Runbook.md_

---

## Completion Tracker

```
Foundation:     T-001 to T-018   (18 tasks)
OCR Services:   T-019 to T-032   (14 tasks)
Agents Core:    T-033 to T-049   (17 tasks)
CEISA:          T-050 to T-066   (17 tasks)
API Layer:      T-067 to T-074   ( 8 tasks)
Dashboard:      T-075 to T-092   (18 tasks)
Eval + Deploy:  T-093 to T-103   (11 tasks)
─────────────────────────────────────────
Total:          103 tasks
```

**Minimum for competition demo:**  
T-001–T-023 (infra + preprocessing) +  
T-024–T-039 (OCR agents + reconciliation) +  
T-050–T-064 (CEISA + simulator) +  
T-067–T-071 (API) +  
T-075–T-087 (core review UI)  
= **72 tasks** for a working demo
