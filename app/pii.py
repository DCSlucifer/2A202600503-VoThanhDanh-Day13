from __future__ import annotations

import hashlib
import re
from typing import Any

# ---------------------------------------------------------------------------
# PII Pattern Registry
# Each entry: name -> compiled regex pattern
# Ordered from most specific to least to avoid partial double-redaction.
# ---------------------------------------------------------------------------
_RAW_PATTERNS: dict[str, str] = {
    # Credit card: major networks (Visa, MC, Amex, Discover) — also catches 4111 test numbers
    "credit_card": (
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?|"       # Visa 13/16
        r"5[1-5][0-9]{14}|"                      # Mastercard
        r"3[47][0-9]{13}|"                       # Amex
        r"6(?:011|5[0-9]{2})[0-9]{12})"          # Discover
        r"\b"
        r"|"
        r"\b\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}\b" # Generic spaced/dashed 16-digit
    ),
    # Vietnamese email addresses (also catches international)
    "email": r"[\w.\+\-]+@[\w.\-]+\.\w{2,}",
    # Vietnamese phone: 0xx or +84xx formats
    "phone_vn": r"(?:\+84|0)[235789]\d{8}\b",
    # CCCD / CMND: 12-digit (new) or 9-digit (old, only standalone)
    "cccd": r"\b\d{12}\b|\b\d{9}\b",
    # Vietnamese passport: 1 letter + 7-8 digits  (e.g. B1234567, N1234567)
    "passport_vn": r"\b[A-Z]\d{7,8}\b",
    # Vietnamese address keywords followed by place name
    "address_vn": (
        r"(?i)\b(?:phường|quận|huyện|xã|tỉnh|thành\s+phố|tp\.?|p\.?|q\.?)\s+"
        r"[^\s,;\"\']{2,30}"
    ),
}

# Pre-compile for performance
PII_PATTERNS: dict[str, re.Pattern] = {
    name: re.compile(pattern, re.IGNORECASE)
    for name, pattern in _RAW_PATTERNS.items()
}


def scrub_text(text: str) -> str:
    """Replace all PII occurrences in a string with [REDACTED_<TYPE>] tokens."""
    safe = text
    for name, pattern in PII_PATTERNS.items():
        safe = pattern.sub(f"[REDACTED_{name.upper()}]", safe)
    return safe


def scrub_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively scrub all string values in a dict, including nested dicts/lists."""
    result: dict[str, Any] = {}
    for k, v in data.items():
        result[k] = _scrub_value(v)
    return result


def _scrub_value(v: Any) -> Any:
    if isinstance(v, str):
        return scrub_text(v)
    if isinstance(v, dict):
        return scrub_dict(v)
    if isinstance(v, list):
        return [_scrub_value(item) for item in v]
    return v


def summarize_text(text: str, max_len: int = 80) -> str:
    """Scrub PII and truncate for safe logging/tracing previews."""
    safe = scrub_text(text).strip().replace("\n", " ")
    return safe[:max_len] + ("..." if len(safe) > max_len else "")


def hash_user_id(user_id: str) -> str:
    """One-way hash of user_id — safe to log, can correlate across requests."""
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
