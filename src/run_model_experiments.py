"""Run raw-baseline re-ranking experiments and build a model comparison table.

All variants in this script start from the same fixed candidate file:
output/raw_baseline_recommendations.csv.  The existing recommender is not
executed here.  Each model only adds its feature bonus to baseline_score and
re-ranks the raw candidates.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from evaluate_recommendations import evaluate, read_csv_with_fallback as read_eval_csv  # noqa: E402
from backend.district_utils import filter_dataframe_by_district, normalize_district  # noqa: E402


MODEL_VARIANTS = [
    "baseline",
    "district_weighted",
    "place_type_weighted",
    "time_weighted",
    "proposed",
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

RECOMMENDATION_OUTPUT_COLUMNS = [
    "query_id",
    "rank",
    "recommended_place_name",
    "recommended_district",
    "recommended_place_type",
    "baseline_score",
    "district_bonus",
    "place_type_bonus",
    "time_bonus",
    "context_bonus",
    "target_bonus",
    "score",
]

COMPARISON_COLUMNS = [
    "model_name",
    "precision_at_1",
    "precision_at_3",
    "precision_at_5",
    "precision_at_10",
    "recall_at_1",
    "recall_at_3",
    "recall_at_5",
    "recall_at_10",
    "ndcg_at_1",
    "ndcg_at_3",
    "ndcg_at_5",
    "ndcg_at_10",
]


class DataValidationError(ValueError):
    """Raised when raw baseline inputs do not match the experiment contract."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate baseline and feature-weighted re-rankers from fixed raw baseline candidates."
    )
    parser.add_argument(
        "--gold",
        default="output/gold_set_evaluation_queries.csv",
        help="Path to output/gold_set_evaluation_queries.csv",
    )
    parser.add_argument(
        "--raw",
        default="output/raw_baseline_recommendations.csv",
        help="Path to output/raw_baseline_recommendations.csv",
    )
    parser.add_argument(
        "--output_dir",
        default="output/experiments",
        help="Directory where model subdirectories and model_comparison.csv will be saved",
    )
    parser.add_argument("--top_k", type=int, default=10, help="Number of recommendations per query")
    parser.add_argument("--k", nargs="+", type=int, default=[1, 3, 5, 10], help="Evaluation K values")
    parser.add_argument(
        "--models",
        nargs="+",
        choices=MODEL_VARIANTS,
        default=MODEL_VARIANTS,
        help="Model variants to run",
    )
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

    raise DataValidationError(f"{label} 파일을 읽을 수 없습니다. {' / '.join(errors)}")


def validate_raw_baseline(raw_baseline: pd.DataFrame, gold_queries: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in RAW_REQUIRED_COLUMNS if column not in raw_baseline.columns]
    if missing:
        raise DataValidationError(f"raw baseline 필수 컬럼이 누락되었습니다: {', '.join(missing)}")

    prepared = raw_baseline.copy()
    prepared["baseline_score"] = pd.to_numeric(prepared["baseline_score"], errors="coerce")
    prepared["raw_rank"] = pd.to_numeric(prepared["raw_rank"], errors="coerce")

    if prepared["baseline_score"].isna().any():
        bad_rows = prepared.loc[prepared["baseline_score"].isna(), ["query_id", "baseline_score"]].head(10)
        raise DataValidationError(
            "baseline_score를 숫자로 변환할 수 없습니다. "
            f"문제 샘플: {bad_rows.to_dict(orient='records')}"
        )
    if prepared["raw_rank"].isna().any():
        bad_rows = prepared.loc[prepared["raw_rank"].isna(), ["query_id", "raw_rank"]].head(10)
        raise DataValidationError(
            "raw_rank를 숫자로 변환할 수 없습니다. "
            f"문제 샘플: {bad_rows.to_dict(orient='records')}"
        )

    gold_query_ids = set(gold_queries["query_id"].astype(str))
    raw_query_ids = set(prepared["query_id"].astype(str))
    missing_queries = sorted(gold_query_ids - raw_query_ids)
    if missing_queries:
        raise DataValidationError(f"raw baseline에 누락된 query_id가 있습니다: {missing_queries[:10]}")

    max_candidates = int(prepared.groupby("query_id")["raw_rank"].count().max())
    if max_candidates > 50:
        raise DataValidationError(f"query당 raw 후보 수가 50개를 초과합니다: max={max_candidates}")

    return prepared


def clean_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def derive_hour(time_text: object) -> int | None:
    text = clean_text(time_text)
    try:
        hour = int(text.split(":", maxsplit=1)[0])
    except (ValueError, IndexError):
        return None
    return hour if 0 <= hour <= 23 else None


def expected_place_types(row: pd.Series) -> set[str]:
    text = " ".join(
        clean_text(row.get(column, ""))
        for column in (
            "place_type",
            "target_voter_group",
            "context_tags",
        )
    )

    expected: set[str] = set()
    if any(keyword in text for keyword in ["전통시장", "시장", "골목상권", "상권", "상인"]):
        expected.add("market")
    if any(keyword in text for keyword in ["공원", "광장", "하천", "도림천", "산", "체육", "어린이", "가족"]):
        expected.add("park")
    if any(keyword in text for keyword in ["복지", "노인", "어르신", "고령", "노년"]):
        expected.add("senior_friendly")
    if any(keyword in text for keyword in ["교통", "역", "퇴근", "출근", "사거리", "직장인"]):
        expected.add("subway")
    return expected


def calc_district_bonus(row: pd.Series) -> float:
    if normalize_district(row.get("district")) and normalize_district(row.get("district")) == normalize_district(row.get("recommended_district")):
        return 0.18
    return 0.0


def calc_place_type_bonus(row: pd.Series) -> float:
    candidate_type = clean_text(row.get("recommended_place_type"))
    if candidate_type in expected_place_types(row):
        return 0.15

    gold_place_type = clean_text(row.get("place_type"))
    if candidate_type == "park" and any(keyword in gold_place_type for keyword in ["체육", "어린이", "가족"]):
        return 0.10
    return 0.0


def calc_time_bonus(row: pd.Series) -> float:
    hour = derive_hour(row.get("time"))
    candidate_type = clean_text(row.get("recommended_place_type"))
    if hour is None:
        return 0.0

    if 7 <= hour < 10:
        if candidate_type == "subway":
            return 0.14
        if candidate_type in {"market", "senior_friendly"}:
            return 0.05
    if 10 <= hour < 12:
        if candidate_type in {"senior_friendly", "market"}:
            return 0.10
        if candidate_type == "park":
            return 0.06
    if 12 <= hour < 16:
        if candidate_type in {"market", "park"}:
            return 0.12
        if candidate_type == "senior_friendly":
            return 0.06
    if 16 <= hour < 20:
        if candidate_type in {"market", "subway"}:
            return 0.12
        if candidate_type == "park":
            return 0.06
    return 0.0


def calc_context_bonus(row: pd.Series) -> float:
    text = " ".join(
        clean_text(row.get(column, ""))
        for column in (
            "target_voter_group",
            "context_tags",
        )
    )
    candidate_type = clean_text(row.get("recommended_place_type"))

    if candidate_type == "market" and any(keyword in text for keyword in ["상인", "지역상권", "생활권", "상권"]):
        return 0.07
    if candidate_type == "park" and any(keyword in text for keyword in ["가족", "일반시민", "체육", "방문인사"]):
        return 0.06
    if candidate_type == "senior_friendly" and any(keyword in text for keyword in ["노년", "노인", "복지", "어르신"]):
        return 0.07
    if candidate_type == "subway" and any(keyword in text for keyword in ["직장인", "퇴근", "출근", "교통"]):
        return 0.06
    return 0.0


def calc_target_bonus(row: pd.Series) -> float:
    target = clean_text(row.get("target_voter_group"))
    candidate_type = clean_text(row.get("recommended_place_type"))

    if candidate_type == "senior_friendly" and any(keyword in target for keyword in ["노년", "노인", "어르신", "복지"]):
        return 0.08
    if candidate_type == "market" and any(keyword in target for keyword in ["상인", "지역주민", "생활권"]):
        return 0.06
    if candidate_type == "subway" and any(keyword in target for keyword in ["직장인", "퇴근길", "일반시민"]):
        return 0.05
    if candidate_type == "park" and any(keyword in target for keyword in ["가족", "일반시민", "지역주민"]):
        return 0.05
    return 0.0


def add_variant_scores(raw_baseline: pd.DataFrame, model_name: str) -> pd.DataFrame:
    scored = raw_baseline.copy()
    scored["district_bonus"] = 0.0
    scored["place_type_bonus"] = 0.0
    scored["time_bonus"] = 0.0
    scored["context_bonus"] = 0.0
    scored["target_bonus"] = 0.0

    if model_name in {"district_weighted", "proposed"}:
        scored["district_bonus"] = scored.apply(calc_district_bonus, axis=1)
    if model_name in {"place_type_weighted", "proposed"}:
        scored["place_type_bonus"] = scored.apply(calc_place_type_bonus, axis=1)
    if model_name in {"time_weighted", "proposed"}:
        scored["time_bonus"] = scored.apply(calc_time_bonus, axis=1)
    if model_name == "proposed":
        scored["context_bonus"] = scored.apply(calc_context_bonus, axis=1)
        scored["target_bonus"] = scored.apply(calc_target_bonus, axis=1)

    scored["score"] = (
        scored["baseline_score"]
        + scored["district_bonus"]
        + scored["place_type_bonus"]
        + scored["time_bonus"]
        + scored["context_bonus"]
        + scored["target_bonus"]
    ).round(4)
    return scored


def build_recommendation_results_from_raw(
    raw_baseline: pd.DataFrame,
    model_name: str,
    top_k: int,
) -> pd.DataFrame:
    if model_name not in MODEL_VARIANTS:
        raise DataValidationError(f"지원하지 않는 모델 variant입니다: {model_name}")
    if top_k <= 0:
        raise DataValidationError("--top_k 값은 양의 정수여야 합니다.")

    scored = add_variant_scores(raw_baseline, model_name)
    result_groups: list[pd.DataFrame] = []

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
            by=["score", "baseline_score", "raw_rank"],
            ascending=[False, False, True],
        ).head(top_k).copy()
        top_group["rank"] = range(1, len(top_group) + 1)
        result_groups.append(top_group)

    if not result_groups:
        raise DataValidationError("모델별 추천 결과가 비어 있습니다.")

    recommendations = pd.concat(result_groups, ignore_index=True)
    for column in [
        "baseline_score",
        "district_bonus",
        "place_type_bonus",
        "time_bonus",
        "context_bonus",
        "target_bonus",
        "score",
    ]:
        recommendations[column] = pd.to_numeric(recommendations[column], errors="coerce").fillna(0.0).round(4)

    return recommendations[RECOMMENDATION_OUTPUT_COLUMNS]


def save_model_outputs(
    model_dir: Path,
    recommendations: pd.DataFrame,
    detail: pd.DataFrame,
    summary: pd.DataFrame,
) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    recommendations.to_csv(model_dir / "recommendation_results.csv", index=False, encoding="utf-8-sig")
    detail.to_csv(model_dir / "evaluation_result.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(model_dir / "evaluation_result_summary.csv", index=False, encoding="utf-8-sig")


def flatten_summary(model_name: str, summary: pd.DataFrame, k_values: list[int]) -> dict[str, float | str]:
    row: dict[str, float | str] = {"model_name": model_name}
    summary_by_k = {int(record["k"]): record for record in summary.to_dict(orient="records")}

    for metric_prefix, summary_column in (
        ("precision", "precision_at_k"),
        ("recall", "recall_at_k"),
        ("ndcg", "ndcg_at_k"),
    ):
        for k in k_values:
            record = summary_by_k.get(int(k))
            row[f"{metric_prefix}_at_{int(k)}"] = float(record[summary_column]) if record else 0.0

    return row


def build_model_comparison(rows: list[dict[str, float | str]]) -> pd.DataFrame:
    comparison = pd.DataFrame(rows)
    for column in COMPARISON_COLUMNS:
        if column not in comparison.columns:
            comparison[column] = 0.0
    return comparison[COMPARISON_COLUMNS]


def run(
    gold_path: Path,
    raw_path: Path,
    output_dir: Path,
    model_names: list[str],
    top_k: int,
    k_values: list[int],
) -> None:
    gold_queries = read_eval_csv(gold_path, "Gold 평가 query")
    raw_baseline = read_csv_with_fallback(raw_path, "raw baseline 추천 후보")
    raw_baseline = validate_raw_baseline(raw_baseline, gold_queries)
    comparison_rows: list[dict[str, float | str]] = []

    print("=== raw baseline 기반 모델 variant 재랭킹 실험 시작 ===")
    print(f"Gold query 파일: {gold_path}")
    print(f"raw baseline 파일: {raw_path}")
    print(f"실험 모델: {', '.join(model_names)}")

    for model_name in model_names:
        print(f"\n[{model_name}] raw 후보 재랭킹 및 평가")
        recommendations = build_recommendation_results_from_raw(
            raw_baseline=raw_baseline,
            model_name=model_name,
            top_k=top_k,
        )
        detail, summary = evaluate(gold_queries, recommendations, k_values)

        model_dir = output_dir / model_name
        save_model_outputs(model_dir, recommendations, detail, summary)
        comparison_rows.append(flatten_summary(model_name, summary, sorted(set(k_values))))

        print(f"- recommendation_results.csv: {model_dir / 'recommendation_results.csv'}")
        print(f"- evaluation_result_summary.csv: {model_dir / 'evaluation_result_summary.csv'}")

    output_dir.mkdir(parents=True, exist_ok=True)
    comparison = build_model_comparison(comparison_rows)
    comparison_path = output_dir / "model_comparison.csv"
    comparison.to_csv(comparison_path, index=False, encoding="utf-8-sig")

    print("\n=== 모델별 비교표 ===")
    print(comparison.to_string(index=False))
    print(f"\n최종 비교표 저장 경로: {comparison_path}")


def main() -> int:
    args = parse_args()
    try:
        run(
            gold_path=Path(args.gold),
            raw_path=Path(args.raw),
            output_dir=Path(args.output_dir),
            model_names=args.models,
            top_k=args.top_k,
            k_values=args.k,
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
