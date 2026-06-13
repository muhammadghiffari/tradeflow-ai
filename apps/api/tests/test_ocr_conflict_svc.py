from src.services.ocr_conflict_svc import reconcile_ocr_candidates


def test_reconcile_ocr_candidates_prefers_consensus_over_single_engine():
    result = reconcile_ocr_candidates(
        {
            "paddleocr": {
                "fields": {"importer_npwp": "01.234.567.8-999.000"},
                "field_confidences": {"importer_npwp": 0.86},
            },
            "azure-di": {
                "fields": {"importer_npwp": "012345678999000"},
                "field_confidences": {"importer_npwp": 0.83},
            },
        }
    )

    assert result["fields"]["importer_npwp"] == "01.234.567.8-999.000"
    assert result["field_confidences"]["importer_npwp"] >= 0.9
    assert result["conflicts"] == []


def test_reconcile_ocr_candidates_flags_close_disagreement():
    result = reconcile_ocr_candidates(
        {
            "paddleocr": {
                "fields": {"total_packages": 100},
                "field_confidences": {"total_packages": 0.88},
            },
            "azure-di": {
                "fields": {"total_packages": 108},
                "field_confidences": {"total_packages": 0.84},
            },
        },
        conflict_margin=0.2,
    )

    assert result["fields"]["total_packages"] == 108
    assert result["conflicts"][0]["field"] == "total_packages"
    assert result["conflicts"][0]["reason"] == "engine_disagreement"
