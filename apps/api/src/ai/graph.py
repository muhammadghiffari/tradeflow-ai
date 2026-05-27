"""
TradeFlow AI — LangGraph Extraction Graph (Step 2 Assembly)

PRD §10 — Full LangGraph pipeline:

  preprocess → llm_extraction → [fallback if needed] → validate
    → risk_assessment → [interrupt if review needed] → DONE

The graph is compiled with a Redis checkpointer for persistence
and resumability across server restarts.
"""

from __future__ import annotations

import structlog
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.redis import RedisSaver

from .state import ExtractionGraphState
from .nodes.preprocess import preprocess_documents_node
from .nodes.extract import llm_extraction_node
from .nodes.fallback_ocr import fallback_ocr_node
from .nodes.validate import validation_node
from .nodes.risk import risk_assessment_node
from .nodes.human_review import human_review_node
from ..config import settings

log = structlog.get_logger()


def _needs_fallback(state: ExtractionGraphState) -> str:
    """Conditional edge: route to fallback OCR if any doc has error or no data."""
    for doc in state.get("documents", []):
        if doc.get("error") or not doc.get("extracted_data"):
            return "fallback"
    return "validate"


def _needs_review(state: ExtractionGraphState) -> str:
    """Conditional edge: route to human review if flagged."""
    if state.get("needs_human_review", False):
        return "human_review"
    return END


def build_extraction_graph() -> StateGraph:
    """Build and compile the LangGraph extraction pipeline."""
    workflow = StateGraph(ExtractionGraphState)

    # ── Add nodes ────────────────────────────────────────────────
    workflow.add_node("preprocess",      preprocess_documents_node)
    workflow.add_node("llm_extraction",  llm_extraction_node)
    workflow.add_node("fallback_ocr",    fallback_ocr_node)
    workflow.add_node("validate",        validation_node)
    workflow.add_node("risk_assessment", risk_assessment_node)
    workflow.add_node("human_review",    human_review_node)

    # ── Entry point ───────────────────────────────────────────────
    workflow.set_entry_point("preprocess")

    # ── Edges ─────────────────────────────────────────────────────
    workflow.add_edge("preprocess", "llm_extraction")

    # After extraction: check if fallback needed
    workflow.add_conditional_edges(
        "llm_extraction",
        _needs_fallback,
        {
            "fallback": "fallback_ocr",
            "validate": "validate",
        },
    )

    # Fallback always proceeds to validate
    workflow.add_edge("fallback_ocr", "validate")

    # After validation: compute risk
    workflow.add_edge("validate", "risk_assessment")

    # After risk: check if human review needed
    workflow.add_conditional_edges(
        "risk_assessment",
        _needs_review,
        {
            "human_review": "human_review",
            END: END,
        },
    )

    # After human review: graph ends (operator approved)
    workflow.add_edge("human_review", END)

    return workflow


def get_compiled_graph():
    """
    Returns the compiled graph with Redis checkpointer.
    The checkpointer enables:
      - State persistence across Celery task restarts
      - interrupt() resumability for human review
      - LangSmith tracing integration
    """
    workflow = build_extraction_graph()

    # Redis checkpointer — stores full graph state per thread_id (batch_id)
    checkpointer = RedisSaver.from_conn_string(settings.REDIS_URL)

    graph = workflow.compile(checkpointer=checkpointer, interrupt_before=["human_review"])

    log.info("LangGraph extraction graph compiled", nodes=list(workflow.nodes.keys()))
    return graph


# ── Singleton (imported by Celery tasks) ──────────────────────────────────────
extraction_graph = get_compiled_graph()
