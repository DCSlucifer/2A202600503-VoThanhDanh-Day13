"""
Tests for Member A: Logging & PII
Covers rubric items:
  - A1.Logging: JSON schema đúng, có correlation ID xuyên suốt
  - A1.Alerts&PII: PII được redact hoàn toàn
  - Bonus +2: Audit logs tách riêng
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import structlog

# ──────────────────────────────────────────────────────────────────────────────
# PII SCRUBBING — scrub_text
# ──────────────────────────────────────────────────────────────────────────────

from app.pii import PII_PATTERNS, hash_user_id, scrub_dict, scrub_text, summarize_text


class TestScrubText:
    """PII scrub_text must redact ALL documented PII categories."""

    def test_email_redacted(self) -> None:
        assert "student@" not in scrub_text("Email me at student@vinuni.edu.vn")
        assert "[REDACTED_EMAIL]" in scrub_text("Email me at student@vinuni.edu.vn")

    def test_email_with_plus(self) -> None:
        result = scrub_text("Contact john.doe+tag@gmail.com please")
        assert "john.doe" not in result
        assert "[REDACTED_EMAIL]" in result

    def test_phone_vn_mobile(self) -> None:
        result = scrub_text("Gọi cho tôi: 0912345678")
        assert "0912345678" not in result
        assert "[REDACTED_PHONE_VN]" in result

    def test_phone_vn_with_country_code(self) -> None:
        result = scrub_text("Phone: +84912345678")
        assert "+84912345678" not in result
        assert "[REDACTED_PHONE_VN]" in result

    def test_credit_card_visa(self) -> None:
        result = scrub_text("Card: 4111111111111111")
        assert "4111" not in result
        assert "[REDACTED_CREDIT_CARD]" in result

    def test_credit_card_spaced(self) -> None:
        result = scrub_text("Card: 4111 1111 1111 1111")
        assert "4111" not in result
        assert "[REDACTED_CREDIT_CARD]" in result

    def test_credit_card_mastercard(self) -> None:
        result = scrub_text("Pay with 5500000000000004")
        assert "5500" not in result
        assert "[REDACTED_CREDIT_CARD]" in result

    def test_cccd_12_digits(self) -> None:
        result = scrub_text("CCCD: 012345678901")
        assert "012345678901" not in result
        assert "[REDACTED_CCCD]" in result

    def test_passport_vn(self) -> None:
        result = scrub_text("Passport: B1234567")
        assert "B1234567" not in result
        assert "[REDACTED_PASSPORT_VN]" in result

    def test_address_vn(self) -> None:
        result = scrub_text("Ở quận Hoàn Kiếm")
        assert "[REDACTED_ADDRESS_VN]" in result

    def test_multiple_pii_in_one_string(self) -> None:
        text = "Email: user@test.com, Phone: 0912345678, Card: 4111111111111111"
        result = scrub_text(text)
        assert "[REDACTED_EMAIL]" in result
        assert "[REDACTED_PHONE_VN]" in result
        assert "[REDACTED_CREDIT_CARD]" in result
        # Confirm no raw PII remains
        assert "user@" not in result
        assert "0912345678" not in result
        assert "4111" not in result

    def test_clean_text_unchanged(self) -> None:
        text = "This is a normal log message with no PII"
        assert scrub_text(text) == text

    def test_all_pattern_names_are_registered(self) -> None:
        """Ensure the PII pattern registry has all expected types."""
        expected = {"credit_card", "email", "phone_vn", "cccd", "passport_vn", "address_vn"}
        assert expected.issubset(set(PII_PATTERNS.keys()))


# ──────────────────────────────────────────────────────────────────────────────
# PII SCRUBBING — scrub_dict (recursive)
# ──────────────────────────────────────────────────────────────────────────────

class TestScrubDict:
    def test_flat_dict(self) -> None:
        data = {"email": "user@test.com", "count": 5}
        result = scrub_dict(data)
        assert "[REDACTED_EMAIL]" in result["email"]
        assert result["count"] == 5

    def test_nested_dict(self) -> None:
        data = {"info": {"contact": "0912345678"}}
        result = scrub_dict(data)
        assert "[REDACTED_PHONE_VN]" in result["info"]["contact"]

    def test_list_in_dict(self) -> None:
        data = {"contacts": ["user@test.com", "admin@mail.com"]}
        result = scrub_dict(data)
        for item in result["contacts"]:
            assert "[REDACTED_EMAIL]" in item


# ──────────────────────────────────────────────────────────────────────────────
# PII HELPERS — hash_user_id and summarize_text
# ──────────────────────────────────────────────────────────────────────────────

class TestPIIHelpers:
    def test_hash_user_id_deterministic(self) -> None:
        h1 = hash_user_id("user123")
        h2 = hash_user_id("user123")
        assert h1 == h2

    def test_hash_user_id_different_for_different_users(self) -> None:
        assert hash_user_id("user1") != hash_user_id("user2")

    def test_hash_user_id_length(self) -> None:
        assert len(hash_user_id("anyuser")) == 12

    def test_hash_user_id_no_raw_id(self) -> None:
        """Hash must not contain the original user ID."""
        assert "user123" not in hash_user_id("user123")

    def test_summarize_text_scrubs_pii(self) -> None:
        result = summarize_text("Send to user@example.com right away")
        assert "[REDACTED_EMAIL]" in result
        assert "user@" not in result

    def test_summarize_text_truncates(self) -> None:
        long_text = "a" * 200
        result = summarize_text(long_text, max_len=80)
        assert len(result) <= 84  # 80 + len("...")


# ──────────────────────────────────────────────────────────────────────────────
# LOGGING CONFIG — structlog pipeline
# ──────────────────────────────────────────────────────────────────────────────

from app.logging_config import (
    AuditLogger,
    JsonlFileProcessor,
    add_service_name,
    audit_logger,
    scrub_event,
)


class TestScrubEventProcessor:
    """The structlog processor must scrub event strings and payload dicts."""

    def test_scrubs_event_string(self) -> None:
        ed = {"event": "User contacted user@test.com"}
        result = scrub_event(None, None, ed)
        assert "[REDACTED_EMAIL]" in result["event"]
        assert "user@" not in result["event"]

    def test_scrubs_payload_dict(self) -> None:
        ed = {"event": "ok", "payload": {"detail": "Card 4111111111111111"}}
        result = scrub_event(None, None, ed)
        assert "[REDACTED_CREDIT_CARD]" in result["payload"]["detail"]
        assert "4111" not in result["payload"]["detail"]

    def test_scrubs_loose_string_fields(self) -> None:
        for field in ("detail", "message_preview", "answer_preview", "query_preview"):
            ed = {"event": "ok", field: "phone 0987654321"}
            result = scrub_event(None, None, ed)
            assert "[REDACTED_PHONE_VN]" in result[field], f"Field {field} not scrubbed"


class TestAddServiceName:
    def test_adds_service_when_missing(self) -> None:
        ed = {"event": "test"}
        result = add_service_name(None, None, ed)
        assert "service" in result
        assert result["service"] == "day13-observability-lab"

    def test_preserves_existing_service(self) -> None:
        ed = {"event": "test", "service": "custom"}
        result = add_service_name(None, None, ed)
        assert result["service"] == "custom"


class TestJsonlFileProcessor:
    def test_writes_to_file(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test_logs.jsonl"
        proc = JsonlFileProcessor()

        with patch("app.logging_config.LOG_PATH", log_file):
            ed = {"event": "test_event", "level": "info"}
            proc(None, "info", ed)

        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) >= 1
        record = json.loads(lines[-1])
        assert record["event"] == "test_event"


# ──────────────────────────────────────────────────────────────────────────────
# AUDIT LOGGER — Bonus +2 pts
# ──────────────────────────────────────────────────────────────────────────────

class TestAuditLogger:
    """Bonus: Separate audit.jsonl, PII-free."""

    def test_writes_to_separate_file(self, tmp_path: Path) -> None:
        audit_file = tmp_path / "audit.jsonl"
        al = AuditLogger(path=audit_file)
        al.log("test_audit", user_id_hash="abc123", feature="qa")

        lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["audit"] is True
        assert record["event"] == "test_audit"

    def test_scrubs_pii_in_audit_event(self, tmp_path: Path) -> None:
        audit_file = tmp_path / "audit.jsonl"
        al = AuditLogger(path=audit_file)
        al.log("sent email to user@bad.com")

        record = json.loads(audit_file.read_text(encoding="utf-8").strip())
        assert "user@" not in record["event"]
        assert "[REDACTED_EMAIL]" in record["event"]

    def test_scrubs_pii_in_audit_fields(self, tmp_path: Path) -> None:
        audit_file = tmp_path / "audit.jsonl"
        al = AuditLogger(path=audit_file)
        al.log("request", detail="phone 0912345678")

        record = json.loads(audit_file.read_text(encoding="utf-8").strip())
        assert "0912345678" not in record["detail"]

    def test_audit_has_timestamp(self, tmp_path: Path) -> None:
        audit_file = tmp_path / "audit.jsonl"
        al = AuditLogger(path=audit_file)
        al.log("event")

        record = json.loads(audit_file.read_text(encoding="utf-8").strip())
        assert "ts" in record


# ──────────────────────────────────────────────────────────────────────────────
# MIDDLEWARE — correlation ID
# ──────────────────────────────────────────────────────────────────────────────

from app.middleware import CorrelationIdMiddleware, _is_valid_correlation_id


class TestCorrelationId:
    def test_valid_correlation_id_format(self) -> None:
        assert _is_valid_correlation_id("req-a1b2c3d4")
        assert _is_valid_correlation_id("req-00000000")

    def test_rejects_invalid_format(self) -> None:
        assert not _is_valid_correlation_id("abc-12345678")
        assert not _is_valid_correlation_id("req-GGGG0000")  # G is not hex
        assert not _is_valid_correlation_id("req-123")       # too short
        assert not _is_valid_correlation_id("")

    def test_rejects_injection_attempts(self) -> None:
        assert not _is_valid_correlation_id("req-12345678\nInjected-Header: value")
        assert not _is_valid_correlation_id("req-<script>")


# ──────────────────────────────────────────────────────────────────────────────
# LOGGING SCHEMA — JSON structure
# ──────────────────────────────────────────────────────────────────────────────

class TestLoggingSchema:
    def test_required_fields_defined(self) -> None:
        schema_path = Path("config/logging_schema.json")
        assert schema_path.exists(), "logging_schema.json must exist"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        required = set(schema.get("required", []))
        assert {"ts", "level", "service", "event", "correlation_id"}.issubset(required)

    def test_schema_has_enrichment_fields(self) -> None:
        schema_path = Path("config/logging_schema.json")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        props = set(schema.get("properties", {}).keys())
        assert {"user_id_hash", "session_id", "feature", "model"}.issubset(props)

    def test_schema_has_payload_field(self) -> None:
        schema_path = Path("config/logging_schema.json")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        assert "payload" in schema.get("properties", {}), "Schema should include payload field"
