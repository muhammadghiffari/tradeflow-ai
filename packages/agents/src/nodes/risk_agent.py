"""
TradeFlow AI — Risk Assessment Agent + CRS Calculation (T-046, T-047)

Two responsibilities:
  1. CRS (Compliance Risk Score): 0-100, weighted rule-based score
  2. Rejection Prediction: XGBoost model OR fallback heuristics

CRS Components (SDD §6.2):
  - Document quality:         20 pts
  - Validation pass rate:     25 pts
  - Agent agreement:          20 pts
  - HS code confidence:       20 pts
  - Vessel validation:        15 pts

XGBoost fallback (<500 labeled samples): rule-based risk from
xgboost_fallback_rules in validation_rules.json.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..state import DeclarationState
from ..validators.rule_engine import get_rules

logger = logging.getLogger("agents.risk")


# ─────────────────────────────────────────────────────────────
# CRS Calculation (T-047)
# ─────────────────────────────────────────────────────────────

def calculate_crs(state: DeclarationState) -> dict:
    """
    Compute Compliance Risk Score (0-100) and grade.

    Components:
      document_quality  (20): avg quality score across preprocessed docs
      validation        (25): fraction of rules passed
      agent_agreement   (20): agent_agreement_rate
      hs_confidence     (20): avg HS code confidence
      vessel_validation (15): vessel check passed
    """
    # Document quality (0-20)
    preprocessed = state.get("preprocessed", [])
    avg_quality = (
        sum(p.get("quality_score", 0.0) for p in preprocessed) / max(len(preprocessed), 1)
    )
    doc_quality_pts = round(avg_quality * 20, 1)

    # Validation pass rate (0-25)
    validation_results = state.get("validation_results", [])
    if validation_results:
        passed = sum(1 for r in validation_results if r.get("passed", False))
        pass_rate = passed / len(validation_results)
    else:
        pass_rate = 1.0
    validation_pts = round(pass_rate * 25, 1)

    # Agent agreement (0-20)
    agreement_rate = state.get("agent_agreement_rate", 1.0)
    agreement_pts = round(agreement_rate * 20, 1)

    # HS code confidence (0-20)
    hs_recommendations = state.get("hs_recommendations", [])
    if hs_recommendations:
        avg_hs_conf = sum(r.get("confidence", 0.0) for r in hs_recommendations) / len(hs_recommendations)
    else:
        # If no HS recs needed, assume OK
        avg_hs_conf = 1.0
    hs_pts = round(avg_hs_conf * 20, 1)

    # Vessel validation (0-15)
    vessel = state.get("vessel_validation", {})
    if vessel.get("passed", True):
        if vessel.get("status") == "warning":
            vessel_pts = 10.0
        else:
            vessel_pts = 15.0
    else:
        vessel_pts = 0.0

    total = doc_quality_pts + validation_pts + agreement_pts + hs_pts + vessel_pts
    total = min(max(round(total, 1), 0), 100)

    if total >= 85:
        grade = "A"
    elif total >= 70:
        grade = "B"
    elif total >= 55:
        grade = "C"
    elif total >= 40:
        grade = "D"
    else:
        grade = "F"

    return {
        "score": int(total),
        "grade": grade,
        "components": {
            "document_quality": doc_quality_pts,
            "validation_pass_rate": validation_pts,
            "agent_agreement": agreement_pts,
            "hs_confidence": hs_pts,
            "vessel_validation": vessel_pts,
        },
    }


# ─────────────────────────────────────────────────────────────
# XGBoost prediction (T-046)
# ─────────────────────────────────────────────────────────────

def _build_feature_vector(state: DeclarationState, crs: dict) -> dict[str, float]:
    """Extract feature values for XGBoost prediction."""
    validation_results = state.get("validation_results", [])
    critical_failures = sum(
        1 for r in validation_results
        if not r.get("passed") and r.get("severity") == "ERROR"
    )
    agent_disagreements = sum(
        1
        for doc_fields in state.get("reconciled_fields", [])
        for field, val in doc_fields.items()
        if isinstance(val, dict) and val.get("agent_disagreement", False)
    )
    hs_recs = state.get("hs_recommendations", [])
    avg_hs_conf = (
        sum(r.get("confidence", 0.0) for r in hs_recs) / max(len(hs_recs), 1)
        if hs_recs else 1.0
    )
    vessel = state.get("vessel_validation", {})
    vessel_critical = 1 if vessel.get("status") == "critical" else 0

    preprocessed = state.get("preprocessed", [])
    avg_quality = (
        sum(p.get("quality_score", 0.0) for p in preprocessed) / max(len(preprocessed), 1)
    )

    return {
        "crs_score": float(crs["score"]),
        "critical_validation_failures": float(critical_failures),
        "agent_disagreement_count": float(agent_disagreements),
        "hs_code_confidence": float(avg_hs_conf),
        "vessel_validation_critical": float(vessel_critical),
        "missing_required_fields_count": float(
            sum(
                1
                for doc in state.get("reconciled_fields", [])
                for field, val in doc.items()
                if isinstance(val, dict) and val.get("level") == "MISSING"
            )
        ),
        "document_quality": float(avg_quality),
        "agent_agreement_rate": float(state.get("agent_agreement_rate", 1.0)),
    }


def _predict_xgboost(features: dict[str, float]) -> float:
    """Try XGBoost prediction; fall back to rule-based."""
    model_path = Path(os.environ.get("XGBOOST_MODEL_PATH", "models/rejection_predictor.json"))
    if model_path.exists():
        try:
            import xgboost as xgb
            import numpy as np
            model = xgb.Booster()
            model.load_model(str(model_path))
            feature_names = [
                "crs_score", "critical_validation_failures", "agent_disagreement_count",
                "hs_code_confidence", "vessel_validation_critical",
                "missing_required_fields_count", "document_quality", "agent_agreement_rate",
            ]
            X = np.array([[features[f] for f in feature_names]])
            dmatrix = xgb.DMatrix(X, feature_names=feature_names)
            prob = float(model.predict(dmatrix)[0])
            logger.info(f"XGBoost prediction: {prob:.3f}")
            return prob
        except Exception as e:
            logger.warning(f"XGBoost prediction failed, using fallback: {e}")

    return _fallback_risk(features)


def _fallback_risk(features: dict[str, float]) -> float:
    """Rule-based fallback when XGBoost model unavailable (<500 samples)."""
    rules_data = get_rules()
    fallback = rules_data.get("xgboost_fallback_rules", {})
    base_risk = fallback.get("base_risk", 0.10)
    max_risk = fallback.get("max_risk", 0.95)
    risk = base_risk

    for rule in fallback.get("rules", []):
        feature = rule.get("feature")
        condition = rule.get("condition")
        threshold = rule.get("threshold", 0)
        contribution = rule.get("risk_contribution", 0.0)
        value = features.get(feature, 0.0)

        triggered = False
        if condition == "lt" and value < threshold:
            triggered = True
        elif condition == "gte" and value >= threshold:
            triggered = True
        elif condition == "eq" and value == threshold:
            triggered = True
        elif condition == "gt" and value > threshold:
            triggered = True

        if triggered:
            risk += contribution

    return round(min(risk, max_risk), 3)


def _risk_level(probability: float) -> str:
    if probability >= 0.70:
        return "HIGH"
    elif probability >= 0.40:
        return "MEDIUM"
    elif probability >= 0.20:
        return "LOW"
    return "VERY_LOW"


# ─────────────────────────────────────────────────────────────
# LangGraph node
# ─────────────────────────────────────────────────────────────

async def risk_assess_node(state: DeclarationState) -> dict:
    """Compute CRS + rejection prediction and update state."""
    crs = calculate_crs(state)
    features = _build_feature_vector(state, crs)
    probability = _predict_xgboost(features)
    risk_level = _risk_level(probability)

    # Top features by contribution
    top_features = sorted(
        [
            {"feature": k, "value": v}
            for k, v in features.items()
            if k != "crs_score"
        ],
        key=lambda x: abs(x["value"]),
        reverse=True,
    )[:5]

    return {
        "crs": crs,
        "rejection_prediction": {
            "probability": probability,
            "risk_level": risk_level,
            "top_features": top_features,
        },
        "messages": [{
            "node": "risk_assess",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "risk_assessment_complete",
            "payload": {
                "crs_score": crs["score"],
                "crs_grade": crs["grade"],
                "rejection_probability": probability,
                "risk_level": risk_level,
            },
        }],
    }
