# Day 13 Observability Lab Report

> **Instruction**: Fill in all sections below. This report is designed to be parsed by an automated grading assistant. Ensure all tags (e.g., `[GROUP_NAME]`) are preserved.

## 1. Team Metadata
- [GROUP_NAME]: . 18
- [REPO_URL]: [ (https://github.com/DCSlucifer/2A202600503-VoThanhDanh-Day13.git) ]
- [MEMBERS]:
  - Member A+B+C: Võ Thành Danh | Role: Logging & PII + Tracing & Enrichment + SLO & Alerts
  - Member D+E+F: Trương Hầu Minh Kiệt | Role: Load Test & Dashboard & Demo & Report

---

## 2. Group Performance (Auto-Verified)
- [VALIDATE_LOGS_FINAL_SCORE]: . 100/100
- [TOTAL_TRACES_COUNT]: . 15
- [PII_LEAKS_FOUND]: . 0

---


### 3.1 Logging & Tracing
- [EVIDENCE_CORRELATION_ID_SCREENSHOT]: ![ correlation_id](evidence/correlation_id.png)
- [EVIDENCE_PII_REDACTION_SCREENSHOT]: ![ EVIDENCE](evidence/screenshot_logs2.png)
- [EVIDENCE_TRACE_WATERFALL_SCREENSHOT]: ![Langfuse Trace Waterfall](evidence/langfuse_trace_waterfall.png)
- [TRACE_WATERFALL_EXPLANATION]: Trace waterfall hiển thị pipeline `agent.run` (0.16s) → `agent.retrieval` (0.00s) → `agent.generation` (0.15s). Mỗi span ghi input/output, metadata (user_id, feature, session_id), và metrics (tokens_in=28, tokens_out=131, cost_usd=$0.002049, quality_score=0.9). 60 spans tổng (15 traces × 4 spans/trace). Langfuse project: Day13-Lab / observability-lab.

### 3.2 Dashboard & SLOs
- [DASHBOARD_6_PANELS_SCREENSHOT]: ![Metrics endpoint](evidence/metrics_dashboard.png)
- [SLO_TABLE]:

| SLI | Objective | Target | Window | Current Value |
|---|---|---:|---|---:|
| Latency P95 | ≤ 2000ms | 99.0% | 28d | 150ms ✅ |
| Error Rate | ≤ 2% | 99.5% | 28d | 0% ✅ |
| Daily Cost | ≤ $1.00/day | 100% | 1d | $0.0647 ✅ |
| Quality Score Avg | ≥ 0.70 | 95.0% | 28d | 0.860 ✅ |

### 3.3 Alerts & Runbook
- [ALERT_RULES_SCREENSHOT]: ![Alert Rules](evidence/alert_rules.png)
- [SAMPLE_RUNBOOK_LINK]: - docs/alerts.md#1-high-latency-p95

---

## 4. Incident Response (Group)
- [SCENARIO_NAME]: rag_slow
- [SYMPTOMS_OBSERVED]: Avg latency tăng từ ~158ms lên ~2658ms (tăng 16.8×) sau khi bật rag_slow. Dashboard Panel 1 (Latency P95) chuyển đỏ, vượt ngưỡng SLO 2000ms.
- [ROOT_CAUSE_PROVED_BY]: req-999329c2 — span `agent.retrieval` chiếm ~2500ms/2658ms tổng latency do `rag_slow=True` trong incident_state metadata. Xác nhận qua Langfuse trace waterfall: `agent.generation` vẫn bình thường (~150ms), chứng minh bottleneck nằm ở tầng RAG retrieval, không phải LLM.
- [FIX_ACTION]: POST /incidents/rag_slow/disable — tắt incident toggle, latency trở về bình thường
- [PREVENTIVE_MEASURE]: Thêm timeout cho RAG retrieval trong mock_rag.py; alert high_latency_p95 (P2, 15m window) sẽ cảnh báo trước khi SLO bị vi phạm. Technical Evidence (Group)


---

## 5. Individual Contributions & Evidence


### Võ Thành Danh — Member A: Logging & PII

- [TASKS_COMPLETED]:
  1. **PII Scrubbing module** (`app/pii.py`): Viết 6 regex patterns cho PII Việt Nam (email, SĐT +84/0xx, thẻ tín dụng Visa/MC/Amex/Discover, CCCD 9/12 số, hộ chiếu VN, địa chỉ VN). Hàm `scrub_text()` replace tất cả PII bằng `[REDACTED_<TYPE>]`. Hàm `scrub_dict()` xử lý recursive cho nested dict/list. Hàm `hash_user_id()` sử dụng SHA-256 truncate 12 ký tự để log user ID an toàn.
  2. **Structlog pipeline** (`app/logging_config.py`): Cấu hình 7-stage processor chain: `merge_contextvars → add_log_level → TimeStamper → add_service_name → scrub_event → JsonlFileProcessor → JSONRenderer`. Processor `scrub_event` chạy trước serialization, đảm bảo không có PII nào tới log file hay stdout.
  3. **Correlation ID middleware** (`app/middleware.py`): `CorrelationIdMiddleware` tạo `req-<8hex>` unique cho mỗi request, bind vào structlog contextvars, set response headers `x-request-id` và `x-response-time-ms`. Chặn header injection bằng validation format.
  4. **Log enrichment** (`app/main.py`): Sử dụng `bind_contextvars()` để thêm `user_id_hash`, `session_id`, `feature`, `model` vào mỗi log call trong request scope.
  5. **Audit Logger** (Bonus +2đ) (`app/logging_config.py`): Class `AuditLogger` ghi audit events ra file riêng `data/audit.jsonl`. Tất cả string values đều được scrub PII trước khi ghi. Output format: `{"ts": "...", "audit": true, "event": "...", ...}`.
  6. **Tests**: 35 unit tests trong `tests/test_member_a_logging_pii.py` cover toàn bộ PII patterns, structlog processors, correlation ID validation, audit logger.

- [EVIDENCE_LINK]: https://github.com/DCSlucifer/2A202600503-VoThanhDanh-Day13/commit/1351b0c

**Giải thích kỹ thuật:**
- Regex PII ordering: credit card chạy trước email vì credit card pattern cụ thể hơn, tránh double-redaction.
- `hash_user_id` dùng SHA-256 thay vì MD5 vì MD5 có collision vulnerabilities. Truncate 12 hex chars = 48 bits entropy, đủ để correlate mà không reversible.
- `_is_valid_correlation_id()` chỉ chấp nhận format `req-<8 ký tự hex>` để chặn header injection attacks.

### Võ Thành Danh — Member B: Tracing & Enrichment

- [TASKS_COMPLETED]:
  1. **Tracing module** (`app/tracing.py`): Tích hợp Langfuse với graceful fallback — nếu Langfuse SDK không available thì dùng no-op `@observe` decorator và `_DummyContext`, đảm bảo app không crash.
  2. **Safe helpers**: `safe_update_trace()`, `safe_update_observation()`, `safe_score_trace()` — tất cả wrap trong try/except pass, tracing errors không bao giờ ảnh hưởng hot path.
  3. **Agent trace tags** (`app/agent.py`): Mỗi trace gắn 4 tags: `["lab", "feature:{feature}", "model:{model}", "env:{env}"]` → cho phép filter/search trong Langfuse dashboard.
  4. **Trace metadata**: `env`, `feature`, `model`, `incident_state` (biết incident toggle nào đang ON tại thời điểm trace).
  5. **Sub-spans**: 3 `@observe` spans riêng biệt cho `agent.retrieval`, `agent.generation`, `agent.scoring` → latency attribution chính xác.
  6. **Quality scoring**: `safe_score_trace(name="quality_score", value=...)` gắn score lên trace cho SLO tracking.
  7. **Auto-instrumentation** (Bonus +2đ) (`app/tracing.py`): Decorator factory `@instrument(name, **static_metadata)` wrap function trong named Langfuse observation span với metadata tự động.
  8. **Tests**: 18 unit tests trong `tests/test_member_b_tracing_tags.py` cover observe decorator, safe helpers, instrument decorator, agent trace integration.

- [EVIDENCE_LINK]: https://github.com/DCSlucifer/2A202600503-VoThanhDanh-Day13/commit/1351b0c

**Giải thích kỹ thuật:**
- Safe helpers dùng bare `except Exception: pass` — trong production thường log error, nhưng trong lab context đây là trade-off hợp lý vì tracing là auxiliary, không được phép break request flow.
- Tags format `feature:qa` cho phép Langfuse tag-based filtering, tương tự Datadog/Jaeger tag conventions.
- `usage_details` với `input` và `output` token counts cho phép Langfuse tính cost tự động.

### Võ Thành Danh — Member C: SLO & Alerts

- [TASKS_COMPLETED]:
  1. **SLO configuration** (`config/slo.yaml`): 4 SLIs hoàn chỉnh với objective, target %, breach budget hours, và alert link. Window 28 ngày. Mỗi SLI có description giải thích reasoning.
  2. **Alert rules** (`config/alert_rules.yaml`): 4 alert rules vượt yêu cầu tối thiểu (≥3). Mỗi alert có: name, severity (P1-P3), condition, metric, threshold, window, type (symptom/anomaly-based), owner, runbook link, labels (team + slo), annotations (summary + description).
  3. **Runbook** (`docs/alerts.md`): 124 dòng documentation với 4 sections (1 per alert). Mỗi section có: User impact, First checks (numbered steps), Mitigation actions. Cuối cùng có Debug Flow diagram: Metrics → Traces → Logs.
  4. **Metrics module** (`app/metrics.py`): In-memory aggregation: `record_request()` thu thập latency, cost, tokens, quality. `percentile()` tính P50/P95/P99. `snapshot()` trả về dict cho `/metrics` endpoint — cung cấp data cho đủ 6 dashboard panels.
  5. **Tests**: 31 unit tests trong `tests/test_member_c_slo_alerts.py` cover SLO config validation, alert rules completeness, runbook content quality, metrics calculations, cost formula.

- [EVIDENCE_LINK]: https://github.com/DCSlucifer/2A202600503-VoThanhDanh-Day13/commit/1351b0c

**Giải thích kỹ thuật:**
- P95 percentile calculation: `idx = max(0, min(len-1, round((p/100)*len + 0.5) - 1))` — nearest-rank method, phù hợp cho small sample sizes trong lab.
- Cost formula: `(tokens_in / 1M) × $3 + (tokens_out / 1M) × $15` — dựa trên Claude Sonnet pricing. Với 15 requests, avg cost = $0.0019/request, total = $0.0288 — rất thấp so với SLO $1/day.
- Alert thresholds set cao hơn SLO objectives (ví dụ: SLO latency = 2000ms, alert = 3000ms) — alert ở 1.5× SLO để có thời gian react trước khi SLO breach.
- Breach budget tính: (100% - target%) × 720h (28 days). Ví dụ: latency target 99% → budget = 1% × 720 = 7.2h, set 5h conservative.

### [MEMBER_D+E+F]: Trương Hầu Minh Kiệt
- [TASKS_COMPLETED]:
  - Viết scripts/send_test_requests.py — gửi 15 requests có PII, in bảng kết quả rõ ràng
  - Viết scripts/dashboard.py — terminal dashboard 6 panels với SLO threshold, auto-refresh 5s
  - Thực thi load test (15 requests, --concurrency 3) và xác nhận validate_logs.py đạt 100/100
  - Thực thi incident injection (rag_slow), quan sát latency tăng, phân tích root cause qua traces
  - Thu thập toàn bộ bằng chứng screenshots cho grading-evidence.md
  - Điền và hoàn thiện báo cáo blueprint-template.md
- [EVIDENCE_LINK]: <!-- TODO: dán link commit của scripts/send_test_requests.py và scripts/dashboard.py -->

---

## 6. Bonus Items (Optional)
- [BONUS_AUDIT_LOGS]: Audit logger ghi file riêng `data/audit.jsonl`, hoàn toàn PII-free. Mọi request/response/error/incident toggle đều được ghi. Implement trong `app/logging_config.py` bởi Võ Thành Danh.
- [BONUS_COST_OPTIMIZATION]: (Không thực hiện — lab mock không có real LLM cost để tối ưu)
- [BONUS_CUSTOM_METRIC]: Auto-instrumentation decorator `@instrument` trong `app/tracing.py` — wrap bất kỳ function nào thành Langfuse span chỉ bằng 1 dòng decorator.
