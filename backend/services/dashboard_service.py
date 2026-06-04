from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from backend.district_utils import (
        count_district_mismatches,
        filter_dataframe_by_district,
        normalize_districts,
    )
except ModuleNotFoundError:
    from district_utils import (  # type: ignore
        count_district_mismatches,
        filter_dataframe_by_district,
        normalize_districts,
    )


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent


def _resolve_data_root() -> Path:
    if (REPOSITORY_ROOT / "output" / "final_ranking_model_comparison.csv").exists():
        return REPOSITORY_ROOT
    for candidate in (REPOSITORY_ROOT, BACKEND_ROOT):
        if (candidate / "output").exists():
            return candidate
    return BACKEND_ROOT


PROJECT_ROOT = _resolve_data_root()

GOLD_QUERIES_PATH = PROJECT_ROOT / "output" / "gold_set_evaluation_queries.csv"
GOLD_SUMMARY_PATH = PROJECT_ROOT / "output" / "gold_set_summary.json"
OPTIMIZED_RECOMMENDATIONS_PATH = (
    PROJECT_ROOT
    / "output"
    / "experiments_optimized"
    / "optimized_proposed"
    / "recommendation_results.csv"
)
MODEL_COMPARISON_PATH = PROJECT_ROOT / "output" / "experiments_optimized" / "model_comparison_optimized.csv"
BEST_WEIGHTS_PATH = PROJECT_ROOT / "output" / "experiments_optimized" / "best_weights.json"
RAW_COVERAGE_PATH = PROJECT_ROOT / "output" / "experiments_optimized" / "raw_candidate_coverage.csv"
RAW_BASELINE_RECOMMENDATIONS_PATH = PROJECT_ROOT / "output" / "raw_baseline_recommendations.csv"
FEATURE_CONTRIBUTION_PATH = (
    PROJECT_ROOT
    / "output"
    / "experiments_optimized"
    / "optimized_proposed"
    / "feature_contribution_summary.csv"
)
HIT_ANALYSIS_PATH = (
    PROJECT_ROOT
    / "output"
    / "experiments_optimized"
    / "optimized_proposed"
    / "hit_analysis.csv"
)
FINAL_MODEL_COMPARISON_PATH = PROJECT_ROOT / "output" / "final_ranking_model_comparison.csv"
FINAL_SIMILARITY_PATH = PROJECT_ROOT / "output" / "final_similarity_evaluation.csv"
FINAL_BEST_WEIGHTS_PATH = PROJECT_ROOT / "output" / "final_best_weights.json"
FINAL_CANDIDATE_COVERAGE_PATH = PROJECT_ROOT / "output" / "final_candidate_coverage_analysis.csv"
FINAL_CANDIDATE_PROFILE_PATH = PROJECT_ROOT / "output" / "final_candidate_profile_analysis.csv"
FINAL_FAILURE_CASE_PATH = PROJECT_ROOT / "output" / "final_failure_case_analysis.csv"
FINAL_EXPLAINABILITY_PATH = PROJECT_ROOT / "output" / "final_explainability_samples.csv"
FINAL_SUMMARY_PATH = PROJECT_ROOT / "output" / "final_evaluation_summary.md"
CANDIDATE_DIAGNOSIS_PATH = (
    PROJECT_ROOT / "output" / "experiments_optimized" / "candidate_generation_diagnosis.csv"
)
MISSING_BY_PLACE_TYPE_PATH = (
    PROJECT_ROOT / "output" / "experiments_optimized" / "missing_gold_by_place_type.csv"
)
MISSING_BY_DISTRICT_PATH = (
    PROJECT_ROOT / "output" / "experiments_optimized" / "missing_gold_by_district.csv"
)
HIT_VS_MISS_PATH = PROJECT_ROOT / "output" / "experiments_optimized" / "hit_vs_miss_summary.csv"
SPLIT_EVALUATION_DIR = PROJECT_ROOT / "output" / "experiments_optimized" / "split_evaluation"


def _require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"required output file not found: {path}")


def _read_csv(path: Path) -> pd.DataFrame:
    _require_file(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _read_json(path: Path) -> dict[str, Any]:
    _require_file(path)
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _read_optional_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _records(dataframe: pd.DataFrame, limit: int | None = None) -> list[dict[str, Any]]:
    if limit is not None:
        dataframe = dataframe.head(max(int(limit), 0))

    clean_dataframe = dataframe.astype(object).where(pd.notna(dataframe), None)
    return clean_dataframe.to_dict(orient="records")


def _source(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")


def _optional_source(path: Path) -> str | None:
    return _source(path) if path.exists() else None


def _similarity_summary(similarity: pd.DataFrame) -> dict[str, Any]:
    if similarity.empty:
        return {}
    top10 = similarity[pd.to_numeric(similarity.get("rank"), errors="coerce").fillna(999).le(10)].copy()
    if top10.empty:
        top10 = similarity.copy()
    metric_columns = [
        "district_match",
        "place_type_match",
        "time_context_match",
        "campaign_context_match",
        "voter_target_match",
        "semantic_similarity",
        "composite_similarity",
    ]
    summary = {
        column: float(pd.to_numeric(top10[column], errors="coerce").fillna(0.0).mean())
        for column in metric_columns
        if column in top10.columns
    }
    if "exact_place_hit" in top10.columns:
        summary["exact_place_hit_rate"] = float(top10["exact_place_hit"].fillna(False).astype(bool).mean())
    summary["evaluated_recommendation_count"] = int(len(top10))
    return summary


def get_gold_queries(limit: int | None = None) -> dict[str, Any]:
    queries = _read_csv(GOLD_QUERIES_PATH)
    sort_columns = [column for column in ["date", "time", "district"] if column in queries.columns]
    if sort_columns:
        queries = queries.sort_values(sort_columns)

    selected_columns = [
        "query_id",
        "date",
        "time",
        "district",
        "place_type",
        "campaign_activity_type",
        "target_voter_group",
        "context_tags",
        "place_name",
        "evaluation_context",
        "relevance",
    ]
    selected_columns = [column for column in selected_columns if column in queries.columns]

    return {
        "count": int(len(queries)),
        "source_file": _source(GOLD_QUERIES_PATH),
        "queries": _records(queries[selected_columns], limit=limit),
    }


def get_optimized_recommendations(query_id: str | None = None, limit: int = 10) -> dict[str, Any]:
    queries = _read_csv(GOLD_QUERIES_PATH)
    recommendations = _read_csv(OPTIMIZED_RECOMMENDATIONS_PATH)

    if "query_id" not in queries.columns or "query_id" not in recommendations.columns:
        raise ValueError("query_id column is required in gold queries and recommendation results")

    if query_id is None:
        query_id = str(queries.iloc[0]["query_id"])

    query_match = queries[queries["query_id"].astype(str) == str(query_id)]
    if query_match.empty:
        raise KeyError(f"unknown query_id: {query_id}")

    selected_districts = normalize_districts(query_match.iloc[0].get("district"))
    recommendation_match = recommendations[
        recommendations["query_id"].astype(str) == str(query_id)
    ].copy()
    candidate_count_before_district_filter = int(len(recommendation_match))
    recommendation_match = filter_dataframe_by_district(
        recommendation_match,
        selected_districts,
        ("recommended_district", "district", "district_name", "자치구", "시군구", "SIG_KOR_NM"),
    )
    candidate_count_after_district_filter = int(len(recommendation_match))
    if "rank" in recommendation_match.columns:
        recommendation_match = recommendation_match.sort_values("rank")
    else:
        recommendation_match = recommendation_match.sort_values("score", ascending=False)
    recommendation_records = _records(recommendation_match, limit=limit)
    warnings: list[str] = []
    if selected_districts and len(recommendation_records) < limit:
        warnings.append(
            "Returned "
            + str(len(recommendation_records))
            + " recommendations because selected district candidates were insufficient for requested "
            + str(limit)
            + " places."
        )

    coverage = _read_csv(RAW_COVERAGE_PATH)
    coverage_match = coverage[coverage["query_id"].astype(str) == str(query_id)]

    hit_analysis = _read_csv(HIT_ANALYSIS_PATH)
    hit_match = hit_analysis[hit_analysis["query_id"].astype(str) == str(query_id)]

    return {
        "model_name": "optimized_proposed",
        "query": _records(query_match)[0],
        "recommendations": recommendation_records,
        "coverage": _records(coverage_match),
        "hit_analysis": _records(hit_match),
        "debug": {
            "selected_districts": selected_districts,
            "candidate_count_before_district_filter": candidate_count_before_district_filter,
            "candidate_count_after_district_filter": candidate_count_after_district_filter,
            "district_filter_applied": bool(selected_districts),
            "district_mismatch_count": count_district_mismatches(recommendation_records, selected_districts),
            "warnings": warnings,
        },
        "best_weights": _read_json(BEST_WEIGHTS_PATH).get("best_weights", {}),
        "source_files": {
            "gold": _source(GOLD_QUERIES_PATH),
            "recommendations": _source(OPTIMIZED_RECOMMENDATIONS_PATH),
            "coverage": _source(RAW_COVERAGE_PATH),
            "hit_analysis": _source(HIT_ANALYSIS_PATH),
        },
    }


def get_evaluation_dashboard() -> dict[str, Any]:
    comparison = _read_csv(MODEL_COMPARISON_PATH)
    feature_contribution = _read_csv(FEATURE_CONTRIBUTION_PATH)
    best_weights = _read_json(BEST_WEIGHTS_PATH)
    gold_summary = _read_json(GOLD_SUMMARY_PATH)
    final_comparison = _read_optional_csv(FINAL_MODEL_COMPARISON_PATH)
    final_similarity = _read_optional_csv(FINAL_SIMILARITY_PATH)
    final_best_weights = _read_optional_json(FINAL_BEST_WEIGHTS_PATH)
    final_profile = _read_optional_csv(FINAL_CANDIDATE_PROFILE_PATH)
    final_failures = _read_optional_csv(FINAL_FAILURE_CASE_PATH)
    final_explainability = _read_optional_csv(FINAL_EXPLAINABILITY_PATH)

    split_summaries: dict[str, list[dict[str, Any]]] = {}
    for split_name in ["train", "validation", "full"]:
        split_path = SPLIT_EVALUATION_DIR / f"{split_name}_result_summary.csv"
        split_summaries[split_name] = _records(_read_csv(split_path))

    display_comparison = final_comparison if not final_comparison.empty else comparison
    optimized_row = display_comparison[display_comparison["model_name"] == "final_proposed"]
    if optimized_row.empty:
        optimized_row = display_comparison[display_comparison["model_name"] == "optimized_proposed"]
    optimized_metrics = _records(optimized_row)[0] if not optimized_row.empty else {}

    return {
        "source_files": {
            "model_comparison": _source(MODEL_COMPARISON_PATH),
            "best_weights": _source(BEST_WEIGHTS_PATH),
            "gold_summary": _source(GOLD_SUMMARY_PATH),
            "feature_contribution": _source(FEATURE_CONTRIBUTION_PATH),
            "final_model_comparison": _optional_source(FINAL_MODEL_COMPARISON_PATH),
            "final_similarity": _optional_source(FINAL_SIMILARITY_PATH),
            "final_best_weights": _optional_source(FINAL_BEST_WEIGHTS_PATH),
            "final_candidate_profile": _optional_source(FINAL_CANDIDATE_PROFILE_PATH),
            "final_failure_cases": _optional_source(FINAL_FAILURE_CASE_PATH),
            "final_summary": _optional_source(FINAL_SUMMARY_PATH),
        },
        "model_comparison": _records(display_comparison),
        "legacy_model_comparison": _records(comparison),
        "final_model_comparison": _records(final_comparison),
        "optimized_metrics": optimized_metrics,
        "best_weights": best_weights,
        "final_best_weights": final_best_weights,
        "final_similarity_summary": _similarity_summary(final_similarity),
        "final_similarity_samples": _records(final_similarity, limit=20),
        "final_candidate_profile": _records(final_profile),
        "final_failure_cases": _records(final_failures, limit=25),
        "final_explainability_samples": _records(final_explainability, limit=20),
        "gold_summary": gold_summary,
        "split_summaries": split_summaries,
        "feature_contribution": _records(feature_contribution),
    }


def get_candidate_coverage_dashboard(limit: int = 15) -> dict[str, Any]:
    raw_coverage = _read_csv(RAW_COVERAGE_PATH)
    raw_baseline = _read_csv(RAW_BASELINE_RECOMMENDATIONS_PATH)
    diagnosis = _read_csv(CANDIDATE_DIAGNOSIS_PATH)
    missing_by_place_type = _read_csv(MISSING_BY_PLACE_TYPE_PATH)
    missing_by_district = _read_csv(MISSING_BY_DISTRICT_PATH)
    hit_vs_miss = _read_csv(HIT_VS_MISS_PATH)

    total_queries = int(len(raw_coverage))
    raw_covered_count = int(raw_coverage["in_raw_top50"].fillna(False).astype(bool).sum())
    hit_at_10_count = int(raw_coverage["in_optimized_top10"].fillna(False).astype(bool).sum())
    missing_count = total_queries - raw_covered_count

    summary = {
        "total_queries": total_queries,
        "raw_covered_count": raw_covered_count,
        "raw_missing_count": missing_count,
        "raw_candidate_row_count": int(len(raw_baseline)),
        "raw_candidate_recall_at_50": raw_covered_count / total_queries if total_queries else 0.0,
        "optimized_hit_at_10_count": hit_at_10_count,
        "optimized_hit_at_10_rate": hit_at_10_count / total_queries if total_queries else 0.0,
    }

    place_type_sorted = missing_by_place_type.sort_values(
        ["missing_count", "missing_ratio_among_group"],
        ascending=[False, False],
    )
    district_sorted = missing_by_district.sort_values(
        ["missing_count", "missing_ratio_among_group"],
        ascending=[False, False],
    )
    activity_rows = hit_vs_miss[hit_vs_miss["group_level"] == "campaign_activity_type"]
    activity_rows = activity_rows.sort_values(
        ["raw_missing_count", "query_count"],
        ascending=[False, False],
    )

    return {
        "source_files": {
            "raw_candidate_coverage": _source(RAW_COVERAGE_PATH),
            "raw_baseline_recommendations": _source(RAW_BASELINE_RECOMMENDATIONS_PATH),
            "candidate_generation_diagnosis": _source(CANDIDATE_DIAGNOSIS_PATH),
            "missing_gold_by_place_type": _source(MISSING_BY_PLACE_TYPE_PATH),
            "missing_gold_by_district": _source(MISSING_BY_DISTRICT_PATH),
            "hit_vs_miss_summary": _source(HIT_VS_MISS_PATH),
        },
        "summary": summary,
        "diagnosis": _records(diagnosis),
        "missing_by_place_type": _records(place_type_sorted, limit=limit),
        "missing_by_district": _records(district_sorted, limit=limit),
        "missing_by_campaign_activity_type": _records(activity_rows, limit=limit),
    }
