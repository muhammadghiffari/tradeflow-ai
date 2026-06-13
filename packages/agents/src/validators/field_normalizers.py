"""
TradeFlow AI — Field Normalizers (T-041)

Normalizes raw OCR values to canonical forms before comparison.
Used by the reconciliation agent to ensure consistent majority voting.
"""

from __future__ import annotations

import re
from datetime import datetime


def normalize_value(field_name: str, raw_value: str | None) -> str | None:
    """
    Dispatch normalization based on field type.
    Returns None if raw_value is None or empty after normalization.
    """
    if raw_value is None:
        return None
    raw = str(raw_value).strip()
    if not raw:
        return None

    normalizers = {
        # Dates
        "bl_date": normalize_date,
        "invoice_date": normalize_date,
        "eta": normalize_date,
        "etd": normalize_date,
        "tglBl": normalize_date,
        "tglPendaftaran": normalize_date,
        "tglArrival": normalize_date,
        # Container numbers
        "container_number": normalize_container,
        "containerNumber": normalize_container,
        # HS codes
        "hs_code": normalize_hs_code,
        "posTarif": normalize_hs_code,
        # Weights
        "gross_weight": normalize_weight,
        "net_weight": normalize_weight,
        "beratKotor": normalize_weight,
        "beratBersih": normalize_weight,
        # Currency codes
        "currency": normalize_currency,
        # Monetary values
        "cif_value": normalize_monetary,
        "fob_value": normalize_monetary,
        "invoice_total": normalize_monetary,
        "cif": normalize_monetary,
        "fob": normalize_monetary,
        "freight": normalize_monetary,
        "asuransi": normalize_monetary,
        # NPWP / NIB
        "npwp": normalize_npwp,
        "nomorIdentitas": normalize_npwp,
        "nib": normalize_nib,
        "nibEntitas": normalize_nib,
        # Text fields
        "vessel_name": normalize_vessel_name,
        "namaKapal": normalize_vessel_name,
    }

    normalizer = normalizers.get(field_name, _default_normalize)
    return normalizer(raw)


def normalize_date(raw: str) -> str | None:
    """Normalize to ISO 8601 YYYY-MM-DD format."""
    # Already ISO
    if re.match(r"^\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]

    formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
        "%B %d, %Y", "%d %B %Y", "%d %b %Y",
        "%b %d, %Y", "%Y%m%d",
        "%d/%m/%y", "%m/%d/%Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw.strip()  # Return as-is if unparseable


def normalize_container(raw: str) -> str | None:
    """Normalize to ISO 6346: XXXX1234567 (no separators, uppercase)."""
    clean = re.sub(r"[\s\-./]", "", raw.strip().upper())
    # Extract container number pattern
    match = re.search(r"([A-Z]{4}\d{7})", clean)
    return match.group(1) if match else clean


def normalize_hs_code(raw: str) -> str | None:
    """Normalize HS code to 8 digits (BTKI Indonesia format)."""
    digits_only = re.sub(r"[.\s\-]", "", str(raw).strip())
    # Pad to 8 digits if shorter (e.g., 6-digit HS → first 6 + 00)
    if len(digits_only) == 6:
        return digits_only + "00"
    if len(digits_only) >= 8:
        return digits_only[:8]
    return digits_only


def normalize_weight(raw: str) -> str | None:
    """
    Normalize weight values: remove units (KGS, MT, LBS), strip commas.
    Returns string representation of float.
    """
    clean = re.sub(r"[,\s]", "", str(raw).strip())
    clean = re.sub(r"(?i)(KGS?|MT|LBS?|G|TON)\.?$", "", clean).strip()
    try:
        return str(round(float(clean), 3))
    except ValueError:
        return raw.strip()


def normalize_currency(raw: str) -> str | None:
    """Normalize currency code to ISO 4217 uppercase."""
    return re.sub(r"[^A-Za-z]", "", raw.strip()).upper()[:3]


def normalize_monetary(raw: str) -> str | None:
    """Normalize monetary value: remove currency symbols, commas."""
    clean = re.sub(r"[,$€£¥₹\s]", "", str(raw).strip())
    clean = re.sub(r"(?i)(USD|EUR|GBP|IDR|CNY|SGD)\.?", "", clean).strip()
    try:
        return str(round(float(clean), 2))
    except ValueError:
        return raw.strip()


def normalize_npwp(raw: str) -> str | None:
    """Normalize NPWP to 15 digits (strip dots and dashes)."""
    clean = re.sub(r"[.\-\s]", "", str(raw).strip())
    return clean if re.match(r"^\d{15}$", clean) else raw.strip()


def normalize_nib(raw: str) -> str | None:
    """Normalize NIB to 13 digits."""
    clean = re.sub(r"[\s\-]", "", str(raw).strip())
    return clean if re.match(r"^\d{13}$", clean) else raw.strip()


def normalize_vessel_name(raw: str) -> str | None:
    """
    Normalize vessel name: uppercase, strip honorifics (M/V, MV, S.S., NMV).
    Carrier profiles may also strip carrier-specific suffixes.
    """
    clean = raw.strip().upper()
    prefixes_to_strip = [
        r"^NMV\s+", r"^M/V\s+", r"^MV\s+", r"^S\.S\.\s+",
        r"^SS\s+", r"^MT\s+", r"^M\.T\.\s+",
    ]
    for pattern in prefixes_to_strip:
        clean = re.sub(pattern, "", clean).strip()
    return clean


def _default_normalize(raw: str) -> str | None:
    """Default: strip whitespace and uppercase."""
    return raw.strip().upper() if raw.strip() else None
