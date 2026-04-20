from __future__ import annotations

import os
import time
from dataclasses import dataclass

from . import incidents, metrics
from .mock_llm import FakeLLM
from .mock_rag import retrieve
from .pii import hash_user_id, summarize_text
from .tracing import (
    instrument,
    observe,
    safe_score_trace,
    safe_update_observation,
    safe_update_trace,
)


@dataclass
class AgentResult:
    answer: str
    latency_ms: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    quality_score: float


class LabAgent:
    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        self.model = model
        self.llm = FakeLLM(model=model)

    # ------------------------------------------------------------------
    # Main pipeline — top-level Langfuse trace
    # ------------------------------------------------------------------

    @observe(name="agent.run")
    def run(self, user_id: str, feature: str, session_id: str, message: str) -> AgentResult:
        started = time.perf_counter()

        # Sub-span: retrieval
        docs = self._retrieve(message)

        # Sub-span: generation
        prompt = f"Feature={feature}\nDocs={docs}\nQuestion={message}"
        response = self._generate(prompt)

        # Sub-span: scoring
        quality_score = self._score(message, response.text, docs)

        latency_ms = int((time.perf_counter() - started) * 1000)
        cost_usd = self._estimate_cost(response.usage.input_tokens, response.usage.output_tokens)

        # --------------- Trace-level metadata ---------------
        safe_update_trace(
            # Hashed user ID — never raw
            user_id=hash_user_id(user_id),
            session_id=session_id,
            # Tags: lab identifies this is coursework; the rest support filtering in Langfuse
            tags=[
                "lab",
                f"feature:{feature}",
                f"model:{self.model}",
                f"env:{os.getenv('APP_ENV', 'dev')}",
            ],
            metadata={
                "env": os.getenv("APP_ENV", "dev"),
                "feature": feature,
                "model": self.model,
                # Expose active incident toggles for incident-response correlation
                "incident_state": incidents.status(),
            },
        )

        # --------------- Observation-level metadata ---------------
        safe_update_observation(
            metadata={
                "doc_count": len(docs),
                "query_preview": summarize_text(message),   # PII scrubbed
                "latency_ms": latency_ms,
                "cost_usd": cost_usd,
                "quality_score": quality_score,
            },
            usage_details={
                "input": response.usage.input_tokens,
                "output": response.usage.output_tokens,
            },
        )

        # Quality score attached to trace for SLO tracking in Langfuse
        safe_score_trace(
            name="quality_score",
            value=quality_score,
            comment=f"heuristic quality for feature={feature}",
        )

        metrics.record_request(
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            quality_score=quality_score,
        )

        return AgentResult(
            answer=response.text,
            latency_ms=latency_ms,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            cost_usd=cost_usd,
            quality_score=quality_score,
        )

    # ------------------------------------------------------------------
    # Sub-span: Retrieval  (auto-instrumented observation)
    # ------------------------------------------------------------------

    @observe(name="agent.retrieval")
    def _retrieve(self, message: str) -> list[str]:
        """RAG retrieval step — separate span for latency attribution."""
        docs = retrieve(message)
        safe_update_observation(
            metadata={
                "step": "retrieval",
                "doc_count": len(docs),
                "query_preview": summarize_text(message),
            },
        )
        return docs

    # ------------------------------------------------------------------
    # Sub-span: Generation  (auto-instrumented observation)
    # ------------------------------------------------------------------

    @observe(name="agent.generation")
    def _generate(self, prompt: str) -> object:
        """LLM generation step — separate span to isolate model latency."""
        response = self.llm.generate(prompt)
        safe_update_observation(
            metadata={
                "step": "generation",
                "model": self.model,
                "prompt_length": len(prompt),
            },
            usage_details={
                "input": response.usage.input_tokens,
                "output": response.usage.output_tokens,
            },
        )
        return response

    # ------------------------------------------------------------------
    # Sub-span: Scoring  (auto-instrumented observation)
    # ------------------------------------------------------------------

    @observe(name="agent.scoring")
    def _score(self, question: str, answer: str, docs: list[str]) -> float:
        """Heuristic quality scoring — separate span for debugging quality regressions."""
        score = self._heuristic_quality(question, answer, docs)
        safe_update_observation(
            metadata={
                "step": "scoring",
                "quality_score": score,
            },
        )
        return score

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _estimate_cost(self, tokens_in: int, tokens_out: int) -> float:
        input_cost = (tokens_in / 1_000_000) * 3
        output_cost = (tokens_out / 1_000_000) * 15
        return round(input_cost + output_cost, 6)

    def _heuristic_quality(self, question: str, answer: str, docs: list[str]) -> float:
        score = 0.5
        if docs:
            score += 0.2
        if len(answer) > 40:
            score += 0.1
        if question.lower().split()[0:1] and any(
            token in answer.lower() for token in question.lower().split()[:3]
        ):
            score += 0.1
        if "[REDACTED" in answer:
            score -= 0.2
        return round(max(0.0, min(1.0, score)), 2)
