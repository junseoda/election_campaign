# Reads: data/서울시 상권분석서비스(직장인구-상권).csv
# Writes: data/processed/cleaned_worker_population.csv

from pathlib import Path

import pandas as pd


SOURCE_FILE = "서울시 상권분석서비스(직장인구-상권).csv"
OUTPUT_FILE = "cleaned_worker_population.csv"

RAW_COLUMNS = [
    "기준_년분기_코드",
    "상권_코드",
    "상권_코드_명",
    "총_직장_인구_수",
    "연령대_20_직장_인구_수",
    "연령대_30_직장_인구_수",
    "연령대_40_직장_인구_수",
    "연령대_60_이상_직장_인구_수",
]

COLUMN_MAPPING = {
    "기준_년분기_코드": "base_year_quarter_code",
    "상권_코드": "commercial_code",
    "상권_코드_명": "commercial_name",
    "총_직장_인구_수": "total_worker_population",
    "연령대_20_직장_인구_수": "age_20_worker_population",
    "연령대_30_직장_인구_수": "age_30_worker_population",
    "연령대_40_직장_인구_수": "age_40_worker_population",
    "연령대_60_이상_직장_인구_수": "age_60_plus_worker_population",
}

NUMERIC_COLUMNS = [
    "base_year_quarter_code",
    "commercial_code",
    "total_worker_population",
    "age_20_worker_population",
    "age_30_worker_population",
    "age_40_worker_population",
    "age_60_plus_worker_population",
]


def read_csv_with_fallback(file_path: Path, usecols: list[str]) -> pd.DataFrame:
    last_error = None

    for encoding in ("utf-8", "cp949"):
        try:
            return pd.read_csv(file_path, encoding=encoding, usecols=usecols, low_memory=False)
        except Exception as error:
            last_error = error

    raise RuntimeError(f"failed to read {file_path.name}: {last_error}")


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = denominator.replace(0, pd.NA)
    return numerator.divide(denominator).fillna(0.0)


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    source_path = project_root / "data" / SOURCE_FILE
    output_dir = project_root / "data" / "processed"
    output_path = output_dir / OUTPUT_FILE

    output_dir.mkdir(parents=True, exist_ok=True)

    dataframe = read_csv_with_fallback(source_path, RAW_COLUMNS)
    dataframe = dataframe.rename(columns=COLUMN_MAPPING)

    dataframe["commercial_name"] = dataframe["commercial_name"].fillna("").astype(str).str.strip()

    for column in NUMERIC_COLUMNS:
        dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce").fillna(0)

    dataframe["worker_id"] = (
        dataframe["base_year_quarter_code"].astype("Int64").astype(str)
        + "_"
        + dataframe["commercial_code"].astype("Int64").astype(str)
    )
    dataframe["age_20_40_worker"] = (
        dataframe["age_20_worker_population"]
        + dataframe["age_30_worker_population"]
        + dataframe["age_40_worker_population"]
    )
    dataframe["age_20_40_worker_ratio"] = safe_divide(
        dataframe["age_20_40_worker"],
        dataframe["total_worker_population"],
    ).round(6)
    dataframe["age_60_plus_worker_ratio"] = safe_divide(
        dataframe["age_60_plus_worker_population"],
        dataframe["total_worker_population"],
    ).round(6)

    dataframe = dataframe[
        (dataframe["commercial_name"] != "")
        & (dataframe["worker_id"] != "")
    ].copy()
    dataframe = dataframe.drop_duplicates(subset=["worker_id"]).copy()

    column_order = [
        "worker_id",
        "base_year_quarter_code",
        "commercial_code",
        "commercial_name",
        "total_worker_population",
        "age_20_worker_population",
        "age_30_worker_population",
        "age_40_worker_population",
        "age_60_plus_worker_population",
        "age_20_40_worker",
        "age_20_40_worker_ratio",
        "age_60_plus_worker_ratio",
    ]

    dataframe = dataframe[column_order]
    dataframe.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"Saved cleaned worker population data: {output_path}")
    print(f"Rows: {len(dataframe)}")


if __name__ == "__main__":
    main()
