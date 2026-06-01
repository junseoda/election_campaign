from __future__ import annotations

import argparse
import csv
import json
import math
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


DEMO_RECOMMENDATIONS = [
    {
        "forecast_date": "2026-05-30",
        "target_date": "2026-06-01",
        "candidate_name": "정원오",
        "rank": 1,
        "prediction_id": "demo-1",
        "recommended_place_name": "강남역 11번 출구 일대",
        "recommended_district": "강남구",
        "recommended_place_type": "교통거점",
    },
    {
        "forecast_date": "2026-05-30",
        "target_date": "2026-06-01",
        "candidate_name": "정원오",
        "rank": 2,
        "prediction_id": "demo-2",
        "recommended_place_name": "삼성역 코엑스 일대",
        "recommended_district": "강남구",
        "recommended_place_type": "교통거점",
    },
]

DEMO_ACTUAL = [
    {
        "actual_visit_date": "2026-06-01",
        "candidate_name": "정원오",
        "actual_visit_place_name": "강남역 11번 출구",
        "actual_visit_district": "강남구",
        "event_title": "퇴근길 집중 유세",
    },
    {
        "actual_visit_date": "2026-06-01",
        "candidate_name": "정원오",
        "actual_visit_place_name": "코엑스 앞",
        "actual_visit_district": "강남구",
        "event_title": "시민 인사",
    },
]

SEOUL_DISTRICTS = [
    "종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구",
    "성북구", "강북구", "도봉구", "노원구", "은평구", "서대문구", "마포구",
    "양천구", "강서구", "구로구", "금천구", "영등포구", "동작구", "관악구",
    "서초구", "강남구", "송파구", "강동구",
]


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def normalize_text(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"(일대|앞|출구|광장|역|사거리)", "", text)
    return text


def normalize_district(value: Any) -> str:
    text = str(value or "").replace("서울특별시", "").replace("서울시", "").replace("서울", "").strip()
    compact = re.sub(r"\s+", "", text)
    for district in SEOUL_DISTRICTS:
        if district in compact:
            return district
    for district in SEOUL_DISTRICTS:
        alias = district.removesuffix("구")
        if compact == alias:
            return district
    return text


def load_rows(path: Path | None, demo_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if path is None:
        return demo_rows
    if not path.exists():
        raise FileNotFoundError(f"input file not found: {path}")
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return payload
        for key in ("recommendations", "predictions", "items", "timeline", "data"):
            if isinstance(payload.get(key), list):
                return payload[key]
        raise ValueError(f"JSON file does not contain a row list: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def get_rec_field(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def score_match(recommendation: dict[str, Any], actual: dict[str, Any]) -> tuple[str, int]:
    rec_name = normalize_text(get_rec_field(recommendation, "recommended_place_name", "place_name"))
    actual_name = normalize_text(get_rec_field(actual, "actual_visit_place_name", "place_name"))
    rec_address = normalize_text(get_rec_field(recommendation, "address", "recommended_address"))
    actual_address = normalize_text(get_rec_field(actual, "actual_visit_address", "address"))
    rec_district = normalize_district(get_rec_field(recommendation, "recommended_district", "district", "district_normalized"))
    actual_district = normalize_district(get_rec_field(actual, "actual_visit_district", "district", "district_normalized"))
    rec_type = get_rec_field(recommendation, "recommended_place_type", "place_type")
    actual_type = get_rec_field(actual, "actual_visit_place_type", "place_type")

    if rec_name and actual_name and rec_name == actual_name:
        return "exact_place_match", 3
    if rec_name and actual_name and (rec_name in actual_name or actual_name in rec_name):
        return "alias_match", 3
    if rec_address and actual_address and (rec_address in actual_address or actual_address in rec_address):
        return "same_address_match", 2
    if rec_district and rec_district == actual_district and (not actual_type or rec_type == actual_type):
        return "same_district_place_type_match", 1
    return "no_match", 0


def filter_actual_rows(
    actual_rows: list[dict[str, Any]],
    target_date: date | None,
    candidate_name: str,
    evaluation_window_days: int,
) -> list[dict[str, Any]]:
    if target_date is None:
        return actual_rows
    window_end = target_date + timedelta(days=max(0, evaluation_window_days))
    filtered = []
    for row in actual_rows:
        actual_date = parse_date(get_rec_field(row, "actual_visit_date", "visit_date", "date"))
        if actual_date is None or not (target_date <= actual_date <= window_end):
            continue
        row_candidate = get_rec_field(row, "candidate_name", "candidate")
        if candidate_name and row_candidate and row_candidate != candidate_name:
            continue
        filtered.append(row)
    return filtered


def evaluate(
    recommendations: list[dict[str, Any]],
    actual_rows: list[dict[str, Any]],
    evaluation_window_days: int,
    k: int,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    top_k = sorted(recommendations, key=lambda row: int(float(row.get("rank") or row.get("order") or 999999)))[:k]
    if not top_k:
        return {
            "Hit@K": 0.0,
            "Precision@K": 0.0,
            "Recall@K": 0.0,
            "NDCG@K": 0.0,
            "MRR": 0.0,
        }, []

    target_date = parse_date(get_rec_field(top_k[0], "target_date", "date"))
    candidate_name = get_rec_field(top_k[0], "candidate_name", "candidate")
    comparable_actual = filter_actual_rows(actual_rows, target_date, candidate_name, evaluation_window_days)

    rows: list[dict[str, Any]] = []
    for rec in top_k:
        best_match_type = "no_match"
        best_relevance = 0
        best_actual = None
        for actual in comparable_actual:
            match_type, relevance = score_match(rec, actual)
            if relevance > best_relevance:
                best_match_type = match_type
                best_relevance = relevance
                best_actual = actual
        rows.append({
            "forecast_date": get_rec_field(rec, "forecast_date"),
            "target_date": get_rec_field(rec, "target_date", "date"),
            "candidate_name": candidate_name,
            "rank": get_rec_field(rec, "rank", "order"),
            "prediction_id": get_rec_field(rec, "prediction_id", "route_item_id", "id"),
            "recommended_place_name": get_rec_field(rec, "recommended_place_name", "place_name"),
            "recommended_district": normalize_district(get_rec_field(rec, "recommended_district", "district", "district_normalized")),
            "matched_actual_place_name": get_rec_field(best_actual or {}, "actual_visit_place_name", "place_name"),
            "match_type": best_match_type,
            "relevance_score": best_relevance,
        })

    direct_matches = [row for row in rows if int(row["relevance_score"]) >= 2]
    hit_at_k = 1.0 if direct_matches else 0.0
    precision_at_k = len(direct_matches) / max(1, k)
    recall_at_k = min(len(direct_matches), len(comparable_actual)) / len(comparable_actual) if comparable_actual else 0.0
    dcg = sum((2 ** int(row["relevance_score"]) - 1) / math.log2(index + 2) for index, row in enumerate(rows))
    ideal = sorted((int(row["relevance_score"]) for row in rows), reverse=True)
    idcg = sum((2 ** relevance - 1) / math.log2(index + 2) for index, relevance in enumerate(ideal))
    first_match_index = next((index for index, row in enumerate(rows) if int(row["relevance_score"]) >= 2), None)
    mrr = 1 / (first_match_index + 1) if first_match_index is not None else 0.0

    return {
        "Hit@K": hit_at_k,
        "Precision@K": precision_at_k,
        "Recall@K": recall_at_k,
        "NDCG@K": dcg / idcg if idcg else 0.0,
        "MRR": mrr,
    }, rows


def write_preview(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "forecast_date",
        "target_date",
        "candidate_name",
        "rank",
        "prediction_id",
        "recommended_place_name",
        "recommended_district",
        "matched_actual_place_name",
        "match_type",
        "relevance_score",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate future route prediction Top-K recommendations against later actual candidate schedules.")
    parser.add_argument("--recommendations", type=Path, help="Recommendations CSV or JSON generated at forecast_date.")
    parser.add_argument("--actual-schedule", type=Path, help="Actual future candidate schedule CSV or JSON.")
    parser.add_argument("--evaluation-window-days", type=int, default=0)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--output", type=Path, help="Optional preview CSV path. Existing evaluation outputs are never touched unless this explicit path is given.")
    parser.add_argument("--demo", action="store_true", help="Run with a small built-in demo dataset.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.demo:
        recommendations = DEMO_RECOMMENDATIONS
        actual_rows = DEMO_ACTUAL
    else:
        recommendations = load_rows(args.recommendations, DEMO_RECOMMENDATIONS)
        actual_rows = load_rows(args.actual_schedule, DEMO_ACTUAL)

    metrics, rows = evaluate(
        recommendations=recommendations,
        actual_rows=actual_rows,
        evaluation_window_days=args.evaluation_window_days,
        k=max(1, int(args.k)),
    )

    print("future_route_prediction_evaluation")
    for key, value in metrics.items():
        print(f"{key}: {value:.4f}")
    print(f"matched recommendations: {sum(1 for row in rows if int(row['relevance_score']) > 0)}")
    print(f"unmatched recommendations: {sum(1 for row in rows if int(row['relevance_score']) == 0)}")

    if args.output:
        write_preview(args.output, rows)
        print(f"preview_csv: {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
