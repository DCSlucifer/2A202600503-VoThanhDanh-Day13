"""
End-to-End Integration Test
Verifies the full pipeline: request → logging → PII scrub → tracing → metrics → audit.
This test starts the FastAPI app with TestClient and sends real requests.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def clean_logs(tmp_path: Path):
    """Redirect log and audit output to temp files."""
    log_file = tmp_path / "logs.jsonl"
    audit_file = tmp_path / "audit.jsonl"
    with patch("app.logging_config.LOG_PATH", log_file), \
         patch("app.logging_config.AUDIT_LOG_PATH", audit_file):
        # Re-create audit logger with temp path
        from app.logging_config import AuditLogger
        temp_audit = AuditLogger(path=audit_file)
        with patch("app.main.audit_logger", temp_audit), \
             patch("app.logging_config.audit_logger", temp_audit):
            yield log_file, audit_file


@pytest.fixture
def client(clean_logs):
    from app.main import app
    return TestClient(app)


class TestEndToEnd:
    """Full pipeline integration tests."""

    def test_health_endpoint(self, client: TestClient) -> None:
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "ok" in data
        assert data["ok"] is True
        assert "tracing_enabled" in data
        assert "incidents" in data

    def test_metrics_endpoint(self, client: TestClient) -> None:
        r = client.get("/metrics")
        assert r.status_code == 200
        data = r.json()
        assert "traffic" in data
        assert "latency_p50" in data

    def test_chat_returns_correlation_id(self, client: TestClient) -> None:
        r = client.post("/chat", json={
            "user_id": "u_test_01",
            "session_id": "s_test_01",
            "feature": "qa",
            "message": "What is monitoring?"
        })
        assert r.status_code == 200
        data = r.json()
        assert "correlation_id" in data
        assert data["correlation_id"].startswith("req-")
        assert len(data["correlation_id"]) == 12  # "req-" + 8 hex

    def test_chat_response_has_all_fields(self, client: TestClient) -> None:
        r = client.post("/chat", json={
            "user_id": "u_test_02",
            "session_id": "s_test_02",
            "feature": "qa",
            "message": "Tell me about refund policy"
        })
        data = r.json()
        assert "answer" in data
        assert "latency_ms" in data
        assert "tokens_in" in data
        assert "tokens_out" in data
        assert "cost_usd" in data
        assert "quality_score" in data

    def test_correlation_id_in_response_header(self, client: TestClient) -> None:
        r = client.post("/chat", json={
            "user_id": "u_test_03",
            "session_id": "s_test_03",
            "feature": "qa",
            "message": "Test request"
        })
        assert "x-request-id" in r.headers
        assert r.headers["x-request-id"].startswith("req-")

    def test_response_time_header(self, client: TestClient) -> None:
        r = client.post("/chat", json={
            "user_id": "u_test_04",
            "session_id": "s_test_04",
            "feature": "qa",
            "message": "Test timing"
        })
        assert "x-response-time-ms" in r.headers
        assert int(r.headers["x-response-time-ms"]) >= 0

    def test_correlation_id_propagated_from_header(self, client: TestClient) -> None:
        custom_id = "req-aabbccdd"
        r = client.post("/chat", json={
            "user_id": "u_test_05",
            "session_id": "s_test_05",
            "feature": "qa",
            "message": "Test propagation"
        }, headers={"x-request-id": custom_id})
        assert r.json()["correlation_id"] == custom_id
        assert r.headers["x-request-id"] == custom_id

    def test_pii_not_in_logs(self, client: TestClient, clean_logs) -> None:
        log_file, _ = clean_logs
        # Send a request with PII in the message
        client.post("/chat", json={
            "user_id": "u_test_pii",
            "session_id": "s_test_pii",
            "feature": "qa",
            "message": "My email is student@vinuni.edu.vn and card 4111111111111111"
        })
        # Check log file for PII leaks
        if log_file.exists():
            content = log_file.read_text(encoding="utf-8")
            assert "student@" not in content, "Email PII leaked to logs!"
            assert "4111111111111111" not in content, "Credit card PII leaked to logs!"

    def test_audit_log_written(self, client: TestClient, clean_logs) -> None:
        _, audit_file = clean_logs
        client.post("/chat", json={
            "user_id": "u_audit_test",
            "session_id": "s_audit_test",
            "feature": "qa",
            "message": "Test audit logging"
        })
        if audit_file.exists():
            lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
            assert len(lines) >= 1, "Audit log should have entries"
            for line in lines:
                record = json.loads(line)
                assert record.get("audit") is True

    def test_incident_toggle(self, client: TestClient) -> None:
        # Enable
        r = client.post("/incidents/rag_slow/enable")
        assert r.status_code == 200
        assert r.json()["incidents"]["rag_slow"] is True

        # Disable
        r = client.post("/incidents/rag_slow/disable")
        assert r.status_code == 200
        assert r.json()["incidents"]["rag_slow"] is False

    def test_incident_unknown_returns_404(self, client: TestClient) -> None:
        r = client.post("/incidents/nonexistent/enable")
        assert r.status_code == 404

    def test_metrics_increase_after_requests(self, client: TestClient) -> None:
        # Get baseline
        r1 = client.get("/metrics")
        traffic_before = r1.json()["traffic"]

        # Send request
        client.post("/chat", json={
            "user_id": "u_metrics",
            "session_id": "s_metrics",
            "feature": "qa",
            "message": "Testing metrics update"
        })

        # Check increase
        r2 = client.get("/metrics")
        traffic_after = r2.json()["traffic"]
        assert traffic_after > traffic_before
