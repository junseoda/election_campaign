"""Shared place alias and candidate expansion helpers.

The alias table is intentionally kept outside the Gold Set.  It acts as a
small, auditable POI normalization layer that both candidate generation and
evaluation can use without changing the Gold labels themselves.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
import unicodedata
from typing import Any

import pandas as pd

from backend.district_utils import normalize_district


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ALIAS_PATH = PROJECT_ROOT / "data" / "processed" / "place_aliases.csv"
ALIAS_COLUMNS = ["canonical_name", "alias_name", "district", "place_type", "source", "note"]

DISTRICT_ALIASES = {
    "광화문": "종로구",
    "광화문광장": "종로구",
    "서울시청": "중구",
    "시청": "중구",
    "여의도": "영등포구",
    "성수": "성동구",
    "성수동": "성동구",
    "강남": "강남구",
    "잠실": "송파구",
    "고덕": "강동구",
    "마곡": "강서구",
    "정릉": "성북구",
}

PLACE_TYPE_COMPATIBILITY = {
    "전통시장": {"전통시장", "골목상권"},
    "골목상권": {"골목상권", "전통시장"},
    "공원": {"공원", "체육시설", "어린이/가족시설"},
    "체육시설": {"체육시설", "공원", "어린이/가족시설"},
    "어린이/가족시설": {"어린이/가족시설", "공원", "체육시설", "복지시설"},
    "복지시설": {"복지시설"},
    "교통거점": {"교통거점", "노동현장"},
    "정책현장": {"정책현장"},
    "노동현장": {"노동현장", "교통거점", "공원"},
    "재개발/도시개발현장": {"재개발/도시개발현장", "정책현장"},
    "종교시설": {"종교시설"},
}

MARKET_KEYWORDS = ["시장", "상가", "상권", "터미널", "맛의거리", "카페거리", "정동길", "약국"]
SUBWAY_KEYWORDS = ["역", "출구", "사거리", "차고지", "차량사업소", "비즈밸리", "교통"]
PARK_KEYWORDS = ["공원", "천", "수변", "팔각정", "벚꽃길", "산", "운동장", "체육관", "경기장", "스포츠"]
SENIOR_KEYWORDS = ["복지", "노인", "홈리스", "나눔", "센터", "어버이날"]


def clean_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def normalize_place_key(value: object) -> str:
    text = unicodedata.normalize("NFKC", clean_text(value)).lower()
    return re.sub(r"[^0-9a-z가-힣]", "", text)


def standardize_district(value: object) -> str:
    text = normalize_district(value) or clean_text(value)
    return DISTRICT_ALIASES.get(text, text)


def _read_alias_csv(path: Path) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(path, encoding=encoding, dtype=str, keep_default_na=False)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def infer_candidate_place_type(place_type: object, *names: object) -> str:
    text = " ".join([clean_text(place_type), *(clean_text(name) for name in names)])
    if any(keyword in text for keyword in MARKET_KEYWORDS):
        return "market"
    if any(keyword in text for keyword in SUBWAY_KEYWORDS):
        return "subway"
    if any(keyword in text for keyword in PARK_KEYWORDS):
        return "park"
    if any(keyword in text for keyword in SENIOR_KEYWORDS):
        return "senior_friendly"

    normalized_type = clean_text(place_type)
    if normalized_type in {"전통시장", "골목상권", "정책현장"}:
        return "market"
    if normalized_type in {"공원", "체육시설", "어린이/가족시설", "종교시설"}:
        return "park"
    if normalized_type == "복지시설":
        return "senior_friendly"
    if normalized_type in {"교통거점", "노동현장", "재개발/도시개발현장"}:
        return "subway"
    return "market"


def place_type_matches(query_place_type: object, alias_place_type: object) -> bool:
    query_type = clean_text(query_place_type)
    alias_type = clean_text(alias_place_type)
    if not query_type or not alias_type:
        return True
    if query_type == alias_type:
        return True
    return alias_type in PLACE_TYPE_COMPATIBILITY.get(query_type, {query_type})


@lru_cache(maxsize=8)
def load_alias_table(alias_path: str | None = None) -> pd.DataFrame:
    path = Path(alias_path) if alias_path else DEFAULT_ALIAS_PATH
    if not path.exists():
        return pd.DataFrame(columns=[*ALIAS_COLUMNS, "canonical_key", "alias_key", "standard_district"])

    aliases = _read_alias_csv(path)
    for column in ALIAS_COLUMNS:
        if column not in aliases.columns:
            aliases[column] = ""

    aliases = aliases[ALIAS_COLUMNS].copy()
    for column in ALIAS_COLUMNS:
        aliases[column] = aliases[column].map(clean_text)

    aliases = aliases[(aliases["canonical_name"] != "") | (aliases["alias_name"] != "")].copy()
    aliases["canonical_name"] = aliases.apply(
        lambda row: row["canonical_name"] or row["alias_name"],
        axis=1,
    )
    aliases["alias_name"] = aliases.apply(
        lambda row: row["alias_name"] or row["canonical_name"],
        axis=1,
    )
    aliases["canonical_key"] = aliases["canonical_name"].map(normalize_place_key)
    aliases["alias_key"] = aliases["alias_name"].map(normalize_place_key)
    aliases["standard_district"] = aliases["district"].map(standardize_district)
    aliases["candidate_place_type"] = aliases.apply(
        lambda row: infer_candidate_place_type(row["place_type"], row["canonical_name"], row["alias_name"]),
        axis=1,
    )
    aliases["place_id"] = aliases.apply(
        lambda row: "alias:"
        + normalize_place_key(row["standard_district"])
        + ":"
        + normalize_place_key(row["canonical_name"]),
        axis=1,
    )
    return aliases.drop_duplicates(
        subset=["canonical_key", "alias_key", "standard_district", "place_type"],
        keep="first",
    ).reset_index(drop=True)


def equivalent_place_keys(name: object, district: object = "", alias_path: str | None = None) -> set[str]:
    key = normalize_place_key(name)
    if not key:
        return set()

    aliases = load_alias_table(alias_path)
    if aliases.empty:
        return {key}

    standard_district = standardize_district(district)
    district_mask = aliases["standard_district"].eq("") | aliases["standard_district"].eq(standard_district)
    matched = aliases[district_mask & ((aliases["canonical_key"] == key) | (aliases["alias_key"] == key))]
    keys = {key}
    if not matched.empty:
        keys.update(matched["canonical_key"].astype(str).tolist())
        keys.update(matched["alias_key"].astype(str).tolist())
    return {item for item in keys if item}


def names_match_by_alias(
    left_name: object,
    right_name: object,
    left_district: object = "",
    right_district: object = "",
    alias_path: str | None = None,
) -> bool:
    district = standardize_district(left_district) or standardize_district(right_district)
    left_keys = equivalent_place_keys(left_name, district, alias_path)
    right_keys = equivalent_place_keys(right_name, district, alias_path)
    return bool(left_keys and right_keys and left_keys.intersection(right_keys))


def alias_candidates_for_query(row: pd.Series, alias_path: str | None = None) -> list[dict[str, Any]]:
    aliases = load_alias_table(alias_path)
    if aliases.empty:
        return []

    query_district = standardize_district(row.get("district", ""))
    query_place_type = clean_text(row.get("place_type", ""))
    filtered = aliases.copy()
    if query_district:
        filtered = filtered[filtered["standard_district"].eq(query_district)]
    if filtered.empty:
        return []
    if query_place_type:
        type_mask = filtered["place_type"].map(lambda value: place_type_matches(query_place_type, value)).astype(bool)
        filtered = filtered[type_mask]
    if filtered.empty:
        return []

    candidates: list[dict[str, Any]] = []
    for _, alias in filtered.sort_values(["place_type", "canonical_name", "alias_name"]).iterrows():
        candidates.append(
            {
                "name": clean_text(alias["canonical_name"]),
                "district_name": clean_text(alias["standard_district"] or alias["district"]),
                "place_type": clean_text(alias["candidate_place_type"]),
                "score": 0.0,
                "place_id": clean_text(alias["place_id"]),
                "candidate_source": f"alias_table:{clean_text(alias['source']) or 'manual'}",
                "alias_name": clean_text(alias["alias_name"]),
                "alias_place_type": clean_text(alias["place_type"]),
                "reason": [
                    "alias table candidate expansion",
                    clean_text(alias["note"]),
                ],
            }
        )
    return candidates
