# Alert Rules and Runbooks

This file contains on-call runbooks for all alert rules defined in `config/alert_rules.yaml`.
**Debug flow**: Metrics → Traces → Logs (see bottom of this document).

---

## 1. High Latency P95

- **Alert name**: `high_latency_p95`
- **Severity**: P2
- **Trigger**: `latency_p95_ms > 3000 for 15m`
- **SLO impact**: Latency SLO (objective: 2000ms, target: 99%) is at risk of breach.

**User impact**: Tail users (5%) experience >3s response times. May cause frontend timeouts.

**First checks**:
1. Open Langfuse → filter traces by last 30m → sort by `latency_ms` descending.
2. Compare `agent.retrieval` span vs `agent.generation` span: which step is the bottleneck?
3. Check incident toggles: `GET /health` → confirm `rag_slow` is `false`. If true → that is the root cause.
4. Check `/metrics` → inspect `latency_p95_ms` trend vs recent baseline.

**Mitigation**:
- If `rag_slow` is active: `POST /incidents/rag_slow/disable`
- If RAG is legitimately slow: truncate input documents in `mock_rag.py` or add a timeout.
- If LLM generation is slow: reduce prompt size, switch to a faster model tier.
- As a short-term relief: lower `max_len` in `summarize_text` to reduce prompt tokens.

---

## 2. High Error Rate

- **Alert name**: `high_error_rate`
- **Severity**: P1
- **Trigger**: `error_rate_pct > 5 for 5m`
- **SLO impact**: Error rate SLO (objective: 1%, target: 99.5%) is in breach.

**User impact**: More than 1-in-20 users receive a 500 error. Direct revenue/experience impact.

**First checks**:
1. Check app logs: `grep '"level":"error"' data/logs.jsonl | tail -20` — group by `error_type`.
2. Open Langfuse → filter failed traces → inspect which span threw the exception.
3. Check incident toggles: `GET /health` → confirm `tool_fail` is `false`.
4. Check recent deployments or config changes.

**Mitigation**:
- If `tool_fail` is active: `POST /incidents/tool_fail/disable`
- If a specific error_type dominates: isolate and add exception handling.
- Rollback latest deploy if the error coincides with a release.
- Retry failed requests with exponential backoff as a temporary workaround.

---

## 3. Cost Budget Spike

- **Alert name**: `cost_budget_spike`
- **Severity**: P2
- **Trigger**: `hourly_cost_usd > 0.10 for 15m`
- **SLO impact**: Daily cost SLO (objective: $1.00/day) is at risk of breach.

**User impact**: No direct user impact, but financial burn rate is unsustainable.

**First checks**:
1. Check incident toggles: `GET /health` → confirm `cost_spike` is `false`. If active → root cause found.
2. Open Langfuse → group traces by `feature` and `model` → identify which flow drives high token usage.
3. Check `/metrics` → compare `tokens_in` and `tokens_out` vs baseline.
4. Inspect trace metadata `doc_count` — unusually large retrieval sets bloat prompts.

**Mitigation**:
- If `cost_spike` is active: `POST /incidents/cost_spike/disable`
- Shorten system prompt or reduce retrieved document count.
- Route easy/short queries to a cheaper model tier.
- Add per-user rate limiting to prevent runaway usage.

---

## 4. Quality Degradation

- **Alert name**: `quality_degradation`
- **Severity**: P3
- **Trigger**: `quality_score_avg < 0.60 for 30m`
- **SLO impact**: Quality SLO (objective: 0.70 avg, target: 95%) may breach.

**User impact**: Responses are less relevant or shorter than expected. Indirect satisfaction impact.

**First checks**:
1. Open Langfuse → filter traces with `quality_score < 0.60` → inspect `query_preview` and `doc_count`.
2. Check if `doc_count = 0` — empty retrieval causes score penalty.
3. Check logs: look for `[REDACTED` in answer previews — a PII-redacted answer lowers score by design.
4. Check if a new query type or feature is being called that the heuristic doesn't handle well.

**Mitigation**:
- If RAG retrieval is returning empty results: check mock data in `data/` directory.
- If quality drop is feature-specific: tune the heuristic in `LabAgent._heuristic_quality`.
- Consider adding a fallback answer template for zero-retrieval cases.

---

## Debug Flow: Metrics → Traces → Logs

This is the standard incident investigation flow for this service:

```
1. METRICS (/metrics endpoint or alert firing)
   ↓ Identify: which SLI is degraded? (latency / errors / cost / quality)
   ↓ Narrow time window of the degradation

2. TRACES (Langfuse)
   ↓ Filter by time window and relevant tags (feature, env, model)
   ↓ Find slow/failed traces
   ↓ Drill into sub-spans: agent.retrieval → agent.generation → agent.scoring
   ↓ Identify WHICH step is responsible (latency attribution)
   ↓ Read trace metadata: incident_state, doc_count, cost_usd

3. LOGS (data/logs.jsonl)
   ↓ Filter by correlation_id from the trace
   ↓ Read full request context: user_id_hash, session_id, feature, model
   ↓ Inspect payload fields: message_preview, error_type, detail
   ↓ Cross-reference with data/audit.jsonl for request timeline
```

**Key**: every log line and every trace share the same `correlation_id` (format: `req-<8hex>`),
making it trivial to jump from a Langfuse trace to the exact log lines for that request.
