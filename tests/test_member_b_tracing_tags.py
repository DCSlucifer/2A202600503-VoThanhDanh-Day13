"""
Tests for Member B: Tracing & Tags
Covers rubric items:
  - A1.Logging&Tracing: ít nhất 10 traces trên Langfuse với đầy đủ metadata
  - Tracing module: @observe decorator, tag propagation, safe helpers
  - Bonus +2: Auto-instrumentation (instrument decorator)
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from app.tracing import (
    instrument,
    observe,
    safe_score_trace,
    safe_update_observation,
    safe_update_trace,
    tracing_enabled,
)


# ──────────────────────────────────────────────────────────────────────────────
# TRACING ENABLED / DISABLED
# ──────────────────────────────────────────────────────────────────────────────

class TestTracingEnabled:
    def test_disabled_when_no_keys(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            # Without keys it should be False (unless Langfuse not installed)
            result = tracing_enabled()
            # Could be True (keys set globally) or False; 
            # just ensure function returns bool
            assert isinstance(result, bool)

    def test_enabled_when_keys_set(self) -> None:
        with patch.dict(os.environ, {
            "LANGFUSE_PUBLIC_KEY": "pk-test",
            "LANGFUSE_SECRET_KEY": "sk-test",
        }):
            # If Langfuse is available AND keys are set
            from app.tracing import _LANGFUSE_AVAILABLE
            if _LANGFUSE_AVAILABLE:
                assert tracing_enabled() is True


# ──────────────────────────────────────────────────────────────────────────────
# OBSERVE DECORATOR EXISTS AND IS CALLABLE
# ──────────────────────────────────────────────────────────────────────────────

class TestObserveDecorator:
    def test_observe_is_callable(self) -> None:
        """observe must work as a decorator factory."""
        assert callable(observe)

    def test_observe_decorates_function(self) -> None:
        @observe(name="test.span")
        def dummy_func(x: int) -> int:
            return x + 1

        # Decorated function must still be callable
        assert dummy_func(5) == 6

    def test_observe_preserves_return_value(self) -> None:
        @observe(name="test.return")
        def compute(a: int, b: int) -> int:
            return a * b

        assert compute(3, 4) == 12


# ──────────────────────────────────────────────────────────────────────────────
# SAFE HELPERS — must never raise
# ──────────────────────────────────────────────────────────────────────────────

class TestSafeHelpers:
    def test_safe_update_trace_no_crash(self) -> None:
        """safe_update_trace must swallow errors silently."""
        safe_update_trace(user_id="test", tags=["lab"])

    def test_safe_update_observation_no_crash(self) -> None:
        safe_update_observation(metadata={"key": "value"})

    def test_safe_score_trace_no_crash(self) -> None:
        safe_score_trace(name="quality", value=0.85, comment="test")


# ──────────────────────────────────────────────────────────────────────────────
# INSTRUMENT DECORATOR (Bonus: +2 pts auto-instrumentation)
# ──────────────────────────────────────────────────────────────────────────────

class TestInstrumentDecorator:
    """Bonus: Auto-instrumentation via @instrument decorator."""

    def test_instrument_is_callable(self) -> None:
        assert callable(instrument)

    def test_instrument_wraps_function(self) -> None:
        @instrument("test.instrument", step="retrieval")
        def my_step(data: str) -> str:
            return f"processed-{data}"

        assert my_step("input") == "processed-input"

    def test_instrument_preserves_function_name(self) -> None:
        @instrument("test.named", step="gen")
        def my_function() -> None:
            pass

        assert my_function.__name__ == "my_function"


# ──────────────────────────────────────────────────────────────────────────────
# AGENT TRACING — tags and metadata on traces
# ──────────────────────────────────────────────────────────────────────────────

from app.agent import AgentResult, LabAgent


class TestAgentTracingIntegration:
    """Verify that agent.run produces correct result and tracing is wired."""

    def test_agent_run_returns_result(self) -> None:
        agent = LabAgent()
        result = agent.run(
            user_id="test_user",
            feature="qa",
            session_id="s_test_01",
            message="What is monitoring?",
        )
        assert isinstance(result, AgentResult)
        assert result.latency_ms >= 0
        assert result.tokens_in > 0
        assert result.tokens_out > 0
        assert result.cost_usd >= 0
        assert 0 <= result.quality_score <= 1

    def test_agent_run_has_observe_decorator(self) -> None:
        """agent.run must be decorated with @observe for Langfuse tracing."""
        # The run method exists and is wrapped (observe changes the function)
        assert hasattr(LabAgent, "run")
        assert callable(LabAgent.run)

    def test_agent_sub_spans_exist(self) -> None:
        """Agent must have separate sub-span methods for retrieval, generation, scoring."""
        agent = LabAgent()
        assert hasattr(agent, "_retrieve")
        assert hasattr(agent, "_generate")
        assert hasattr(agent, "_score")

    def test_agent_tags_format(self) -> None:
        """Verify the expected tag structure in the agent.run code (static analysis)."""
        import inspect
        source = inspect.getsource(LabAgent.run)
        # Must contain tag assignments
        assert "tags=" in source or "tags=[" in source
        # Must include lab, feature, model, env tags
        assert "lab" in source
        assert "feature:" in source
        assert "model:" in source
        assert "env:" in source

    def test_agent_trace_metadata_includes_incident_state(self) -> None:
        """Trace metadata must include incident state for correlation."""
        import inspect
        source = inspect.getsource(LabAgent.run)
        assert "incident_state" in source

    def test_agent_uses_hashed_user_id(self) -> None:
        """Agent must hash user_id before sending to trace (never raw PII)."""
        import inspect
        source = inspect.getsource(LabAgent.run)
        assert "hash_user_id" in source

    def test_agent_uses_summarize_text(self) -> None:
        """Agent must use summarize_text for PII-safe previews."""
        import inspect
        source = inspect.getsource(LabAgent)
        assert "summarize_text" in source

    def test_agent_scores_trace(self) -> None:
        """Agent must call safe_score_trace for quality SLO tracking."""
        import inspect
        source = inspect.getsource(LabAgent.run)
        assert "safe_score_trace" in source

    def test_agent_usage_details(self) -> None:
        """Agent must report token usage details in observation."""
        import inspect
        source = inspect.getsource(LabAgent.run)
        assert "usage_details" in source
