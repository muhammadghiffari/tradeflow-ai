"""
TradeFlow AI — LangGraph Declaration State (T-033)

DeclarationState is the single shared typed dictionary threaded
through the entire LangGraph pipeline. It persists to Redis via
RedisSaver (langgraph-checkpoint-redis) after every node.

SDD §2.2 — State Definition
PRD Invariant #6: Graph state persisted via Redis (not in-memory).
"""

from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict


class DeclarationState(TypedDict):
    """
    Complete state of a single import declaration batch.
    Every field is optional (TypedDict total=False defaults handled per node).
    """

    # ── Core identifiers ─────────────────────────────────────────────────────
    batch_id: str
    langgraph_thread_id: str
    tier: Literal["enterprise", "sme"]

    # ── Input documents ───────────────────────────────────────────────────────
    documents: list[dict]
    # Each dict: {id, doc_type, storage_path, quality_score, file_hash}

    # ── Preprocessing (T-035) ─────────────────────────────────────────────────
    preprocessed: list[dict]
    # Each dict:
    # {
    #   id, doc_type, processing_route, carrier_scac,
    #   images_b64: list[str], has_text_layer, quality_score,
    #   page_count, page_types, signed_url
    # }

    # ── Multi-agent OCR outputs (T-036) ──────────────────────────────────────
    surya_output: list[dict | None]
    # Agent A (Surya 2): {text_blocks, layout, html, confidence, tables}

    layout_analysis: list[dict | None]
    # Agent B (PaddleOCR): {regions, table_cells, reading_order, text_blocks_with_bbox}

    azure_di_output: list[dict | None]
    # Agent C (Azure DI): {fields, confidence_scores, page_words, model}

    extraction_results: list[dict | None]
    # Agent D (olmOCR-2-7B-CIPL via vLLM): {fields: {field: {value, confidence}}}

    # ── Reconciled fields (T-039) ─────────────────────────────────────────────
    reconciled_fields: list[dict]
    # Per-document: {field_name: ReconciledField}
    # ReconciledField: {value, confidence, level, source, agent_disagreement, all_agent_values, flag_reason}
    agent_agreement_rate: float  # Overall agreement rate across all documents

    # ── Vessel validation (T-043) ─────────────────────────────────────────────
    vessel_validation: dict
    # {passed, status, issues: [{severity, code, message}], vessel_confirmed, ais_eta, lineup_confirmed}

    # ── Cross-document + schema validation (T-042, T-044) ────────────────────
    validation_results: list[dict]
    # [{rule_id, rule_name, severity, passed, error_message, affected_fields}]
    schema_validation: dict
    # {valid: bool, errors: [str]}

    # ── HS code recommendations (T-045) ──────────────────────────────────────
    hs_recommendations: list[dict]
    # Per line item: [{hs_code, description_id, description_en, confidence, duty_rate, vat_rate}]

    # ── Risk assessment (T-046) ───────────────────────────────────────────────
    rejection_prediction: dict
    # {probability: float, risk_level: "LOW"|"MEDIUM"|"HIGH"|"CRITICAL", top_features: [...]}
    crs: dict
    # {score: int (0-100), grade: "A"|"B"|"C"|"D"|"F", components: {}}

    # ── Human-in-the-loop corrections ────────────────────────────────────────
    operator_corrections: list[dict]
    # [{field_name, corrected_value, correction_reason, operator_id, corrected_at}]

    # ── Blockchain (T-049) ────────────────────────────────────────────────────
    blockchain_tx: dict
    # {tx_hash, block_number, ipfs_cid, status, polygonscan_url, anchored_at}

    # ── CEISA submission (T-059) ──────────────────────────────────────────────
    ceisa_payload: dict          # Full PIB JSON (PIBPayload)
    ceisa_aju: str               # AJU number returned by CEISA
    ceisa_reference: str         # CEISA reference ID
    ceisa_response: dict         # Raw CEISA response
    insw_status: dict            # {passed: bool, issues: [str]}
    submission_attempt: int      # Current attempt number (max: MAX_RESUBMIT_ATTEMPTS)

    # ── Learning (T-065) ─────────────────────────────────────────────────────
    learning_feedback: dict
    # {corrections_recorded: int, drift_alerts: [...], triggered_retrain: bool}

    # ── Error tracking ────────────────────────────────────────────────────────
    error: str | None

    # ── Message accumulator (LangGraph convention) ────────────────────────────
    # Annotated[list, operator.add] enables reducer-based append semantics
    messages: Annotated[list[dict], operator.add]
    # Each entry: {node, timestamp, event_type, payload}
