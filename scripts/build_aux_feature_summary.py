# Reads:
# - data/processed/cleaned_commercial_flow.csv
# - data/processed/cleaned_worker_population.csv
# - data/processed/cleaned_living_population.csv
# Writes:
# - data/processed/aux_feature_summary.json

import json
from pathlib import Path

import pandas as pd


def load_csv(file_path: Path) -> pd.DataFrame:
    return pd.read_csv(file_path, encoding="utf-8-sig")


def numeric_series(dataframe: pd.DataFrame, column_name: str) -> pd.Series:
    return pd.to_numeric(dataframe[column_name], errors="coerce").fillna(0.0)


def build_stat_block(summary: dict, prefix: str, series: pd.Series) -> None:
    summary[f"{prefix}_mean"] = float(series.mean())
    summary[f"{prefix}_min"] = float(series.min())
    summary[f"{prefix}_max"] = float(series.max())


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    processed_dir = project_root / "data" / "processed"

    commercial_path = processed_dir / "cleaned_commercial_flow.csv"
    worker_path = processed_dir / "cleaned_worker_population.csv"
    living_path = processed_dir / "cleaned_living_population.csv"
    output_path = processed_dir / "aux_feature_summary.json"

    commercial_df = load_csv(commercial_path)
    worker_df = load_csv(worker_path)
    living_df = load_csv(living_path)

    summary: dict[str, float] = {}

    build_stat_block(
        summary,
        "commercial_age_20_40_ratio",
        numeric_series(commercial_df, "age_20_40_ratio"),
    )
    build_stat_block(
        summary,
        "commercial_age_60_plus_ratio",
        numeric_series(commercial_df, "age_60_plus_ratio"),
    )
    build_stat_block(
        summary,
        "commercial_morning_flow_score",
        numeric_series(commercial_df, "morning_flow_score"),
    )
    build_stat_block(
        summary,
        "commercial_afternoon_flow_score",
        numeric_series(commercial_df, "afternoon_flow_score"),
    )
    build_stat_block(
        summary,
        "worker_age_20_40_ratio",
        numeric_series(worker_df, "age_20_40_worker_ratio"),
    )
    build_stat_block(
        summary,
        "worker_age_60_plus_ratio",
        numeric_series(worker_df, "age_60_plus_worker_ratio"),
    )
    build_stat_block(
        summary,
        "living_pop_20_40_ratio",
        numeric_series(living_df, "age_20_40_ratio"),
    )
    build_stat_block(
        summary,
        "living_pop_60_plus_ratio",
        numeric_series(living_df, "age_60_plus_ratio"),
    )
    build_stat_block(
        summary,
        "living_pop_morning_score",
        numeric_series(living_df, "morning_score"),
    )
    build_stat_block(
        summary,
        "living_pop_afternoon_score",
        numeric_series(living_df, "afternoon_score"),
    )

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)

    print(f"Saved aux feature summary: {output_path}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
