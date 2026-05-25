"""Build before/after comparison tables for the improved candidate experiment."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd


METRICS = [
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
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create improved experiment comparison CSVs.")
    parser.add_argument("--before_dir", default="output/improved/before_recomputed/experiments_optimized")
    parser.add_argument("--after_dir", default="output/improved/experiments_optimized")
    parser.add_argument("--before_raw", default="output/raw_baseline_recommendations.csv")
    parser.add_argument("--after_raw", default="output/improved/raw_baseline_recommendations.csv")
    parser.add_argument("--output_dir", default="output/improved")
    return parser.parse_args()


def read_csv(path: Path) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(path, encoding=encoding, dtype=str, keep_default_na=False)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin(["true", "1", "yes"])


def to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def metric_columns(frame: pd.DataFrame) -> pd.DataFrame:
    converted = frame.copy()
    rename_map = {
        "precision_at_1": "P@1",
        "precision_at_3": "P@3",
        "precision_at_5": "P@5",
        "precision_at_10": "P@10",
        "recall_at_1": "R@1",
        "recall_at_3": "R@3",
        "recall_at_5": "R@5",
        "recall_at_10": "R@10",
        "ndcg_at_1": "NDCG@1",
        "ndcg_at_3": "NDCG@3",
        "ndcg_at_5": "NDCG@5",
        "ndcg_at_10": "NDCG@10",
    }
    converted = converted.rename(columns=rename_map)
    for metric in METRICS:
        if metric not in converted.columns:
            converted[metric] = 0.0
        converted[metric] = pd.to_numeric(converted[metric], errors="coerce").fillna(0.0)
    return converted


def model_metric_lookup(path: Path, model_name: str) -> dict[str, float]:
    frame = metric_columns(read_csv(path))
    model_rows = frame[frame["model_name"].astype(str).eq(model_name)]
    if model_rows.empty:
        return {metric: 0.0 for metric in METRICS}
    row = model_rows.iloc[0]
    return {metric: float(row[metric]) for metric in METRICS}


def relative_change(after: float, before: float) -> float:
    if before == 0:
        return 0.0 if after == 0 else 1.0
    return (after - before) / abs(before)


def metric_interpretation(metric: str, before: float, after: float) -> str:
    delta = after - before
    if abs(delta) < 1e-12:
        return f"{metric} did not change under the improved candidate pool."
    direction = "increased" if delta > 0 else "decreased"
    return f"{metric} {direction} by {delta:.4f} after alias-based candidate expansion."


def build_model_comparison(before_dir: Path, after_dir: Path) -> pd.DataFrame:
    before_path = before_dir / "model_comparison_optimized.csv"
    after_path = after_dir / "model_comparison_optimized.csv"
    before_baseline = model_metric_lookup(before_path, "baseline")
    before_optimized = model_metric_lookup(before_path, "optimized_proposed")
    after_baseline = model_metric_lookup(after_path, "baseline")
    after_optimized = model_metric_lookup(after_path, "optimized_proposed")

    rows: list[dict[str, Any]] = []
    for metric in METRICS:
        before_value = before_optimized[metric]
        after_value = after_optimized[metric]
        rows.append(
            {
                "metric": metric,
                "before_baseline": before_baseline[metric],
                "before_optimized": before_value,
                "after_baseline": after_baseline[metric],
                "after_optimized": after_value,
                "absolute_change": after_value - before_value,
                "relative_change": relative_change(after_value, before_value),
                "interpretation": metric_interpretation(metric, before_value, after_value),
            }
        )
    return pd.DataFrame(rows)


def coverage_stats(raw_path: Path, coverage_path: Path) -> dict[str, float]:
    raw = read_csv(raw_path)
    coverage = read_csv(coverage_path)
    in_raw = bool_series(coverage["in_raw_top50"])
    in_top10 = bool_series(coverage["in_optimized_top10"])
    per_query = raw.groupby("query_id").size()
    return {
        "raw_candidate_recall@50": float(in_raw.mean()) if len(in_raw) else 0.0,
        "missing_query_count": float((~in_raw).sum()),
        "raw_present_not_top10_count": float((in_raw & ~in_top10).sum()),
        "optimized_hit@10_rate": float(in_top10.mean()) if len(in_top10) else 0.0,
        "raw_candidate_rows": float(len(raw)),
        "raw_query_count": float(raw["query_id"].nunique()),
        "avg_raw_candidates_per_query": float(per_query.mean()) if len(per_query) else 0.0,
    }


def coverage_interpretation(metric: str, before: float, after: float) -> str:
    delta = after - before
    if metric == "missing_query_count":
        if delta < 0:
            return f"Missing raw candidates decreased by {abs(delta):.0f} queries."
        if delta > 0:
            return f"Missing raw candidates increased by {delta:.0f} queries."
        return "Missing raw candidate count did not change."
    if metric == "raw_candidate_rows":
        return f"Raw candidate rows changed by {delta:.0f}; existing outputs were not overwritten."
    return metric_interpretation(metric, before, after)


def build_raw_coverage_comparison(before_raw: Path, after_raw: Path, before_dir: Path, after_dir: Path) -> pd.DataFrame:
    before = coverage_stats(before_raw, before_dir / "raw_candidate_coverage.csv")
    after = coverage_stats(after_raw, after_dir / "raw_candidate_coverage.csv")
    rows: list[dict[str, Any]] = []
    for metric in before:
        before_value = before[metric]
        after_value = after[metric]
        rows.append(
            {
                "metric": metric,
                "before": before_value,
                "after": after_value,
                "absolute_change": after_value - before_value,
                "relative_change": relative_change(after_value, before_value),
                "interpretation": coverage_interpretation(metric, before_value, after_value),
            }
        )
    return pd.DataFrame(rows)


def build_missing_place_type_comparison(before_dir: Path, after_dir: Path) -> pd.DataFrame:
    before = read_csv(before_dir / "missing_gold_by_place_type.csv")
    after = read_csv(after_dir / "missing_gold_by_place_type.csv")
    merged = before.merge(after, on="place_type", how="outer", suffixes=("_before", "_after")).fillna("0")
    numeric_columns = [
        "total_gold_count_before",
        "total_gold_count_after",
        "missing_count_before",
        "missing_count_after",
        "raw_coverage_rate_before",
        "raw_coverage_rate_after",
        "hit_at_10_rate_before",
        "hit_at_10_rate_after",
    ]
    for column in numeric_columns:
        if column in merged.columns:
            merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0.0)

    merged["missing_count_change"] = merged["missing_count_after"] - merged["missing_count_before"]
    merged["raw_coverage_rate_change"] = merged["raw_coverage_rate_after"] - merged["raw_coverage_rate_before"]
    merged["hit_at_10_rate_change"] = merged["hit_at_10_rate_after"] - merged["hit_at_10_rate_before"]
    merged["interpretation"] = merged.apply(
        lambda row: (
            f"{row['place_type']}: missing decreased by {abs(row['missing_count_change']):.0f}."
            if row["missing_count_change"] < 0
            else f"{row['place_type']}: missing unchanged."
            if row["missing_count_change"] == 0
            else f"{row['place_type']}: missing increased by {row['missing_count_change']:.0f}."
        ),
        axis=1,
    )
    output_columns = [
        "place_type",
        "total_gold_count_before",
        "total_gold_count_after",
        "missing_count_before",
        "missing_count_after",
        "missing_count_change",
        "raw_coverage_rate_before",
        "raw_coverage_rate_after",
        "raw_coverage_rate_change",
        "hit_at_10_rate_before",
        "hit_at_10_rate_after",
        "hit_at_10_rate_change",
        "interpretation",
    ]
    return merged[output_columns].sort_values(
        ["missing_count_before", "missing_count_after", "place_type"],
        ascending=[False, False, True],
    )


def build_improvement_summary(model_comparison: pd.DataFrame, raw_coverage: pd.DataFrame) -> pd.DataFrame:
    selected_metrics = {"P@1", "P@3", "R@10", "NDCG@10"}
    model_rows = model_comparison[model_comparison["metric"].isin(selected_metrics)].copy()

    coverage_rows: list[dict[str, Any]] = []
    for metric in ["raw_candidate_recall@50", "missing_query_count", "optimized_hit@10_rate"]:
        row = raw_coverage[raw_coverage["metric"].eq(metric)].iloc[0]
        coverage_rows.append(
            {
                "metric": metric,
                "before_baseline": "",
                "before_optimized": float(row["before"]),
                "after_baseline": "",
                "after_optimized": float(row["after"]),
                "absolute_change": float(row["absolute_change"]),
                "relative_change": float(row["relative_change"]),
                "interpretation": row["interpretation"],
            }
        )
    return pd.concat([model_rows, pd.DataFrame(coverage_rows)], ignore_index=True)


def run(before_dir: Path, after_dir: Path, before_raw: Path, after_raw: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    model_comparison = build_model_comparison(before_dir, after_dir)
    raw_coverage = build_raw_coverage_comparison(before_raw, after_raw, before_dir, after_dir)
    missing_by_place_type = build_missing_place_type_comparison(before_dir, after_dir)
    improvement_summary = build_improvement_summary(model_comparison, raw_coverage)

    model_comparison.to_csv(output_dir / "model_comparison_before_after.csv", index=False, encoding="utf-8-sig")
    raw_coverage.to_csv(output_dir / "raw_coverage_before_after.csv", index=False, encoding="utf-8-sig")
    missing_by_place_type.to_csv(
        output_dir / "missing_by_place_type_before_after.csv",
        index=False,
        encoding="utf-8-sig",
    )
    improvement_summary.to_csv(output_dir / "improvement_summary.csv", index=False, encoding="utf-8-sig")

    print("=== improvement summary ===")
    print(improvement_summary.to_string(index=False))
    print(f"Saved comparison CSVs to {output_dir}")


def main() -> int:
    args = parse_args()
    run(
        before_dir=Path(args.before_dir),
        after_dir=Path(args.after_dir),
        before_raw=Path(args.before_raw),
        after_raw=Path(args.after_raw),
        output_dir=Path(args.output_dir),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
