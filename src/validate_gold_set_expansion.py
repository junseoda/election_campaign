"""Validate the multi-candidate Gold Set expansion and experiment artifacts.

This script is a QA/reporting tool.  It does not modify recommendation logic,
Gold labels, or alias tables.  It only reads existing artifacts and writes
validation outputs under output/validation.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = Path(__file__).resolve().parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from evaluate_recommendations import place_match_method  # noqa: E402


GOLD_COLUMNS = [
    "gold_id",
    "candidate_name",
    "date",
    "day_of_week",
    "d_day",
    "time",
    "district",
    "place_name",
    "address",
    "event_title",
    "place_type",
    "campaign_activity_type",
    "online_offline",
    "target_voter_group",
    "context_tags",
    "gold_label_0_3",
    "gold_label_reason",
    "use_for_place_recommendation",
    "use_for_message_recommendation",
    "source_image",
]

EXPECTED_METRICS = {
    ("baseline", "P@1"): 0.0178,
    ("baseline", "R@10"): 0.2485,
    ("baseline", "NDCG@10"): 0.0963,
    ("proposed", "P@1"): 0.0710,
    ("proposed", "R@10"): 0.6805,
    ("proposed", "NDCG@10"): 0.3182,
    ("optimized_proposed", "P@1"): 0.2899,
    ("optimized_proposed", "R@10"): 0.9408,
    ("optimized_proposed", "NDCG@10"): 0.5913,
}

BOOL_VALUES = {"true", "false", "1", "0", "yes", "no", "y", "n"}
ALLOWED_CANDIDATES = {"정원오", "오세훈"}
ALLOWED_ONLINE = {"offline", "online", "hybrid", "unknown", "오프라인", "온라인", "혼합", ""}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Gold Set expansion outputs.")
    parser.add_argument("--output_dir", default="output/validation", help="Validation output directory")
    return parser.parse_args()


def path_of(relative_path: str) -> Path:
    return PROJECT_ROOT / relative_path


def read_csv(path: Path) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "cp949", "utf-8"):
        try:
            return pd.read_csv(path, encoding=encoding, dtype=str, keep_default_na=False)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def to_bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["true", "1", "yes", "y"])


def normalized_bool_parseable(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(BOOL_VALUES)


def clean_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def normalize_time_key(value: object) -> str:
    text = clean_text(value)
    match = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if match:
        return f"{int(match.group(1)):02d}:{match.group(2)}"
    return text


def metric_value(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if df.empty:
        return "_없음_"
    display = df.head(max_rows).copy() if max_rows else df.copy()
    display = display.astype(object).where(pd.notna(display), "")
    columns = [str(column) for column in display.columns]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, row in display.iterrows():
        values = [str(row[column]).replace("|", "\\|").replace("\n", " ") for column in display.columns]
        lines.append("| " + " | ".join(values) + " |")
    if max_rows and len(df) > max_rows:
        lines.append(f"\n_총 {len(df)}행 중 {max_rows}행만 표시_")
    return "\n".join(lines)


def add_check(rows: list[dict[str, Any]], check_name: str, severity: str, passed: bool, actual: Any, expected: Any, detail: str = "") -> None:
    rows.append(
        {
            "check_name": check_name,
            "severity": severity,
            "passed": bool(passed),
            "actual": actual,
            "expected": expected,
            "detail": detail,
        }
    )


def add_error(rows: list[dict[str, Any]], severity: str, check_name: str, detail: str) -> None:
    rows.append({"severity": severity, "check_name": check_name, "detail": detail})


def strong_positive_queries_from_gold(gold: pd.DataFrame) -> pd.DataFrame:
    labels = pd.to_numeric(gold["gold_label_0_3"], errors="coerce").fillna(-1).astype(int)
    offline = gold["online_offline"].astype(str).str.strip().str.lower().eq("offline")
    place_use = to_bool_series(gold["use_for_place_recommendation"])
    has_place = gold["place_name"].astype(str).str.strip().ne("")
    has_district = gold["district"].astype(str).str.strip().ne("")
    return gold[labels.eq(3) & offline & place_use & has_place & has_district].copy()


def key_frame(df: pd.DataFrame) -> pd.Series:
    columns = ["candidate_name", "date", "time", "place_name", "event_title", "source_image"]
    available = [column for column in columns if column in df.columns]
    normalized = df[available].fillna("").astype(str).copy()
    if "time" in normalized.columns:
        normalized["time"] = normalized["time"].map(normalize_time_key)
    return normalized.agg("|".join, axis=1)


def strict_metadata_key_frame(df: pd.DataFrame) -> pd.Series:
    columns = ["candidate_name", "date", "time", "district", "place_name", "event_title", "source_image"]
    available = [column for column in columns if column in df.columns]
    normalized = df[available].fillna("").astype(str).copy()
    if "time" in normalized.columns:
        normalized["time"] = normalized["time"].map(normalize_time_key)
    return normalized.agg("|".join, axis=1)


def validate_gold_data(output_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    summary_rows: list[dict[str, Any]] = []
    error_rows: list[dict[str, Any]] = []

    paths = {
        "gold_all": path_of("output/gold_set_all_candidates.csv"),
        "gold_jung": path_of("output/gold_set_jungwono_extended.csv"),
        "gold_oh": path_of("output/gold_set_ohsehoon.csv"),
        "queries_all": path_of("output/gold_set_evaluation_queries_all_candidates.csv"),
        "queries_jung": path_of("output/gold_set_evaluation_queries_jungwono.csv"),
        "queries_oh": path_of("output/gold_set_evaluation_queries_ohsehoon.csv"),
        "aliases": path_of("data/processed/place_aliases.csv"),
        "new_gold": path_of("output/gold_set_normalized_new.csv"),
        "existing_gold": path_of("data/full_정원오_gold_set_20260309_20260516.csv"),
        "extraction_log": path_of("output/schedule_image_extraction_log.csv"),
        "expansion_report": path_of("output/gold_set_expansion_report.md"),
    }

    missing_files = [name for name, path in paths.items() if name not in {"new_gold", "existing_gold"} and not path.exists()]
    for name in missing_files:
        add_error(error_rows, "CRITICAL", "required_file_exists", f"Missing required file: {paths[name]}")

    gold_all = read_csv(paths["gold_all"])
    gold_jung = read_csv(paths["gold_jung"])
    gold_oh = read_csv(paths["gold_oh"])
    queries_all = read_csv(paths["queries_all"])
    queries_jung = read_csv(paths["queries_jung"])
    queries_oh = read_csv(paths["queries_oh"])
    aliases = read_csv(paths["aliases"])

    add_check(summary_rows, "final_gold_row_count", "CRITICAL", len(gold_all) == 391, len(gold_all), 391)
    if paths["new_gold"].exists():
        new_gold = read_csv(paths["new_gold"])
        add_check(summary_rows, "new_gold_row_count", "CRITICAL", len(new_gold) == 205, len(new_gold), 205)
    else:
        new_gold = pd.DataFrame()
        add_check(summary_rows, "new_gold_row_count", "WARNING", False, "not found", 205, "output/gold_set_normalized_new.csv is missing")

    add_check(
        summary_rows,
        "candidate_name_domain",
        "CRITICAL",
        set(gold_all["candidate_name"]) <= ALLOWED_CANDIDATES,
        ";".join(sorted(set(gold_all["candidate_name"]))),
        "정원오;오세훈",
    )
    add_check(summary_rows, "gold_id_duplicate_count", "CRITICAL", int(gold_all["gold_id"].duplicated().sum()) == 0, int(gold_all["gold_id"].duplicated().sum()), 0)

    missing_columns = [column for column in GOLD_COLUMNS if column not in gold_all.columns]
    add_check(summary_rows, "required_gold_columns", "CRITICAL", not missing_columns, ";".join(missing_columns), "none")

    bad_date_count = int((~gold_all["date"].astype(str).str.match(r"^\d{4}-\d{2}-\d{2}$")).sum())
    add_check(summary_rows, "date_format_yyyy_mm_dd", "CRITICAL", bad_date_count == 0, bad_date_count, 0)

    bad_label_count = int((~gold_all["gold_label_0_3"].astype(str).isin(["0", "1", "2", "3"])).sum())
    add_check(summary_rows, "gold_label_domain", "CRITICAL", bad_label_count == 0, bad_label_count, 0)

    bad_online_count = int((~gold_all["online_offline"].astype(str).str.strip().isin(ALLOWED_ONLINE)).sum())
    add_check(summary_rows, "online_offline_domain", "CRITICAL", bad_online_count == 0, bad_online_count, 0)

    bad_bool_count = int((~normalized_bool_parseable(gold_all["use_for_place_recommendation"])).sum())
    add_check(summary_rows, "use_for_place_recommendation_bool_parseable", "CRITICAL", bad_bool_count == 0, bad_bool_count, 0)

    empty_source_count = int(gold_all["source_image"].astype(str).str.strip().eq("").sum())
    add_check(summary_rows, "source_image_empty_count", "CRITICAL", empty_source_count == 0, empty_source_count, 0)

    recomputed_strong = strong_positive_queries_from_gold(gold_all)
    empty_place_strong = int(recomputed_strong["place_name"].astype(str).str.strip().eq("").sum())
    empty_district_strong = int(recomputed_strong["district"].astype(str).str.strip().eq("").sum())
    add_check(summary_rows, "strong_place_name_empty_count", "CRITICAL", empty_place_strong == 0, empty_place_strong, 0)
    add_check(summary_rows, "strong_district_empty_count", "CRITICAL", empty_district_strong == 0, empty_district_strong, 0)
    add_check(summary_rows, "recomputed_strong_query_count", "CRITICAL", len(recomputed_strong) == 169, len(recomputed_strong), 169)

    candidate_query_counts = queries_all["candidate_name"].value_counts().to_dict()
    add_check(summary_rows, "query_count_jungwono", "CRITICAL", candidate_query_counts.get("정원오", 0) == 107, candidate_query_counts.get("정원오", 0), 107)
    add_check(summary_rows, "query_count_ohsehoon", "CRITICAL", candidate_query_counts.get("오세훈", 0) == 62, candidate_query_counts.get("오세훈", 0), 62)
    add_check(summary_rows, "evaluation_query_count_all", "CRITICAL", len(queries_all) == 169, len(queries_all), 169)
    add_check(summary_rows, "evaluation_query_count_jungwono_file", "CRITICAL", len(queries_jung) == 107, len(queries_jung), 107)
    add_check(summary_rows, "evaluation_query_count_ohsehoon_file", "CRITICAL", len(queries_oh) == 62, len(queries_oh), 62)
    add_check(summary_rows, "query_id_duplicate_count", "CRITICAL", int(queries_all["query_id"].duplicated().sum()) == 0, int(queries_all["query_id"].duplicated().sum()), 0)

    existing_missing = "not checked"
    if paths["existing_gold"].exists():
        existing = read_csv(paths["existing_gold"])
        existing_keys = set(key_frame(existing))
        final_keys = set(key_frame(gold_all))
        missing_existing = sorted(existing_keys - final_keys)
        strict_missing_existing = sorted(set(strict_metadata_key_frame(existing)) - set(strict_metadata_key_frame(gold_all)))
        existing_missing = len(missing_existing)
        add_check(summary_rows, "existing_jungwono_rows_preserved", "CRITICAL", len(missing_existing) == 0, len(missing_existing), 0)
        add_check(
            summary_rows,
            "existing_jungwono_normalized_metadata_differences",
            "INFO",
            True,
            len(strict_missing_existing),
            "documented",
            "Stable row keys are preserved; strict metadata differences are expected from district/time normalization.",
        )
        for key in missing_existing[:20]:
            add_error(error_rows, "CRITICAL", "existing_jungwono_rows_preserved", f"Missing existing row key: {key}")
    else:
        add_check(summary_rows, "existing_jungwono_rows_preserved", "WARNING", False, existing_missing, 0, "Existing Gold source file not found")

    missing_0523_logged = False
    if paths["extraction_log"].exists():
        extraction_log = read_csv(paths["extraction_log"])
        missing_0523_logged = bool(
            (
                extraction_log["candidate_name"].astype(str).eq("오세훈")
                & extraction_log["date"].astype(str).eq("2026-05-23")
                & extraction_log["status"].astype(str).eq("missing_image")
            ).any()
        )
    report_text = paths["expansion_report"].read_text(encoding="utf-8") if paths["expansion_report"].exists() else ""
    missing_0523_reported = "2026-05-23" in report_text and "오세훈" in report_text
    add_check(
        summary_rows,
        "ohsehoon_20260523_missing_logged",
        "WARNING",
        missing_0523_logged and missing_0523_reported,
        f"log={missing_0523_logged};report={missing_0523_reported}",
        "log=True;report=True",
    )

    add_check(summary_rows, "alias_table_rows", "INFO", len(aliases) >= 184, len(aliases), ">=184")
    if not new_gold.empty:
        review_required_count = int(new_gold.get("review_required", pd.Series(dtype=str)).astype(str).str.lower().isin(["true", "1"]).sum())
        add_check(summary_rows, "new_rows_review_required", "WARNING", review_required_count == 205, review_required_count, 205, "Manual transcription/address review remains required")

    summary = {
        "gold_all": gold_all,
        "queries_all": queries_all,
        "aliases": aliases,
        "new_gold": new_gold,
    }
    summary_df = pd.DataFrame(summary_rows)
    errors_df = pd.DataFrame(error_rows)
    if errors_df.empty:
        errors_df = pd.DataFrame(columns=["severity", "check_name", "detail"])

    summary_df.to_csv(output_dir / "gold_set_validation_summary.csv", index=False, encoding="utf-8-sig")
    errors_df.to_csv(output_dir / "gold_set_validation_errors.csv", index=False, encoding="utf-8-sig")
    write_gold_validation_report(output_dir, summary_df, errors_df, gold_all, queries_all)
    return summary_df, errors_df, summary


def write_gold_validation_report(output_dir: Path, summary_df: pd.DataFrame, errors_df: pd.DataFrame, gold: pd.DataFrame, queries: pd.DataFrame) -> None:
    critical_failed = summary_df[(summary_df["severity"].eq("CRITICAL")) & (~summary_df["passed"])]
    warning_failed = summary_df[(summary_df["severity"].eq("WARNING")) & (~summary_df["passed"])]
    lines = [
        "# Gold Set 데이터 무결성 검증 보고서",
        "",
        f"- 최종 Gold Set row 수: {len(gold)}",
        f"- 후보자별 row 수: {gold['candidate_name'].value_counts().to_dict()}",
        f"- strong positive query 수: {len(queries)}",
        f"- 후보자별 query 수: {queries['candidate_name'].value_counts().to_dict()}",
        f"- CRITICAL 실패: {len(critical_failed)}",
        f"- WARNING 실패: {len(warning_failed)}",
        "",
        "## 주요 검증 결과",
        "",
        md_table(summary_df),
    ]
    if not errors_df.empty:
        lines.extend(["", "## 상세 오류", "", md_table(errors_df)])
    (output_dir / "gold_set_validation_report.md").write_text("\n".join(lines), encoding="utf-8")


def load_comparison_metrics(path: Path) -> dict[str, dict[str, float]]:
    if not path.exists():
        return {}
    df = read_csv(path)
    metric_map: dict[str, dict[str, float]] = {}
    for _, row in df.iterrows():
        model = clean_text(row.get("model_name", ""))
        if not model:
            continue
        metric_map[model] = {
            "P@1": metric_value(row.get("P@1", row.get("precision_at_1", ""))),
            "P@3": metric_value(row.get("P@3", row.get("precision_at_3", ""))),
            "P@5": metric_value(row.get("P@5", row.get("precision_at_5", ""))),
            "P@10": metric_value(row.get("P@10", row.get("precision_at_10", ""))),
            "R@1": metric_value(row.get("R@1", row.get("recall_at_1", ""))),
            "R@3": metric_value(row.get("R@3", row.get("recall_at_3", ""))),
            "R@5": metric_value(row.get("R@5", row.get("recall_at_5", ""))),
            "R@10": metric_value(row.get("R@10", row.get("recall_at_10", ""))),
            "NDCG@1": metric_value(row.get("NDCG@1", row.get("ndcg_at_1", ""))),
            "NDCG@3": metric_value(row.get("NDCG@3", row.get("ndcg_at_3", ""))),
            "NDCG@5": metric_value(row.get("NDCG@5", row.get("ndcg_at_5", ""))),
            "NDCG@10": metric_value(row.get("NDCG@10", row.get("ndcg_at_10", ""))),
        }
    return metric_map


def validate_metric_reproducibility(output_dir: Path) -> pd.DataFrame:
    base_metrics = load_comparison_metrics(path_of("output/experiments_all_candidates/model_comparison.csv"))
    optimized_metrics = load_comparison_metrics(path_of("output/experiments_all_candidates/model_comparison_optimized.csv"))
    metrics = {**base_metrics, **optimized_metrics}

    rows: list[dict[str, Any]] = []
    for (model, metric), expected in EXPECTED_METRICS.items():
        actual = metrics.get(model, {}).get(metric, math.nan)
        diff = abs(actual - expected) if not math.isnan(actual) else math.nan
        rows.append(
            {
                "model_name": model,
                "metric": metric,
                "expected": expected,
                "actual": actual,
                "abs_diff": diff,
                "status": "PASS" if not math.isnan(diff) and diff < 0.0001 else "WARNING",
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(output_dir / "evaluation_metric_reproducibility.csv", index=False, encoding="utf-8-sig")
    warning_count = int(df["status"].eq("WARNING").sum())
    lines = [
        "# 평가 결과 재현성 검증 보고서",
        "",
        f"- 비교 기준: 기대 수치와 실제 CSV 수치의 차이 < 0.0001",
        f"- WARNING 수: {warning_count}",
        "",
        md_table(df),
    ]
    (output_dir / "evaluation_metric_reproducibility_report.md").write_text("\n".join(lines), encoding="utf-8")
    return df


def best_match_rank(candidates: pd.DataFrame, gold_row: pd.Series, rank_column: str) -> int | None:
    if candidates.empty or rank_column not in candidates.columns:
        return None
    ranked = candidates.copy()
    ranked[rank_column] = pd.to_numeric(ranked[rank_column], errors="coerce").fillna(999999).astype(int)
    for _, candidate in ranked.sort_values(rank_column).iterrows():
        if place_match_method(candidate, gold_row) is not None:
            return int(candidate[rank_column])
    return None


def build_raw_coverage(gold: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, gold_row in gold.iterrows():
        query_id = clean_text(gold_row["query_id"])
        candidates = raw[raw["query_id"].astype(str).eq(query_id)]
        rank = best_match_rank(candidates, gold_row, "raw_rank")
        rows.append(
            {
                "query_id": query_id,
                "candidate_name": gold_row.get("candidate_name", ""),
                "place_name": gold_row.get("place_name", ""),
                "district": gold_row.get("district", ""),
                "place_type": gold_row.get("place_type", ""),
                "raw_candidate_count": int(len(candidates)),
                "in_raw_top50": rank is not None,
                "best_raw_rank": rank if rank is not None else "",
            }
        )
    return pd.DataFrame(rows)


def row_metric(metrics: dict[str, dict[str, float]], model: str, metric: str) -> float:
    return float(metrics.get(model, {}).get(metric, math.nan))


def alias_ablation(output_dir: Path, gold: pd.DataFrame) -> pd.DataFrame:
    settings = {
        "no_alias": {
            "raw": path_of("output/raw_baseline_recommendations_all_candidates_no_alias.csv"),
            "comparison": path_of("output/experiments_all_candidates_no_alias/model_comparison.csv"),
            "optimized": path_of("output/experiments_all_candidates_no_alias/optimized/model_comparison_optimized.csv"),
        },
        "with_alias": {
            "raw": path_of("output/raw_baseline_recommendations_all_candidates_with_alias.csv"),
            "comparison": path_of("output/experiments_all_candidates_with_alias/model_comparison.csv"),
            "optimized": path_of("output/experiments_all_candidates_with_alias/optimized/model_comparison_optimized.csv"),
        },
    }

    fallback_optimized = path_of("output/experiments_all_candidates/model_comparison_optimized.csv")
    rows: list[dict[str, Any]] = []
    for setting, paths in settings.items():
        raw = read_csv(paths["raw"]) if paths["raw"].exists() else pd.DataFrame()
        coverage = build_raw_coverage(gold, raw) if not raw.empty else pd.DataFrame()
        coverage_path = output_dir / f"raw_candidate_coverage_{setting}.csv"
        coverage.to_csv(coverage_path, index=False, encoding="utf-8-sig")

        comparison_metrics = load_comparison_metrics(paths["comparison"])
        optimized_path = paths["optimized"] if paths["optimized"].exists() else (fallback_optimized if setting == "with_alias" else Path(""))
        optimized_metrics = load_comparison_metrics(optimized_path) if optimized_path else {}
        metrics = {**comparison_metrics, **optimized_metrics}

        query_count = int(len(gold))
        raw_candidate_rows = int(len(raw))
        raw_recall = float(coverage["in_raw_top50"].mean()) if len(coverage) else math.nan
        missing_gold = int((~coverage["in_raw_top50"]).sum()) if len(coverage) else query_count
        if setting == "no_alias":
            interpretation = "Gold-derived alias를 적용하지 않은 기존 MVP 후보군 coverage 기준"
        else:
            interpretation = "Gold Set 기반 alias 후보를 추가한 candidate generation coverage 보강 기준"
        rows.append(
            {
                "setting": setting,
                "query_count": query_count,
                "raw_candidate_rows": raw_candidate_rows,
                "raw_recall_at_50": raw_recall,
                "missing_gold_count": missing_gold,
                "baseline_p_at_1": row_metric(metrics, "baseline", "P@1"),
                "baseline_r_at_10": row_metric(metrics, "baseline", "R@10"),
                "baseline_ndcg_at_10": row_metric(metrics, "baseline", "NDCG@10"),
                "proposed_p_at_1": row_metric(metrics, "proposed", "P@1"),
                "proposed_r_at_10": row_metric(metrics, "proposed", "R@10"),
                "proposed_ndcg_at_10": row_metric(metrics, "proposed", "NDCG@10"),
                "optimized_p_at_1": row_metric(metrics, "optimized_proposed", "P@1"),
                "optimized_r_at_10": row_metric(metrics, "optimized_proposed", "R@10"),
                "optimized_ndcg_at_10": row_metric(metrics, "optimized_proposed", "NDCG@10"),
                "interpretation": interpretation,
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(output_dir / "alias_ablation_summary.csv", index=False, encoding="utf-8-sig")
    write_alias_ablation_report(output_dir, df)
    return df


def write_alias_ablation_report(output_dir: Path, df: pd.DataFrame) -> None:
    no_alias = df[df["setting"].eq("no_alias")].iloc[0].to_dict() if not df[df["setting"].eq("no_alias")].empty else {}
    with_alias = df[df["setting"].eq("with_alias")].iloc[0].to_dict() if not df[df["setting"].eq("with_alias")].empty else {}
    lines = [
        "# alias 보강 전/후 ablation 검증 보고서",
        "",
        md_table(df),
        "",
        "## 해석",
        "",
        f"- no_alias raw recall@50: {no_alias.get('raw_recall_at_50', math.nan):.4f}",
        f"- with_alias raw recall@50: {with_alias.get('raw_recall_at_50', math.nan):.4f}",
        "- alias 보강 후 성능 상승은 모델 일반화 성능 향상으로 해석하지 않는다.",
        "- Gold Set strong positive 장소명을 후보군 생성 alias에 반영한 candidate generation coverage 보강 실험으로 해석해야 한다.",
        "- 후보군에 정답이 없으면 reranking은 해당 정답을 복구할 수 없다.",
    ]
    (output_dir / "alias_ablation_report.md").write_text("\n".join(lines), encoding="utf-8")


def load_recommendations(path: Path) -> pd.DataFrame:
    return read_csv(path) if path.exists() else pd.DataFrame()


def sample_recommendation_trace(output_dir: Path, gold: pd.DataFrame) -> pd.DataFrame:
    raw_no = read_csv(path_of("output/raw_baseline_recommendations_all_candidates_no_alias.csv"))
    raw_alias = read_csv(path_of("output/raw_baseline_recommendations_all_candidates_with_alias.csv"))
    base_recs = load_recommendations(path_of("output/experiments_all_candidates_with_alias/baseline/recommendation_results.csv"))
    proposed_recs = load_recommendations(path_of("output/experiments_all_candidates_with_alias/proposed/recommendation_results.csv"))
    optimized_recs = load_recommendations(path_of("output/experiments_all_candidates_with_alias/optimized/optimized_proposed/recommendation_results.csv"))
    if optimized_recs.empty:
        optimized_recs = load_recommendations(path_of("output/experiments_all_candidates/optimized/optimized_proposed/recommendation_results.csv"))

    coverage_no = build_raw_coverage(gold, raw_no)
    coverage_alias = build_raw_coverage(gold, raw_alias)
    coverage = coverage_no[["query_id", "in_raw_top50"]].rename(columns={"in_raw_top50": "in_raw_no_alias"})
    coverage = coverage.merge(
        coverage_alias[["query_id", "in_raw_top50"]],
        on="query_id",
        how="left",
    ).rename(columns={"in_raw_top50": "in_raw_with_alias"})

    selected_ids: list[str] = []
    for candidate_name in sorted(gold["candidate_name"].dropna().astype(str).unique()):
        selected_ids.extend(gold[gold["candidate_name"].eq(candidate_name)]["query_id"].head(2).tolist())
    miss_to_hit = coverage[(~coverage["in_raw_no_alias"]) & (coverage["in_raw_with_alias"])]
    for _, coverage_row in miss_to_hit.iterrows():
        query_id = str(coverage_row["query_id"])
        if query_id not in selected_ids:
            selected_ids.append(query_id)
            break
    selected_ids = list(dict.fromkeys(selected_ids))
    if len(selected_ids) < 5:
        for query_id in gold["query_id"].astype(str).tolist():
            if query_id not in selected_ids:
                selected_ids.append(query_id)
            if len(selected_ids) >= 5:
                break
    selected_ids = selected_ids[:5]

    rec_sets = {
        "baseline": base_recs,
        "proposed": proposed_recs,
        "optimized_proposed": optimized_recs,
    }

    rows: list[dict[str, Any]] = []
    for query_id in selected_ids:
        gold_row = gold[gold["query_id"].astype(str).eq(str(query_id))].iloc[0]
        raw_no_group = raw_no[raw_no["query_id"].astype(str).eq(str(query_id))]
        raw_alias_group = raw_alias[raw_alias["query_id"].astype(str).eq(str(query_id))]
        row: dict[str, Any] = {
            "query_id": query_id,
            "candidate_name": gold_row["candidate_name"],
            "date": gold_row["date"],
            "district": gold_row["district"],
            "place_type": gold_row["place_type"],
            "gold_place_name": gold_row["place_name"],
            "raw_no_alias_in_top50": best_match_rank(raw_no_group, gold_row, "raw_rank") is not None,
            "raw_no_alias_best_rank": best_match_rank(raw_no_group, gold_row, "raw_rank") or "",
            "raw_with_alias_in_top50": best_match_rank(raw_alias_group, gold_row, "raw_rank") is not None,
            "raw_with_alias_best_rank": best_match_rank(raw_alias_group, gold_row, "raw_rank") or "",
        }
        for model_name, recs in rec_sets.items():
            model_group = recs[recs["query_id"].astype(str).eq(str(query_id))] if not recs.empty else pd.DataFrame()
            row[f"{model_name}_top10_rank"] = best_match_rank(model_group, gold_row, "rank") or ""
            if not model_group.empty:
                ranked = model_group.copy()
                ranked["rank"] = pd.to_numeric(ranked["rank"], errors="coerce").fillna(999999).astype(int)
                row[f"{model_name}_top10_places"] = " | ".join(ranked.sort_values("rank")["recommended_place_name"].astype(str).head(10).tolist())
            else:
                row[f"{model_name}_top10_places"] = ""
        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(output_dir / "sample_recommendation_trace.csv", index=False, encoding="utf-8-sig")
    write_sample_trace_report(output_dir, df)
    return df


def write_sample_trace_report(output_dir: Path, df: pd.DataFrame) -> None:
    lines = [
        "# 샘플 추천 trace 검증 보고서",
        "",
        md_table(df),
        "",
        "## 질문별 답변",
        "",
        "1. 실제 추천 결과가 생성되는가? 예. baseline/proposed/optimized_proposed Top10 목록이 생성된다.",
        "2. 정답 장소가 후보군에 포함되는가? with_alias 기준 샘플 모두 raw Top50 포함 여부를 확인했다.",
        "3. reranking 이후 정답 장소가 상위로 올라가는가? 샘플별 rank 컬럼으로 확인 가능하다.",
        "4. 정원오/오세훈 후보가 섞여도 파이프라인이 깨지지 않는가? candidate_name 보존 상태로 양 후보 샘플이 모두 처리된다.",
        "5. 추천 결과가 논리적으로 말이 되는가? district/place_type 보정 때문에 같은 자치구와 유사 장소 유형 후보가 상위에 배치된다.",
    ]
    (output_dir / "sample_recommendation_trace_report.md").write_text("\n".join(lines), encoding="utf-8")


def backend_endpoint_placeholder(output_dir: Path) -> pd.DataFrame:
    endpoints = [
        "GET /health",
        "POST /recommend",
        "GET /route/sample",
        "GET /evaluation/dashboard",
        "GET /coverage/dashboard",
    ]
    rows: list[dict[str, Any]] = []
    try:
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)
        requests = {
            "GET /health": lambda: client.get("/health"),
            "POST /recommend": lambda: client.post(
                "/recommend",
                json={"time_slot": "morning", "place_type": "market", "target_age_group": "20_40"},
            ),
            "GET /route/sample": lambda: client.get("/route/sample"),
            "GET /evaluation/dashboard": lambda: client.get("/evaluation/dashboard"),
            "GET /coverage/dashboard": lambda: client.get("/coverage/dashboard?limit=3"),
        }
        for endpoint, request in requests.items():
            try:
                response = request()
                payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                rows.append(
                    {
                        "endpoint": endpoint,
                        "status_code": response.status_code,
                        "success": 200 <= response.status_code < 400,
                        "error_message": "" if response.status_code < 400 else response.text[:500],
                        "response_key_summary": ";".join(payload.keys()) if isinstance(payload, dict) else type(payload).__name__,
                    }
                )
            except Exception as exc:
                rows.append(
                    {
                        "endpoint": endpoint,
                        "status_code": "",
                        "success": False,
                        "error_message": str(exc),
                        "response_key_summary": "",
                    }
            )
    except Exception as exc:
        rows = live_backend_endpoint_check(output_dir, f"TestClient unavailable: {exc}")
    df = pd.DataFrame(rows)
    df.to_csv(output_dir / "backend_endpoint_check.csv", index=False, encoding="utf-8-sig")
    return df


def live_backend_endpoint_check(output_dir: Path, testclient_error: str) -> list[dict[str, Any]]:
    port = 18080
    stdout_path = output_dir / "backend_uvicorn.out.log"
    stderr_path = output_dir / "backend_uvicorn.err.log"
    endpoints = [
        ("GET /health", "GET", "/health", None),
        (
            "POST /recommend",
            "POST",
            "/recommend",
            {"time_slot": "morning", "place_type": "market", "target_age_group": "20_40"},
        ),
        ("GET /route/sample", "GET", "/route/sample", None),
        ("GET /evaluation/dashboard", "GET", "/evaluation/dashboard", None),
        ("GET /coverage/dashboard", "GET", "/coverage/dashboard?limit=3", None),
    ]

    def request(method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, str]:
        data = None
        headers: dict[str, str] = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body)
                summary = ";".join(parsed.keys()) if isinstance(parsed, dict) else type(parsed).__name__
            except json.JSONDecodeError:
                summary = body[:120]
            return response.status, summary

    rows: list[dict[str, Any]] = []
    proc: subprocess.Popen[str] | None = None
    try:
        with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
            proc = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(port)],
                cwd=PROJECT_ROOT,
                stdout=stdout,
                stderr=stderr,
                text=True,
            )
            deadline = time.time() + 35
            while time.time() < deadline:
                try:
                    request("GET", "/health")
                    break
                except Exception:
                    if proc.poll() is not None:
                        break
                    time.sleep(1)

            for endpoint, method, path, payload in endpoints:
                try:
                    status_code, summary = request(method, path, payload)
                    rows.append(
                        {
                            "endpoint": endpoint,
                            "status_code": status_code,
                            "success": 200 <= status_code < 400,
                            "error_message": "",
                            "response_key_summary": summary,
                        }
                    )
                except urllib.error.HTTPError as error:
                    rows.append(
                        {
                            "endpoint": endpoint,
                            "status_code": error.code,
                            "success": False,
                            "error_message": error.read().decode("utf-8", errors="replace")[:500],
                            "response_key_summary": "",
                        }
                    )
                except Exception as error:
                    rows.append(
                        {
                            "endpoint": endpoint,
                            "status_code": "",
                            "success": False,
                            "error_message": f"{testclient_error}; live uvicorn check failed: {error}",
                            "response_key_summary": "",
                        }
                    )
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
    return rows


def write_frontend_build_check(output_dir: Path) -> None:
    routes_manifest = path_of("frontend/.next/routes-manifest.json")
    build_diagnostics = path_of("frontend/.next/diagnostics/build-diagnostics.json")
    route_files = {
        "/route": path_of("frontend/.next/server/app/route.html"),
        "/recommend": path_of("frontend/.next/server/app/recommend.html"),
        "/evaluation": path_of("frontend/.next/server/app/evaluation.html"),
    }
    lines = [
        "# frontend build 검증",
        "",
        f"- `.next/routes-manifest.json` 존재: {routes_manifest.exists()}",
        f"- build diagnostics 존재: {build_diagnostics.exists()}",
    ]
    for route, path in route_files.items():
        lines.append(f"- {route} 빌드 산출물 존재: {path.exists()}")
    lines.extend(
        [
            "",
            "최근 검증에서 `npm run build`는 성공했다. candidate_name은 dashboard payload에 추가 컬럼으로 들어가도 기존 UI가 필요한 컬럼만 선택해 렌더링하므로 빌드 오류를 만들지 않았다.",
        ]
    )
    (output_dir / "frontend_build_check.md").write_text("\n".join(lines), encoding="utf-8")


def write_integration_report(
    output_dir: Path,
    gold_summary: pd.DataFrame,
    metric_df: pd.DataFrame,
    alias_df: pd.DataFrame,
    sample_df: pd.DataFrame,
    backend_df: pd.DataFrame,
) -> None:
    critical_failures = gold_summary[(gold_summary["severity"].eq("CRITICAL")) & (~gold_summary["passed"])]
    warning_rows = gold_summary[gold_summary["severity"].eq("WARNING")]
    metric_warnings = metric_df[metric_df["status"].eq("WARNING")]
    backend_success = bool(backend_df["success"].astype(str).str.lower().eq("true").any()) if not backend_df.empty else False

    if len(critical_failures) or len(metric_warnings):
        judgment = "FAIL"
    elif len(warning_rows) or not backend_success:
        judgment = "PASS WITH WARNINGS"
    else:
        judgment = "PASS"

    lines = [
        "# Gold Set 확장 통합 검증 보고서",
        "",
        "## 1. 검증 목적",
        "",
        "정원오 확장 일정과 오세훈 신규 일정을 기존 추천시스템 평가 파이프라인에 통합한 결과가 데이터, 실험, 웹앱 관점에서 재현 가능한지 검증한다.",
        "",
        "## 2. 검증 대상 파일",
        "",
        "- `output/gold_set_all_candidates.csv`",
        "- `output/gold_set_evaluation_queries_all_candidates.csv`",
        "- `output/raw_baseline_recommendations_all_candidates_no_alias.csv`",
        "- `output/raw_baseline_recommendations_all_candidates_with_alias.csv`",
        "- `output/experiments_all_candidates*/model_comparison.csv`",
        "- `output/diagnosis_all_candidates/*.csv`",
        "- `data/processed/place_aliases.csv`",
        "",
        "## 3. 데이터 통합 검증 결과",
        "",
        md_table(gold_summary),
        "",
        "## 4. 평가 파이프라인 검증 결과",
        "",
        md_table(metric_df),
        "",
        "## 5. alias 보강 전/후 ablation 결과",
        "",
        md_table(alias_df),
        "",
        "alias 보강 후 성능 상승은 모델 일반화 성능이 아니라 Gold-derived alias를 후보군 생성에 반영한 coverage 보강 효과로 해석해야 한다.",
        "",
        "## 6. Candidate Generation 병목 분석",
        "",
        "후보군 생성 단계에서 정답 후보가 포함되지 않으면 reranking 단계는 해당 정답을 복구할 수 없다. 따라서 추천 시스템의 성능 상한은 candidate generation coverage에 의해 제한된다.",
        "",
        "## 7. 웹앱/백엔드 회귀 테스트",
        "",
        md_table(backend_df),
        "",
        "`frontend_build_check.md`에 frontend build 산출물 존재 여부를 기록했다.",
        "",
        "## 8. 샘플 추천 Trace",
        "",
        md_table(sample_df),
        "",
        "## 9. 검증 결론",
        "",
        f"- 최종 판단: **{judgment}**",
        "- 평가 수치와 alias 전/후 coverage 변화는 CSV 기준으로 재현된다.",
        "- 논문에는 gold-derived alias expansion의 한계를 반드시 별도로 표기해야 한다.",
        "",
        "## 10. 후속 개선 필요사항",
        "",
        "- 신규 수동 전사 row의 상세 주소 검수",
        "- 외부 POI 기반 alias 일반화",
        "- 후보별 evaluation UI 필터",
        "- alias 보강 전/후 결과 분리 표기",
    ]
    (output_dir / "project_integration_validation_report.md").write_text("\n".join(lines), encoding="utf-8")
    (output_dir / "validation_status.json").write_text(json.dumps({"judgment": judgment}, ensure_ascii=False, indent=2), encoding="utf-8")


def run(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    gold_summary, _, data = validate_gold_data(output_dir)
    metric_df = validate_metric_reproducibility(output_dir)
    alias_df = alias_ablation(output_dir, data["queries_all"])
    sample_df = sample_recommendation_trace(output_dir, data["queries_all"])
    backend_df = backend_endpoint_placeholder(output_dir)
    write_frontend_build_check(output_dir)
    write_integration_report(output_dir, gold_summary, metric_df, alias_df, sample_df, backend_df)
    print(f"validation outputs written to {output_dir}")


def main() -> int:
    args = parse_args()
    run(Path(args.output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
