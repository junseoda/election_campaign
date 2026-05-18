"""Generate evaluation-ready recommendation_results.csv from Gold queries.

The recommendation model itself lives in scripts/recommender.py.  This file is
an adapter: it converts each Gold Set evaluation query into the existing model's
input shape, preserves the model's score, and writes the CSV contract consumed
by src/evaluate_recommendations.py.
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

from scripts.recommender import recommend_places  # noqa: E402


SUPPORTED_RECOMMENDER_TYPES = ["market", "park", "subway", "senior_friendly"]
MODEL_VARIANTS = [
    "baseline",
    "district_weighted",
    "place_type_weighted",
    "time_weighted",
    "proposed",
]
GOLD_REQUIRED_COLUMNS = ["query_id", "date", "time", "district", "place_type"]
OUTPUT_COLUMNS = [
    "query_id",
    "rank",
    "recommended_place_name",
    "recommended_district",
    "recommended_place_type",
    "score",
]


class DataValidationError(ValueError):
    """Raised when Gold queries cannot be converted into recommendation inputs."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run existing place recommender for every Gold evaluation query."
    )
    parser.add_argument(
        "--gold",
        default="output/gold_set_evaluation_queries.csv",
        help="Path to output/gold_set_evaluation_queries.csv",
    )
    parser.add_argument(
        "--output",
        default="output/recommendation_results.csv",
        help="Path where recommendation_results.csv will be saved",
    )
    parser.add_argument("--top_k", type=int, default=10, help="Number of recommendations per query")
    parser.add_argument(
        "--candidate_pool",
        type=int,
        default=200,
        help="Number of candidates to request from each existing recommender before query filtering",
    )
    parser.add_argument(
        "--model",
        choices=MODEL_VARIANTS,
        default="baseline",
        help="Recommendation variant to generate",
    )
    return parser.parse_args()


def read_csv_with_fallback(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Gold 평가 query 파일이 존재하지 않습니다: {path}")

    errors: list[str] = []
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(path, encoding=encoding, dtype=str, keep_default_na=False)
        except UnicodeDecodeError as exc:
            errors.append(f"{encoding}: {exc}")
        except pd.errors.ParserError as exc:
            raise DataValidationError(f"Gold 평가 query CSV 파싱에 실패했습니다: {exc}") from exc

    raise DataValidationError(f"Gold 평가 query 파일을 읽을 수 없습니다. {' / '.join(errors)}")


def validate_gold_queries(gold_queries: pd.DataFrame) -> None:
    missing = [column for column in GOLD_REQUIRED_COLUMNS if column not in gold_queries.columns]
    if missing:
        raise DataValidationError(f"Gold 평가 query 필수 컬럼이 누락되었습니다: {', '.join(missing)}")

    empty_query = gold_queries["query_id"].astype(str).str.strip().eq("")
    if empty_query.any():
        raise DataValidationError("Gold 평가 query에 비어 있는 query_id가 있습니다.")


def derive_time_slot(time_text: object) -> str:
    text = str(time_text).strip()
    try:
        hour = int(text.split(":", maxsplit=1)[0])
    except (ValueError, IndexError):
        return "afternoon"

    if 5 <= hour < 12:
        return "morning"
    return "afternoon"


def derive_hour(time_text: object) -> int | None:
    text = str(time_text).strip()
    try:
        hour = int(text.split(":", maxsplit=1)[0])
    except (ValueError, IndexError):
        return None
    return hour if 0 <= hour <= 23 else None


def infer_target_age_group(row: pd.Series) -> str:
    text = " ".join(
        str(row.get(column, ""))
        for column in (
            "place_type",
            "campaign_activity_type",
            "target_voter_group",
            "context_tags",
        )
    )
    senior_keywords = ["노년", "노인", "어르신", "고령", "복지", "60"]
    if any(keyword in text for keyword in senior_keywords):
        return "60_plus"
    return "20_40"


def infer_recommender_types(row: pd.Series) -> list[str]:
    text = " ".join(
        str(row.get(column, ""))
        for column in (
            "place_type",
            "campaign_activity_type",
            "target_voter_group",
            "context_tags",
            "evaluation_context",
        )
    )

    if any(keyword in text for keyword in ["전통시장", "시장", "골목상권", "상권", "상인"]):
        return ["market"]
    if any(keyword in text for keyword in ["복지", "노인", "어르신", "고령"]):
        return ["senior_friendly"]
    if any(keyword in text for keyword in ["교통", "역", "퇴근", "출근", "사거리"]):
        return ["subway"]
    if any(keyword in text for keyword in ["공원", "하천", "도림천", "산", "광장", "체육", "어린이", "가족"]):
        return ["park"]

    # Some Gold Set place types, such as policy sites, labor sites, religious
    # events, and redevelopment sites, do not have a one-to-one MVP recommender.
    # For those queries, run all existing place recommenders and let scores rank.
    return SUPPORTED_RECOMMENDER_TYPES.copy()


def expected_place_types(row: pd.Series) -> set[str]:
    text = " ".join(
        str(row.get(column, ""))
        for column in (
            "place_type",
            "campaign_activity_type",
            "target_voter_group",
            "context_tags",
            "evaluation_context",
        )
    )

    expected: set[str] = set()
    if any(keyword in text for keyword in ["전통시장", "시장", "골목상권", "상권", "상인"]):
        expected.add("market")
    if any(keyword in text for keyword in ["공원", "광장", "하천", "도림천", "산", "체육", "어린이", "가족"]):
        expected.add("park")
    if any(keyword in text for keyword in ["복지", "노인", "어르신", "고령"]):
        expected.add("senior_friendly")
    if any(keyword in text for keyword in ["교통", "역", "퇴근", "출근", "사거리", "직장인"]):
        expected.add("subway")

    return expected


def clean_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def cached_recommendations(
    cache: dict[tuple[str, str, str, int], list[dict[str, Any]]],
    time_slot: str,
    place_type: str,
    target_age_group: str,
    candidate_pool: int,
) -> list[dict[str, Any]]:
    key = (time_slot, place_type, target_age_group, candidate_pool)
    if key not in cache:
        cache[key] = recommend_places(
            time_slot=time_slot,
            place_type=place_type,
            target_age_group=target_age_group,
            top_n=candidate_pool,
        )
    return cache[key]


def deduplicate_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []

    for candidate in candidates:
        name = clean_text(candidate.get("name"))
        district = clean_text(candidate.get("district_name"))
        place_type = clean_text(candidate.get("place_type"))
        if not name:
            continue

        key = (name, district, place_type)
        if key in seen:
            continue

        seen.add(key)
        deduped.append(candidate)

    return deduped


def score_value(candidate: dict[str, Any]) -> float:
    try:
        return float(candidate.get("score", 0.0))
    except (TypeError, ValueError):
        return 0.0


def district_bonus(row: pd.Series, candidate: dict[str, Any]) -> float:
    query_district = clean_text(row.get("district", ""))
    candidate_district = clean_text(candidate.get("district_name", ""))
    if query_district and candidate_district and query_district == candidate_district:
        return 0.18
    return 0.0


def place_type_bonus(row: pd.Series, candidate: dict[str, Any]) -> float:
    candidate_type = clean_text(candidate.get("place_type"))
    if not candidate_type:
        return 0.0

    expected_types = expected_place_types(row)
    if candidate_type in expected_types:
        return 0.15

    # 체육시설, 어린이/가족시설 등은 MVP 데이터에서는 공원 계열 후보로
    # 대응하는 것이 가장 자연스럽다.
    gold_place_type = clean_text(row.get("place_type", ""))
    if candidate_type == "park" and any(keyword in gold_place_type for keyword in ["체육", "어린이", "가족"]):
        return 0.10
    return 0.0


def time_bonus(row: pd.Series, candidate: dict[str, Any]) -> float:
    hour = derive_hour(row.get("time", ""))
    candidate_type = clean_text(candidate.get("place_type"))
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


def context_bonus(row: pd.Series, candidate: dict[str, Any]) -> float:
    text = " ".join(
        str(row.get(column, ""))
        for column in (
            "campaign_activity_type",
            "target_voter_group",
            "context_tags",
        )
    )
    candidate_type = clean_text(candidate.get("place_type"))

    bonus = 0.0
    if candidate_type == "market" and any(keyword in text for keyword in ["상인", "지역상권", "생활권", "상권"]):
        bonus += 0.07
    if candidate_type == "park" and any(keyword in text for keyword in ["가족", "일반시민", "체육", "방문인사"]):
        bonus += 0.06
    if candidate_type == "senior_friendly" and any(keyword in text for keyword in ["노년", "노인", "복지", "어르신"]):
        bonus += 0.07
    if candidate_type == "subway" and any(keyword in text for keyword in ["직장인", "퇴근", "출근", "교통"]):
        bonus += 0.06

    return bonus


def variant_score(row: pd.Series, candidate: dict[str, Any], model_name: str) -> float:
    base_score = score_value(candidate)
    if model_name == "baseline":
        return base_score
    if model_name == "district_weighted":
        return base_score + district_bonus(row, candidate)
    if model_name == "place_type_weighted":
        return base_score + place_type_bonus(row, candidate)
    if model_name == "time_weighted":
        return base_score + time_bonus(row, candidate)
    if model_name == "proposed":
        return (
            base_score
            + district_bonus(row, candidate)
            + place_type_bonus(row, candidate)
            + time_bonus(row, candidate)
            + context_bonus(row, candidate)
        )
    raise DataValidationError(f"지원하지 않는 모델 variant입니다: {model_name}")


def select_top_k_for_query(candidates: list[dict[str, Any]], query_district: str, top_k: int) -> list[dict[str, Any]]:
    sorted_candidates = sorted(
        candidates,
        key=lambda candidate: (score_value(candidate), clean_text(candidate.get("name"))),
        reverse=True,
    )

    same_district = [
        candidate
        for candidate in sorted_candidates
        if query_district and clean_text(candidate.get("district_name")) == query_district
    ]

    if same_district:
        selected = same_district[:top_k]
        selected_keys = {
            (
                clean_text(candidate.get("name")),
                clean_text(candidate.get("district_name")),
                clean_text(candidate.get("place_type")),
            )
            for candidate in selected
        }
        for candidate in sorted_candidates:
            key = (
                clean_text(candidate.get("name")),
                clean_text(candidate.get("district_name")),
                clean_text(candidate.get("place_type")),
            )
            if key in selected_keys:
                continue
            selected.append(candidate)
            if len(selected) >= top_k:
                break
    else:
        selected = sorted_candidates[:top_k]

    return sorted(
        selected[:top_k],
        key=lambda candidate: (score_value(candidate), clean_text(candidate.get("name"))),
        reverse=True,
    )


def select_top_k_for_variant(
    row: pd.Series,
    candidates: list[dict[str, Any]],
    top_k: int,
    model_name: str,
) -> list[dict[str, Any]]:
    scored_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        scored_candidate = candidate.copy()
        scored_candidate["variant_score"] = variant_score(row, candidate, model_name)
        scored_candidates.append(scored_candidate)

    return sorted(
        scored_candidates,
        key=lambda candidate: (
            float(candidate.get("variant_score", 0.0)),
            clean_text(candidate.get("name")),
        ),
        reverse=True,
    )[:top_k]


def build_recommendations_for_query(
    row: pd.Series,
    cache: dict[tuple[str, str, str, int], list[dict[str, Any]]],
    top_k: int,
    candidate_pool: int,
    model_name: str,
) -> list[dict[str, Any]]:
    query_id = clean_text(row["query_id"])
    query_district = clean_text(row["district"])
    time_slot = derive_time_slot(row["time"])
    target_age_group = infer_target_age_group(row)
    recommender_types = infer_recommender_types(row)

    candidates: list[dict[str, Any]] = []
    for recommender_type in recommender_types:
        candidates.extend(
            cached_recommendations(
                cache=cache,
                time_slot=time_slot,
                place_type=recommender_type,
                target_age_group=target_age_group,
                candidate_pool=candidate_pool,
            )
        )

    deduped_candidates = deduplicate_candidates(candidates)
    if model_name == "baseline":
        selected = select_top_k_for_query(
            deduped_candidates,
            query_district=query_district,
            top_k=top_k,
        )
    else:
        selected = select_top_k_for_variant(
            row=row,
            candidates=deduped_candidates,
            top_k=top_k,
            model_name=model_name,
        )

    rows: list[dict[str, Any]] = []
    for rank, candidate in enumerate(selected, start=1):
        rows.append(
            {
                "query_id": query_id,
                "rank": rank,
                "recommended_place_name": clean_text(candidate.get("name")),
                "recommended_district": clean_text(candidate.get("district_name")),
                "recommended_place_type": clean_text(candidate.get("place_type")),
                "score": round(variant_score(row, candidate, model_name), 4),
            }
        )
    return rows


def build_recommendation_results(
    gold_queries: pd.DataFrame,
    top_k: int,
    candidate_pool: int,
    model_name: str = "baseline",
) -> pd.DataFrame:
    if top_k <= 0:
        raise DataValidationError("--top_k 값은 양의 정수여야 합니다.")
    if candidate_pool < top_k:
        raise DataValidationError("--candidate_pool 값은 --top_k 이상이어야 합니다.")
    if model_name not in MODEL_VARIANTS:
        raise DataValidationError(f"지원하지 않는 모델 variant입니다: {model_name}")

    validate_gold_queries(gold_queries)

    cache: dict[tuple[str, str, str, int], list[dict[str, Any]]] = {}
    rows: list[dict[str, Any]] = []
    for _, query in gold_queries.iterrows():
        rows.extend(
            build_recommendations_for_query(
                row=query,
                cache=cache,
                top_k=top_k,
                candidate_pool=candidate_pool,
                model_name=model_name,
            )
        )

    results = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    if results.empty:
        raise DataValidationError("추천 결과가 비어 있습니다. 기존 추천 알고리즘 출력과 Gold query 매핑을 확인하세요.")

    return results


def run(gold_path: Path, output_path: Path, top_k: int, candidate_pool: int, model_name: str) -> None:
    gold_queries = read_csv_with_fallback(gold_path)
    results = build_recommendation_results(
        gold_queries,
        top_k=top_k,
        candidate_pool=candidate_pool,
        model_name=model_name,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output_path, index=False, encoding="utf-8-sig")

    query_count = results["query_id"].nunique()
    print("=== 추천 결과 CSV 생성 완료 ===")
    print(f"모델 variant: {model_name}")
    print(f"Gold query 수: {query_count}")
    print(f"추천 row 수: {len(results)}")
    print(f"query당 최대 추천 수: {top_k}")
    print(f"저장 경로: {output_path}")


def main() -> int:
    args = parse_args()
    try:
        run(Path(args.gold), Path(args.output), args.top_k, args.candidate_pool, args.model)
    except (FileNotFoundError, DataValidationError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"[ERROR] 파일 처리 중 오류가 발생했습니다: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
