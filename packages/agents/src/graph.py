"""
TradeFlow AI — LangGraph Graph Definition (T-034)

Builds the full declarative import processing pipeline.
Critical invariants:
  - Checkpointer: RedisSaver (not AsyncSqliteSaver) per PRD Invariant #6
  - interrupt_before=["submit"] — mandatory HitL checkpoint per PRD Invariant #7
  - All nodes are async for non-blocking execution in Celery workers
  - Graph survives worker restarts via Redis state persistence

SDD §2.2 — Graph Definition
"""

from __future__ import annotations

import logging
from typing import Literal

from langgraph.checkpoint.redis import RedisSaver
from langgraph.graph import END, StateGraph

from .state import DeclarationState

logger = logging.getLogger("agents.graph")


# ─────────────────────────────────────────────────────────────
# Conditional edge routing functions
# ─────────────────────────────────────────────────────────────

def route_after_validation(
    state: DeclarationState,
) -> Literal["hs_needed", "skip_hs"]:
    """
    After validation: check if any line items are missing HS codes.
    Enterprise tier always skips HS recommendation (they pre-fill).
    """
    if state.get("tier") == "enterprise":
        return "skip_hs"

    reconciled = state.get("reconciled_fields", [])
    for doc_fields in reconciled:
        hs = doc_fields.get("hs_code")
        if hs is None or (isinstance(hs, dict) and hs.get("confidence", 0) < 0.5):
            return "hs_needed"

    return "skip_hs"


def route_after_insw(
    state: DeclarationState,
) -> Literal["pass", "fail"]:
    """After INSW lartas check: pass → submit, fail → back to review."""
    insw = state.get("insw_status", {})
    if insw.get("passed", False):
        return "pass"
    return "fail"


def route_after_ceisa(
    state: DeclarationState,
) -> Literal["terminal", "pending"]:
    """
    Poll CEISA status. Terminal states: accepted or rejected.
    Pending states: submitted, processing.
    """
    response = state.get("ceisa_response", {})
    ceisa_status = response.get("status", "pending")
    terminal_states = {"accepted", "rejected", "failed"}
    if ceisa_status in terminal_states:
        return "terminal"
    return "pending"


# ─────────────────────────────────────────────────────────────
# Placeholder node stubs (full implementations in nodes/ folder)
# ─────────────────────────────────────────────────────────────
# These are imported here to build the graph. Each node module
# is responsible for its own logic and state mutations.

def _import_node(name: str):
    """Lazy import to avoid circular dependencies at module load."""
    import importlib
    mod = importlib.import_module(f".nodes.{name}", package="packages.agents.src")
    return getattr(mod, f"{name}_node")


# ─────────────────────────────────────────────────────────────
# Graph builder
# ─────────────────────────────────────────────────────────────

def build_graph(redis_url: str) -> StateGraph:
    """
    Build and compile the TradeFlow AI LangGraph pipeline.

    Args:
        redis_url: Redis connection string for RedisSaver checkpointer.

    Returns:
        Compiled StateGraph with RedisSaver checkpointer and
        interrupt_before=["submit"] for mandatory HitL.
    """
    # Lazy imports to avoid circular deps when first loading the module
    from .nodes.ingest import ingest_node
    from .nodes.preprocess import preprocess_node
    from .nodes.multi_ocr_agent import multi_ocr_node
    from .nodes.reconciliation_agent import reconcile_node
    from .nodes.vessel_validation_agent import vessel_validate_node
    from .nodes.validation_agent import validate_node
    from .nodes.hs_code_agent import hs_recommend_node
    from .nodes.risk_agent import risk_assess_node
    from .nodes.blockchain_agent import blockchain_anchor_node
    from .nodes.review_ready import review_ready_node
    from .nodes.submission_agent import (
        build_payload_node,
        insw_check_node,
        submit_node,
    )
    from .nodes.status_poller import poll_status_node
    from .nodes.learning_agent import record_outcome_node

    builder = StateGraph(DeclarationState)

    # ── Register nodes ───────────────────────────────────────────────────────
    builder.add_node("ingest", ingest_node)
    builder.add_node("preprocess", preprocess_node)
    builder.add_node("multi_ocr", multi_ocr_node)
    builder.add_node("reconcile", reconcile_node)
    builder.add_node("vessel_validate", vessel_validate_node)
    builder.add_node("validate", validate_node)
    builder.add_node("hs_recommend", hs_recommend_node)
    builder.add_node("risk_assess", risk_assess_node)
    builder.add_node("blockchain_anchor", blockchain_anchor_node)  # parallel branch
    builder.add_node("review_ready", review_ready_node)
    builder.add_node("build_payload", build_payload_node)
    builder.add_node("insw_check", insw_check_node)
    builder.add_node("submit", submit_node)       # ← HitL interrupt point
    builder.add_node("poll_status", poll_status_node)
    builder.add_node("record_outcome", record_outcome_node)

    # ── Pre-approval pipeline (automated) ───────────────────────────────────
    builder.set_entry_point("ingest")
    builder.add_edge("ingest", "preprocess")
    builder.add_edge("preprocess", "multi_ocr")
    builder.add_edge("multi_ocr", "reconcile")
    builder.add_edge("reconcile", "vessel_validate")
    builder.add_edge("vessel_validate", "validate")

    builder.add_conditional_edges(
        "validate",
        route_after_validation,
        {
            "hs_needed": "hs_recommend",
            "skip_hs": "risk_assess",
        },
    )
    builder.add_edge("hs_recommend", "risk_assess")

    # risk_assess → both blockchain_anchor (parallel) AND review_ready
    # LangGraph handles parallel via Send API; here we chain sequentially
    # (blockchain_anchor is fire-and-forget, completes before review_ready)
    builder.add_edge("risk_assess", "blockchain_anchor")
    builder.add_edge("blockchain_anchor", "review_ready")

    # review_ready sets batch.status = REVIEW_READY, triggers Realtime CDC
    # Graph PAUSES here (interrupt_before=["submit"]) until operator approves
    builder.add_edge("review_ready", END)

    # ── Post-approval pipeline (resumed after operator POST /submit) ─────────
    # When operator hits /submit, Celery resumes the graph at build_payload
    builder.add_edge("build_payload", "insw_check")

    builder.add_conditional_edges(
        "insw_check",
        route_after_insw,
        {
            "pass": "submit",
            "fail": "review_ready",
        },
    )

    # submit → poll_status → terminal or re-poll
    builder.add_edge("submit", "poll_status")

    builder.add_conditional_edges(
        "poll_status",
        route_after_ceisa,
        {
            "terminal": "record_outcome",
            "pending": "poll_status",   # self-loop until terminal
        },
    )

    builder.add_edge("record_outcome", END)

    # ── Checkpointer: Redis (PRD Invariant #6) ──────────────────────────────
    # RedisSaver persists state to Redis after EVERY node execution.
    # This allows Celery workers to crash and resume from last checkpoint.
    memory = RedisSaver.from_conn_string(redis_url)

    compiled = builder.compile(
        checkpointer=memory,
        interrupt_before=["submit"],   # PRD Invariant #7: mandatory HitL
    )

    logger.info("TradeFlow AI LangGraph pipeline compiled successfully")
    return compiled


# ─────────────────────────────────────────────────────────────
# Singleton graph instance (initialized in app startup)
# ─────────────────────────────────────────────────────────────
_graph_instance = None


def get_graph() -> StateGraph:
    """Return the singleton compiled graph. Raises if not initialized."""
    global _graph_instance
    if _graph_instance is None:
        raise RuntimeError(
            "Graph not initialized. Call initialize_graph(redis_url) first."
        )
    return _graph_instance


def initialize_graph(redis_url: str) -> StateGraph:
    """Build and cache the graph singleton. Called once at app startup."""
    global _graph_instance
    _graph_instance = build_graph(redis_url)
    return _graph_instance
