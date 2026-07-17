"""
TradeFlow AI — LangGraph State Definition
"""

from operator import add
from typing import Annotated, TypedDict


class DocumentState(TypedDict):
    doc_id: str
    doc_type: str
    storage_path: str
    pages: list[str]  # Base64 encoded images or temporary paths
    extracted_data: dict | None
    quality_score: float
    ocr_method: str | None
    error: str | None
    ocr_candidates: dict
    ocr_conflicts: list[dict]
    field_confidences: dict[str, float]

class ExtractionGraphState(TypedDict):
    """The state of the document extraction LangGraph."""
    batch_id: str
    company_id: str
    documents: list[DocumentState]
    combined_data: dict
    validation_results: list[dict]
    needs_human_review: bool
    risk_level: str
    customs_readiness_score: float | None
    crs_grade: str | None
    rejection_probability: float | None
    risk_features: dict
    ocr_conflicts: list[dict]
    field_confidences: dict[str, float]
    # Keep track of which node executed
    steps: Annotated[list[str], add]
