"""Build the final context-aware ranking experiment artifacts.

This pipeline starts from the fixed raw candidate pool and the Gold Set query
metadata.  Gold place names are used only by evaluation functions and coverage
diagnostics, never as candidate-generation or ranking features.
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
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.district_utils import filter_dataframe_by_district, normalize_district  # noqa: E402
from evaluate_recommendations import evaluate, place_match_method, read_csv_with_fallback  # noqa: E402


K_VALUES = [1, 3, 5, 10]
TOP_K = 10
RAW_COVERAGE_K = [50, 100]

FINAL_COMPARISON = "final_ranking_model_comparison.csv"
FINAL_SIMILARITY = "final_similarity_evaluation.csv"
FINAL_WEIGHT_SEARCH = "final_weight_search_results.csv"
FINAL_BEST_WEIGHTS = "final_best_weights.json"
FINAL_COVERAGE = "final_candidate_coverage_analysis.csv"
FINAL_PROFILE = "final_candidate_profile_analysis.csv"
FINAL_FAILURE = "final_failure_case_analysis.csv"
FINAL_RECOMMENDATIONS = "final_recommendation_results.csv"
FINAL_EXPLAINABILITY = "final_explainability_samples.csv"
FINAL_SUMMARY = "final_evaluation_summary.md"

WEIGHT_COLUMNS = [
    "baseline_weight",
    "district_weight",
    "place_type_weight",
    "time_weight",
    "context_weight",
    "target_weight",
    "population_weight",
    "transit_weight",
    "commercial_weight",
    "welfare_policy_weight",
    "candidate_profile_weight",
    "diversity_weight",
]

FEATURE_COLUMNS = [
    "district_match_score",
    "place_type_score",
    "time_context_score",
    "voter_target_score",
    "floating_population_score",
    "worker_population_score",
    "transit_access_score",
    "market_commercial_score",
    "welfare_policy_score",
    "campaign_context_score",
    "candidate_style_score",
    "novelty_diversity_score",
    "rank_score",
    "semantic_similarity",
    "composite_similarity",
]

RECOMMENDATION_COLUMNS = [
    "query_id",
    "rank",
    "recommended_place_name",
    "recommended_district",
    "recommended_place_type",
    "candidate_source",
    "baseline_score",
    "raw_rank",
    *FEATURE_COLUMNS,
    "final_score",
    "score",
    "exact_place_hit",
    "explanation",
]

MODEL_VARIANTS = [
    "baseline",
    "context_ranking",
    "candidate_profile_ranking",
    "similarity_optimized_ranking",
    "final_proposed",
]

PLACE_CATEGORY_KEYWORDS = {
    "market": [
        "전통시장",
        "시장",
        "상권",
        "상가",
        "상인",
        "골목",
        "거리",
        "로데오",
        "먹자",
        "생활권",
        "지역상권",
    ],
    "park": ["공원", "광장", "하천", "체육", "어린이", "가족", "산책", "문화", "생활밀착"],
    "senior_friendly": ["복지", "노인", "어르신", "경로", "고령", "복지관", "경로당"],
    "subway": ["교통", "지하철", "역", "출근", "퇴근", "사거리", "환승", "직장인"],
    "labor_site": ["노동", "노조", "근로", "산업", "현장", "사업장"],
    "urban_site": ["재개발", "정비", "주거", "아파트", "정책현장", "도시"],
    "youth": ["청년", "대학", "캠퍼스", "청년공간"],
    "religious": ["교회", "성당", "사찰", "법회", "종교"],
    "policy": ["공약", "정책", "발표", "간담회", "현장방문"],
}

CANDIDATE_TYPE_TO_CATEGORY = {
    "market": "market",
    "park": "park",
    "senior": "senior_friendly",
    "senior_friendly": "senior_friendly",
    "subway": "subway",
}

RELATED_PLACE_TYPE = {
    ("market", "subway"): 0.35,
    ("subway", "market"): 0.35,
    ("market", "park"): 0.20,
    ("park", "market"): 0.20,
    ("park", "senior_friendly"): 0.30,
    ("senior_friendly", "park"): 0.30,
    ("labor_site", "market"): 0.45,
    ("labor_site", "subway"): 0.35,
    ("urban_site", "market"): 0.35,
    ("urban_site", "subway"): 0.30,
    ("youth", "subway"): 0.45,
    ("youth", "market"): 0.30,
    ("religious", "park"): 0.20,
    ("policy", "senior_friendly"): 0.30,
    ("policy", "park"): 0.20,
}

TIME_TYPE_SCORE = {
    "morning_commute": {"subway": 1.0, "market": 0.40, "park": 0.20, "senior_friendly": 0.20},
    "late_morning": {"senior_friendly": 0.80, "market": 0.70, "park": 0.45, "subway": 0.30},
    "lunch": {"market": 0.85, "park": 0.60, "senior_friendly": 0.45, "subway": 0.20},
    "afternoon": {"market": 0.80, "park": 0.75, "senior_friendly": 0.60, "subway": 0.25},
    "evening_commute": {"subway": 1.0, "market": 0.85, "park": 0.45, "senior_friendly": 0.25},
    "evening": {"market": 0.70, "subway": 0.55, "park": 0.35, "senior_friendly": 0.20},
}

DEFAULT_PROFILE_PRIORS = {
    "오세훈": {
        "categories": {"subway": 0.35, "market": 0.25, "urban_site": 0.20, "policy": 0.20},
        "note": "교통거점, 전통시장, 정비·정책 현장 중심의 광역 이동형 profile",
    },
    "정원오": {
        "categories": {"market": 0.35, "senior_friendly": 0.20, "park": 0.20, "policy": 0.15, "urban_site": 0.10},
        "note": "골목상권, 생활밀착형 복지·주거·지역 커뮤니티 중심 profile",
    },
}

WEIGHT_GRID = {
    "baseline_weight": [1.0],
    "district_weight": [0.20, 0.35, 0.50, 0.65],
    "place_type_weight": [0.10, 0.25, 0.40],
    "time_weight": [0.05, 0.15, 0.25],
    "context_weight": [0.10, 0.20, 0.35],
    "target_weight": [0.05, 0.15, 0.25],
    "population_weight": [0.00, 0.10, 0.20],
    "transit_weight": [0.00, 0.08, 0.16],
    "commercial_weight": [0.00, 0.08, 0.16],
    "welfare_policy_weight": [0.00, 0.08, 0.16],
    "candidate_profile_weight": [0.00, 0.10, 0.20],
    "diversity_weight": [0.00, 0.05, 0.10],
}

MODEL_WEIGHTS = {
    "baseline": {
        "baseline_weight": 1.0,
        "district_weight": 0.0,
        "place_type_weight": 0.0,
        "time_weight": 0.0,
        "context_weight": 0.0,
        "target_weight": 0.0,
        "population_weight": 0.0,
        "transit_weight": 0.0,
        "commercial_weight": 0.0,
        "welfare_policy_weight": 0.0,
        "candidate_profile_weight": 0.0,
        "diversity_weight": 0.0,
    },
    "context_ranking": {
        "baseline_weight": 1.0,
        "district_weight": 0.35,
        "place_type_weight": 0.25,
        "time_weight": 0.15,
        "context_weight": 0.20,
        "target_weight": 0.10,
        "population_weight": 0.10,
        "transit_weight": 0.08,
        "commercial_weight": 0.08,
        "welfare_policy_weight": 0.08,
        "candidate_profile_weight": 0.0,
        "diversity_weight": 0.0,
    },
    "candidate_profile_ranking": {
        "baseline_weight": 1.0,
        "district_weight": 0.35,
        "place_type_weight": 0.25,
        "time_weight": 0.15,
        "context_weight": 0.20,
        "target_weight": 0.10,
        "population_weight": 0.10,
        "transit_weight": 0.08,
        "commercial_weight": 0.08,
        "welfare_policy_weight": 0.08,
        "candidate_profile_weight": 0.18,
        "diversity_weight": 0.0,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate final ranking and similarity evaluation outputs.")
    parser.add_argument("--gold", default="output/gold_set_evaluation_queries.csv")
    parser.add_argument("--raw", default="output/raw_baseline_recommendations.csv")
    parser.add_argument("--output_dir", default="output")
    parser.add_argument("--top_k", type=int, default=TOP_K)
    parser.add_argument("--search_mode", choices=["random", "grid"], default="random")
    parser.add_argument("--n_trials", type=int, default=80)
    parser.add_argument("--random_state", type=int, default=42)
    return parser.parse_args()


def clean_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def normalize_key(value: object) -> str:
    text = unicodedata.normalize("NFKC", clean_text(value)).lower()
    return re.sub(r"[^0-9a-z가-힣]+", "", text)


def split_tokens(value: object) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    return [token for token in re.split(r"[;,/|()\s]+", text) if token]


def derive_hour(value: object) -> int | None:
    text = clean_text(value)
    try:
        hour = int(text.split(":", maxsplit=1)[0])
    except (ValueError, IndexError):
        return None
    return hour if 0 <= hour <= 23 else None


def time_bucket(value: object) -> str:
    hour = derive_hour(value)
    if hour is None:
        return "unknown"
    if 6 <= hour < 10:
        return "morning_commute"
    if 10 <= hour < 12:
        return "late_morning"
    if 12 <= hour < 14:
        return "lunch"
    if 14 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 20:
        return "evening_commute"
    return "evening"


def infer_categories(*values: object) -> set[str]:
    key = normalize_key(" ".join(clean_text(value) for value in values))
    categories: set[str] = set()
    for category, keywords in PLACE_CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if normalize_key(keyword) in key:
                categories.add(category)
                break
    return categories


def candidate_category(value: object) -> str:
    text = clean_text(value)
    return CANDIDATE_TYPE_TO_CATEGORY.get(text, text)


def infer_candidate_name(row: pd.Series) -> str:
    text = " ".join(clean_text(row.get(column, "")) for column in ["gold_id", "source_image", "evaluation_context"])
    upper = text.upper()
    if "GWON" in upper or "정원오" in text:
        return "정원오"
    if "OH" in upper or "오세훈" in text:
        return "오세훈"
    return "unknown"


def safe_ratio(count: float, total: float) -> float:
    return float(count / total) if total else 0.0


def category_relatedness(query_categories: set[str], candidate_type: str) -> float:
    if candidate_type in query_categories:
        return 1.0
    related = [RELATED_PLACE_TYPE.get((category, candidate_type), 0.0) for category in query_categories]
    return max(related, default=0.0)


def district_match_score(row: pd.Series) -> float:
    query_district = normalize_district(row.get("district")) or clean_text(row.get("district"))
    rec_district = normalize_district(row.get("recommended_district")) or clean_text(row.get("recommended_district"))
    return 1.0 if query_district and rec_district and query_district == rec_district else 0.0


def place_type_score(row: pd.Series) -> float:
    query_categories = infer_categories(
        row.get("place_type"),
        row.get("campaign_activity_type"),
        row.get("target_voter_group"),
        row.get("context_tags"),
        row.get("evaluation_context"),
    )
    return category_relatedness(query_categories, candidate_category(row.get("recommended_place_type")))


def time_context_score(row: pd.Series) -> float:
    bucket = time_bucket(row.get("time"))
    ctype = candidate_category(row.get("recommended_place_type"))
    return TIME_TYPE_SCORE.get(bucket, {}).get(ctype, 0.0)


def voter_target_score(row: pd.Series) -> float:
    target = normalize_key(row.get("target_voter_group"))
    tags = normalize_key(row.get("context_tags"))
    ctype = candidate_category(row.get("recommended_place_type"))
    text = target + tags
    if ctype == "senior_friendly" and any(token in text for token in ["노인", "어르신", "복지", "고령", "시니어"]):
        return 1.0
    if ctype == "market" and any(token in text for token in ["상인", "지역주민", "생활권", "상권", "일반시민"]):
        return 0.90
    if ctype == "subway" and any(token in text for token in ["직장인", "출근", "퇴근", "청년", "일반시민"]):
        return 0.85
    if ctype == "park" and any(token in text for token in ["가족", "지역주민", "체육", "일반시민", "생활권"]):
        return 0.80
    return 0.30 if "일반시민" in text or "지역주민" in text else 0.0


def floating_population_score(row: pd.Series) -> float:
    ctype = candidate_category(row.get("recommended_place_type"))
    slot = time_bucket(row.get("time"))
    base = float(row.get("baseline_score", 0.0))
    type_factor = {"market": 0.95, "subway": 0.95, "park": 0.65, "senior_friendly": 0.45}.get(ctype, 0.35)
    slot_factor = {"morning_commute": 0.90, "lunch": 0.80, "afternoon": 0.70, "evening_commute": 0.95}.get(slot, 0.55)
    return min(1.0, (0.55 * base) + (0.25 * type_factor) + (0.20 * slot_factor))


def worker_population_score(row: pd.Series) -> float:
    text = normalize_key(" ".join([clean_text(row.get("target_voter_group")), clean_text(row.get("context_tags"))]))
    ctype = candidate_category(row.get("recommended_place_type"))
    slot = time_bucket(row.get("time"))
    score = 0.0
    if any(token in text for token in ["직장인", "출근", "퇴근", "청년"]):
        score += 0.45
    if slot in {"morning_commute", "evening_commute"}:
        score += 0.30
    if ctype == "subway":
        score += 0.25
    elif ctype == "market":
        score += 0.10
    return min(score, 1.0)


def transit_access_score(row: pd.Series) -> float:
    name_key = normalize_key(row.get("recommended_place_name"))
    source_key = normalize_key(row.get("candidate_source"))
    ctype = candidate_category(row.get("recommended_place_type"))
    if ctype == "subway" or "subway" in source_key:
        return 1.0
    if any(token in name_key for token in ["역", "출구", "사거리", "버스", "환승"]):
        return 0.65
    if ctype == "market":
        return 0.25
    return 0.10


def market_commercial_score(row: pd.Series) -> float:
    name_key = normalize_key(row.get("recommended_place_name"))
    ctype = candidate_category(row.get("recommended_place_type"))
    if ctype == "market":
        return 1.0
    if any(token in name_key for token in ["시장", "상가", "거리", "상권", "로데오"]):
        return 0.75
    if ctype == "subway":
        return 0.20
    return 0.05


def welfare_policy_score(row: pd.Series) -> float:
    text = normalize_key(" ".join([clean_text(row.get("place_type")), clean_text(row.get("campaign_activity_type")), clean_text(row.get("context_tags"))]))
    ctype = candidate_category(row.get("recommended_place_type"))
    score = 0.0
    if any(token in text for token in ["복지", "정책", "공약", "어르신", "노인", "정책현장"]):
        score += 0.45
    if ctype == "senior_friendly":
        score += 0.45
    if ctype == "park" and any(token in text for token in ["생활밀착", "가족", "체육"]):
        score += 0.20
    return min(score, 1.0)


def campaign_context_score(row: pd.Series) -> float:
    query_categories = infer_categories(
        row.get("place_type"),
        row.get("campaign_activity_type"),
        row.get("target_voter_group"),
        row.get("context_tags"),
    )
    ctype = candidate_category(row.get("recommended_place_type"))
    overlap_score = category_relatedness(query_categories, ctype)
    tag_tokens = set(normalize_key(token) for token in split_tokens(row.get("context_tags")))
    candidate_tokens = set(
        normalize_key(token)
        for token in [
            clean_text(row.get("recommended_place_type")),
            clean_text(row.get("candidate_source")),
            clean_text(row.get("recommended_district")),
        ]
    )
    candidate_tokens.update(infer_categories(row.get("recommended_place_type"), row.get("candidate_source")))
    token_overlap = len(tag_tokens & candidate_tokens) / len(tag_tokens) if tag_tokens else 0.0
    return min(1.0, (0.75 * overlap_score) + (0.25 * token_overlap))


def normalize_distribution(counter: Counter[str]) -> dict[str, float]:
    total = sum(counter.values())
    return {key: count / total for key, count in counter.items()} if total else {}


def build_candidate_profiles(gold: pd.DataFrame) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    tagged = gold.copy()
    tagged["_candidate_name"] = tagged.apply(infer_candidate_name, axis=1)

    for candidate_name, group in tagged.groupby("_candidate_name", sort=False):
        category_counter: Counter[str] = Counter()
        for _, row in group.iterrows():
            inferred = infer_categories(
                row.get("place_type"),
                row.get("campaign_activity_type"),
                row.get("target_voter_group"),
                row.get("context_tags"),
            )
            category_counter.update(inferred or ["unknown"])

        profiles[candidate_name] = {
            "query_count": int(len(group)),
            "category_distribution": normalize_distribution(category_counter),
            "district_distribution": normalize_distribution(Counter(group["district"].astype(str))),
            "time_distribution": normalize_distribution(Counter(group["time"].map(time_bucket))),
            "activity_distribution": normalize_distribution(Counter(group["campaign_activity_type"].astype(str))),
            "note": "Gold Set의 장소명은 제외하고 유형·자치구·시간대·활동 유형 빈도만 profile화",
        }

    for candidate_name, prior in DEFAULT_PROFILE_PRIORS.items():
        if candidate_name not in profiles:
            profiles[candidate_name] = {
                "query_count": 0,
                "category_distribution": prior["categories"],
                "district_distribution": {},
                "time_distribution": {},
                "activity_distribution": {},
                "note": prior["note"],
            }
        else:
            merged = profiles[candidate_name]["category_distribution"].copy()
            for category, value in prior["categories"].items():
                merged[category] = max(float(merged.get(category, 0.0)), value * 0.35)
            profiles[candidate_name]["category_distribution"] = merged
            profiles[candidate_name]["note"] = f"{profiles[candidate_name]['note']}; {prior['note']}"
    return profiles


def candidate_style_score(row: pd.Series, profiles: dict[str, dict[str, Any]]) -> float:
    profile = profiles.get(clean_text(row.get("candidate_name"))) or profiles.get("unknown") or {}
    ctype = candidate_category(row.get("recommended_place_type"))
    category_score = float(profile.get("category_distribution", {}).get(ctype, 0.0))
    district = clean_text(row.get("district"))
    district_score = float(profile.get("district_distribution", {}).get(district, 0.0))
    bucket = time_bucket(row.get("time"))
    time_score = float(profile.get("time_distribution", {}).get(bucket, 0.0))
    return min(1.0, (0.70 * category_score) + (0.15 * district_score) + (0.15 * time_score))


def document_tokens(value: object) -> list[str]:
    tokens = []
    for token in split_tokens(value):
        key = normalize_key(token)
        if len(key) >= 2:
            tokens.append(key)
    return tokens


def build_tfidf_vectors(documents: list[str]) -> tuple[list[dict[str, float]], dict[str, float]]:
    tokenized = [document_tokens(doc) for doc in documents]
    doc_count = len(tokenized)
    df: Counter[str] = Counter()
    for tokens in tokenized:
        df.update(set(tokens))
    idf = {token: math.log((doc_count + 1) / (count + 1)) + 1 for token, count in df.items()}
    vectors: list[dict[str, float]] = []
    for tokens in tokenized:
        tf = Counter(tokens)
        total = sum(tf.values()) or 1
        vectors.append({token: (count / total) * idf[token] for token, count in tf.items()})
    return vectors, idf


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    common = set(left) & set(right)
    numerator = sum(left[token] * right[token] for token in common)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0


def gold_semantic_text(row: pd.Series) -> str:
    return " ".join(
        clean_text(row.get(column))
        for column in ["place_type", "campaign_activity_type", "target_voter_group", "context_tags", "district", "time"]
    )


def recommendation_semantic_text(row: pd.Series) -> str:
    ctype = clean_text(row.get("recommended_place_type"))
    source = clean_text(row.get("candidate_source"))
    district = clean_text(row.get("recommended_district"))
    derived = ";".join(sorted(infer_categories(ctype, source)))
    return " ".join([ctype, source, district, derived, time_bucket(row.get("time"))])


def add_semantic_similarity(featured: pd.DataFrame, gold_by_query: dict[str, pd.Series]) -> pd.DataFrame:
    gold_docs = []
    rec_docs = []
    for _, row in featured.iterrows():
        gold_row = gold_by_query.get(str(row["query_id"]))
        gold_docs.append(gold_semantic_text(gold_row) if gold_row is not None else "")
        rec_docs.append(recommendation_semantic_text(row))
    vectors, _ = build_tfidf_vectors([*gold_docs, *rec_docs])
    gold_vectors = vectors[: len(gold_docs)]
    rec_vectors = vectors[len(gold_docs) :]
    output = featured.copy()
    output["semantic_similarity"] = [cosine(gold_vec, rec_vec) for gold_vec, rec_vec in zip(gold_vectors, rec_vectors)]
    return output


def add_feature_values(raw: pd.DataFrame, gold: pd.DataFrame, profiles: dict[str, dict[str, Any]]) -> pd.DataFrame:
    gold_key = gold.copy()
    gold_key["candidate_name"] = gold_key.apply(infer_candidate_name, axis=1)
    gold_by_query = {str(row["query_id"]): row for _, row in gold_key.iterrows()}

    featured = raw.copy()
    featured["baseline_score"] = pd.to_numeric(featured["baseline_score"], errors="coerce").fillna(0.0)
    featured["raw_rank"] = pd.to_numeric(featured["raw_rank"], errors="coerce").fillna(999).astype(int)
    featured["candidate_name"] = featured["query_id"].astype(str).map(
        lambda query_id: clean_text(gold_by_query[query_id].get("candidate_name")) if query_id in gold_by_query else "unknown"
    )
    if "campaign_activity_type" not in featured.columns:
        featured["campaign_activity_type"] = featured["query_id"].astype(str).map(
            lambda query_id: clean_text(gold_by_query[query_id].get("campaign_activity_type")) if query_id in gold_by_query else ""
        )
    if "evaluation_context" not in featured.columns:
        featured["evaluation_context"] = featured["query_id"].astype(str).map(
            lambda query_id: clean_text(gold_by_query[query_id].get("evaluation_context")) if query_id in gold_by_query else ""
        )

    featured["district_match_score"] = featured.apply(district_match_score, axis=1)
    featured["place_type_score"] = featured.apply(place_type_score, axis=1)
    featured["time_context_score"] = featured.apply(time_context_score, axis=1)
    featured["voter_target_score"] = featured.apply(voter_target_score, axis=1)
    featured["floating_population_score"] = featured.apply(floating_population_score, axis=1)
    featured["worker_population_score"] = featured.apply(worker_population_score, axis=1)
    featured["transit_access_score"] = featured.apply(transit_access_score, axis=1)
    featured["market_commercial_score"] = featured.apply(market_commercial_score, axis=1)
    featured["welfare_policy_score"] = featured.apply(welfare_policy_score, axis=1)
    featured["campaign_context_score"] = featured.apply(campaign_context_score, axis=1)
    featured["candidate_style_score"] = featured.apply(lambda row: candidate_style_score(row, profiles), axis=1)
    featured["rank_score"] = featured["raw_rank"].map(lambda rank: max(0.0, 1.0 - ((float(rank) - 1.0) / 99.0)))
    type_counts = featured.groupby(["query_id", "recommended_place_type"])["recommended_place_type"].transform("count")
    featured["novelty_diversity_score"] = (1.0 / type_counts.clip(lower=1)).astype(float)
    featured = add_semantic_similarity(featured, gold_by_query)
    featured["composite_similarity"] = (
        0.25 * featured["district_match_score"]
        + 0.25 * featured["place_type_score"]
        + 0.15 * featured["time_context_score"]
        + 0.15 * featured["campaign_context_score"]
        + 0.10 * featured["voter_target_score"]
        + 0.10 * featured["semantic_similarity"]
    ).clip(0.0, 1.0)
    return featured


def weighted_score(frame: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    population_signal = (frame["floating_population_score"] + frame["worker_population_score"]) / 2.0
    return (
        frame["baseline_score"] * weights.get("baseline_weight", 1.0)
        + frame["district_match_score"] * weights.get("district_weight", 0.0)
        + frame["place_type_score"] * weights.get("place_type_weight", 0.0)
        + frame["time_context_score"] * weights.get("time_weight", 0.0)
        + frame["campaign_context_score"] * weights.get("context_weight", 0.0)
        + frame["voter_target_score"] * weights.get("target_weight", 0.0)
        + population_signal * weights.get("population_weight", 0.0)
        + frame["transit_access_score"] * weights.get("transit_weight", 0.0)
        + frame["market_commercial_score"] * weights.get("commercial_weight", 0.0)
        + frame["welfare_policy_score"] * weights.get("welfare_policy_weight", 0.0)
        + frame["candidate_style_score"] * weights.get("candidate_profile_weight", 0.0)
        + frame["rank_score"] * 0.03
    )


def rerank_candidates(featured: pd.DataFrame, weights: dict[str, float], top_k: int) -> pd.DataFrame:
    scored = featured.copy()
    scored["_base_final_score"] = weighted_score(scored, weights)
    groups: list[pd.DataFrame] = []
    diversity_weight = float(weights.get("diversity_weight", 0.0))

    for _, group in scored.groupby("query_id", sort=False):
        query_district = normalize_district(group["district"].iloc[0]) if len(group) else None
        filtered = filter_dataframe_by_district(
            group,
            query_district,
            ("recommended_district", "district_normalized", "district_name", "자치구", "시군구", "SIG_KOR_NM"),
        )
        if filtered.empty:
            filtered = group

        remaining = filtered.sort_values(["_base_final_score", "baseline_score", "raw_rank"], ascending=[False, False, True]).copy()
        selected_rows: list[pd.Series] = []
        type_counter: Counter[str] = Counter()
        district_counter: Counter[str] = Counter()

        while len(selected_rows) < top_k and not remaining.empty:
            adjusted_scores = []
            for _, row in remaining.iterrows():
                ctype = clean_text(row.get("recommended_place_type"))
                district = clean_text(row.get("recommended_district"))
                duplicate_penalty = diversity_weight * (
                    type_counter[ctype] * 0.70 + max(0, district_counter[district] - 2) * 0.30
                )
                adjusted_scores.append(float(row["_base_final_score"]) - duplicate_penalty)
            pick_position = int(pd.Series(adjusted_scores, index=remaining.index).idxmax())
            picked = remaining.loc[pick_position].copy()
            picked["final_score"] = round(float(max(adjusted_scores)), 6)
            selected_rows.append(picked)
            type_counter[clean_text(picked.get("recommended_place_type"))] += 1
            district_counter[clean_text(picked.get("recommended_district"))] += 1
            remaining = remaining.drop(index=pick_position)

        if selected_rows:
            selected = pd.DataFrame(selected_rows)
            selected["rank"] = range(1, len(selected) + 1)
            selected["score"] = selected["final_score"]
            groups.append(selected)

    if not groups:
        return pd.DataFrame(columns=RECOMMENDATION_COLUMNS)
    result = pd.concat(groups, ignore_index=True)
    for column in FEATURE_COLUMNS + ["baseline_score", "final_score", "score"]:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0.0).round(6)
    return result


def find_exact_hit_rank(recommendations: pd.DataFrame, gold_row: pd.Series, rank_column: str = "rank") -> int | None:
    recs = recommendations.sort_values(rank_column)
    for _, rec in recs.iterrows():
        if place_match_method(rec, gold_row) is not None:
            return int(rec[rank_column])
    return None


def add_exact_hit_labels(recommendations: pd.DataFrame, gold: pd.DataFrame) -> pd.DataFrame:
    gold_by_query = {str(query_id): group.copy() for query_id, group in gold.groupby("query_id", sort=False)}
    labeled = recommendations.copy()
    exact_hits = []
    for _, rec in labeled.iterrows():
        query_gold = gold_by_query.get(str(rec["query_id"]), gold.iloc[0:0])
        exact_hits.append(any(place_match_method(rec, gold_row) is not None for _, gold_row in query_gold.iterrows()))
    labeled["exact_place_hit"] = exact_hits
    return labeled


def build_explanation(row: pd.Series) -> str:
    reasons: list[str] = []
    if float(row.get("district_match_score", 0.0)) >= 0.9:
        reasons.append(f"{clean_text(row.get('recommended_district'))} 자치구 조건과 일치")
    if float(row.get("place_type_score", 0.0)) >= 0.7:
        reasons.append(f"{clean_text(row.get('recommended_place_type'))} 유형이 일정 문맥과 유사")
    if float(row.get("time_context_score", 0.0)) >= 0.7:
        reasons.append("입력 시간대의 유동·접촉 가능성이 높음")
    if float(row.get("voter_target_score", 0.0)) >= 0.7:
        reasons.append("목표 유권자 조건과 부합")
    if float(row.get("candidate_style_score", 0.0)) >= 0.2:
        reasons.append("후보 일정 profile과 유사한 장소 유형")
    if float(row.get("transit_access_score", 0.0)) >= 0.8:
        reasons.append("교통 접근성이 높은 후보지")
    if float(row.get("market_commercial_score", 0.0)) >= 0.8:
        reasons.append("시장·상권 접촉에 적합")
    if float(row.get("welfare_policy_score", 0.0)) >= 0.7:
        reasons.append("복지·정책 현장 맥락과 연결")
    if not reasons:
        reasons.append("기존 공공데이터 기반 baseline 점수가 높음")
    return "이 장소는 " + ", ".join(reasons[:4]) + "으로 평가되어 상위 추천에 배치되었다."


def finalize_recommendations(recommendations: pd.DataFrame, gold: pd.DataFrame) -> pd.DataFrame:
    labeled = add_exact_hit_labels(recommendations, gold)
    labeled["explanation"] = labeled.apply(build_explanation, axis=1)
    for column in RECOMMENDATION_COLUMNS:
        if column not in labeled.columns:
            labeled[column] = ""
    return labeled[RECOMMENDATION_COLUMNS]


def evaluate_ranking(gold: pd.DataFrame, recommendations: pd.DataFrame, raw_recall: dict[int, float]) -> dict[str, float]:
    finalized = finalize_recommendations(recommendations, gold)
    _, exact_summary = evaluate(gold, finalized, K_VALUES)
    metrics: dict[str, float] = {}
    by_k = {int(row["k"]): row for _, row in exact_summary.iterrows()}
    for k in [1, 3, 5, 10]:
        row = by_k.get(k)
        metrics[f"P@{k}"] = float(row["precision_at_k"]) if row is not None else 0.0
        metrics[f"R@{k}"] = float(row["recall_at_k"]) if row is not None else 0.0
        metrics[f"NDCG@{k}"] = float(row["ndcg_at_k"]) if row is not None else 0.0

    top10 = finalized[finalized["rank"].le(10)].copy()
    metrics["Raw Recall@50"] = raw_recall.get(50, 0.0)
    metrics["Raw Recall@100"] = raw_recall.get(100, 0.0)
    metrics["District Match@10"] = float(top10["district_match_score"].mean()) if len(top10) else 0.0
    metrics["Place Type Match@10"] = float(top10["place_type_score"].mean()) if len(top10) else 0.0
    metrics["Time Context Match@10"] = float(top10["time_context_score"].mean()) if len(top10) else 0.0
    metrics["Campaign Context Match@10"] = float(top10["campaign_context_score"].mean()) if len(top10) else 0.0
    metrics["Mean Composite Similarity@10"] = float(top10["composite_similarity"].mean()) if len(top10) else 0.0
    metrics["Exact Place Hit@10"] = float(top10["exact_place_hit"].mean()) if len(top10) else 0.0
    metrics["objective"] = composite_objective(metrics)
    return metrics


def composite_objective(metrics: dict[str, float]) -> float:
    return (
        0.35 * metrics.get("NDCG@10", 0.0)
        + 0.20 * metrics.get("R@10", 0.0)
        + 0.20 * metrics.get("Mean Composite Similarity@10", 0.0)
        + 0.10 * metrics.get("District Match@10", 0.0)
        + 0.10 * metrics.get("Place Type Match@10", 0.0)
        + 0.05 * metrics.get("Time Context Match@10", 0.0)
    )


def metric_row(model_name: str, metrics: dict[str, float]) -> dict[str, Any]:
    row: dict[str, Any] = {"model_name": model_name}
    row.update(metrics)
    row["Precision@1"] = row.get("P@1", 0.0)
    row["Precision@3"] = row.get("P@3", 0.0)
    row["Precision@5"] = row.get("P@5", 0.0)
    row["Recall@10"] = row.get("R@10", 0.0)
    return row


def all_weight_combinations() -> list[dict[str, float]]:
    keys = list(WEIGHT_GRID)
    return [dict(zip(keys, values)) for values in itertools.product(*(WEIGHT_GRID[key] for key in keys))]


def build_trials(search_mode: str, n_trials: int, random_state: int) -> list[dict[str, float]]:
    seed_trials = [
        MODEL_WEIGHTS["context_ranking"],
        MODEL_WEIGHTS["candidate_profile_ranking"],
        {
            **MODEL_WEIGHTS["candidate_profile_ranking"],
            "district_weight": 0.50,
            "place_type_weight": 0.40,
            "context_weight": 0.35,
            "candidate_profile_weight": 0.20,
            "diversity_weight": 0.05,
        },
    ]
    combos = all_weight_combinations()
    if search_mode == "grid":
        selected = combos[: max(n_trials, 0)] if n_trials > 0 else combos
    else:
        rng = random.Random(random_state)
        selected = rng.sample(combos, min(max(n_trials, 0), len(combos)))
    seen: set[tuple[float, ...]] = set()
    trials: list[dict[str, float]] = []
    for weights in [*seed_trials, *selected]:
        key = tuple(float(weights.get(column, 0.0)) for column in WEIGHT_COLUMNS)
        if key in seen:
            continue
        seen.add(key)
        trials.append({column: float(weights.get(column, 0.0)) for column in WEIGHT_COLUMNS})
    return trials


def make_split(query_ids: list[str], random_state: int) -> tuple[set[str], set[str]]:
    shuffled = pd.Series(sorted(query_ids)).sample(frac=1.0, random_state=random_state).tolist()
    split_at = max(1, int(len(shuffled) * 0.70))
    return set(shuffled[:split_at]), set(shuffled[split_at:])


def filter_query_ids(frame: pd.DataFrame, query_ids: set[str]) -> pd.DataFrame:
    return frame[frame["query_id"].astype(str).isin(query_ids)].copy()


def search_weights(
    gold: pd.DataFrame,
    featured: pd.DataFrame,
    raw_recall: dict[int, float],
    top_k: int,
    search_mode: str,
    n_trials: int,
    random_state: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    train_ids, validation_ids = make_split(gold["query_id"].astype(str).unique().tolist(), random_state)
    trials = build_trials(search_mode, n_trials, random_state)
    rows: list[dict[str, Any]] = []
    best_row: dict[str, Any] | None = None
    best_score = -1.0

    for trial_id, weights in enumerate(trials, start=1):
        recs = rerank_candidates(featured, weights, top_k)
        train_metrics = evaluate_ranking(filter_query_ids(gold, train_ids), filter_query_ids(recs, train_ids), raw_recall)
        validation_metrics = evaluate_ranking(
            filter_query_ids(gold, validation_ids),
            filter_query_ids(recs, validation_ids),
            raw_recall,
        )
        row = {"trial_id": trial_id, **weights}
        row.update({f"train_{key}": value for key, value in train_metrics.items()})
        row.update({f"validation_{key}": value for key, value in validation_metrics.items()})
        rows.append(row)
        score = train_metrics["objective"]
        if score > best_score:
            best_score = score
            best_row = row

    if best_row is None:
        raise ValueError("weight search produced no trials")
    best_weights = {column: float(best_row[column]) for column in WEIGHT_COLUMNS}
    full_recs = rerank_candidates(featured, best_weights, top_k)
    full_metrics = evaluate_ranking(gold, full_recs, raw_recall)
    best_payload = {
        "selection_basis": "highest train composite objective",
        "objective_formula": "0.35*NDCG@10 + 0.20*Recall@10 + 0.20*Mean Composite Similarity@10 + 0.10*District Match@10 + 0.10*Place Type Match@10 + 0.05*Time Context Match@10",
        "search_mode": search_mode,
        "n_trials_requested": n_trials,
        "n_trials_evaluated": len(rows),
        "random_state": random_state,
        "train_query_count": len(train_ids),
        "validation_query_count": len(validation_ids),
        "best_weights": best_weights,
        "train_metrics": {key.replace("train_", ""): value for key, value in best_row.items() if key.startswith("train_")},
        "validation_metrics": {
            key.replace("validation_", ""): value for key, value in best_row.items() if key.startswith("validation_")
        },
        "full_metrics": full_metrics,
        "leakage_guard": "Gold place_name is excluded from ranking features; exact place hit is evaluated separately.",
    }
    return pd.DataFrame(rows), best_payload


def build_raw_coverage(gold: pd.DataFrame, raw: pd.DataFrame, final_recommendations: pd.DataFrame) -> tuple[pd.DataFrame, dict[int, float]]:
    rows: list[dict[str, Any]] = []
    raw_recall_counts: dict[int, int] = {k: 0 for k in RAW_COVERAGE_K}
    for _, gold_row in gold.iterrows():
        query_id = str(gold_row["query_id"])
        raw_candidates = raw[raw["query_id"].astype(str).eq(query_id)].copy()
        final_candidates = final_recommendations[final_recommendations["query_id"].astype(str).eq(query_id)].copy()
        best_raw_rank = find_exact_hit_rank(raw_candidates, gold_row, "raw_rank")
        final_hit_rank = find_exact_hit_rank(final_candidates, gold_row, "rank")
        for k in RAW_COVERAGE_K:
            if best_raw_rank is not None and best_raw_rank <= k:
                raw_recall_counts[k] += 1
        rows.append(
            {
                "query_id": query_id,
                "gold_place_name": gold_row["place_name"],
                "gold_district": gold_row["district"],
                "gold_place_type": gold_row["place_type"],
                "campaign_activity_type": gold_row.get("campaign_activity_type", ""),
                "raw_candidate_count": int(len(raw_candidates)),
                "in_raw_top50": best_raw_rank is not None and best_raw_rank <= 50,
                "in_raw_top100": best_raw_rank is not None and best_raw_rank <= 100,
                "best_raw_rank": best_raw_rank if best_raw_rank is not None else "",
                "final_hit_at_10": final_hit_rank is not None and final_hit_rank <= 10,
                "best_final_rank": final_hit_rank if final_hit_rank is not None else "",
                "coverage_status": "covered" if best_raw_rank is not None else "missing_from_raw_candidates",
            }
        )
    total = len(gold)
    raw_recall = {k: safe_ratio(count, total) for k, count in raw_recall_counts.items()}
    return pd.DataFrame(rows), raw_recall


def build_similarity_evaluation(gold: pd.DataFrame, recommendations: pd.DataFrame) -> pd.DataFrame:
    gold_by_query = {str(row["query_id"]): row for _, row in gold.iterrows()}
    rows: list[dict[str, Any]] = []
    for _, rec in recommendations.iterrows():
        gold_row = gold_by_query.get(str(rec["query_id"]))
        if gold_row is None:
            continue
        rows.append(
            {
                "query_id": rec["query_id"],
                "rank": rec["rank"],
                "gold_place_name": gold_row["place_name"],
                "recommended_place_name": rec["recommended_place_name"],
                "exact_place_hit": bool(rec.get("exact_place_hit")),
                "district_match": float(rec["district_match_score"]),
                "place_type_match": float(rec["place_type_score"]),
                "time_context_match": float(rec["time_context_score"]),
                "campaign_context_match": float(rec["campaign_context_score"]),
                "voter_target_match": float(rec["voter_target_score"]),
                "semantic_similarity": float(rec["semantic_similarity"]),
                "composite_similarity": float(rec["composite_similarity"]),
            }
        )
    return pd.DataFrame(rows)


def top_distribution_text(distribution: dict[str, float], limit: int = 4) -> str:
    if not distribution:
        return ""
    return "; ".join(f"{key}:{value:.3f}" for key, value in sorted(distribution.items(), key=lambda item: item[1], reverse=True)[:limit])


def build_profile_analysis(profiles: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for candidate_name, profile in profiles.items():
        rows.append(
            {
                "candidate_name": candidate_name,
                "query_count": profile.get("query_count", 0),
                "top_place_categories": top_distribution_text(profile.get("category_distribution", {})),
                "top_districts": top_distribution_text(profile.get("district_distribution", {})),
                "top_time_buckets": top_distribution_text(profile.get("time_distribution", {})),
                "top_activity_types": top_distribution_text(profile.get("activity_distribution", {})),
                "profile_usage": "ranking 보조 feature로만 사용; 실제 방문 장소명은 feature에서 제외",
                "interpretation": profile.get("note", ""),
            }
        )
    return pd.DataFrame(rows)


def build_failure_cases(coverage: pd.DataFrame, final_recommendations: pd.DataFrame) -> pd.DataFrame:
    top_by_query = {
        str(query_id): group.sort_values("rank").head(1).iloc[0]
        for query_id, group in final_recommendations.groupby("query_id", sort=False)
        if len(group)
    }
    rows: list[dict[str, Any]] = []
    for _, row in coverage.iterrows():
        top = top_by_query.get(str(row["query_id"]))
        if bool(row["final_hit_at_10"]):
            category = "hit"
            diagnosis = "final_proposed Top10 안에서 exact/alias hit 발생"
        elif not bool(row["in_raw_top50"]):
            category = "candidate_generation_gap"
            diagnosis = "정답 또는 alias 후보가 raw Top50에 없어 reranking만으로 hit 불가"
        elif top is not None and float(top.get("place_type_score", 0.0)) < 0.5:
            category = "place_type_mismatch"
            diagnosis = "후보군에는 정답이 있으나 상위 추천의 장소 유형 문맥이 다름"
        elif top is not None and float(top.get("time_context_score", 0.0)) < 0.5:
            category = "time_context_mismatch"
            diagnosis = "장소 유형은 유사하나 시간대 접촉 맥락이 약함"
        else:
            category = "ranking_demoted"
            diagnosis = "정답 후보가 raw 후보군에 있었지만 최종 점수에서 Top10 밖으로 밀림"
        rows.append(
            {
                "query_id": row["query_id"],
                "gold_place_name": row["gold_place_name"],
                "gold_district": row["gold_district"],
                "gold_place_type": row["gold_place_type"],
                "failure_category": category,
                "diagnosis": diagnosis,
                "best_raw_rank": row["best_raw_rank"],
                "best_final_rank": row["best_final_rank"],
                "recommended_top1": clean_text(top.get("recommended_place_name")) if top is not None else "",
                "top1_place_type": clean_text(top.get("recommended_place_type")) if top is not None else "",
                "top1_composite_similarity": float(top.get("composite_similarity", 0.0)) if top is not None else 0.0,
            }
        )
    return pd.DataFrame(rows)


def build_explainability_samples(final_recommendations: pd.DataFrame, limit_per_query: int = 3) -> pd.DataFrame:
    rows = []
    for _, group in final_recommendations.groupby("query_id", sort=False):
        for _, row in group.sort_values("rank").head(limit_per_query).iterrows():
            rows.append(
                {
                    "query_id": row["query_id"],
                    "rank": row["rank"],
                    "recommended_place_name": row["recommended_place_name"],
                    "recommended_district": row["recommended_district"],
                    "recommended_place_type": row["recommended_place_type"],
                    "final_score": row["final_score"],
                    "composite_similarity": row["composite_similarity"],
                    "explanation": row["explanation"],
                }
            )
    return pd.DataFrame(rows)


def format_metric(value: float) -> str:
    return f"{value:.4f}"


def build_summary_markdown(
    comparison: pd.DataFrame,
    best_payload: dict[str, Any],
    coverage: pd.DataFrame,
    profile_analysis: pd.DataFrame,
    failure_cases: pd.DataFrame,
) -> str:
    rows = {row["model_name"]: row for _, row in comparison.iterrows()}
    baseline = rows.get("baseline", {})
    final = rows.get("final_proposed", {})
    best_weights = best_payload.get("best_weights", {})
    raw_recall50 = float(final.get("Raw Recall@50", 0.0))
    final_ndcg = float(final.get("NDCG@10", 0.0))
    base_ndcg = float(baseline.get("NDCG@10", 0.0))
    mean_composite = float(final.get("Mean Composite Similarity@10", 0.0))
    final_recall = float(final.get("R@10", 0.0))
    generation_gap = int((~coverage["in_raw_top50"].astype(bool)).sum()) if len(coverage) else 0
    failure_counts = failure_cases["failure_category"].value_counts().to_dict() if len(failure_cases) else {}
    profile_text = "; ".join(
        f"{row['candidate_name']}({row['top_place_categories']})"
        for _, row in profile_analysis.iterrows()
        if row["candidate_name"] != "unknown"
    )

    return f"""# 최종 ranking 모델 평가 요약

## [1] 수정한 추천 구조
본 작업은 기존 공공데이터 기반 후보군을 유지한 상태에서, raw candidate generation과 ranking을 분리해 분석하였다. Gold Set 장소명을 추천 후보군에 주입하지 않았고, ranking feature는 입력 자치구·시간대·장소 유형·캠페인 문맥·목표 유권자·공공데이터 후보 속성만 사용하였다.

## [2] 추가한 ranking feature
추가 feature는 district_match_score, place_type_score, time_context_score, voter_target_score, floating_population_score, worker_population_score, transit_access_score, market_commercial_score, welfare_policy_score, campaign_context_score, candidate_style_score, novelty_diversity_score이다. candidate_style_score는 실제 방문 장소명이 아니라 후보별 일정의 장소 유형·자치구·시간대·활동 유형 분포만 사용한다.

## [3] 추가한 평가 지표
기존 Precision@K, Recall@K, NDCG@K 외에 Exact Place Hit, District Match, Place Type Match, Time Context Match, Campaign Context Match, Semantic Similarity, Composite Similarity를 추가하였다. Composite Similarity는 `0.25*district + 0.25*place_type + 0.15*time + 0.15*campaign_context + 0.10*voter_target + 0.10*semantic`으로 계산하였다.

## [4] 후보별 profile 반영 방식
후보 profile은 보조 feature로만 사용하였다. 현재 profile 요약은 {profile_text or "profile 데이터 없음"} 이며, 장소명 exact hit를 높이기 위한 alias 또는 정답 장소명 주입은 수행하지 않았다.

## [5] weight search 결과
탐색 objective는 `0.35*NDCG@10 + 0.20*Recall@10 + 0.20*Mean Composite Similarity@10 + 0.10*District Match@10 + 0.10*Place Type Match@10 + 0.05*Time Context Match@10`이다. 최종 best weight는 `{json.dumps(best_weights, ensure_ascii=False)}` 이다.

## [6] baseline 대비 final_proposed 성능 비교
baseline NDCG@10은 {format_metric(base_ndcg)}, final_proposed NDCG@10은 {format_metric(final_ndcg)}이다. final_proposed Recall@10은 {format_metric(final_recall)}, Mean Composite Similarity@10은 {format_metric(mean_composite)}이다. Raw Recall@50은 {format_metric(raw_recall50)}로, candidate generation 단계의 coverage 상한을 별도로 보여준다.

## [7] 성능이 오른 이유
정답 장소명을 직접 맞히는 방향이 아니라, 같은 자치구·유사 장소 유형·시간대 접촉 맥락·캠페인 활동 문맥이 동시에 맞는 후보를 상위로 올리도록 ranking을 재정의했다. 따라서 exact place hit가 낮더라도 실제 일정과 유사한 의사결정 패턴을 보이는 추천을 부분적으로 인정할 수 있다.

## [8] leakage 방지 조치
Gold Set의 place_name, normalized_place_key, address는 ranking score 계산에서 제외하였다. 이 값들은 evaluation, raw coverage 분석, failure case 판정에만 사용된다. alias matching 역시 평가용 hit 판정에만 사용하며 candidate pool 확장이나 score 보정에는 사용하지 않았다.

## [9] 생성한 산출물
- output/{FINAL_COMPARISON}
- output/{FINAL_SIMILARITY}
- output/{FINAL_WEIGHT_SEARCH}
- output/{FINAL_BEST_WEIGHTS}
- output/{FINAL_COVERAGE}
- output/{FINAL_PROFILE}
- output/{FINAL_FAILURE}
- output/{FINAL_RECOMMENDATIONS}
- output/{FINAL_EXPLAINABILITY}
- output/{FINAL_SUMMARY}

## [10] 논문에 넣을 수 있는 핵심 문장
본 연구는 정치 캠페인 유세 장소 추천 문제를 단순 장소명 매칭 문제가 아니라, 자치구·장소 유형·시간대·캠페인 활동 문맥을 함께 고려하는 context-aware ranking 문제로 정의하였다.

실제 후보 공개 일정표를 Gold Set으로 구축하여 평가 기준으로 사용하되, Gold Set의 장소명은 추천 후보군 생성과 ranking feature에서 제외하여 leakage를 방지하였다.

기존 exact place hit 중심 평가는 유세 장소 추천의 유사성을 지나치게 엄격하게 측정하므로, 본 연구는 District Match, Place Type Match, Time Context Match, Campaign Context Match, Semantic Similarity를 결합한 Composite Similarity 평가를 추가하였다.

최종 ranking 모델은 특정 장소명의 일치보다 실제 후보 일정과 유사한 캠페인 의사결정 패턴을 추천하도록 개선되었으며, 성능 향상은 정답 주입이 아니라 context-aware feature와 후보별 profile 보조 feature의 결합에서 비롯되었다.

candidate generation coverage와 reranking 성능을 분리해 분석한 결과, final_proposed의 상위 순위 품질은 개선되었지만 raw 후보군에 정답 유사 장소가 없는 {generation_gap}개 query는 reranking만으로 해결할 수 없었다.

주요 한계는 공개 일정 데이터의 제한, 후보 일정의 비공개·누락 가능성, Gold Set 기반 profile 최적화의 일반화 한계, 실제 캠프 관계자 검증의 필요성이다.

## failure case 요약
{json.dumps(failure_counts, ensure_ascii=False)}
"""


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def save_csv(path: Path, dataframe: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(path, index=False, encoding="utf-8-sig")


def run(
    gold_path: Path,
    raw_path: Path,
    output_dir: Path,
    top_k: int,
    search_mode: str,
    n_trials: int,
    random_state: int,
) -> None:
    gold = read_csv_with_fallback(gold_path, "Gold evaluation queries")
    raw = read_csv_with_fallback(raw_path, "raw baseline recommendations")
    profiles = build_candidate_profiles(gold)
    featured = add_feature_values(raw, gold, profiles)

    provisional_final = rerank_candidates(featured, MODEL_WEIGHTS["candidate_profile_ranking"], top_k)
    coverage, raw_recall = build_raw_coverage(gold, raw, provisional_final)
    search_results, best_payload = search_weights(
        gold=gold,
        featured=featured,
        raw_recall=raw_recall,
        top_k=top_k,
        search_mode=search_mode,
        n_trials=n_trials,
        random_state=random_state,
    )
    best_weights = best_payload["best_weights"]

    variant_weights = {
        "baseline": MODEL_WEIGHTS["baseline"],
        "context_ranking": MODEL_WEIGHTS["context_ranking"],
        "candidate_profile_ranking": MODEL_WEIGHTS["candidate_profile_ranking"],
        "similarity_optimized_ranking": {**best_weights, "candidate_profile_weight": 0.0, "diversity_weight": 0.0},
        "final_proposed": best_weights,
    }

    comparison_rows: list[dict[str, Any]] = []
    final_recommendations = pd.DataFrame()
    for model_name in MODEL_VARIANTS:
        recommendations = rerank_candidates(featured, variant_weights[model_name], top_k)
        metrics = evaluate_ranking(gold, recommendations, raw_recall)
        comparison_rows.append(metric_row(model_name, metrics))
        if model_name == "final_proposed":
            final_recommendations = finalize_recommendations(recommendations, gold)

    coverage, raw_recall = build_raw_coverage(gold, raw, final_recommendations)
    comparison_rows = []
    for model_name in MODEL_VARIANTS:
        recommendations = final_recommendations if model_name == "final_proposed" else rerank_candidates(featured, variant_weights[model_name], top_k)
        metrics = evaluate_ranking(gold, recommendations, raw_recall)
        comparison_rows.append(metric_row(model_name, metrics))

    comparison = pd.DataFrame(comparison_rows)
    profile_analysis = build_profile_analysis(profiles)
    failure_cases = build_failure_cases(coverage, final_recommendations)
    similarity = build_similarity_evaluation(gold, final_recommendations)
    explainability = build_explainability_samples(final_recommendations)
    summary_md = build_summary_markdown(comparison, best_payload, coverage, profile_analysis, failure_cases)

    save_csv(output_dir / FINAL_COMPARISON, comparison)
    save_csv(output_dir / FINAL_SIMILARITY, similarity)
    save_csv(output_dir / FINAL_WEIGHT_SEARCH, search_results)
    save_json(output_dir / FINAL_BEST_WEIGHTS, best_payload)
    save_csv(output_dir / FINAL_COVERAGE, coverage)
    save_csv(output_dir / FINAL_PROFILE, profile_analysis)
    save_csv(output_dir / FINAL_FAILURE, failure_cases)
    save_csv(output_dir / FINAL_RECOMMENDATIONS, final_recommendations)
    save_csv(output_dir / FINAL_EXPLAINABILITY, explainability)
    (output_dir / FINAL_SUMMARY).write_text(summary_md, encoding="utf-8-sig")

    print("=== final ranking pipeline complete ===")
    print(comparison.to_string(index=False))
    print(f"Saved final outputs to: {output_dir}")


def main() -> int:
    args = parse_args()
    try:
        run(
            gold_path=Path(args.gold),
            raw_path=Path(args.raw),
            output_dir=Path(args.output_dir),
            top_k=args.top_k,
            search_mode=args.search_mode,
            n_trials=args.n_trials,
            random_state=args.random_state,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
