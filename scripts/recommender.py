import json
from math import log
from pathlib import Path
import re

import pandas as pd


PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
AUX_SUMMARY_PATH = PROCESSED_DIR / "aux_feature_summary.json"
AUXILIARY_ADJUSTMENT_STRENGTH = 0.12
FEATURE_COLUMNS = [
    "time_match_score",
    "age_match_score",
    "context_score",
    "facility_score",
    "interaction_score",
]

PLACE_TYPE_WEIGHTS = {
    "subway": {
        "time_match_score": 0.45,
        "age_match_score": 0.17,
        "context_score": 0.18,
        "facility_score": 0.05,
        "interaction_score": 0.15,
    },
    "park": {
        "time_match_score": 0.08,
        "age_match_score": 0.14,
        "context_score": 0.25,
        "facility_score": 0.38,
        "interaction_score": 0.15,
    },
    "senior": {
        "time_match_score": 0.08,
        "age_match_score": 0.27,
        "context_score": 0.18,
        "facility_score": 0.32,
        "interaction_score": 0.15,
    },
    "market": {
        "time_match_score": 0.12,
        "age_match_score": 0.18,
        "context_score": 0.18,
        "facility_score": 0.37,
        "interaction_score": 0.15,
    },
}

SEOUL_DISTRICTS = {
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
}

SUBWAY_DISTRICT_MAP = {
    "강남": "강남구",
    "건대입구": "광진구",
    "가산디지털단지": "금천구",
    "까치산": "강서구",
    "고속터미널": "서초구",
    "구로디지털단지": "구로구",
    "구의": "광진구",
    "구의(광진구청)": "광진구",
    "낙성대": "관악구",
    "낙성대(강감찬)": "관악구",
    "노원": "노원구",
    "당산": "영등포구",
    "명동": "중구",
    "봉천": "관악구",
    "사당": "동작구",
    "삼성": "강남구",
    "삼성(무역센터)": "강남구",
    "서울역": "중구",
    "서울대입구": "관악구",
    "서울대입구(관악구청)": "관악구",
    "성수": "성동구",
    "선릉": "강남구",
    "수유": "강북구",
    "수유(강북구청)": "강북구",
    "신대방": "동작구",
    "신도림": "구로구",
    "신림": "관악구",
    "쌍문": "도봉구",
    "여의도": "영등포구",
    "역삼": "강남구",
    "연신내": "은평구",
    "영등포": "영등포구",
    "용산": "용산구",
    "을지로입구": "중구",
    "잠실": "송파구",
    "잠실(송파구청)": "송파구",
    "종각": "종로구",
    "청량리": "동대문구",
    "합정": "마포구",
    "홍대입구": "마포구",
    "화곡": "강서구",
    "혜화": "종로구",
}

SUBWAY_STATION_DISTRICT_MAP = SUBWAY_DISTRICT_MAP

PARK_FEATURE_KEYWORDS = ["광장", "야외무대", "문화", "체육", "산책로"]
SENIOR_FEATURE_KEYWORDS = ["노인복지관", "종합복지관", "노인교실", "복지센터"]
SENIOR_KEYWORD_WEIGHTS = {
    "노인복지관": 0.45,
    "종합복지관": 0.35,
    "노인교실": 0.30,
    "복지센터": 0.25,
}


def load_cleaned_csv(file_name: str) -> pd.DataFrame:
    file_path = PROCESSED_DIR / file_name
    if not file_path.exists():
        raise FileNotFoundError(f"cleaned file not found: {file_path}")

    return pd.read_csv(file_path, encoding="utf-8-sig")


def load_aux_feature_summary() -> dict[str, float]:
    try:
        with AUX_SUMMARY_PATH.open("r", encoding="utf-8") as file:
            raw_data = json.load(file)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}

    summary: dict[str, float] = {}
    for key, value in raw_data.items():
        try:
            summary[key] = float(value)
        except (TypeError, ValueError):
            continue

    return summary


def normalize_time_slot(time_slot: str) -> str:
    normalized = str(time_slot).strip().lower()

    if "morning" in normalized:
        return "morning"
    if "afternoon" in normalized:
        return "afternoon"

    raise ValueError("time_slot must include 'morning' or 'afternoon'")


def normalize_place_type(place_type: str) -> str:
    normalized = str(place_type).strip().lower()

    if normalized == "subway":
        return "subway"
    if normalized == "park":
        return "park"
    if normalized == "market":
        return "market"
    if normalized in {"senior", "senior_friendly"}:
        return "senior"

    raise ValueError("place_type must be one of: subway, park, market, senior_friendly")


def normalize_series(series: pd.Series) -> pd.Series:
    numeric_series = pd.to_numeric(series, errors="coerce").fillna(0.0)
    max_value = float(numeric_series.max()) if len(numeric_series) else 0.0
    if max_value <= 0:
        return pd.Series(0.0, index=series.index, dtype=float)
    return (numeric_series / max_value).clip(lower=0.0, upper=1.0)


def clamp_score(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def clamp_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0).clip(lower=0.0, upper=1.0)


def get_summary_normalized_value(summary: dict[str, float], key_prefix: str) -> float | None:
    mean_value = summary.get(f"{key_prefix}_mean")
    min_value = summary.get(f"{key_prefix}_min")
    max_value = summary.get(f"{key_prefix}_max")

    if mean_value is None:
        return None

    if min_value is None or max_value is None or max_value <= min_value:
        return clamp_score(mean_value)

    normalized_value = (mean_value - min_value) / (max_value - min_value)
    return clamp_score(normalized_value)


def apply_auxiliary_adjustment(
    base_value: float,
    auxiliary_value: float | None,
    strength: float = AUXILIARY_ADJUSTMENT_STRENGTH,
) -> float:
    if auxiliary_value is None:
        return clamp_score(base_value)

    adjusted_value = float(base_value) + (strength * (auxiliary_value - 0.5))
    return clamp_score(adjusted_value)


def blend_auxiliary_values(*auxiliary_values: float | None) -> float | None:
    available_values = [value for value in auxiliary_values if value is not None]
    if not available_values:
        return None

    return sum(available_values) / len(available_values)


def apply_series_auxiliary_adjustment(
    dataframe: pd.DataFrame,
    column_name: str,
    auxiliary_value: float | None,
) -> None:
    dataframe[column_name] = dataframe[column_name].apply(
        lambda value: apply_auxiliary_adjustment(value, auxiliary_value)
    )


def add_auxiliary_note(auxiliary_notes: list[str], auxiliary_value: float | None, note: str) -> None:
    if auxiliary_value is not None and note not in auxiliary_notes:
        auxiliary_notes.append(note)


def get_living_age_aux(summary: dict[str, float], target_age_group: str) -> float | None:
    if target_age_group == "20_40":
        return get_summary_normalized_value(summary, "living_pop_20_40_ratio")
    if target_age_group == "60_plus":
        return get_summary_normalized_value(summary, "living_pop_60_plus_ratio")

    return None


def get_living_context_aux(summary: dict[str, float], time_slot: str) -> float | None:
    key_prefix = "living_pop_morning_score" if time_slot == "morning" else "living_pop_afternoon_score"
    return get_summary_normalized_value(summary, key_prefix)


def apply_weighted_score(dataframe: pd.DataFrame, place_type: str) -> pd.DataFrame:
    weights = PLACE_TYPE_WEIGHTS[place_type]
    dataframe["final_score"] = 0.0

    for feature_name in FEATURE_COLUMNS:
        dataframe["final_score"] += dataframe[feature_name] * weights[feature_name]

    return dataframe


def extract_matching_keywords(text: str, keywords: list[str]) -> list[str]:
    value = str(text)
    return [keyword for keyword in keywords if keyword in value]


def normalize_text(value: object) -> str:
    return str(value).strip()


def optional_text(value: object) -> str | None:
    text = normalize_text(value)
    return text or None


def optional_float(value: object) -> float | None:
    numeric_value = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric_value):
        return None

    return float(numeric_value)


def extract_district_name(*values: object) -> str | None:
    for value in values:
        text = normalize_text(value)
        if not text:
            continue

        match = re.search(r"([가-힣]+구)", text)
        if match:
            return match.group(1)

    return None


def infer_subway_district_name(station_name: object) -> str | None:
    normalized_name = normalize_text(station_name)
    if not normalized_name:
        return None

    direct_match = SUBWAY_STATION_DISTRICT_MAP.get(normalized_name)
    if direct_match:
        return direct_match

    extracted_district = extract_district_name(normalized_name)
    if extracted_district:
        return extracted_district

    base_name = re.sub(r"\(.*?\)", "", normalized_name).strip()
    if not base_name:
        return None

    return SUBWAY_STATION_DISTRICT_MAP.get(base_name)


def build_place_result(
    row: pd.Series,
    place_id: object,
    name: object,
    place_type: str,
    score: float,
    reason: list[str],
    district_name: object = None,
    latitude: object = None,
    longitude: object = None,
) -> dict:
    return {
        "place_id": optional_text(place_id),
        "name": normalize_text(name),
        "place_type": place_type,
        "district_name": extract_district_name(district_name),
        "latitude": optional_float(latitude),
        "longitude": optional_float(longitude),
        "score": round(float(score), 4),
        "reason": reason,
    }


def add_subway_interaction_features(
    dataframe: pd.DataFrame,
    time_slot: str,
    target_age_group: str,
) -> None:
    audience_synergy = 1.0 if target_age_group == "20_40" else 0.60
    time_synergy = 1.0 if (time_slot == "morning" and target_age_group == "20_40") else 0.78
    dataframe["interaction_score"] = clamp_series(
        (0.45 * dataframe["time_match_score"])
        + (0.25 * dataframe["context_score"])
        + (0.15 * dataframe["age_match_score"])
        + (0.15 * time_synergy * audience_synergy)
    )

    interaction_reason = (
        "commuter timing and working-age audience synergy"
        if target_age_group == "20_40"
        else "broad transit exposure interaction for mixed-age outreach"
    )
    dataframe["interaction_reason"] = interaction_reason


def add_park_interaction_features(
    dataframe: pd.DataFrame,
    time_slot: str,
    target_age_group: str,
) -> None:
    keyword_density = dataframe["matched_keywords"].apply(
        lambda values: len(values) / len(PARK_FEATURE_KEYWORDS)
    )
    audience_synergy = 1.0 if target_age_group == "20_40" else 0.78
    time_synergy = 1.0 if time_slot == "afternoon" else 0.75
    dataframe["interaction_score"] = clamp_series(
        (0.20 * dataframe["time_match_score"])
        + (0.22 * dataframe["age_match_score"])
        + (0.23 * dataframe["context_score"])
        + (0.20 * dataframe["facility_score"])
        + (0.15 * keyword_density * time_synergy * audience_synergy)
    )

    if target_age_group == "20_40" and time_slot == "afternoon":
        interaction_reason = "afternoon leisure context and working-age outreach synergy"
    elif time_slot == "afternoon":
        interaction_reason = "afternoon park footfall and neighborhood outreach synergy"
    else:
        interaction_reason = "park amenity context interaction applied"
    dataframe["interaction_reason"] = interaction_reason


def add_senior_interaction_features(
    dataframe: pd.DataFrame,
    time_slot: str,
    target_age_group: str,
) -> None:
    keyword_presence = dataframe["matched_keywords"].apply(lambda values: 1.0 if values else 0.55)
    audience_synergy = 1.0 if target_age_group == "60_plus" else 0.65
    time_synergy = 1.0 if time_slot == "afternoon" else 0.82
    dataframe["interaction_score"] = clamp_series(
        (0.18 * dataframe["time_match_score"])
        + (0.30 * dataframe["age_match_score"])
        + (0.17 * dataframe["context_score"])
        + (0.20 * dataframe["facility_score"])
        + (0.15 * keyword_presence * time_synergy * audience_synergy)
    )

    if target_age_group == "60_plus":
        interaction_reason = "afternoon senior welfare context and 60_plus outreach synergy"
    else:
        interaction_reason = "senior-friendly facility interaction applied"
    dataframe["interaction_reason"] = interaction_reason


def add_market_interaction_features(
    dataframe: pd.DataFrame,
    time_slot: str,
    target_age_group: str,
) -> None:
    market_type_bonus = dataframe["market_type"].apply(
        lambda value: 1.0 if "골목형" in value else 0.85 if "건물형" in value else 0.70
    )
    audience_synergy = 1.0 if target_age_group == "60_plus" else 0.80
    time_synergy = 1.0 if time_slot == "afternoon" else 0.72
    dataframe["interaction_score"] = clamp_series(
        (0.18 * dataframe["time_match_score"])
        + (0.22 * dataframe["age_match_score"])
        + (0.20 * dataframe["context_score"])
        + (0.25 * dataframe["facility_score"])
        + (0.15 * market_type_bonus * time_synergy * audience_synergy)
    )

    if target_age_group == "60_plus" and time_slot == "afternoon":
        interaction_reason = "afternoon market activity and senior neighborhood outreach synergy"
    elif time_slot == "afternoon":
        interaction_reason = "afternoon market activity and working-age neighborhood contact synergy"
    else:
        interaction_reason = "market context interaction applied"
    dataframe["interaction_reason"] = interaction_reason


def build_subway_reason(
    row: pd.Series,
    time_slot: str,
    latest_month: int,
    auxiliary_notes: list[str],
) -> list[str]:
    reason = [
        f"time_match_score={row['time_match_score']:.2f} from {time_slot} rider volume in latest month {latest_month}",
        f"age_match_score={row['age_match_score']:.2f} for target outreach fit",
        f"context_score={row['context_score']:.2f} from overall station exposure",
        f"facility_score={row['facility_score']:.2f} for baseline transit visibility",
        f"interaction_score={row['interaction_score']:.2f} from {row['interaction_reason']}",
    ]

    if row["age_match_score"] >= 0.95:
        reason.append("suitable for working-age outreach")

    reason.extend(auxiliary_notes)
    return reason


def build_park_reason(
    row: pd.Series,
    time_slot: str,
    target_age_group: str,
    auxiliary_notes: list[str],
) -> list[str]:
    reason = [
        f"time_match_score={row['time_match_score']:.2f} because parks fit {time_slot} outreach",
        f"age_match_score={row['age_match_score']:.2f} for target group {target_age_group}",
        f"context_score={row['context_score']:.2f} from place context and district fit",
        f"facility_score={row['facility_score']:.2f} from park scale and facilities",
        f"interaction_score={row['interaction_score']:.2f} from {row['interaction_reason']}",
    ]

    if row["matched_keywords"]:
        reason.append(f"context keyword match: {', '.join(row['matched_keywords'])}")

    if row["region"] not in SEOUL_DISTRICTS:
        reason.append("non-Seoul district penalty applied")
    else:
        reason.append("located in a Seoul district")

    reason.extend(auxiliary_notes)
    return reason


def build_senior_reason(
    row: pd.Series,
    time_slot: str,
    target_age_group: str,
    auxiliary_notes: list[str],
) -> list[str]:
    reason = [
        f"time_match_score={row['time_match_score']:.2f} for {time_slot} senior outreach timing",
        f"age_match_score={row['age_match_score']:.2f} for target group {target_age_group}",
        f"context_score={row['context_score']:.2f} from district and address context",
        f"facility_score={row['facility_score']:.2f} from facility keyword relevance",
        f"interaction_score={row['interaction_score']:.2f} from {row['interaction_reason']}",
    ]

    if row["matched_keywords"]:
        reason.append(f"facility keyword match: {', '.join(row['matched_keywords'])}")
    else:
        reason.append("basic senior-friendly facility match")

    reason.append("district diversity applied")
    reason.extend(auxiliary_notes)
    return reason


def build_market_reason(
    row: pd.Series,
    time_slot: str,
    target_age_group: str,
    auxiliary_notes: list[str],
) -> list[str]:
    reason = [
        f"time_match_score={row['time_match_score']:.2f} for {time_slot} market outreach timing",
        f"age_match_score={row['age_match_score']:.2f} for target group {target_age_group}",
        f"context_score={row['context_score']:.2f} from market type and local context",
        f"facility_score={row['facility_score']:.2f} from store count and floor area",
        f"interaction_score={row['interaction_score']:.2f} from {row['interaction_reason']}",
        f"market type: {row['market_type']}",
        f"district: {row['district_name']}",
    ]

    reason.extend(auxiliary_notes)
    return reason


def recommend_subway(time_slot: str, target_age_group: str, top_n: int = 3) -> list[dict]:
    slot = normalize_time_slot(time_slot)
    dataframe = load_cleaned_csv("cleaned_subway.csv")
    aux_summary = load_aux_feature_summary()
    auxiliary_notes: list[str] = []

    dataframe["use_month"] = pd.to_numeric(dataframe["use_month"], errors="coerce")
    dataframe["morning_total_in"] = pd.to_numeric(dataframe["morning_total_in"], errors="coerce").fillna(0)
    dataframe["afternoon_total_in"] = pd.to_numeric(dataframe["afternoon_total_in"], errors="coerce").fillna(0)
    dataframe["station_name"] = dataframe["station_name"].fillna("").astype(str).str.strip()

    latest_month = int(dataframe["use_month"].max())
    latest_data = dataframe[dataframe["use_month"] == latest_month].copy()
    latest_data = latest_data[latest_data["station_name"] != ""].copy()

    selected_flow_column = "morning_total_in" if slot == "morning" else "afternoon_total_in"
    latest_data["selected_flow"] = latest_data[selected_flow_column]
    latest_data["all_day_flow"] = latest_data["morning_total_in"] + latest_data["afternoon_total_in"]

    latest_data["time_match_score"] = normalize_series(latest_data["selected_flow"])
    latest_data["age_match_score"] = 1.0 if target_age_group == "20_40" else 0.55
    latest_data["context_score"] = normalize_series(latest_data["all_day_flow"])
    latest_data["facility_score"] = 0.60
    latest_data["district_name"] = latest_data["station_name"].apply(infer_subway_district_name)

    worker_age_aux = None
    if target_age_group == "20_40":
        worker_age_aux = get_summary_normalized_value(
            aux_summary,
            "worker_age_20_40_ratio",
        )
    living_age_aux = get_living_age_aux(aux_summary, target_age_group)
    blended_age_aux = blend_auxiliary_values(worker_age_aux, living_age_aux)
    apply_series_auxiliary_adjustment(latest_data, "age_match_score", blended_age_aux)
    add_auxiliary_note(
        auxiliary_notes,
        worker_age_aux,
        "auxiliary worker population age match applied",
    )
    add_auxiliary_note(
        auxiliary_notes,
        living_age_aux,
        "auxiliary living population age match applied",
    )

    commercial_context_aux = get_summary_normalized_value(
        aux_summary,
        "commercial_morning_flow_score" if slot == "morning" else "commercial_afternoon_flow_score",
    )
    living_context_aux = get_living_context_aux(aux_summary, slot)
    blended_context_aux = blend_auxiliary_values(commercial_context_aux, living_context_aux)
    apply_series_auxiliary_adjustment(latest_data, "context_score", blended_context_aux)
    add_auxiliary_note(
        auxiliary_notes,
        commercial_context_aux,
        "auxiliary commercial flow context applied",
    )
    add_auxiliary_note(
        auxiliary_notes,
        living_context_aux,
        "auxiliary living population context applied",
    )

    add_subway_interaction_features(latest_data, slot, target_age_group)
    latest_data = apply_weighted_score(latest_data, "subway")
    latest_data = latest_data.sort_values(
        by=["final_score", "station_name"],
        ascending=[False, True],
    )
    latest_data = latest_data.drop_duplicates(subset=["station_name"]).head(top_n)

    results = []
    for _, row in latest_data.iterrows():
        results.append(
            build_place_result(
                row=row,
                place_id=row.get("station_id"),
                name=row.get("station_name"),
                place_type="subway",
                district_name=row.get("district_name"),
                latitude=None,
                longitude=None,
                score=float(row["final_score"]),
                reason=build_subway_reason(row, slot, latest_month, auxiliary_notes),
            )
        )

    return results


def recommend_parks(time_slot: str, target_age_group: str, top_n: int = 3) -> list[dict]:
    slot = normalize_time_slot(time_slot)
    dataframe = load_cleaned_csv("cleaned_parks.csv")
    aux_summary = load_aux_feature_summary()
    auxiliary_notes: list[str] = []

    dataframe["park_name"] = dataframe["park_name"].fillna("").astype(str).str.strip()
    dataframe["region"] = dataframe["region"].fillna("").astype(str).str.strip()
    dataframe["main_facilities"] = dataframe["main_facilities"].fillna("").astype(str)
    dataframe["area_sqm"] = pd.to_numeric(dataframe["area_sqm"], errors="coerce").fillna(0)

    dataframe = dataframe[dataframe["park_name"] != ""].copy()
    dataframe["facility_text_length"] = dataframe["main_facilities"].str.len()
    dataframe["matched_keywords"] = dataframe["main_facilities"].apply(
        lambda value: extract_matching_keywords(value, PARK_FEATURE_KEYWORDS)
    )
    dataframe["log_area"] = dataframe["area_sqm"].clip(lower=1).apply(log)

    area_score = normalize_series(dataframe["log_area"])
    facility_text_score = normalize_series(dataframe["facility_text_length"])
    keyword_score = dataframe["matched_keywords"].apply(
        lambda values: len(values) / len(PARK_FEATURE_KEYWORDS)
    )
    region_score = dataframe["region"].apply(
        lambda value: 1.0 if value in SEOUL_DISTRICTS else 0.45
    )

    dataframe["time_match_score"] = 1.0 if slot == "afternoon" else 0.75
    dataframe["age_match_score"] = 1.0 if target_age_group == "20_40" else 0.70
    dataframe["context_score"] = (0.65 * region_score) + (0.35 * keyword_score)
    dataframe["facility_score"] = (0.75 * area_score) + (0.25 * facility_text_score)

    commercial_age_aux = None
    if target_age_group == "20_40":
        commercial_age_aux = get_summary_normalized_value(
            aux_summary,
            "commercial_age_20_40_ratio",
        )
    elif target_age_group == "60_plus":
        commercial_age_aux = get_summary_normalized_value(
            aux_summary,
            "commercial_age_60_plus_ratio",
        )
    living_age_aux = get_living_age_aux(aux_summary, target_age_group)
    blended_age_aux = blend_auxiliary_values(commercial_age_aux, living_age_aux)
    apply_series_auxiliary_adjustment(dataframe, "age_match_score", blended_age_aux)
    add_auxiliary_note(
        auxiliary_notes,
        commercial_age_aux,
        "auxiliary commercial age match applied",
    )
    add_auxiliary_note(
        auxiliary_notes,
        living_age_aux,
        "auxiliary living population age match applied",
    )

    commercial_context_aux = None
    if slot == "afternoon":
        commercial_context_aux = get_summary_normalized_value(
            aux_summary,
            "commercial_afternoon_flow_score",
        )
    living_context_aux = get_living_context_aux(aux_summary, slot)
    blended_context_aux = blend_auxiliary_values(commercial_context_aux, living_context_aux)
    apply_series_auxiliary_adjustment(dataframe, "context_score", blended_context_aux)
    add_auxiliary_note(
        auxiliary_notes,
        commercial_context_aux,
        "auxiliary commercial flow context applied",
    )
    add_auxiliary_note(
        auxiliary_notes,
        living_context_aux,
        "auxiliary living population context applied",
    )

    add_park_interaction_features(dataframe, slot, target_age_group)
    dataframe = apply_weighted_score(dataframe, "park")
    dataframe = dataframe.sort_values(
        by=["final_score", "park_name"],
        ascending=[False, True],
    ).head(top_n)

    results = []
    for _, row in dataframe.iterrows():
        results.append(
            build_place_result(
                row=row,
                place_id=row.get("park_id"),
                name=row.get("park_name"),
                place_type="park",
                district_name=row.get("region") or row.get("park_address"),
                latitude=row.get("latitude"),
                longitude=row.get("longitude"),
                score=float(row["final_score"]),
                reason=build_park_reason(row, slot, target_age_group, auxiliary_notes),
            )
        )

    return results


def recommend_senior(time_slot: str, target_age_group: str, top_n: int = 3) -> list[dict]:
    slot = normalize_time_slot(time_slot)
    dataframe = load_cleaned_csv("cleaned_senior.csv")
    aux_summary = load_aux_feature_summary()
    auxiliary_notes: list[str] = []

    dataframe["facility_name"] = dataframe["facility_name"].fillna("").astype(str).str.strip()
    dataframe["district_name"] = dataframe["district_name"].fillna("").astype(str).str.strip()
    dataframe["facility_type"] = dataframe["facility_type"].fillna("").astype(str).str.strip()
    dataframe["facility_address"] = dataframe["facility_address"].fillna("").astype(str).str.strip()

    dataframe = dataframe[
        (dataframe["facility_name"] != "")
        & (dataframe["district_name"] != "")
        & (dataframe["facility_type"] != "")
    ].copy()

    dataframe["matched_keywords"] = dataframe.apply(
        lambda row: extract_matching_keywords(
            f"{row['facility_name']} {row['facility_type']}",
            SENIOR_FEATURE_KEYWORDS,
        ),
        axis=1,
    )
    dataframe["keyword_raw"] = dataframe["matched_keywords"].apply(
        lambda values: sum(SENIOR_KEYWORD_WEIGHTS[keyword] for keyword in values)
    )
    dataframe["name_length"] = dataframe["facility_name"].str.len()
    dataframe["data_completeness"] = dataframe.apply(
        lambda row: 1.0 if row["district_name"] and row["facility_address"] else 0.50,
        axis=1,
    )

    keyword_norm = normalize_series(dataframe["keyword_raw"])
    name_length_norm = normalize_series(dataframe["name_length"])
    keyword_presence = dataframe["matched_keywords"].apply(lambda values: 1.0 if values else 0.40)

    dataframe["time_match_score"] = 1.0 if slot == "afternoon" else 0.85
    dataframe["age_match_score"] = 1.0 if target_age_group == "60_plus" else 0.45
    dataframe["context_score"] = (0.80 * dataframe["data_completeness"]) + (0.20 * name_length_norm)
    dataframe["facility_score"] = (0.65 * keyword_presence) + (0.35 * keyword_norm)

    commercial_age_aux = None
    worker_age_aux = None
    if target_age_group == "60_plus":
        commercial_age_aux = get_summary_normalized_value(
            aux_summary,
            "commercial_age_60_plus_ratio",
        )
        worker_age_aux = get_summary_normalized_value(
            aux_summary,
            "worker_age_60_plus_ratio",
        )
    living_age_aux = get_living_age_aux(aux_summary, target_age_group)
    blended_age_aux = blend_auxiliary_values(
        commercial_age_aux,
        worker_age_aux,
        living_age_aux,
    )
    apply_series_auxiliary_adjustment(dataframe, "age_match_score", blended_age_aux)
    add_auxiliary_note(
        auxiliary_notes,
        commercial_age_aux,
        "auxiliary commercial age match applied",
    )
    add_auxiliary_note(
        auxiliary_notes,
        worker_age_aux,
        "auxiliary worker population age match applied",
    )
    add_auxiliary_note(
        auxiliary_notes,
        living_age_aux,
        "auxiliary living population age match applied",
    )

    commercial_context_aux = get_summary_normalized_value(
        aux_summary,
        "commercial_afternoon_flow_score",
    )
    living_context_aux = get_living_context_aux(aux_summary, slot)
    blended_context_aux = blend_auxiliary_values(commercial_context_aux, living_context_aux)
    apply_series_auxiliary_adjustment(dataframe, "context_score", blended_context_aux)
    add_auxiliary_note(
        auxiliary_notes,
        commercial_context_aux,
        "auxiliary commercial flow context applied",
    )
    add_auxiliary_note(
        auxiliary_notes,
        living_context_aux,
        "auxiliary living population context applied",
    )

    add_senior_interaction_features(dataframe, slot, target_age_group)
    dataframe = apply_weighted_score(dataframe, "senior")
    dataframe = dataframe.sort_values(
        by=["final_score", "district_name", "facility_name"],
        ascending=[False, True, True],
    )
    dataframe = dataframe.drop_duplicates(subset=["district_name"]).head(top_n)

    results = []
    for _, row in dataframe.iterrows():
        results.append(
            build_place_result(
                row=row,
                place_id=row.get("senior_id"),
                name=row.get("facility_name"),
                place_type="senior_friendly",
                district_name=row.get("district_name") or row.get("facility_address"),
                latitude=None,
                longitude=None,
                score=float(row["final_score"]),
                reason=build_senior_reason(row, slot, target_age_group, auxiliary_notes),
            )
        )

    return results


def recommend_market(time_slot: str, target_age_group: str, top_n: int = 3) -> list[dict]:
    slot = normalize_time_slot(time_slot)
    dataframe = load_cleaned_csv("cleaned_market.csv")
    aux_summary = load_aux_feature_summary()
    auxiliary_notes: list[str] = []

    dataframe["market_name"] = dataframe["market_name"].fillna("").astype(str).str.strip()
    dataframe["district_name"] = dataframe["district_name"].fillna("").astype(str).str.strip()
    dataframe["market_address"] = dataframe["market_address"].fillna("").astype(str).str.strip()
    dataframe["market_type"] = dataframe["market_type"].fillna("").astype(str).str.strip()
    dataframe["floor_area"] = pd.to_numeric(dataframe["floor_area"], errors="coerce").fillna(0.0)
    dataframe["store_count"] = pd.to_numeric(dataframe["store_count"], errors="coerce").fillna(0.0)

    dataframe = dataframe[
        (dataframe["market_name"] != "")
        & (dataframe["district_name"] != "")
        & (dataframe["market_address"] != "")
    ].copy()

    store_count_score = normalize_series(dataframe["store_count"])
    floor_area_score = normalize_series(dataframe["floor_area"].clip(lower=0))

    dataframe["time_match_score"] = 1.0 if slot == "afternoon" else 0.70
    dataframe["age_match_score"] = 0.65 if target_age_group == "20_40" else 0.82
    dataframe["context_score"] = dataframe["market_type"].apply(
        lambda value: 0.78 if "골목형" in value else 0.68 if "건물형" in value else 0.60
    )
    dataframe["facility_score"] = (0.60 * store_count_score) + (0.40 * floor_area_score)

    commercial_age_aux = None
    worker_age_aux = None
    if target_age_group == "20_40":
        commercial_age_aux = get_summary_normalized_value(
            aux_summary,
            "commercial_age_20_40_ratio",
        )
        worker_age_aux = get_summary_normalized_value(
            aux_summary,
            "worker_age_20_40_ratio",
        )
    elif target_age_group == "60_plus":
        commercial_age_aux = get_summary_normalized_value(
            aux_summary,
            "commercial_age_60_plus_ratio",
        )
        worker_age_aux = get_summary_normalized_value(
            aux_summary,
            "worker_age_60_plus_ratio",
        )
    living_age_aux = get_living_age_aux(aux_summary, target_age_group)
    blended_age_aux = blend_auxiliary_values(
        commercial_age_aux,
        worker_age_aux,
        living_age_aux,
    )
    apply_series_auxiliary_adjustment(dataframe, "age_match_score", blended_age_aux)
    add_auxiliary_note(
        auxiliary_notes,
        commercial_age_aux,
        "auxiliary commercial age match applied",
    )
    add_auxiliary_note(
        auxiliary_notes,
        worker_age_aux,
        "auxiliary worker population age match applied",
    )
    add_auxiliary_note(
        auxiliary_notes,
        living_age_aux,
        "auxiliary living population age match applied",
    )

    commercial_context_aux = get_summary_normalized_value(
        aux_summary,
        "commercial_afternoon_flow_score" if slot == "afternoon" else "commercial_morning_flow_score",
    )
    living_context_aux = get_living_context_aux(aux_summary, slot)
    blended_context_aux = blend_auxiliary_values(commercial_context_aux, living_context_aux)
    apply_series_auxiliary_adjustment(dataframe, "context_score", blended_context_aux)
    add_auxiliary_note(
        auxiliary_notes,
        commercial_context_aux,
        "auxiliary commercial flow context applied",
    )
    add_auxiliary_note(
        auxiliary_notes,
        living_context_aux,
        "auxiliary living population context applied",
    )

    add_market_interaction_features(dataframe, slot, target_age_group)
    dataframe = apply_weighted_score(dataframe, "market")
    dataframe = dataframe.sort_values(
        by=["final_score", "market_name"],
        ascending=[False, True],
    ).head(top_n)

    results = []
    for _, row in dataframe.iterrows():
        results.append(
            build_place_result(
                row=row,
                place_id=row.get("market_id"),
                name=row.get("market_name"),
                place_type="market",
                district_name=row.get("district_name") or row.get("market_address"),
                latitude=None,
                longitude=None,
                score=float(row["final_score"]),
                reason=build_market_reason(row, slot, target_age_group, auxiliary_notes),
            )
        )

    return results


def recommend_places(
    time_slot: str,
    place_type: str,
    target_age_group: str,
    top_n: int = 3,
) -> list[dict]:
    normalized_place_type = normalize_place_type(place_type)

    if normalized_place_type == "subway":
        return recommend_subway(time_slot, target_age_group, top_n=top_n)
    if normalized_place_type == "park":
        return recommend_parks(time_slot, target_age_group, top_n=top_n)
    if normalized_place_type == "market":
        return recommend_market(time_slot, target_age_group, top_n=top_n)
    return recommend_senior(time_slot, target_age_group, top_n=top_n)


if __name__ == "__main__":
    print("subway")
    print(recommend_places("morning", "subway", "20_40"))
    print()
    print("park")
    print(recommend_places("afternoon", "park", "20_40"))
    print()
    print("market")
    print(recommend_places("afternoon", "market", "60_plus"))
    print()
    print("senior")
    print(recommend_places("afternoon", "senior_friendly", "60_plus"))
