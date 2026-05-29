from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
import hashlib
import re
from typing import Any

import pandas as pd

try:
    from backend.district_utils import (
        SEOUL_DISTRICT_LIST as CANONICAL_SEOUL_DISTRICTS,
        count_district_mismatches,
        filter_dataframe_by_district,
        get_candidate_district,
        get_dataframe_district_series,
        normalize_district,
        normalize_districts,
        validate_recommendation_districts,
    )
    from backend.services.district_fallbacks import DISTRICT_FALLBACK_SEEDS
except ModuleNotFoundError:
    from district_utils import (  # type: ignore
        SEOUL_DISTRICT_LIST as CANONICAL_SEOUL_DISTRICTS,
        count_district_mismatches,
        filter_dataframe_by_district,
        get_candidate_district,
        get_dataframe_district_series,
        normalize_district,
        normalize_districts,
        validate_recommendation_districts,
    )
    from services.district_fallbacks import DISTRICT_FALLBACK_SEEDS  # type: ignore


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
    "station": "교통거점",
    "park": "공원",
    "senior_friendly": "복지시설",
    "senior": "복지시설",
    "welfare": "복지시설",
    "commercial": "골목상권",
    "public": "정책현장",
    "policy_site": "정책현장",
}

DISTRICT_COLUMN_CANDIDATES = (
    "district_normalized",
    "recommended_district",
    "district",
    "district_name",
    "region",
    "자치구",
    "시군구",
    "SIG_KOR_NM",
)

ROUTE_FALLBACK_STAGES = (
    "strict",
    "relaxed_place_type",
    "relaxed_target_purpose",
    "all_district_candidates",
    "district_fallback_seed",
    "synthetic_district_fallback",
)

ROUTE_STAGE_BONUS = {
    "strict": 0.16,
    "relaxed_place_type": 0.08,
    "relaxed_target_purpose": 0.04,
    "all_district_candidates": 0.0,
    "district_fallback_seed": -0.04,
    "synthetic_district_fallback": -0.08,
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
        district = normalize_district(value)
        if district:
            return district
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


def _processed_data_path(file_name: str) -> Path | None:
    for root in (BACKEND_ROOT, REPOSITORY_ROOT):
        path = root / "data" / "processed" / file_name
        if path.exists():
            return path
    return None


def _optional_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(numeric):
        return None
    return numeric


def _normalized_preferred_place_types(values: list[str]) -> set[str]:
    return {_normalize_place_type(value) for value in values or [] if _clean_text(value)}


def _score_from_series(series: pd.Series, base: float = 0.82, spread: float = 0.35) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").fillna(0.0).clip(lower=0.0)
    max_value = float(numeric.max()) if len(numeric) else 0.0
    if max_value <= 0:
        return pd.Series([base] * len(numeric), index=numeric.index, dtype=float)
    return base + (spread * (numeric / max_value))


def _candidate_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    columns = [
        "recommended_place_name",
        "recommended_district",
        "district_normalized",
        "recommended_place_type",
        "address",
        "lat",
        "lng",
        "latitude",
        "longitude",
        "score",
        "candidate_score",
        "candidate_source",
        "source",
        "district_match",
        "explanation",
    ]
    if not records:
        return pd.DataFrame(columns=columns)
    frame = pd.DataFrame(records)
    for column in columns:
        if column not in frame.columns:
            frame[column] = None
    return frame[columns]


def _load_subway_candidates() -> pd.DataFrame:
    path = _processed_data_path("cleaned_subway.csv")
    if not path:
        return _candidate_dataframe([])
    try:
        from backend.scripts.recommender import infer_subway_district_name
    except ModuleNotFoundError:
        try:
            from scripts.recommender import infer_subway_district_name  # type: ignore
        except ModuleNotFoundError:
            return _candidate_dataframe([])

    dataframe = pd.read_csv(path, encoding="utf-8-sig")
    if dataframe.empty:
        return _candidate_dataframe([])
    dataframe["use_month"] = pd.to_numeric(dataframe.get("use_month"), errors="coerce")
    latest_month = dataframe["use_month"].max()
    dataframe = dataframe[dataframe["use_month"] == latest_month].copy()
    dataframe["station_name"] = dataframe["station_name"].fillna("").astype(str).str.strip()
    dataframe = dataframe[dataframe["station_name"] != ""].copy()
    dataframe["recommended_district"] = dataframe["station_name"].apply(infer_subway_district_name)
    dataframe = dataframe[dataframe["recommended_district"].fillna("") != ""].copy()
    dataframe["flow_score"] = (
        pd.to_numeric(dataframe.get("morning_total_in"), errors="coerce").fillna(0.0)
        + pd.to_numeric(dataframe.get("afternoon_total_in"), errors="coerce").fillna(0.0)
    )
    dataframe["candidate_score"] = _score_from_series(dataframe["flow_score"], base=0.92, spread=0.35)

    records = []
    for _, row in dataframe.drop_duplicates(subset=["station_name"]).iterrows():
        station_name = _clean_text(row.get("station_name"))
        place_name = station_name if station_name.endswith("역") else f"{station_name}역 일대"
        district = normalize_district(row.get("recommended_district")) or _clean_text(row.get("recommended_district"))
        records.append(
            {
                "recommended_place_name": place_name,
                "recommended_district": district,
                "district_normalized": district,
                "recommended_place_type": "교통거점",
                "address": f"서울특별시 {district} {station_name}역 일대" if district else "주소 확인 필요",
                "score": float(row.get("candidate_score", 0.0)),
                "candidate_score": float(row.get("candidate_score", 0.0)),
                "candidate_source": "public_subway",
                "source": "public_subway",
            }
        )
    return _candidate_dataframe(records)


def _load_market_candidates() -> pd.DataFrame:
    path = _processed_data_path("cleaned_market.csv")
    if not path:
        return _candidate_dataframe([])
    dataframe = pd.read_csv(path, encoding="utf-8-sig")
    if dataframe.empty:
        return _candidate_dataframe([])
    dataframe["market_name"] = dataframe["market_name"].fillna("").astype(str).str.strip()
    dataframe["district_name"] = dataframe["district_name"].fillna("").astype(str).str.strip()
    dataframe["market_address"] = dataframe["market_address"].fillna("").astype(str).str.strip()
    dataframe = dataframe[(dataframe["market_name"] != "") & (dataframe["district_name"] != "")].copy()
    score_base = (
        pd.to_numeric(dataframe.get("store_count"), errors="coerce").fillna(0.0)
        + pd.to_numeric(dataframe.get("floor_area"), errors="coerce").fillna(0.0).clip(lower=0.0) / 100.0
    )
    dataframe["candidate_score"] = _score_from_series(score_base, base=0.9, spread=0.3)
    records = []
    for _, row in dataframe.iterrows():
        district = normalize_district(row.get("district_name")) or _clean_text(row.get("district_name"))
        records.append(
            {
                "recommended_place_name": row.get("market_name"),
                "recommended_district": district,
                "district_normalized": district,
                "recommended_place_type": "전통시장",
                "address": row.get("market_address") or f"서울특별시 {district} 일대",
                "score": float(row.get("candidate_score", 0.0)),
                "candidate_score": float(row.get("candidate_score", 0.0)),
                "candidate_source": "public_market",
                "source": "public_market",
            }
        )
    return _candidate_dataframe(records)


def _load_park_candidates() -> pd.DataFrame:
    path = _processed_data_path("cleaned_parks.csv")
    if not path:
        return _candidate_dataframe([])
    dataframe = pd.read_csv(path, encoding="utf-8-sig")
    if dataframe.empty:
        return _candidate_dataframe([])
    dataframe["park_name"] = dataframe["park_name"].fillna("").astype(str).str.strip()
    dataframe["region"] = dataframe["region"].fillna("").astype(str).str.strip()
    dataframe = dataframe[(dataframe["park_name"] != "") & (dataframe["region"] != "")].copy()
    dataframe["candidate_score"] = _score_from_series(
        pd.to_numeric(dataframe.get("area_sqm"), errors="coerce").fillna(0.0),
        base=0.86,
        spread=0.28,
    )
    records = []
    for _, row in dataframe.iterrows():
        district = normalize_district(row.get("region")) or _clean_text(row.get("region"))
        records.append(
            {
                "recommended_place_name": row.get("park_name"),
                "recommended_district": district,
                "district_normalized": district,
                "recommended_place_type": "공원",
                "address": row.get("park_address") or f"서울특별시 {district} 일대",
                "lat": _optional_float(row.get("latitude")),
                "lng": _optional_float(row.get("longitude")),
                "latitude": _optional_float(row.get("latitude")),
                "longitude": _optional_float(row.get("longitude")),
                "score": float(row.get("candidate_score", 0.0)),
                "candidate_score": float(row.get("candidate_score", 0.0)),
                "candidate_source": "public_park",
                "source": "public_park",
            }
        )
    return _candidate_dataframe(records)


def _load_welfare_candidates() -> pd.DataFrame:
    path = _processed_data_path("cleaned_senior.csv")
    if not path:
        return _candidate_dataframe([])
    dataframe = pd.read_csv(path, encoding="utf-8-sig")
    if dataframe.empty:
        return _candidate_dataframe([])
    dataframe["facility_name"] = dataframe["facility_name"].fillna("").astype(str).str.strip()
    dataframe["district_name"] = dataframe["district_name"].fillna("").astype(str).str.strip()
    dataframe["facility_address"] = dataframe["facility_address"].fillna("").astype(str).str.strip()
    dataframe = dataframe[(dataframe["facility_name"] != "") & (dataframe["district_name"] != "")].copy()
    dataframe["candidate_score"] = 0.88
    records = []
    for _, row in dataframe.iterrows():
        district = normalize_district(row.get("district_name")) or _clean_text(row.get("district_name"))
        records.append(
            {
                "recommended_place_name": row.get("facility_name"),
                "recommended_district": district,
                "district_normalized": district,
                "recommended_place_type": "복지시설",
                "address": row.get("facility_address") or f"서울특별시 {district} 일대",
                "score": float(row.get("candidate_score", 0.0)),
                "candidate_score": float(row.get("candidate_score", 0.0)),
                "candidate_source": "public_welfare",
                "source": "public_welfare",
            }
        )
    return _candidate_dataframe(records)


def _load_commercial_candidates() -> pd.DataFrame:
    path = _processed_data_path("cleaned_commercial_flow.csv")
    if not path:
        return _candidate_dataframe([])
    dataframe = pd.read_csv(path, encoding="utf-8-sig")
    if dataframe.empty:
        return _candidate_dataframe([])
    dataframe["commercial_name"] = dataframe["commercial_name"].fillna("").astype(str).str.strip()
    dataframe["recommended_district"] = dataframe["commercial_name"].apply(_extract_district)
    dataframe = dataframe[(dataframe["commercial_name"] != "") & (dataframe["recommended_district"] != "")].copy()
    dataframe["candidate_score"] = _score_from_series(
        pd.to_numeric(dataframe.get("total_flow"), errors="coerce").fillna(0.0),
        base=0.88,
        spread=0.32,
    )
    records = []
    for _, row in dataframe.iterrows():
        district = normalize_district(row.get("recommended_district")) or _clean_text(row.get("recommended_district"))
        records.append(
            {
                "recommended_place_name": f"{row.get('commercial_name')} 일대",
                "recommended_district": district,
                "district_normalized": district,
                "recommended_place_type": "골목상권",
                "address": f"서울특별시 {district} {row.get('commercial_name')} 일대",
                "score": float(row.get("candidate_score", 0.0)),
                "candidate_score": float(row.get("candidate_score", 0.0)),
                "candidate_source": "public_commercial",
                "source": "public_commercial",
            }
        )
    return _candidate_dataframe(records)


def _load_public_candidate_pool() -> pd.DataFrame:
    frames = [
        _load_subway_candidates(),
        _load_market_candidates(),
        _load_park_candidates(),
        _load_welfare_candidates(),
        _load_commercial_candidates(),
    ]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return _candidate_dataframe([])
    records: list[dict[str, Any]] = []
    for frame in frames:
        records.extend(frame.to_dict("records"))
    return _candidate_dataframe(records)


def _build_seed_candidate(seed: dict[str, Any], stage: str = "district_fallback_seed", order: int = 0) -> dict[str, Any]:
    district = normalize_district(seed.get("district_normalized") or seed.get("district")) or _clean_text(seed.get("district"))
    place_type = _normalize_place_type(seed.get("place_type"))
    score = float(seed.get("score") or 1.05)
    return {
        "recommended_place_name": _clean_text(seed.get("place_name")) or f"{district} 유세 거점",
        "recommended_district": district,
        "district_normalized": district,
        "recommended_place_type": place_type,
        "address": _clean_text(seed.get("address")) or f"서울특별시 {district} 일대",
        "lat": _optional_float(seed.get("lat")),
        "lng": _optional_float(seed.get("lng")),
        "latitude": _optional_float(seed.get("lat")),
        "longitude": _optional_float(seed.get("lng")),
        "score": score,
        "candidate_score": score - (order * 0.01),
        "candidate_source": seed.get("source") or stage,
        "source": seed.get("source") or stage,
        "district_match": True,
        "explanation": seed.get("explanation") or "선택한 자치구 내 기본 fallback 후보입니다.",
        "_fallback_stage": stage,
    }


def _build_district_synthetic_fallback(
    selected_districts: list[str],
    existing_candidates: list[dict[str, Any]],
    needed: int,
    preferred_place_types: list[str],
) -> list[dict[str, Any]]:
    if needed <= 0 or not selected_districts:
        return []

    existing_names = {_clean_text(candidate.get("recommended_place_name")) for candidate in existing_candidates}
    preferred = list(_normalized_preferred_place_types(preferred_place_types))
    type_cycle = preferred or ["교통거점", "골목상권", "전통시장", "공원", "정책현장"]
    synthetic: list[dict[str, Any]] = []
    sequence = 1
    while len(synthetic) < needed:
        district = selected_districts[(sequence - 1) % len(selected_districts)]
        place_name = f"{district} 생활권 유세 거점 {sequence}"
        if place_name in existing_names:
            sequence += 1
            continue
        place_type = type_cycle[(sequence - 1) % len(type_cycle)]
        synthetic.append(
            {
                "recommended_place_name": place_name,
                "recommended_district": district,
                "district_normalized": district,
                "recommended_place_type": place_type,
                "address": f"서울특별시 {district} 주요 생활권 일대",
                "lat": None,
                "lng": None,
                "latitude": None,
                "longitude": None,
                "score": 0.98,
                "candidate_score": 0.98 - (sequence * 0.01),
                "candidate_source": "synthetic_district_fallback",
                "source": "synthetic_district_fallback",
                "district_match": True,
                "explanation": "선택한 자치구 내 후보가 부족해 생성한 안전 fallback 후보입니다.",
                "_fallback_stage": "synthetic_district_fallback",
            }
        )
        sequence += 1
    return synthetic


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[float, str]:
    return (
        float(candidate.get("candidate_score") or candidate.get("score") or 0.0),
        _clean_text(candidate.get("recommended_place_name")),
    )


def _candidate_identity(candidate: dict[str, Any]) -> tuple[str, str, str]:
    return (
        re.sub(r"\s+", "", _clean_text(candidate.get("recommended_place_name"))),
        normalize_district(candidate.get("district_normalized") or candidate.get("recommended_district")) or "",
        _normalize_place_type(candidate.get("recommended_place_type")),
    )


def _filter_route_candidates(
    candidates: pd.DataFrame,
    selected_districts: list[str],
    place_types: set[str] | None = None,
) -> list[dict[str, Any]]:
    if candidates.empty:
        return []

    filtered = filter_dataframe_by_district(candidates, selected_districts, DISTRICT_COLUMN_CANDIDATES)
    if place_types:
        filtered = filtered[
            filtered["recommended_place_type"].apply(_normalize_place_type).isin(place_types)
        ].copy()
    if filtered.empty:
        return []
    records = filtered.to_dict("records")
    return sorted(records, key=_candidate_sort_key, reverse=True)


def _dedupe_candidates_preserve_order(stages: list[tuple[str, list[dict[str, Any]]]]) -> tuple[list[dict[str, Any]], str]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    stage_reaching_count = ""
    for stage, candidates in stages:
        for candidate in candidates:
            candidate = dict(candidate)
            candidate["_fallback_stage"] = candidate.get("_fallback_stage") or stage
            key = _candidate_identity(candidate)
            if key in seen:
                continue
            seen.add(key)
            merged.append(candidate)
            stage_reaching_count = stage
    return merged, stage_reaching_count


def generate_district_safe_route_candidates(
    all_candidates: pd.DataFrame,
    selected_districts: list[str],
    preferred_place_types: list[str],
    visit_count: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    selected = normalize_districts(selected_districts)
    preferred_types = _normalized_preferred_place_types(preferred_place_types)
    requested_count = max(1, int(visit_count or 5))

    strict = _filter_route_candidates(all_candidates, selected, preferred_types or None)
    relaxed_place_type = _filter_route_candidates(all_candidates, selected, None)
    relaxed_target_purpose = _filter_route_candidates(all_candidates, selected, None)
    all_district = _filter_route_candidates(all_candidates, selected, None)

    stages = [
        ("strict", strict),
        ("relaxed_place_type", relaxed_place_type),
        ("relaxed_target_purpose", relaxed_target_purpose),
        ("all_district_candidates", all_district),
    ]

    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    fallback_stage = "strict"
    reached_requested = False
    stage_counts: dict[str, int] = {}
    for stage, candidates in stages:
        added = 0
        for candidate in candidates:
            candidate = dict(candidate)
            candidate["_fallback_stage"] = stage
            key = _candidate_identity(candidate)
            if key in seen:
                continue
            seen.add(key)
            merged.append(candidate)
            added += 1
        stage_counts[stage] = len(candidates)
        if len(merged) >= requested_count and not reached_requested:
            fallback_stage = stage
            reached_requested = True

    if len(merged) < requested_count:
        seed_candidates: list[dict[str, Any]] = []
        for district in selected:
            for index, seed_item in enumerate(DISTRICT_FALLBACK_SEEDS.get(district, [])):
                seed_candidates.append(_build_seed_candidate(seed_item, "district_fallback_seed", index))
        for candidate in seed_candidates:
            key = _candidate_identity(candidate)
            if key in seen:
                continue
            seen.add(key)
            merged.append(candidate)
        stage_counts["district_fallback_seed"] = len(seed_candidates)
        if len(merged) >= requested_count:
            fallback_stage = "district_fallback_seed"
            reached_requested = True

    if len(merged) < requested_count:
        synthetic = _build_district_synthetic_fallback(
            selected,
            merged,
            requested_count - len(merged),
            preferred_place_types,
        )
        merged.extend(synthetic)
        stage_counts["synthetic_district_fallback"] = len(synthetic)
        fallback_stage = "synthetic_district_fallback"

    validated, validation_warnings = validate_recommendation_districts(merged, selected)
    candidate_frame = _candidate_dataframe(validated)
    if "_fallback_stage" not in candidate_frame.columns:
        candidate_frame["_fallback_stage"] = [candidate.get("_fallback_stage", "strict") for candidate in validated]

    debug = {
        "selected_districts": selected,
        "requested_visit_count": requested_count,
        "returned_count": min(len(candidate_frame), requested_count),
        "candidate_count_before_district_filter": int(len(all_candidates)),
        "candidate_count_after_district_filter": int(len(candidate_frame)),
        "district_filter_applied": bool(selected),
        "district_mismatch_count": count_district_mismatches(validated, selected),
        "fallback_used": fallback_stage != "strict",
        "fallback_stage": fallback_stage,
        "stage_counts": stage_counts,
        "warnings": validation_warnings,
    }
    return candidate_frame.reset_index(drop=True), debug


def _district_relation(previous_district: str, current_district: str) -> str:
    previous_district = normalize_district(previous_district) or _clean_text(previous_district)
    current_district = normalize_district(current_district) or _clean_text(current_district)
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
    candidate_district = normalize_district(candidate_district) or _clean_text(candidate_district)
    preferred_districts = normalize_districts(preferred_districts)
    if not preferred_districts:
        return 0.08
    if candidate_district in preferred_districts:
        return 0.22
    if any(_district_relation(candidate_district, district) == "adjacent" for district in preferred_districts):
        return 0.10
    return 0.0


@lru_cache(maxsize=1)
def _load_candidate_pool() -> pd.DataFrame:
    frames = []
    try:
        optimized = _read_csv(OPTIMIZED_RECOMMENDATIONS_PATH)
    except FileNotFoundError:
        optimized = pd.DataFrame()
    try:
        raw = _read_csv(RAW_BASELINE_PATH)
    except FileNotFoundError:
        raw = pd.DataFrame()

    if not optimized.empty:
        optimized_candidates = optimized.copy()
        optimized_candidates["candidate_score"] = pd.to_numeric(
            optimized_candidates.get("score"),
            errors="coerce",
        ).fillna(0.0)
        optimized_candidates["source"] = "backend_api"
        if "candidate_source" not in optimized_candidates.columns:
            optimized_candidates["candidate_source"] = "optimized_recommendations"
        frames.append(optimized_candidates)

    if not raw.empty:
        raw_candidates = raw.copy()
        raw_candidates["score"] = pd.to_numeric(raw_candidates.get("baseline_score"), errors="coerce").fillna(0.0)
        raw_candidates["candidate_score"] = raw_candidates["score"]
        raw_candidates["source"] = "backend_api"
        if "candidate_source" not in raw_candidates.columns:
            raw_candidates["candidate_source"] = "raw_baseline"
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

    public_candidates = _load_public_candidate_pool()
    if not public_candidates.empty:
        frames.append(public_candidates)

    if not frames:
        return _candidate_dataframe([])

    candidates = pd.concat(frames, ignore_index=True, sort=False)
    for column in ["recommended_place_name", "recommended_district", "recommended_place_type", "address"]:
        if column not in candidates.columns:
            candidates[column] = ""
    candidates["recommended_place_name"] = candidates["recommended_place_name"].fillna("").astype(str).str.strip()
    candidates = candidates[candidates["recommended_place_name"] != ""].copy()
    candidates["recommended_district"] = candidates["recommended_district"].apply(_clean_text)
    candidates["district_normalized"] = get_dataframe_district_series(
        candidates,
        DISTRICT_COLUMN_CANDIDATES,
    )
    candidates["recommended_district"] = candidates["district_normalized"].fillna(candidates["recommended_district"])
    candidates["recommended_place_type"] = candidates["recommended_place_type"].apply(_normalize_place_type)
    candidates["candidate_score"] = pd.to_numeric(candidates["candidate_score"], errors="coerce").fillna(0.0)
    candidates["score"] = pd.to_numeric(candidates.get("score"), errors="coerce").fillna(candidates["candidate_score"])
    candidates["source"] = candidates.get("source", "backend_api").fillna("backend_api").astype(str)
    candidates["candidate_source"] = candidates.get("candidate_source", candidates["source"]).fillna(candidates["source"]).astype(str)

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
    visits["district"] = visits["district"].fillna("").astype(str).str.strip().apply(
        lambda value: normalize_district(value) or value
    )
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
    district = get_candidate_district(candidate) or _clean_text(candidate.get("recommended_district"))
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
    district = get_candidate_district(candidate) or _clean_text(candidate.get("recommended_district"))
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
    district = get_candidate_district(candidate) or _clean_text(candidate.get("recommended_district"))
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
    district = get_candidate_district(candidate) or _clean_text(candidate.get("recommended_district"))
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
    selected_request_districts = normalize_districts(request.districts)
    selected_request_district_set = set(selected_request_districts)
    start_district = infer_start_location_district(request.start_location) or (
        selected_request_districts[0] if selected_request_districts else ""
    )
    start_district = normalize_district(start_district) or start_district

    preferred_place_types = _normalized_preferred_place_types(request.preferred_place_types)
    selected_names: set[str] = set()
    selected_types: set[str] = set()
    selected_districts: set[str] = set()
    selected_district_counts: dict[str, int] = {}
    selected_type_counts: dict[str, int] = {}
    previous_district = start_district
    timeline = []
    warnings: list[str] = []

    filtered, candidate_debug = generate_district_safe_route_candidates(
        candidates,
        selected_request_districts,
        request.preferred_place_types,
        request.num_visits,
    )
    warnings.extend(candidate_debug.get("warnings", []))
    if selected_request_districts and candidate_debug.get("fallback_used"):
        if candidate_debug.get("fallback_stage") == "district_fallback_seed":
            warnings.append("선택한 자치구 내 기본 후보를 사용했습니다.")
        elif candidate_debug.get("fallback_stage") == "synthetic_district_fallback":
            warnings.append("선택한 자치구 내 기본 후보도 부족하여 안전 fallback 후보를 생성했습니다.")
        else:
            warnings.append("선택한 자치구 내 후보가 부족하여 일부 조건을 완화했습니다.")

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
            district = get_candidate_district(candidate) or _clean_text(candidate.get("recommended_district"))
            optimized_place_score = float(candidate.get("candidate_score", 0.0))
            time_score = _time_slot_fit(time_value, place_type, request.campaign_goal)
            target_score = _target_fit(request.target_voter_group, place_type, place_name)
            district_score = _district_fit(district, selected_request_districts)
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
            fallback_stage = _clean_text(candidate.get("_fallback_stage")) or "strict"
            stage_bonus = ROUTE_STAGE_BONUS.get(fallback_stage, 0.0)
            route_score = (
                optimized_place_score
                + time_score
                + target_score
                + district_score
                + start_score
                + diversity_score
                + duplicate_penalty
                + travel_penalty
                + stage_bonus
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
                    "stage_bonus": stage_bonus,
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
        district = get_candidate_district(candidate) or _clean_text(candidate.get("recommended_district"))
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
            "stage_bonus": best["stage_bonus"],
        }
        lat = _optional_float(candidate.get("lat")) or _optional_float(candidate.get("latitude"))
        lng = _optional_float(candidate.get("lng")) or _optional_float(candidate.get("longitude"))
        map_position = {"lat": lat, "lng": lng} if lat is not None and lng is not None else _stable_mock_position(place_name, order)
        candidate_source = _clean_text(candidate.get("candidate_source")) or _clean_text(candidate.get("source")) or "backend_api"
        fallback_stage = _clean_text(candidate.get("_fallback_stage")) or "strict"
        timeline.append(
            {
                "order": order,
                "time": time_value,
                "place_name": place_name,
                "district": district,
                "district_normalized": district,
                "district_match": district in selected_request_district_set if selected_request_district_set else True,
                "place_type": place_type,
                "address": _normalize_address(candidate.get("address")),
                "candidate_source": candidate_source,
                "source": candidate_source,
                "fallback_stage": fallback_stage,
                "lat": lat,
                "lng": lng,
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
                "map_position": map_position,
            }
        )
        previous_district = district

    district_removed_count = count_district_mismatches(timeline, selected_request_districts)
    timeline, validation_warnings = validate_recommendation_districts(timeline, selected_request_districts)
    warnings.extend(validation_warnings)
    if timeline and any(item.get("lat") is None or item.get("lng") is None for item in timeline):
        warnings.append("좌표가 없는 후보는 지도에 권역 기준 위치로 표시되며, 타임라인에는 정상 표시됩니다.")
    if len(timeline) < request.num_visits:
        warnings.append(
            "Returned "
            + str(len(timeline))
            + " recommendations because selected district candidates were insufficient for requested "
            + str(request.num_visits)
            + " visits."
        )
    warnings = list(dict.fromkeys(warnings))
    district_mismatch_count = count_district_mismatches(timeline, selected_request_districts)

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
        "debug": {
            "source": "backend_api",
            "selected_districts": selected_request_districts,
            "requested_visit_count": request.num_visits,
            "returned_count": len(timeline),
            "candidate_count_before_district_filter": candidate_debug.get("candidate_count_before_district_filter", 0),
            "candidate_count_after_district_filter": candidate_debug.get("candidate_count_after_district_filter", 0),
            "district_filter_applied": bool(selected_request_districts),
            "district_mismatch_count": district_mismatch_count,
            "district_removed_count": district_removed_count,
            "fallback_used": bool(candidate_debug.get("fallback_used")),
            "fallback_stage": candidate_debug.get("fallback_stage", "strict"),
            "stage_counts": candidate_debug.get("stage_counts", {}),
            "candidate_sources": sorted({item.get("source") for item in timeline if item.get("source")}),
            "warnings": warnings,
        },
        "map": {
            "mode": "mock_preview",
            "start_location": request.start_location,
            "start_district": start_district,
            "note": "TODO: geocoding으로 address를 lat/lng로 변환하고 Leaflet/OpenStreetMap으로 교체",
        },
    }


def get_route_options() -> dict[str, Any]:
    return {
        "districts": CANONICAL_SEOUL_DISTRICTS,
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


def _coerce_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [_clean_text(value)] if _clean_text(value) else []
    if isinstance(value, (list, tuple, set)):
        return [_clean_text(item) for item in value if _clean_text(item)]
    return [_clean_text(value)] if _clean_text(value) else []


def _payload_districts(payload: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("districts", "district", "selectedDistricts", "selected_districts"):
        values.extend(_coerce_text_list(payload.get(key)))
    return normalize_districts(values)


def recommend_route(payload: dict[str, Any]) -> dict[str, Any]:
    request = RouteRequestData(
        date=_clean_text(payload.get("date")) or get_default_route_request()["date"],
        start_time=_clean_text(payload.get("start_time")) or "09:00",
        end_time=_clean_text(payload.get("end_time")) or "18:00",
        start_location=_clean_text(payload.get("start_location")) or "서울시청",
        districts=_payload_districts(payload),
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
