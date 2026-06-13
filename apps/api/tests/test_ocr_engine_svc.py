import pytest

from src.services.ocr_engine_svc import OCREngineService, extract_ceisa_fields_from_text, settings


def test_extract_ceisa_fields_from_text_for_cipl_fields():
    text = """
    Consignee / Importer: PT CIKARANG LOGISTICS INDONESIA
    NPWP: 01.234.567.8-999.000
    Total Packages: 42
    Gross Weight: 1,250.50 KGS
    Currency: USD
    CIF USD 12500.75
    """

    fields = extract_ceisa_fields_from_text(text)

    assert fields["importer_name"] == "PT CIKARANG LOGISTICS INDONESIA"
    assert fields["importer_npwp"] == "01.234.567.8-999.000"
    assert fields["total_packages"] == 42
    assert fields["gross_weight"] == 1250.50
    assert fields["currency"] == "USD"
    assert fields["cif_value"] == 12500.75


@pytest.mark.asyncio
async def test_prepare_document_runs_dual_ocr_candidates(monkeypatch):
    service = OCREngineService()

    async def fake_paddle(page_images):
        return {
            "fields": {"importer_npwp": "01.234.567.8-999.000"},
            "text": "paddle text",
            "confidence": 0.82,
        }

    async def fake_azure(file_bytes, mime_type):
        return {
            "fields": {"total_packages": 42},
            "text": "azure text",
            "confidence": 0.88,
        }

    monkeypatch.setattr(service, "_render_page_images", lambda file_bytes, suffix: [b"fake-image"])
    monkeypatch.setattr(service, "_run_paddle", fake_paddle)
    monkeypatch.setattr(service, "_run_azure", fake_azure)
    monkeypatch.setattr(service, "_estimate_quality", lambda images: 0.95)

    monkeypatch.setattr(settings, "ENABLE_DUAL_OCR", True)

    result = await service.prepare_document(
        doc_id="doc-123",
        storage_path="documents/doc-123.png",
        filename="doc-123.png",
        file_bytes=b"fake-image-bytes",
    )

    assert "paddleocr" in result["ocr_candidates"]
    assert "azure-di" in result["ocr_candidates"]
    assert "paddle text" in result["raw_text"]
    assert "azure text" in result["raw_text"]
    assert result["quality_score"] == 0.95
