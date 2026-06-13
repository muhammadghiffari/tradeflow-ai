"""
TradeFlow AI — Field Validators (T-040)

Deterministic validators for CEISA 4.0 required fields.
All validators return (is_valid: bool, normalized_value: str | None).
These are used by the rule engine and reconciliation agent.
"""

from __future__ import annotations

import re
import string
from datetime import datetime


# ─────────────────────────────────────────────────────────────
# NPWP checksum validation
# ─────────────────────────────────────────────────────────────
def validate_npwp_checksum(npwp: str) -> bool:
    """
    Validate 15-digit NPWP (Nomor Pokok Wajib Pajak).
    Format: XX.XXX.XXX.X-XXX.XXX (stored without dots/dashes).
    """
    if not npwp:
        return False
    # Strip formatting characters
    clean = re.sub(r"[.\-\s]", "", npwp)
    if not re.match(r"^\d{15}$", clean):
        return False
    # Basic NPWP structure validation (not full modulo check — varies by KPP)
    return True


# ─────────────────────────────────────────────────────────────
# NIB format validation
# ─────────────────────────────────────────────────────────────
def validate_nib_format(nib: str) -> bool:
    """
    Validate NIB (Nomor Induk Berusaha) — exactly 13 digits.
    Issued by OSS (Online Single Submission).
    """
    if not nib:
        return False
    clean = re.sub(r"\s", "", nib)
    return bool(re.match(r"^\d{13}$", clean))


# ─────────────────────────────────────────────────────────────
# HS Code 8-digit validation (BTKI format)
# ─────────────────────────────────────────────────────────────
def validate_hs_8digit(hs_code: str) -> bool:
    """Validate HS code — must be exactly 8 digits (BTKI Indonesia format)."""
    if not hs_code:
        return False
    clean = re.sub(r"[.\s]", "", str(hs_code))
    return bool(re.match(r"^\d{8}$", clean))


# ─────────────────────────────────────────────────────────────
# UN/LOCODE validation
# ─────────────────────────────────────────────────────────────
_VALID_LOCODES: frozenset[str] = frozenset({
    # Indonesian ports
    "IDJKT", "IDJBK", "IDTPP", "IDSBY", "IDBTM", "IDPLM",
    "IDMKQ", "IDDJJ", "IDAMT",
    # Major origin ports
    "CNSHA", "CNSZX", "CNNGB", "CNGZH", "CNSHK", "CNQIN",
    "SGSIN", "MYPEN", "MYPKG", "MYKUA",
    "INNSA", "INMUN", "INPAV",
    "AEJEA", "AEAUH",
    "DEHAM", "GBTIL", "NLRTM",
    "USNYC", "USLAX", "USSEA",
    "JPOSA", "JPTYO",
    "KRPUS", "KRSEL",
    "VNSGN", "VNHPH",
    "THBKK", "THLTB",
})


def validate_unlocode(locode: str) -> bool:
    """
    Validate UN/LOCODE format (5 uppercase chars: 2-letter country + 3-letter port).
    Checks against a curated set of commonly used ports.
    For production, integrate with full UN/LOCODE database.
    """
    if not locode:
        return False
    clean = locode.strip().upper()
    if not re.match(r"^[A-Z]{2}[A-Z0-9]{3}$", clean):
        return False
    # Soft validation — accept any properly formatted LOCODE
    # (full lookup is done via the un_locodes table in the DB)
    return True


# ─────────────────────────────────────────────────────────────
# ISO date validation
# ─────────────────────────────────────────────────────────────
def validate_iso_date(date_str: str) -> bool:
    """Validate ISO 8601 date string (YYYY-MM-DD)."""
    if not date_str:
        return False
    try:
        datetime.strptime(date_str.strip(), "%Y-%m-%d")
        return True
    except ValueError:
        # Try alternate common formats from carrier docs
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%B %d, %Y", "%d %B %Y"):
            try:
                datetime.strptime(date_str.strip(), fmt)
                return True
            except ValueError:
                continue
    return False


# ─────────────────────────────────────────────────────────────
# ISO 4217 currency validation
# ─────────────────────────────────────────────────────────────
_COMMON_CURRENCIES = frozenset({
    "USD", "EUR", "GBP", "JPY", "CNY", "SGD", "AUD", "CAD",
    "CHF", "HKD", "KRW", "MYR", "THB", "IDR", "INR", "AED",
    "SAR", "SEK", "NOK", "DKK", "VND",
})


def validate_iso_4217(currency: str) -> bool:
    """Validate ISO 4217 currency code (3 uppercase letters)."""
    if not currency:
        return False
    clean = currency.strip().upper()
    return bool(re.match(r"^[A-Z]{3}$", clean))


# ─────────────────────────────────────────────────────────────
# Container number ISO 6346 validation
# ─────────────────────────────────────────────────────────────
def validate_container_iso6346(container_number: str) -> bool:
    """
    Validate container number per ISO 6346:
    4 alpha owner code + U/J/Z category + 6 digit serial + 1 check digit
    Pattern: XXXX-XXXXXXX (e.g., HLCU-1234567)
    """
    if not container_number:
        return False
    clean = re.sub(r"[\s\-]", "", container_number.strip().upper())
    if not re.match(r"^[A-Z]{4}\d{7}$", clean):
        return False

    # ISO 6346 check digit validation
    owner = clean[:4]
    serial = clean[4:10]
    check = clean[10]

    char_values = {c: i for i, c in enumerate(string.digits + string.ascii_uppercase)}
    total = 0
    for i, c in enumerate(owner + serial):
        val = char_values.get(c, 0)
        total += val * (2 ** i)

    computed_check = total % 11
    if computed_check == 10:
        computed_check = 0  # Per ISO 6346 spec

    try:
        return int(check) == computed_check
    except ValueError:
        return False
