"""Validate whether alias-based candidate expansion overfits the Gold Set.

This script does not change the production outputs.  It reads the public-only
and alias-expanded experiment artifacts, classifies alias rows, measures Top10
hit contribution by alias candidates, and runs leave-one-place-type-out
ablation with the already selected improved weights.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from evaluate_recommendations import evaluate, place_match_method, read_csv_with_fallback  # noqa: E402
from optimize_reranking_weights import (  # noqa: E402
    add_feature_values,
    add_match_labels,
    build_raw_candidate_coverage,
    rerank_candidates,
    summary_metrics,
)
from place_aliases import normalize_place_key  # noqa: E402


METRICS = ["P@1", "P@3", "P@5", "P@10", "R@1", "R@3", "R@5", "R@10", "NDCG@1", "NDCG@3", "NDCG@5", "NDCG@10"]
K_VALUES = [1, 3, 5, 10]
LEAVE_OUT_TYPES = ["전통시장", "공원", "교통거점", "복지시설"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate alias expansion against possible Gold Set leakage.")
    parser.add_argument("--gold", default="output/gold_set_evaluation_queries.csv")
    parser.add_argument("--alias", default="data/processed/place_aliases.csv")
    parser.add_argument("--public_raw", default="output/raw_baseline_recommendations.csv")
    parser.add_argument("--expanded_raw", default="output/improved/raw_baseline_recommendations.csv")
    parser.add_argument("--public_optimized_dir", default="output/improved/before_recomputed/experiments_optimized")
    parser.add_argument("--expanded_optimized_dir", default="output/improved/experiments_optimized")
    parser.add_argument("--output_dir", default="output/improved/alias_validation")
    parser.add_argument("--report", default="docs/alias_expansion_validation_report.md")
    return parser.parse_args()


def read_csv(path: Path) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(path, encoding=encoding, dtype=str, keep_default_na=False)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def clean_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin(["true", "1", "yes"])


def to_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def similarity(left: object, right: object) -> float:
    left_key = normalize_place_key(left)
    right_key = normalize_place_key(right)
    if not left_key or not right_key:
        return 0.0
    if left_key == right_key:
        return 1.0
    return SequenceMatcher(None, left_key, right_key).ratio()


def near_same(left: object, right: object) -> bool:
    left_key = normalize_place_key(left)
    right_key = normalize_place_key(right)
    if not left_key or not right_key:
        return False
    if left_key == right_key:
        return True
    if min(len(left_key), len(right_key)) >= 4 and (left_key in right_key or right_key in left_key):
        return True
    return similarity(left_key, right_key) >= 0.90


def load_public_poi_keys(root: Path) -> dict[str, set[str]]:
    sources: dict[str, tuple[str, str]] = {
        "market": ("cleaned_market.csv", "market_name"),
        "park": ("cleaned_parks.csv", "park_name"),
        "senior": ("cleaned_senior.csv", "facility_name"),
        "subway": ("cleaned_subway.csv", "station_name"),
    }
    public_keys: dict[str, set[str]] = {}
    processed_dir = root / "data" / "processed"
    for label, (file_name, column) in sources.items():
        path = processed_dir / file_name
        if not path.exists():
            public_keys[label] = set()
            continue
        frame = read_csv(path)
        public_keys[label] = {normalize_place_key(value) for value in frame.get(column, pd.Series(dtype=str))}
        public_keys[label].discard("")
    return public_keys


def public_source_matches(row: pd.Series, public_keys: dict[str, set[str]]) -> list[str]:
    keys = {normalize_place_key(row.get("canonical_name")), normalize_place_key(row.get("alias_name"))}
    keys.discard("")
    matches: list[str] = []
    for source_name, source_keys in public_keys.items():
        if keys.intersection(source_keys):
            matches.append(source_name)
    return sorted(matches)


def classify_alias_rows(alias: pd.DataFrame, gold: pd.DataFrame, public_keys: dict[str, set[str]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row_id, row in alias.reset_index(drop=True).iterrows():
        gold_matches: list[dict[str, Any]] = []
        for _, gold_row in gold.iterrows():
            exact_or_near = near_same(row.get("alias_name"), gold_row.get("place_name")) or near_same(
                row.get("canonical_name"),
                gold_row.get("place_name"),
            )
            if exact_or_near:
                gold_matches.append(
                    {
                        "query_id": clean_text(gold_row.get("query_id")),
                        "place_name": clean_text(gold_row.get("place_name")),
                        "place_type": clean_text(gold_row.get("place_type")),
                        "alias_similarity": max(
                            similarity(row.get("alias_name"), gold_row.get("place_name")),
                            similarity(row.get("canonical_name"), gold_row.get("place_name")),
                        ),
                    }
                )

        source_matches = public_source_matches(row, public_keys)
        alias_name = clean_text(row.get("alias_name"))
        canonical_name = clean_text(row.get("canonical_name"))
        note = clean_text(row.get("note")).lower()
        labels: list[str] = []
        evidence: list[str] = []

        if source_matches:
            labels.append("public_poi_alias")
            evidence.append(f"matches public source(s): {', '.join(source_matches)}")
        if any(token in alias_name for token in ["출구", "역", "사거리"]) or "station" in note:
            labels.append("station_exit_alias")
            evidence.append("station/exit/intersection expression")
        if any(token in alias_name for token in ["광장", "팔각정", "공원", "수변", "폭포", "동산", "차고지", "체육관", "운동장"]):
            labels.append("district_landmark_alias")
            evidence.append("landmark or public facility expression")
        if canonical_name != alias_name and normalize_place_key(canonical_name) != normalize_place_key(alias_name):
            labels.append("common_name_alias")
            evidence.append("canonical and alias names differ")
        if clean_text(row.get("source")) == "manual_alias_seed":
            labels.append("manual_seed")
            evidence.append("source=manual_alias_seed")
        if gold_matches:
            labels.append("gold_specific_alias 의심")
            evidence.append(
                "near/exact Gold place match: "
                + "; ".join(f"{item['query_id']}:{item['place_name']}" for item in gold_matches[:3])
            )

        single_gold_specific = bool(gold_matches) and len(gold_matches) == 1 and not source_matches
        if single_gold_specific:
            evidence.append("single Gold query match with no public POI source match")

        primary_class = "manual_seed"
        for preferred in [
            "gold_specific_alias 의심",
            "public_poi_alias",
            "station_exit_alias",
            "district_landmark_alias",
            "common_name_alias",
            "manual_seed",
        ]:
            if preferred in labels:
                primary_class = preferred
                break

        rows.append(
            {
                "alias_row_id": row_id + 1,
                "canonical_name": canonical_name,
                "alias_name": alias_name,
                "district": clean_text(row.get("district")),
                "place_type": clean_text(row.get("place_type")),
                "source": clean_text(row.get("source")),
                "note": clean_text(row.get("note")),
                "primary_class": primary_class,
                "all_labels": ";".join(dict.fromkeys(labels)),
                "public_source_matches": ";".join(source_matches),
                "gold_match_count": len(gold_matches),
                "matched_gold_query_ids": ";".join(item["query_id"] for item in gold_matches),
                "matched_gold_place_names": ";".join(item["place_name"] for item in gold_matches),
                "max_gold_similarity": max([item["alias_similarity"] for item in gold_matches], default=0.0),
                "single_query_gold_specific_suspect": single_gold_specific,
                "evidence": " | ".join(evidence),
            }
        )
    return pd.DataFrame(rows)


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
        if metric in converted.columns:
            converted[metric] = pd.to_numeric(converted[metric], errors="coerce").fillna(0.0)
    return converted


def get_model_metrics(comparison_path: Path, model_name: str) -> dict[str, float]:
    frame = metric_columns(read_csv(comparison_path))
    row = frame[frame["model_name"].astype(str).eq(model_name)]
    if row.empty:
        return {metric: 0.0 for metric in METRICS}
    record = row.iloc[0]
    return {metric: float(record.get(metric, 0.0)) for metric in METRICS}


def coverage_metrics(coverage: pd.DataFrame) -> dict[str, float]:
    in_raw = bool_series(coverage["in_raw_top50"])
    in_top10 = bool_series(coverage["in_optimized_top10"])
    return {
        "raw_recall@50": float(in_raw.mean()) if len(in_raw) else 0.0,
        "missing_count": float((~in_raw).sum()),
        "hit@10_count": float(in_top10.sum()),
        "hit@10_rate": float(in_top10.mean()) if len(in_top10) else 0.0,
    }


def build_performance_split(public_dir: Path, expanded_dir: Path) -> pd.DataFrame:
    public_metrics = get_model_metrics(public_dir / "model_comparison_optimized.csv", "optimized_proposed")
    expanded_metrics = get_model_metrics(expanded_dir / "model_comparison_optimized.csv", "optimized_proposed")
    rows: list[dict[str, Any]] = []
    for metric in METRICS:
        public_value = public_metrics[metric]
        expanded_value = expanded_metrics[metric]
        rows.append(
            {
                "metric": metric,
                "public_only": public_value,
                "alias_expanded": expanded_value,
                "alias_only_contribution": expanded_value - public_value,
            }
        )
    return pd.DataFrame(rows)


def row_key(row: pd.Series) -> tuple[str, str, str, str]:
    return (
        clean_text(row.get("query_id")),
        clean_text(row.get("recommended_place_name")),
        clean_text(row.get("recommended_district")),
        clean_text(row.get("recommended_place_type")),
    )


def candidate_source_lookup(raw: pd.DataFrame) -> dict[tuple[str, str, str, str], str]:
    lookup: dict[tuple[str, str, str, str], str] = {}
    for _, row in raw.iterrows():
        lookup[row_key(row)] = clean_text(row.get("candidate_source"))
    return lookup


def first_top10_match(rec_rows: pd.DataFrame, gold_rows: pd.DataFrame) -> dict[str, Any] | None:
    for _, rec in rec_rows[rec_rows["rank"].astype(int).le(10)].sort_values("rank").iterrows():
        for _, gold_row in gold_rows.iterrows():
            method = place_match_method(rec, gold_row)
            if method is not None:
                return {
                    "rank": int(rec["rank"]),
                    "recommended_place_name": clean_text(rec.get("recommended_place_name")),
                    "recommended_district": clean_text(rec.get("recommended_district")),
                    "recommended_place_type": clean_text(rec.get("recommended_place_type")),
                    "method": method,
                    "gold_place_name": clean_text(gold_row.get("place_name")),
                }
    return None


def build_alias_hit_contribution(
    gold: pd.DataFrame,
    expanded_raw: pd.DataFrame,
    public_hit: pd.DataFrame,
    expanded_recommendations: pd.DataFrame,
) -> pd.DataFrame:
    source_by_key = candidate_source_lookup(expanded_raw)
    public_hit_map = {
        clean_text(row["query_id"]): str(row["hit_at_10"]).lower() in {"true", "1", "yes"}
        for _, row in public_hit.iterrows()
    }
    rec_by_query = {
        clean_text(query_id): group.copy()
        for query_id, group in expanded_recommendations.groupby("query_id", sort=False)
    }

    rows: list[dict[str, Any]] = []
    for query_id, gold_rows in gold.groupby("query_id", sort=False):
        query_id = clean_text(query_id)
        match = first_top10_match(rec_by_query.get(query_id, expanded_recommendations.iloc[0:0]), gold_rows)
        public_already_hit = public_hit_map.get(query_id, False)
        if match is None:
            rows.append(
                {
                    "query_id": query_id,
                    "after_hit_at_10": False,
                    "public_only_hit_at_10": public_already_hit,
                    "contribution_category": "not_hit_after_expansion",
                    "matched_rank": "",
                    "matched_place_name": "",
                    "matched_source": "",
                    "matched_method": "",
                    "gold_place_name": clean_text(gold_rows.iloc[0].get("place_name")),
                }
            )
            continue

        key = (
            query_id,
            match["recommended_place_name"],
            match["recommended_district"],
            match["recommended_place_type"],
        )
        source = source_by_key.get(key, "")
        is_alias = source.startswith("alias_table")
        if public_already_hit:
            category = "public_candidate_already_hit"
        elif is_alias:
            category = "new_hit_from_alias_candidate"
        else:
            category = "new_hit_from_public_candidate_or_matching_change"

        rows.append(
            {
                "query_id": query_id,
                "after_hit_at_10": True,
                "public_only_hit_at_10": public_already_hit,
                "contribution_category": category,
                "matched_rank": match["rank"],
                "matched_place_name": match["recommended_place_name"],
                "matched_source": source,
                "matched_method": match["method"],
                "gold_place_name": match["gold_place_name"],
            }
        )
    return pd.DataFrame(rows)


def load_best_weights(path: Path) -> dict[str, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    weights = payload.get("best_weights", {})
    return {key: float(value) for key, value in weights.items()}


def evaluate_raw_with_weights(gold: pd.DataFrame, raw: pd.DataFrame, weights: dict[str, float]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    prepared = raw.copy()
    prepared["baseline_score"] = pd.to_numeric(prepared["baseline_score"], errors="coerce").fillna(0.0)
    prepared["raw_rank"] = pd.to_numeric(prepared["raw_rank"], errors="coerce").fillna(999999)
    featured = add_match_labels(add_feature_values(prepared), gold)
    recommendations = rerank_candidates(featured, weights, top_k=10)
    detail, summary = evaluate(gold, recommendations, K_VALUES)
    coverage = build_raw_candidate_coverage(gold, prepared, recommendations)
    return recommendations, detail, summary, coverage


def build_leave_one_type_out(
    gold: pd.DataFrame,
    expanded_raw: pd.DataFrame,
    weights: dict[str, float],
    output_dir: Path,
) -> pd.DataFrame:
    baseline_recs, _, baseline_summary, baseline_coverage = evaluate_raw_with_weights(gold, expanded_raw, weights)
    _ = baseline_recs
    baseline_metrics = summary_metrics(baseline_summary)
    baseline_coverage_metrics = coverage_metrics(baseline_coverage)

    rows: list[dict[str, Any]] = [
        {
            "ablation": "alias_expanded_all",
            "removed_place_type": "",
            "raw_recall@50": baseline_coverage_metrics["raw_recall@50"],
            "missing_count": baseline_coverage_metrics["missing_count"],
            "R@10": baseline_metrics.get("R@10", 0.0),
            "NDCG@10": baseline_metrics.get("NDCG@10", 0.0),
            "P@1": baseline_metrics.get("P@1", 0.0),
            "delta_raw_recall@50": 0.0,
            "delta_R@10": 0.0,
            "delta_NDCG@10": 0.0,
        }
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    baseline_coverage.to_csv(output_dir / "leave_out_all_coverage.csv", index=False, encoding="utf-8-sig")

    for place_type in LEAVE_OUT_TYPES:
        mask_remove = expanded_raw["candidate_source"].astype(str).str.startswith("alias_table") & expanded_raw[
            "place_type"
        ].astype(str).eq(place_type)
        filtered_raw = expanded_raw.loc[~mask_remove].copy()
        _, _, summary, coverage = evaluate_raw_with_weights(gold, filtered_raw, weights)
        metrics = summary_metrics(summary)
        coverage_stat = coverage_metrics(coverage)
        safe_name = re.sub(r"[^0-9A-Za-z가-힣_]+", "_", place_type)
        coverage.to_csv(output_dir / f"leave_out_{safe_name}_coverage.csv", index=False, encoding="utf-8-sig")
        rows.append(
            {
                "ablation": f"remove_{place_type}_alias",
                "removed_place_type": place_type,
                "raw_recall@50": coverage_stat["raw_recall@50"],
                "missing_count": coverage_stat["missing_count"],
                "R@10": metrics.get("R@10", 0.0),
                "NDCG@10": metrics.get("NDCG@10", 0.0),
                "P@1": metrics.get("P@1", 0.0),
                "delta_raw_recall@50": coverage_stat["raw_recall@50"] - baseline_coverage_metrics["raw_recall@50"],
                "delta_R@10": metrics.get("R@10", 0.0) - baseline_metrics.get("R@10", 0.0),
                "delta_NDCG@10": metrics.get("NDCG@10", 0.0) - baseline_metrics.get("NDCG@10", 0.0),
            }
        )
    return pd.DataFrame(rows)


def markdown_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_No rows._"
    table = frame.copy()
    if columns is not None:
        table = table[columns]
    if max_rows is not None:
        table = table.head(max_rows)

    headers = [str(column) for column in table.columns]
    rows = []
    for _, row in table.iterrows():
        rows.append([str(row[column]).replace("\n", " ").replace("|", "\\|") for column in table.columns])

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def top_rows_markdown(frame: pd.DataFrame, columns: list[str], max_rows: int = 12) -> str:
    return markdown_table(frame, columns=columns, max_rows=max_rows)


def metric_value(frame: pd.DataFrame, metric: str, column: str) -> float:
    row = frame[frame["metric"].eq(metric)]
    if row.empty:
        return 0.0
    return float(row.iloc[0][column])


def build_report(
    report_path: Path,
    alias_classification: pd.DataFrame,
    gold_specific: pd.DataFrame,
    single_query_suspects: pd.DataFrame,
    performance_split: pd.DataFrame,
    contribution: pd.DataFrame,
    contribution_summary: pd.DataFrame,
    leave_out: pd.DataFrame,
) -> None:
    class_counts = alias_classification["primary_class"].value_counts().rename_axis("primary_class").reset_index(name="count")
    label_counts = (
        alias_classification["all_labels"]
        .str.get_dummies(sep=";")
        .sum()
        .sort_values(ascending=False)
        .rename_axis("label")
        .reset_index(name="count")
    )

    total_alias_rows = len(alias_classification)
    gold_specific_count = int(alias_classification["gold_match_count"].astype(int).gt(0).sum())
    single_query_count = int(alias_classification["single_query_gold_specific_suspect"].astype(bool).sum())

    total_after_hits = int(contribution["after_hit_at_10"].astype(bool).sum())
    new_alias_hits = int(contribution["contribution_category"].eq("new_hit_from_alias_candidate").sum())
    public_hits = int(contribution["contribution_category"].eq("public_candidate_already_hit").sum())
    other_new_hits = int(contribution["contribution_category"].eq("new_hit_from_public_candidate_or_matching_change").sum())

    public_r10 = metric_value(performance_split, "R@10", "public_only")
    expanded_r10 = metric_value(performance_split, "R@10", "alias_expanded")
    public_ndcg = metric_value(performance_split, "NDCG@10", "public_only")
    expanded_ndcg = metric_value(performance_split, "NDCG@10", "alias_expanded")
    public_p1 = metric_value(performance_split, "P@1", "public_only")
    expanded_p1 = metric_value(performance_split, "P@1", "alias_expanded")

    high_risk_note = (
        "과적합 가능성이 높다"
        if single_query_count / total_alias_rows >= 0.30
        else "과적합 가능성이 존재한다"
    )

    content = f"""# Alias Expansion Validation Report

생성일: 2026-05-22

## 1. 검증 목적

이 문서는 alias 기반 후보군 확장이 실제로 공공데이터와 일정표 사이의 명칭 불일치를 줄인 것인지, 또는 Gold Set 정답을 과도하게 주입한 것인지 검증한다. 결론부터 말하면, alias expansion은 성능을 크게 높였지만 현재 alias table은 수작업 seed와 Gold place name에 매우 가까운 row가 많아 **{high_risk_note}**. 논문에는 성능 개선 수치를 쓰되, "Gold Set 확장 후 재검증 필요"를 명시해야 한다.

## 2. Alias Row 분류 결과

총 alias row 수는 {total_alias_rows}개다. Gold place_name과 완전 동일하거나 거의 동일한 row는 {gold_specific_count}개이고, 공공 POI source에서 직접 확인되지 않으면서 단일 Gold query와만 강하게 매칭되는 의심 row는 {single_query_count}개다.

### Primary Class Count

{markdown_table(class_counts)}

### Multi-label Count

{markdown_table(label_counts)}

## 3. Gold-specific Alias 의심 목록

아래 row는 alias_name 또는 canonical_name이 Gold Set의 place_name과 거의 같다. 이 자체가 모두 잘못은 아니다. 실제 장소명을 normalization table에 넣을 수는 있다. 그러나 현재처럼 같은 Gold query를 맞추기 위해 수작업으로 들어간 흔적이 강하면 평가 성능이 낙관적으로 측정될 수 있다.

{top_rows_markdown(gold_specific, ["alias_row_id", "canonical_name", "alias_name", "place_type", "matched_gold_query_ids", "matched_gold_place_names", "public_source_matches", "max_gold_similarity"], 25)}

## 4. 단일 Gold Query 주입 의심 목록

다음 row는 public source match가 없고 단일 Gold query와만 거의 동일하게 매칭된다. 논문에는 이 row들을 포함한 성능을 "최종 일반화 성능"으로 주장하기보다 "coverage bottleneck을 확인하기 위한 alias-expanded candidate experiment"로 해석하는 것이 안전하다.

{top_rows_markdown(single_query_suspects, ["alias_row_id", "canonical_name", "alias_name", "place_type", "matched_gold_query_ids", "matched_gold_place_names", "evidence"], 30)}

## 5. Public-only vs Alias-expanded 성능

public-only는 alias 후보를 제외하고 기존 공공데이터 후보만 사용한 결과이며, alias-expanded는 alias 후보를 포함한 결과다.

{markdown_table(performance_split[performance_split["metric"].isin(["P@1", "P@3", "P@10", "R@10", "NDCG@10"])])}

핵심 변화는 P@1 {public_p1:.4f} -> {expanded_p1:.4f}, R@10 {public_r10:.4f} -> {expanded_r10:.4f}, NDCG@10 {public_ndcg:.4f} -> {expanded_ndcg:.4f}이다. 이 변화는 candidate generation coverage 개선 효과를 보여주지만, alias table의 Gold-specific 성격 때문에 일반화 성능으로는 보수적으로 해석해야 한다.

## 6. Top10 Hit Contribution

after optimized Top10 hit 전체는 {total_after_hits}개다. 이 중 기존 public-only optimized에서도 맞춘 hit는 {public_hits}개이고, public-only에서는 못 맞췄지만 alias 후보가 Top10에서 맞춘 새 hit는 {new_alias_hits}개다. 기타 public/matching 변화로 분류된 새 hit는 {other_new_hits}개다.

{markdown_table(contribution_summary)}

### Alias로 새로 맞춘 예시

{top_rows_markdown(contribution[contribution["contribution_category"].eq("new_hit_from_alias_candidate")], ["query_id", "gold_place_name", "matched_place_name", "matched_rank", "matched_source", "matched_method"], 20)}

## 7. Leave-One-Place-Type-Out 검증

아래 ablation은 after optimized best weights를 고정한 상태에서 특정 place_type alias 후보만 제거한 결과다. 따라서 weight 재탐색 효과가 아니라 candidate coverage 제거 효과를 본다.

{markdown_table(leave_out)}

전통시장 alias 제거는 영향이 상대적으로 작고, 공원 alias 제거는 raw recall@50과 R@10을 크게 낮춘다. 이는 공원/하천/산책로 계열이 기존 public candidate source에서 매우 부족했음을 의미한다. 복지시설과 교통거점도 alias 의존도가 확인된다.

## 8. 결론

1. Alias expansion은 public-only 대비 R@10과 NDCG@10을 크게 높였다.
2. 그러나 alias table의 상당수가 Gold place_name과 거의 동일하고, 일부는 단일 Gold query만을 겨냥한 것처럼 보인다.
3. 따라서 alias-expanded 결과는 "후보군 coverage 개선 시 성능 상한이 크게 올라간다"는 병목 검증 결과로 사용하는 것이 타당하다.
4. 논문 최종 성능으로는 public-only 결과와 alias-expanded 결과를 함께 제시하고, alias-expanded는 Gold Set 확장 전의 보강 실험으로 명시해야 한다.

## 9. 논문에 쓸 수 있는 보수적 해석 문장

Alias 확장은 실제 후보 일정표에 기록된 장소명과 공공데이터 후보명 사이의 표기 차이, 출입구 표현, 광장·산책로·상권명 표현 차이를 줄이기 위한 정규화 방법이다. 실험 결과 alias-expanded candidate pool에서 raw candidate recall@50과 R@10이 크게 상승하여, 본 시스템의 주요 병목이 reranking보다 candidate generation coverage에 있음을 확인하였다. 다만 현재 alias table은 수작업 seed이며 일부 row가 Gold Set 장소명과 매우 유사하므로, 해당 결과를 일반화 성능으로 단정하기보다는 coverage bottleneck을 확인하는 보강 실험으로 해석해야 한다. 향후 추가 후보자와 기간의 Gold Set을 구축한 뒤 동일한 alias 규칙을 고정한 상태에서 재평가하여 과적합 가능성을 검증할 필요가 있다.

## 10. 산출물

- Alias row classification: `output/improved/alias_validation/alias_row_classification.csv`
- Gold-specific suspects: `output/improved/alias_validation/gold_specific_alias_suspects.csv`
- Single-query suspects: `output/improved/alias_validation/single_query_gold_specific_suspects.csv`
- Performance split: `output/improved/alias_validation/performance_public_vs_alias.csv`
- Hit contribution: `output/improved/alias_validation/alias_hit_contribution.csv`
- Leave-one-type-out: `output/improved/alias_validation/leave_one_place_type_out.csv`
"""

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(content, encoding="utf-8-sig")


def run(args: argparse.Namespace) -> None:
    gold = read_csv_with_fallback(Path(args.gold), "Gold evaluation queries")
    alias = read_csv(Path(args.alias))
    public_raw = read_csv(Path(args.public_raw))
    expanded_raw = read_csv(Path(args.expanded_raw))
    public_hit = read_csv(Path(args.public_optimized_dir) / "optimized_proposed" / "hit_analysis.csv")
    expanded_recommendations = read_csv(Path(args.expanded_optimized_dir) / "optimized_proposed" / "recommendation_results.csv")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    public_keys = load_public_poi_keys(PROJECT_ROOT)
    alias_classification = classify_alias_rows(alias, gold, public_keys)
    gold_specific = alias_classification[alias_classification["gold_match_count"].astype(int).gt(0)].copy()
    single_query_suspects = alias_classification[
        alias_classification["single_query_gold_specific_suspect"].astype(bool)
    ].copy()
    performance_split = build_performance_split(Path(args.public_optimized_dir), Path(args.expanded_optimized_dir))
    contribution = build_alias_hit_contribution(gold, expanded_raw, public_hit, expanded_recommendations)
    contribution_summary = (
        contribution.groupby("contribution_category", as_index=False)
        .size()
        .rename(columns={"size": "query_count"})
        .sort_values("query_count", ascending=False)
    )

    weights = load_best_weights(Path(args.expanded_optimized_dir) / "best_weights.json")
    leave_out = build_leave_one_type_out(gold, expanded_raw, weights, output_dir)

    alias_classification.to_csv(output_dir / "alias_row_classification.csv", index=False, encoding="utf-8-sig")
    gold_specific.to_csv(output_dir / "gold_specific_alias_suspects.csv", index=False, encoding="utf-8-sig")
    single_query_suspects.to_csv(
        output_dir / "single_query_gold_specific_suspects.csv",
        index=False,
        encoding="utf-8-sig",
    )
    performance_split.to_csv(output_dir / "performance_public_vs_alias.csv", index=False, encoding="utf-8-sig")
    contribution.to_csv(output_dir / "alias_hit_contribution.csv", index=False, encoding="utf-8-sig")
    contribution_summary.to_csv(output_dir / "alias_hit_contribution_summary.csv", index=False, encoding="utf-8-sig")
    leave_out.to_csv(output_dir / "leave_one_place_type_out.csv", index=False, encoding="utf-8-sig")

    build_report(
        report_path=Path(args.report),
        alias_classification=alias_classification,
        gold_specific=gold_specific,
        single_query_suspects=single_query_suspects,
        performance_split=performance_split,
        contribution=contribution,
        contribution_summary=contribution_summary,
        leave_out=leave_out,
    )

    print("=== alias expansion validation ===")
    print(f"alias rows: {len(alias_classification)}")
    print(f"gold-specific suspect rows: {len(gold_specific)}")
    print(f"single-query suspect rows: {len(single_query_suspects)}")
    print(contribution_summary.to_string(index=False))
    print("\nPerformance split")
    print(performance_split[performance_split["metric"].isin(["P@1", "R@10", "NDCG@10"])].to_string(index=False))
    print("\nLeave-one-place-type-out")
    print(leave_out.to_string(index=False))
    print(f"\nSaved report: {args.report}")


def main() -> int:
    args = parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
