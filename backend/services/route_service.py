from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
import hashlib
import re
from typing import Any

import pandas as pd


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent


def _resolve_data_root() -> Path:
    for candidate in (BACKEND_ROOT, REPOSITORY_ROOT):
        if (candidate / "output").exists():
            return candidate
    return BACKEND_ROOT


PROJECT_ROOT = _resolve_data_root()
OPTIMIZED_RECOMMENDATIONS_PATH = (
    PROJECT_ROOT
    / "output"
    / "experiments_optimized"
    / "optimized_proposed"
    / "recommendation_results.csv"
)
RAW_BASELINE_PATH = PROJECT_ROOT / "output" / "raw_baseline_recommendations.csv"
PAST_VISITS_PATH = PROJECT_ROOT / "output" / "gold_set_strong_place_only.csv"

SEOUL_DISTRICTS = [
    "강남구",
    "강동구",
    "강북구",
    "강서구",
    "관악구",
    "광진구",
    "구로구",
    "금천구",
    "노원구",
    "도봉구",
    "동대문구",
    "동작구",
    "마포구",
    "서대문구",
    "서초구",
    "성동구",
    "성북구",
    "송파구",
    "양천구",
    "영등포구",
    "용산구",
    "은평구",
    "종로구",
    "중구",
    "중랑구",
]

ADJACENT_DISTRICTS = {
    "성동구": {"중구", "광진구", "동대문구", "용산구"},
    "중구": {"종로구", "성동구", "용산구", "동대문구"},
    "마포구": {"서대문구", "용산구", "영등포구", "은평구"},
    "영등포구": {"마포구", "동작구", "양천구", "구로구"},
    "종로구": {"중구", "서대문구", "성북구", "동대문구"},
    "광진구": {"성동구", "중랑구", "동대문구", "송파구"},
    "송파구": {"강남구", "강동구", "광진구"},
    "강남구": {"서초구", "송파구", "성동구"},
    "서초구": {"강남구", "동작구", "관악구"},
}

PLACE_TYPE_LABELS = {
    "market": "전통시장",
    "subway": "교통거점",
    "park": "공원",
    "senior_friendly": "복지시설",
    "senior": "복지시설",
}

TARGET_GROUPS = ["직장인", "청년", "상인", "노년층", "가족/어린이", "지역주민"]
CAMPAIGN_GOALS = ["출근인사", "시장방문", "정책현장", "공원방문", "퇴근인사", "지역상권방문"]
PLACE_TYPES = ["교통거점", "골목상권", "전통시장", "공원", "복지시설", "정책현장", "체육시설"]

LOCATION_DISTRICT_HINTS = {
    "서울시청": "중구",
    "시청역": "중구",
    "광화문": "종로구",
    "왕십리역": "성동구",
    "왕십리": "성동구",
    "성동구청": "성동구",
    "성수역": "성동구",
    "성수": "성동구",
    "강남역": "강남구",
    "강남": "강남구",
    "홍대입구": "마포구",
    "홍대": "마포구",
    "여의도": "영등포구",
    "구로디지털단지": "구로구",
    "신림역": "관악구",
    "신림": "관악구",
    "건대입구": "광진구",
    "잠실역": "송파구",
    "잠실": "송파구",
}

PLACE_NAME_OVERRIDES = {
    "강남": "강남역 11번 출구 앞",
    "강남역": "강남역 11번 출구 앞",
    "성수": "성수역 3번 출구 앞",
    "성수역": "성수역 3번 출구 앞",
    "왕십리": "왕십리역 광장",
    "왕십리역": "왕십리역 광장",
    "서울시청": "서울시청 앞 광장",
    "시청": "서울시청 앞 광장",
    "시청역": "시청역 5번 출구 앞",
    "홍대": "홍대입구역 9번 출구 앞",
    "홍대입구": "홍대입구역 9번 출구 앞",
    "여의도": "여의도역 5번 출구 앞",
    "건대입구": "건대입구역 2번 출구 앞",
    "신림": "신림역 4번 출구 앞",
    "잠실": "잠실역 8번 출구 앞",
    "종로": "종로3가역 일대",
}


@dataclass
class RouteRequestData:
    date: str
    start_time: str
    end_time: str
    start_location: str
    districts: list[str]
    target_voter_group: str
    campaign_goal: str
    preferred_place_types: list[str]
    num_visits: int
    avoid_duplicates: bool


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"required route data file not found: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _extract_district(*values: Any) -> str:
    for value in values:
        text = _clean_text(value)
        match = re.search(r"([가-힣]+구)", text)
        if match:
            return match.group(1)
    return ""


def _normalize_place_type(value: Any) -> str:
    text = _clean_text(value)
    return PLACE_TYPE_LABELS.get(text, text or "기타")


def _normalize_address(value: Any) -> str:
    text = _clean_text(value)
    if not text or text in {"확인 필요", "해당 없음", "nan", "None"}:
        return "주소 확인 필요"
    return text


def infer_start_location_district(start_location: Any) -> str:
    text = _clean_text(start_location)
    direct = _extract_district(text)
    if direct:
        return direct

    for keyword, district in LOCATION_DISTRICT_HINTS.items():
        if keyword in text:
            return district

    for district in SEOUL_DISTRICTS:
        district_stem = district.replace("구", "")
        if district_stem and district_stem in text:
            return district

    return ""


def place_name_normalizer(place_name: Any, place_type: str = "", district: str = "") -> str:
    text = re.sub(r"\s+", " ", _clean_text(place_name))
    if not text or text in {"확인 필요", "해당 없음", "nan", "None"}:
        return "장소 확인 필요"

    compact = re.sub(r"\s+", "", text)
    normalized_type = _normalize_place_type(place_type)
    if compact in PLACE_NAME_OVERRIDES:
        return PLACE_NAME_OVERRIDES[compact]

    for district_name in SEOUL_DISTRICTS:
        district_stem = district_name.replace("구", "")
        if compact in {district_name, district_stem}:
            if normalized_type == "교통거점":
                return f"{district_stem}역 일대"
            return f"{district_name} 주요 유세 거점"

    if normalized_type == "교통거점":
        if compact.endswith("역") and not any(token in compact for token in ["출구", "광장", "앞", "일대"]):
            if compact in {"왕십리역", "서울역", "청량리역"}:
                return f"{compact} 광장"
            return f"{compact} 출구 앞"
        if len(compact) <= 5 and not any(token in compact for token in ["역", "시장", "공원", "복지"]):
            return f"{compact}역 일대"

    if normalized_type in {"전통시장", "골목상권"} and "시장" in compact and not any(
        token in compact for token in ["입구", "앞", "일대", "남문", "북문"]
    ):
        return f"{text} 입구"

    return text


def _parse_minutes(value: str) -> int:
    match = re.match(r"^(\d{1,2}):(\d{2})$", _clean_text(value))
    if not match:
        raise ValueError(f"time must be HH:MM format: {value}")
    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError(f"invalid time value: {value}")
    return (hour * 60) + minute


def _format_minutes(minutes: int) -> str:
    minutes = max(0, min(23 * 60 + 59, int(minutes)))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _build_time_slots(start_time: str, end_time: str, num_visits: int) -> list[str]:
    start_minutes = _parse_minutes(start_time)
    end_minutes = _parse_minutes(end_time)
    if end_minutes <= start_minutes:
        raise ValueError("end_time must be later than start_time")

    visit_count = max(1, min(8, int(num_visits)))
    if visit_count == 1:
        return [_format_minutes(start_minutes)]

    interval = (end_minutes - start_minutes) / (visit_count - 1)
    return [_format_minutes(round(start_minutes + (interval * index))) for index in range(visit_count)]


def _day_of_week(route_date: str) -> str:
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    parsed = datetime.strptime(route_date, "%Y-%m-%d").date()
    return weekdays[parsed.weekday()]


def _stable_mock_position(name: str, order: int) -> dict[str, float | None]:
    digest = hashlib.md5(f"{name}-{order}".encode("utf-8")).hexdigest()
    x_seed = int(digest[:4], 16)
    y_seed = int(digest[4:8], 16)
    return {
        "lat": None,
        "lng": None,
        "mock_x": 18 + (x_seed % 64),
        "mock_y": 22 + (y_seed % 58),
    }


def _district_relation(previous_district: str, current_district: str) -> str:
    if previous_district and current_district and previous_district == current_district:
        return "same"
    if current_district in ADJACENT_DISTRICTS.get(previous_district, set()):
        return "adjacent"
    if previous_district in ADJACENT_DISTRICTS.get(current_district, set()):
        return "adjacent"
    return "far"


def _travel_penalty_and_minutes(previous_district: str, current_district: str) -> tuple[float, int]:
    relation = _district_relation(previous_district, current_district)
    if relation == "same":
        return 0.0, 12
    if relation == "adjacent":
        return -0.05, 24
    return -0.15, 42


def _start_location_fit(order: int, start_district: str, candidate_district: str) -> float:
    if order != 1 or not start_district or not candidate_district:
        return 0.0
    relation = _district_relation(start_district, candidate_district)
    if relation == "same":
        return 0.45
    if relation == "adjacent":
        return 0.12
    return -0.35


def _time_slot_fit(time_value: str, place_type: str, campaign_goal: str) -> float:
    hour = _parse_minutes(time_value) // 60
    goal = _clean_text(campaign_goal)

    if 7 <= hour < 10:
        preferred = {"교통거점": 0.30, "골목상권": 0.16, "전통시장": 0.14}
    elif 10 <= hour < 12:
        preferred = {"전통시장": 0.24, "복지시설": 0.22, "정책현장": 0.20, "교통거점": 0.12}
    elif 12 <= hour < 14:
        preferred = {"골목상권": 0.26, "전통시장": 0.24, "교통거점": 0.14}
    elif 14 <= hour < 17:
        preferred = {"공원": 0.22, "복지시설": 0.20, "체육시설": 0.20, "정책현장": 0.20}
    elif 17 <= hour < 20:
        preferred = {"교통거점": 0.30, "골목상권": 0.22, "전통시장": 0.20}
    else:
        preferred = {"교통거점": 0.10, "전통시장": 0.10, "골목상권": 0.10}

    score = preferred.get(place_type, 0.06)
    if "출근" in goal and 7 <= hour < 10 and place_type == "교통거점":
        score += 0.08
    if "퇴근" in goal and 17 <= hour < 20 and place_type in {"교통거점", "골목상권"}:
        score += 0.08
    if "시장" in goal and place_type == "전통시장":
        score += 0.06
    if "공원" in goal and place_type == "공원":
        score += 0.06
    if "정책" in goal and place_type == "정책현장":
        score += 0.06

    return round(min(score, 0.38), 4)


def _target_fit(target: str, place_type: str, place_name: str) -> float:
    text = f"{target} {place_type} {place_name}"
    rules = {
        "직장인": {"교통거점", "골목상권", "전통시장"},
        "청년": {"교통거점", "골목상권", "공원"},
        "상인": {"전통시장", "골목상권"},
        "노년층": {"복지시설", "전통시장", "공원"},
        "가족/어린이": {"공원", "체육시설", "복지시설"},
        "지역주민": {"전통시장", "골목상권", "공원", "복지시설"},
    }
    for key, preferred_types in rules.items():
        if key in text and place_type in preferred_types:
            return 0.18
    return 0.08


def _district_fit(candidate_district: str, preferred_districts: list[str]) -> float:
    if not preferred_districts:
        return 0.08
    if candidate_district in preferred_districts:
        return 0.22
    if any(_district_relation(candidate_district, district) == "adjacent" for district in preferred_districts):
        return 0.10
    return 0.0


@lru_cache(maxsize=1)
def _load_candidate_pool() -> pd.DataFrame:
    optimized = _read_csv(OPTIMIZED_RECOMMENDATIONS_PATH)
    raw = _read_csv(RAW_BASELINE_PATH)

    frames = []
    if not optimized.empty:
        optimized_candidates = optimized.copy()
        optimized_candidates["candidate_score"] = pd.to_numeric(
            optimized_candidates.get("score"),
            errors="coerce",
        ).fillna(0.0)
        frames.append(optimized_candidates)

    if not raw.empty:
        raw_candidates = raw.copy()
        raw_candidates["score"] = pd.to_numeric(raw_candidates.get("baseline_score"), errors="coerce").fillna(0.0)
        raw_candidates["candidate_score"] = raw_candidates["score"]
        for column in [
            "rank",
            "district_bonus",
            "place_type_bonus",
            "time_bonus",
            "context_bonus",
            "target_bonus",
            "rank_bonus",
            "final_variant_score",
        ]:
            if column not in raw_candidates.columns:
                raw_candidates[column] = 0.0
        frames.append(raw_candidates)

    if not frames:
        raise ValueError("route candidate pool is empty")

    candidates = pd.concat(frames, ignore_index=True, sort=False)
    candidates["recommended_place_name"] = candidates["recommended_place_name"].fillna("").astype(str).str.strip()
    candidates = candidates[candidates["recommended_place_name"] != ""].copy()
    candidates["recommended_district"] = candidates["recommended_district"].apply(_clean_text)
    candidates["recommended_place_type"] = candidates["recommended_place_type"].apply(_normalize_place_type)
    candidates["candidate_score"] = pd.to_numeric(candidates["candidate_score"], errors="coerce").fillna(0.0)

    sort_columns = ["candidate_score", "recommended_place_name"]
    candidates = candidates.sort_values(sort_columns, ascending=[False, True])
    return candidates.drop_duplicates(
        subset=["recommended_place_name", "recommended_district", "recommended_place_type"],
        keep="first",
    ).reset_index(drop=True)


@lru_cache(maxsize=1)
def _load_past_visits() -> pd.DataFrame:
    try:
        visits = _read_csv(PAST_VISITS_PATH)
    except FileNotFoundError:
        return pd.DataFrame()

    if visits.empty:
        return visits

    visits = visits.copy()
    visits["date"] = pd.to_datetime(visits["date"], errors="coerce")
    visits["place_name"] = visits["place_name"].fillna("").astype(str).str.strip()
    visits["address"] = visits["address"].fillna("").astype(str).str.strip()
    visits["district"] = visits["district"].fillna("").astype(str).str.strip()
    return visits


def _duplicate_penalty(
    candidate: pd.Series,
    route_date: str,
    past_visits: pd.DataFrame,
    selected_district_counts: dict[str, int],
    selected_type_counts: dict[str, int],
) -> float:
    penalty = 0.0
    place_name = _clean_text(candidate.get("recommended_place_name"))
    district = _clean_text(candidate.get("recommended_district"))
    place_type = _clean_text(candidate.get("recommended_place_type"))

    if not past_visits.empty:
        route_day = pd.to_datetime(pd.Series([route_date]), errors="coerce").iloc[0]
        matched_visits = past_visits[
            (past_visits["place_name"] == place_name)
            | ((district != "") & (past_visits["district"] == district))
        ].copy()
        for _, visit in matched_visits.iterrows():
            visit_date = visit.get("date")
            if pd.isna(route_day) or pd.isna(visit_date):
                continue
            day_gap = (route_day - visit_date).days
            if place_name and visit.get("place_name") == place_name:
                penalty -= 0.50 if 0 <= day_gap <= 7 else 0.30 if 0 <= day_gap <= 30 else 0.12
            elif district and visit.get("district") == district and 0 <= day_gap <= 30:
                penalty -= 0.10

    if selected_district_counts.get(district, 0) >= 1:
        penalty -= 0.10
    if selected_type_counts.get(place_type, 0) >= 2:
        penalty -= 0.15

    return round(max(penalty, -0.75), 4)


def _diversity_bonus(
    candidate: pd.Series,
    selected_types: set[str],
    selected_districts: set[str],
) -> float:
    place_type = _clean_text(candidate.get("recommended_place_type"))
    district = _clean_text(candidate.get("recommended_district"))
    bonus = 0.0
    if place_type and place_type not in selected_types:
        bonus += 0.08
    if district and district not in selected_districts:
        bonus += 0.04
    return round(bonus, 4)


def _sequence_reason(
    order: int,
    time_value: str,
    candidate: pd.Series,
    start_district: str,
    previous_district: str,
    travel_minutes: int,
    total_orders: int,
) -> str:
    place_type = _clean_text(candidate.get("recommended_place_type"))
    district = _clean_text(candidate.get("recommended_district"))
    hour = _parse_minutes(time_value) // 60

    if order == 1:
        relation = _district_relation(start_district, district)
        if relation == "same":
            return f"시작 위치와 같은 {district} 내 {place_type}이므로 첫 일정으로 배치했습니다."
        if relation == "adjacent":
            return f"시작 위치 인접 자치구인 {district} 후보라 첫 이동 부담이 낮아 초반 일정으로 배치했습니다."
        return f"출발지와 거리가 있어 감점했지만, 추천 점수와 시간대 적합도가 높아 첫 일정 후보로 선택했습니다."

    if order == total_orders and 17 <= hour < 20:
        return f"퇴근 시간대 유동인구가 많은 {place_type} 후보라 마지막 일정으로 배치했습니다."
    if 12 <= hour < 14:
        return f"점심 시간대 상권·생활권 접촉에 적합하여 {order}번째 일정으로 배치했습니다."
    if previous_district and _district_relation(previous_district, district) == "same":
        return f"이전 일정과 같은 {district} 안에서 이동 부담을 줄이기 위해 이어서 배치했습니다."
    return f"이전 일정에서 예상 이동 {travel_minutes}분 이내로 연결 가능한 후보 장소라 {order}번째 일정으로 배치했습니다."


def _recommendation_reason(
    time_value: str,
    candidate: pd.Series,
    target: str,
    duplicate_penalty: float,
    travel_minutes: int,
) -> str:
    place_type = _clean_text(candidate.get("recommended_place_type"))
    district = _clean_text(candidate.get("recommended_district"))
    hour = _parse_minutes(time_value) // 60

    if 7 <= hour < 10:
        timing = "출근 시간대 접촉 가능성이 높아"
    elif 17 <= hour < 20:
        timing = "퇴근 시간대 유동 인구 접점이 좋아"
    elif 12 <= hour < 14:
        timing = "점심 시간대 생활권 접촉에 적합해"
    else:
        timing = "해당 시간대 현장 방문 맥락에 맞아"

    duplicate_text = " 최근 방문 이력이 있어 우선순위가 일부 낮아졌습니다." if duplicate_penalty < 0 else ""
    return (
        f"{timing} {district}의 {place_type} 후보 장소로 배치했습니다. "
        f"{target} 타깃과의 접점, 예상 이동 {travel_minutes}분을 함께 고려했습니다.{duplicate_text}"
    )


def _build_route(request: RouteRequestData) -> dict[str, Any]:
    candidates = _load_candidate_pool()
    past_visits = _load_past_visits() if request.avoid_duplicates else pd.DataFrame()
    time_slots = _build_time_slots(request.start_time, request.end_time, request.num_visits)
    start_district = infer_start_location_district(request.start_location) or (
        request.districts[0] if request.districts else ""
    )

    preferred_place_types = set(request.preferred_place_types or [])
    selected_names: set[str] = set()
    selected_types: set[str] = set()
    selected_districts: set[str] = set()
    selected_district_counts: dict[str, int] = {}
    selected_type_counts: dict[str, int] = {}
    previous_district = start_district
    timeline = []

    filtered = candidates.copy()
    if request.districts:
        district_mask = filtered["recommended_district"].isin(request.districts)
        adjacent_mask = filtered["recommended_district"].apply(
            lambda district: any(_district_relation(district, preferred) == "adjacent" for preferred in request.districts)
        )
        if int((district_mask | adjacent_mask).sum()) >= max(3, request.num_visits):
            filtered = filtered[district_mask | adjacent_mask].copy()

    for order, time_value in enumerate(time_slots, start=1):
        scored_rows = []
        for _, candidate in filtered.iterrows():
            place_name = _clean_text(candidate.get("recommended_place_name"))
            display_place_name = place_name_normalizer(
                place_name,
                candidate.get("recommended_place_type"),
                candidate.get("recommended_district"),
            )
            if not place_name or place_name in selected_names or display_place_name in selected_names:
                continue

            place_type = _clean_text(candidate.get("recommended_place_type"))
            district = _clean_text(candidate.get("recommended_district"))
            optimized_place_score = float(candidate.get("candidate_score", 0.0))
            time_score = _time_slot_fit(time_value, place_type, request.campaign_goal)
            target_score = _target_fit(request.target_voter_group, place_type, place_name)
            district_score = _district_fit(district, request.districts)
            start_score = _start_location_fit(order, start_district, district)
            diversity_score = _diversity_bonus(candidate, selected_types, selected_districts)
            if preferred_place_types and place_type in preferred_place_types:
                diversity_score += 0.05
            duplicate_penalty = (
                _duplicate_penalty(
                    candidate,
                    request.date,
                    past_visits,
                    selected_district_counts,
                    selected_type_counts,
                )
                if request.avoid_duplicates
                else 0.0
            )
            travel_penalty, travel_minutes = _travel_penalty_and_minutes(previous_district, district)
            route_score = (
                optimized_place_score
                + time_score
                + target_score
                + district_score
                + start_score
                + diversity_score
                + duplicate_penalty
                + travel_penalty
            )
            scored_rows.append(
                {
                    "candidate": candidate,
                    "route_score": route_score,
                    "optimized_place_score": optimized_place_score,
                    "time_slot_fit_score": time_score,
                    "target_voter_fit_score": target_score,
                    "district_fit_score": district_score,
                    "start_location_fit_score": start_score,
                    "diversity_bonus": round(diversity_score, 4),
                    "duplicate_visit_penalty": duplicate_penalty,
                    "travel_distance_penalty": travel_penalty,
                    "travel_minutes": travel_minutes,
                }
            )

        if not scored_rows:
            break

        best = max(scored_rows, key=lambda row: row["route_score"])
        candidate = best["candidate"]
        raw_place_name = _clean_text(candidate.get("recommended_place_name"))
        place_name = place_name_normalizer(
            candidate.get("recommended_place_name"),
            candidate.get("recommended_place_type"),
            candidate.get("recommended_district"),
        )
        district = _clean_text(candidate.get("recommended_district"))
        place_type = _clean_text(candidate.get("recommended_place_type"))
        selected_names.add(raw_place_name)
        selected_names.add(place_name)
        selected_types.add(place_type)
        selected_districts.add(district)
        selected_district_counts[district] = selected_district_counts.get(district, 0) + 1
        selected_type_counts[place_type] = selected_type_counts.get(place_type, 0) + 1

        travel_minutes = best["travel_minutes"]
        score_breakdown = {
            "optimized_place_score": round(best["optimized_place_score"], 4),
            "time_slot_fit_score": best["time_slot_fit_score"],
            "target_voter_fit_score": best["target_voter_fit_score"],
            "district_fit_score": best["district_fit_score"],
            "start_location_fit_score": best["start_location_fit_score"],
            "diversity_bonus": round(best["diversity_bonus"], 4),
            "duplicate_visit_penalty": best["duplicate_visit_penalty"],
            "travel_distance_penalty": best["travel_distance_penalty"],
        }
        timeline.append(
            {
                "order": order,
                "time": time_value,
                "place_name": place_name,
                "district": district,
                "place_type": place_type,
                "address": _normalize_address(candidate.get("address")),
                "candidate_source": _clean_text(candidate.get("candidate_source")),
                "estimated_travel_time_from_previous": f"{travel_minutes}분",
                "score": round(best["route_score"], 4),
                "score_breakdown": score_breakdown,
                "sequence_reason": _sequence_reason(
                    order,
                    time_value,
                    candidate,
                    start_district,
                    previous_district,
                    travel_minutes,
                    len(time_slots),
                ),
                "recommendation_reason": _recommendation_reason(
                    time_value,
                    candidate,
                    request.target_voter_group,
                    best["duplicate_visit_penalty"],
                    travel_minutes,
                ),
                "map_position": _stable_mock_position(place_name, order),
            }
        )
        previous_district = district

    total_minutes = _parse_minutes(request.end_time) - _parse_minutes(request.start_time)
    estimated_total_time = f"{total_minutes // 60}시간 {total_minutes % 60}분"
    place_type_diversity = len({item["place_type"] for item in timeline})
    insights = [
        "최근 방문 장소 중복을 감점하여 새로운 접촉 지점을 우선 배치했습니다."
        if request.avoid_duplicates
        else "중복 방문 감점 없이 시간대와 장소 적합도를 중심으로 배치했습니다.",
        "오전에는 교통거점, 점심에는 상권, 오후에는 현장 방문 중심으로 동선을 구성했습니다.",
        f"장소 유형 {place_type_diversity}개를 섞어 하루 일정의 메시지 접점을 넓혔습니다.",
    ]

    return {
        "summary": {
            "date": request.date,
            "day_of_week": _day_of_week(request.date),
            "start_location": request.start_location,
            "start_location_district": start_district,
            "num_visits": len(timeline),
            "estimated_total_time": estimated_total_time,
            "target_voter_group": request.target_voter_group,
            "campaign_goal": request.campaign_goal,
            "place_type_diversity": place_type_diversity,
            "avoid_duplicates": request.avoid_duplicates,
            "model": "optimized_route_planner",
        },
        "timeline": timeline,
        "insights": insights,
        "map": {
            "mode": "mock_preview",
            "start_location": request.start_location,
            "start_district": start_district,
            "note": "TODO: geocoding으로 address를 lat/lng로 변환하고 Leaflet/OpenStreetMap으로 교체",
        },
    }


def get_route_options() -> dict[str, Any]:
    return {
        "districts": SEOUL_DISTRICTS,
        "target_voter_groups": TARGET_GROUPS,
        "campaign_goals": CAMPAIGN_GOALS,
        "place_types": PLACE_TYPES,
        "default_time_slots": [
            {"label": "출근", "start": "07:30", "end": "09:30"},
            {"label": "오전", "start": "10:00", "end": "12:00"},
            {"label": "점심", "start": "12:00", "end": "14:00"},
            {"label": "오후", "start": "14:00", "end": "17:00"},
            {"label": "퇴근", "start": "17:00", "end": "20:00"},
        ],
        "default_request": get_default_route_request(),
    }


def get_default_route_request() -> dict[str, Any]:
    return {
        "date": "2026-05-20",
        "start_time": "09:00",
        "end_time": "18:00",
        "start_location": "성동구청",
        "districts": ["성동구", "중구"],
        "target_voter_group": "직장인",
        "campaign_goal": "퇴근인사",
        "preferred_place_types": ["교통거점", "골목상권", "전통시장"],
        "num_visits": 5,
        "avoid_duplicates": True,
    }


def recommend_route(payload: dict[str, Any]) -> dict[str, Any]:
    request = RouteRequestData(
        date=_clean_text(payload.get("date")) or get_default_route_request()["date"],
        start_time=_clean_text(payload.get("start_time")) or "09:00",
        end_time=_clean_text(payload.get("end_time")) or "18:00",
        start_location=_clean_text(payload.get("start_location")) or "서울시청",
        districts=[_clean_text(value) for value in payload.get("districts", []) if _clean_text(value)],
        target_voter_group=_clean_text(payload.get("target_voter_group")) or "직장인",
        campaign_goal=_clean_text(payload.get("campaign_goal")) or "퇴근인사",
        preferred_place_types=[
            _clean_text(value) for value in payload.get("preferred_place_types", []) if _clean_text(value)
        ],
        num_visits=int(payload.get("num_visits", 5)),
        avoid_duplicates=bool(payload.get("avoid_duplicates", True)),
    )

    datetime.strptime(request.date, "%Y-%m-%d")
    return _build_route(request)


@lru_cache(maxsize=1)
def get_sample_route() -> dict[str, Any]:
    return recommend_route(get_default_route_request())
