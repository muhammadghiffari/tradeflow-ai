"""
TradeFlow AI — Validation Node (T-042 integration)

LangGraph node that runs the rule engine against reconciled fields.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..state import DeclarationState
from ..validators.rule_engine import evaluate_cross_document_rules, evaluate_rules


async def validate_node(state: DeclarationState) -> dict:
    reconciled = state.get("reconciled_fields", [])
    results = []

    # Per-document rule evaluation
    for doc_fields in reconciled:
        results.extend(evaluate_rules([doc_fields]))

    # Cross-document rules
    results.extend(evaluate_cross_document_rules(reconciled))

    errors = [r for r in results if not r["passed"] and r.get("severity") == "ERROR"]

    return {
        "validation_results": results,
        "schema_validation": {
            "valid": len(errors) == 0,
            "errors": [r["error_message"] for r in errors if r["error_message"]],
        },
        "messages": [{
            "node": "validate",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "validation_complete",
            "payload": {
                "total_rules": len(results),
                "passed": sum(1 for r in results if r["passed"]),
                "failed": sum(1 for r in results if not r["passed"]),
            },
        }],
    }
