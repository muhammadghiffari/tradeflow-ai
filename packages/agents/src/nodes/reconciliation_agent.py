"""
TradeFlow AI — Reconciliation Agent (T-039)

Merges outputs from all 4 OCR agents using majority voting + rule validation.
Produces a ReconciledField per CEISA field with confidence levels.

Algorithm per SDD §5.2:
  1. Normalize all agent values for the field
  2. Count votes (majority = most common normalized value)
  3. Compute confidence as agreement_fraction * avg_individual_confidence
  4. If rule-validated field → cross-check with validator
  5. Label: HIGH (≥0.90), MEDIUM (≥0.70), LOW (>0), MISSING (none)
  6. agent_disagreement=True if any agent differs from majority
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from ..state import DeclarationState
from ..validators.field_normalizers import normalize_value
from ..validators.field_validators import (
    validate_hs_8digit,
    validate_iso_4217,
    validate_iso_date,
    validate_nib_format,
    validate_npwp_checksum,
    validate_unlocode,
)

logger = logging.getLogger("agents.reconciliation")

# Fields that have deterministic validators — rule takes priority
RULE_VALIDATED_FIELDS: dict[str, Any] = {
    "npwp": validate_npwp_checksum,
    "nomorIdentitas": validate_npwp_checksum,
    "nib": validate_nib_format,
    "nibEntitas": validate_nib_format,
    "hs_code": validate_hs_8digit,
    "posTarif": validate_hs_8digit,
    "port_loading_code": validate_unlocode,
    "kodePelabuhanMuat": validate_unlocode,
    "port_discharge_code": validate_unlocode,
    "kodePelabuhanBongkar": validate_unlocode,
    "bl_date": validate_iso_date,
    "tglBl": validate_iso_date,
    "invoice_date": validate_iso_date,
    "tglArrival": validate_iso_date,
    "currency": validate_iso_4217,
}

# Confidence thresholds
HIGH_CONFIDENCE = 0.90
MEDIUM_CONFIDENCE = 0.70


def _get_all_fields_for_doc_type(doc_type: str) -> list[str]:
    """Return the ordered list of CEISA fields expected for a doc type."""
    common = [
        "vessel_name", "voyage_number", "bl_number", "port_loading_code",
        "port_discharge_code", "gross_weight", "net_weight",
        "total_packages", "container_number", "bl_date",
    ]
    invoice_fields = [
        "invoice_number", "invoice_date", "seller_name", "buyer_name",
        "buyer_npwp", "npwp", "nib", "currency", "fob_value",
        "freight", "insurance", "cif_value",
    ]
    packing_fields = [
        "pl_number", "pl_date", "total_gross_weight", "total_net_weight",
    ]

    if doc_type == "bill_of_lading":
        return common
    elif doc_type == "invoice":
        return common + invoice_fields
    elif doc_type == "packing_list":
        return common + packing_fields
    return common


def _extract_agent_fields(agent_output: dict | None, doc_type: str) -> dict[str, dict]:
    """
    Extract field dict from any agent output format.
    Returns: {field_name: {"value": ..., "confidence": float}}
    """
    if agent_output is None:
        return {}

    # Agent D (olmOCR) and FAST_PATH format: {"fields": {field: {"value", "confidence"}}}
    if "fields" in agent_output:
        return {
            k: {"value": v.get("value"), "confidence": float(v.get("confidence", 0.0))}
            for k, v in agent_output["fields"].items()
            if isinstance(v, dict)
        }

    # Agent A (Surya) format: {"text_blocks": [...], "html": ...}
    # Fields are embedded in structured text — parse basic key-values
    if "text_blocks" in agent_output:
        return _parse_surya_text_blocks(agent_output, doc_type)

    # Agent B (PaddleOCR) format: {"regions": [...], "table_cells": [...]}
    if "regions" in agent_output or "table_cells" in agent_output:
        return _parse_paddle_regions(agent_output, doc_type)

    # Azure DI already normalizes to {fields: {field: {value, confidence}}}
    return {}


def _parse_surya_text_blocks(output: dict, doc_type: str) -> dict[str, dict]:
    """Parse Surya text blocks into field dict (simplified extraction)."""
    # In production, use structured HTML parsing + field-specific regex
    # Here we use confidence from Surya's output
    result = {}
    confidence_avg = output.get("confidence", 0.7)
    for block in output.get("text_blocks", []):
        for line in block if isinstance(block, list) else [block]:
            text = getattr(line, "text", "") or str(line)
            # Field matching via regex patterns (simplified)
            if "B/L" in text.upper() or "BL NO" in text.upper():
                parts = re.split(r"[:\s]+", text, maxsplit=1)
                if len(parts) > 1:
                    result["bl_number"] = {"value": parts[-1].strip(), "confidence": confidence_avg}
    return result


def _parse_paddle_regions(output: dict, doc_type: str) -> dict[str, dict]:
    """Parse PaddleOCR regions into field dict."""
    result = {}
    confidence_avg = 0.75
    for cell in output.get("table_cells", []):
        if isinstance(cell, dict):
            key = cell.get("key", "")
            val = cell.get("value", "")
            conf = cell.get("confidence", confidence_avg)
            if key and val:
                result[key.lower().replace(" ", "_")] = {
                    "value": val,
                    "confidence": float(conf),
                }
    return result


import re  # noqa: E402


def reconcile_single_field(
    field: str,
    agent_values: dict[str, dict],
) -> dict:
    """
    Reconcile a single field across all available agents.

    Returns a ReconciledField dict:
    {value, confidence, level, source, agent_disagreement, all_agent_values, flag_reason}
    """
    if not agent_values:
        return {
            "value": None,
            "confidence": 0.0,
            "level": "MISSING",
            "source": "ensemble",
            "agent_disagreement": False,
        }

    # Normalize all values
    normalized: dict[str, str | None] = {}
    individual_confidences: dict[str, float] = {}
    for agent, data in agent_values.items():
        raw = data.get("value")
        normalized[agent] = normalize_value(field, str(raw) if raw is not None else None)
        individual_confidences[agent] = float(data.get("confidence", 0.0))

    # Filter out None values
    valid_normalized = {a: v for a, v in normalized.items() if v is not None}
    if not valid_normalized:
        return {
            "value": None,
            "confidence": 0.0,
            "level": "MISSING",
            "source": "ensemble",
            "agent_disagreement": False,
        }

    # Rule-validated fields: pick the first agent value that passes validation
    if field in RULE_VALIDATED_FIELDS:
        validator = RULE_VALIDATED_FIELDS[field]
        for agent, val in valid_normalized.items():
            if validator(val):
                agreement = sum(
                    1 for v in valid_normalized.values() if v == val
                ) / len(valid_normalized)
                avg_conf = sum(individual_confidences.values()) / len(individual_confidences)
                confidence = round(agreement * avg_conf, 3)
                return {
                    "value": val,
                    "confidence": confidence,
                    "level": _confidence_level(confidence),
                    "source": "rule",
                    "agent_disagreement": len(set(valid_normalized.values())) > 1,
                    "all_agent_values": agent_values if len(set(valid_normalized.values())) > 1 else None,
                    "flag_reason": None,
                }
        # No value passed rule validation
        return {
            "value": list(valid_normalized.values())[0],
            "confidence": 0.3,
            "level": "LOW",
            "source": "ensemble",
            "agent_disagreement": True,
            "all_agent_values": agent_values,
            "flag_reason": f"No agent produced a valid {field} value",
        }

    # Majority voting
    vote_counts = Counter(valid_normalized.values())
    majority_value, vote_count = vote_counts.most_common(1)[0]
    total_agents = len(valid_normalized)
    agreement_fraction = vote_count / total_agents

    # Average confidence from agents that agreed
    agreeing_agents = [a for a, v in valid_normalized.items() if v == majority_value]
    avg_confidence = sum(individual_confidences[a] for a in agreeing_agents) / len(agreeing_agents)

    confidence = round(agreement_fraction * avg_confidence, 3)
    disagreement = len(set(valid_normalized.values())) > 1

    return {
        "value": majority_value,
        "confidence": confidence,
        "level": _confidence_level(confidence),
        "source": "ensemble",
        "agent_disagreement": disagreement,
        "all_agent_values": agent_values if disagreement else None,
        "flag_reason": None,
    }


def _confidence_level(confidence: float) -> str:
    if confidence >= HIGH_CONFIDENCE:
        return "HIGH"
    elif confidence >= MEDIUM_CONFIDENCE:
        return "MEDIUM"
    elif confidence > 0:
        return "LOW"
    return "MISSING"


async def reconcile_node(state: DeclarationState) -> dict:
    """
    Reconcile all OCR agent outputs per document, per field.
    Computes agent_agreement_rate across all documents.
    """
    reconciled_per_doc = []
    all_fields_count = 0
    agreement_count = 0

    for idx, doc in enumerate(state["preprocessed"]):
        doc_type = doc.get("doc_type", "bill_of_lading")

        agent_outputs = {
            "agent_a": _extract_agent_fields(
                state["surya_output"][idx] if idx < len(state.get("surya_output", [])) else None,
                doc_type,
            ),
            "agent_b": _extract_agent_fields(
                state["layout_analysis"][idx] if idx < len(state.get("layout_analysis", [])) else None,
                doc_type,
            ),
            "agent_c": _extract_agent_fields(
                state["azure_di_output"][idx] if idx < len(state.get("azure_di_output", [])) else None,
                doc_type,
            ),
            "agent_d": _extract_agent_fields(
                state["extraction_results"][idx] if idx < len(state.get("extraction_results", [])) else None,
                doc_type,
            ),
        }
        # Remove agents that returned no data
        agent_outputs = {k: v for k, v in agent_outputs.items() if v}

        fields = _get_all_fields_for_doc_type(doc_type)
        reconciled: dict[str, dict] = {}

        for field in fields:
            agent_values = {
                agent: data[field]
                for agent, data in agent_outputs.items()
                if field in data
            }
            reconciled[field] = reconcile_single_field(field, agent_values)
            all_fields_count += 1
            if not reconciled[field]["agent_disagreement"]:
                agreement_count += 1

        reconciled_per_doc.append(reconciled)

    agreement_rate = agreement_count / max(all_fields_count, 1)

    logger.info(
        f"Reconciliation complete: {all_fields_count} fields, "
        f"agreement rate: {agreement_rate:.1%}"
    )

    return {
        "reconciled_fields": reconciled_per_doc,
        "agent_agreement_rate": round(agreement_rate, 3),
        "messages": [
            {
                "node": "reconcile",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "reconciliation_complete",
                "payload": {
                    "fields_total": all_fields_count,
                    "agreement_rate": agreement_rate,
                },
            }
        ],
    }
