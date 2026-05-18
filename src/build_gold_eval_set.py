"""Build a strong-positive evaluation set from Jeong Won-oh's Gold Set CSV.

This script intentionally reads one integrated Gold Set file only.  It keeps
the full cleaned table for auditability, then extracts the strict offline
place-recommendation positives used for Precision/Recall/NDCG evaluation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Iterable

import pandas as pd


REQUIRED_COLUMNS = [
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

EVALUATION_BASE_COLUMNS = [
    "gold_id",
    "date",
    "day_of_week",
    "time",
    "district",
    "place_name",
    "address",
    "place_type",
    "campaign_activity_type",
    "target_voter_group",
    "context_tags",
    "gold_label_0_3",
    "source_image",
]

TRUE_VALUES = {"true", "t", "1", "yes", "y", "사용", "예", "네", "맞음"}
FALSE_VALUES = {"false", "f", "0", "no", "n", "미사용", "아니오", "아니요", "틀림", ""}


class DataValidationError(ValueError):
    """Raised when the input Gold Set does not satisfy the expected schema."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build strong offline place positives from one integrated Gold Set CSV."
    )
    parser.add_argument("--input", required=True, help="Path to full_정원오_gold_set_20260309_20260516.csv")
    parser.add_argument("--output_dir", required=True, help="Directory where evaluation files will be saved")
    return parser.parse_args()


def read_csv_with_fallback(input_path: Path) -> tuple[pd.DataFrame, str]:
    if not input_path.exists():
        raise FileNotFoundError(f"입력 CSV 파일이 존재하지 않습니다: {input_path}")

    errors: list[str] = []
    for encoding in ("utf-8-sig", "cp949"):
        try:
            df = pd.read_csv(input_path, encoding=encoding, dtype=str, keep_default_na=False)
            return df, encoding
        except UnicodeDecodeError as exc:
            errors.append(f"{encoding}: {exc}")
        except pd.errors.ParserError as exc:
            raise DataValidationError(f"CSV 파싱에 실패했습니다: {exc}") from exc

    detail = " / ".join(errors)
    raise DataValidationError(f"CSV 인코딩을 utf-8-sig 또는 cp949로 읽을 수 없습니다. {detail}")


def validate_required_columns(df: pd.DataFrame, required_columns: Iterable[str]) -> None:
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise DataValidationError(f"필수 컬럼이 누락되었습니다: {', '.join(missing)}")


def strip_string_columns(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    for column in cleaned.columns:
        if cleaned[column].dtype == "object":
            cleaned[column] = cleaned[column].map(lambda value: value.strip() if isinstance(value, str) else value)
    return cleaned


def drop_duplicate_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Remove exact duplicate rows and duplicated non-empty gold_id values."""

    cleaned = df.drop_duplicates().reset_index(drop=True)
    cleaned["_original_order"] = range(len(cleaned))

    gold_id = cleaned["gold_id"].astype(str).str.strip()
    has_gold_id = gold_id.ne("")
    without_gold_id = cleaned.loc[~has_gold_id]
    with_gold_id = cleaned.loc[has_gold_id].drop_duplicates(subset=["gold_id"], keep="first")

    deduped = pd.concat([without_gold_id, with_gold_id], ignore_index=True)
    deduped = deduped.sort_values("_original_order").drop(columns=["_original_order"]).reset_index(drop=True)
    return deduped


def coerce_gold_label(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    raw_label = cleaned["gold_label_0_3"].astype(str).str.strip()
    numeric_label = pd.to_numeric(raw_label, errors="coerce")

    bad_mask = numeric_label.isna()
    non_integer_mask = numeric_label.notna() & (numeric_label % 1 != 0)
    range_mask = numeric_label.notna() & ~numeric_label.between(0, 3)

    if bad_mask.any() or non_integer_mask.any() or range_mask.any():
        bad_rows = cleaned.loc[bad_mask | non_integer_mask | range_mask, ["gold_id", "gold_label_0_3"]].head(10)
        raise DataValidationError(
            "gold_label_0_3 컬럼을 0~3 정수로 변환할 수 없습니다. "
            f"문제 샘플: {bad_rows.to_dict(orient='records')}"
        )

    cleaned["gold_label_0_3"] = numeric_label.astype(int)
    return cleaned


def coerce_date(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    parsed_date = pd.to_datetime(cleaned["date"], errors="coerce")

    bad_mask = parsed_date.isna()
    if bad_mask.any():
        bad_rows = cleaned.loc[bad_mask, ["gold_id", "date"]].head(10)
        raise DataValidationError(
            "date 컬럼을 날짜 형식으로 변환할 수 없습니다. "
            f"문제 샘플: {bad_rows.to_dict(orient='records')}"
        )

    cleaned["date"] = parsed_date.dt.normalize()
    return cleaned


def normalize_time_value(value: object) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        return ""

    colon_match = re.fullmatch(r"(\d{1,2}):(\d{1,2})", text)
    if colon_match:
        hour = int(colon_match.group(1))
        minute = int(colon_match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
        return text

    compact_match = re.fullmatch(r"(\d{1,2})(\d{2})", text)
    if compact_match:
        hour = int(compact_match.group(1))
        minute = int(compact_match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    return text


def derive_time_slot(time_text: str) -> str:
    match = re.fullmatch(r"(\d{2}):(\d{2})", time_text)
    if not match:
        return "unknown"

    hour = int(match.group(1))
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 22:
        return "evening"
    return "night"


def coerce_bool_series(series: pd.Series) -> pd.Series:
    def to_bool(value: object) -> bool:
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in TRUE_VALUES:
            return True
        if normalized in FALSE_VALUES:
            return False
        return False

    return series.map(to_bool).astype(bool)


def normalize_place_key(value: object) -> str:
    """Create a comparison key that is robust to spaces and punctuation."""

    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).strip().lower()
    return re.sub(r"[^0-9a-z가-힣]", "", text)


def build_gold_all(raw_df: pd.DataFrame) -> pd.DataFrame:
    validate_required_columns(raw_df, REQUIRED_COLUMNS)
    gold_all = strip_string_columns(raw_df)
    gold_all = drop_duplicate_rows(gold_all)
    gold_all = coerce_gold_label(gold_all)
    gold_all = coerce_date(gold_all)
    gold_all["time"] = gold_all["time"].map(normalize_time_value)
    gold_all["time_slot"] = gold_all["time"].map(derive_time_slot)
    return gold_all


def is_present(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().ne("")


def build_strong_place_gold(gold_all: pd.DataFrame) -> pd.DataFrame:
    offline_mask = gold_all["online_offline"].astype(str).str.contains("오프라인", na=False)
    place_recommendation_mask = coerce_bool_series(gold_all["use_for_place_recommendation"])

    place_name = gold_all["place_name"].astype(str).str.strip()
    district = gold_all["district"].astype(str).str.strip()
    address = gold_all["address"].astype(str).str.strip()

    strong_mask = (
        gold_all["gold_label_0_3"].eq(3)
        & offline_mask
        & place_recommendation_mask
        & is_present(place_name)
        & place_name.ne("확인 필요")
        & is_present(district)
        & district.ne("해당 없음")
        & is_present(address)
        & address.ne("해당 없음")
    )

    strong_place_gold = gold_all.loc[strong_mask].copy().reset_index(drop=True)
    if strong_place_gold.empty:
        raise DataValidationError(
            "strong_place_gold 추출 결과가 비어 있습니다. "
            "gold_label_0_3 == 3, 오프라인, 장소 추천 사용 여부, 장소/자치구/주소 조건을 확인하세요."
        )

    strong_place_gold["normalized_place_key"] = strong_place_gold["place_name"].map(normalize_place_key)
    strong_place_gold["is_strong_positive"] = True
    return strong_place_gold


def build_evaluation_queries(strong_place_gold: pd.DataFrame) -> pd.DataFrame:
    eval_queries = strong_place_gold[EVALUATION_BASE_COLUMNS].copy()
    date_text = pd.to_datetime(eval_queries["date"]).dt.strftime("%Y-%m-%d")

    eval_queries["date"] = date_text
    eval_queries["query_id"] = (
        date_text + "_" + eval_queries["time"].astype(str) + "_" + eval_queries["district"].astype(str)
    )
    eval_queries["evaluation_context"] = (
        date_text
        + " "
        + eval_queries["time"].astype(str)
        + " "
        + eval_queries["district"].astype(str)
        + "에서 유세 장소를 추천"
    )
    eval_queries["relevance"] = eval_queries["gold_label_0_3"].astype(int)
    eval_queries["is_strong_positive"] = True
    eval_queries["normalized_place_key"] = eval_queries["place_name"].map(normalize_place_key)

    ordered_columns = [
        "query_id",
        "evaluation_context",
        *EVALUATION_BASE_COLUMNS,
        "relevance",
        "is_strong_positive",
        "normalized_place_key",
    ]
    return eval_queries[ordered_columns].reset_index(drop=True)


def value_counts_dict(series: pd.Series) -> dict[str, int]:
    return {str(key): int(value) for key, value in series.value_counts(dropna=False).items()}


def build_summary(gold_all: pd.DataFrame, strong_place_gold: pd.DataFrame) -> dict[str, object]:
    date_min = pd.to_datetime(gold_all["date"]).min().strftime("%Y-%m-%d")
    date_max = pd.to_datetime(gold_all["date"]).max().strftime("%Y-%m-%d")
    return {
        "total_rows": int(len(gold_all)),
        "strong_place_rows": int(len(strong_place_gold)),
        "date_range": {"start": date_min, "end": date_max},
        "strong_positive_by_district": value_counts_dict(strong_place_gold["district"]),
        "strong_positive_by_place_type": value_counts_dict(strong_place_gold["place_type"]),
        "strong_positive_by_campaign_activity_type": value_counts_dict(
            strong_place_gold["campaign_activity_type"]
        ),
    }


def print_counts(title: str, counts: pd.Series, top_n: int | None = None) -> None:
    print(f"\n{title}")
    display_counts = counts.head(top_n) if top_n else counts
    if display_counts.empty:
        print("- 없음")
        return
    for key, value in display_counts.items():
        print(f"- {key}: {int(value)}")


def save_outputs(
    gold_all: pd.DataFrame,
    strong_place_gold: pd.DataFrame,
    eval_queries: pd.DataFrame,
    summary: dict[str, object],
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "all": output_dir / "gold_set_all_merged.csv",
        "strong": output_dir / "gold_set_strong_place_only.csv",
        "queries": output_dir / "gold_set_evaluation_queries.csv",
        "summary": output_dir / "gold_set_summary.json",
    }

    gold_all.to_csv(paths["all"], index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    strong_place_gold.to_csv(paths["strong"], index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    eval_queries.to_csv(paths["queries"], index=False, encoding="utf-8-sig")
    with paths["summary"].open("w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)

    return paths


def run(input_path: Path, output_dir: Path) -> None:
    raw_df, encoding = read_csv_with_fallback(input_path)
    gold_all = build_gold_all(raw_df)
    strong_place_gold = build_strong_place_gold(gold_all)
    eval_queries = build_evaluation_queries(strong_place_gold)
    summary = build_summary(gold_all, strong_place_gold)
    paths = save_outputs(gold_all, strong_place_gold, eval_queries, summary, output_dir)

    strong_ratio = len(strong_place_gold) / len(gold_all) if len(gold_all) else 0.0
    date_min = pd.to_datetime(gold_all["date"]).min().strftime("%Y-%m-%d")
    date_max = pd.to_datetime(gold_all["date"]).max().strftime("%Y-%m-%d")

    print("=== Gold Set 평가 데이터 구축 결과 ===")
    print(f"입력 인코딩: {encoding}")
    print(f"전체 Gold Set row 수: {len(gold_all)}")
    print(f"strong positive row 수: {len(strong_place_gold)}")
    print(f"strong positive 비율: {strong_ratio:.2%}")
    print(f"기간 범위: {date_min} ~ {date_max}")

    print_counts("자치구별 strong positive 상위 10개", strong_place_gold["district"].value_counts(), top_n=10)
    print_counts("장소 유형별 strong positive 분포", strong_place_gold["place_type"].value_counts())
    print_counts(
        "일정 유형별 strong positive 분포",
        strong_place_gold["campaign_activity_type"].value_counts(),
    )

    print("\n저장된 파일 경로")
    for path in paths.values():
        print(f"- {path}")


def main() -> int:
    args = parse_args()
    try:
        run(Path(args.input), Path(args.output_dir))
    except (FileNotFoundError, DataValidationError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"[ERROR] 파일 처리 중 오류가 발생했습니다: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
