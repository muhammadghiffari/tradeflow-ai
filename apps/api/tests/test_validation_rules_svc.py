import json
import time

import pytest

from src.ai.nodes.validate import validation_node
from src.services.validation_rules_svc import ValidationRulesService


def _write_rules(path, *, threshold: int) -> None:
    path.write_text(
        json.dumps(
            {
                "version": f"test-{threshold}",
                "rules": [
                    {
                        "rule_id": "T001",
                        "severity": "CRITICAL",
                        "name": "Package threshold",
                        "check": f"bl.total_packages <= {threshold}",
                        "error_message": "Package count {bl} exceeds threshold",
                        "affected_fields": ["total_packages"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_validation_rules_reload_when_json_changes(tmp_path, monkeypatch):
    rules_path = tmp_path / "validation_rules.json"
    _write_rules(rules_path, threshold=10)
    monkeypatch.setattr("src.services.validation_rules_svc.settings.VALIDATION_RULES_PATH", str(rules_path))

    service = ValidationRulesService()
    state = {
        "combined_data": {"total_packages": 12},
        "documents": [
            {
                "doc_type": "bill_of_lading",
                "extracted_data": {"total_packages": 12},
            }
        ],
    }

    results, needs_review = service.evaluate(state)
    assert results[0]["severity"] == "CRITICAL_FAIL"
    assert needs_review is True

    time.sleep(0.01)
    _write_rules(rules_path, threshold=20)

    results, needs_review = service.evaluate(state)
    assert results[0]["severity"] == "PASS"
    assert needs_review is False


def test_missing_fields_do_not_false_pass(tmp_path, monkeypatch):
    rules_path = tmp_path / "validation_rules.json"
    rules_path.write_text(
        json.dumps(
            {
                "version": "missing-test",
                "rules": [
                    {
                        "rule_id": "T002",
                        "severity": "CRITICAL",
                        "name": "Currency match",
                        "check": "inv.currency_code == pl.currency_code",
                        "error_message": "Currency mismatch",
                        "affected_fields": ["currency_code"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("src.services.validation_rules_svc.settings.VALIDATION_RULES_PATH", str(rules_path))

    service = ValidationRulesService()
    results, needs_review = service.evaluate({"combined_data": {}, "documents": []})

    assert results[0]["severity"] == "CRITICAL_FAIL"
    assert needs_review is True


@pytest.mark.asyncio
async def test_validation_node_uses_hot_reloadable_rules(tmp_path, monkeypatch):
    rules_path = tmp_path / "validation_rules.json"
    _write_rules(rules_path, threshold=10)
    monkeypatch.setattr("src.services.validation_rules_svc.settings.VALIDATION_RULES_PATH", str(rules_path))

    result = await validation_node(
        {
            "batch_id": "batch-1",
            "combined_data": {"total_packages": 3},
            "documents": [
                {
                    "doc_type": "bill_of_lading",
                    "extracted_data": {"total_packages": 3},
                }
            ],
            "needs_human_review": False,
        }
    )

    assert result["validation_results"][0]["rule_id"] == "T001"
    assert result["validation_results"][0]["severity"] == "PASS"
    assert result["needs_human_review"] is False
