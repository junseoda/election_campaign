from __future__ import annotations

from typing import Any, Iterable

import pandas as pd


SEOUL_DISTRICT_LIST = [
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

SEOUL_DISTRICTS = set(SEOUL_DISTRICT_LIST)

DISTRICT_ALIAS = {
    "종로": "종로구",
    "중": "중구",
    "용산": "용산구",
    "성동": "성동구",
    "광진": "광진구",
    "동대문": "동대문구",
    "중랑": "중랑구",
    "성북": "성북구",
    "강북": "강북구",
    "도봉": "도봉구",
    "노원": "노원구",
    "은평": "은평구",
    "서대문": "서대문구",
    "마포": "마포구",
    "양천": "양천구",
    "강서": "강서구",
    "구로": "구로구",
    "금천": "금천구",
    "영등포": "영등포구",
    "동작": "동작구",
    "관악": "관악구",
    "서초": "서초구",
    "강남": "강남구",
    "송파": "송파구",
    "강동": "강동구",
}

DISTRICT_FIELD_CANDIDATES = (
    "district_normalized",
    "recommended_district_normalized",
    "district",
    "district_name",
    "recommended_district",
    "자치구",
    "시군구",
    "SIG_KOR_NM",
    "gu",
    "region",
)


def normalize_district(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, float) and pd.isna(value):
        return None

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None

    text = (
        text.replace("서울특별시", "")
        .replace("서울시", "")
        .replace("서울", "")
        .strip()
    )
    if not text:
        return None

    parts = text.split()
    for part in parts:
        normalized_part = _normalize_district_token(part)
        if normalized_part:
            return normalized_part

    normalized_text = _normalize_district_token(text)
    if normalized_text:
        return normalized_text

    compact = text.replace(" ", "")
    for district in SEOUL_DISTRICT_LIST:
        if district in compact:
            return district

    for alias, district in DISTRICT_ALIAS.items():
        if alias and alias in compact:
            return district

    return text


def _normalize_district_token(value: str) -> str | None:
    token = str(value).strip().strip(",.;:()[]{}")
    if not token:
        return None
    if token in SEOUL_DISTRICTS:
        return token
    if token in DISTRICT_ALIAS:
        return DISTRICT_ALIAS[token]
    if not token.endswith("구") and f"{token}구" in SEOUL_DISTRICTS:
        return f"{token}구"
    return None


def normalize_districts(selected_districts: Any) -> list[str]:
    if not selected_districts:
        return []
    if isinstance(selected_districts, str):
        selected_districts = [selected_districts]

    normalized: list[str] = []
    seen: set[str] = set()
    for district in selected_districts:
        value = normalize_district(district)
        if value and value not in seen:
            normalized.append(value)
            seen.add(value)
    return normalized


def get_candidate_district(candidate: Any) -> str | None:
    if candidate is None:
        return None

    if isinstance(candidate, dict):
        for key in DISTRICT_FIELD_CANDIDATES:
            value = candidate.get(key)
            normalized = normalize_district(value)
            if normalized:
                return normalized
        return None

    if isinstance(candidate, pd.Series):
        for key in DISTRICT_FIELD_CANDIDATES:
            if key in candidate:
                normalized = normalize_district(candidate.get(key))
                if normalized:
                    return normalized
        return None

    for key in DISTRICT_FIELD_CANDIDATES:
        normalized = normalize_district(getattr(candidate, key, None))
        if normalized:
            return normalized
    return None


def filter_by_district(candidates: list[Any], selected_districts: Any) -> list[Any]:
    selected = set(normalize_districts(selected_districts))
    if not selected:
        return candidates

    filtered: list[Any] = []
    for candidate in candidates:
        candidate_district = get_candidate_district(candidate)
        if candidate_district in selected:
            if isinstance(candidate, dict):
                candidate["district_normalized"] = candidate_district
                candidate["district_match"] = True
            filtered.append(candidate)
    return filtered


def add_district_fields(candidate: dict[str, Any], selected_districts: Any = None) -> dict[str, Any]:
    candidate_district = get_candidate_district(candidate)
    selected = set(normalize_districts(selected_districts))
    candidate["district_normalized"] = candidate_district
    candidate["district_match"] = candidate_district in selected if selected else True
    if candidate_district and not candidate.get("district"):
        candidate["district"] = candidate_district
    return candidate


def get_dataframe_district_series(
    dataframe: pd.DataFrame,
    district_columns: Iterable[str] = DISTRICT_FIELD_CANDIDATES,
) -> pd.Series:
    columns = [column for column in district_columns if column in dataframe.columns]
    if not columns:
        return pd.Series([None] * len(dataframe), index=dataframe.index, dtype=object)

    return dataframe[columns].apply(
        lambda row: next(
            (
                normalized
                for normalized in (normalize_district(row.get(column)) for column in columns)
                if normalized
            ),
            None,
        ),
        axis=1,
    )


def filter_dataframe_by_district(
    dataframe: pd.DataFrame,
    selected_districts: Any,
    district_columns: Iterable[str] = DISTRICT_FIELD_CANDIDATES,
) -> pd.DataFrame:
    selected = set(normalize_districts(selected_districts))
    if not selected:
        filtered = dataframe.copy()
        if "district_normalized" not in filtered.columns:
            filtered["district_normalized"] = get_dataframe_district_series(filtered, district_columns)
        return filtered

    filtered = dataframe.copy()
    filtered["district_normalized"] = get_dataframe_district_series(filtered, district_columns)
    filtered = filtered[filtered["district_normalized"].isin(selected)].copy()
    filtered["district_match"] = True
    return filtered


def validate_recommendation_districts(
    results: list[dict[str, Any]],
    selected_districts: Any,
) -> tuple[list[dict[str, Any]], list[str]]:
    selected = set(normalize_districts(selected_districts))
    if not selected:
        for result in results:
            add_district_fields(result)
        return results, []

    warnings: list[str] = []
    valid_results: list[dict[str, Any]] = []
    invalid_results: list[dict[str, Any]] = []

    for result in results:
        result_district = get_candidate_district(result)
        result["district_normalized"] = result_district
        result["district_match"] = result_district in selected
        if result_district in selected:
            valid_results.append(result)
        else:
            invalid_results.append(result)

    if invalid_results:
        invalid_districts = sorted(
            {str(get_candidate_district(result) or "UNKNOWN") for result in invalid_results}
        )
        warnings.append(
            "Removed "
            + str(len(invalid_results))
            + " recommendations outside selected districts: "
            + ", ".join(invalid_districts)
        )

    return valid_results, warnings


def count_district_mismatches(results: list[dict[str, Any]], selected_districts: Any) -> int:
    selected = set(normalize_districts(selected_districts))
    if not selected:
        return 0
    return sum(1 for result in results if get_candidate_district(result) not in selected)
