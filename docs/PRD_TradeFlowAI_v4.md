# Product Requirements Document
## TradeFlow AI — Predictive Customs Intelligence Platform
### Cikarang Dry Port · AI Open Innovation Challenge 2026

---

**Document Version:** 4.0 — DEFINITIVE BUILD SPEC (No-Downgrade Edition)  
**Date:** May 2026  
**Status:** Active · Authoritative Reference for AI Coding Agents & Developers  
**Previous Versions:** CeisaSync PRD v1.0, TradeFlow AI PRD v2.0, v3.0 (all superseded)

> **Purpose:** This is the single source of truth for building the full TradeFlow AI prototype.  
> Every section is directly actionable by developers and AI coding agents.  
> All architectural decisions are argued against rejected alternatives. No assumption is implicit.


---

## 0. Pre-Flight: Inconsistencies, Invariants, & Cross-Reference

Before reading the full PRD, developers and AI agents must internalize these rules and resolutions.

### 0.1 PRD Inconsistencies Resolution

The following minor inconsistencies have been resolved to provide a single source of truth:

| Location | Inconsistency | Resolution |
|----------|--------------|-----------|
| §2 vs §9.6 | §2 targets "≥85% CEISA acceptance" but §9.6 acknowledges 25–40% real rejection rate. | §9.6 describes the *baseline problem*, §2 is the *goal* after AI intervention. Both are correct. |
| §6 vs §7 | §6 service map says Traefik, §7 docker-compose uses supabase-kong. | Use **Traefik 3.x** as the main reverse proxy. supabase-kong is for internal Supabase routing only — do not expose it. |
| §2 & §6 | Some lines say "Supabase Auth JWT" after Decision 2 mandated Keycloak. | **Keycloak 26 is the only auth provider.** "Supabase Auth" means "Supabase RLS consuming Keycloak JWT", not Supabase Auth as the provider. |

### 0.2 Key Invariants (Never Violate)

1. **Audit Log is Append-Only:** The `audit_log` table must never be updated or deleted. Enforce via `REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM PUBLIC`.
2. **Validation Rules are Hot-Reloadable:** Never hardcode cross-document validation rules in Python/TypeScript. Always read dynamically from `validation_rules.json`.
3. **No Bare `os.getenv()`:** All environment variables must be validated through `pydantic-settings` in `config.py` with strict type annotations.
4. **Keycloak is the Only Auth Provider:** Never use Supabase Auth for user login or session management. Use it only for RLS authorization.
5. **Human-in-the-Loop is Mandatory:** The LangGraph pipeline MUST pause at `interrupt_before=["submit"]` for operator review. Do not bypass this.
6. **Async Task Prioritization:** Celery queues must be strictly prioritized (`critical`, `high`, `default`, `low`). Enterprise tier MUST use `critical`/`high`.
7. **Graceful Fallbacks:** If Azure DI, PaddleOCR, or Gemini fails, the system must degrade gracefully (e.g., rule-based fallback or lower confidence flags) without crashing the pipeline.
8. **Single Source of Truth for Types:** Use `packages/shared-types` (Zod schemas) to maintain contract sync between Next.js (tRPC) and FastAPI (Pydantic).

### 0.3 PRD Cross-Reference Map

Instead of scanning the entire document, use this map to find exactly what you need based on what you are building:

| If you are building... | Read this section |
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

## Table of Contents

1. Product Overview & Positioning
2. Goals, Success Metrics & Personas
3. Problem Definition (Technical)
4. Architecture Philosophy & Key Decisions
5. Multi-Agent System Design (LangGraph)
6. Full System Architecture
7. Infrastructure: Database, Storage & CI/CD Strategy
8. Blockchain Integration Specification
9. MCP Integration Map (from Day 1)
10. Core AI/ML Modules
11. Feature Requirements (All Tiers)
12. Data Models & Database Schema
13. API Contracts
14. State Machines & Workflow Logic
15. Tech Stack — Complete Reference (2026)
16. CEISA Integration Specification
17. CEISA Simulator Specification
18. Dashboard & UI Specifications
19. Dual-Tier System (Enterprise vs SME)
20. Non-Functional Requirements
21. Error Handling & Fallback Logic
22. Feature Flags & Environment Variables
23. Observability & Evaluation Framework
24. Risks & Mitigations
25. Delivery Milestones

---

## 1. Product Overview & Positioning

### Product Name
**TradeFlow AI** — Predictive Customs Intelligence Platform

### One-Line Definition
TradeFlow AI transforms fragmented trade documents (B/L, Packing List, Invoice) into validated, CEISA 4.0-ready customs declarations, with proactive rejection risk prediction, immutable blockchain audit trail, and adaptive multi-agent intelligence that improves with every submission.

### What This System Does (Developer Summary)
1. Accepts multi-format CIPL documents (PDF, image, XLSX)
2. Runs multi-engine OCR with preprocessing pipeline
3. Dispatches documents to specialized LangGraph extraction agents per document type
4. Cross-validates extracted fields across all 3 source documents via rule engine
5. Runs HS Code Recommendation (RAG-based) for missing/low-confidence codes
6. Runs CEISA Rejection Prediction (XGBoost ML model)
7. Computes Customs Readiness Score (CRS) composite
8. Routes to operator review with prioritized flagging and AI Co-pilot
9. Anchors document hashes on Polygon blockchain (audit trail)
10. Submits to CEISA via API H2H with full retry/circuit-breaker/idempotency
11. Parses CEISA response, feeds Adaptive Learning Engine
12. Broadcasts real-time status via Supabase Realtime + custom WebSocket

### What This System Does NOT Do (v1 Scope Boundaries)
- Does not replace human operator decision-making
- Does not connect to real CEISA in demo/competition mode (uses simulator)
- Does not store or process real PII in demo mode (all synthetic data)
- Does not support PEB (export) in v1 — documented as Future Enhancement

---

## 2. Goals, Success Metrics & Personas

### Primary Goals & KPIs

| Goal | Metric | Target | Measurement Method |
|------|--------|--------|--------------------|
| OCR accuracy — digital PDF | Field-level extraction accuracy | ≥ 95% | Ground truth eval set (15 docs) |
| OCR accuracy — scanned/photo | Field-level extraction accuracy | ≥ 85% | Ground truth eval set |
| Processing time per batch | Upload → REVIEW_READY | < 45s (CPU), < 15s (GPU) | P95 latency |
| HS code recommendation | Top-1 accuracy | ≥ 75% | Eval against BTKI ground truth |
| Rejection prediction | AUC-ROC | ≥ 0.75 | After 500+ labeled samples |
| CEISA first-pass acceptance | Submissions accepted without rejection | ≥ 85% | Simulator S06 (mixed scenario) |
| Blockchain anchoring | % of declarations with on-chain hash | 100% | Audit log |
| Operator review efficiency | Fields needing manual correction | < 10% of total fields | Per-batch stats |

### Competition-Specific Goals
- Demonstrate full E2E flow (upload → OCR → AI → review → CEISA → response) in < 90 seconds live demo
- Show CEISA simulator with 6 configurable scenarios switchable in real time
- Demonstrate blockchain audit trail with verifiable on-chain hash
- Show adaptive learning feedback loop (prediction improves with submissions)
- Show dual-tier system (Enterprise vs SME) with different feature sets

### User Personas

**Persona 1: Bea Cukai Operator (CDP Internal)**
- Primary user of review interface
- Moderate tech level; expert in customs forms and CEISA portal
- Pain: 80% time on manual transcription, not verification
- Needs: Fast review UI, confidence indicators, AI suggestions, one-click submit
- Tier: Enterprise

**Persona 2: Importir / SME Trader**
- Uploads documents, monitors declaration status
- Variable tech level; needs guided, simple UI
- Pain: No visibility into declaration progress, high rejection rate costs money
- Needs: Guided wizard, plain-language status, WhatsApp notifications, HS Code wizard
- Tier: SME

**Persona 3: CDP Supervisor / Admin**
- System oversight: accuracy metrics, SLA compliance, operator performance
- High tech level
- Needs: Analytics dashboard, rejection pattern analysis, learning engine monitoring
- Tier: Enterprise (admin role)

**Persona 4: IT Administrator**
- Manages deployment, monitors infrastructure
- Needs: CI/CD visibility, Sentry errors, Grafana dashboards, MCP integrations
- Tier: System

---

## 3. Problem Definition (Technical)

### Input Documents

| Document | Content | Common Formats | Key Challenges |
|----------|---------|----------------|----------------|
| Bill of Lading (B/L) | Routing, vessel, package counts, B/L number | PDF (digital/scan), photo | Semi-structured; carrier-specific layouts vary widely |
| Packing List (PL) | Line items: description, qty, weight, dims, HS code | PDF, Excel .xlsx, scan | High complexity; 10–500 rows; multi-page tables; merged cells |
| Commercial Invoice (CI) | Prices, currencies, seller/buyer, incoterms, NPWP | PDF (digital/scan), photo | Semi-structured; currency/date format variance |

Together referred to as **CIPL** throughout this document.

### Core Technical Challenges

**Challenge 1: Format variance**
Same shipper sends different format each shipment. Quality ranges from crisp digital PDF to blurry phone photo. Tables in Packing List may span pages, use merged cells, or inconsistent column headers. **Solution**: Multi-engine OCR + LangGraph specialized extraction agents per document type.

**Challenge 2: Cross-document consistency**
Total packages B/L = Packing List total. CIF = FOB + freight + insurance. HS code in Invoice must match what Packing List description implies. Any inconsistency → CEISA rejection. **Solution**: Cross-Document Validation Engine with hot-reloadable JSON rules.

**Challenge 3: HS Code accuracy**
8-digit BTKI code required. Operators guess or copy from previous declarations. Wrong code = rejection + potential audit. Codes expire. **Solution**: RAG-based HS Code Recommendation Engine (ChromaDB + LLM re-ranker).

**Challenge 4: CEISA rejection loop**
~25–40% first-submission rejection rate. Rejection reasons are repetitive and learnable. Currently: operator fixes manually, no learning. **Solution**: XGBoost Rejection Prediction Engine + Adaptive Learning Engine.

**Challenge 5: Throughput**
Single operator manually processes 8–15 declarations/day (1.5–3h each). CDP handles 150–300/day. **Solution**: Async multi-agent pipeline with Celery workers + LangGraph orchestration.

**Challenge 6: Audit & compliance**
No tamper-proof record of declaration submission history. Regulatory requirement for 7-year retention. **Solution**: Blockchain anchoring via Polygon PoS + immutable PostgreSQL audit log.

---

## 4. Architecture Philosophy & Key Decisions

This section documents **why** each major architectural decision was made. Every decision has a rationale and rejected alternatives.

---

### Decision 1: Multi-Agent Framework — LangGraph (NOT Swarm, NOT CrewAI)

**Chosen: LangGraph 0.3+**

**Why:**
The customs declaration pipeline is fundamentally a **complex stateful workflow** with:
- Multiple sequential + parallel processing stages
- **Mandatory human-in-the-loop** checkpoints (operator review before CEISA submission)
- Conditional branching (OCR fallback, HS code trigger, rejection risk routing)
- Long-running tasks requiring checkpointing (resume after crash)
- Streaming output required (real-time progress to frontend)

LangGraph is purpose-built for exactly this pattern. It models the entire pipeline as a **directed state graph** with nodes (agents), edges (transitions), and conditional edges (branching). Human-in-the-loop is a first-class primitive, not an afterthought.

**Why NOT OpenAI Swarm:**
Experimental, minimal state management, handoff-only architecture, no checkpointing, not production-ready. Effectively deprecated in favor of proper frameworks.

**Why NOT CrewAI:**
Role-based collaborative agent design is excellent for autonomous research/writing tasks but provides insufficient control over strict sequential workflows with regulatory compliance requirements. State management is less granular.

**Why NOT AutoGen:**
Conversation-based multi-agent designed for interactive chatbot-style workflows. Customs pipeline needs deterministic state transitions, not conversational loops.

**LangGraph Agent Graph:**
```
[START]
   │
   ▼
SupervisorAgent ──────────────────────────────────────────────
   │                                                          │
   ├─── DocumentIngestAgent                                   │ (orchestrates all)
   │       ├── PreprocessorSubAgent                           │
   │       └── TypeClassifierSubAgent                         │
   │                                                          │
   ├─── OCRAgent (parallel per doc)                           │
   │       ├── PaddleOCRSubAgent                              │
   │       └── AzureDISubAgent (conditional fallback)         │
   │                                                          │
   ├─── ExtractionAgent (parallel per doc type)               │
   │       ├── BillOfLadingExtractorAgent                     │
   │       ├── PackingListExtractorAgent                      │
   │       └── InvoiceExtractorAgent                          │
   │                                                          │
   ├─── ValidationAgent                                       │
   │       ├── CrossDocValidatorAgent                         │
   │       └── SchemaValidatorAgent                           │
   │                                                          │
   ├─── HSCodeAgent (conditional: triggered if needed)        │
   │       ├── RAGRetrieverSubAgent                           │
   │       └── LLMRerankerSubAgent                            │
   │                                                          │
   ├─── RiskAssessmentAgent                                   │
   │       ├── RejectionPredictorSubAgent                     │
   │       └── CRSCalculatorSubAgent                          │
   │                                                          │
   ├─── [HUMAN_IN_THE_LOOP: OperatorReview] ◄──── CHECKPOINT │
   │       (operator reviews, corrects, approves/rejects)     │
   │                                                          │
   ├─── BlockchainAnchorAgent (parallel to submission)        │
   │                                                          │
   ├─── SubmissionAgent                                       │
   │       ├── PayloadBuilderSubAgent                         │
   │       └── H2HSubmitterSubAgent (retry/circuit-breaker)   │
   │                                                          │
   └─── LearningAgent (post-submission)                       │
           ├── OutcomeRecorderSubAgent                        │
           └── ModelRetrainerSubAgent (async, triggered)      │
                                                              │
[END] ◄────────────────────────────────────────────────────────
```

**LangGraph State Object:**
```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator

class DeclarationState(TypedDict):
    batch_id: str
    documents: list[dict]
    preprocessed: list[dict]
    ocr_results: list[dict]
    extracted_fields: dict
    validation_results: list[dict]
    hs_recommendations: list[dict]
    rejection_prediction: dict
    crs: dict
    operator_corrections: list[dict]  # HitL checkpoint output
    blockchain_tx: dict
    ceisa_payload: dict
    ceisa_response: dict
    learning_feedback: dict
    error: str | None
    messages: Annotated[list, operator.add]  # append-only message log
```

**Checkpointing:** Redis-based LangGraph checkpointer (via `langgraph-checkpoint-redis`) ensures pipeline resumes correctly if a worker crashes mid-processing.

---

### Decision 2: Auth — Keycloak 26 as Primary OIDC (NOT Supabase Auth)

**Chosen: Keycloak 26.x as the sole OIDC/auth provider.**

v3.0 made the mistake of replacing Keycloak with Supabase Auth. This was a downgrade. Restored here.

**Why Keycloak 26 is non-negotiable for this system:**
1. **Multi-tenant enterprise RBAC**: Keycloak supports multiple realms, fine-grained role-based access (operator / admin / supervisor / importer), and enterprise LDAP/AD federation — required for CDP's actual enterprise clients
2. **Offline tokens + session management**: Customs operators work 8-hour shifts. Keycloak offline tokens allow long-lived sessions without re-login. Supabase Auth has no offline token concept.
3. **Industry standard**: All customs, government, and logistics B2B platforms use enterprise OIDC (Keycloak, Auth0 Enterprise) — not consumer auth solutions
4. **Supabase RLS integration**: Keycloak-issued JWTs (RS256) work natively with Supabase Row Level Security by setting `jwt_secret` to Keycloak's realm public key. No either/or — both coexist perfectly.

**Integration architecture:**
```
Browser → Keycloak /auth → RS256 JWT (sub, realm_access.roles claims)
JWT → FastAPI (python-jose validates against Keycloak JWKS endpoint)
JWT → Supabase RLS (configured to verify Keycloak JWT: auth.jwt()->>'role')
JWT → Next.js (next-auth 5.x Keycloak provider)
```

**Why NOT Supabase Auth as replacement:** No offline tokens, no LDAP federation, no fine-grained RBAC policies beyond basic roles, inadequate session management for enterprise B2B.

---

### Decision 3: Database & Storage — Supabase PostgreSQL 17 + Dual Storage

**Chosen: Supabase (PostgreSQL 17) + MinIO local dev + Supabase Storage production**

**Why Supabase PostgreSQL:**
1. **Supabase Realtime** (Postgres CDC via logical replication → WebSocket) for DB-level events — batch status changes, extracted_fields inserts — zero infrastructure overhead
2. **Supabase MCP** natively available — schema migrations, RLS policies, table queries without leaving dev workflow
3. **Supabase Edge Functions** (Deno) for lightweight serverless handlers (CEISA webhooks, NPWP validation)
4. **GitHub Actions → Supabase CLI** zero-config migration CI/CD
5. PostgreSQL 17 — same JSONB, gen_random_uuid(), RLS, pg_cron we need

**Dual storage (not a downgrade — correct for each environment):**
- **Local dev**: MinIO 7.x in Docker Compose (S3-identical API, zero egress cost, works offline, parity with production S3 API for 50MB documents)
- **Production**: Supabase Storage (CDN, presigned URLs, RLS on files via Keycloak JWT)
- **Single abstraction**: `storage_client.py` wraps both behind `upload_document()` — `STORAGE_BACKEND=supabase|minio` switches implementation

**Architecture layers:**
```
KEYCLOAK 26 (Auth)                 SUPABASE (Data)
──────────────────                 ───────────────────────────────
OIDC provider                      PostgreSQL 17 (DB)
JWT issuer (RS256)                 Realtime (CDC WebSocket — DB events)
RBAC (4 roles)                     Storage (prod documents)
Session management                 Edge Functions (lightweight logic)
LDAP federation ready              MCP server available

REDIS 8 STANDALONE (Queue)         VERCEL (Frontend)
──────────────────────────         ──────────────────────────────
Celery broker (RESP3 native)       Next.js 15 (App Router + PPR)
Celery result backend              Edge deployment, preview per PR
LangGraph checkpointer             Vercel Remote Cache (Turborepo)
Rate limiting cache

MinIO 7.x (Local Dev Only)         POLYGON (Blockchain)
──────────────────────────         ──────────────────────────
Docker Compose only                Amoy testnet (demo)
S3-compatible, zero egress         PoS mainnet (production)
Dev/test document storage          IPFS via Pinata (metadata)
```

---

### Decision 3: Blockchain — Polygon PoS (YES, implemented)

**Chosen: Polygon PoS + Solidity 0.8.28 + Hardhat 2.22 + ethers.js 6 + OpenZeppelin 5**

**Why blockchain is the right call for customs declarations:**
Customs declarations are regulatory documents with 7-year retention requirements. A tamper-proof, independently verifiable audit trail:
1. Proves document was submitted at exact timestamp (legal standing)
2. Detects if declaration data was modified after submission
3. Enables multi-party verification (CDP, importer, customs authority) without shared infrastructure
4. Differentiates TradeFlow AI from competitors in the competition

**Why Polygon PoS over alternatives:**
- **vs Ethereum mainnet**: Gas fees too high (~$5–50/tx) for per-declaration anchoring
- **vs Base**: Excellent L2 but newer (2023), less enterprise recognition in Indonesia
- **vs Hyperledger Fabric**: Private chain requires consortium setup — overkill for demo, no public verifiability
- **Polygon PoS 2026**: ~$0.0001/tx, 2.3s finality, battle-tested, widely recognized, EVM-compatible

**Why NOT blockchain-only for storage:**
IPFS stores document metadata (hash, fields summary) — not the full declaration payload (CEISA payloads are sensitive). Polygon stores only the content hash + submission event.

**Smart Contracts:**
```
contracts/
├── DocumentRegistry.sol    — Document hash registration + event emission
├── SubmissionAudit.sol     — CEISA submission outcomes on-chain
└── interfaces/
    └── IDocumentRegistry.sol
```

**Gas optimization:** Batch multiple document hashes per transaction using Merkle roots (reduces on-chain cost by ~70% for bulk Enterprise submissions).

**Feature flag:** `ENABLE_BLOCKCHAIN=true` — graceful degradation if Polygon RPC unavailable.

---

### Decision 4: Redis — Redis 8 Standalone (NOT Upstash for Celery)

**Chosen: Redis 8 standalone (Railway managed in production, Docker in local dev).**

v3.0 replaced Redis with Upstash HTTP. This was a downgrade for the task queue layer.

**Why Redis 8 standalone is mandatory for Celery:**
- Celery broker uses native Redis protocol (RESP3) — HTTP is not supported
- Upstash HTTP layer adds 20–50ms per task enqueue/dequeue, compounding across hundreds of tasks per declaration — unacceptable
- Upstash free tier rate limits would fail under demo day load
- `langgraph-checkpoint-redis` requires native Redis connection (not HTTP)

**Usage split:**
- **Redis 8 standalone** (Railway): Celery broker, Celery result backend, LangGraph checkpointer, pub/sub for Socket.io rooms
- **Upstash** (HTTP, optional): Only for Next.js edge middleware rate limiting where native protocol is not available (Edge Runtime constraint)

---

### Decision 5: Real-time — DUAL LAYER (Socket.io 4.8 + Supabase Realtime)

**Both are required. They serve fundamentally different responsibilities.**

v3.0 dropped Socket.io in favor of Supabase Realtime only. This was a downgrade.

| Layer | Tool | Handles | Why the other can't |
|-------|------|---------|---------------------|
| DB-level events | Supabase Realtime (CDC) | `batch.status` changes, `extracted_fields` INSERTs, `validation_results` | Postgres CDC — zero-code, triggers on committed rows |
| Agent streaming | Socket.io 4.8 | LangGraph node progress %, LLM token streaming, AI Co-pilot streaming responses | Realtime only fires on committed DB rows — partial LLM output never reaches the DB |

**Why Socket.io over plain SSE for agent streaming:**
- Bi-directional: client sends `copilot:explain_field` events, server streams back tokens
- Rooms: each operator is in `room:batch_{id}` — targeted broadcasts without polling
- Reconnect with exponential backoff built-in
- Fallback to long-polling if WSS blocked (useful for demo venue networks)

```
Supabase Realtime → DB change events (status, fields, validation)
Socket.io 4.8    → LangGraph agent progress, LLM streaming, Co-pilot
```

---

### Decision 6: Storage — Dual (Supabase Storage prod + MinIO local dev) ✓

*Covered in Decision 3 above.*

---

### Decision 7: CI/CD — Turborepo 2 + pnpm 9 + GitHub Actions + Vercel + Railway

**Chosen. Upgraded from v3.0.**

- **pnpm 9 workspaces** (not npm): 60–70% faster installs, strict dependency hoisting, correct monorepo semantics
- **Turborepo 2.x**: build task graph with remote caching (Vercel Remote Cache, free for Vercel projects), incremental builds skip unchanged packages
- **Biome 1.9** (not ESLint + Prettier): single binary, 10–20× faster lint + format, zero config drift between the two tools
- **Vitest 2.x** (not Jest): native ESM support, TypeScript first-class, 5–10× faster than Jest, same API
- **uv** (not pip/poetry): Rust-based Python package manager, 10–100× faster installs, lockfile-based reproducible environments

---

### Decision 8: Blockchain — Polygon PoS + Solidity 0.8.28 + Hardhat 2.22 ✓

No change from v3.0. This is the correct decision — see v3.0 arguments. Restored from v2.0 where it was incorrectly removed.

---

### Decision 9: tRPC 11 for End-to-End Type Safety (NEW in v4.0)

**Added.** FastAPI + Pydantic defines the contract server-side. Next.js consumes it. Without tRPC, this contract is maintained by convention (OpenAPI spec) and breaks silently when either side changes.

With tRPC 11 HTTP adapter:
- Zod schemas shared between `packages/shared-types` → Python Pydantic models and TypeScript tRPC router
- Type errors at compile time, not runtime
- React Query integration built-in (no separate `useQuery` wrappers needed)
- Used for: all Next.js Server Components → FastAPI data fetching

---

## 5. MCP Integration Map (from Day 1)

MCP servers wired into the development workflow from project initialization — not added later.

| MCP Server | Primary Use in TradeFlow AI | Setup Stage |
|------------|------------------------------|-------------|
| **GitHub MCP** | PR review automation, issue creation from Sentry errors, code search, branch management | Week 1 |
| **Supabase MCP** | Schema migrations, RLS policy management, table queries, Edge Function deployment | Week 1 |
| **Vercel MCP** | Deployment status checks, preview URL retrieval, domain management, env var sync | Week 1 |
| **Linear MCP** | Sprint board, issue tracking, automatic issue creation from failed CI, roadmap | Week 1 |
| **Sentry MCP** | Error triage, stack trace analysis, alert rule management, release tracking | Week 1 |
| **Slack MCP** | CEISA rejection alerts to operator channel, deployment notifications, daily standup digest | Week 1 |
| **PostHog MCP** | Feature flag management (LaunchDarkly alternative), usage analytics, funnel analysis | Week 2 |
| **Playwright/BrowserBase MCP** | E2E test automation, screenshot-based regression, demo flow validation | Week 4 |
| **Cloudflare MCP** | DNS management, WAF rules, CDN cache purge, Workers deployment | Week 7 |
| **Polygon/EVM MCP** *(custom)* | Smart contract interaction, transaction status, Polygonscan verification | Week 6 |

**MCP config file (`.mcp.json` in repo root):**
```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}" }
    },
    "supabase": {
      "command": "npx",
      "args": ["-y", "@supabase/mcp-server-supabase@latest"],
      "env": { "SUPABASE_ACCESS_TOKEN": "${SUPABASE_ACCESS_TOKEN}" }
    },
    "linear": {
      "command": "npx",
      "args": ["-y", "@linear/mcp-server"],
      "env": { "LINEAR_API_KEY": "${LINEAR_API_KEY}" }
    },
    "sentry": {
      "command": "npx",
      "args": ["-y", "@sentry/mcp-server"],
      "env": { "SENTRY_AUTH_TOKEN": "${SENTRY_AUTH_TOKEN}" }
    },
    "vercel": {
      "command": "npx",
      "args": ["-y", "@vercel/mcp-adapter"],
      "env": { "VERCEL_TOKEN": "${VERCEL_TOKEN}" }
    },
    "posthog": {
      "command": "npx",
      "args": ["-y", "posthog-mcp"],
      "env": { "POSTHOG_PERSONAL_API_KEY": "${POSTHOG_API_KEY}" }
    }
  }
}
```

---

## 6. Full System Architecture

### Service Map

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND — Vercel Edge                             │
│    Next.js 15 (App Router + PPR + Turbopack)                              │
│    Enterprise Dashboard │ SME Wizard │ Review UI │ Admin │ Simulator Panel │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │ HTTPS / Supabase Realtime WS
┌─────────────────────────────────▼────────────────────────────────────────┐
│                    API GATEWAY — Railway                                   │
│              FastAPI 0.115 + Uvicorn 0.34 + Traefik 3.x                  │
│         Supabase Auth JWT validation · Rate Limiting · Routing            │
└──┬──────────────┬──────────────┬───────────────┬─────────────────────────┘
   │              │              │               │
┌──▼────┐  ┌──────▼──────┐  ┌───▼──────┐  ┌────▼──────────┐
│Ingest │  │ LangGraph   │  │  CEISA   │  │  Blockchain   │
│ Svc   │  │ Orchestrator│  │ Gateway  │  │   Svc         │
└──┬────┘  └──────┬──────┘  └───┬──────┘  └────┬──────────┘
   │              │              │               │
┌──▼──────────────▼──────────────▼───────────────▼───────────────────────┐
│                       TASK LAYER — Celery 5.5 + Upstash Redis            │
│   preprocess · ocr · extract · validate · hs_recommend ·                 │
│   predict_rejection · compute_crs · submit · anchor_blockchain ·         │
│   process_response · retrain_model                                        │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼─────────────────────────────────────┐
│                              DATA LAYER                                  │
│  Supabase PostgreSQL 17  │  Supabase Storage (S3-compat)                │
│  Upstash Redis 8          │  ChromaDB 0.6 (HS RAG, Railway volume)      │
│  Supabase Realtime (CDC)  │  MinIO local (Docker dev only)              │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼─────────────────────────────────────┐
│                         EXTERNAL SERVICES                                │
│  Gemini API (gemini-3.1-pro / gemini-2.5-flash) │ Azure DI 1.0       │
│  OpenAI text-embedding-3-small (HS RAG)            │ CEISA Simulator    │
│  Polygon Amoy / PoS (blockchain)                   │ Pinata IPFS        │
│  LangSmith (LLM tracing)  │  Sentry │  PostHog  │  Resend │ WhatsApp   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Async Processing Pipeline (LangGraph orchestrated)

```
upload_complete → [SupervisorAgent starts graph]
   │
   ▼
[PreprocessorSubAgent]     Deskew · CLAHE · denoise · language detect · text layer check
   │
   ▼
[OCRAgent] ─────── parallel per document ──────────────
   ├── PaddleOCR PP-OCRv4 + PP-StructureV3
   └── AzureDI (conditional: confidence < 0.78)
   │
   ▼
[ExtractionAgent] ── parallel per doc type ────────────
   ├── BillOfLadingExtractorAgent (Gemini multimodal)
   ├── PackingListExtractorAgent  (Gemini multimodal + table-aware)
   └── InvoiceExtractorAgent      (Gemini multimodal)
   │
   ▼
[ValidationAgent]          CrossDocRules (JSON hot-reload) + CEISA schema validation
   │
   ▼
[HSCodeAgent] ─ conditional: missing/low-confidence HS codes only
   ├── ChromaDB RAG retrieval
   └── Gemini LLM re-ranker
   │
   ▼
[RiskAssessmentAgent]      XGBoost rejection prediction + CRS computation
   │
   ▼
[BlockchainAnchorAgent] ── parallel branch ─────────────
   └── Polygon tx: document hashes anchored
   │
   ▼
[CHECKPOINT: REVIEW_READY]  ← Supabase Realtime event → operator dashboard
   │
   (operator reviews, corrects, approves via UI)
   │
   ▼
[SubmissionAgent]          CEISA H2H payload build + submit + retry
   │
   ├── ACCEPTED → [LearningAgent.RecordOutcome] → [BlockchainAudit: accepted]
   └── REJECTED → [LearningAgent.RecordOutcome] → operator error screen
                   (if AUTO_RECOVERABLE → auto-fix → resubmit)
                   (retraining trigger if threshold reached)
```

---

## 7. Infrastructure: Database, Storage & CI/CD Strategy

### Local Development Stack (Docker Compose)

```yaml
# docker-compose.yml (key services)
services:
  supabase-db:      postgres:17-alpine  # local Supabase
  supabase-realtime: supabase/realtime
  supabase-storage:  supabase/storage-api
  supabase-kong:     kong              # local API gateway for Supabase
  
  redis:            redis/redis-stack:8.0   # local Redis (Upstash-compatible)
  
  api:              ./apps/api          # FastAPI
  worker:           ./apps/api          # Celery workers (same image, different CMD)
  langgraph:        ./packages/agents   # LangGraph orchestrator process
  
  chromadb:         chromadb/chroma:0.6.0   # HS code vector store
  simulator:        ./apps/simulator    # CEISA simulator
  
  frontend:         ./apps/web         # Next.js dev server
  
  traefik:          traefik:v3.2       # reverse proxy
  
  hardhat-node:     (optional) local Hardhat EVM for blockchain dev
```

### Supabase Schema Management

```
packages/db/
├── migrations/
│   ├── 20260501_001_init_schema.sql
│   ├── 20260508_002_add_learning_tables.sql
│   └── ...
├── seed/
│   ├── seed_synthetic_data.sql     # 500+ labeled submissions for XGBoost
│   ├── seed_btki_hs_codes.sql      # HS code reference data
│   └── seed_demo_users.sql
├── functions/                      # Supabase Edge Functions (Deno/TypeScript)
│   ├── ceisa-webhook/             # Process CEISA response webhook
│   ├── npwp-validate/             # NPWP checksum validation (lightweight)
│   └── notify-operator/           # Trigger WhatsApp/email on declaration event
└── supabase.config.ts
```

### CI/CD GitHub Actions Workflows

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  lint-backend:     ruff check + mypy --strict (Python 3.13)
  lint-frontend:    eslint + tsc --noEmit (TypeScript 5.8 strict)
  test-backend:     pytest --cov (≥70% coverage gate)
  test-frontend:    vitest run
  test-e2e:         playwright test (smoke: upload → review → submit flow)
  eval-ai:          python eval/run_eval.py (AI accuracy gate: ≥5% regression blocks PR)
  db-validate:      supabase db diff --schema public (no drift from migrations)
  blockchain-test:  npx hardhat test (contracts/)
  docker-build:     docker build api + worker (cache layers)

# .github/workflows/deploy-staging.yml
name: Deploy Staging
on: push to develop
jobs:
  deploy-vercel-preview:   vercel deploy --prebuilt --env preview
  deploy-railway-staging:  railway up --service api --service worker --env staging
  migrate-supabase-staging: supabase db push --project-ref ${STAGING_REF}
  deploy-contracts-amoy:   npx hardhat run scripts/deploy.ts --network amoy

# .github/workflows/deploy-production.yml
name: Deploy Production
on: push to main (with manual approval gate)
jobs:
  deploy-vercel-prod:      vercel deploy --prod
  deploy-railway-prod:     railway up --service api --replicas 2 --service worker --replicas 3
  migrate-supabase-prod:   supabase db push --project-ref ${PROD_REF}
  sentry-release:          sentry-cli releases finalize ${VERSION}
  posthog-deploy-event:    curl PostHog /capture deployment event
```

---

## 8. Blockchain Integration Specification

### Smart Contracts

**contracts/DocumentRegistry.sol**
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/cryptography/MerkleProof.sol";

contract DocumentRegistry is Ownable {
    
    struct DocumentRecord {
        bytes32 contentHash;    // SHA-256 of declaration payload
        bytes32 merkleRoot;     // root of [bl_hash, pl_hash, invoice_hash]
        uint256 timestamp;
        address submitter;
        string batchId;         // off-chain reference
        bool exists;
    }
    
    mapping(bytes32 => DocumentRecord) public records;  // batchId hash → record
    
    event DocumentAnchored(
        bytes32 indexed batchId,
        bytes32 contentHash,
        bytes32 merkleRoot,
        uint256 timestamp,
        address submitter
    );
    
    event SubmissionOutcomeRecorded(
        bytes32 indexed batchId,
        bool accepted,
        string ceisaReference,
        uint256 timestamp
    );
    
    function anchorDocument(
        bytes32 batchIdHash,
        bytes32 contentHash,
        bytes32 merkleRoot,
        string calldata batchId
    ) external onlyOwner {
        require(!records[batchIdHash].exists, "Already anchored");
        records[batchIdHash] = DocumentRecord({
            contentHash: contentHash,
            merkleRoot: merkleRoot,
            timestamp: block.timestamp,
            submitter: msg.sender,
            batchId: batchId,
            exists: true
        });
        emit DocumentAnchored(batchIdHash, contentHash, merkleRoot, block.timestamp, msg.sender);
    }
    
    // Batch anchor (Enterprise: Merkle batch, gas efficient)
    function anchorBatch(
        bytes32[] calldata batchIdHashes,
        bytes32[] calldata contentHashes,
        bytes32 batchMerkleRoot
    ) external onlyOwner {
        // Store single root + emit events for individual records
    }
    
    function verifyDocument(bytes32 batchIdHash, bytes32 contentHash) 
        external view returns (bool valid, uint256 timestamp) {
        DocumentRecord memory r = records[batchIdHash];
        return (r.exists && r.contentHash == contentHash, r.timestamp);
    }
}
```

**blockchain_svc/anchor.py**
```python
from web3 import Web3
from eth_account import Account
from eth_account.signers.local import LocalAccount
import hashlib, json

class BlockchainAnchorService:
    
    def anchor_declaration(self, batch_id: str, payload: dict) -> BlockchainReceipt:
        # 1. Compute SHA-256 of each document
        bl_hash = hashlib.sha256(json.dumps(payload["bill_of_lading"]).encode()).hexdigest()
        pl_hash = hashlib.sha256(json.dumps(payload["packing_list"]).encode()).hexdigest()
        inv_hash = hashlib.sha256(json.dumps(payload["invoice"]).encode()).hexdigest()
        
        # 2. Build Merkle tree of the three hashes
        merkle_root = self._compute_merkle_root([bl_hash, pl_hash, inv_hash])
        
        # 3. Compute full payload hash
        content_hash = hashlib.sha256(json.dumps(payload).encode()).hexdigest()
        
        # 4. Submit on-chain via contract function
        tx = self.contract.functions.anchorDocument(
            Web3.solidity_keccak(['string'], [batch_id]),
            bytes.fromhex(content_hash),
            bytes.fromhex(merkle_root),
            batch_id
        ).build_transaction({...})
        
        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
        
        # 5. Pin metadata to IPFS via Pinata
        ipfs_cid = self._pin_to_ipfs(batch_id, content_hash, merkle_root)
        
        return BlockchainReceipt(
            tx_hash=tx_hash.hex(),
            block_number=receipt.blockNumber,
            polygon_scan_url=f"https://amoy.polygonscan.com/tx/{tx_hash.hex()}",
            ipfs_cid=ipfs_cid,
            content_hash=content_hash
        )
```

### Polygon Scan Verification Widget (UI)
- Shows tx hash as clickable link to Polygonscan
- Shows `Verified ✓` with timestamp when on-chain record found
- Shows Merkle proof for individual document within batch
- "Download Certificate" → generates PDF with QR code linking to Polygonscan

---

## 9. Core AI/ML Modules

### 9.1 Document Preprocessing

```python
# packages/agents/preprocessing.py
def preprocess(file_path: str, doc_type: str) -> PreprocessResult:
    # 1. Text layer detection (pdfplumber 0.11)
    #    → If chars exist: extract directly, confidence=0.98, skip OCR
    #    → If no text layer: convert to images (pymupdf 1.25 at 300 DPI)
    
    # 2. Image enhancement pipeline (opencv-python 4.11):
    #    a. CLAHE contrast: clip_limit=2.0, tile_grid=(8,8)
    #    b. Deskew via Hough Transform (correct if |angle| > 0.5°)
    #    c. Denoise: fastNlMeansDenoisingColored for photos (h=10, hColor=10)
    #    d. Binarization: Otsu's adaptive thresholding
    #    e. Border removal: detect and crop margins
    
    # 3. Language detection: lingua-py 2.0
    #    Supported: id, en, zh, ja — default fallback: en
    
    # 4. Quality scoring: sharpness (Laplacian variance) + contrast + skew angle
    #    quality_score ∈ [0,1]
    
    return PreprocessResult(images=[], text=None, language="en", quality_score=0.92)
```

### 9.2 Multi-Engine OCR

**Primary:** PaddleOCR 2.9 (PP-OCRv4 + PP-StructureV3)  
**Fallback:** Azure Document Intelligence 1.0 (prebuilt-invoice / prebuilt-document)

```python
# Confidence thresholds
OCR_FALLBACK_TRIGGER_CONFIDENCE = 0.78   # page-level avg
OCR_FALLBACK_TRIGGER_QUALITY    = 0.65   # preprocessing quality_score

# Ensemble: when both run → higher confidence per field wins
# Numeric fields with >5% discrepancy → flag for mandatory operator review
# Named entity disagreement → flag for mandatory operator review
```

### 9.3 Multimodal LLM Extraction (Gemini, via LangGraph Agents)

Each document type has a dedicated extraction agent with specialized prompts and few-shot examples:

**Models:**
- Primary: `gemini-3.1-pro` (high accuracy, used when `COST_SAVING_MODE=false`)
- Fallback: `gemini-2.5-flash` (faster/cheaper, used when `COST_SAVING_MODE=true`)

**Input to each LLM call:**
1. Full OCR output as structured JSON (text + bounding boxes)
2. Original document image(s) — base64 encoded
3. CEISA field schema (injected as system context, hot-reloadable)
4. 5 few-shot extraction examples per document type (versioned in `prompts/`)
5. Explicit uncertainty instruction: "If unsure, set confidence < 0.70, never hallucinate"

**Output format (strict JSON):**
```json
{
  "fields": {
    "npwp_importir": {
      "value": "01.234.567.8-901.000",
      "confidence": 0.95,
      "source_page": 1,
      "bounding_box": {"x": 120, "y": 340, "w": 200, "h": 18},
      "extraction_method": "direct_ocr | llm_inferred | cross_doc"
    }
  },
  "extraction_notes": "CIF field unclear — estimated from FOB + freight line items",
  "overall_confidence": 0.87
}
```

**Post-processing validators:**
- NPWP: 15-digit checksum formula
- Dates: normalize to ISO 8601
- Currency: validate against ISO 4217
- Port codes: validate against UN/LOCODE database
- Numeric values: strip currency symbols, normalize decimal separators

**LangSmith tracing:** Every LLM call tagged with `document_id`, `batch_id`, `doc_type`, `prompt_version`, token counts, latency, and whether operator corrected the output (feedback loop).

### 9.4 Cross-Document Validation Engine

Hot-reloadable JSON rule file (`packages/db/validation_rules.json`). Domain experts update rules without code changes.

```json
{
  "rules": [
    { "rule_id": "CV001", "severity": "CRITICAL", "name": "Package Count Consistency",
      "check": "abs(bl.total_packages - pl.total_packages) <= 0",
      "error_message": "Jumlah koli B/L ({bl}) ≠ Packing List ({pl})" },
    { "rule_id": "CV002", "severity": "WARNING", "name": "CIF Value Consistency",
      "check": "abs((inv.fob+inv.freight+inv.insurance) - inv.cif) / inv.cif <= 0.05",
      "error_message": "Nilai CIF tidak konsisten (selisih {diff}%)" },
    { "rule_id": "CV003", "severity": "CRITICAL", "name": "B/L Date Before Arrival",
      "check": "bl.bl_date <= bl.arrival_date" },
    { "rule_id": "CV004", "severity": "CRITICAL", "name": "Invoice Currency Match",
      "check": "inv.currency_code == pl.currency_code" },
    { "rule_id": "CV005", "severity": "WARNING",  "name": "Gross Weight Tolerance",
      "check": "abs(bl.gross_weight - sum(pl.items[*].gross_weight)) / bl.gross_weight <= 0.02" },
    { "rule_id": "CV006", "severity": "CRITICAL", "name": "HS Code Format",
      "check": "regex_match(item.hs_code, '^[0-9]{8}$')" },
    { "rule_id": "CV007", "severity": "CRITICAL", "name": "NPWP Checksum",
      "check": "npwp_checksum_valid(importir.npwp)" }
  ]
}
```

### 9.5 HS Code Recommendation Engine (RAG)

**Triggered when:** HS confidence < 0.75 OR field empty OR CV006 fails OR operator requests

```
Product Description (Packing List)
   ↓ text normalizer (lowercase, noise removal, ID→EN translation)
   ↓ text-embedding-3-small (OpenAI API)
   ↓ ChromaDB cosine similarity search (top-10, collection: btki_hs_codes ~10,000 entries)
   ↓ Gemini LLM re-ranker ("rank these HS codes for this product description")
   → Top-3 candidates: { hs_code, description_id, duty_rate, vat_rate, confidence, reasoning }
```

**BTKI Knowledge Base (ChromaDB):** Seeded from BTKI public data at startup. Monthly refresh via scheduled Celery task. Entry structure: `{ hs_code, description_id, description_en, duty_rate, vat_rate, pph_rate, effective_date, embedding }`.

### 9.6 CEISA Rejection Prediction Engine (XGBoost)

**~25 engineered features** per declaration before submission:

```python
features = {
    # Document quality
    "avg_ocr_confidence": float,
    "num_low_confidence_fields": int,
    "num_operator_corrections": int,
    "had_cross_doc_warnings": bool,
    "had_critical_validation_failures": bool,
    
    # HS code signals
    "hs_code_ai_suggested": bool,
    "hs_code_confidence": float,
    "hs_code_changed_by_operator": bool,
    "hs_category_2digit": str,          # first 2 digits (chapter)
    
    # Value signals
    "cif_value_usd": float,
    "cif_per_unit_usd": float,          # outlier flag
    "num_line_items": int,
    
    # Importer signals
    "shipper_country_code": str,
    "importir_historical_rejection_rate": float,
    "importir_total_submissions": int,
    
    # Timing
    "hour_of_submission": int,
    "days_since_bl_date": int,          # urgency proxy
    
    # CRS at time of prediction
    "customs_readiness_score": float,
}
```

**Model:** XGBoost 2.1 binary classifier. Cold start (< 500 samples): rule-based heuristics. Retraining every 100 new labeled submissions or weekly. AUC gate: new model must exceed current - 0.05.

**Risk levels:** LOW < 0.20 · MEDIUM 0.20–0.45 · HIGH 0.45–0.70 · CRITICAL > 0.70

### 9.7 Customs Readiness Score (CRS)

```python
crs = (
    field_completeness   * 0.30 +   # required fields filled / total required
    ocr_confidence_score * 0.25 +   # weighted avg (critical fields ×2.0)
    validation_score     * 0.25 +   # 1.0 - (CRITICAL_FAIL×0.30 + WARNING×0.10)
    risk_score           * 0.20     # 1.0 - rejection_probability
) * 100

# Grades: A (85–100) · B (70–84) · C (55–69) · D (<55)
# submit_recommended = crs >= 70 (configurable: CRS_MIN_SUBMIT_THRESHOLD)
```

### 9.8 Adaptive Learning Engine

Records every operator correction and CEISA outcome. Feeds XGBoost retraining pipeline. Detects field-level extraction drift (>50 corrections in 30 days → alert for prompt update). `get_similar_past_submissions()` powers the AI Co-pilot "show similar declarations" feature.

---

## 10. Feature Requirements (All Tiers)

### Document Ingestion (Both Tiers)

**F-001:** Accept PDF, JPG, PNG, TIFF, WEBP, XLSX. Max 50MB/file, 3 files/batch. Auto-detect document type (classifier); if confidence < 0.80 → ask user to confirm.

**F-002:** XLSX Packing List handling — extract via openpyxl 3.2 (skip OCR), auto-detect header row, map columns via LLM mapper, output same structured JSON.

**F-003:** Batch grouping — partial batches allowed (1–2 docs), expire after 48h if incomplete.

### Operator Review (Both Tiers, different depth)

**F-010:** Split layout — 60% PDF.js document viewer (bounding box canvas overlay), 40% fields form. Click field → document jumps to that region.

**F-011:** Confidence badges per field — 🟢 HIGH ≥0.90 · 🟡 MEDIUM 0.70–0.89 · 🔴 LOW <0.70. Tooltip shows OCR confidence, LLM confidence, flag reason.

**F-012:** Inline field editing with undo, original value shown in gray, correction reason selector (Typo OCR / Wrong mapping / Data changed / Other). All corrections logged to audit_log with operator ID + timestamp + IP.

**F-013:** Line items grid (TanStack Table v8) — editable, sortable, bulk "Apply HS to similar items", row-level confidence score.

**F-014:** AI Co-pilot panel (Enterprise: full, SME: basic) — streamed responses. "Why was this flagged?" · "Suggest correction" · "Show similar past declarations"

**F-015:** CRS widget — live-updating as operator corrects fields. Expandable breakdown. Submit button disabled if CRS < threshold.

**F-016:** Rejection Risk widget — risk level + probability % + top-3 predicted reasons + "View similar rejections" link.

**F-017:** Blockchain status widget — shows anchoring status (pending/anchored), Polygonscan link, IPFS CID, "Download Certificate" button.

### CEISA Submission Workflow

**F-020:** Pre-submit modal checklist — CRITICAL rules PASS · all required fields filled · CRS ≥ threshold · HIGH/CRITICAL risk warning · operator confirmation checkbox.

**F-021:** Submission tracking — unique submission ID + idempotency key. Status machine: PENDING → QUEUED → SUBMITTED → CEISA_PROCESSING → ACCEPTED/REJECTED.

**F-022:** Rejection handling — AUTO_RECOVERABLE (system fixes + resubmits, logs both) · OPERATOR_REQUIRED (open review with error highlighted) · ADMIN_ESCALATION (lock + notify admin).

**F-023:** Re-submission — max 5 attempts (configurable). New idempotency key per attempt. Full version history accessible.

### SME-Specific Features

**F-030:** Guided Upload Wizard — Step 1: B/L · Step 2: PL · Step 3: Invoice. Each step has plain-language explanation + example screenshot + mobile camera capture button.

**F-031:** Simplified Review Mode — hides low-priority fields, plain language labels, "I don't know this field" → AI suggests from document.

**F-032:** HS Code Wizard — text input "what is your product?" → top-3 suggestions with duty + VAT rates.

**F-033:** "Summary for Broker" PDF export + direct WhatsApp share.

### Admin Features

**F-040:** Analytics dashboard — KPI cards, daily volume trend, CRS distribution, rejection reasons breakdown, operator performance table, field accuracy heatmap.

**F-041:** Learning engine monitoring — predictor AUC, training data size, field drift alerts, HS suggestion accuracy, manual retraining trigger.

**F-042:** Queue management — all declarations by status, assign to operators, priority queue, SLA tracker (4-hour target).

**F-043:** Blockchain audit log — table of all anchored declarations, tx hashes, block timestamps, verification status.

---

## 11. Data Models & Database Schema

### Supabase PostgreSQL 17 — Full Schema

```sql
-- ─────────────────────────────────────
-- USERS & COMPANIES (Supabase Auth integration)
-- ─────────────────────────────────────

CREATE TYPE user_tier AS ENUM ('enterprise', 'sme');
CREATE TYPE user_role AS ENUM ('operator', 'admin', 'supervisor', 'importer');

CREATE TABLE companies (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL,
    npwp                TEXT UNIQUE,
    tier                user_tier NOT NULL,
    submission_count    INTEGER DEFAULT 0,
    rejection_rate      DECIMAL(5,4) DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE profiles (
    id              UUID PRIMARY KEY REFERENCES auth.users(id),  -- Supabase Auth
    full_name       TEXT NOT NULL,
    tier            user_tier NOT NULL DEFAULT 'sme',
    role            user_role NOT NULL DEFAULT 'operator',
    company_id      UUID REFERENCES companies(id),
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Row Level Security
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can read own profile" ON profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Admins can read all profiles" ON profiles FOR SELECT USING (
    EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
);

-- ─────────────────────────────────────
-- DOCUMENT PROCESSING
-- ─────────────────────────────────────

CREATE TYPE doc_type AS ENUM ('bill_of_lading', 'packing_list', 'invoice');
CREATE TYPE batch_status AS ENUM (
    'uploaded', 'preprocessing', 'ocr_running', 'ocr_complete',
    'extracting', 'extracted', 'validating', 'validated',
    'review_ready', 'reviewing', 'approved', 'submitting', 'submitted',
    'accepted', 'rejected', 'error'
);

CREATE TABLE batches (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_by                  UUID REFERENCES profiles(id),
    company_id                  UUID REFERENCES companies(id),
    status                      batch_status DEFAULT 'uploaded',
    customs_readiness_score     DECIMAL(5,2),
    crs_grade                   CHAR(1),
    rejection_probability       DECIMAL(5,4),
    risk_level                  TEXT CHECK (risk_level IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    ceisa_submission_id         UUID,
    langgraph_thread_id         TEXT,   -- LangGraph checkpointer reference
    blockchain_tx_hash          TEXT,
    blockchain_block_number     BIGINT,
    ipfs_cid                    TEXT,
    expires_at                  TIMESTAMPTZ DEFAULT NOW() + INTERVAL '48 hours',
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);

-- Supabase Realtime: enable on batches for live operator dashboard
ALTER PUBLICATION supabase_realtime ADD TABLE batches;

CREATE TABLE documents (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id                UUID REFERENCES batches(id) ON DELETE CASCADE,
    doc_type                doc_type NOT NULL,
    original_name           TEXT NOT NULL,
    storage_path            TEXT NOT NULL,          -- Supabase Storage object path
    file_hash               CHAR(64) NOT NULL,      -- SHA-256
    file_size_bytes         INTEGER,
    language                TEXT DEFAULT 'en',
    has_text_layer          BOOLEAN DEFAULT FALSE,
    page_count              INTEGER DEFAULT 1,
    quality_score           DECIMAL(4,3),
    ocr_engine_used         TEXT,                   -- 'paddle' | 'azure_di' | 'ensemble'
    overall_ocr_confidence  DECIMAL(4,3),
    status                  batch_status DEFAULT 'uploaded',
    error_message           TEXT,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────
-- EXTRACTED FIELDS
-- ─────────────────────────────────────

CREATE TABLE extracted_fields (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id            UUID REFERENCES batches(id) ON DELETE CASCADE,
    document_id         UUID REFERENCES documents(id) ON DELETE CASCADE,
    ceisa_field         TEXT NOT NULL,
    raw_ocr_value       TEXT,
    extracted_value     TEXT,
    normalized_value    TEXT,
    confidence          DECIMAL(4,3) NOT NULL,
    confidence_level    TEXT GENERATED ALWAYS AS (
        CASE WHEN confidence >= 0.90 THEN 'HIGH'
             WHEN confidence >= 0.70 THEN 'MEDIUM'
             ELSE 'LOW' END
    ) STORED,
    extraction_method   TEXT,   -- 'direct_ocr' | 'llm_inferred' | 'cross_doc' | 'manual'
    source_page         INTEGER,
    bounding_box        JSONB,  -- {x, y, w, h}
    is_corrected        BOOLEAN DEFAULT FALSE,
    corrected_value     TEXT,
    correction_reason   TEXT,
    corrected_by        UUID REFERENCES profiles(id),
    corrected_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_extracted_fields_batch ON extracted_fields(batch_id);
CREATE INDEX idx_extracted_fields_field ON extracted_fields(ceisa_field);
ALTER PUBLICATION supabase_realtime ADD TABLE extracted_fields;

-- ─────────────────────────────────────
-- VALIDATION, HS RECOMMENDATIONS
-- ─────────────────────────────────────

CREATE TABLE validation_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id        UUID REFERENCES batches(id) ON DELETE CASCADE,
    rule_id         TEXT NOT NULL,
    rule_name       TEXT NOT NULL,
    severity        TEXT CHECK (severity IN ('PASS','WARNING','CRITICAL_FAIL')),
    error_message   TEXT,
    affected_fields TEXT[],
    resolved        BOOLEAN DEFAULT FALSE,
    resolved_by     UUID REFERENCES profiles(id),
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE hs_recommendations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id            UUID REFERENCES batches(id),
    line_item_index     INTEGER,
    product_description TEXT,
    recommendations     JSONB,  -- top-3: [{hs_code, description_id, confidence, duty_rate, reasoning}]
    selected_hs_code    TEXT,
    selected_by         UUID REFERENCES profiles(id),
    selected_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────
-- CEISA SUBMISSIONS
-- ─────────────────────────────────────

CREATE TABLE ceisa_submissions (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id                    UUID REFERENCES batches(id),
    idempotency_key             UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    payload_hash                CHAR(64),
    payload_encrypted           BYTEA,          -- AES-256
    ceisa_reference             TEXT,           -- CDO number from CEISA
    status                      TEXT DEFAULT 'pending',
    attempt_number              INTEGER DEFAULT 1,
    submitted_at                TIMESTAMPTZ,
    ceisa_responded_at          TIMESTAMPTZ,
    ceisa_response_encrypted    BYTEA,          -- AES-256
    error_code                  TEXT,
    error_classification        TEXT,           -- 'AUTO_RECOVERABLE' | 'OPERATOR_REQUIRED' | 'ADMIN_ESCALATION'
    auto_fixed                  BOOLEAN DEFAULT FALSE,
    parent_submission_id        UUID REFERENCES ceisa_submissions(id),
    created_at                  TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────
-- BLOCKCHAIN RECORDS
-- ─────────────────────────────────────

CREATE TABLE blockchain_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id        UUID REFERENCES batches(id),
    content_hash    CHAR(64) NOT NULL,
    merkle_root     CHAR(64),
    tx_hash         TEXT NOT NULL,
    block_number    BIGINT,
    network         TEXT DEFAULT 'polygon-amoy',  -- 'polygon-amoy' | 'polygon-pos'
    polygonscan_url TEXT,
    ipfs_cid        TEXT,
    anchored_at     TIMESTAMPTZ,
    verified        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────
-- ADAPTIVE LEARNING
-- ─────────────────────────────────────

CREATE TABLE learning_samples (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id            UUID REFERENCES batches(id),
    field_name          TEXT NOT NULL,
    extracted_value     TEXT,
    corrected_value     TEXT NOT NULL,
    correction_reason   TEXT,
    operator_id         UUID REFERENCES profiles(id),
    used_in_training    BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE submission_outcomes (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id               UUID REFERENCES ceisa_submissions(id),
    batch_id                    UUID REFERENCES batches(id),
    outcome                     TEXT CHECK (outcome IN ('accepted', 'rejected')),
    rejection_codes             TEXT[],
    feature_snapshot            JSONB,
    predicted_rejection_prob    DECIMAL(5,4),
    used_in_training            BOOLEAN DEFAULT FALSE,
    created_at                  TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────
-- AUDIT LOG (IMMUTABLE — Supabase RLS)
-- ─────────────────────────────────────

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

-- Immutable via RLS: app_role can INSERT only
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Insert only" ON audit_log FOR INSERT WITH CHECK (true);
CREATE POLICY "Read own company audit" ON audit_log FOR SELECT USING (
    EXISTS (SELECT 1 FROM batches b JOIN profiles p ON p.id = auth.uid()
            WHERE b.id = audit_log.batch_id AND b.company_id = p.company_id)
);

CREATE INDEX idx_audit_log_batch ON audit_log(batch_id);
CREATE INDEX idx_audit_log_time ON audit_log(created_at);
```

---

## 12. API Contracts

### Authentication
All endpoints require Supabase Auth JWT (Bearer token). Public exceptions: `/health`, simulator endpoints.

```
POST /api/v1/batches
  Body: multipart/form-data  files[]: File[] (max 3), tier: "enterprise"|"sme"
  Response 201: { batch_id, documents: [{id, type, status}], expires_at, langgraph_thread_id }

GET /api/v1/batches/{batch_id}
  Response 200:
  {
    batch_id, status, created_at,
    documents: [{id, type, status, ocr_confidence}],
    extracted_fields: [{ceisa_field, value, confidence, confidence_level, is_corrected}],
    validation_results: [{rule_id, severity, error_message, resolved}],
    hs_recommendations: [{line_item, candidates[]}],
    crs: {score, grade, submit_recommended, blocking_issues[], improvement_hints[]},
    rejection_prediction: {probability, risk_level, top_reasons[]},
    blockchain: {status, tx_hash, polygonscan_url, ipfs_cid}
  }

PATCH /api/v1/batches/{batch_id}/fields
  Body: { corrections: [{field_name, corrected_value, correction_reason}] }
  Response 200: { updated_count, new_crs, updated_risk }

POST /api/v1/batches/{batch_id}/submit
  Body: { confirmed: true }
  Response 202: { submission_id, queued_at }

GET  /api/v1/batches/{batch_id}/document/{doc_id}/preview
  Response: PDF stream (Content-Type: application/pdf, presigned Supabase Storage URL)

POST /api/v1/hs-recommend
  Body: { product_description, context?: string }
  Response 200: { recommendations: [{hs_code, description_id, confidence, duty_rate, vat_rate, reasoning}] }

GET /api/v1/batches
  Query: status, date_from, date_to, company_id, risk_level, page, limit
  Response 200: { items[], total, page, pages }

GET /api/v1/analytics/dashboard
  Response 200: { kpi_cards, daily_volume_30d, crs_distribution, rejection_reasons, operator_stats }

GET /api/v1/blockchain/{batch_id}/verify
  Response 200: { valid, tx_hash, block_number, timestamp, content_hash, polygonscan_url }
```

### Supabase Realtime Events (Postgres CDC → Client)
```
Channel: batch:{batch_id}
  INSERT/UPDATE on batches      → status change event
  INSERT on extracted_fields    → field extraction progress
  INSERT on validation_results  → validation complete
  UPDATE on batches (crs set)   → CRS computed
  
Channel: admin:queue
  INSERT on batches             → new declaration entered queue
  UPDATE on batches (assigned)  → assignment changed
```

### LangGraph Streaming (SSE endpoint)
```
GET /api/v1/batches/{batch_id}/stream
  Response: text/event-stream
  Events: { node: "ocr_agent", status: "running|complete", data: {...} }
```

---

## 13. State Machines & Workflow Logic

### Batch Status State Machine
```
UPLOADED → PREPROCESSING → OCR_RUNNING → OCR_COMPLETE → EXTRACTING → EXTRACTED
         → VALIDATING → VALIDATED → REVIEW_READY → REVIEWING → APPROVED
         → SUBMITTING → SUBMITTED → ACCEPTED (terminal)
                                  → REJECTED → (resubmit up to 5× → REVIEWING)
         → ERROR (terminal, any stage)
```

### CEISA Retry + Circuit Breaker
```
Submit attempt:
  200 OK         → ACCEPTED
  4xx (non-422)  → REJECTED (classify)
  422            → REJECTED (auto-fix if AUTO_RECOVERABLE, else OPERATOR_REQUIRED)
  429            → wait 60s → retry (not counted as attempt)
  5xx/timeout    → exponential backoff: 1s · 2s · 4s · 8s · 16s (jitter ±10%)
  After 5 fails  → DEAD_LETTER_QUEUE → admin alert

Circuit breaker: OPEN after 3 consecutive 5xx · HALF_OPEN after 60s · CLOSED on next success
```

---

## 14. Tech Stack — Complete Reference (2026)

### Backend

| Component | Package | Version | Notes |
|-----------|---------|---------|-------|
| API Framework | fastapi | 0.115.x | Async, lifespan events |
| Runtime | Python | 3.13 | Free-threaded GIL mode for OCR workers |
| ASGI Server | uvicorn[standard] | 0.34.x | Behind Traefik |
| Reverse Proxy | traefik | 3.2.x | Auto TLS, microservice routing, dashboard |
| Task Queue | celery | 5.5.x | Redis 8 native broker |
| Message Broker | **redis 8 standalone** | 8.0 | **Native RESP3** — not HTTP. Celery + LangGraph checkpointer |
| Redis Client | redis-py | 5.x | Async mode |
| Multi-Agent | langgraph | 0.3.x | Stateful agent graph with HitL checkpoints |
| Agent Checkpoints | langgraph-checkpoint-redis | latest | **Redis 8 native** — requires RESP3 |
| LLM Orchestration | langchain | 0.3.x | Prompt templates, few-shot examples |
| LLM Tracing | langsmith | 0.2.x | Full LLM observability |
| WebSocket Server | python-socketio | 5.x | **Agent streaming** — different role from Supabase Realtime |
| ORM | sqlalchemy | 2.0.x | Async with asyncpg |
| DB Driver | asyncpg | 0.30.x | Native PostgreSQL async |
| Database | Supabase (PostgreSQL 17) | — | BaaS + Realtime (CDC) + Storage + Edge Functions |
| Auth Provider | **Keycloak 26** | **26.1.x** | **Primary OIDC — multi-tenant RBAC, LDAP, offline tokens** |
| JWT Validation | python-jose | 3.3.x | Validates Keycloak RS256 JWT against JWKS endpoint |
| Supabase Client | supabase-py | 2.x | Realtime subscriptions, Storage, Edge Functions |
| HTTP Client | httpx | 0.28.x | Async; CEISA H2H calls |
| Validation | pydantic | 2.11.x | v2 model_config |
| Settings | pydantic-settings | 2.x | .env + environment |
| Logging | structlog | 25.x | JSON structured logs |
| Package Manager | **uv** | **0.5.x** | **Replaces pip/poetry — 100× faster, lockfile-native** |
| Migrations | supabase CLI | 2.x | Via GitHub Actions |
| Error Tracking | sentry-sdk[fastapi] | 2.x | With Profiling (CPU flamegraphs) |
| APM | opentelemetry-sdk | 1.x | Traces + spans → OTEL Collector → Jaeger |
| Secrets | doppler | — | .env replacement, secret rotation |

### AI / OCR / ML

| Component | Package | Version | Notes |
|-----------|---------|---------|-------|
| Primary OCR | paddleocr | 2.9.x | PP-OCRv4 + PP-StructureV3 |
| PDF text extract | pdfplumber | 0.11.x | Text layer detection |
| PDF render | pymupdf | 1.25.x | High-quality 300 DPI render |
| Image processing | opencv-python | 4.11.x | Full preprocessing pipeline |
| Language detect | lingua-py | 2.0.x | More accurate than langdetect |
| Excel parsing | openpyxl | 3.2.x | Packing List XLSX |
| Azure DI fallback | azure-ai-documentintelligence | 1.0.x | prebuilt-invoice / prebuilt-document |
| LLM (primary) | gemini | 0.40.x | gemini-2.5-pro |
| LLM (fallback) | gemini | 0.40.x | gemini-2.0-flash |
| Embeddings | openai | 1.x | text-embedding-3-small (HS RAG) |
| Vector DB | chromadb | 0.6.x | Persistent, local, HS collection |
| ML model | xgboost | 2.1.x | Rejection predictor |
| ML utilities | scikit-learn | 1.6.x | Feature preprocessing, eval |
| Model serialization | joblib | 1.4.x | Model versioning to Supabase Storage |

### Frontend

| Component | Package | Version | Notes |
|-----------|---------|---------|-------|
| Framework | next | 15.3.x | App Router + PPR + Turbopack |
| Language | typescript | 5.8.x | strict mode |
| Package Manager | **pnpm** | **9.x** | **Replaces npm — 70% faster, strict hoisting** |
| Monorepo Build | **turborepo** | **2.x** | Task graph + Vercel Remote Cache |
| Styling | tailwindcss | 4.1.x | CSS-first config |
| Lint + Format | **biome** | **1.9.x** | **Replaces ESLint+Prettier — single binary, 20× faster** |
| UI Primitives | shadcn/ui + @radix-ui | latest | Accessible, composable |
| Auth (Frontend) | **next-auth** | **5.x** | **Keycloak OIDC provider** |
| API Type Safety | **trpc** | **11.x** | **End-to-end types: FastAPI ↔ Next.js** |
| State | zustand | 5.0.x | Client state |
| Server State | @tanstack/react-query | 5.x | tRPC integrates natively |
| Forms | react-hook-form | 7.x + zod 3.x | |
| Table | @tanstack/react-table | 8.x | Line items grid |
| Charts | recharts | 2.15.x | Analytics dashboard |
| PDF Viewer | pdfjs-dist | 4.x | Document viewer + canvas bounding box overlay |
| Supabase Realtime | @supabase/supabase-js | 2.x | **DB-level CDC events** (status, fields, validation) |
| Agent Streaming | **socket.io-client** | **4.8.x** | **LangGraph progress + LLM token streaming** |
| Web3 | ethers | 6.x | Polygon blockchain interaction |
| Animations | motion | 12.x | Framer Motion v12 |
| Icons | lucide-react | 0.400.x | |
| Dates | date-fns | 4.x | |
| Notifications | sonner | 2.x | Toast |
| Unit Tests | **vitest** | **2.x** | **Replaces Jest — native ESM, 10× faster** |
| E2E Tests | playwright | 1.x | Smoke + screenshot regression |

### Blockchain

| Component | Package | Version | Notes |
|-----------|---------|---------|-------|
| Smart contracts | Solidity | 0.8.28 | |
| Dev framework | hardhat | 2.22.x | |
| Contract libs | @openzeppelin/contracts | 5.x | Ownable, MerkleProof |
| Web3 JS | ethers.js | 6.x | Frontend Polygon interaction |
| Web3 Python | web3.py | 7.x | Backend blockchain service |
| IPFS | pinata-web3 | 1.x | Metadata pinning |
| Testnet | Polygon Amoy | — | Chain ID 80002 |
| Mainnet | Polygon PoS | — | Chain ID 137 |

### Infrastructure & DevOps

| Component | Tool | Notes |
|-----------|------|-------|
| Containers | docker 27.x | |
| Compose | docker compose 2.x | Local full-stack dev |
| Frontend Deploy | Vercel | Edge, preview per PR, Remote Cache |
| Backend Deploy | Railway | Docker autoscale (API ×2, Worker ×3) |
| Auth Server | **Keycloak 26 (Railway Docker)** | **Enterprise OIDC — not replaced** |
| DB / Realtime / Storage | Supabase | BaaS |
| Redis | **Redis 8 standalone (Railway)** | **Native protocol — Celery + LangGraph** |
| File Storage (local dev) | MinIO 7.x | Docker Compose only — S3 API parity |
| CI/CD | GitHub Actions | lint · test · eval-ai · db-migrate · blockchain · docker-build |
| Metrics | Prometheus 3 + Grafana 11 | |
| Tracing | OpenTelemetry 1 + OTEL Collector + Jaeger | Distributed traces |
| Errors | Sentry (errors + **CPU Profiling**) | |
| Analytics + Feature Flags | PostHog | Funnels, A/B, flag management |
| Secrets | Doppler | Secret rotation, per-environment |

---

## 15. CEISA Integration Specification

*(Identical to v2.0 PRD Section 10 — assumed API spec based on PIB standard)*

**Base URLs:**
- Demo: `http://ceisa-simulator:8001/api/v4`
- Production: `https://ceisa.beacukai.go.id/api/v4`

**Endpoints:** `POST /declarations` · `GET /declarations/{id}` · `GET /declarations/{id}/response`

**Auth:** Bearer JWT, TTL 3600s

**Key request headers:** `X-Idempotency-Key`, `X-Source-System: TradeFlowAI-v4`, `X-Submission-Type: PIB`

**Retry config:**
```python
CEISA_RETRY_CONFIG = {
    "max_attempts": 5,
    "initial_delay_seconds": 1,
    "backoff_multiplier": 2,
    "jitter_factor": 0.1,
    "retryable_status_codes": [429, 500, 502, 503, 504],
    "circuit_breaker_threshold": 3,
    "circuit_breaker_timeout_seconds": 60,
}
```

**Error Code Dictionary:** E001 (B/L format) · E004 (HS Code invalid) → trigger_hs_recommendation · E007 (date format) → AUTO_RECOVERABLE · E012 (NPWP not registered) → ADMIN_ESCALATION · E015 (CIF inconsistent) → OPERATOR_REQUIRED · E019 (country code) → AUTO_RECOVERABLE

---

## 16. CEISA Simulator Specification

Six configurable scenarios (identical to v2.0) — see PRD v2.0 Section 11 for full scenario definitions.

**Scenarios:** S01 Always Approve · S02 30% Reject E004 · S03 20% Reject E012 · S04 Timeout 35s · S05 503 for 60s · S06 Mixed Realistic (70/20/10 split)

**Extra endpoints (demo-only):** `GET/PUT /simulator/scenarios/active` · `GET /simulator/logs` · `GET /simulator/stats`

---

## 17. Dashboard & UI Specifications

### Routes
```
/                     → redirect /dashboard
/login                → Supabase Auth
/dashboard            → role-aware overview (Enterprise vs SME)
/batches/new          → upload wizard
/batches/{id}         → batch detail + review
/batches/{id}/review  → full operator review screen
/batches/{id}/status  → submission status + CEISA + blockchain
/batches              → list with filters
/analytics            → admin analytics (role: admin, supervisor)
/simulator            → CEISA simulator control panel (admin)
/blockchain           → blockchain audit log (admin)
/settings             → preferences, company, team (Enterprise)
```

### Component Architecture
```
ReviewScreen
├── DocumentViewer (PDF.js)
│   ├── PageNavigator · BoundingBoxOverlay (canvas) · ZoomControls
├── FieldsPanel
│   ├── SectionGroups → FieldRow (ConfidenceBadge · InlineEditField · FieldTooltip)
│   └── LineItemsGrid (TanStack Table v8)
├── CRSWidget (live-updating via Supabase Realtime)
├── RejectionRiskWidget
├── BlockchainStatusWidget (tx hash · Polygonscan link · IPFS · certificate download)
├── ValidationIssuesList
├── AICopilotPanel (streamed SSE responses)
└── SubmitBar → PreSubmitChecklist (modal) → SubmitButton
```

---

## 18. Dual-Tier System

| Feature | SME | Enterprise |
|---------|-----|-----------|
| Guided wizard | ✅ | Optional |
| Full review UI | Simplified | Full |
| AI Co-pilot | Basic | Full streaming |
| Rejection prediction | Rule-based | Full XGBoost ML |
| Bulk/batch upload | ❌ | ✅ (50/day) |
| Analytics dashboard | ❌ | ✅ |
| ERP/TMS API | ❌ | ✅ |
| Team management | ❌ | ✅ |
| Priority queue | ❌ | ✅ |
| Custom HS dictionaries | ❌ | ✅ |
| Blockchain audit cert | Basic | Full (Merkle batch) |
| WhatsApp notifications | ✅ | ✅ |
| "Summary for broker" PDF | ✅ | ❌ |
| Processing SLA | Best effort | 4h guaranteed |

---

## 19. Non-Functional Requirements

| Category | Requirement | Target |
|----------|-------------|--------|
| Performance | OCR per 3-doc batch (CPU) | P95 < 45s |
| Performance | OCR per 3-doc batch (GPU) | P95 < 15s |
| Performance | LLM extraction per batch | P95 < 30s |
| Performance | API endpoints (non-async) | P95 < 200ms |
| Performance | Dashboard initial load | LCP < 2s |
| Accuracy | OCR digital PDF | ≥ 95% field accuracy |
| Accuracy | OCR scanned/photo | ≥ 85% field accuracy |
| Accuracy | HS code RAG top-1 | ≥ 75% |
| Accuracy | Rejection prediction AUC | ≥ 0.75 (after 500 samples) |
| Reliability | API uptime (demo) | 99.5% |
| Concurrency | Simultaneous operators | 50 (load tested) |
| Security | Auth | Supabase Auth JWT + RLS, no hardcoded secrets |
| Security | Data at rest | AES-256 for CEISA payloads |
| Security | Transport | TLS 1.3 minimum (Vercel/Railway enforce) |
| Security | Audit log | Immutable via RLS (INSERT only for app role) |
| Blockchain | Anchoring latency | < 30s (Polygon Amoy testnet) |
| Blockchain | Gas per tx | < 100,000 gas |
| Data | Retention | 7 years (customs regulation) |
| Data | PII compliance | Encrypted at rest, access logged, synthetic data in demo |
| Accessibility | Key screens | WCAG 2.1 AA |

---

## 20. Error Handling & Fallback Logic

### OCR Pipeline
```
Text layer detected (pdfplumber) → extract directly (confidence=0.98), skip OCR
No text layer → PaddleOCR
  PaddleOCR page avg confidence ≥ 0.78 → proceed
  PaddleOCR confidence < 0.78 → also run Azure DI (parallel)
    Ensemble: higher confidence per field wins
    Numeric >5% discrepancy → flag mandatory review
    Both fail → ERROR status → admin alert
  Azure DI exception → proceed with PaddleOCR only, flag "ocr_degraded"
```

### LLM Extraction
```
Gemini API OK → proceed
Gemini timeout (> 30s) → retry once → if again → rule-based extractor fallback
Gemini 5xx → wait 2s → retry once → rule-based fallback
Gemini 4xx (token limit) → chunk document into sections → extract per section → merge
Rule-based extractor: regex + keyword lookup for NPWP, B/L number, dates (zero latency)
```

### Feature Flag Degradation

| Flag | Default | Effect when disabled |
|------|---------|---------------------|
| `ENABLE_AZURE_DI_FALLBACK` | true | PaddleOCR only |
| `ENABLE_REJECTION_PREDICTION` | true | CRS only, no ML prediction |
| `ENABLE_HS_RAG` | true | Manual HS entry only |
| `ENABLE_AI_COPILOT` | true | Hide co-pilot panel |
| `ENABLE_BLOCKCHAIN` | true | Skip anchoring, log locally |
| `ENABLE_NOTIFICATIONS_WHATSAPP` | true | Email only |
| `COST_SAVING_MODE` | false | Use gemini-2.5-flash instead of pro |

---

## 21. Feature Flags & Environment Variables

```env
# ── App ──────────────────────────────────────────
APP_ENV=development|staging|production
APP_SECRET_KEY=...

# ── Supabase ─────────────────────────────────────
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...

# ── Redis (Upstash) ───────────────────────────────
UPSTASH_REDIS_REST_URL=https://...upstash.io
UPSTASH_REDIS_REST_TOKEN=...
CELERY_BROKER_URL=redis://...upstash.io:6379

# ── AI Services ───────────────────────────────────
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL_PRIMARY=gemini-3.1-pro
GEMINI_MODEL_FALLBACK=gemini-2.5-flash
OPENAI_API_KEY=...             # text-embedding-3-small
AZURE_DI_ENDPOINT=https://....cognitiveservices.azure.com/
AZURE_DI_KEY=...
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=tradeflow-ai-v3

# ── CEISA ─────────────────────────────────────────
CEISA_BASE_URL=http://ceisa-simulator:8001   # swap to real in prod
CEISA_CLIENT_ID=...
CEISA_CLIENT_SECRET=...
CEISA_REQUEST_TIMEOUT_SECONDS=30

# ── Blockchain ────────────────────────────────────
POLYGON_RPC_URL=https://rpc-amoy.polygon.technology
POLYGON_MAINNET_RPC_URL=https://polygon-rpc.com
CONTRACT_ADDRESS=0x...
OPERATOR_WALLET_PRIVATE_KEY=...  # via Doppler, never in git
PINATA_JWT=...
PINATA_GATEWAY=https://gateway.pinata.cloud

# ── Notifications ─────────────────────────────────
RESEND_API_KEY=...
WHATSAPP_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID=...

# ── Feature Flags ─────────────────────────────────
ENABLE_AZURE_DI_FALLBACK=true
ENABLE_REJECTION_PREDICTION=true
ENABLE_HS_RAG=true
ENABLE_AI_COPILOT=true
ENABLE_BLOCKCHAIN=true
ENABLE_NOTIFICATIONS_WHATSAPP=true
COST_SAVING_MODE=false
CRS_MIN_SUBMIT_THRESHOLD=55
MAX_RESUBMIT_ATTEMPTS=5

# ── MCP (dev tooling, not runtime) ───────────────
GITHUB_TOKEN=...
SUPABASE_ACCESS_TOKEN=...
LINEAR_API_KEY=...
SENTRY_AUTH_TOKEN=...
VERCEL_TOKEN=...
POSTHOG_API_KEY=...

# ── Thresholds ────────────────────────────────────
OCR_CONFIDENCE_FALLBACK_THRESHOLD=0.78
LLM_CONFIDENCE_REVIEW_THRESHOLD=0.70
REJECTION_RISK_BLOCK_THRESHOLD=0.70
```

---

## 22. Observability & Evaluation Framework

### LangSmith — LLM Tracing
Every LLM call tagged: `document_id`, `batch_id`, `doc_type`, `prompt_version`, input/output token counts, latency, operator correction (feedback).

### Sentry — Error Tracking
Source maps uploaded on deploy. Performance transactions on OCR pipeline + CEISA submission. Alerts: P95 latency breach · error rate spike · blockchain tx failure.

### PostHog — Product Analytics
Events: `document_uploaded` · `ocr_complete` · `review_started` · `field_corrected` · `submission_sent` · `ceisa_accepted/rejected`. Funnel: upload → submit. Feature flags managed here.

### Prometheus + Grafana
```python
# Key metrics
tradeflow_ocr_duration_seconds_histogram          # by doc_type, engine
tradeflow_extraction_confidence_histogram          # by field_name
tradeflow_ceisa_submission_total_counter           # by outcome
tradeflow_rejection_prediction_auc_gauge           # current model AUC
tradeflow_crs_distribution_histogram               # score distribution
tradeflow_llm_tokens_total_counter                 # by model, direction
tradeflow_blockchain_tx_duration_seconds           # anchoring latency
tradeflow_queue_depth_gauge                        # Celery task queue
```

### Automated AI Evaluation (CI Gate)
```python
# eval/run_eval.py — runs on every push touching AI modules or prompts
# 20 labeled CIPL sets in eval/fixtures/ with ground truth JSON

METRICS = {
    "field_extraction_accuracy":        target ≥ 0.92 (critical fields exact + text fuzzy)
    "hs_recommendation_top1_accuracy":  target ≥ 0.75
    "cross_doc_validation_recall":      target ≥ 0.95
    "processing_time_p95_cpu_seconds":  target ≤ 45
}
# CI gate: >5% regression from baseline blocks PR merge
```

---

## 23. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| CEISA 4.0 schema undocumented | High | High | Own JSON schema based on PIB form; hot-reloadable JSON |
| OCR low accuracy on poor scans | Medium | High | Azure DI fallback + human review escalation at confidence < 0.70 |
| Gemini API latency/outage | Low | Medium | Async queue + 30s timeout + rule-based extractor fallback |
| Polygon Amoy testnet instability | Medium | Low | Feature flag `ENABLE_BLOCKCHAIN=false` for graceful degradation; local Hardhat node as last resort |
| HS Code DB unavailable | Medium | Medium | 10,000+ codes embedded locally in ChromaDB seed; monthly refresh |
| LangGraph state corruption | Low | High | Redis checkpointing; idempotent node design; dead letter queue |
| XGBoost cold start (<500 samples) | High (early) | Medium | Rule-based heuristics until 500 samples; clearly labeled as "v0 prediction" |
| Supabase rate limits on demo day | Low | High | Connection pooling via PgBouncer (Supabase built-in); query caching |
| Demo data privacy | Low | High | All demo documents synthetic/fictitious — no real PII |
| Gas price spike (Polygon) | Low | Low | EIP-1559 dynamic pricing; max fee cap; demo uses Amoy (free) |
| Worker crashes mid-pipeline | Low | Medium | LangGraph Redis checkpointing → automatic resume on restart |

---

## 24. Delivery Milestones

### Sprint Plan (8 Weeks)

**Week 1–2: Foundation**
- Turborepo monorepo setup (FastAPI + Next.js 15 + Hardhat + packages)
- Docker Compose: all local services (Supabase local, Upstash Redis mock, Traefik)
- Supabase schema + migrations via CLI
- Supabase Auth (JWT) integration
- Document upload → Supabase Storage
- Basic OCR pipeline (PaddleOCR 2.9, preprocessing)
- CEISA JSON schema definition (`ceisa_schema_v4.json`)
- All MCP configs wired: GitHub, Supabase, Linear, Sentry (`.mcp.json`)
- GitHub Actions: lint + test + docker build CI

**Week 3–4: AI Core**
- LangGraph agent graph scaffolding (all nodes, conditional edges)
- PDF text layer extraction (pdfplumber)
- Azure DI fallback integration
- Multimodal LLM extraction agents (Gemini API + image + OCR)
- Cross-document validation engine (JSON rules, hot-reload)
- HS Code RAG (ChromaDB + BTKI seed + OpenAI embeddings + Gemini reranker)
- CRS computation (rule-based v1)

**Week 5: Prediction & Learning**
- Rejection prediction feature engineering
- 500+ synthetic labeled submissions seeded
- XGBoost initial model training
- Adaptive learning data collection (corrections, outcomes)
- Model retraining pipeline + versioning to Supabase Storage

**Week 6: Blockchain + CEISA Integration**
- `DocumentRegistry.sol` + `SubmissionAudit.sol` (Hardhat)
- Deploy to Polygon Amoy (GitHub Actions workflow)
- `blockchain_svc` (web3.py + Pinata IPFS)
- CEISA Simulator (all 6 scenarios)
- `ceisa_gateway` service (H2H, retry, circuit breaker)
- Error code dictionary + auto-fix handlers
- Re-submission workflow

**Week 7: Dashboard + Realtime**
- Full operator review UI (PDF.js + bounding boxes + fields panel)
- Supabase Realtime subscriptions for live status
- SME wizard flow + HS Code wizard
- Analytics dashboard (admin)
- Blockchain status widget + Polygonscan verification
- CEISA simulator control panel
- Notification system (Resend email + WhatsApp Cloud API)
- PostHog + Sentry integration

**Week 8: Polish + Demo Prep**
- 15 diverse synthetic CIPL documents (eval/fixtures/)
- End-to-end demo flow rehearsal (< 90s target)
- Performance optimization (async parallelism, caching)
- Prometheus + Grafana setup
- Full evaluation framework run (CI gate must pass)
- Vercel + Railway production deploy
- Demo script + Q&A prep

### Definition of Done (per feature)
1. Unit tests pass (≥ 70% coverage on AI modules)
2. API contract matches Section 12 specification
3. AI evaluation metrics meet Section 22 targets
4. Error handling implemented per Section 20
5. Feature flag respected (graceful degradation works)
6. Audit log records all relevant events
7. MCP-accessible (Supabase schema, GitHub issue for bugs)

---

## Appendix A: Sample CIPL Evaluation Dataset (15 Documents)

1. Digital PDF invoice — standard EN, single currency
2. Digital PDF invoice — ID format, IDR + USD mixed
3. Scanned invoice — good quality, single page
4. Scanned invoice — poor quality (phone photo, blurry)
5. Digital PDF packing list — 12 items, simple table
6. Digital PDF packing list — 80 items, multi-page, complex table
7. Excel packing list (.xlsx) — clean format
8. Excel packing list (.xlsx) — messy headers, merged cells
9. Scanned packing list — dot matrix print, 25 items
10. Bill of Lading — standard HLCU format
11. Bill of Lading — non-standard (local carrier)
12. Multi-language invoice — English + Chinese annotations
13. Incomplete invoice — missing CIF fields (tests fallback)
14. Invoice with HS code error — tests rejection prediction
15. Full CIPL batch — contains deliberate cross-doc inconsistency (tests CV rules)

Each: `eval/fixtures/{n}/expected.json` (ground truth) + `eval/fixtures/{n}/docs/`

---

## Appendix B: Future Enhancements (Post-Competition)

- **PEB (Export declarations):** Extend schema for export PIB/PEB
- **ERP/TMS connectors:** SAP S/4HANA, Oracle TMS, Odoo via webhooks
- **Mobile app:** React Native with camera capture
- **Hyperledger Fabric:** Private chain for enterprise multi-party document sharing
- **API marketplace:** Third-party customs brokers integrate via API
- **Multi-language UI:** Full Bahasa Indonesia localization
- **LangGraph Platform:** Hosted agent deployment for enterprise scale
- **Real CEISA integration:** When official API spec becomes available

---

*TradeFlow AI v3.0 — Reducing Trade Friction Through Predictive Customs Intelligence*  
*AI Open Innovation Challenge 2026 — Cikarang Dry Port Track*  
*Internal development spec. Competition pitch materials in separate document.*