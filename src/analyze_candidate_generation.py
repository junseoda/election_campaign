"""Diagnose candidate generation bottlenecks from optimized experiment outputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


PLACE_TYPE_RECOMMENDATIONS = {
    "전통시장": "전통시장 공식 목록에 시장 출입구/남문/북문, 통칭, 별칭을 확장하고 상권 POI alias table을 추가",
    "골목상권": "서울시 골목상권/상점가/먹자골목 데이터와 상권명 alias를 후보군에 추가",
    "공원": "공원뿐 아니라 하천 산책로, 산 정상/팔각정, 광장, 생활권 야외공간 POI를 확장",
    "복지시설": "노인복지시설 외에 종합사회복지관, 장애인복지관, 구립 복지시설 목록을 통합",
    "체육시설": "공공체육시설, 학교/학생체육관, 생활체육 행사장 데이터를 별도 candidate source로 추가",
    "교통거점": "지하철역 외에 사거리, 광장, 주요 도로 결절점, 버스 환승거점 데이터를 추가",
    "정책현장": "정책 발표/민원 현장 후보로 공공시설, 도시문제 현장, 생활 SOC 데이터를 추가",
    "노동현장": "노동조합, 산업단지, 사업장 밀집지, 근로자센터 후보군을 별도 구축",
    "재개발/도시개발현장": "정비사업구역, 재개발/재건축 사업지, 도시개발 프로젝트 위치 데이터를 추가",
    "어린이/가족시설": "어린이공원, 키즈시설, 가족센터, 보육/돌봄시설 후보군을 추가",
    "종교시설": "종교시설 POI와 종교행사 장소 후보군을 별도 구축",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze raw candidate coverage and hit/miss patterns.")
    parser.add_argument("--gold", default="output/gold_set_evaluation_queries.csv")
    parser.add_argument("--coverage", default="output/experiments_optimized/raw_candidate_coverage.csv")
    parser.add_argument("--hit", default="output/experiments_optimized/optimized_proposed/hit_analysis.csv")
    parser.add_argument("--raw", default="output/raw_baseline_recommendations.csv")
    parser.add_argument("--output_dir", default="output/experiments_optimized")
    return parser.parse_args()


def read_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{label} file not found: {path}")
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not read {label}: {path}")


def bool_series(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().isin(["true", "1", "yes"])


def build_analysis_frame(gold: pd.DataFrame, coverage: pd.DataFrame, hit: pd.DataFrame) -> pd.DataFrame:
    gold_columns = [
        "query_id",
        "gold_id",
        "date",
        "time",
        "district",
        "place_name",
        "address",
        "place_type",
        "campaign_activity_type",
        "target_voter_group",
        "context_tags",
    ]
    frame = gold[gold_columns].copy()
    frame = frame.merge(
        coverage[
            [
                "query_id",
                "raw_candidate_count",
                "in_raw_top50",
                "best_raw_rank",
                "in_optimized_top10",
                "best_optimized_rank",
                "coverage_status",
            ]
        ],
        on="query_id",
        how="left",
    )
    frame = frame.merge(
        hit[
            [
                "query_id",
                "hit_at_1",
                "hit_at_3",
                "hit_at_5",
                "hit_at_10",
                "best_hit_rank",
                "recommended_top1",
                "recommended_top3",
                "reason_estimate",
            ]
        ],
        on="query_id",
        how="left",
    )
    for column in ["in_raw_top50", "in_optimized_top10", "hit_at_1", "hit_at_3", "hit_at_5", "hit_at_10"]:
        frame[column] = bool_series(frame[column]).fillna(False)
    return frame


def summarize_missing_by_group(frame: pd.DataFrame, group_column: str) -> pd.DataFrame:
    total = frame.groupby(group_column, dropna=False).size().rename("total_gold_count")
    missing = (
        frame.loc[~frame["in_raw_top50"]]
        .groupby(group_column, dropna=False)
        .size()
        .rename("missing_count")
    )
    hit10 = (
        frame.loc[frame["hit_at_10"]]
        .groupby(group_column, dropna=False)
        .size()
        .rename("hit_at_10_count")
    )
    summary = pd.concat([total, missing, hit10], axis=1).fillna(0).reset_index()
    summary["total_gold_count"] = summary["total_gold_count"].astype(int)
    summary["missing_count"] = summary["missing_count"].astype(int)
    summary["hit_at_10_count"] = summary["hit_at_10_count"].astype(int)
    summary["missing_ratio_among_group"] = summary["missing_count"] / summary["total_gold_count"]
    summary["raw_coverage_count"] = summary["total_gold_count"] - summary["missing_count"]
    summary["raw_coverage_rate"] = summary["raw_coverage_count"] / summary["total_gold_count"]
    summary["hit_at_10_rate"] = summary["hit_at_10_count"] / summary["total_gold_count"]
    return summary.sort_values(["missing_count", "total_gold_count"], ascending=[False, False])


def build_missing_by_place_type(frame: pd.DataFrame) -> pd.DataFrame:
    summary = summarize_missing_by_group(frame, "place_type")
    total_missing = int((~frame["in_raw_top50"]).sum())
    summary["missing_ratio_among_missing"] = summary["missing_count"] / total_missing if total_missing else 0.0
    summary["candidate_generation_gap"] = summary["place_type"].map(
        lambda value: PLACE_TYPE_RECOMMENDATIONS.get(str(value), "해당 유형에 맞는 외부 POI/공공데이터 후보군 보강 필요")
    )
    return summary[
        [
            "place_type",
            "total_gold_count",
            "missing_count",
            "missing_ratio_among_group",
            "missing_ratio_among_missing",
            "raw_coverage_count",
            "raw_coverage_rate",
            "hit_at_10_count",
            "hit_at_10_rate",
            "candidate_generation_gap",
        ]
    ]


def build_missing_by_district(frame: pd.DataFrame) -> pd.DataFrame:
    summary = summarize_missing_by_group(frame, "district")
    total_missing = int((~frame["in_raw_top50"]).sum())
    summary["missing_ratio_among_missing"] = summary["missing_count"] / total_missing if total_missing else 0.0
    summary["diagnosis"] = summary.apply(
        lambda row: "후보군 coverage 취약 자치구" if row["missing_ratio_among_group"] >= 0.75 else "일부 장소 유형 보강 필요",
        axis=1,
    )
    return summary[
        [
            "district",
            "total_gold_count",
            "missing_count",
            "missing_ratio_among_group",
            "missing_ratio_among_missing",
            "raw_coverage_count",
            "raw_coverage_rate",
            "hit_at_10_count",
            "hit_at_10_rate",
            "diagnosis",
        ]
    ]


def build_hit_vs_miss_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for group_level, column in [
        ("overall", None),
        ("place_type", "place_type"),
        ("district", "district"),
        ("campaign_activity_type", "campaign_activity_type"),
    ]:
        if column is None:
            groups = [("ALL", frame)]
        else:
            groups = list(frame.groupby(column, dropna=False))

        for group_value, group in groups:
            total = len(group)
            covered = int(group["in_raw_top50"].sum())
            hit1 = int(group["hit_at_1"].sum())
            hit3 = int(group["hit_at_3"].sum())
            hit5 = int(group["hit_at_5"].sum())
            hit10 = int(group["hit_at_10"].sum())
            rows.append(
                {
                    "group_level": group_level,
                    "group_value": group_value,
                    "query_count": total,
                    "raw_covered_count": covered,
                    "raw_missing_count": total - covered,
                    "raw_coverage_rate": covered / total if total else 0.0,
                    "hit_at_1_count": hit1,
                    "hit_at_3_count": hit3,
                    "hit_at_5_count": hit5,
                    "hit_at_10_count": hit10,
                    "hit_at_10_rate": hit10 / total if total else 0.0,
                    "avg_raw_candidate_count": group["raw_candidate_count"].mean(),
                    "diagnosis": diagnose_group(group),
                }
            )
    return pd.DataFrame(rows).sort_values(["group_level", "raw_missing_count", "query_count"], ascending=[True, False, False])


def diagnose_group(group: pd.DataFrame) -> str:
    coverage_rate = group["in_raw_top50"].mean() if len(group) else 0.0
    hit_rate = group["hit_at_10"].mean() if len(group) else 0.0
    if coverage_rate < 0.3:
        return "candidate generation 병목이 큼"
    if coverage_rate >= 0.3 and hit_rate < coverage_rate:
        return "후보는 있으나 reranking 또는 명칭 매칭 개선 여지"
    return "후보군 coverage와 reranking이 상대적으로 양호"


def build_candidate_generation_diagnosis(frame: pd.DataFrame) -> pd.DataFrame:
    total = len(frame)
    missing = int((~frame["in_raw_top50"]).sum())
    covered = int(frame["in_raw_top50"].sum())
    hit10 = int(frame["hit_at_10"].sum())

    rows = [
        {
            "diagnosis_category": "overall",
            "metric": "total_queries",
            "value": total,
            "ratio": 1.0,
            "interpretation": "strong positive Gold query 전체 수",
            "recommendation": "동일 query set을 유지해 모델별 비교 재현성 확보",
        },
        {
            "diagnosis_category": "overall",
            "metric": "raw_candidate_missing_queries",
            "value": missing,
            "ratio": missing / total if total else 0.0,
            "interpretation": "정답 장소가 raw Top50 후보군에 없어 reranking으로 맞출 수 없는 query",
            "recommendation": "candidate generation 단계의 장소 소스 확장과 alias 정규화가 우선 필요",
        },
        {
            "diagnosis_category": "overall",
            "metric": "raw_candidate_recall_at_50",
            "value": covered,
            "ratio": covered / total if total else 0.0,
            "interpretation": "raw 후보군 Top50 안에 정답 장소가 존재하는 비율",
            "recommendation": "R@10 상한을 높이려면 raw recall@50 자체를 개선해야 함",
        },
        {
            "diagnosis_category": "overall",
            "metric": "optimized_hit_at_10",
            "value": hit10,
            "ratio": hit10 / total if total else 0.0,
            "interpretation": "optimized reranking 후 Top10 hit 수",
            "recommendation": "현재 covered query는 모두 Top10에 진입해 reranking보다 후보 생성이 병목",
        },
    ]

    for _, row in summarize_missing_by_group(frame, "campaign_activity_type").head(10).iterrows():
        rows.append(
            {
                "diagnosis_category": "missing_by_campaign_activity_type",
                "metric": row["campaign_activity_type"],
                "value": int(row["missing_count"]),
                "ratio": float(row["missing_ratio_among_group"]),
                "interpretation": f"{row['campaign_activity_type']} 유형에서 raw 후보 누락이 발생",
                "recommendation": "일정 유형별 전용 후보 source를 추가하고 장소명 alias를 보강",
            }
        )

    for _, row in build_missing_by_place_type(frame).head(10).iterrows():
        rows.append(
            {
                "diagnosis_category": "missing_by_place_type",
                "metric": row["place_type"],
                "value": int(row["missing_count"]),
                "ratio": float(row["missing_ratio_among_group"]),
                "interpretation": f"{row['place_type']} 장소 유형의 raw 후보 coverage 한계",
                "recommendation": row["candidate_generation_gap"],
            }
        )
    return pd.DataFrame(rows)


def run(gold_path: Path, coverage_path: Path, hit_path: Path, raw_path: Path, output_dir: Path) -> None:
    gold = read_csv(gold_path, "gold evaluation queries")
    coverage = read_csv(coverage_path, "raw candidate coverage")
    hit = read_csv(hit_path, "hit analysis")
    _ = read_csv(raw_path, "raw baseline recommendations")

    frame = build_analysis_frame(gold, coverage, hit)
    output_dir.mkdir(parents=True, exist_ok=True)

    diagnosis = build_candidate_generation_diagnosis(frame)
    missing_place_type = build_missing_by_place_type(frame)
    missing_district = build_missing_by_district(frame)
    hit_vs_miss = build_hit_vs_miss_summary(frame)

    diagnosis.to_csv(output_dir / "candidate_generation_diagnosis.csv", index=False, encoding="utf-8-sig")
    missing_place_type.to_csv(output_dir / "missing_gold_by_place_type.csv", index=False, encoding="utf-8-sig")
    missing_district.to_csv(output_dir / "missing_gold_by_district.csv", index=False, encoding="utf-8-sig")
    hit_vs_miss.to_csv(output_dir / "hit_vs_miss_summary.csv", index=False, encoding="utf-8-sig")

    print("=== candidate generation diagnosis ===")
    print(f"total queries: {len(frame)}")
    print(f"missing from raw Top50: {(~frame['in_raw_top50']).sum()}")
    print(f"raw recall@50: {frame['in_raw_top50'].mean():.4f}")
    print(f"hit@10: {frame['hit_at_10'].mean():.4f}")
    print("\nMissing by place_type")
    print(missing_place_type[["place_type", "total_gold_count", "missing_count", "raw_coverage_rate"]].to_string(index=False))
    print("\nMissing by campaign_activity_type")
    print(
        summarize_missing_by_group(frame, "campaign_activity_type")[
            ["campaign_activity_type", "total_gold_count", "missing_count", "raw_coverage_rate"]
        ].to_string(index=False)
    )


def main() -> int:
    args = parse_args()
    try:
        run(Path(args.gold), Path(args.coverage), Path(args.hit), Path(args.raw), Path(args.output_dir))
    except (FileNotFoundError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
