# Day 13 Observability Lab Report

> **Instruction**: Fill in all sections below. This report is designed to be parsed by an automated grading assistant. Ensure all tags (e.g., `[GROUP_NAME]`) are preserved.

## 1. Team Metadata
- [GROUP_NAME]: 2A202600502
- [REPO_URL]: <!-- TODO: dán URL repo GitHub/GitLab vào đây sau khi push -->
- [MEMBERS]:
  - Member A+B+C: Võ Thành Danh | Role: Logging & PII + Tracing & Enrichment + SLO & Alerts
  - Member D+E: Trương Hậu Minh Kiệt | Role: Load Test & Dashboard & Demo & Report

---

## 2. Group Performance (Auto-Verified)
- [VALIDATE_LOGS_FINAL_SCORE]: <!-- TODO: điền số từ output của validate_logs.py, ví dụ: 100/100 -->/100
- [TOTAL_TRACES_COUNT]: <!-- TODO: điền số traces thấy trên Langfuse sau khi chạy send_test_requests.py -->
- [PII_LEAKS_FOUND]: <!-- TODO: điền số từ dòng "Potential PII leaks detected" trong validate_logs.py -->

---

## 3. Technical Evidence (Group)

### 3.1 Logging & Tracing
- [EVIDENCE_CORRELATION_ID_SCREENSHOT]: <!-- TODO: chụp màn hình file data/logs.jsonl, dán path ảnh vào đây, ví dụ: docs/screenshots/correlation_id.png -->
- [EVIDENCE_PII_REDACTION_SCREENSHOT]: <!-- TODO: chụp dòng log có [REDACTED_EMAIL] hoặc [REDACTED_PHONE_VN] -->
- [EVIDENCE_TRACE_WATERFALL_SCREENSHOT]: <!-- TODO: chụp màn hình Langfuse trace waterfall -->
- [TRACE_WATERFALL_EXPLANATION]: <!-- TODO: sau khi xem trace trên Langfuse, giải thích 1 span thú vị — ví dụ: "span agent.retrieval mất 850ms do rag_slow=true, chiếm 90% tổng latency" -->

### 3.2 Dashboard & SLOs
- [DASHBOARD_6_PANELS_SCREENSHOT]: <!-- TODO: chụp màn hình khi dashboard.py đang chạy (hoặc /metrics response) -->
- [SLO_TABLE]:
| SLI | Target | Window | Current Value |
|---|---:|---|---:|
| Latency P95 | < 2000ms | 28d | <!-- TODO: lấy latency_p95 từ GET /metrics --> |
| Error Rate | < 1% | 28d | <!-- TODO: tính từ error_breakdown / traffic * 100 --> |
| Cost Budget | < $1.00/day | 1d | <!-- TODO: lấy total_cost_usd từ GET /metrics --> |
| Quality Score | > 0.70 avg | 28d | <!-- TODO: lấy quality_avg từ GET /metrics --> |

### 3.3 Alerts & Runbook
- [ALERT_RULES_SCREENSHOT]: <!-- TODO: chụp nội dung config/alert_rules.yaml -->
- [SAMPLE_RUNBOOK_LINK]: docs/alerts.md#1-high-latency-p95

---

## 4. Incident Response (Group)
- [SCENARIO_NAME]: rag_slow
- [SYMPTOMS_OBSERVED]: <!-- TODO: sau khi inject rag_slow, ghi lại latency_p95 tăng lên bao nhiêu ms. Ví dụ: "latency_p95 tăng từ ~300ms lên ~2500ms, dashboard Panel 1 chuyển đỏ" -->
- [ROOT_CAUSE_PROVED_BY]: <!-- TODO: dán correlation_id của 1 request chậm, ví dụ: "req-a1b2c3d4 — span agent.retrieval chiếm 2300ms/2500ms tổng latency" -->
- [FIX_ACTION]: POST /incidents/rag_slow/disable — tắt incident toggle, latency trở về bình thường
- [PREVENTIVE_MEASURE]: Thêm timeout cho RAG retrieval trong mock_rag.py; alert high_latency_p95 (P2, 15m window) sẽ cảnh báo trước khi SLO bị vi phạm

---

## 5. Individual Contributions & Evidence

### [MEMBER_A+B+C_NAME]: Võ Thành Danh
- [TASKS_COMPLETED]:
  - Viết PII scrubber (regex cho email, SĐT VN, CCCD, thẻ tín dụng, hộ chiếu, địa chỉ VN) — app/pii.py
  - Cấu hình structlog pipeline với PII-safe processors + audit logger — app/logging_config.py
  - Implement CorrelationIdMiddleware (req-<8hex>, header injection prevention) — app/middleware.py
  - Implement Langfuse @observe decorator + safe helpers (không crash app) — app/tracing.py
  - Gắn sub-spans (agent.retrieval, agent.generation, agent.scoring) và tags — app/agent.py
  - Viết 4 SLIs + 4 alert rules với runbook links — config/slo.yaml, config/alert_rules.yaml
  - Viết in-memory metrics (percentile P50/P95/P99) + /metrics endpoint — app/metrics.py
  - Viết 112 tests (35 + 18 + 31 + 12 + 16) — tests/
- [EVIDENCE_LINK]: <!-- TODO: dán link commit 1351b0c trên GitHub, ví dụ: https://github.com/.../commit/1351b0c -->

### [MEMBER_D+E_NAME]: Trương Hậu Minh Kiệt
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
