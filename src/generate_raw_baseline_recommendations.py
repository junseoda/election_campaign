"""Freeze raw baseline recommendation candidates for model variant experiments.

This script runs the existing rule-based recommender once per Gold evaluation
query and stores the emitted score as baseline_score.  No feature bonus is
applied here.  Downstream model variants must re-rank this fixed candidate file
instead of running the recommender again.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_recommendation_results import (  # noqa: E402
    DataValidationError,
    cached_recommendations,
    clean_text,
    deduplicate_candidates,
    derive_time_slot,
    infer_recommender_types,
    infer_target_age_group,
    read_csv_with_fallback,
    score_value,
    select_top_k_for_query,
    validate_gold_queries,
)
from place_aliases import alias_candidates_for_query  # noqa: E402


RAW_OUTPUT_COLUMNS = [
    "query_id",
    "candidate_name",
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
    "place_id",
    "candidate_source",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate fixed raw baseline candidates from the existing recommender."
    )
    parser.add_argument(
        "--gold",
        default="output/gold_set_evaluation_queries.csv",
        help="Path to output/gold_set_evaluation_queries.csv",
    )
    parser.add_argument(
        "--output",
        default="output/raw_baseline_recommendations.csv",
        help="Path where raw_baseline_recommendations.csv will be saved",
    )
    parser.add_argument("--top_k", type=int, default=50, help="Maximum raw baseline candidates per query")
    parser.add_argument(
        "--candidate_pool",
        type=int,
        default=200,
        help="Number of candidates to request from each existing recommender before raw selection",
    )
    parser.add_argument(
        "--use_alias_expansion",
        action="store_true",
        help="Add query-compatible candidates from data/processed/place_aliases.csv after the protected baseline Top10.",
    )
    parser.add_argument(
        "--alias_path",
        default="data/processed/place_aliases.csv",
        help="Path to the place alias table used when --use_alias_expansion is enabled.",
    )
    return parser.parse_args()


def build_raw_rows_for_query(
    row: pd.Series,
    cache: dict[tuple[str, str, str, int], list[dict[str, Any]]],
    top_k: int,
    candidate_pool: int,
    use_alias_expansion: bool = False,
    alias_path: str | None = None,
) -> list[dict[str, Any]]:
    query_id = clean_text(row["query_id"])
    query_district = clean_text(row["district"])
    time_slot = derive_time_slot(row["time"])
    target_age_group = infer_target_age_group(row)
    recommender_types = infer_recommender_types(row)

    candidates: list[dict[str, Any]] = []
    for recommender_type in recommender_types:
        for candidate in cached_recommendations(
            cache=cache,
            time_slot=time_slot,
            place_type=recommender_type,
            target_age_group=target_age_group,
            candidate_pool=candidate_pool,
        ):
            candidate_with_source = candidate.copy()
            candidate_with_source["candidate_source"] = recommender_type
            candidates.append(candidate_with_source)

    deduped_candidates = deduplicate_candidates(candidates)
    protected_top_k = min(10, top_k)
    protected_baseline = select_top_k_for_query(
        deduped_candidates,
        query_district=query_district,
        top_k=protected_top_k,
    )

    protected_keys = {
        (
            clean_text(candidate.get("name")),
            clean_text(candidate.get("district_name")),
            clean_text(candidate.get("place_type")),
        )
        for candidate in protected_baseline
    }
    protected_rank = {
        (
            clean_text(candidate.get("name")),
            clean_text(candidate.get("district_name")),
            clean_text(candidate.get("place_type")),
        ): rank
        for rank, candidate in enumerate(protected_baseline, start=1)
    }
    min_protected_score = min((score_value(candidate) for candidate in protected_baseline), default=float("inf"))

    # Keep the previous baseline Top 10 stable, then add lower-scoring raw
    # candidates up to top_k.  This freezes the old baseline while still giving
    # re-rankers a larger, identical candidate pool.
    selected = list(protected_baseline)

    if use_alias_expansion:
        alias_score = 0.45 if min_protected_score == float("inf") else max(0.01, min_protected_score - 0.0001)
        for candidate in alias_candidates_for_query(row, alias_path):
            candidate = candidate.copy()
            candidate["score"] = round(max(score_value(candidate), alias_score), 4)
            key = (
                clean_text(candidate.get("name")),
                clean_text(candidate.get("district_name")),
                clean_text(candidate.get("place_type")),
            )
            if key in protected_keys:
                continue
            selected.append(candidate)
            protected_keys.add(key)
            if len(selected) >= top_k:
                break

    additional_candidates = sorted(
        deduped_candidates,
        key=lambda candidate: (score_value(candidate), clean_text(candidate.get("name"))),
        reverse=True,
    )
    for candidate in additional_candidates:
        key = (
            clean_text(candidate.get("name")),
            clean_text(candidate.get("district_name")),
            clean_text(candidate.get("place_type")),
        )
        if key in protected_keys:
            continue
        if score_value(candidate) > min_protected_score:
            continue

        selected.append(candidate)
        protected_keys.add(key)
        if len(selected) >= top_k:
            break

    def raw_sort_key(candidate: dict[str, Any]) -> tuple[float, int, str]:
        key = (
            clean_text(candidate.get("name")),
            clean_text(candidate.get("district_name")),
            clean_text(candidate.get("place_type")),
        )
        return (-score_value(candidate), protected_rank.get(key, 999999), clean_text(candidate.get("name")))

    selected = sorted(selected[:top_k], key=raw_sort_key)

    raw_rows: list[dict[str, Any]] = []
    for raw_rank, candidate in enumerate(selected, start=1):
        raw_rows.append(
            {
                "query_id": query_id,
                "candidate_name": clean_text(row.get("candidate_name", "")),
                "date": clean_text(row.get("date", "")),
                "time": clean_text(row.get("time", "")),
                "district": query_district,
                "place_type": clean_text(row.get("place_type", "")),
                "target_voter_group": clean_text(row.get("target_voter_group", "")),
                "context_tags": clean_text(row.get("context_tags", "")),
                "raw_rank": raw_rank,
                "recommended_place_name": clean_text(candidate.get("name")),
                "recommended_district": clean_text(candidate.get("district_name")),
                "recommended_place_type": clean_text(candidate.get("place_type")),
                "baseline_score": round(score_value(candidate), 4),
                "place_id": clean_text(candidate.get("place_id")),
                "candidate_source": clean_text(candidate.get("candidate_source")),
            }
        )
    return raw_rows


def build_raw_baseline_recommendations(
    gold_queries: pd.DataFrame,
    top_k: int,
    candidate_pool: int,
    use_alias_expansion: bool = False,
    alias_path: str | None = None,
) -> pd.DataFrame:
    if top_k <= 0:
        raise DataValidationError("--top_k 값은 양의 정수여야 합니다.")
    if candidate_pool < top_k:
        raise DataValidationError("--candidate_pool 값은 --top_k 이상이어야 합니다.")

    validate_gold_queries(gold_queries)

    cache: dict[tuple[str, str, str, int], list[dict[str, Any]]] = {}
    rows: list[dict[str, Any]] = []
    for _, query in gold_queries.iterrows():
        rows.extend(
            build_raw_rows_for_query(
                row=query,
                cache=cache,
                top_k=top_k,
                candidate_pool=candidate_pool,
                use_alias_expansion=use_alias_expansion,
                alias_path=alias_path,
            )
        )

    raw_baseline = pd.DataFrame(rows, columns=RAW_OUTPUT_COLUMNS)
    if raw_baseline.empty:
        raise DataValidationError("raw baseline 추천 후보가 비어 있습니다. Gold query와 추천기 출력을 확인하세요.")
    return raw_baseline


def run(
    gold_path: Path,
    output_path: Path,
    top_k: int,
    candidate_pool: int,
    use_alias_expansion: bool = False,
    alias_path: str | None = None,
) -> None:
    gold_queries = read_csv_with_fallback(gold_path)
    raw_baseline = build_raw_baseline_recommendations(
        gold_queries=gold_queries,
        top_k=top_k,
        candidate_pool=candidate_pool,
        use_alias_expansion=use_alias_expansion,
        alias_path=alias_path,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    raw_baseline.to_csv(output_path, index=False, encoding="utf-8-sig")

    per_query_counts = raw_baseline.groupby("query_id")["raw_rank"].count()
    print("=== raw baseline 추천 후보 생성 완료 ===")
    print(f"Gold query 수: {raw_baseline['query_id'].nunique()}")
    print(f"raw 후보 row 수: {len(raw_baseline)}")
    print(f"query당 최대 raw 후보 수: {int(per_query_counts.max())}")
    print(f"저장 경로: {output_path}")


def main() -> int:
    args = parse_args()
    try:
        run(
            Path(args.gold),
            Path(args.output),
            args.top_k,
            args.candidate_pool,
            use_alias_expansion=args.use_alias_expansion,
            alias_path=args.alias_path,
        )
    except (FileNotFoundError, DataValidationError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"[ERROR] 파일 처리 중 오류가 발생했습니다: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
