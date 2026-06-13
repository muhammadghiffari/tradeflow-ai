# Software Requirements Specification (SRS)
## TradeFlow AI — Predictive Customs Intelligence Platform v5.1
**Document:** SRS-TF-001  
**Status:** Approved for Build  
**Date:** June 2026

---

## 1. Introduction

### 1.1 Purpose
This SRS defines all functional, non-functional, interface, and data requirements for TradeFlow AI v5.1. Every requirement is numbered, testable, and maps directly to PRD v5.1. This document is the authoritative source for acceptance criteria in the task breakdown.

### 1.2 Scope
TradeFlow AI is a web platform that:
- Extracts structured data from CIPL trade documents (Bill of Lading, Packing List, Commercial Invoice) using a four-agent OCR ensemble
- Validates extracted data against CEISA 4.0 schema and cross-document rules
- Submits validated PIB import declarations to CEISA 4.0 via OAuth 2.0 Host-to-Host API
- Provides operator review UI, rejection risk prediction, blockchain audit trail, and real-time notifications

**In Scope v1:** Import declarations (PIB BC 2.0), Cikarang Dry Port only  
**Out of Scope v1:** Export declarations (PEB), multi-port, real PII in demo mode

### 1.3 Definitions & Acronyms

| Term | Definition |
|---|---|
| CIPL | Commercial Invoice, Packing List — collectively the three source documents (B/L + PL + CI) |
| PIB | Pemberitahuan Impor Barang — Indonesian Customs Import Declaration (BC 2.0) |
| CEISA | Customs-Excise Information System and Automation — Indonesia customs system |
| PIA | Public Internet Access — CEISA's external submission API |
| AJU | Nomor Ajuan — CEISA declaration reference number |
| NIB | Nomor Induk Berusaha — 13-digit Indonesian business registration number |
| NPWP | Nomor Pokok Wajib Pajak — 15-digit Indonesian tax identification number |
| CDP | Cikarang Dry Port — the competition's host organization |
| CRS | Customs Readiness Score — composite quality score [0–100] |
| INSW | Indonesia National Single Window — lartas (restricted goods) pre-check system |
| BTKI | Buku Tarif Kepabeanan Indonesia — Indonesian HS code tariff reference book |
| HS Code | Harmonized System code — 8-digit customs classification code |
| AIS | Automatic Identification System — real-time vessel tracking data |
| HitL | Human-in-the-Loop — mandatory operator review checkpoint |
| LangGraph | Stateful multi-agent orchestration framework |
| vLLM | High-throughput LLM inference server |
| QLoRA | Quantized Low-Rank Adaptation — parameter-efficient fine-tuning method |

### 1.4 References
- PRD v5.1 (TradeFlow AI — Predictive Customs Intelligence Platform)
- CEISA PIA API Documentation (DJBC, Indonesia)
- BTKI 2022 — Buku Tarif Kepabeanan Indonesia
- OmniDocBench v1.5 benchmark (May 2026)
- olmOCR-bench evaluation harness (AllenAI)

---

## 2. Overall Description

### 2.1 System Context

```
External Actors:
  Operator     → Review UI (browser/mobile)
  SME Trader   → Wizard UI (browser/mobile)
  CEISA System → H2H REST API
  INSW System  → Lartas validation
  Polygon PoS  → Blockchain audit
  
Internal Actors:
  LangGraph    → Agent orchestration
  Celery       → Async task execution
  Supabase     → Database + realtime
  Keycloak     → Authentication
```

### 2.2 Product Functions Summary
1. Document ingestion (PDF/scan/photo/XLSX → structured pipeline)
2. Multi-agent OCR ensemble (Surya 2 + PaddleOCR 3.0 + Azure DI + olmOCR-2-7B-CIPL)
3. Confidence reconciliation (majority vote per field)
4. Vessel validation (AIS + vessel characteristics + port lineup cross-check)
5. Cross-document validation (10+ hot-reloadable rules)
6. HS code recommendation (RAG: ChromaDB + Gemini reranker)
7. Rejection risk prediction (XGBoost + rule-based fallback)
8. Operator review (split PDF+fields UI with agent disagreement view)
9. CEISA PIB submission (OAuth2 + schema v0.5.7.20 + INSW pre-check)
10. Async status polling + notifications (email + WhatsApp)
11. Blockchain anchoring (Polygon Amoy → PoS mainnet)
12. Adaptive learning engine

### 2.3 User Classes

| Class | Access Level | Primary Touchpoint |
|---|---|---|
| Operator | Authenticated — operator role | Review UI, dashboard |
| SME Trader | Authenticated — sme role | Wizard UI, status page |
| Admin/Supervisor | Authenticated — admin role | Analytics, simulator control |
| System (Celery worker) | Service account | Internal APIs |

### 2.4 Operating Environment
- **API/Workers:** Railway (Linux/AMD64), Python 3.13, FastAPI 0.115
- **Frontend:** Vercel Edge, Next.js 16.2
- **GPU Inference:** Railway GPU instance (NVIDIA T4 or A10G), vLLM 0.6.x
- **Database:** Supabase (PostgreSQL 17)
- **Auth:** Keycloak 26 (Railway)
- **Queue:** Redis 8 (Railway)
- **Storage:** Supabase Storage (production), MinIO (local dev)

---

## 3. Functional Requirements

### 3.1 Document Ingestion

**FR-001** The system SHALL accept file uploads of types: `.pdf`, `.jpg`, `.jpeg`, `.png`, `.tiff`, `.tif`, `.webp`, `.xlsx`, `.xls`.

**FR-002** The system SHALL reject files exceeding 50 MB per file and return HTTP 400 with message `"File {name} exceeds 50MB limit"`.

**FR-003** The system SHALL accept between 1 and 3 files per batch submission.

**FR-004** The system SHALL auto-detect document type (bill_of_lading | packing_list | invoice) using the classification agent. If confidence < 0.80, the system SHALL prompt the user to confirm document type before processing continues.

**FR-005** The system SHALL process `.xlsx`/`.xls` Packing Lists using openpyxl 3.2, auto-detect header rows via LLM column mapping, and produce identical structured JSON output as the OCR path.

**FR-006** The system SHALL assign each batch a UUID, store all uploaded files in Supabase Storage at path `{company_id}/{batch_id}/{doc_type}_{filename}`, and return the `batch_id` in the upload response.

**FR-007** Partial batches (1–2 documents) SHALL be accepted and marked with `expires_at = NOW() + 48h`. Expired batches SHALL be auto-deleted by a Celery periodic task.

**FR-008** The system SHALL record a `batch.status = 'uploaded'` entry in the audit log immediately upon successful upload, before any processing begins.

### 3.2 Document Preprocessing

**FR-009** The system SHALL use MinerU 2.5 to detect text layers in PDF files. If a text layer is present AND `quality_score >= 0.95`, the system SHALL route to the fast path (PP-ChatOCRv4) and skip the image preprocessing pipeline.

**FR-010** For documents without a text layer or with `quality_score < 0.95`, the system SHALL convert PDF pages to images at 300 DPI using PyMuPDF.

**FR-011** The system SHALL apply the following image enhancement steps in order:
  1. CLAHE: `clip_limit=2.0`, `tile_grid_size=(8,8)`
  2. Deskew via Hough Transform if `|angle| > 0.5°`
  3. Denoise: `fastNlMeansDenoisingColored(h=10, hColor=10)`
  4. Binarization: Otsu adaptive thresholding
  5. Border removal via contour detection

**FR-012** The system SHALL compute a `quality_score ∈ [0,1]` based on: Laplacian variance (sharpness), contrast ratio, and skew angle. The score SHALL be stored on the `documents` table.

**FR-013** The system SHALL detect document language from: `id` (Indonesian), `en` (English), `zh` (Chinese), `ja` (Japanese) using lingua-py 2.0. Default to `en` if detection fails.

### 3.3 Multi-Agent OCR Ensemble

**FR-014** The system SHALL run the following four OCR agents concurrently using `asyncio.gather` for any scan/photo document (i.e., `processing_route = STANDARD` or `DEGRADED`):
  - **Agent A:** Surya 2 via vLLM — layout detection + HTML OCR output
  - **Agent B:** PaddleOCR 3.0 PP-StructureV3 — bounding boxes + table cell coordinates
  - **Agent C:** Azure DI 4.0 (`prebuilt-invoice` for invoices, `prebuilt-document` for B/L and PL)
  - **Agent D:** olmOCR-2-7B-CIPL via vLLM + LoRA adapter — primary CEISA JSON extraction

**FR-015** Agent failures SHALL NOT abort the pipeline. If an agent raises an exception or times out (> 20s), the system SHALL log the error, set that agent's output to `null`, and continue with remaining agents.

**FR-016** If 3 or more agents fail for the same document, the system SHALL set `batch.status = 'error'`, log the failure to `audit_log`, and send an alert notification to admin.

**FR-017** For the fast path (`processing_route = FAST_PATH`), the system SHALL use ONLY PP-ChatOCRv4 (PaddleOCR 3.0) and skip Agents A, C, D. The result SHALL be assigned `confidence = 0.97` and `extraction_method = 'fast_path_kia'`.

**FR-018** Azure DI usage SHALL be tracked in Redis key `azure_di:pages_used:{YYYY-MM}`. When usage reaches `AZURE_DI_FREE_LIMIT - 100` pages, the system SHALL log a warning and set `ENABLE_AZURE_DI_AGENT = false` for remaining batch in the session. When usage reaches `AZURE_DI_FREE_LIMIT`, Agent C SHALL be disabled until the first day of the next month.

### 3.4 Confidence Reconciliation

**FR-019** The Confidence Reconciliation Agent SHALL process every CEISA PIB field defined in `ceisa_schema_v0.5.7.20.json` and produce a `ReconciledField` with `value`, `confidence`, `level`, and `agent_disagreement` flag.

**FR-020** For **rule-validated fields** (`buyer_npwp`, `buyer_nib`, `hs_code`, `port_loading_code`, `port_discharge_code`, `bl_date`, `invoice_date`, `currency`): The system SHALL apply the corresponding validator function. The first agent value that passes validation SHALL be returned with `confidence = 0.98`. If NO agent produces a valid value, the field SHALL be returned with `confidence = 0.40` and `level = 'LOW'`.

**FR-021** For all other fields, the system SHALL apply majority-vote reconciliation:
  - `count(agreeing_agents) >= 3` → `confidence = 0.94`, `level = 'HIGH'`
  - `count(agreeing_agents) == 2` and Agent D is one of the two → `confidence = 0.85`, `level = 'MEDIUM'`
  - `count(agreeing_agents) == 2` and Agent D is NOT one of the two → `confidence = 0.78`, `level = 'MEDIUM'`
  - All agents disagree → use Agent D value, `confidence = 0.55`, `level = 'LOW'`, `agent_disagreement = true`

**FR-022** Field value normalization SHALL be applied before comparison: strip whitespace, lowercase, remove thousand separators, normalize decimal to period. Normalization SHALL NOT modify the stored `extracted_value` — only used for comparison.

**FR-023** The system SHALL store all per-agent values in `extracted_fields.agent_outputs` (JSONB) for every field where `agent_disagreement = true`.

**FR-024** The system SHALL compute and store `batches.agent_agreement_rate` as the percentage of fields where at least 2 agents agreed.

### 3.5 Vessel Validation

**FR-025** After OCR reconciliation, the system SHALL execute the `VesselValidationAgent` if `ENABLE_VESSEL_VALIDATION = true`.

**FR-026** The VesselValidationAgent SHALL query `vessel_characteristics` by IMO number (preferred) or LOWER(vessel_name) match.

**FR-027** If the vessel's `dead_year IS NOT NULL` and `dead_year <= YEAR(extracted_bl_date)`, the system SHALL create a `VesselIssue` with `severity = 'CRITICAL'` and `code = 'V001'`.

**FR-028** If `vessel_characteristics.trading_status != 'Trdg'`, the system SHALL create a `VesselIssue` with `severity = 'WARNING'` and `code = 'V002'`.

**FR-029** The system SHALL query `ais_vessel_positions` for the most recent record within 30 days matching the vessel. If the AIS ETA differs from the B/L arrival date by more than 3 days, the system SHALL create a `VesselIssue` with `severity = 'WARNING'` and `code = 'V003'`.

**FR-030** The system SHALL query `port_lineup` for a matching vessel + port `unlocode` + ETA within ±7 days. If no match is found, the system SHALL create a `VesselIssue` with `severity = 'INFO'` and `code = 'V004'`.

**FR-031** `batches.vessel_validation_status` SHALL be set to: `'critical'` if any issue has `severity = 'CRITICAL'`; `'warning'` if any issue has `severity = 'WARNING'`; `'info'` if only INFO issues; `'passed'` if no issues.

**FR-032** A `vessel_validation_status = 'critical'` SHALL add 0.25 to the XGBoost fallback rule-based risk score.

### 3.6 Cross-Document Validation

**FR-033** The system SHALL load validation rules exclusively from `packages/db/validation_rules.json` at worker startup and on each hot-reload signal (SIGHUP). Rules SHALL never be hardcoded in Python.

**FR-034** The system SHALL evaluate all rules in `validation_rules.json`. Each rule SHALL produce a `ValidationResult` with `rule_id`, `severity`, `passed`, and `error_message` with substituted values.

**FR-035** Rules CV001–CV011 SHALL be evaluated as specified in PRD §11.5. CRITICAL failures SHALL block submission (CRS validation gate). WARNING failures SHALL be visible in the UI but SHALL NOT block submission.

**FR-036** The `SchemaValidatorAgent` SHALL validate the assembled PIB JSON against `ceisa_schema_v0.5.7.20.json` using `jsonschema` library. Any schema violation SHALL produce a CRITICAL validation result.

**FR-037** All validation results SHALL be stored in `validation_results` table linked to `batch_id`.

### 3.7 HS Code Recommendation

**FR-038** The HSCodeAgent SHALL be triggered when ANY of the following is true:
  - `extracted_fields.hs_code.confidence < 0.75`
  - `extracted_fields.hs_code.value IS NULL`
  - Rule CV006 failed for any line item

**FR-039** The system SHALL normalize the product description: lowercase, remove duplicate words, translate Indonesian terms to English using Gemini 2.5 Flash.

**FR-040** The system SHALL generate an embedding using `text-embedding-3-small` (OpenAI) and query ChromaDB collection `btki_hs_codes` for top-10 candidates by cosine similarity.

**FR-041** The system SHALL pass top-10 candidates + original product description to Gemini 2.5 Flash reranker with prompt: `"Rank these HS codes for this product being imported into Indonesia. Include duty rate, VAT rate, and whether it is lartas-restricted."` The system SHALL return top-3 results.

**FR-042** Each HS recommendation SHALL include: `hs_code`, `description_id`, `description_en`, `duty_rate`, `vat_rate`, `pph_rate`, `lartas_flag`, `confidence`, `reasoning`.

**FR-043** The system SHALL validate each recommended HS code against the CEISA reference API (`GET /openapi/referensi/tarif/{hs_code}`) to confirm duty/VAT rates and lartas status.

### 3.8 Rejection Risk Prediction

**FR-044** When `xgb_labeled_samples >= XGB_MIN_SAMPLES_FOR_MODEL (default: 500)`, the system SHALL use the trained XGBoost 2.1 model with the 32 features defined in PRD §11.7.

**FR-045** When `xgb_labeled_samples < XGB_MIN_SAMPLES_FOR_MODEL`, the system SHALL compute risk using the `xgboost_fallback_rules` defined in `validation_rules.json`, starting from a base risk of 0.10 and additively applying matching rule weights, capped at 0.95.

**FR-046** Risk levels SHALL be assigned: LOW if `probability < 0.20`; MEDIUM if `0.20 <= probability < 0.45`; HIGH if `0.45 <= probability < 0.70`; CRITICAL if `probability >= 0.70`.

**FR-047** If `risk_level = 'CRITICAL'`, the system SHALL display a blocking warning in the UI. The operator SHALL be required to explicitly acknowledge the warning before the Submit button becomes active.

### 3.9 Customs Readiness Score

**FR-048** The CRS SHALL be computed as:
```
crs = (field_completeness*0.30 + ocr_confidence_score*0.25 + validation_score*0.25 + risk_score*0.20) * 100
```
Where:
  - `field_completeness` = filled required fields / total required fields
  - `ocr_confidence_score` = weighted avg confidence (critical fields weight=2.0: HS, NIB, NPWP, CIF)
  - `validation_score` = 1.0 - (count_critical_fails×0.30 + count_warnings×0.10), floored at 0
  - `risk_score` = 1.0 - rejection_probability

**FR-049** CRS grades: A if `crs >= 85`; B if `70 <= crs < 85`; C if `55 <= crs < 70`; D if `crs < 55`.

**FR-050** The system SHALL recalculate CRS in real-time whenever the operator modifies any field in the review UI. The updated CRS SHALL be pushed via Supabase Realtime within 2 seconds.

**FR-051** The system SHALL block submission if `crs < CRS_MIN_SUBMIT_THRESHOLD (default: 55)`.

### 3.10 Operator Review

**FR-052** The review UI SHALL display a split layout: 60% document viewer (PDF.js), 40% fields panel.

**FR-053** Each extracted field row SHALL show:
  - Confidence badge: 🟢 HIGH (≥0.90), 🟡 MEDIUM (0.70–0.89), 🔴 LOW (<0.70)
  - ⚠️ badge if `agent_disagreement = true` — clicking SHALL show a tooltip with all agent values
  - Inline editable input — editing triggers real-time CRS recalculation
  - Original OCR value in gray when corrected

**FR-054** Clicking any field in the fields panel SHALL scroll the PDF viewer to the corresponding page and highlight the bounding box (from Agent B output) in a distinct color.

**FR-055** The line items grid SHALL use TanStack Table v8 with: inline editing per cell, sortable columns, bulk HS code application to selected rows.

**FR-056** The pre-submit checklist modal SHALL verify: all CRITICAL validation rules pass, `crs >= CRS_MIN_SUBMIT_THRESHOLD`, NIB field filled and 13-digit format valid, NPWP checksum valid, `vessel_validation_status != 'critical'`, AJU number generated.

**FR-057** Every operator field correction SHALL be stored in `extracted_fields` with: `is_corrected=true`, `corrected_value`, `correction_reason` (from dropdown), `corrected_by`, `corrected_at`.

**FR-058** Operator corrections SHALL be written to `audit_log` with `actor_type='operator'`, `before_state` (previous value), `after_state` (corrected value).

### 3.11 AI Co-pilot

**FR-059** The AI Co-pilot panel SHALL stream responses via Socket.io using LangGraph token streaming.

**FR-060** The Co-pilot SHALL be able to: explain any validation error in plain Indonesian/English, suggest corrections for LOW-confidence fields, explain HS code recommendations with duty implications, summarize batch status.

**FR-061** Enterprise tier: full streaming Co-pilot. SME tier: basic (3 query types, non-streaming).

### 3.12 CEISA Submission

**FR-062** The system SHALL generate a unique AJU number per submission attempt using format: `{YYYYMMDDHHMMSS}{company_ceisa_code}{sequence:06d}`. A new AJU SHALL be generated for each re-submission attempt.

**FR-063** The system SHALL obtain a CEISA OAuth 2.0 access token via `POST /nle-oauth/v1/user/update-token` using `clientId` and `clientSecret`. Tokens SHALL be cached in memory and refreshed 60 seconds before expiry.

**FR-064** The system SHALL validate the full PIB payload against the INSW pre-check service (`INSWPreCheckService`) before sending to CEISA. If any line item has `lartas_flag = true` and no permit number is present, the system SHALL return `insw_status = 'reject'` and block submission.

**FR-065** The system SHALL submit the PIB JSON to CEISA via `POST /openapi/document` with headers:
  - `Authorization: Bearer {token}`
  - `X-Idempotency-Key: {uuid}` (unique per attempt, stored in `ceisa_submissions.idempotency_key`)
  - `X-Source-System: TradeFlowAI-v5`

**FR-066** The PIB JSON payload SHALL conform to CEISA schema v0.5.7.20 and include all required fields specified in PRD §16.3, including `nibEntitas` (13-digit), `nomorIdentitas` (NPWP), `kodeJenisApi`, `barangTarif`, and `barangVd` for each line item.

**FR-067** For CEISA HTTP 5xx responses (up to 3 consecutive), the system SHALL apply exponential backoff: 1s, 2s, 4s, 8s, 16s with ±10% jitter.

**FR-068** After 3 consecutive 5xx responses, the system SHALL trip the circuit breaker (status: OPEN) and store the submission in `DEAD_LETTER_QUEUE`. The circuit breaker SHALL transition to HALF_OPEN after 60 seconds.

**FR-069** The system SHALL poll CEISA status via `GET /openapi/document/status/{ajuNumber}` every 30 seconds (Celery periodic task) until the status is in `{ACCEPTED, REJECTED, CANCELLED}`.

**FR-070** Maximum re-submission attempts per batch SHALL be `MAX_RESUBMIT_ATTEMPTS (default: 5)`.

**FR-071** CEISA error code `E007` (date format) and `E019` (country code) and `E023` (port code) SHALL trigger `AUTO_RECOVERABLE` handling: auto-fix the field and resubmit without operator intervention.

**FR-072** CEISA error codes `E004` (HS invalid), `E015` (CIF inconsistent), `E031` (NIB not found), `E001` (B/L format) SHALL trigger `OPERATOR_REQUIRED` handling: set batch to REJECTED status, highlight affected fields in RED, notify operator.

**FR-073** CEISA error codes `E012` (NPWP unregistered), `E099` (company unauthorized) SHALL trigger `ADMIN_ESCALATION`: notify admin and halt re-submission.

### 3.13 Status & Notifications

**FR-074** Batch status changes SHALL be broadcast via Supabase Realtime CDC on the `batches` channel within 2 seconds of database update.

**FR-075** Field extraction progress SHALL be streamed via Socket.io events with format: `{ node, status, progress, data }`.

**FR-076** On `batch.status → REVIEW_READY`, the system SHALL send a notification to the assigned operator via: email (Resend) AND WhatsApp (Cloud API) if `ENABLE_NOTIFICATIONS_WHATSAPP = true`.

**FR-077** On `ceisa_submissions.status → ACCEPTED`, the system SHALL notify: operator, importir contact, and CDP supervisor via email. WhatsApp notification SHALL be sent to importir if configured.

**FR-078** On `ceisa_submissions.status → REJECTED`, the system SHALL notify operator with error code, Indonesian error message, and recommended action.

### 3.14 Blockchain Anchoring

**FR-079** The `BlockchainAnchorAgent` SHALL compute: `content_hash = SHA-256(full_PIB_JSON_bytes)` and `merkle_root = MerkleTree([SHA-256(bl_bytes), SHA-256(pl_bytes), SHA-256(invoice_bytes)]).root`.

**FR-080** The system SHALL call `DocumentRegistry.anchorDocument(batchIdHash, contentHash, merkleRoot, batchId, ajuNumber)` on the deployed contract. The transaction SHALL be sent by the operator wallet configured in `OPERATOR_WALLET_PRIVATE_KEY`.

**FR-081** The blockchain `tx_hash`, `block_number`, and IPFS CID SHALL be stored in `batches.blockchain_tx_hash`, `batches.blockchain_block_number`, `batches.ipfs_cid`.

**FR-082** The full PIB JSON SHALL be pinned to IPFS via Pinata before the on-chain anchor call. The IPFS CID SHALL be included in the `anchorDocument` transaction metadata.

**FR-083** If Polygon RPC is unavailable, the system SHALL degrade gracefully (log error, set `blockchain_tx_hash = null`), the batch SHALL continue to submission. The audit log SHALL record `blockchain_skipped = true`.

### 3.15 Adaptive Learning

**FR-084** Every accepted/rejected CEISA outcome SHALL be recorded in `learning_outcomes` table with all 32 XGBoost features at submission time.

**FR-085** When `new_labeled_outcomes >= 100` since last training OR `7 days` have elapsed, the system SHALL trigger async XGBoost retraining via Celery task.

**FR-086** When any single field accumulates `>= 50 corrections in 30 days`, the system SHALL create an alert in `model_drift_alerts` table and notify admin: `"Field {field_name} has {count} corrections in 30 days — consider re-fine-tuning olmOCR-2-7B-CIPL"`.

### 3.16 CEISA Simulator

**FR-087** The simulator SHALL implement identical wire protocol as production CEISA: same OAuth 2.0 endpoint, same PIB submission endpoint, same status polling endpoint. The production system SHALL require only changing `CEISA_BASE_URL` to switch between simulator and real CEISA.

**FR-088** The simulator SHALL validate every submitted PIB payload using the same `validate_pib_schema()` function as the production validator and return real CEISA error codes in Indonesian.

**FR-089** The simulator SHALL support 6 configurable scenarios (S01–S06) as specified in PRD §17. Scenario SHALL be switchable at runtime via `PUT /simulator/scenario/{id}` without restart.

**FR-090** The simulator SHALL simulate the INSW lartas check for any HS code flagged as lartas in the test data.

**FR-091** The simulator admin panel SHALL be accessible at `/simulator` route in the Next.js dashboard (admin role only).

### 3.17 Authentication & Authorization

**FR-092** All API endpoints except health checks SHALL require a valid Keycloak JWT in the `Authorization: Bearer` header.

**FR-093** FastAPI SHALL validate JWT using python-jose against Keycloak JWKS endpoint (`{KEYCLOAK_URL}/auth/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs`).

**FR-094** Row-Level Security (RLS) on all Supabase tables SHALL use the Keycloak JWT (passed via `Authorization` header) to enforce data isolation by `company_id`.

**FR-095** Role-based access: `operator` role → review + submit; `sme` role → wizard + status; `admin` role → all including analytics + simulator control.

**FR-096** The Next.js frontend SHALL use next-auth 5.x with the Keycloak OIDC provider. Session tokens SHALL not be stored in localStorage.

---

## 4. Non-Functional Requirements

### 4.1 Performance

**NFR-001** P95 end-to-end processing time (upload → REVIEW_READY) for a standard 3-document batch SHALL be:
  - CPU only: ≤ 45 seconds
  - GPU (T4): ≤ 15 seconds

**NFR-002** olmOCR-2-7B-CIPL inference per page SHALL be ≤ 6 seconds P95 on a single T4 GPU.

**NFR-003** Surya 2 inference per page SHALL be ≤ 1 second P95 on T4.

**NFR-004** The Review UI SHALL load the full field panel within 3 seconds of navigating to `/batches/{id}/review`.

**NFR-005** CRS recalculation on field edit SHALL complete and update the CRS widget within 2 seconds.

**NFR-006** Supabase Realtime status update SHALL reach the connected browser client within 3 seconds of database write.

### 4.2 Accuracy

**NFR-007** Field-level extraction accuracy on clean digital PDFs SHALL be ≥ 95% on the 20-document eval set.

**NFR-008** Field-level extraction accuracy on scanned/photo documents SHALL be ≥ 85% on the eval set.

**NFR-009** Fine-tuned olmOCR-2-7B-CIPL SHALL achieve ≥ +8% F1 improvement over zero-shot olmOCR-2-7B on CIPL-specific fields.

**NFR-010** Agent disagreement detection SHALL correctly flag ≥ 90% of true field disagreements (where ground-truth value differs between agents).

**NFR-011** HS code RAG top-1 accuracy SHALL be ≥ 75% on the BTKI ground-truth eval set.

**NFR-012** CEISA first-pass acceptance rate SHALL be ≥ 85% in Simulator Scenario S06 (mixed realistic).

**NFR-013** XGBoost rejection predictor SHALL achieve AUC-ROC ≥ 0.75 after 500+ labeled samples.

### 4.3 Reliability

**NFR-014** API uptime SHALL be ≥ 99.5% during the competition demo period.

**NFR-015** Any single OCR agent failure SHALL NOT affect overall pipeline availability. The system SHALL complete processing with 3 or fewer agents.

**NFR-016** The system SHALL handle Celery worker crashes gracefully via task acknowledgment only after successful completion (`acks_late=True`).

**NFR-017** The CEISA circuit breaker SHALL prevent cascading failures within 3 consecutive 5xx responses.

### 4.4 Security

**NFR-018** All API communication SHALL use TLS 1.3 minimum.

**NFR-019** CEISA PIB payloads containing NIB/NPWP SHALL be encrypted at rest using AES-256-GCM before database storage (`ceisa_submissions.payload_encrypted`).

**NFR-020** `OPERATOR_WALLET_PRIVATE_KEY` and `CEISA_CLIENT_SECRET` SHALL be managed via Doppler secrets manager and NEVER committed to git.

**NFR-021** SQL injection SHALL be prevented by exclusive use of parameterized queries (SQLAlchemy 2.0 ORM or `asyncpg` with `$N` parameters).

**NFR-022** The audit log (`audit_log` table) SHALL be physically append-only enforced by `REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM PUBLIC` at the database level.

### 4.5 Scalability

**NFR-023** The Celery worker pool SHALL support horizontal scaling (multiple worker instances) without coordination failures. Task idempotency SHALL be guaranteed via `idempotency_key`.

**NFR-024** The system SHALL support concurrent processing of up to 10 batches simultaneously without degradation.

### 4.6 Data Retention

**NFR-025** All documents, extracted fields, and audit logs SHALL be retained for a minimum of 7 years.

**NFR-026** Blockchain records on Polygon PoS are permanent and immutable by design.

---

## 5. Interface Requirements

### 5.1 External API Interfaces

**IF-001** CEISA PIA API:
  - Auth: `POST /nle-oauth/v1/user/update-token` → Bearer token
  - Submit: `POST /openapi/document` → PIB JSON
  - Status: `GET /openapi/document/status/{ajuNumber}`
  - Ref: `GET /openapi/referensi/tarif/{hs_code}`
  - All calls: 30s timeout, circuit breaker after 3 consecutive 5xx

**IF-002** Azure Document Intelligence 4.0:
  - Endpoint: `{AZURE_DI_ENDPOINT}/documentintelligence/documentModels/{model}:analyze`
  - Models: `prebuilt-invoice` (invoices), `prebuilt-document` (B/L, PL)
  - Auth: `Ocp-Apim-Subscription-Key: {AZURE_DI_KEY}`
  - Free tier F0: 5,000 pages/month

**IF-003** OpenAI Embeddings API:
  - `POST https://api.openai.com/v1/embeddings`
  - Model: `text-embedding-3-small`
  - Used for: ChromaDB BTKI HS code collection

**IF-004** Gemini API (Google):
  - Model: `gemini-2.5-flash`
  - Used for: HS code reranker, ID→EN translation only
  - NOT used for document extraction (cost control)

**IF-005** Polygon Amoy RPC:
  - `POST {POLYGON_RPC_URL}` (JSON-RPC)
  - Contract: `DocumentRegistry.sol` deployed at `{CONTRACT_ADDRESS}`

**IF-006** Pinata IPFS API:
  - `POST https://api.pinata.cloud/pinning/pinFileToIPFS`
  - Auth: `Authorization: Bearer {PINATA_JWT}`

**IF-007** Resend Email API:
  - `POST https://api.resend.com/emails`
  - Auth: `Authorization: Bearer {RESEND_API_KEY}`

**IF-008** WhatsApp Cloud API:
  - `POST https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages`
  - Auth: `Authorization: Bearer {WHATSAPP_TOKEN}`

### 5.2 Internal Service Interfaces

**IF-009** Surya vLLM service (`http://surya-svc:8001`):
  - `POST /v1/chat/completions` → HTML layout + OCR output
  - Health: `GET /health`

**IF-010** olmOCR vLLM service (`http://olm-inference:8000`):
  - `POST /v1/chat/completions` with `lora_request.lora_name = "cipl_adapter"`
  - Health: `GET /health`

**IF-011** PaddleOCR service (`http://paddleocr-svc:8002`):
  - `POST /extract` → bounding boxes + table structure JSON
  - `POST /kia` → PP-ChatOCRv4 key information extraction (fast path)
  - Health: `GET /health`

**IF-012** MinerU service (`http://mineru-svc:8003`):
  - `POST /preprocess` → `{ images: [], text_layer: bool, quality_score: float }`
  - Health: `GET /health`

### 5.3 User Interface

**IF-013** Web application SHALL be responsive for screen widths 1024px–2560px (desktop/laptop). Mobile support for SME wizard only (≥ 375px).

**IF-014** The review UI PDF viewer SHALL render using PDF.js 4.x with canvas overlay for bounding boxes.

**IF-015** Real-time field updates SHALL use Supabase Realtime WebSocket client `@supabase/supabase-js 2.x`.

**IF-016** Agent streaming SHALL use Socket.io 4.8 WebSocket client.

---

## 6. Data Requirements

### 6.1 Core Data Entities

**DR-001** `batches` — Central entity linking all processing artifacts. `batch_id` (UUID) is the primary correlation key throughout the system.

**DR-002** `documents` — Individual files within a batch. One batch has 1–3 documents of distinct types.

**DR-003** `extracted_fields` — One row per CEISA field per document. Stores raw, extracted, normalized, and corrected values plus all agent outputs.

**DR-004** `ceisa_submissions` — One row per submission attempt. Attempts are linked via `parent_submission_id` for re-submission chains.

**DR-005** `audit_log` — Immutable append-only record of all state-changing events.

**DR-006** `validation_results` — Output of CV001–CV011 plus schema validator per batch.

**DR-007** `hs_recommendations` — Top-3 HS code candidates per line item.

**DR-008** `learning_outcomes` — Training data for XGBoost: 32 features + CEISA acceptance/rejection label.

**DR-009** `ais_vessel_positions` — AIS tracking data loaded from `AIS_Data_Sample.csv` and updated periodically.

**DR-010** `vessel_characteristics` — Vessel spec data from `Website_Vessel_Characteristics_Sample.xlsx`.

**DR-011** `vessel_ownership` — Ownership data from `Ownership_-_Website_Data_Sample.xlsx`.

**DR-012** `port_lineup` — Port arrival schedule from `Lineup_Data_Sample.csv`.

### 6.2 Data Integrity Rules

**DR-013** `batches.ceisa_aju_number` SHALL be UNIQUE across all batches.

**DR-014** `ceisa_submissions.idempotency_key` SHALL be UNIQUE. Any duplicate submission with the same idempotency key SHALL be rejected at the database level.

**DR-015** `extracted_fields.confidence` SHALL be in range [0.000, 1.000].

**DR-016** Foreign key constraints SHALL use `ON DELETE CASCADE` for child records of `batches` and `ON DELETE RESTRICT` for `profiles` references.

**DR-017** All `TIMESTAMPTZ` columns SHALL store UTC. Timezone conversion is the responsibility of the presentation layer.

---

## 7. Business Rules

**BR-001** A batch CANNOT be submitted to CEISA if any of the following are true:
  - Any CRITICAL validation rule fails
  - `crs < CRS_MIN_SUBMIT_THRESHOLD`
  - `buyer_nib` is null or not 13 digits
  - `buyer_npwp` fails checksum validation
  - `vessel_validation_status = 'critical'`
  - INSW pre-check returns any CRITICAL issue

**BR-002** AJU numbers are single-use. A new AJU MUST be generated for every resubmission attempt, even if the payload is identical.

**BR-003** Operators MAY override LOW-confidence field values but MUST provide a correction reason from a predefined list.

**BR-004** The `operator_corrections` count contributes negatively to the XGBoost risk model (more corrections = higher historical rejection probability).

**BR-005** All CEISA payloads containing NIB/NPWP data MUST be encrypted before persistence. Raw PIB JSON is transient (in memory only during processing).

**BR-006** The Adaptive Learning Engine MAY NOT retrain during an active submission batch. Retraining is only triggered when no batches are in `SUBMITTING` or `CEISA_PROCESSING` status.

---

## 8. Constraints

**CN-001** The system MUST operate within the Azure DI free tier limit of 5,000 pages/month for competition purposes.

**CN-002** Model weights MUST NOT be included in Docker images. Images are code-only; weights are downloaded at container startup from HuggingFace Hub.

**CN-003** The competition demo MUST use the CEISA Simulator (not real CEISA). The real CEISA URL requires DJBC-registered credentials which will be obtained post-competition.

**CN-004** Surya 2 is licensed under GPL-3.0. For competition use this is acceptable. Production commercial deployment requires license evaluation.

**CN-005** All LangGraph checkpoints MUST use the `langgraph-checkpoint-redis` backend (not in-memory) to support worker restarts without state loss.

**CN-006** The `OPERATOR_WALLET_PRIVATE_KEY` (Polygon) MUST be provisioned via environment variable (Doppler) and NEVER written to any log, database, or file.

---

## AMENDMENT v5.2 — Real Carrier Document Analysis
**Date:** June 2026 | **Basis:** 8 real filled B/L documents (HLCU×2, MSCU×1, MAEU×1, EGLV×3, CSLU×1)

---

## 9. Carrier-Specific Requirements (NEW — v5.2)

### 9.1 Watermark Handling

**FR-111** The preprocessing pipeline SHALL detect and remove the following four watermark types confirmed across all 8 real carrier documents:
- `DRAFT` — Hapag-Lloyd, Cordelia (diagonal, large, semi-transparent)
- `ORIGINAL` — Maersk, MSC, all Evergreen (diagonal, right side)
- `PROOFREAD` — Evergreen only (diagonal, left side)
- `READ` — Evergreen only (diagonal, center)

**FR-112** Watermark removal SHALL use inpainting (cv2.inpaint with INPAINT_TELEA) on detected text regions. The system SHALL NOT use simple masking, as watermarks overlap carrier field data. After removal, the image SHALL be re-evaluated for quality_score.

**FR-113** The system SHALL detect watermarks BEFORE running any OCR agent. Watermark-containing regions found by Agent B (PaddleOCR bboxes) SHALL be flagged and excluded from confidence scoring for fields they overlap.

### 9.2 Multi-Page B/L Handling

**FR-114** The system SHALL detect multi-page B/L documents. Of the 8 real documents, 5 are multi-page (Hapag_2: 2 pages, Evergreen_1/2/3: 2 pages each, Cordelia: 2 pages).

**FR-115** Page type classification SHALL assign each page one of:
- `MAIN` — primary B/L fields (page 1 always)
- `ATTACHMENT` — container list continuation (Evergreen page 2 pattern)
- `TERMS_AND_CONDITIONS` — legal clauses (Cordelia page 2 pattern, detected by presence of "DEFINITIONS" or clause numbering "1. DEFINITIONS", "2. CARRIER'S TARIFF" etc.)
- `DEMURRAGE_SCHEDULE` — rate tables (Hapag page 3 pattern)

**FR-116** The system SHALL process ONLY `MAIN` and `ATTACHMENT` pages for field extraction. `TERMS_AND_CONDITIONS` and `DEMURRAGE_SCHEDULE` pages SHALL be skipped and excluded from OCR. Skipped pages SHALL be logged in `extracted_fields.metadata`.

**FR-117** For `ATTACHMENT` pages (container list), the system SHALL merge extracted container rows with the `MAIN` page container data, de-duplicating by container number.

### 9.3 Carrier SCAC Detection and Profile Routing

**FR-118** The system SHALL detect carrier SCAC code from document text using the following priority order:
1. Explicit SCAC field (Maersk: "SCAC MAEU", MSC: "SCAC Code: MSCU")
2. B/L number prefix (HLCU→HLCU, EGLV→EGLV, MAEU→MAEU, CSX→CSLU)
3. Carrier name in header (Hapag-Lloyd Aktiengesellschaft → HLCU)
4. Logo detection via Agent A (Surya layout)

**FR-119** Detected SCAC SHALL be stored in `documents.carrier_scac` and used to load the corresponding carrier profile from `packages/db/carrier_profiles.json` to guide Agent D field extraction.

### 9.4 Field Normalization Requirements

**FR-120** Container Number Normalization: The system SHALL normalize all container numbers to ISO 6346 format (4 alpha + 7 digits, no spaces). Real documents show: "HLXU 2382861" (space) → "HLXU2382861". The validator SHALL also verify check digit using the ISO 6346 modulo-11 algorithm.

**FR-121** HS Code Normalization: The system SHALL handle both formats found in real documents:
- 8-digit format: `28151110`, `72193590` → already correct
- 10-digit dot format: `8482.10.00` → strip dots, take 8 digits → `84821000`
- Multiple HS codes comma-separated on one line → split and normalize each

**FR-122** Date Format Normalization: The system SHALL parse all 7 date formats confirmed in real documents:
| Format | Example | Carrier |
|---|---|---|
| DD/MON/YYYY | 27/FEB/2013 | Hapag-Lloyd |
| MON-DD-YYYY | FEB-20-2012 | Hapag-Lloyd |
| DD/MM/YYYY | 14/09/2016 | MSC |
| DD-MM-YYYY | 03-06-2024 | Maersk |
| MON.DD,YYYY | APR.15,2015 | Evergreen |
| DD.MM.YYYY | 18.09.2021 | Evergreen |
| DD-MON-YYYY | 29-MAR-2023 | Cordelia |
All SHALL be normalized to ISO 8601 (YYYY-MM-DD) before CEISA submission.

**FR-123** Weight Unit Normalization: The system SHALL convert all weight units to KGS for CEISA:
- KGS/KG → multiply by 1.0
- KGM → multiply by 1.0 (ISO unit code for kilograms)
- MTS/MT/T → multiply by 1000
- LBS/LB → multiply by 0.453592
- Thousand separators (128,500 kg) SHALL be stripped before parsing

**FR-124** Port Name to UN/LOCODE Mapping: The system SHALL maintain a lookup table for port names found in real documents:

| Port Name in Document | UN/LOCODE | Carrier Found In |
|---|---|---|
| TILBURY, ESSEX | GBTIL | HLCU |
| NHAVA SHEVA | INNSA | HLCU |
| JEBEL ALI, U.A.E. | AEJEA | HLCU |
| ODESSA, UKRAINE | UAODS | HLCU |
| GUANGZHOU PORT, CHINA | CNGZH | MAEU |
| ONNE PORT, RIVERS STATE | NGAPP | MAEU |
| HAMBURG | DEHAM | EGLV |
| MUNDRA, INDIA | INMUN | EGLV, CSLU |
| HO CHI MINH CITY PORT | VNSGN | EGLV |
| KUANTAN, MALAYSIA | MYKUA | EGLV |
| JAKARTA, INDONESIA | IDJKT | EGLV |
| SHEKOU, CHINA | CNSHK | CSLU |

Ports not found in the lookup SHALL be passed to Gemini API for resolution. IDJBK (Cikarang Dry Port) SHALL always be hardcoded as the primary CDP port.

**FR-125** B/L Number Format Normalization: Carrier-specific B/L number formats SHALL be normalized for storage:
- Maersk: `MAEU-AT-06324` → store as-is (dashes are valid)
- Hapag: `HLCULIV130219209` → store as-is
- Evergreen: `EGLV100150418716` → store as-is
- Cordelia: `CSX23SHKMUN017829` → store as-is
The system SHALL NOT strip dashes or other separators from B/L numbers, as they are part of the carrier's official numbering.

### 9.5 INSW Critical Finding — Evergreen_Filled_1

**FR-126** The system SHALL maintain a dangerous goods HS code list for INSW pre-check. From real document analysis, HS code `28151110` (Caustic Soda Flakes, UN 1813, Class 8) was confirmed as a lartas-restricted goods code. When this HS code is detected, the system SHALL:
1. Set `insw_flag = true` on the line item
2. Require dangerous goods permit number in the PIB payload
3. Display INSW warning in the review UI with: DG class, UN number, permit requirement

### 9.6 MSC Document Handling

**FR-127** For MSC (MSCU) documents where the document appears largely unfilled (detected by: >60% of expected fields returning null from all agents), the system SHALL:
1. Set `processing_route = DEGRADED`
2. Notify the operator that the document may be an incomplete draft
3. Still attempt extraction with all 4 agents
4. Set all field confidence levels to maximum MEDIUM (0.80 cap)

---

## 10. Updated Non-Functional Requirements (v5.2)

**NFR-027** The OCR pipeline SHALL correctly handle documents from the following confirmed carrier layouts: HLCU (Hapag-Lloyd), MSCU (MSC), MAEU (Maersk), EGLV (Evergreen), CSLU (Cordelia). Accuracy targets in NFR-007 and NFR-008 apply to ALL five carrier formats.

**NFR-028** The preprocessing watermark removal step SHALL complete within 2 seconds per page on CPU.

**NFR-029** Date parsing SHALL achieve 100% success rate on all 7 confirmed date formats (FR-122) in automated unit tests.

**NFR-030** Port name to UN/LOCODE lookup SHALL resolve within 100ms for table entries and within 3 seconds for Gemini-assisted resolution of unknown ports.
