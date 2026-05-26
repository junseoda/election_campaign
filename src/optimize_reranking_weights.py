"""Optimize feature-based re-ranking weights for campaign place recommendation.

This script does not modify or re-run the baseline recommender.  It starts from
the fixed raw candidate file, engineers explainable query-candidate features,
searches over additive weights on the train split, evaluates on validation and
full data, and writes analysis artifacts for paper reporting.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from evaluate_recommendations import (  # noqa: E402
    evaluate,
    place_match_method,
    read_csv_with_fallback as read_eval_csv,
)
from backend.district_utils import filter_dataframe_by_district, normalize_district  # noqa: E402


FEATURE_COLUMNS = [
    "district_bonus",
    "place_type_bonus",
    "time_bonus",
    "context_bonus",
    "target_bonus",
    "rank_bonus",
]

WEIGHT_COLUMNS = [
    "baseline_weight",
    "district_weight",
    "place_type_weight",
    "time_weight",
    "context_weight",
    "target_weight",
    "rank_weight",
]

RECOMMENDATION_COLUMNS = [
    "query_id",
    "rank",
    "recommended_place_name",
    "recommended_district",
    "recommended_place_type",
    "baseline_score",
    "raw_rank",
    "district_bonus",
    "place_type_bonus",
    "time_bonus",
    "context_bonus",
    "target_bonus",
    "rank_bonus",
    "final_variant_score",
    "score",
]

MATCH_COLUMNS = ["_matched_gold_item_id", "_matched_relevance"]

COMPARISON_COLUMNS = [
    "model_name",
    "P@1",
    "P@3",
    "P@5",
    "P@10",
    "R@1",
    "R@3",
    "R@5",
    "R@10",
    "NDCG@1",
    "NDCG@3",
    "NDCG@5",
    "NDCG@10",
    "optimization_score",
]

RAW_REQUIRED_COLUMNS = [
    "query_id",
    "date",
    "time",
    "district",
    "place_type",
    "target_voter_group",
    "context_tags",
    "raw_rank",
    "recommended_place_name",
    "recommended_district",
    "recommended_place_type",
    "baseline_score",
]

SEOUL_ADJACENCY = {
    "강남구": {"서초구", "송파구", "성동구", "광진구"},
    "강동구": {"송파구", "광진구"},
    "강북구": {"도봉구", "노원구", "성북구"},
    "강서구": {"양천구", "영등포구", "마포구"},
    "관악구": {"동작구", "금천구", "구로구", "서초구"},
    "광진구": {"성동구", "중랑구", "송파구", "강동구", "강남구"},
    "구로구": {"금천구", "양천구", "영등포구", "관악구"},
    "금천구": {"구로구", "관악구"},
    "노원구": {"도봉구", "강북구", "중랑구"},
    "도봉구": {"노원구", "강북구"},
    "동대문구": {"성동구", "광진구", "중랑구", "성북구", "종로구"},
    "동작구": {"관악구", "서초구", "용산구", "영등포구"},
    "마포구": {"서대문구", "은평구", "영등포구", "용산구", "강서구"},
    "서대문구": {"마포구", "은평구", "종로구", "중구"},
    "서초구": {"강남구", "동작구", "관악구", "용산구"},
    "성동구": {"광진구", "동대문구", "중구", "용산구", "강남구"},
    "성북구": {"강북구", "동대문구", "종로구", "중랑구"},
    "송파구": {"강남구", "강동구", "광진구"},
    "양천구": {"강서구", "구로구", "영등포구"},
    "영등포구": {"구로구", "양천구", "강서구", "마포구", "동작구"},
    "용산구": {"중구", "성동구", "마포구", "동작구", "서초구"},
    "은평구": {"서대문구", "마포구", "종로구"},
    "종로구": {"중구", "서대문구", "성북구", "동대문구", "은평구"},
    "중구": {"종로구", "서대문구", "용산구", "성동구"},
    "중랑구": {"노원구", "성북구", "동대문구", "광진구"},
}

SEOUL_AREAS = {
    "central": {"종로구", "중구", "용산구", "성동구"},
    "northeast": {"동대문구", "중랑구", "성북구", "강북구", "도봉구", "노원구", "광진구"},
    "northwest": {"은평구", "서대문구", "마포구"},
    "southwest": {"강서구", "양천구", "영등포구", "구로구", "금천구", "동작구", "관악구"},
    "southeast": {"서초구", "강남구", "송파구", "강동구"},
}

DISTRICT_ALIASES = {
    "광화문": "종로구",
    "세종대로": "중구",
}

PLACE_TYPE_SYNONYMS = {
    "market": [
        "전통시장",
        "시장",
        "골목상권",
        "상권",
        "상점가",
        "로데오",
        "먹자",
        "맛의거리",
        "음식문화거리",
        "상인",
        "생활밀착",
    ],
    "park": [
        "공원",
        "광장",
        "하천",
        "도림천",
        "응봉산",
        "둘레길",
        "체육",
        "운동장",
        "어린이",
        "가족",
        "야외",
    ],
    "senior_friendly": [
        "복지",
        "노인",
        "어르신",
        "노년",
        "고령",
        "종합사회복지관",
        "복지관",
        "장애인",
    ],
    "subway": [
        "교통",
        "역",
        "지하철",
        "사거리",
        "퇴근",
        "출근",
        "직장인",
        "환승",
        "거점",
    ],
    "labor_site": ["노동", "노조", "근로", "산업", "현장"],
    "urban_site": ["재개발", "도시개발", "주거", "정비", "정책현장"],
    "religious": ["종교", "교회", "성당", "사찰", "법회"],
    "youth": ["대학", "청년", "캠퍼스", "청년공간"],
}

CANDIDATE_TYPE_STANDARD = {
    "market": "market",
    "park": "park",
    "senior": "senior_friendly",
    "senior_friendly": "senior_friendly",
    "subway": "subway",
}

PLACE_TYPE_RELATEDNESS = {
    ("labor_site", "market"): 0.35,
    ("urban_site", "market"): 0.25,
    ("urban_site", "subway"): 0.20,
    ("religious", "park"): 0.15,
    ("youth", "subway"): 0.30,
    ("youth", "market"): 0.20,
    ("park", "senior_friendly"): 0.20,
    ("senior_friendly", "park"): 0.20,
    ("market", "subway"): 0.15,
    ("subway", "market"): 0.15,
}

WEIGHT_GRID = {
    "baseline_weight": [1.0],
    "district_weight": [0.2, 0.3, 0.4, 0.5, 0.7],
    "place_type_weight": [0.0, 0.1, 0.2, 0.3],
    "time_weight": [0.0, 0.05, 0.1, 0.2],
    "context_weight": [0.0, 0.05, 0.1, 0.2],
    "target_weight": [0.0, 0.05, 0.1, 0.2],
    "rank_weight": [0.0, 0.05, 0.1],
}


class DataValidationError(ValueError):
    """Raised when optimization inputs do not satisfy the expected contract."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Optimize explainable re-ranking weights.")
    parser.add_argument("--gold", required=True, help="Path to gold_set_evaluation_queries.csv")
    parser.add_argument("--raw", required=True, help="Path to raw_baseline_recommendations.csv")
    parser.add_argument(
        "--existing_comparison",
        default="",
        help="Path to output/experiments/model_comparison.csv. If omitted, baseline/proposed rows are recomputed from the current raw file.",
    )
    parser.add_argument("--output_dir", required=True, help="Directory for optimized experiment artifacts")
    parser.add_argument("--top_k", type=int, default=10)
    parser.add_argument("--k", nargs="+", type=int, default=[1, 3, 5, 10])
    parser.add_argument("--search_mode", choices=["grid", "random"], default="random")
    parser.add_argument("--n_trials", type=int, default=300)
    parser.add_argument("--random_state", type=int, default=42)
    return parser.parse_args()


def read_csv_with_fallback(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{label} file not found: {path}")
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(path, encoding=encoding, dtype=str, keep_default_na=False)
        except UnicodeDecodeError:
            continue
    raise DataValidationError(f"Could not read {label} with utf-8-sig or cp949: {path}")


def validate_raw(raw: pd.DataFrame, gold: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in RAW_REQUIRED_COLUMNS if column not in raw.columns]
    if missing:
        raise DataValidationError(f"raw baseline missing required columns: {', '.join(missing)}")

    prepared = raw.copy()
    prepared["baseline_score"] = pd.to_numeric(prepared["baseline_score"], errors="coerce")
    prepared["raw_rank"] = pd.to_numeric(prepared["raw_rank"], errors="coerce")
    if prepared["baseline_score"].isna().any() or prepared["raw_rank"].isna().any():
        raise DataValidationError("baseline_score and raw_rank must be numeric.")

    gold_query_ids = set(gold["query_id"].astype(str))
    raw_query_ids = set(prepared["query_id"].astype(str))
    missing_query_ids = sorted(gold_query_ids - raw_query_ids)
    if missing_query_ids:
        raise DataValidationError(f"raw baseline missing query_id values: {missing_query_ids[:10]}")
    return prepared


def normalize_key(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).lower()
    return re.sub(r"[^0-9a-z가-힣]", "", text)


def clean_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def standard_district(value: object) -> str:
    text = normalize_district(value) or clean_text(value)
    return DISTRICT_ALIASES.get(text, text)


def district_area(district: str) -> str | None:
    for area_name, districts in SEOUL_AREAS.items():
        if district in districts:
            return area_name
    return None


def split_tags(value: object) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    tokens = re.split(r"[;,/|()\s]+", text)
    return [token.strip() for token in tokens if token.strip()]


def infer_place_categories(*values: object) -> set[str]:
    text = " ".join(clean_text(value) for value in values)
    key = normalize_key(text)
    categories: set[str] = set()
    for category, keywords in PLACE_TYPE_SYNONYMS.items():
        if any(normalize_key(keyword) in key for keyword in keywords):
            categories.add(category)
    return categories


def standard_candidate_type(value: object) -> str:
    return CANDIDATE_TYPE_STANDARD.get(clean_text(value), clean_text(value))


def calc_district_bonus(row: pd.Series) -> float:
    query_district = standard_district(row.get("district"))
    candidate_district = standard_district(row.get("recommended_district"))
    if not query_district or not candidate_district:
        return 0.0
    if query_district == candidate_district:
        return 1.0
    return 0.0


def calc_place_type_bonus(row: pd.Series) -> float:
    query_categories = infer_place_categories(
        row.get("place_type"),
        row.get("target_voter_group"),
        row.get("context_tags"),
    )
    candidate_category = standard_candidate_type(row.get("recommended_place_type"))
    if candidate_category in query_categories:
        return 1.0

    related_scores = [
        PLACE_TYPE_RELATEDNESS.get((query_category, candidate_category), 0.0)
        for query_category in query_categories
    ]
    return max(related_scores, default=0.0)


def derive_hour(value: object) -> int | None:
    text = clean_text(value)
    try:
        hour = int(text.split(":", maxsplit=1)[0])
    except (ValueError, IndexError):
        return None
    return hour if 0 <= hour <= 23 else None


def calc_time_bonus(row: pd.Series) -> float:
    hour = derive_hour(row.get("time"))
    candidate_type = standard_candidate_type(row.get("recommended_place_type"))
    if hour is None:
        return 0.0

    if 7 <= hour < 10:
        return {"subway": 1.0, "market": 0.35, "senior_friendly": 0.20, "park": 0.15}.get(candidate_type, 0.0)
    if 10 <= hour < 12:
        return {"senior_friendly": 0.80, "market": 0.70, "park": 0.40, "subway": 0.30}.get(candidate_type, 0.0)
    if 12 <= hour < 14:
        return {"market": 0.85, "park": 0.65, "senior_friendly": 0.45, "subway": 0.20}.get(candidate_type, 0.0)
    if 14 <= hour < 17:
        return {"market": 0.80, "park": 0.70, "senior_friendly": 0.55, "subway": 0.25}.get(candidate_type, 0.0)
    if 17 <= hour < 20:
        return {"subway": 1.0, "market": 0.80, "park": 0.40, "senior_friendly": 0.25}.get(candidate_type, 0.0)
    return {"market": 0.50, "subway": 0.40, "park": 0.25, "senior_friendly": 0.20}.get(candidate_type, 0.0)


def calc_context_bonus(row: pd.Series) -> float:
    tags = split_tags(row.get("context_tags"))
    if not tags:
        return 0.0

    candidate_text = " ".join(
        clean_text(row.get(column, ""))
        for column in (
            "recommended_place_name",
            "recommended_district",
            "recommended_place_type",
            "place_id",
            "candidate_source",
        )
    )
    candidate_key = normalize_key(candidate_text)
    query_district_key = normalize_key(row.get("district"))
    semantic_categories = infer_place_categories(row.get("context_tags"), row.get("target_voter_group"))
    candidate_category = standard_candidate_type(row.get("recommended_place_type"))

    score = 0.0
    for tag in tags:
        tag_key = normalize_key(tag)
        if not tag_key or tag_key == query_district_key:
            continue
        if tag_key in {"오전", "오후", "저녁", "아침", "점심", "출근", "퇴근"}:
            continue
        if tag_key and tag_key in candidate_key:
            score += 0.18
        elif len(tag_key) >= 3 and any(part in candidate_key for part in [tag_key[:3], tag_key[-3:]]):
            score += 0.08

    if candidate_category in semantic_categories:
        score += 0.35
    elif any(PLACE_TYPE_RELATEDNESS.get((category, candidate_category), 0.0) > 0 for category in semantic_categories):
        score += 0.12
    return min(score, 1.0)


def calc_target_bonus(row: pd.Series) -> float:
    target = normalize_key(row.get("target_voter_group"))
    candidate_type = standard_candidate_type(row.get("recommended_place_type"))
    if not target:
        return 0.0

    if candidate_type == "senior_friendly" and any(keyword in target for keyword in ["노년", "노인", "어르신", "복지", "장애인"]):
        return 1.0
    if candidate_type == "market" and any(keyword in target for keyword in ["상인", "지역주민", "생활권", "일반시민"]):
        return 0.75
    if candidate_type == "subway" and any(keyword in target for keyword in ["직장인", "퇴근길", "출근", "일반시민", "청년"]):
        return 0.70
    if candidate_type == "park" and any(keyword in target for keyword in ["가족", "어린이", "체육", "일반시민", "지역주민"]):
        return 0.70
    if "일반시민" in target:
        return 0.25
    return 0.0


def calc_rank_bonus(raw_rank: object) -> float:
    rank = pd.to_numeric(pd.Series([raw_rank]), errors="coerce").iloc[0]
    if pd.isna(rank):
        return 0.0
    rank = max(1.0, min(float(rank), 50.0))
    return round(1.0 - ((rank - 1.0) / 49.0), 6)


def add_feature_values(raw: pd.DataFrame) -> pd.DataFrame:
    featured = raw.copy()
    featured["district_bonus"] = featured.apply(calc_district_bonus, axis=1)
    featured["place_type_bonus"] = featured.apply(calc_place_type_bonus, axis=1)
    featured["time_bonus"] = featured.apply(calc_time_bonus, axis=1)
    featured["context_bonus"] = featured.apply(calc_context_bonus, axis=1)
    featured["target_bonus"] = featured.apply(calc_target_bonus, axis=1)
    featured["rank_bonus"] = featured["raw_rank"].map(calc_rank_bonus)
    return featured


def add_match_labels(featured_raw: pd.DataFrame, gold: pd.DataFrame) -> pd.DataFrame:
    labeled = featured_raw.copy()
    labeled["_matched_gold_item_id"] = ""
    labeled["_matched_relevance"] = 0.0

    gold_by_query = {str(query_id): group.copy() for query_id, group in gold.groupby("query_id", sort=False)}
    for index, candidate in labeled.iterrows():
        query_gold = gold_by_query.get(str(candidate["query_id"]), gold.iloc[0:0])
        for _, gold_row in query_gold.iterrows():
            if place_match_method(candidate, gold_row) is not None:
                labeled.at[index, "_matched_gold_item_id"] = clean_text(gold_row.get("gold_id", ""))
                labeled.at[index, "_matched_relevance"] = float(gold_row.get("relevance", 0.0))
                break
    return labeled


def build_gold_stats(gold: pd.DataFrame) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    for query_id, group in gold.groupby("query_id", sort=False):
        relevances = pd.to_numeric(group["relevance"], errors="coerce").fillna(0.0).astype(float).tolist()
        stats[str(query_id)] = {
            "total_relevant": int(len(group)),
            "relevances": relevances,
        }
    return stats


def all_weight_combinations() -> list[dict[str, float]]:
    keys = list(WEIGHT_GRID)
    values = [WEIGHT_GRID[key] for key in keys]
    return [dict(zip(keys, combo)) for combo in itertools.product(*values)]


def build_trials(search_mode: str, n_trials: int, random_state: int) -> list[dict[str, float]]:
    combos = all_weight_combinations()
    required = [
        {
            "baseline_weight": 1.0,
            "district_weight": 0.0,
            "place_type_weight": 0.0,
            "time_weight": 0.0,
            "context_weight": 0.0,
            "target_weight": 0.0,
            "rank_weight": 0.0,
        },
        {
            "baseline_weight": 1.0,
            "district_weight": 0.2,
            "place_type_weight": 0.0,
            "time_weight": 0.0,
            "context_weight": 0.0,
            "target_weight": 0.0,
            "rank_weight": 0.0,
        },
        {
            "baseline_weight": 1.0,
            "district_weight": 0.3,
            "place_type_weight": 0.1,
            "time_weight": 0.05,
            "context_weight": 0.05,
            "target_weight": 0.05,
            "rank_weight": 0.05,
        },
    ]

    if search_mode == "grid":
        selected = combos[: max(n_trials, 0)] if n_trials > 0 else combos
    else:
        rng = random.Random(random_state)
        sample_size = min(max(n_trials, 0), len(combos))
        selected = rng.sample(combos, sample_size)

    seen: set[tuple[float, ...]] = set()
    trials: list[dict[str, float]] = []
    for weights in [*required, *selected]:
        key = tuple(float(weights[column]) for column in WEIGHT_COLUMNS)
        if key in seen:
            continue
        seen.add(key)
        trials.append(weights)
    return trials


def make_split(query_ids: list[str], random_state: int, train_ratio: float = 0.7) -> tuple[set[str], set[str]]:
    ids = pd.Series(sorted(query_ids)).sample(frac=1.0, random_state=random_state).tolist()
    split_index = int(len(ids) * train_ratio)
    train_ids = set(ids[:split_index])
    validation_ids = set(ids[split_index:])
    return train_ids, validation_ids


def rerank_candidates(
    featured_raw: pd.DataFrame,
    weights: dict[str, float],
    top_k: int,
    include_match_columns: bool = False,
) -> pd.DataFrame:
    scored = featured_raw.copy()
    scored["final_variant_score"] = (
        scored["baseline_score"] * weights["baseline_weight"]
        + scored["district_bonus"] * weights["district_weight"]
        + scored["place_type_bonus"] * weights["place_type_weight"]
        + scored["time_bonus"] * weights["time_weight"]
        + scored["context_bonus"] * weights["context_weight"]
        + scored["target_bonus"] * weights["target_weight"]
        + scored["rank_bonus"] * weights["rank_weight"]
    ).round(6)
    scored["score"] = scored["final_variant_score"]

    groups: list[pd.DataFrame] = []
    for _, group in scored.groupby("query_id", sort=False):
        query_district = normalize_district(group["district"].iloc[0]) if "district" in group.columns and len(group) else None
        group = filter_dataframe_by_district(
            group,
            query_district,
            ("recommended_district", "district_normalized", "district_name", "자치구", "시군구", "SIG_KOR_NM"),
        )
        if group.empty:
            continue
        top_group = group.sort_values(
            by=["final_variant_score", "baseline_score", "raw_rank"],
            ascending=[False, False, True],
        ).head(top_k).copy()
        top_group["rank"] = range(1, len(top_group) + 1)
        groups.append(top_group)
    output_columns = RECOMMENDATION_COLUMNS.copy()
    if include_match_columns:
        output_columns.extend([column for column in MATCH_COLUMNS if column in scored.columns])
    if not groups:
        return pd.DataFrame(columns=output_columns)
    return pd.concat(groups, ignore_index=True)[output_columns]


def filter_by_query_ids(dataframe: pd.DataFrame, query_ids: set[str]) -> pd.DataFrame:
    return dataframe[dataframe["query_id"].astype(str).isin(query_ids)].copy()


def summary_metrics(summary: pd.DataFrame, prefix: str = "") -> dict[str, float]:
    metrics: dict[str, float] = {}
    for _, row in summary.iterrows():
        k = int(row["k"])
        metrics[f"{prefix}P@{k}"] = float(row["precision_at_k"])
        metrics[f"{prefix}R@{k}"] = float(row["recall_at_k"])
        metrics[f"{prefix}NDCG@{k}"] = float(row["ndcg_at_k"])
    return metrics


def optimization_score(metrics: dict[str, float], prefix: str = "") -> float:
    return (
        0.35 * metrics.get(f"{prefix}NDCG@10", 0.0)
        + 0.25 * metrics.get(f"{prefix}P@1", 0.0)
        + 0.20 * metrics.get(f"{prefix}P@3", 0.0)
        + 0.10 * metrics.get(f"{prefix}P@5", 0.0)
        + 0.10 * metrics.get(f"{prefix}R@10", 0.0)
    )


def ideal_dcg(relevances: list[float], k: int) -> float:
    return sum(
        (2**rel - 1) / math.log2(rank + 1)
        for rank, rel in enumerate(sorted(relevances, reverse=True)[:k], start=1)
    )


def fast_evaluate_summary(
    recommendations: pd.DataFrame,
    query_ids: set[str],
    gold_stats: dict[str, dict[str, Any]],
    k_values: list[int],
) -> pd.DataFrame:
    rec_by_query = {
        str(query_id): group.sort_values("rank").copy()
        for query_id, group in recommendations.groupby("query_id", sort=False)
    }
    rows: list[dict[str, Any]] = []

    for k in sorted(set(k_values)):
        per_query_rows: list[dict[str, float]] = []
        for query_id in query_ids:
            stats = gold_stats[str(query_id)]
            total_relevant = stats["total_relevant"]
            top_recs = rec_by_query.get(str(query_id), recommendations.iloc[0:0])
            top_recs = top_recs[top_recs["rank"].le(k)].sort_values("rank")

            used_gold: set[str] = set()
            hits = 0
            dcg = 0.0
            for _, rec in top_recs.iterrows():
                gold_item_id = clean_text(rec.get("_matched_gold_item_id", ""))
                if not gold_item_id or gold_item_id in used_gold:
                    continue
                used_gold.add(gold_item_id)
                hits += 1
                relevance = float(rec.get("_matched_relevance", 0.0))
                rank = int(rec["rank"])
                dcg += (2**relevance - 1) / math.log2(rank + 1)

            idcg = ideal_dcg(stats["relevances"], k)
            per_query_rows.append(
                {
                    "precision_at_k": hits / k,
                    "recall_at_k": hits / total_relevant if total_relevant else 0.0,
                    "ndcg_at_k": dcg / idcg if idcg > 0 else 0.0,
                }
            )

        metric_frame = pd.DataFrame(per_query_rows)
        rows.append(
            {
                "k": k,
                "precision_at_k": float(metric_frame["precision_at_k"].mean()),
                "recall_at_k": float(metric_frame["recall_at_k"].mean()),
                "ndcg_at_k": float(metric_frame["ndcg_at_k"].mean()),
                "query_count": len(query_ids),
            }
        )
    return pd.DataFrame(rows)


def evaluate_subset(
    gold: pd.DataFrame,
    recommendations: pd.DataFrame,
    query_ids: set[str],
    k_values: list[int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    return evaluate(
        filter_by_query_ids(gold, query_ids),
        filter_by_query_ids(recommendations, query_ids),
        k_values,
    )


def run_search(
    gold: pd.DataFrame,
    featured_raw: pd.DataFrame,
    train_ids: set[str],
    validation_ids: set[str],
    trials: list[dict[str, float]],
    top_k: int,
    k_values: list[int],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    gold_stats = build_gold_stats(gold)
    rows: list[dict[str, Any]] = []

    for trial_id, weights in enumerate(trials, start=1):
        recommendations = rerank_candidates(featured_raw, weights, top_k, include_match_columns=True)
        train_summary = fast_evaluate_summary(recommendations, train_ids, gold_stats, k_values)

        train_metrics = summary_metrics(train_summary, "train_")
        row: dict[str, Any] = {"trial_id": trial_id, **weights}
        row.update(train_metrics)
        row["train_optimization_score"] = optimization_score(train_metrics, "train_")
        rows.append(row)

    results = pd.DataFrame(rows)
    best = {
        "best_by_ndcg10": results.loc[results["train_NDCG@10"].idxmax()].to_dict(),
        "best_by_p1": results.loc[results["train_P@1"].idxmax()].to_dict(),
        "best_by_p3": results.loc[results["train_P@3"].idxmax()].to_dict(),
        "best_by_optimization_score": results.loc[results["train_optimization_score"].idxmax()].to_dict(),
    }
    return results, best


def extract_weights(row: dict[str, Any] | pd.Series) -> dict[str, float]:
    return {column: float(row[column]) for column in WEIGHT_COLUMNS}


def save_summary(summary: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(path, index=False, encoding="utf-8-sig")


def metric_row_from_summary(model_name: str, summary: pd.DataFrame) -> dict[str, Any]:
    metrics = summary_metrics(summary)
    row = {
        "model_name": model_name,
        "P@1": metrics.get("P@1", 0.0),
        "P@3": metrics.get("P@3", 0.0),
        "P@5": metrics.get("P@5", 0.0),
        "P@10": metrics.get("P@10", 0.0),
        "R@1": metrics.get("R@1", 0.0),
        "R@3": metrics.get("R@3", 0.0),
        "R@5": metrics.get("R@5", 0.0),
        "R@10": metrics.get("R@10", 0.0),
        "NDCG@1": metrics.get("NDCG@1", 0.0),
        "NDCG@3": metrics.get("NDCG@3", 0.0),
        "NDCG@5": metrics.get("NDCG@5", 0.0),
        "NDCG@10": metrics.get("NDCG@10", 0.0),
    }
    row["optimization_score"] = optimization_score(metrics)
    return row


def convert_existing_comparison(path: Path) -> pd.DataFrame:
    existing = read_csv_with_fallback(path, "existing model comparison")
    rows: list[dict[str, Any]] = []
    for _, row in existing.iterrows():
        converted = {
            "model_name": row["model_name"],
            "P@1": float(row.get("precision_at_1", 0.0)),
            "P@3": float(row.get("precision_at_3", 0.0)),
            "P@5": float(row.get("precision_at_5", 0.0)),
            "P@10": float(row.get("precision_at_10", 0.0)),
            "R@1": float(row.get("recall_at_1", 0.0)),
            "R@3": float(row.get("recall_at_3", 0.0)),
            "R@5": float(row.get("recall_at_5", 0.0)),
            "R@10": float(row.get("recall_at_10", 0.0)),
            "NDCG@1": float(row.get("ndcg_at_1", 0.0)),
            "NDCG@3": float(row.get("ndcg_at_3", 0.0)),
            "NDCG@5": float(row.get("ndcg_at_5", 0.0)),
            "NDCG@10": float(row.get("ndcg_at_10", 0.0)),
        }
        converted["optimization_score"] = optimization_score(converted)
        rows.append(converted)
    return pd.DataFrame(rows, columns=COMPARISON_COLUMNS)


def build_comparison_from_current(gold: pd.DataFrame, raw: pd.DataFrame, k_values: list[int], top_k: int) -> pd.DataFrame:
    from run_model_experiments import MODEL_VARIANTS, build_recommendation_results_from_raw, flatten_summary

    rows: list[dict[str, Any]] = []
    for model_name in MODEL_VARIANTS:
        recommendations = build_recommendation_results_from_raw(raw, model_name, top_k)
        _, summary = evaluate(gold, recommendations, k_values)
        rows.append(flatten_summary(model_name, summary, sorted(set(k_values))))

    converted: list[dict[str, Any]] = []
    for row in rows:
        converted_row = {
            "model_name": row["model_name"],
            "P@1": float(row.get("precision_at_1", 0.0)),
            "P@3": float(row.get("precision_at_3", 0.0)),
            "P@5": float(row.get("precision_at_5", 0.0)),
            "P@10": float(row.get("precision_at_10", 0.0)),
            "R@1": float(row.get("recall_at_1", 0.0)),
            "R@3": float(row.get("recall_at_3", 0.0)),
            "R@5": float(row.get("recall_at_5", 0.0)),
            "R@10": float(row.get("recall_at_10", 0.0)),
            "NDCG@1": float(row.get("ndcg_at_1", 0.0)),
            "NDCG@3": float(row.get("ndcg_at_3", 0.0)),
            "NDCG@5": float(row.get("ndcg_at_5", 0.0)),
            "NDCG@10": float(row.get("ndcg_at_10", 0.0)),
        }
        converted_row["optimization_score"] = optimization_score(converted_row)
        converted.append(converted_row)
    return pd.DataFrame(converted, columns=COMPARISON_COLUMNS)


def match_candidate(candidate: pd.Series, gold_row: pd.Series) -> bool:
    return place_match_method(candidate, gold_row) is not None


def best_match_rank(candidates: pd.DataFrame, gold_row: pd.Series, rank_column: str) -> int | None:
    for _, candidate in candidates.sort_values(rank_column).iterrows():
        if match_candidate(candidate, gold_row):
            return int(candidate[rank_column])
    return None


def build_raw_candidate_coverage(gold: pd.DataFrame, raw: pd.DataFrame, optimized: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, gold_row in gold.iterrows():
        query_id = str(gold_row["query_id"])
        raw_candidates = raw[raw["query_id"].astype(str).eq(query_id)].copy()
        optimized_candidates = optimized[optimized["query_id"].astype(str).eq(query_id)].copy()
        raw_rank = best_match_rank(raw_candidates, gold_row, "raw_rank")
        optimized_rank = best_match_rank(optimized_candidates, gold_row, "rank")
        rows.append(
            {
                "query_id": query_id,
                "gold_place_name": gold_row["place_name"],
                "gold_district": gold_row["district"],
                "raw_candidate_count": int(len(raw_candidates)),
                "in_raw_top50": raw_rank is not None,
                "best_raw_rank": raw_rank if raw_rank is not None else "",
                "in_optimized_top10": optimized_rank is not None and optimized_rank <= 10,
                "best_optimized_rank": optimized_rank if optimized_rank is not None else "",
                "coverage_status": "covered" if raw_rank is not None else "missing_from_raw_candidates",
            }
        )
    return pd.DataFrame(rows)


def build_hit_analysis(gold: pd.DataFrame, raw: pd.DataFrame, optimized: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, gold_row in gold.iterrows():
        query_id = str(gold_row["query_id"])
        raw_candidates = raw[raw["query_id"].astype(str).eq(query_id)].copy()
        recs = optimized[optimized["query_id"].astype(str).eq(query_id)].copy()
        best_hit = best_match_rank(recs, gold_row, "rank")
        raw_hit = best_match_rank(raw_candidates, gold_row, "raw_rank")
        top1 = recs.sort_values("rank").head(1)
        top3 = recs.sort_values("rank").head(3)
        recommended_top1 = top1["recommended_place_name"].iloc[0] if len(top1) else ""
        recommended_top3 = "; ".join(top3["recommended_place_name"].astype(str).tolist())

        if best_hit is not None and best_hit <= 10:
            hit_row = recs[recs["rank"].eq(best_hit)].iloc[0]
            if float(hit_row.get("district_bonus", 0.0)) > 0:
                reason = "자치구 일치 또는 생활권 인접 후보가 상위에 배치되어 hit"
            elif float(hit_row.get("place_type_bonus", 0.0)) > 0:
                reason = "장소 유형 유사도가 상위 배치에 기여하여 hit"
            else:
                reason = "baseline_score와 보조 feature가 함께 작동하여 hit"
        elif raw_hit is None:
            reason = "정답 장소가 raw 후보군에 없어 recall 한계"
        elif raw_hit > 10:
            reason = "정답 장소가 raw 후보군에는 있었으나 bonus 부족으로 하위 랭크"
        else:
            top1_district = clean_text(top1["recommended_district"].iloc[0]) if len(top1) else ""
            if top1_district != clean_text(gold_row["district"]):
                reason = "장소 유형은 유사했으나 자치구 불일치로 miss"
            else:
                reason = "정답 후보가 Top10 근처에 있었으나 점수 차이로 miss"

        rows.append(
            {
                "query_id": query_id,
                "gold_place_name": gold_row["place_name"],
                "gold_district": gold_row["district"],
                "hit_at_1": best_hit is not None and best_hit <= 1,
                "hit_at_3": best_hit is not None and best_hit <= 3,
                "hit_at_5": best_hit is not None and best_hit <= 5,
                "hit_at_10": best_hit is not None and best_hit <= 10,
                "best_hit_rank": best_hit if best_hit is not None else "",
                "recommended_top1": recommended_top1,
                "recommended_top3": recommended_top3,
                "reason_estimate": reason,
            }
        )
    return pd.DataFrame(rows)


def add_hit_label(recommendations: pd.DataFrame, gold: pd.DataFrame) -> pd.Series:
    labels: list[int] = []
    gold_by_query = {query_id: group.copy() for query_id, group in gold.groupby("query_id", sort=False)}
    for _, rec in recommendations.iterrows():
        query_gold = gold_by_query.get(rec["query_id"], gold.iloc[0:0])
        labels.append(int(any(match_candidate(rec, gold_row) for _, gold_row in query_gold.iterrows())))
    return pd.Series(labels, index=recommendations.index)


def build_feature_contribution_summary(recommendations: pd.DataFrame, gold: pd.DataFrame) -> pd.DataFrame:
    analyzed = recommendations.copy()
    analyzed["is_hit"] = add_hit_label(analyzed, gold)
    rows: list[dict[str, Any]] = []
    for feature in FEATURE_COLUMNS:
        values = pd.to_numeric(analyzed[feature], errors="coerce").fillna(0.0)
        hits = analyzed["is_hit"]
        if values.std() == 0 or hits.std() == 0:
            corr = 0.0
        else:
            corr = float(values.corr(hits))
            if math.isnan(corr):
                corr = 0.0
        non_zero_count = int((values != 0).sum())
        if corr > 0.05:
            comment = "hit 후보와 양의 상관을 보여 성능 개선 근거로 설명 가능"
        elif non_zero_count == 0:
            comment = "현재 Top10 결과에서 활성화되지 않음"
        else:
            comment = "활성화되지만 단독 hit 상관은 제한적"
        rows.append(
            {
                "feature_name": feature,
                "non_zero_count": non_zero_count,
                "non_zero_ratio": non_zero_count / len(analyzed) if len(analyzed) else 0.0,
                "mean_bonus": float(values.mean()) if len(values) else 0.0,
                "max_bonus": float(values.max()) if len(values) else 0.0,
                "total_bonus": float(values.sum()) if len(values) else 0.0,
                "correlation_with_hit": corr,
                "comment": comment,
            }
        )
    return pd.DataFrame(rows)


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def run(
    gold_path: Path,
    raw_path: Path,
    existing_comparison_path: Path,
    output_dir: Path,
    top_k: int,
    k_values: list[int],
    search_mode: str,
    n_trials: int,
    random_state: int,
) -> None:
    gold = read_eval_csv(gold_path, "Gold evaluation queries")
    raw = validate_raw(read_csv_with_fallback(raw_path, "raw baseline recommendations"), gold)
    featured_raw = add_match_labels(add_feature_values(raw), gold)
    train_ids, validation_ids = make_split(gold["query_id"].astype(str).unique().tolist(), random_state)
    trials = build_trials(search_mode, n_trials, random_state)

    output_dir.mkdir(parents=True, exist_ok=True)
    print("=== reranking weight optimization ===")
    print(f"trial count: {len(trials)}")
    print(f"train queries: {len(train_ids)}, validation queries: {len(validation_ids)}")

    search_results, best_records = run_search(
        gold=gold,
        featured_raw=featured_raw,
        train_ids=train_ids,
        validation_ids=validation_ids,
        trials=trials,
        top_k=top_k,
        k_values=k_values,
    )
    search_results.to_csv(output_dir / "weight_search_results.csv", index=False, encoding="utf-8-sig")

    best_record = best_records["best_by_optimization_score"]
    best_weights = extract_weights(best_record)
    optimized_recommendations = rerank_candidates(featured_raw, best_weights, top_k)

    train_detail, train_summary = evaluate_subset(gold, optimized_recommendations, train_ids, k_values)
    validation_detail, validation_summary = evaluate_subset(gold, optimized_recommendations, validation_ids, k_values)
    full_detail, full_summary = evaluate_subset(
        gold,
        optimized_recommendations,
        set(gold["query_id"].astype(str)),
        k_values,
    )

    optimized_dir = output_dir / "optimized_proposed"
    split_dir = output_dir / "split_evaluation"
    optimized_dir.mkdir(parents=True, exist_ok=True)
    split_dir.mkdir(parents=True, exist_ok=True)

    optimized_recommendations.to_csv(
        optimized_dir / "recommendation_results.csv",
        index=False,
        encoding="utf-8-sig",
    )
    full_detail.to_csv(optimized_dir / "evaluation_result.csv", index=False, encoding="utf-8-sig")
    full_summary.to_csv(optimized_dir / "evaluation_result_summary.csv", index=False, encoding="utf-8-sig")
    save_summary(train_summary, split_dir / "train_result_summary.csv")
    save_summary(validation_summary, split_dir / "validation_result_summary.csv")
    save_summary(full_summary, split_dir / "full_result_summary.csv")

    feature_summary = build_feature_contribution_summary(optimized_recommendations, gold)
    feature_summary.to_csv(
        optimized_dir / "feature_contribution_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    hit_analysis = build_hit_analysis(gold, raw, optimized_recommendations)
    hit_analysis.to_csv(optimized_dir / "hit_analysis.csv", index=False, encoding="utf-8-sig")
    coverage = build_raw_candidate_coverage(gold, raw, optimized_recommendations)
    coverage.to_csv(output_dir / "raw_candidate_coverage.csv", index=False, encoding="utf-8-sig")

    if existing_comparison_path.is_file():
        existing_comparison = convert_existing_comparison(existing_comparison_path)
    else:
        existing_comparison = build_comparison_from_current(gold, raw, k_values, top_k)
    optimized_row = pd.DataFrame([metric_row_from_summary("optimized_proposed", full_summary)])
    comparison = pd.concat([existing_comparison, optimized_row], ignore_index=True)[COMPARISON_COLUMNS]
    comparison.to_csv(output_dir / "model_comparison_optimized.csv", index=False, encoding="utf-8-sig")

    best_payload = {
        "selection_basis": "highest train optimization_score",
        "optimization_formula": "0.35*NDCG@10 + 0.25*P@1 + 0.20*P@3 + 0.10*P@5 + 0.10*R@10",
        "search_mode": search_mode,
        "n_trials_requested": n_trials,
        "n_trials_evaluated": int(len(search_results)),
        "random_state": random_state,
        "train_query_count": int(len(train_ids)),
        "validation_query_count": int(len(validation_ids)),
        "best_weights": best_weights,
        "best_by_ndcg10": {
            "trial_id": int(best_records["best_by_ndcg10"]["trial_id"]),
            "weights": extract_weights(best_records["best_by_ndcg10"]),
            "train_NDCG@10": float(best_records["best_by_ndcg10"]["train_NDCG@10"]),
        },
        "best_by_p1": {
            "trial_id": int(best_records["best_by_p1"]["trial_id"]),
            "weights": extract_weights(best_records["best_by_p1"]),
            "train_P@1": float(best_records["best_by_p1"]["train_P@1"]),
        },
        "best_by_p3": {
            "trial_id": int(best_records["best_by_p3"]["trial_id"]),
            "weights": extract_weights(best_records["best_by_p3"]),
            "train_P@3": float(best_records["best_by_p3"]["train_P@3"]),
        },
        "best_by_optimization_score": {
            "trial_id": int(best_record["trial_id"]),
            "weights": best_weights,
            "train_metrics": summary_metrics(train_summary),
            "validation_metrics": summary_metrics(validation_summary),
            "full_metrics": summary_metrics(full_summary),
            "train_optimization_score": float(best_record["train_optimization_score"]),
            "validation_optimization_score": optimization_score(summary_metrics(validation_summary)),
            "full_optimization_score": optimization_score(summary_metrics(full_summary)),
        },
    }
    save_json(output_dir / "best_weights.json", best_payload)

    raw_recall_at_50 = float(coverage["in_raw_top50"].mean()) if len(coverage) else 0.0
    missing_raw = int((~coverage["in_raw_top50"]).sum())
    raw_present_not_top10 = int((coverage["in_raw_top50"] & ~coverage["in_optimized_top10"]).sum())
    print("\n=== best weights ===")
    print(json.dumps(best_weights, ensure_ascii=False, indent=2))
    print("\n=== optimized full summary ===")
    print(full_summary.to_string(index=False))
    print("\n=== raw candidate coverage ===")
    print(f"raw candidate recall@50: {raw_recall_at_50:.4f}")
    print(f"missing from raw candidates: {missing_raw}")
    print(f"in raw candidates but not optimized Top10: {raw_present_not_top10}")
    print(f"\nSaved: {output_dir}")


def main() -> int:
    args = parse_args()
    try:
        run(
            gold_path=Path(args.gold),
            raw_path=Path(args.raw),
            existing_comparison_path=Path(args.existing_comparison) if args.existing_comparison else Path(""),
            output_dir=Path(args.output_dir),
            top_k=args.top_k,
            k_values=args.k,
            search_mode=args.search_mode,
            n_trials=args.n_trials,
            random_state=args.random_state,
        )
    except (FileNotFoundError, DataValidationError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"[ERROR] file processing failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
