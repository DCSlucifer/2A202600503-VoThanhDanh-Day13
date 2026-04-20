"""Terminal dashboard — displays 6 required panels from GET /metrics."""
from __future__ import annotations

import time

import httpx

BASE_URL = "http://127.0.0.1:8000"
SLO = {
    "latency_p95": 2000,
    "error_rate": 2.0,
    "quality": 0.70,
}


def bar(value: float, max_val: float, width: int = 30, invert: bool = False) -> str:
    ratio = min(value / max_val, 1.0) if max_val > 0 else 0.0
    filled = round(ratio * width)
    fill_char = "█"
    over_slo = (value > max_val) if not invert else (value < max_val)
    color = "\033[91m" if over_slo else "\033[92m"
    reset = "\033[0m"
    return f"{color}{'█' * filled}{'░' * (width - filled)}{reset}"


def slo_tag(ok: bool) -> str:
    return "\033[92m[OK ]\033[0m" if ok else "\033[91m[SLO BREACH]\033[0m"


def fetch(client: httpx.Client) -> dict | None:
    try:
        r = client.get(f"{BASE_URL}/metrics", timeout=5.0)
        return r.json()
    except Exception as exc:
        print(f"\033[91m[ERROR] Cannot reach {BASE_URL}/metrics — {exc}\033[0m")
        return None


def render(m: dict) -> None:
    latency_p50 = m.get("latency_p50", 0)
    latency_p95 = m.get("latency_p95", 0)
    latency_p99 = m.get("latency_p99", 0)
    traffic = m.get("traffic", 0)
    errors = m.get("error_breakdown", {})
    total_errors = sum(errors.values())
    error_rate = (total_errors / traffic * 100) if traffic > 0 else 0.0
    avg_cost = m.get("avg_cost_usd", 0.0)
    total_cost = m.get("total_cost_usd", 0.0)
    tokens_in = m.get("tokens_in_total", 0)
    tokens_out = m.get("tokens_out_total", 0)
    quality = m.get("quality_avg", 0.0)

    # Estimated hourly cost (rough: assume requests spread over 1 hour)
    hourly_cost = total_cost

    ts = time.strftime("%H:%M:%S")

    print("\033[2J\033[H", end="")  # clear screen
    print("=" * 60)
    print(f"  Day 13 Observability Dashboard        {ts}")
    print("=" * 60)

    # Panel 1 — Latency P50 / P95 / P99
    print("\n\033[1mPanel 1 — Latency (ms)\033[0m")
    print(f"  P50 : {latency_p50:>7.1f} ms  {bar(latency_p50, 3000)}")
    print(f"  P95 : {latency_p95:>7.1f} ms  {bar(latency_p95, 3000)}  SLO<2000ms {slo_tag(latency_p95 < SLO['latency_p95'])}")
    print(f"  P99 : {latency_p99:>7.1f} ms  {bar(latency_p99, 3000)}")

    # Panel 2 — Traffic (request count)
    print(f"\n\033[1mPanel 2 — Traffic\033[0m")
    print(f"  Total requests : {traffic}")
    print(f"  Errors         : {total_errors}  breakdown: {errors if errors else 'none'}")

    # Panel 3 — Error rate
    print(f"\n\033[1mPanel 3 — Error Rate\033[0m")
    print(f"  {error_rate:.2f}%  {bar(error_rate, 10)}  SLO<2%  {slo_tag(error_rate < SLO['error_rate'])}")

    # Panel 4 — Cost over time
    print(f"\n\033[1mPanel 4 — Cost (USD)\033[0m")
    print(f"  Avg per request : ${avg_cost:.5f}")
    print(f"  Total session   : ${total_cost:.4f}")
    print(f"  Hourly estimate : ${hourly_cost:.4f}  SLO<$0.10/hr  {slo_tag(hourly_cost < 0.10)}")

    # Panel 5 — Tokens in / out
    print(f"\n\033[1mPanel 5 — Tokens\033[0m")
    print(f"  Tokens IN  : {tokens_in:,}")
    print(f"  Tokens OUT : {tokens_out:,}")
    print(f"  Ratio OUT/IN : {tokens_out/tokens_in:.2f}" if tokens_in > 0 else "  Ratio OUT/IN : N/A")

    # Panel 6 — Quality proxy
    print(f"\n\033[1mPanel 6 — Quality Score (heuristic)\033[0m")
    print(f"  Avg : {quality:.3f}  {bar(quality, 1.0, invert=False)}  SLO>0.70  {slo_tag(quality >= SLO['quality'])}")

    print("\n" + "=" * 60)
    print("  Refreshing every 5s — Ctrl+C to stop")


def main() -> None:
    print(f"Connecting to {BASE_URL} ...")
    with httpx.Client(timeout=10.0) as client:
        while True:
            data = fetch(client)
            if data is not None:
                render(data)
            try:
                time.sleep(5)
            except KeyboardInterrupt:
                print("\nDashboard stopped.")
                break


if __name__ == "__main__":
    main()
