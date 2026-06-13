import pytest

from src.ai.nodes.risk import risk_assessment_node


@pytest.mark.asyncio
async def test_risk_assessment_uses_shared_rejection_predictor(monkeypatch):
    calls = []

    def fake_predict(features: dict) -> float:
        calls.append(features)
        return 0.42

    monkeypatch.setattr(
        "src.ai.nodes.risk.rejection_predictor.predict_proba",
        fake_predict,
    )

    result = await risk_assessment_node(
        {
            "batch_id": "batch-1",
            "combined_data": {
                "importer_name": "PT Demo",
                "importer_npwp": "012345678999000",
                "total_packages": 10,
                "gross_weight": 500,
                "cif_value": 15000,
                "currency": "USD",
            },
            "validation_results": [{"severity": "PASS"}],
            "documents": [{"quality_score": 0.95}],
            "needs_human_review": False,
        }
    )

    assert calls
    assert calls[0]["doc_quality_score"] == 0.95
    assert calls[0]["cif_value_usd"] == 15000.0
    assert result["_rejection_prob"] == 0.42
    assert result["risk_level"] == "HIGH"
    assert result["needs_human_review"] is True
