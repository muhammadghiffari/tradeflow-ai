# TradeFlow AI 🚢

[![AI Open Innovation Challenge 2026](https://img.shields.io/badge/AI_Open_Innovation_Challenge_2026-Cikarang_Dry_Port-blue?style=for-the-badge)](#)
[![DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/muhammadghiffari/tradeflow-ai)
[![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-FF6B6B?style=for-the-badge)](https://langchain-ai.github.io/langgraph/)
[![CEISA 4.0](https://img.shields.io/badge/CEISA_4.0-Ready-00A65A?style=for-the-badge)](https://ceisa40.customs.go.id/)
[![Accuracy](https://img.shields.io/badge/OCR_Accuracy-90.59%25_ANLS-8A2BE2?style=for-the-badge)](#)
[![INSW](https://img.shields.io/badge/INSW_Detection-100%25-00C851?style=for-the-badge)](#)

<div align="center">
  <br />
  <a href="https://tradeflow-ai.vercel.app">
    <img src="https://img.shields.io/badge/🌐_Try_Live_24/7_Demo-FF0055?style=for-the-badge" alt="Live Demo" />
  </a>
  &nbsp;&nbsp;&nbsp;
  <a href="./docs/E2E_Runbook.md">
    <img src="https://img.shields.io/badge/💻_Run_Locally_(Docker)-0078D6?style=for-the-badge" alt="Run Locally" />
  </a>
  <br /><br />
</div>

> [!WARNING]
> **Important Note for Judges & Reviewers:** 
> - 🌐 **Live 24/7 Demo:** Runs on a $0 budget architecture using a lightweight **Google Gemini Fallback** to enable 24/7 access without a GPU. **This mode bypasses the Multi-Agent Orchestration.**
> - 💻 **Run Locally (Docker):** This is the **TRUE TradeFlow AI experience**. It runs the complete LangGraph Multi-Agent Orchestration (Surya, PaddleOCR, Azure DI) and utilizes our custom **fine-tuned `olmOCR-2-7B-CIPL` model**. We highly recommend evaluating the Local Docker deployment or reviewing our Demo Video to witness the full orchestration architecture in action.

**Predictive Customs Intelligence Platform**

TradeFlow AI transforms fragmented CIPL trade documents (Bill of Lading, Packing List, Commercial Invoice) into validated, CEISA 4.0-compliant import declarations. Powered by a multi-agent Vision-Language Model ensemble, proactive rejection risk prediction, an immutable blockchain audit trail, and an adaptive learning system.

---

## 🌟 Key Features

*   **Multi-Agent OCR Ensemble:** Parallel processing using Surya 2, PaddleOCR 3.0, Azure DI 4.0, and a fine-tuned olmOCR-2-7B model to extract structured CEISA JSON from messy documents.
*   **Confidence Reconciliation:** Automatically merges outputs from all agents per field, using majority voting and anomaly detection to flag uncertain fields for human review.
*   **Proactive Rejection Prediction:** XGBoost ML model evaluates maritime signals (vessel history, route) and document inconsistencies to predict CEISA rejection probability *before* submission.
*   **RAG-based HS Code Recommendation:** Utilizes ChromaDB and Gemini reranker to suggest highly accurate 8-digit BTKI codes.
*   **Immutable Audit Trail:** Anchors document hashes on the Polygon blockchain for a tamper-proof 7-year compliance record.
*   **Vessel Validation:** Cross-checks extracted vessel names, IMOs, and ETAs against live AIS and vessel characteristics databases.

## 🏗️ Architecture

TradeFlow AI is built on a robust, modern stack:

*   **Orchestration:** LangGraph 0.3+ for stateful multi-agent workflows with human-in-the-loop checkpoints.
*   **AI Models:** olmOCR-2-7B (Fine-tuned), Surya 2, PaddleOCR 3.0, MinerU 2.5, XGBoost.
*   **Backend:** FastAPI, Python 3.13, Celery, Redis.
*   **Database:** Supabase (PostgreSQL 17), ChromaDB.
*   **Frontend:** Next.js 16, Shadcn UI, Supabase Realtime, Socket.io.
*   **Infrastructure:** Docker Build Cloud, GitHub Actions, Traefik.

## 🚀 Getting Started

### Prerequisites

*   Docker & Docker Compose
*   Node.js 20+
*   Python 3.13+
*   Supabase CLI

### Local Development Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/muhammadghiffari/tradeflow-ai.git
    cd tradeflow-ai
    ```

2.  **Environment Variables:**
    Copy the example env file and configure your API keys (HuggingFace, Gemini, Supabase, etc.).
    ```bash
    cp .env.example .env
    ```

3.  **Start the Local Stack:**
    ```bash
    docker-compose up -d
    ```
    *Note: AI model weights will be downloaded from the HuggingFace Hub on first startup.*

4.  **Access the Dashboard:**
    Open `http://localhost:3000` in your browser.

## 📚 Documentation

For complete technical specifications, see our [Product Requirements Document (PRD)](./docs/TradeFlow_PRD_v5.2.md).

## 🛡️ License

This project is built for the AI Open Innovation Challenge 2026. All rights reserved.
