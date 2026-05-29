from __future__ import annotations

import csv
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backend.services.route_service import diagnose_route_candidate_sources  # noqa: E402


FIELDNAMES = [
    "district",
    "market_count",
    "park_count",
    "welfare_count",
    "medical_welfare_count",
    "subway_count",
    "commercial_worker_count",
    "commercial_street_count",
    "public_json_count",
    "total_real_count",
    "fallback_needed",
]


def main() -> int:
    rows = diagnose_route_candidate_sources()
    writer = csv.DictWriter(sys.stdout, fieldnames=FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)

    fallback_needed = [row for row in rows if str(row.get("fallback_needed")).lower() == "true"]
    if fallback_needed:
        print(f"\nWARN: {len(fallback_needed)} districts have no real route candidates.", file=sys.stderr)
    else:
        print(f"\nPASS: all {len(rows)} Seoul districts have at least one real route candidate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
