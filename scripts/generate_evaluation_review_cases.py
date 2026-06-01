import argparse
import csv
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HIT_ANALYSIS_PATH = REPO_ROOT / "output" / "experiments_all_candidates" / "optimized" / "optimized_proposed" / "hit_analysis.csv"
QUERY_PATH = REPO_ROOT / "output" / "gold_set_evaluation_queries_all_candidates.csv"


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def is_true(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def build_case(row: dict, query: dict) -> dict:
    return {
        "query_id": row.get("query_id", ""),
        "query": query.get("evaluation_context") or f"{query.get('date')} {query.get('time')} {query.get('district')} {query.get('place_type')}",
        "gold_place": row.get("gold_place_name") or query.get("place_name", ""),
        "recommended_top1": row.get("recommended_top1", ""),
        "recommended_top3": row.get("recommended_top3", ""),
        "best_hit_rank": row.get("best_hit_rank", ""),
        "top1_hit": is_true(row.get("hit_at_1", "")),
    }


def select_cases(limit: int) -> dict:
    hit_rows = read_csv(HIT_ANALYSIS_PATH)
    queries = {row.get("query_id"): row for row in read_csv(QUERY_PATH)}
    top1_hits = []
    top1_misses = []

    for row in hit_rows:
        query = queries.get(row.get("query_id"), {})
        case = build_case(row, query)
        if case["top1_hit"] and len(top1_hits) < limit:
            top1_hits.append(case)
        if not case["top1_hit"] and len(top1_misses) < limit:
            top1_misses.append(case)
        if len(top1_hits) >= limit and len(top1_misses) >= limit:
            break

    if len(top1_hits) < limit:
        raise RuntimeError(f"Top1 Hit 사례가 {limit}개보다 적습니다: {len(top1_hits)}개")
    if len(top1_misses) < limit:
        raise RuntimeError(f"Top1 Miss 사례가 {limit}개보다 적습니다: {len(top1_misses)}개")

    return {
        "status": "PASS",
        "top1_hit_cases": top1_hits,
        "top1_miss_cases": top1_misses,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate professor-review Top1 Hit/Miss examples without modifying evaluation CSV files.")
    parser.add_argument("--limit", type=int, default=5, help="Number of Top1 Hit and Top1 Miss cases to print.")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    args = parser.parse_args()

    result = select_cases(args.limit)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print("# Evaluation Review Cases")
    print("\n## Top1 Hit")
    for index, case in enumerate(result["top1_hit_cases"], start=1):
        print(f"{index}. Query: {case['query']}")
        print(f"   Gold: {case['gold_place']} / Top1: {case['recommended_top1']} / Rank: {case['best_hit_rank']} / Hit: True")
    print("\n## Top1 Miss")
    for index, case in enumerate(result["top1_miss_cases"], start=1):
        print(f"{index}. Query: {case['query']}")
        print(f"   Gold: {case['gold_place']} / Top1: {case['recommended_top1']} / Best Rank: {case['best_hit_rank']} / Hit: False")


if __name__ == "__main__":
    main()
