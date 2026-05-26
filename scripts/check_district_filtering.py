from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backend.district_utils import normalize_district  # noqa: E402
from backend.scripts.recommender import recommend_places  # noqa: E402
from backend.services.route_service import recommend_route  # noqa: E402


def route_payload(districts: list[str], visit_count: int = 5) -> dict:
    return {
        "date": "2026-03-10",
        "start_time": "09:00",
        "end_time": "18:00",
        "start_location": districts[0] if districts else "서울시청",
        "num_visits": visit_count,
        "districts": districts,
        "target_voter_group": "상인",
        "campaign_goal": "지역상권방문",
        "preferred_place_types": ["market", "senior_friendly", "subway", "park"],
        "avoid_duplicates": True,
    }


def assert_route_case(label: str, districts: list[str], visit_count: int = 5, require_warning: bool = False) -> None:
    result = recommend_route(route_payload(districts, visit_count))
    timeline = result.get("timeline", [])
    selected = {normalize_district(district) for district in districts}
    actual = {item.get("district_normalized") for item in timeline}
    debug = result.get("debug", {})

    assert all(item.get("district_normalized") in selected for item in timeline), (
        label,
        actual,
        timeline,
    )
    assert debug.get("district_mismatch_count") == 0, (label, debug)
    if require_warning and len(timeline) < visit_count:
        assert debug.get("warnings"), (label, "expected shortage warning", debug)

    print(
        f"[PASS] {label}: selected={debug.get('selected_districts')} "
        f"results={sorted(actual)} count={len(timeline)} warnings={debug.get('warnings')}"
    )


def assert_single_case() -> None:
    payload = recommend_places(
        "afternoon",
        "market",
        "60_plus",
        top_n=5,
        selected_districts=["동대문구"],
        include_debug=True,
    )
    places = payload["places"]
    debug = payload["debug"]
    assert all(place.get("district_normalized") == "동대문구" for place in places), places
    assert debug.get("district_mismatch_count") == 0, debug
    print(
        f"[PASS] single recommend 동대문구: count={len(places)} "
        f"warnings={debug.get('warnings')}"
    )


def main() -> int:
    assert_route_case("route 동대문구", ["동대문구"])
    assert_route_case("route 중구", ["중구"])
    assert_route_case("route 중구+동대문구", ["중구", "동대문구"])
    assert_route_case("route 도봉구 후보 부족", ["도봉구"], visit_count=10, require_warning=True)
    assert_single_case()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
