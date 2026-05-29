from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backend.district_utils import SEOUL_DISTRICT_LIST, normalize_districts  # noqa: E402
from backend.services.route_service import recommend_route  # noqa: E402


FALLBACK_SOURCES = {"district_fallback_seed", "synthetic_district_fallback"}

CONDITIONS = {
    "A": {
        "target_voter_group": "직장인",
        "campaign_goal": "퇴근인사",
        "preferred_place_types": ["교통거점", "골목상권", "전통시장"],
    },
    "B": {
        "target_voter_group": "상인",
        "campaign_goal": "지역상권방문",
        "preferred_place_types": ["전통시장", "골목상권"],
    },
    "C": {
        "target_voter_group": "생활 유권자",
        "campaign_goal": "생활불편청취",
        "preferred_place_types": ["공원", "복지시설", "교통거점"],
    },
}

MULTI_DISTRICT_CASES = [
    ["성북구", "송파구"],
    ["용산구", "강남구"],
    ["중구", "동대문구"],
    ["서초구", "강남구"],
    ["마포구", "영등포구"],
]

FIELDNAMES = [
    "case_type",
    "condition",
    "districts",
    "result_count",
    "real_candidate_count",
    "fallback_candidate_count",
    "source_counts",
    "district_distribution",
    "district_mismatch_count",
    "fallback_used",
    "fallback_stage",
    "status",
]


def build_payload(districts: list[str], condition: dict) -> dict:
    return {
        "date": "2026-03-10",
        "start_time": "09:00",
        "end_time": "18:00",
        "start_location": districts[0],
        "visit_count": 5,
        "num_visits": 5,
        "districts": districts,
        "target_voter_group": condition["target_voter_group"],
        "campaign_goal": condition["campaign_goal"],
        "preferred_place_types": condition["preferred_place_types"],
        "avoid_duplicates": True,
    }


def is_fallback(item: dict) -> bool:
    source = item.get("source") or item.get("candidate_source") or ""
    return bool(item.get("is_fallback")) or source in FALLBACK_SOURCES


def fallback_before_real(timeline: list[dict]) -> bool:
    fallback_indices = [index for index, item in enumerate(timeline) if is_fallback(item)]
    real_indices = [index for index, item in enumerate(timeline) if not is_fallback(item)]
    return bool(fallback_indices and real_indices and min(fallback_indices) < max(real_indices))


def check_case(case_type: str, condition_name: str, districts: list[str]) -> dict:
    normalized = normalize_districts(districts)
    result = recommend_route(build_payload(normalized, CONDITIONS[condition_name]))
    timeline = result.get("timeline", [])
    debug = result.get("debug", {})
    mismatch_count = int(debug.get("district_mismatch_count") or 0)
    unselected = [
        item.get("district_normalized")
        for item in timeline
        if item.get("district_normalized") not in normalized
    ]
    priority_failed = fallback_before_real(timeline)
    passed = bool(timeline) and mismatch_count == 0 and not unselected and not priority_failed
    return {
        "case_type": case_type,
        "condition": condition_name,
        "districts": "|".join(normalized),
        "result_count": len(timeline),
        "real_candidate_count": int(debug.get("real_candidate_count") or 0),
        "fallback_candidate_count": int(debug.get("fallback_candidate_count") or 0),
        "source_counts": json.dumps(debug.get("source_counts", {}), ensure_ascii=False, sort_keys=True),
        "district_distribution": json.dumps(debug.get("district_distribution", {}), ensure_ascii=False, sort_keys=True),
        "district_mismatch_count": mismatch_count,
        "fallback_used": str(bool(debug.get("fallback_used"))).lower(),
        "fallback_stage": debug.get("fallback_stage") or "",
        "status": "PASS" if passed else "FAIL",
    }


def main() -> int:
    rows = []
    for condition_name in CONDITIONS:
        rows.extend(
            check_case("single", condition_name, [district])
            for district in SEOUL_DISTRICT_LIST
        )
        rows.extend(
            check_case("multi", condition_name, districts)
            for districts in MULTI_DISTRICT_CASES
        )

    writer = csv.DictWriter(sys.stdout, fieldnames=FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)

    failed = [row for row in rows if row["status"] != "PASS"]
    if failed:
        print(f"\nFAIL: {len(failed)} route real-candidate priority checks failed.", file=sys.stderr)
        return 1
    print(f"\nPASS: all {len(rows)} route real-candidate priority checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
