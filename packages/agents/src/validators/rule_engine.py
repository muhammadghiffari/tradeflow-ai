"""
TradeFlow AI — Hot-reloadable Validation Rule Engine (T-042)

Loads CV001-CV011 rules from validation_rules.json.
Sends SIGHUP to workers to hot-reload (never restart the service).

PRD Invariant #7 anti-pattern: rules MUST be in the JSON file,
never hardcoded here.
"""
from __future__ import annotations

import json
import logging
import os
import signal
import threading
from pathlib import Path
from typing import Any

from ..validators.field_validators import (
    validate_container_iso6346,
    validate_hs_8digit,
    validate_iso_date,
    validate_nib_format,
    validate_npwp_checksum,
    validate_unlocode,
)
from ..validators.field_normalizers import normalize_value

logger = logging.getLogger("agents.rule_engine")

RULES_PATH = Path(
    os.environ.get("VALIDATION_RULES_PATH", "packages/db/validation_rules.json")
)

_rules_lock = threading.Lock()
_rules_data: dict[str, Any] = {}
_last_loaded: float = 0.0


def _load_rules() -> dict[str, Any]:
    global _rules_data, _last_loaded
    import time
    if RULES_PATH.exists():
        with open(RULES_PATH, encoding="utf-8") as f:
            data = json.load(f)
        _last_loaded = time.monotonic()
        logger.info(f"Loaded {len(data.get('rules', []))} validation rules from {RULES_PATH}")
        return data
    logger.warning(f"Rules file not found at {RULES_PATH}")
    return {"rules": [], "xgboost_fallback_rules": {}}


def get_rules() -> dict[str, Any]:
    """Return current rules dict (loads on first call)."""
    with _rules_lock:
        if not _rules_data:
            _rules_data.update(_load_rules())
        return _rules_data


def reload_rules() -> None:
    """Force reload from disk (called on SIGHUP)."""
    with _rules_lock:
        _rules_data.clear()
        _rules_data.update(_load_rules())
    logger.info("Validation rules hot-reloaded ✓")


def _setup_sighup_handler() -> None:
    try:
        signal.signal(signal.SIGHUP, lambda *_: reload_rules())
    except (AttributeError, OSError):
        pass  # SIGHUP not available on Windows


_setup_sighup_handler()

# ─────────────────────────────────────────────────────────────
# Rule evaluation
# ─────────────────────────────────────────────────────────────
_VALIDATOR_MAP = {
    "CV001": validate_hs_8digit,
    "CV003": validate_nib_format,
    "CV004": validate_npwp_checksum,
    "CV005": validate_container_iso6346,
    "CV011": validate_unlocode,
}


def evaluate_rules(
    reconciled_fields: list[dict],
) -> list[dict]:
    """
    Evaluate all CV001-CV011 rules against reconciled fields.
    Returns list of ValidationResult dicts.
    """
    rules = get_rules().get("rules", [])
    results = []

    for rule in rules:
        rule_id = rule["id"]
        rule_type = rule.get("type", "")

        # Collect values from all documents for this field
        target_fields = [rule.get("field")] + rule.get("fields", [])
        target_fields = [f for f in target_fields if f]

        for doc_fields in reconciled_fields:
            result = _evaluate_single_rule(rule, rule_id, rule_type, target_fields, doc_fields)
            if result:
                results.append(result)

    return results


def _evaluate_single_rule(
    rule: dict,
    rule_id: str,
    rule_type: str,
    target_fields: list[str],
    doc_fields: dict,
) -> dict | None:
    """Evaluate one rule against one document's fields."""
    rule_name = rule.get("name", rule_id)
    severity = rule.get("severity", "WARNING")

    if rule_type in ("regex", "regex_and_lookup"):
        import re
        pattern = rule.get("regex", "")
        for field in target_fields:
            rec = doc_fields.get(field)
            if rec is None:
                continue
            value = rec.get("value") if isinstance(rec, dict) else str(rec)
            if value is None:
                return {
                    "rule_id": rule_id, "rule_name": rule_name,
                    "severity": severity, "passed": False,
                    "error_message": f"Field '{field}' is missing",
                    "affected_fields": [field],
                }
            # Validator from map (most reliable)
            if rule_id in _VALIDATOR_MAP:
                valid = _VALIDATOR_MAP[rule_id](str(value))
            else:
                valid = bool(re.match(pattern, str(value).strip())) if pattern else True
            return {
                "rule_id": rule_id, "rule_name": rule_name,
                "severity": severity, "passed": valid,
                "error_message": None if valid else f"Field '{field}' value '{value}' failed {rule_id}",
                "affected_fields": [field],
            }

    elif rule_type == "cross_document_match":
        # Collect all values across docs (handled at batch level, not doc level)
        return None

    elif rule_type == "lookup":
        for field in target_fields:
            rec = doc_fields.get(field)
            if rec is None:
                continue
            value = rec.get("value") if isinstance(rec, dict) else str(rec)
            if value is None:
                continue
            valid = validate_unlocode(str(value))
            return {
                "rule_id": rule_id, "rule_name": rule_name,
                "severity": severity, "passed": valid,
                "error_message": None if valid else f"UN/LOCODE '{value}' is invalid",
                "affected_fields": [field],
            }

    return None


def evaluate_cross_document_rules(
    all_reconciled: list[dict],
) -> list[dict]:
    """
    Evaluate cross-document matching rules (CV006, CV007, CV008, CV009, CV010).
    Requires all document fields to be present.
    """
    rules = get_rules().get("rules", [])
    results = []
    tolerance_fields = {"beratKotor", "gross_weight"}

    for rule in rules:
        rule_type = rule.get("type", "")
        if rule_type not in ("cross_document_match", "cross_document", "date_sequence"):
            continue

        rule_id = rule["id"]
        rule_name = rule.get("name", rule_id)
        severity = rule.get("severity", "WARNING")
        fields = rule.get("fields", [])
        tolerance_pct = rule.get("tolerance_pct", 0.0)

        if rule_type == "cross_document_match":
            for field in fields:
                values = []
                for doc in all_reconciled:
                    rec = doc.get(field)
                    if rec and isinstance(rec, dict) and rec.get("value"):
                        normalized = normalize_value(field, str(rec["value"]))
                        values.append(normalized)
                if len(values) < 2:
                    continue
                unique = set(v for v in values if v)
                passed = len(unique) <= 1
                results.append({
                    "rule_id": rule_id, "rule_name": rule_name,
                    "severity": severity, "passed": passed,
                    "error_message": (
                        None if passed
                        else f"{field} mismatch across documents: {sorted(unique)}"
                    ),
                    "affected_fields": fields,
                })

        elif rule_type == "cross_document" and tolerance_pct > 0:
            for field in fields:
                values = []
                for doc in all_reconciled:
                    rec = doc.get(field)
                    if rec and isinstance(rec, dict) and rec.get("value"):
                        try:
                            values.append(float(str(rec["value"]).replace(",", "")))
                        except ValueError:
                            pass
                if len(values) < 2:
                    continue
                min_v, max_v = min(values), max(values)
                if max_v == 0:
                    continue
                pct_diff = abs(max_v - min_v) / max_v * 100
                passed = pct_diff <= tolerance_pct
                results.append({
                    "rule_id": rule_id, "rule_name": rule_name,
                    "severity": severity, "passed": passed,
                    "error_message": (
                        None if passed
                        else f"{field} differs by {pct_diff:.2f}% (limit {tolerance_pct}%)"
                    ),
                    "affected_fields": fields,
                })

    return results
