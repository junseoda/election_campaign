"""Build strong-positive evaluation queries from an integrated Gold Set."""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from normalize_gold_set import GOLD_COLUMNS, normalize_dataframe, read_csv_with_fallback  # noqa: E402


EVALUATION_COLUMNS = [
    "query_id",
    "candidate_name",
    "evaluation_context",
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
    "relevance",
    "is_strong_positive",
    "normalized_place_key",
]

CANDIDATE_SLUGS = {"정원오": "jungwono", "오세훈": "ohsehoon"}
CANDIDATE_PREFIX = {"정원오": "JG", "오세훈": "OH"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build strong offline place-recommendation queries.")
    parser.add_argument("--gold", required=True, help="Integrated Gold Set CSV")
    parser.add_argument("--output", required=True, help="Evaluation query CSV output")
    parser.add_argument("--candidate", default="all", help="all, 정원오, or 오세훈")
    parser.add_argument("--write_candidate_files", action="store_true", help="Also write candidate split files")
    return parser.parse_args()


def clean_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def normalize_place_key(value: object) -> str:
    text = unicodedata.normalize("NFKC", clean_text(value)).lower()
    return re.sub(r"[^0-9a-z가-힣]", "", text)


def bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["true", "1", "yes", "y", "사용", "예"])


def is_missing_place(value: object) -> bool:
    text = clean_text(value)
    return text in {"", "해당 없음", "확인 필요", "미상", "unknown"}


def build_queries(gold: pd.DataFrame, candidate: str = "all") -> pd.DataFrame:
    normalized = normalize_dataframe(gold)
    if candidate and candidate != "all":
        normalized = normalized[normalized["candidate_name"].eq(candidate)].copy()

    label = pd.to_numeric(normalized["gold_label_0_3"], errors="coerce").fillna(0).astype(int)
    offline = normalized["online_offline"].astype(str).str.lower().isin(["offline", "hybrid", "오프라인", "혼합"])
    place_use = bool_series(normalized["use_for_place_recommendation"])
    has_place = ~normalized["place_name"].map(is_missing_place)
    has_district = ~normalized["district"].map(is_missing_place)

    strong = normalized[label.eq(3) & offline & place_use & has_place & has_district].copy()
    strong["normalized_place_key"] = strong["place_name"].map(normalize_place_key)
    strong = strong[strong["normalized_place_key"].ne("")].copy()
    strong["relevance"] = 3
    strong["is_strong_positive"] = True

    def make_query_id(row: pd.Series) -> str:
        prefix = CANDIDATE_PREFIX.get(row["candidate_name"], "CD")
        time_text = clean_text(row["time"]).replace(":", "")
        place_key = clean_text(row["normalized_place_key"])[:16]
        return f"{prefix}_{row['date'].replace('-', '')}_{time_text}_{row['district']}_{place_key}_{row['gold_id']}"

    strong["query_id"] = strong.apply(make_query_id, axis=1)
    strong["evaluation_context"] = strong.apply(
        lambda row: f"{row['candidate_name']} {row['date']} {row['time']} {row['district']}에서 유세 장소를 추천",
        axis=1,
    )
    strong = strong.drop_duplicates("query_id", keep="first").reset_index(drop=True)
    for column in EVALUATION_COLUMNS:
        if column not in strong.columns:
            strong[column] = ""
    return strong[EVALUATION_COLUMNS]


def candidate_output_path(base_output: Path, candidate_name: str) -> Path:
    slug = CANDIDATE_SLUGS.get(candidate_name, candidate_name)
    return base_output.with_name(f"gold_set_evaluation_queries_{slug}.csv")


def run(gold_path: Path, output_path: Path, candidate: str, write_candidate_files: bool) -> None:
    gold = read_csv_with_fallback(gold_path)
    selected = build_queries(gold, candidate)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    selected.to_csv(output_path, index=False, encoding="utf-8-sig")

    if candidate == "all":
        all_path = output_path.with_name("gold_set_evaluation_queries_all_candidates.csv")
        if all_path.resolve() != output_path.resolve():
            selected.to_csv(all_path, index=False, encoding="utf-8-sig")

    if write_candidate_files or candidate == "all":
        for candidate_name in ["정원오", "오세훈"]:
            candidate_queries = build_queries(gold, candidate_name)
            candidate_queries.to_csv(candidate_output_path(output_path, candidate_name), index=False, encoding="utf-8-sig")

    print("=== evaluation queries ===")
    print(f"candidate: {candidate}")
    print(f"queries: {len(selected)}")
    print(f"output: {output_path}")
    if len(selected):
        print(selected["candidate_name"].value_counts().to_string())


def main() -> int:
    args = parse_args()
    run(Path(args.gold), Path(args.output), args.candidate, args.write_candidate_files)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
