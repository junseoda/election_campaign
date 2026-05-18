"""Evaluate recommendation results against the Gold Set evaluation queries.

The evaluator computes macro-averaged Precision@K, Recall@K, and NDCG@K.
Matching is intentionally place-name centric, with district constraints to
avoid crediting similarly named places in different Seoul districts.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd


GOLD_REQUIRED_COLUMNS = ["query_id", "gold_id", "place_name", "district", "relevance"]
RECOMMENDATION_REQUIRED_COLUMNS = ["query_id", "rank", "recommended_place_name"]
PARTIAL_RELAXED_TOKENS = ["전통", "재래", "공영", "공공"]


class DataValidationError(ValueError):
    """Raised when recommendation or Gold Set files do not match the contract."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate ranked place recommendations with Gold Set queries.")
    parser.add_argument("--gold", required=True, help="Path to output/gold_set_evaluation_queries.csv")
    parser.add_argument("--recommendations", required=True, help="Path to output/recommendation_results.csv")
    parser.add_argument("--output", required=True, help="Path to save query-level evaluation results")
    parser.add_argument("--k", nargs="+", type=int, default=[1, 3, 5, 10], help="K values for @K metrics")
    return parser.parse_args()


def read_csv_with_fallback(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{label} 파일이 존재하지 않습니다: {path}")

    errors: list[str] = []
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(path, encoding=encoding, dtype=str, keep_default_na=False)
        except UnicodeDecodeError as exc:
            errors.append(f"{encoding}: {exc}")
        except pd.errors.ParserError as exc:
            raise DataValidationError(f"{label} CSV 파싱에 실패했습니다: {exc}") from exc

    raise DataValidationError(f"{label} 파일을 utf-8-sig 또는 cp949로 읽을 수 없습니다. {' / '.join(errors)}")


def validate_required_columns(df: pd.DataFrame, required_columns: list[str], label: str) -> None:
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise DataValidationError(f"{label} 필수 컬럼이 누락되었습니다: {', '.join(missing)}")


def normalize_place_key(value: object) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).strip().lower()
    return re.sub(r"[^0-9a-z가-힣]", "", text)


def relaxed_partial_key(key: str) -> str:
    relaxed = key
    for token in PARTIAL_RELAXED_TOKENS:
        relaxed = relaxed.replace(token, "")
    return relaxed


def is_partial_match(left_key: str, right_key: str) -> bool:
    if len(left_key) >= 3 and len(right_key) >= 3 and (left_key in right_key or right_key in left_key):
        return True

    left_relaxed = relaxed_partial_key(left_key)
    right_relaxed = relaxed_partial_key(right_key)
    return (
        len(left_relaxed) >= 3
        and len(right_relaxed) >= 3
        and (left_relaxed in right_relaxed or right_relaxed in left_relaxed)
    )


def clean_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def place_match_method(recommendation: pd.Series, gold: pd.Series) -> str | None:
    rec_name = clean_text(recommendation["recommended_place_name"])
    gold_name = clean_text(gold["place_name"])
    if not rec_name or not gold_name:
        return None

    rec_district = clean_text(recommendation.get("recommended_district", ""))
    gold_district = clean_text(gold.get("district", ""))
    if rec_district and gold_district and rec_district != gold_district:
        return None

    if rec_name == gold_name:
        return "exact"

    rec_key = normalize_place_key(rec_name)
    gold_key = clean_text(gold.get("normalized_place_key", "")) or normalize_place_key(gold_name)

    if rec_key and gold_key and rec_key == gold_key:
        return "normalized"
    if rec_key and gold_key and is_partial_match(rec_key, gold_key):
        return "partial"

    return None


def validate_and_prepare_gold(gold: pd.DataFrame) -> pd.DataFrame:
    validate_required_columns(gold, GOLD_REQUIRED_COLUMNS, "Gold 평가 query")
    prepared = gold.copy()
    prepared["relevance"] = pd.to_numeric(prepared["relevance"], errors="coerce")
    if prepared["relevance"].isna().any():
        bad_rows = prepared.loc[prepared["relevance"].isna(), ["query_id", "gold_id", "relevance"]].head(10)
        raise DataValidationError(
            "Gold 평가 query의 relevance 컬럼을 숫자로 변환할 수 없습니다. "
            f"문제 샘플: {bad_rows.to_dict(orient='records')}"
        )

    if "normalized_place_key" not in prepared.columns:
        prepared["normalized_place_key"] = prepared["place_name"].map(normalize_place_key)
    else:
        missing_key = prepared["normalized_place_key"].astype(str).str.strip().eq("")
        prepared.loc[missing_key, "normalized_place_key"] = prepared.loc[missing_key, "place_name"].map(
            normalize_place_key
        )

    prepared["gold_item_id"] = prepared["gold_id"].astype(str).str.strip()
    missing_id = prepared["gold_item_id"].eq("")
    prepared.loc[missing_id, "gold_item_id"] = (
        prepared.loc[missing_id, "query_id"].astype(str)
        + "|"
        + prepared.loc[missing_id, "place_name"].astype(str)
        + "|"
        + pd.Series(prepared.index.astype(str), index=prepared.index).loc[missing_id]
    )
    return prepared


def validate_and_prepare_recommendations(recommendations: pd.DataFrame) -> pd.DataFrame:
    validate_required_columns(recommendations, RECOMMENDATION_REQUIRED_COLUMNS, "추천 결과")

    prepared = recommendations.copy()
    if "recommended_district" not in prepared.columns:
        prepared["recommended_district"] = ""

    prepared["rank"] = pd.to_numeric(prepared["rank"], errors="coerce")
    bad_rank = prepared["rank"].isna() | (prepared["rank"] <= 0) | (prepared["rank"] % 1 != 0)
    if bad_rank.any():
        bad_rows = prepared.loc[bad_rank, ["query_id", "rank", "recommended_place_name"]].head(10)
        raise DataValidationError(
            "추천 결과의 rank 컬럼이 양의 정수로 변환되지 않습니다. "
            f"문제 샘플: {bad_rows.to_dict(orient='records')}"
        )
    prepared["rank"] = prepared["rank"].astype(int)

    empty_place = prepared["recommended_place_name"].astype(str).str.strip().eq("")
    if empty_place.any():
        bad_rows = prepared.loc[empty_place, ["query_id", "rank", "recommended_place_name"]].head(10)
        raise DataValidationError(
            "추천 결과에 recommended_place_name이 비어 있는 row가 있습니다. "
            f"문제 샘플: {bad_rows.to_dict(orient='records')}"
        )

    duplicate_rank_queries = [
        str(query_id)
        for query_id, group in prepared.groupby("query_id", sort=False)
        if group["rank"].duplicated().any()
    ]
    if duplicate_rank_queries:
        raise DataValidationError(
            "추천 결과에 동일 query_id 내 중복 rank가 있습니다. "
            f"문제 query_id: {duplicate_rank_queries[:10]}"
        )

    unsorted_queries = [
        str(query_id)
        for query_id, group in prepared.groupby("query_id", sort=False)
        if not group["rank"].is_monotonic_increasing
    ]
    if unsorted_queries:
        raise DataValidationError(
            "추천 결과 rank가 query_id별 오름차순으로 정렬되어 있지 않습니다. "
            f"문제 query_id: {unsorted_queries[:10]}"
        )

    prepared["recommended_normalized_place_key"] = prepared["recommended_place_name"].map(normalize_place_key)
    return prepared.sort_values(["query_id", "rank"]).reset_index(drop=True)


def ideal_dcg(relevances: list[float], k: int) -> float:
    sorted_relevances = sorted(relevances, reverse=True)[:k]
    return sum((2**rel - 1) / math.log2(rank + 1) for rank, rel in enumerate(sorted_relevances, start=1))


def find_best_match(
    recommendation: pd.Series,
    gold_rows: pd.DataFrame,
    used_gold_item_ids: set[str],
) -> dict[str, Any] | None:
    method_priority = {"exact": 3, "normalized": 2, "partial": 1}
    candidates: list[dict[str, Any]] = []

    for _, gold in gold_rows.iterrows():
        gold_item_id = str(gold["gold_item_id"])
        if gold_item_id in used_gold_item_ids:
            continue

        method = place_match_method(recommendation, gold)
        if method is None:
            continue

        candidates.append(
            {
                "gold_item_id": gold_item_id,
                "gold_id": str(gold["gold_id"]),
                "place_name": str(gold["place_name"]),
                "relevance": float(gold["relevance"]),
                "method": method,
                "priority": method_priority[method],
            }
        )

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item["priority"], item["relevance"]), reverse=True)
    return candidates[0]


def evaluate_query_at_k(query_id: str, gold_rows: pd.DataFrame, rec_rows: pd.DataFrame, k: int) -> dict[str, Any]:
    top_recommendations = rec_rows.loc[rec_rows["rank"] <= k].sort_values("rank")
    used_gold_item_ids: set[str] = set()
    matched_gold_ids: list[str] = []
    matched_methods: list[str] = []
    dcg = 0.0

    for _, recommendation in top_recommendations.iterrows():
        match = find_best_match(recommendation, gold_rows, used_gold_item_ids)
        if match is None:
            continue

        used_gold_item_ids.add(match["gold_item_id"])
        matched_gold_ids.append(match["gold_id"])
        matched_methods.append(match["method"])
        rank = int(recommendation["rank"])
        relevance = float(match["relevance"])
        dcg += (2**relevance - 1) / math.log2(rank + 1)

    total_relevant = len(gold_rows)
    hits = len(used_gold_item_ids)
    precision = hits / k
    recall = hits / total_relevant if total_relevant else 0.0
    idcg = ideal_dcg(gold_rows["relevance"].astype(float).tolist(), k)
    ndcg = dcg / idcg if idcg > 0 else 0.0

    return {
        "query_id": query_id,
        "k": k,
        "precision_at_k": precision,
        "recall_at_k": recall,
        "ndcg_at_k": ndcg,
        "hits": hits,
        "total_relevant": total_relevant,
        "recommended_count_at_k": int(len(top_recommendations)),
        "matched_gold_ids": ";".join(matched_gold_ids),
        "match_methods": ";".join(matched_methods),
    }


def evaluate(gold: pd.DataFrame, recommendations: pd.DataFrame, k_values: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    if any(k <= 0 for k in k_values):
        raise DataValidationError("--k 값은 모두 양의 정수여야 합니다.")

    gold_prepared = validate_and_prepare_gold(gold)
    recommendations_prepared = validate_and_prepare_recommendations(recommendations)

    rec_by_query = {
        str(query_id): group.copy()
        for query_id, group in recommendations_prepared.groupby("query_id", sort=False)
    }

    detail_rows: list[dict[str, Any]] = []
    for query_id, gold_rows in gold_prepared.groupby("query_id", sort=False):
        query_id_text = str(query_id)
        rec_rows = rec_by_query.get(query_id_text, recommendations_prepared.iloc[0:0])
        for k in sorted(set(k_values)):
            detail_rows.append(evaluate_query_at_k(query_id_text, gold_rows.copy(), rec_rows.copy(), k))

    detail = pd.DataFrame(detail_rows)
    summary = (
        detail.groupby("k", as_index=False)
        .agg(
            precision_at_k=("precision_at_k", "mean"),
            recall_at_k=("recall_at_k", "mean"),
            ndcg_at_k=("ndcg_at_k", "mean"),
            query_count=("query_id", "nunique"),
        )
        .sort_values("k")
    )
    return detail, summary


def print_summary(summary: pd.DataFrame) -> None:
    print("=== 추천 결과 평가 결과 ===")
    for metric in ("precision_at_k", "recall_at_k", "ndcg_at_k"):
        metric_name = {
            "precision_at_k": "Precision",
            "recall_at_k": "Recall",
            "ndcg_at_k": "NDCG",
        }[metric]
        for _, row in summary.iterrows():
            print(f"{metric_name}@{int(row['k'])}: {row[metric]:.4f}")


def save_results(detail: pd.DataFrame, summary: pd.DataFrame, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(output_path, index=False, encoding="utf-8-sig")

    summary_path = output_path.with_name(f"{output_path.stem}_summary{output_path.suffix}")
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    return summary_path


def run(gold_path: Path, recommendation_path: Path, output_path: Path, k_values: list[int]) -> None:
    gold = read_csv_with_fallback(gold_path, "Gold 평가 query")
    recommendations = read_csv_with_fallback(recommendation_path, "추천 결과")
    detail, summary = evaluate(gold, recommendations, k_values)
    summary_path = save_results(detail, summary, output_path)

    print_summary(summary)
    print(f"\nquery별 상세 평가 결과 저장 경로: {output_path}")
    print(f"전체 요약 평가 결과 저장 경로: {summary_path}")


def main() -> int:
    args = parse_args()
    try:
        run(Path(args.gold), Path(args.recommendations), Path(args.output), args.k)
    except (FileNotFoundError, DataValidationError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"[ERROR] 파일 처리 중 오류가 발생했습니다: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
