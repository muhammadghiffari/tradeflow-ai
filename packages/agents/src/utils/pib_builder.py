"""
TradeFlow AI — PIB Payload Builder (T-058)

Assembles the complete CEISA 4.0 PIB JSON from DeclarationState.
Maps reconciled field names to CEISA schema field names.

Never hardcode CEISA field mappings here — mapping table is derived
from the SDD §3.3 FieldMapping specification.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ..state import DeclarationState

logger = logging.getLogger("agents.pib_builder")

# ─────────────────────────────────────────────────────────────
# Field mapping: reconciled_field_name → CEISA JSON path
# ─────────────────────────────────────────────────────────────
_HEADER_FIELD_MAP = {
    "nomorBl":              ["bl_number", "nomorBl"],
    "namaKapal":            ["vessel_name", "namaKapal"],
    "voyageNumber":         ["voyage_number", "voyageNumber"],
    "kodePelabuhanMuat":    ["port_loading_code", "kodePelabuhanMuat"],
    "kodePelabuhanBongkar": ["port_discharge_code", "kodePelabuhanBongkar"],
    "tglBl":                ["bl_date", "tglBl"],
    "tglArrival":           ["arrival_date", "tglArrival", "eta"],
    "beratKotor":           ["gross_weight", "beratKotor"],
    "beratBersih":          ["net_weight", "beratBersih"],
    "jumlahKemasan":        ["total_packages", "jumlahKemasan"],
    "nomorContainer":       ["container_number", "nomorContainer"],
}

_ENTITY_FIELD_MAP = {
    "npwp":         ["npwp", "nomorIdentitas", "buyer_npwp"],
    "nib":          ["nib", "nibEntitas"],
    "namaEntitas":  ["buyer_name", "namaEntitas", "consignee_name"],
    "alamatEntitas": ["buyer_address", "alamatEntitas"],
}

_ITEM_FIELD_MAP = {
    "posTarif":       ["hs_code", "posTarif"],
    "uraianBarang":   ["goods_description", "uraianBarang", "description_of_goods"],
    "jumlahSatuan":   ["quantity", "jumlahSatuan"],
    "satuanBarang":   ["unit", "satuanBarang"],
    "nilaiBarangFob": ["unit_price", "nilaiBarangFob"],
    "nilaiTotalFob":  ["fob_value", "nilaiTotalFob", "total_amount"],
    "valuta":         ["currency", "valuta"],
}


def _pick_value(reconciled_fields: dict, candidate_keys: list[str]) -> Any:
    """Try multiple field name candidates and return the first non-null value."""
    for key in candidate_keys:
        field = reconciled_fields.get(key)
        if field is None:
            continue
        if isinstance(field, dict):
            val = field.get("value")
            if val is not None:
                return val
        elif field:
            return field
    return None


def build_pib_payload(state: DeclarationState) -> dict:
    """
    Assemble complete PIB JSON from state.
    Uses operator_corrections to override reconciled values where present.
    """
    if not state.get("reconciled_fields"):
        raise ValueError("Cannot build PIB: no reconciled fields in state")

    # Merge reconciled + corrections
    primary_doc = _merge_corrections(
        state["reconciled_fields"][0] if state["reconciled_fields"] else {},
        state.get("operator_corrections", []),
    )

    # Header fields
    header = {}
    for ceisa_key, candidates in _HEADER_FIELD_MAP.items():
        val = _pick_value(primary_doc, candidates)
        if val is not None:
            header[ceisa_key] = str(val)

    # Entity (importir)
    entity = {"tipeEntitas": "IMPORTIR"}
    for ceisa_key, candidates in _ENTITY_FIELD_MAP.items():
        val = _pick_value(primary_doc, candidates)
        if val is not None:
            entity[ceisa_key] = str(val)

    # HS line items
    items = _build_items(state)

    # CIF breakdown
    cif_breakdown = _build_cif(primary_doc)

    # HS recommendations override where confidence is low
    items = _apply_hs_recommendations(items, state.get("hs_recommendations", []))

    payload = {
        "kodeDokumen": "20",
        "ajuNumber": "",
        "nomorBl": header.get("nomorBl", ""),
        "namaKapal": header.get("namaKapal", ""),
        "voyageNumber": header.get("voyageNumber", ""),
        "kodePelabuhanMuat": header.get("kodePelabuhanMuat", ""),
        "kodePelabuhanBongkar": header.get("kodePelabuhanBongkar", "IDJKT"),
        "tglBl": header.get("tglBl", ""),
        "tglArrival": header.get("tglArrival", ""),
        "beratKotor": _safe_float(header.get("beratKotor")),
        "beratBersih": _safe_float(header.get("beratBersih")),
        "jumlahKemasan": _safe_int(header.get("jumlahKemasan")),
        "nomorContainer": header.get("nomorContainer", ""),
        "entitas": [entity],
        "barang": items,
        "nilaiCif": cif_breakdown.get("cif"),
        "nilaiFreight": cif_breakdown.get("freight"),
        "nilaiAsuransi": cif_breakdown.get("insurance"),
        "nilaiFob": cif_breakdown.get("fob"),
        "valuta": _pick_value(primary_doc, ["currency", "valuta"]) or "USD",
        "_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "batch_id": state.get("batch_id", ""),
            "crs_score": state.get("crs", {}).get("score"),
            "agent_agreement_rate": state.get("agent_agreement_rate"),
        },
    }

    return payload


def _merge_corrections(reconciled: dict, corrections: list[dict]) -> dict:
    """Apply operator corrections on top of reconciled fields."""
    merged = dict(reconciled)
    for correction in corrections:
        field = correction.get("field_name")
        value = correction.get("corrected_value")
        if field and value is not None:
            if field in merged and isinstance(merged[field], dict):
                merged[field] = {**merged[field], "value": value, "source": "operator"}
            else:
                merged[field] = {"value": value, "source": "operator", "confidence": 1.0}
    return merged


def _build_items(state: DeclarationState) -> list[dict]:
    """Build barang (line items) list from reconciled fields and HS recs."""
    items = []
    for doc_fields in state.get("reconciled_fields", []):
        item = {}
        for ceisa_key, candidates in _ITEM_FIELD_MAP.items():
            val = _pick_value(doc_fields, candidates)
            if val is not None:
                item[ceisa_key] = str(val)
        if item.get("posTarif") or item.get("uraianBarang"):
            item.setdefault("jumlahSatuan", "1")
            item.setdefault("satuanBarang", "PKG")
            items.append(item)
    # Ensure at least one item
    if not items:
        items.append({
            "posTarif": "00000000",
            "uraianBarang": "UNCLASSIFIED",
            "jumlahSatuan": "1",
            "satuanBarang": "PKG",
        })
    return items


def _build_cif(fields: dict) -> dict:
    """Extract CIF breakdown values."""
    return {
        "fob": _safe_float(_pick_value(fields, ["fob_value", "nilaiTotalFob", "fob"])),
        "freight": _safe_float(_pick_value(fields, ["freight", "nilaiFreight"])),
        "insurance": _safe_float(_pick_value(fields, ["insurance", "nilaiAsuransi", "asuransi"])),
        "cif": _safe_float(_pick_value(fields, ["cif_value", "nilaiCif", "total_cif"])),
    }


def _apply_hs_recommendations(items: list[dict], recs: list[dict]) -> list[dict]:
    """Apply top HS recommendation to items where HS is missing or low confidence."""
    if not recs or not items:
        return items
    for i, item in enumerate(items):
        if not item.get("posTarif") or item["posTarif"] == "00000000":
            if i < len(recs):
                item["posTarif"] = recs[i].get("hs_code", item.get("posTarif", ""))
                item["_hs_recommended"] = True
    return items


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return round(float(str(val).replace(",", "")), 2)
    except (ValueError, TypeError):
        return None


def _safe_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        return int(float(str(val).replace(",", "")))
    except (ValueError, TypeError):
        return None
