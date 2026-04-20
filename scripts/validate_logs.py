from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.pii import PII_PATTERNS

DEFAULT_LOG_PATH = Path("data/logs.jsonl")
BASE_REQUIRED_FIELDS = {"ts", "level", "service", "event"}
REQUEST_REQUIRED_FIELDS = {"correlation_id"}
ENRICHMENT_FIELDS = {"user_id_hash", "session_id", "feature", "model"}
REQUEST_SERVICES = {"api", "control"}


def _iter_string_values(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    """Yield all string leaf values with their JSON-like path."""
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path != "$" else key
            yield from _iter_string_values(child, child_path)
        return
    if isinstance(value, list):
        for idx, child in enumerate(value):
            yield from _iter_string_values(child, f"{path}[{idx}]")
        return
    if isinstance(value, str):
        yield path, value


def _find_pii_hits(record: dict[str, Any]) -> list[tuple[str, str]]:
    """
    Return list of (field_path, pii_type) where unredacted PII is still present.
    """
    hits: list[tuple[str, str]] = []
    for field_path, text in _iter_string_values(record):
        # Skip already-redacted content.
        if "[REDACTED_" in text:
            continue
        for pii_type, pattern in PII_PATTERNS.items():
            if pattern.search(text):
                hits.append((field_path, pii_type))
                break
    return hits


def _load_records(log_path: Path) -> list[dict[str, Any]]:
    if not log_path.exists():
        print(f"Error: {log_path} not found. Run the app and send some requests first.")
        sys.exit(1)

    records: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            records.append(parsed)

    if not records:
        print(f"Error: No valid JSON logs found in {log_path}")
        sys.exit(1)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Day 13 structured logs.")
    parser.add_argument(
        "--log-path",
        default=str(DEFAULT_LOG_PATH),
        help="Path to JSONL log file (default: data/logs.jsonl)",
    )
    args = parser.parse_args()
    log_path = Path(args.log_path)

    records = _load_records(log_path)

    total = len(records)
    missing_base_required = 0
    missing_request_required = 0
    missing_enrichment = 0
    pii_hits: list[tuple[str, str, str]] = []
    correlation_ids = set()

    for idx, rec in enumerate(records, start=1):
        if not BASE_REQUIRED_FIELDS.issubset(rec.keys()):
            missing_base_required += 1

        service = rec.get("service")
        if service in REQUEST_SERVICES:
            cid = rec.get("correlation_id")
            if not REQUEST_REQUIRED_FIELDS.issubset(rec.keys()) or cid == "MISSING":
                missing_request_required += 1

        if service == "api" and not ENRICHMENT_FIELDS.issubset(rec.keys()):
            missing_enrichment += 1

        cid = rec.get("correlation_id")
        if cid and cid != "MISSING":
            correlation_ids.add(cid)

        for field_path, pii_type in _find_pii_hits(rec):
            pii_hits.append((str(rec.get("event", "unknown")), field_path, pii_type))

    missing_required_total = missing_base_required + missing_request_required

    print("--- Lab Verification Results ---")
    print(f"Log path: {log_path}")
    print(f"Total log records analyzed: {total}")
    print(f"Records missing base required fields: {missing_base_required}")
    print(f"Records missing request required fields: {missing_request_required}")
    print(f"Records with missing enrichment (api context): {missing_enrichment}")
    print(f"Unique correlation IDs found: {len(correlation_ids)}")
    print(f"Potential PII leaks detected: {len(pii_hits)}")
    if pii_hits:
        sample = pii_hits[:5]
        print("  Leak samples (event, field, pii_type):")
        for event, field_path, pii_type in sample:
            print(f"    - ({event}, {field_path}, {pii_type})")

    print("\n--- Grading Scorecard (Estimates) ---")
    score = 100
    if missing_required_total > 0:
        score -= 30
        print("- [FAILED] Missing required fields (schema/propagation)")
    else:
        print("+ [PASSED] Basic JSON schema + request field requirements")

    if len(correlation_ids) < 2:
        score -= 20
        print("- [FAILED] Correlation ID propagation (less than 2 unique IDs)")
    else:
        print("+ [PASSED] Correlation ID propagation")

    if missing_enrichment > 0:
        score -= 20
        print("- [FAILED] Log enrichment (missing user_id_hash/session/feature/model)")
    else:
        print("+ [PASSED] Log enrichment")

    if pii_hits:
        score -= 30
        print("- [FAILED] PII scrubbing (raw PII detected via pattern scan)")
    else:
        print("+ [PASSED] PII scrubbing")

    print(f"\nEstimated Score: {max(0, score)}/100")


if __name__ == "__main__":
    main()
