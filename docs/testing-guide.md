# Day 13 — Hướng dẫn Test & Giải thích Workflow

> **Tác giả**: Vo Thanh Danh (Member A + B + C)
> **Ngày**: 20/04/2026

---

## Mục lục

1. [Lệnh test từng phần](#1-lệnh-test-từng-phần)
2. [Giải thích kết quả — Thế nào là đạt?](#2-giải-thích-kết-quả--thế-nào-là-đạt)
3. [Workflow — Đã làm gì?](#3-workflow--đã-làm-gì)
4. [Tổng kết — Hôm nay học được gì?](#4-tổng-kết--hôm-nay-học-được-gì)

---

## 1. Lệnh test từng phần

### 1.1 Cài đặt môi trường (chạy 1 lần)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

---

### 1.2 Member A: Logging + PII (35 tests)

```bash
.venv\Scripts\python -m pytest tests/test_member_a_logging_pii.py -v
```

**Kết quả mong đợi:**
```
tests/test_member_a_logging_pii.py::TestScrubText::test_email_redacted PASSED
tests/test_member_a_logging_pii.py::TestScrubText::test_phone_vn_mobile PASSED
tests/test_member_a_logging_pii.py::TestScrubText::test_credit_card_visa PASSED
tests/test_member_a_logging_pii.py::TestScrubText::test_cccd_12_digits PASSED
tests/test_member_a_logging_pii.py::TestScrubText::test_passport_vn PASSED
tests/test_member_a_logging_pii.py::TestScrubText::test_address_vn PASSED
... (tất cả PASSED)
============================== 35 passed ==============================
```

**Đạt khi:** Tất cả 35 test đều `PASSED`. Nghĩa là:
- ✅ Mọi loại PII (email, SĐT, CCCD, thẻ tín dụng, hộ chiếu, địa chỉ VN) đều bị thay bằng `[REDACTED_xxx]`
- ✅ Chuỗi JSON log có đầy đủ 5 trường bắt buộc: `ts`, `level`, `service`, `event`, `correlation_id`
- ✅ Correlation ID có format đúng `req-<8 ký tự hex>` và chặn được injection
- ✅ Audit logger ghi file riêng, có scrub PII

**Không đạt khi:** Có bất kỳ test nào `FAILED` — nghĩa là PII bị rò rỉ hoặc cấu trúc log sai.

---

### 1.3 Member B: Tracing + Tags (18 tests)

```bash
.venv\Scripts\python -m pytest tests/test_member_b_tracing_tags.py -v
```

**Kết quả mong đợi:**
```
tests/test_member_b_tracing_tags.py::TestObserveDecorator::test_observe_is_callable PASSED
tests/test_member_b_tracing_tags.py::TestSafeHelpers::test_safe_update_trace_no_crash PASSED
tests/test_member_b_tracing_tags.py::TestInstrumentDecorator::test_instrument_wraps_function PASSED
tests/test_member_b_tracing_tags.py::TestAgentTracingIntegration::test_agent_tags_format PASSED
... (tất cả PASSED)
============================== 18 passed ==============================
```

**Đạt khi:** Tất cả 18 test đều `PASSED`. Nghĩa là:
- ✅ `@observe` decorator hoạt động, không làm hỏng logic gốc
- ✅ Safe helpers (`safe_update_trace`, `safe_score_trace`...) không bao giờ crash ứng dụng
- ✅ Agent pipeline có đủ sub-spans (retrieval → generation → scoring)
- ✅ Tags đúng format: `["lab", "feature:qa", "model:claude-sonnet-4-5", "env:dev"]`
- ✅ User ID luôn được hash trước khi gửi lên trace
- ✅ Auto-instrumentation decorator `@instrument` hoạt động (bonus)

**Không đạt khi:** `test_agent_tags_format` fail = thiếu tags → mất điểm tracing.

---

### 1.4 Member C: SLO + Alerts (31 tests)

```bash
.venv\Scripts\python -m pytest tests/test_member_c_slo_alerts.py -v
```

**Kết quả mong đợi:**
```
tests/test_member_c_slo_alerts.py::TestSLOConfig::test_slo_has_at_least_4_slis PASSED
tests/test_member_c_slo_alerts.py::TestAlertRules::test_at_least_3_alert_rules PASSED
tests/test_member_c_slo_alerts.py::TestAlertRules::test_all_alerts_have_runbook_link PASSED
tests/test_member_c_slo_alerts.py::TestRunbook::test_has_debug_flow_section PASSED
tests/test_member_c_slo_alerts.py::TestMetrics::test_snapshot_matches_dashboard_panels PASSED
... (tất cả PASSED)
============================== 31 passed ==============================
```

**Đạt khi:** Tất cả 31 test đều `PASSED`. Nghĩa là:
- ✅ SLO config có ≥ 4 SLIs với objective, target, breach budget rõ ràng
- ✅ Alert rules ≥ 3 (thực tế có 4), mỗi alert có severity, condition, threshold, window
- ✅ Mỗi alert đều có runbook link trỏ tới section thực sự trong `docs/alerts.md`
- ✅ Runbook có đủ: User impact, First checks, Mitigation, Debug flow
- ✅ Metrics endpoint cung cấp data cho đủ 6 dashboard panels
- ✅ Cost formula tính đúng ($3/M input + $15/M output)

**Không đạt khi:** `test_at_least_3_alert_rules` fail = thiếu alert rules → mất 10đ.

---

### 1.5 Integration E2E (12 tests)

```bash
.venv\Scripts\python -m pytest tests/test_integration_e2e.py -v
```

**Kết quả mong đợi:**
```
tests/test_integration_e2e.py::TestEndToEnd::test_health_endpoint PASSED
tests/test_integration_e2e.py::TestEndToEnd::test_chat_returns_correlation_id PASSED
tests/test_integration_e2e.py::TestEndToEnd::test_pii_not_in_logs PASSED
tests/test_integration_e2e.py::TestEndToEnd::test_audit_log_written PASSED
tests/test_integration_e2e.py::TestEndToEnd::test_incident_toggle PASSED
... (tất cả PASSED)
============================== 12 passed ==============================
```

**Đạt khi:** Tất cả 12 test đều `PASSED`. Đây là test chạy app thật (FastAPI TestClient), kiểm tra toàn bộ pipeline từ đầu đến cuối.

---

### 1.6 Validate Logs (chạy thủ công)

```bash
# Terminal 1: Start server
.venv\Scripts\python -m uvicorn app.main:app --port 8000

# Terminal 2: Gửi 15 requests
.venv\Scripts\python scripts/send_test_requests.py

# Terminal 2: Chạy validate
.venv\Scripts\python scripts/validate_logs.py
```

**Kết quả mong đợi:**
```
--- Lab Verification Results ---
Total log records analyzed: 31
Records with missing required fields: 0
Records with missing enrichment (context): 0
Unique correlation IDs found: 15
Potential PII leaks detected: 0

--- Grading Scorecard (Estimates) ---
+ [PASSED] Basic JSON schema
+ [PASSED] Correlation ID propagation
+ [PASSED] Log enrichment
+ [PASSED] PII scrubbing

Estimated Score: 100/100
```

**Đạt khi:** Score ≥ 80/100 (theo rubric). Lý tưởng là 100/100.

---

### 1.7 Chạy TẤT CẢ cùng lúc

```bash
.venv\Scripts\python -m pytest tests/ -v
```

**Đạt khi:** `112 passed, 0 failed`

---

## 2. Giải thích kết quả — Thế nào là đạt?

### Bảng tổng hợp tiêu chí đạt

| Tiêu chí | Ngưỡng đạt | Kết quả thực tế |
|---|---|---|
| validate_logs.py score | ≥ 80/100 | **100/100** ✅ |
| Số traces trên Langfuse | ≥ 10 | **15 requests** (mỗi request = 1 trace) ✅ |
| PII leaks | = 0 | **0** ✅ |
| Alert rules | ≥ 3 | **4** ✅ |
| Dashboard panels | = 6 | **6** (từ /metrics endpoint) ✅ |
| TODO blocks completed | 100% | **100%** (không còn TODO nào) ✅ |

### Ý nghĩa từng test status

| Status | Ý nghĩa |
|---|---|
| `PASSED` ✅ | Test chạy đúng, tính năng hoạt động như mong đợi |
| `FAILED` ❌ | Có lỗi logic hoặc thiếu implementation — cần fix |
| `ERROR` ⚠️ | Code bị crash (import error, syntax error...) — cần fix trước |
| `SKIPPED` ⏭️ | Test bị bỏ qua (thường do điều kiện không thỏa) |

---

## 3. Workflow — Đã làm gì?

### Kiến trúc tổng thể

```
User Request ──→ FastAPI ──→ Middleware ──→ Agent Pipeline ──→ Response
                   │            │              │
                   │            │              ├── _retrieve() ──→ Mock RAG
                   │            │              ├── _generate() ──→ Mock LLM
                   │            │              └── _score()    ──→ Quality Heuristic
                   │            │
                   │            └── CorrelationIdMiddleware
                   │                 • Tạo req-<8hex> ID
                   │                 • Bind vào structlog contextvars
                   │                 • Set x-request-id header
                   │
                   ├── Logging Pipeline (structlog)
                   │    1. merge_contextvars     ← lấy correlation_id, env, user_id_hash
                   │    2. add_log_level         ← info/warning/error
                   │    3. TimeStamper           ← ISO 8601 UTC
                   │    4. add_service_name      ← "day13-observability-lab"
                   │    5. scrub_event           ← XÓA PII trước khi ghi
                   │    6. JsonlFileProcessor    ← ghi vào data/logs.jsonl
                   │    7. JSONRenderer          ← in ra stdout
                   │
                   ├── Tracing (Langfuse)
                   │    • @observe trên mỗi step
                   │    • Tags: lab, feature, model, env
                   │    • Metadata: incident_state, doc_count
                   │    • Score: quality_score per trace
                   │
                   ├── Metrics (in-memory)
                   │    • Latency P50/P95/P99
                   │    • Traffic count, Error breakdown
                   │    • Cost, Tokens, Quality avg
                   │
                   └── Audit Logger
                        • Ghi file riêng data/audit.jsonl
                        • PII-free (tất cả string đều scrub)
```

### Member A đã làm gì? (Logging + PII)

```
1. app/pii.py — Viết regex cho 6 loại PII Việt Nam:
   • Email, SĐT (+84/0xx), Thẻ tín dụng (Visa/MC/Amex/Discover)
   • CCCD/CMND (9/12 số), Hộ chiếu VN, Địa chỉ VN (phường/quận/huyện...)
   
2. app/logging_config.py — Thiết lập structlog pipeline:
   • scrub_event processor: chạy PII redaction TRƯỚC khi data ra stdout/file
   • JsonlFileProcessor: ghi mỗi log record vào JSONL file
   • AuditLogger (Bonus): ghi audit events ra file riêng, đảm bảo PII-free
   
3. app/middleware.py — Correlation ID:
   • Mỗi request được gán 1 ID unique: req-<8 ký tự hex>
   • ID được bind vào structlog → mọi log trong request đều có ID này
   • Hỗ trợ propagation: nếu client gửi x-request-id header → tái sử dụng
   • Chặn header injection (chỉ chấp nhận format req-<8hex>)

4. app/main.py — Enrichment:
   • bind_contextvars(user_id_hash, session_id, feature, model)
   • Mọi log call trong request scope đều tự động có các field này
```

### Member B đã làm gì? (Tracing + Tags)

```
1. app/tracing.py — Langfuse integration:
   • @observe decorator để tạo trace/span trên Langfuse
   • Safe helpers: safe_update_trace(), safe_score_trace() — KHÔNG BAO GIỜ crash app
   • Graceful fallback: nếu Langfuse SDK không cài → dùng no-op decorator
   • @instrument decorator factory (Bonus: auto-instrumentation)

2. app/agent.py — Pipeline với đầy đủ metadata:
   • @observe(name="agent.run") → trace chính
   • @observe(name="agent.retrieval") → sub-span RAG
   • @observe(name="agent.generation") → sub-span LLM
   • @observe(name="agent.scoring") → sub-span quality

3. Tags attached to every trace:
   • ["lab", "feature:qa", "model:claude-sonnet-4-5", "env:dev"]
   • → Cho phép filter/search trong Langfuse dashboard

4. Metadata trên trace:
   • env, feature, model, incident_state (biết incident nào đang ON)
   • usage_details: input/output tokens
   • quality_score: heuristic quality (0-1)
```

### Member C đã làm gì? (SLO + Alerts)

```
1. config/slo.yaml — 4 Service Level Indicators:
   • latency_p95_ms: ≤ 2000ms, target 99%, budget 5h/28d
   • error_rate_pct: ≤ 1%, target 99.5%, budget 3.5h/28d
   • daily_cost_usd: ≤ $1.00/day, target 100% (luôn comply)
   • quality_score_avg: ≥ 0.70, target 95%, budget 30h/28d

2. config/alert_rules.yaml — 4 Alert Rules:
   • high_error_rate (P1): error > 5% trong 5 phút
   • high_latency_p95 (P2): P95 > 3000ms trong 15 phút
   • cost_budget_spike (P2): chi phí/giờ > $0.10 trong 15 phút
   • quality_degradation (P3): quality < 0.60 trong 30 phút
   • Mỗi alert có: severity, owner, labels, annotations, runbook link

3. docs/alerts.md — Runbook chi tiết:
   • Mỗi alert có: User impact, First checks, Mitigation steps
   • Debug flow chuẩn: Metrics → Traces → Logs
   • Hướng dẫn cross-reference qua correlation_id

4. app/metrics.py — In-memory metrics:
   • Thu thập: latency, cost, tokens, errors, quality
   • Tính: P50, P95, P99 percentile
   • Expose qua GET /metrics endpoint → data cho 6 dashboard panels
```

---

## 4. Tổng kết — Hôm nay học được gì?

### 4.1 Ba trụ cột của Observability

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   METRICS   │    │   TRACES    │    │    LOGS     │
│             │    │             │    │             │
│ "CÁI GÌ    │    │ "Ở ĐÂU      │    │ "TẠI SAO    │
│  bị hỏng?"  │    │  bị chậm?"   │    │  nó xảy ra?"│
│             │    │             │    │             │
│ • Latency   │    │ • Spans     │    │ • Structured│
│ • Error rate│    │ • Waterfall │    │ • JSON      │
│ • Cost      │    │ • Tags      │    │ • Context   │
│ • Quality   │    │ • Metadata  │    │ • PII-free  │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘
       │                  │                  │
       └──────────────────┼──────────────────┘
                          │
                   correlation_id
              (kết nối cả 3 pillars lại)
```

### 4.2 Các khái niệm quan trọng

| Khái niệm | Giải thích | Ví dụ trong bài |
|---|---|---|
| **Structured Logging** | Log bằng JSON thay vì text → dễ query, parse, filter | structlog viết JSON vào `data/logs.jsonl` |
| **Correlation ID** | 1 ID duy nhất theo dõi request xuyên suốt hệ thống | `req-a1b2c3d4` xuất hiện trong log, trace, response header |
| **PII Scrubbing** | Xóa/che dữ liệu cá nhân trước khi log | Email → `[REDACTED_EMAIL]`, SĐT → `[REDACTED_PHONE_VN]` |
| **Distributed Tracing** | Theo dõi từng bước (span) trong pipeline | `agent.run` → `agent.retrieval` → `agent.generation` → `agent.scoring` |
| **SLO/SLI** | Service Level Objective/Indicator — cam kết chất lượng dịch vụ | "P95 latency ≤ 2000ms cho 99% thời gian trong 28 ngày" |
| **Alert Rules** | Điều kiện tự động cảnh báo khi SLO bị vi phạm | "Nếu error rate > 5% trong 5 phút → P1 alert" |
| **Runbook** | Hướng dẫn xử lý khi alert kích hoạt | "Bước 1: Check Langfuse, Bước 2: Check incident toggles..." |
| **Breach Budget** | Thời gian cho phép vi phạm SLO trong 1 window | "5h/28 ngày = ~0.5% thời gian được phép latency > 2000ms" |

### 4.3 Debug Flow chuẩn công nghiệp

```
1. ALERT kích hoạt (ví dụ: high_latency_p95)
   │
   ▼
2. METRICS — Nhìn dashboard → xác định SLI nào bị ảnh hưởng
   │         → Thu hẹp khoảng thời gian sự cố
   ▼
3. TRACES — Vào Langfuse/Jaeger → filter theo time window
   │         → Tìm trace chậm nhất → Xem waterfall
   │         → Xác định BƯỚC NÀO gây chậm (retrieval? generation?)
   ▼
4. LOGS — Lấy correlation_id từ trace → grep trong logs.jsonl
   │       → Đọc full context: user, session, feature, error_type
   │       → Xác định ROOT CAUSE
   ▼
5. FIX — Áp dụng mitigation → verify bằng metrics
```

### 4.4 Tại sao những thứ này quan trọng?

**Không có Observability:**
- App crash → không biết tại sao
- User phàn nàn chậm → không biết chậm ở đâu
- Bị hack lộ PII → không biết data nào bị lộ
- Chi phí LLM tăng vọt → không phát hiện

**Có Observability:**
- Alert tự động khi có vấn đề (trước cả khi user phàn nàn)
- Trace cho thấy chính xác step nào chậm (retrieval 2.5s vs generation 150ms)
- Logs filtered by correlation_id → đọc toàn bộ context của 1 request
- PII scrubbed → an toàn pháp lý, tuân thủ GDPR/PDPA
- Cost tracking → phát hiện sớm chi phí bất thường

### 4.5 Kỹ năng thực tế đã practice

1. **Viết regex PII matching** — skill phổ biến trong data privacy
2. **Cấu hình structlog pipeline** — dùng processors pattern (giống middleware)
3. **Thiết kế SLO/SLI** — kỹ năng Site Reliability Engineering (SRE)
4. **Viết alert rules** — symptom-based vs cause-based alerting
5. **Viết runbook** — tài liệu operational cho on-call team
6. **Integration testing** — kiểm thử end-to-end với FastAPI TestClient
7. **Graceful degradation** — tracing không bao giờ crash hot path

---

## Phụ lục: File map

```
app/
  pii.py              ← Member A: regex PII, scrub_text(), hash_user_id()
  logging_config.py    ← Member A: structlog pipeline, audit logger
  middleware.py        ← Member A: correlation ID middleware
  main.py              ← Member A: log enrichment (bind_contextvars)
  tracing.py           ← Member B: @observe, safe helpers, @instrument
  agent.py             ← Member B: trace tags, metadata, sub-spans
  metrics.py           ← Member C: in-memory metrics, percentile, snapshot

config/
  slo.yaml             ← Member C: 4 SLIs with objectives & budgets
  alert_rules.yaml     ← Member C: 4 alert rules with runbook links
  logging_schema.json   ← Member A: expected log JSON schema

docs/
  alerts.md            ← Member C: runbook for all 4 alerts
  testing-guide.md     ← File này!

tests/
  test_member_a_logging_pii.py  ← 35 tests cho Logging + PII
  test_member_b_tracing_tags.py ← 18 tests cho Tracing + Tags
  test_member_c_slo_alerts.py   ← 31 tests cho SLO + Alerts
  test_integration_e2e.py       ← 12 tests end-to-end
  test_pii.py                   ← 1 test gốc (email)
  test_metrics.py               ← 1 test gốc (percentile)
```
