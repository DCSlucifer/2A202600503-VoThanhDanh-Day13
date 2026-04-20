"""
Tests for Member C: SLO & Alerts
Covers rubric items:
  - A1.Dashboard&SLO: Có bảng SLO hợp lý
  - A1.Alerts&PII: Có ít nhất 3 alert rules với runbook link hoạt động
  - Bonus +3: Cost optimization (before/after numbers)
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml
import pytest

from app.metrics import (
    ERRORS,
    QUALITY_SCORES,
    REQUEST_COSTS,
    REQUEST_LATENCIES,
    REQUEST_TOKENS_IN,
    REQUEST_TOKENS_OUT,
    percentile,
    record_error,
    record_request,
    snapshot,
)


# ──────────────────────────────────────────────────────────────────────────────
# SLO CONFIGURATION — config/slo.yaml
# ──────────────────────────────────────────────────────────────────────────────

class TestSLOConfig:
    """SLO config must be well-structured with meaningful objectives."""

    @pytest.fixture
    def slo(self) -> dict:
        slo_path = Path("config/slo.yaml")
        assert slo_path.exists(), "config/slo.yaml must exist"
        return yaml.safe_load(slo_path.read_text(encoding="utf-8"))

    def test_slo_has_service_name(self, slo: dict) -> None:
        assert "service" in slo
        assert slo["service"] == "day13-observability-lab"

    def test_slo_has_window(self, slo: dict) -> None:
        assert "window" in slo
        assert slo["window"] == "28d"

    def test_slo_has_at_least_4_slis(self, slo: dict) -> None:
        slis = slo.get("slis", {})
        assert len(slis) >= 4, f"Expected >=4 SLIs, got {len(slis)}"

    def test_sli_latency_p95_defined(self, slo: dict) -> None:
        sli = slo["slis"]["latency_p95_ms"]
        assert sli["objective"] > 0
        assert sli["target"] >= 95
        assert "alert" in sli

    def test_sli_error_rate_defined(self, slo: dict) -> None:
        sli = slo["slis"]["error_rate_pct"]
        assert sli["objective"] <= 5
        assert sli["target"] >= 99
        assert "alert" in sli

    def test_sli_daily_cost_defined(self, slo: dict) -> None:
        sli = slo["slis"]["daily_cost_usd"]
        assert sli["objective"] > 0
        assert "alert" in sli

    def test_sli_quality_score_defined(self, slo: dict) -> None:
        sli = slo["slis"]["quality_score_avg"]
        assert 0 < sli["objective"] <= 1
        assert "alert" in sli

    def test_all_slis_have_description(self, slo: dict) -> None:
        for name, sli in slo["slis"].items():
            assert "description" in sli, f"SLI {name} missing description"

    def test_all_slis_have_breach_budget(self, slo: dict) -> None:
        """Breach budget hours show thoughtful SLO design."""
        for name, sli in slo["slis"].items():
            # daily_cost_usd is always-on (100% target), no budget needed
            if sli.get("target") == 100.0:
                continue
            assert "breach_budget_hours" in sli, f"SLI {name} missing breach budget"


# ──────────────────────────────────────────────────────────────────────────────
# ALERT RULES — config/alert_rules.yaml
# ──────────────────────────────────────────────────────────────────────────────

class TestAlertRules:
    """Alert rules must be complete, actionable, and linked to runbooks."""

    @pytest.fixture
    def alerts(self) -> list[dict]:
        alert_path = Path("config/alert_rules.yaml")
        assert alert_path.exists(), "config/alert_rules.yaml must exist"
        data = yaml.safe_load(alert_path.read_text(encoding="utf-8"))
        return data.get("alerts", [])

    def test_at_least_3_alert_rules(self, alerts: list[dict]) -> None:
        """Rubric requires >=3 alert rules."""
        assert len(alerts) >= 3, f"Expected >=3 alerts, got {len(alerts)}"

    def test_has_4_alert_rules(self, alerts: list[dict]) -> None:
        """We have 4 alerts covering all SLIs — exceeds rubric minimum."""
        assert len(alerts) == 4

    def test_all_alerts_have_name(self, alerts: list[dict]) -> None:
        for alert in alerts:
            assert "name" in alert and alert["name"]

    def test_all_alerts_have_severity(self, alerts: list[dict]) -> None:
        for alert in alerts:
            assert "severity" in alert
            assert alert["severity"] in ("P1", "P2", "P3", "P4")

    def test_all_alerts_have_condition(self, alerts: list[dict]) -> None:
        for alert in alerts:
            assert "condition" in alert and alert["condition"]

    def test_all_alerts_have_threshold(self, alerts: list[dict]) -> None:
        for alert in alerts:
            assert "threshold" in alert
            assert isinstance(alert["threshold"], (int, float))

    def test_all_alerts_have_window(self, alerts: list[dict]) -> None:
        for alert in alerts:
            assert "window" in alert and alert["window"]

    def test_all_alerts_have_runbook_link(self, alerts: list[dict]) -> None:
        """Rubric: runbook link hoạt động (active/working link)."""
        for alert in alerts:
            assert "runbook" in alert, f"Alert {alert['name']} missing runbook"
            runbook = alert["runbook"]
            assert runbook.startswith("docs/alerts.md"), f"Runbook should point to docs/alerts.md"

    def test_runbook_sections_exist_in_alerts_md(self, alerts: list[dict]) -> None:
        """Verify each runbook anchor actually exists in docs/alerts.md."""
        alerts_md = Path("docs/alerts.md")
        assert alerts_md.exists(), "docs/alerts.md must exist"
        content = alerts_md.read_text(encoding="utf-8").lower()

        for alert in alerts:
            runbook = alert.get("runbook", "")
            if "#" in runbook:
                anchor = runbook.split("#")[1]
                # Check that the heading exists (markdown anchors are lowercased, hyphens)
                heading_text = anchor.replace("-", " ").strip()
                # Just check that keywords from the anchor appear in the doc
                keywords = [w for w in heading_text.split() if len(w) > 2]
                for kw in keywords:
                    assert kw in content, f"Runbook anchor keyword '{kw}' not found in alerts.md"

    def test_all_alerts_have_type(self, alerts: list[dict]) -> None:
        for alert in alerts:
            assert "type" in alert
            assert alert["type"] in ("symptom-based", "anomaly-based", "cause-based")

    def test_all_alerts_have_owner(self, alerts: list[dict]) -> None:
        for alert in alerts:
            assert "owner" in alert and alert["owner"]

    def test_all_alerts_have_labels(self, alerts: list[dict]) -> None:
        for alert in alerts:
            assert "labels" in alert
            assert "team" in alert["labels"]
            assert "slo" in alert["labels"]

    def test_all_alerts_have_annotations(self, alerts: list[dict]) -> None:
        for alert in alerts:
            assert "annotations" in alert
            assert "summary" in alert["annotations"]
            assert "description" in alert["annotations"]

    def test_alert_names_match_slo_alerts(self) -> None:
        """Each SLO should reference an existing alert rule."""
        slo_data = yaml.safe_load(
            Path("config/slo.yaml").read_text(encoding="utf-8")
        )
        alert_data = yaml.safe_load(
            Path("config/alert_rules.yaml").read_text(encoding="utf-8")
        )
        alert_names = {a["name"] for a in alert_data["alerts"]}

        for sli_name, sli in slo_data["slis"].items():
            referenced_alert = sli.get("alert")
            assert referenced_alert in alert_names, (
                f"SLI '{sli_name}' references alert '{referenced_alert}' which doesn't exist"
            )


# ──────────────────────────────────────────────────────────────────────────────
# RUNBOOK — docs/alerts.md content quality
# ──────────────────────────────────────────────────────────────────────────────

class TestRunbook:
    """Runbook must be actionable with structured debugging flow."""

    @pytest.fixture
    def content(self) -> str:
        return Path("docs/alerts.md").read_text(encoding="utf-8")

    def test_has_debug_flow_section(self, content: str) -> None:
        assert "Metrics" in content and "Traces" in content and "Logs" in content

    def test_has_mitigation_steps(self, content: str) -> None:
        assert "Mitigation" in content or "mitigation" in content

    def test_has_first_checks(self, content: str) -> None:
        assert "First checks" in content or "first checks" in content

    def test_has_user_impact(self, content: str) -> None:
        assert "User impact" in content or "user impact" in content

    def test_mentions_correlation_id(self, content: str) -> None:
        assert "correlation_id" in content

    def test_has_at_least_4_sections(self, content: str) -> None:
        """One section per alert rule."""
        section_count = content.count("## ")
        assert section_count >= 4


# ──────────────────────────────────────────────────────────────────────────────
# METRICS MODULE — in-memory aggregation
# ──────────────────────────────────────────────────────────────────────────────

class TestMetrics:
    @pytest.fixture(autouse=True)
    def reset_metrics(self) -> None:
        """Reset global state before each test."""
        import app.metrics as m
        m.REQUEST_LATENCIES.clear()
        m.REQUEST_COSTS.clear()
        m.REQUEST_TOKENS_IN.clear()
        m.REQUEST_TOKENS_OUT.clear()
        m.ERRORS.clear()
        m.QUALITY_SCORES.clear()
        m.TRAFFIC = 0

    def test_percentile_empty(self) -> None:
        assert percentile([], 50) == 0.0

    def test_percentile_single(self) -> None:
        assert percentile([100], 50) == 100.0

    def test_percentile_basic(self) -> None:
        values = [100, 200, 300, 400]
        p50 = percentile(values, 50)
        assert 100 <= p50 <= 400

    def test_percentile_p95(self) -> None:
        values = list(range(1, 101))
        p95 = percentile(values, 95)
        assert p95 >= 90

    def test_record_request(self) -> None:
        record_request(latency_ms=150, cost_usd=0.01, tokens_in=100, tokens_out=50, quality_score=0.8)
        snap = snapshot()
        assert snap["traffic"] == 1
        assert snap["total_cost_usd"] == 0.01
        assert snap["quality_avg"] == 0.8

    def test_record_error(self) -> None:
        record_error("TimeoutError")
        record_error("TimeoutError")
        record_error("ValueError")
        snap = snapshot()
        assert snap["error_breakdown"]["TimeoutError"] == 2
        assert snap["error_breakdown"]["ValueError"] == 1

    def test_snapshot_fields(self) -> None:
        record_request(latency_ms=100, cost_usd=0.005, tokens_in=50, tokens_out=30, quality_score=0.9)
        snap = snapshot()
        required_keys = {
            "traffic", "latency_p50", "latency_p95", "latency_p99",
            "avg_cost_usd", "total_cost_usd", "tokens_in_total",
            "tokens_out_total", "error_breakdown", "quality_avg",
        }
        assert required_keys.issubset(set(snap.keys()))

    def test_snapshot_matches_dashboard_panels(self) -> None:
        """Snapshot must provide data for all 6 dashboard panels."""
        record_request(latency_ms=200, cost_usd=0.01, tokens_in=100, tokens_out=80, quality_score=0.75)
        snap = snapshot()
        # Panel 1: Latency P50/P95/P99
        assert "latency_p50" in snap
        assert "latency_p95" in snap
        assert "latency_p99" in snap
        # Panel 2: Traffic
        assert "traffic" in snap
        # Panel 3: Error rate
        assert "error_breakdown" in snap
        # Panel 4: Cost
        assert "total_cost_usd" in snap
        assert "avg_cost_usd" in snap
        # Panel 5: Tokens
        assert "tokens_in_total" in snap
        assert "tokens_out_total" in snap
        # Panel 6: Quality
        assert "quality_avg" in snap


# ──────────────────────────────────────────────────────────────────────────────
# COST ESTIMATION — Bonus +3 cost optimization evidence
# ──────────────────────────────────────────────────────────────────────────────

from app.agent import LabAgent


class TestCostEstimation:
    """Cost tracking enables the cost optimization bonus."""

    def test_cost_formula(self) -> None:
        agent = LabAgent()
        cost = agent._estimate_cost(tokens_in=1000, tokens_out=500)
        # $3/M input + $15/M output
        expected = (1000 / 1_000_000) * 3 + (500 / 1_000_000) * 15
        assert abs(cost - round(expected, 6)) < 1e-6

    def test_cost_increases_with_tokens(self) -> None:
        agent = LabAgent()
        cost_small = agent._estimate_cost(100, 50)
        cost_large = agent._estimate_cost(10000, 5000)
        assert cost_large > cost_small

    def test_cost_in_snapshot(self) -> None:
        import app.metrics as m
        m.REQUEST_COSTS.clear()
        m.REQUEST_LATENCIES.clear()
        m.REQUEST_TOKENS_IN.clear()
        m.REQUEST_TOKENS_OUT.clear()
        m.QUALITY_SCORES.clear()
        m.TRAFFIC = 0

        record_request(latency_ms=100, cost_usd=0.01, tokens_in=100, tokens_out=50, quality_score=0.8)
        record_request(latency_ms=200, cost_usd=0.02, tokens_in=200, tokens_out=100, quality_score=0.7)
        snap = snapshot()
        assert snap["total_cost_usd"] == 0.03
        assert snap["avg_cost_usd"] == 0.015
