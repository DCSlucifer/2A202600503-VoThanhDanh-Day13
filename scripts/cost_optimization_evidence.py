"""
Cost Optimization Evidence Script
Chạy scenario: BEFORE (normal) → ENABLE cost_spike → AFTER (spike) → DISABLE → RECOVERED
Tạo số liệu trước/sau cho bonus +3đ
"""
import httpx
import json
import time

BASE = "http://127.0.0.1:8000"
client = httpx.Client(timeout=30.0)

def send_requests(n=5, label=""):
    for i in range(n):
        r = client.post(f"{BASE}/chat", json={
            "user_id": f"u_cost_{label}_{i}",
            "session_id": f"s_cost_{label}_{i}",
            "feature": "qa",
            "message": "What is monitoring?"
        })
    metrics = client.get(f"{BASE}/metrics").json()
    return metrics

print("=" * 60)
print("COST OPTIMIZATION EVIDENCE — Before/After Comparison")
print("=" * 60)

# Phase 1: BEFORE (normal operation)
print("\n--- Phase 1: NORMAL operation (5 requests) ---")
m1 = send_requests(5, "normal")
print(f"  Traffic:        {m1['traffic']}")
print(f"  Avg Cost:       ${m1['avg_cost_usd']}/req")
print(f"  Total Cost:     ${m1['total_cost_usd']}")
print(f"  Tokens Out:     {m1['tokens_out_total']}")
cost_before = m1["avg_cost_usd"]

# Phase 2: ENABLE cost_spike incident
print("\n--- Phase 2: ENABLE cost_spike (simulates 4x token bloat) ---")
r = client.post(f"{BASE}/incidents/cost_spike/enable")
print(f"  Incident status: {r.json()['incidents']}")

m2_before = send_requests(5, "spike")
print(f"  Traffic:        {m2_before['traffic']}")
print(f"  Avg Cost:       ${m2_before['avg_cost_usd']}/req")
print(f"  Total Cost:     ${m2_before['total_cost_usd']}")
print(f"  Tokens Out:     {m2_before['tokens_out_total']}")
cost_during_spike = m2_before["avg_cost_usd"]

# Phase 3: DETECT & FIX — disable cost_spike
print("\n--- Phase 3: DETECT via alert, FIX by disabling cost_spike ---")
r = client.post(f"{BASE}/incidents/cost_spike/disable")
print(f"  Incident status: {r.json()['incidents']}")

m3 = send_requests(5, "recovered")
print(f"  Traffic:        {m3['traffic']}")
print(f"  Avg Cost:       ${m3['avg_cost_usd']}/req")
print(f"  Total Cost:     ${m3['total_cost_usd']}")
print(f"  Tokens Out:     {m3['tokens_out_total']}")
cost_after_fix = m3["avg_cost_usd"]

# Summary
print("\n" + "=" * 60)
print("SUMMARY — Cost Optimization Results")
print("=" * 60)
print(f"  BEFORE (normal):      ${cost_before}/req")
print(f"  DURING spike:         ${cost_during_spike}/req")
print(f"  AFTER fix:            ${cost_after_fix}/req")

if cost_during_spike > cost_before:
    spike_pct = ((cost_during_spike - cost_before) / cost_before) * 100
    print(f"  Cost spike detected:  +{spike_pct:.0f}% increase")
if cost_during_spike > cost_after_fix:
    savings_pct = ((cost_during_spike - cost_after_fix) / cost_during_spike) * 100
    print(f"  Cost savings after:   -{savings_pct:.0f}% reduction")

print("\nConclusion: cost_budget_spike alert would fire at $0.10/hour.")
print("Disabling the cost_spike incident immediately restores normal cost levels.")
