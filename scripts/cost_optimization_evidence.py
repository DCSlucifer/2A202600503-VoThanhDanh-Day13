from __future__ import annotations

"""
Cost Optimization Evidence Script
Runs phases with delta-based accounting:
  1) normal
  2) cost_spike enabled
  3) recovered after disabling cost_spike
This avoids using cumulative avg_cost_usd directly, which can hide phase effects.
"""

import argparse
from dataclasses import dataclass

import httpx


@dataclass
class PhaseDelta:
    requests_sent: int
    traffic_delta: int
    cost_delta_usd: float
    tokens_out_delta: int
    avg_cost_usd_per_request: float


def get_metrics(client: httpx.Client, base_url: str) -> dict:
    response = client.get(f"{base_url}/metrics")
    response.raise_for_status()
    return response.json()


def set_cost_spike(client: httpx.Client, base_url: str, enabled: bool) -> dict:
    action = "enable" if enabled else "disable"
    response = client.post(f"{base_url}/incidents/cost_spike/{action}")
    response.raise_for_status()
    return response.json()


def send_requests(client: httpx.Client, base_url: str, n: int, label: str) -> int:
    sent = 0
    for i in range(n):
        response = client.post(
            f"{base_url}/chat",
            json={
                "user_id": f"u_cost_{label}_{i}",
                "session_id": f"s_cost_{label}_{i}",
                "feature": "qa",
                "message": "What is monitoring?",
            },
        )
        response.raise_for_status()
        sent += 1
    return sent


def compute_phase_delta(before: dict, after: dict, requests_sent: int) -> PhaseDelta:
    traffic_delta = max(0, int(after["traffic"]) - int(before["traffic"]))
    cost_delta_usd = round(float(after["total_cost_usd"]) - float(before["total_cost_usd"]), 6)
    tokens_out_delta = max(0, int(after["tokens_out_total"]) - int(before["tokens_out_total"]))
    avg_cost_usd_per_request = round(cost_delta_usd / traffic_delta, 6) if traffic_delta else 0.0
    return PhaseDelta(
        requests_sent=requests_sent,
        traffic_delta=traffic_delta,
        cost_delta_usd=cost_delta_usd,
        tokens_out_delta=tokens_out_delta,
        avg_cost_usd_per_request=avg_cost_usd_per_request,
    )


def run_phase(client: httpx.Client, base_url: str, requests_per_phase: int, label: str) -> PhaseDelta:
    before = get_metrics(client, base_url)
    requests_sent = send_requests(client, base_url, requests_per_phase, label)
    after = get_metrics(client, base_url)
    return compute_phase_delta(before, after, requests_sent)


def print_phase(title: str, phase: PhaseDelta) -> None:
    print(f"\n--- {title} ---")
    print(f"  Requests Sent:        {phase.requests_sent}")
    print(f"  Traffic Delta:        {phase.traffic_delta}")
    print(f"  Cost Delta:           ${phase.cost_delta_usd}")
    print(f"  Avg Cost (delta):     ${phase.avg_cost_usd_per_request}/req")
    print(f"  Tokens Out Delta:     {phase.tokens_out_delta}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate cost optimization before/after evidence.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    parser.add_argument("--requests", type=int, default=5, help="Requests per phase")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    requests_per_phase = max(1, args.requests)

    print("=" * 60)
    print("COST OPTIMIZATION EVIDENCE - Before/After Comparison")
    print("=" * 60)

    with httpx.Client(timeout=30.0) as client:
        # Ensure deterministic baseline
        baseline_state = set_cost_spike(client, base_url, enabled=False)
        print(f"Initial incident state: {baseline_state['incidents']}")

        normal = run_phase(client, base_url, requests_per_phase, "normal")
        print_phase(f"Phase 1: NORMAL operation ({requests_per_phase} requests)", normal)

        spike_state = set_cost_spike(client, base_url, enabled=True)
        print(f"\nEnabled cost_spike: {spike_state['incidents']}")
        spike = run_phase(client, base_url, requests_per_phase, "spike")
        print_phase(f"Phase 2: COST SPIKE ({requests_per_phase} requests)", spike)

        recovered_state = set_cost_spike(client, base_url, enabled=False)
        print(f"\nDisabled cost_spike: {recovered_state['incidents']}")
        recovered = run_phase(client, base_url, requests_per_phase, "recovered")
        print_phase(f"Phase 3: RECOVERED ({requests_per_phase} requests)", recovered)

    print("\n" + "=" * 60)
    print("SUMMARY - Cost Optimization Results")
    print("=" * 60)
    print(f"  BEFORE (normal):      ${normal.avg_cost_usd_per_request}/req")
    print(f"  DURING spike:         ${spike.avg_cost_usd_per_request}/req")
    print(f"  AFTER fix:            ${recovered.avg_cost_usd_per_request}/req")

    if normal.avg_cost_usd_per_request > 0 and spike.avg_cost_usd_per_request > normal.avg_cost_usd_per_request:
        spike_pct = ((spike.avg_cost_usd_per_request - normal.avg_cost_usd_per_request) / normal.avg_cost_usd_per_request) * 100
        print(f"  Cost spike detected:  +{spike_pct:.0f}% increase")
    if spike.avg_cost_usd_per_request > 0 and recovered.avg_cost_usd_per_request < spike.avg_cost_usd_per_request:
        savings_pct = ((spike.avg_cost_usd_per_request - recovered.avg_cost_usd_per_request) / spike.avg_cost_usd_per_request) * 100
        print(f"  Cost savings after:   -{savings_pct:.0f}% reduction")

    print("\nConclusion: cost_budget_spike alert should fire on abnormal spend growth.")
    print("Disabling cost_spike should bring per-request cost back toward baseline.")


if __name__ == "__main__":
    main()
