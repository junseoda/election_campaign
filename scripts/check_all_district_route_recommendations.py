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

from backend.services.route_service import recommend_route  # noqa: E402


SEOUL_DISTRICTS = [
    "종로구",
    "중구",
    "용산구",
    "성동구",
    "광진구",
    "동대문구",
    "중랑구",
    "성북구",
    "강북구",
    "도봉구",
    "노원구",
    "은평구",
    "서대문구",
    "마포구",
    "양천구",
    "강서구",
    "구로구",
    "금천구",
    "영등포구",
    "동작구",
    "관악구",
    "서초구",
    "강남구",
    "송파구",
    "강동구",
]


def build_payload(district: str) -> dict:
    return {
        "date": "2026-03-10",
        "start_time": "09:00",
        "end_time": "18:00",
        "start_location": district,
        "visit_count": 5,
        "num_visits": 5,
        "districts": [district],
        "target_voter_group": "직장인",
        "campaign_goal": "퇴근인사",
        "preferred_place_types": ["교통거점", "골목상권", "전통시장"],
        "avoid_duplicates": True,
    }


def check_district(district: str) -> dict:
    result = recommend_route(build_payload(district))
    timeline = result.get("timeline", [])
    debug = result.get("debug", {})
    districts_returned = sorted({item.get("district_normalized") for item in timeline if item.get("district_normalized")})
    mismatch_count = int(debug.get("district_mismatch_count") or 0)
    passed = bool(timeline) and mismatch_count == 0 and all(
        item.get("district_normalized") == district for item in timeline
    )
    return {
        "district": district,
        "result_count": len(timeline),
        "real_candidate_count": int(debug.get("real_candidate_count") or 0),
        "fallback_candidate_count": int(debug.get("fallback_candidate_count") or 0),
        "source_counts": json.dumps(debug.get("source_counts", {}), ensure_ascii=False, sort_keys=True),
        "districts_returned": "|".join(districts_returned),
        "mismatch_count": mismatch_count,
        "fallback_used": str(bool(debug.get("fallback_used"))).lower(),
        "fallback_stage": debug.get("fallback_stage") or "",
        "status": "PASS" if passed else "FAIL",
    }


def main() -> int:
    writer = csv.DictWriter(
        sys.stdout,
        fieldnames=[
            "district",
            "result_count",
            "real_candidate_count",
            "fallback_candidate_count",
            "source_counts",
            "districts_returned",
            "mismatch_count",
            "fallback_used",
            "fallback_stage",
            "status",
        ],
        lineterminator="\n",
    )
    writer.writeheader()
    rows = [check_district(district) for district in SEOUL_DISTRICTS]
    writer.writerows(rows)

    failed = [row for row in rows if row["status"] != "PASS"]
    if failed:
        print(f"\nFAIL: {len(failed)} districts failed route recommendation checks.", file=sys.stderr)
        return 1
    print(f"\nPASS: all {len(rows)} Seoul districts returned district-safe route recommendations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
