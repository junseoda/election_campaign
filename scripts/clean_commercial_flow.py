# Reads: data/서울시 상권분석서비스(길단위인구-상권).csv
# Writes: data/processed/cleaned_commercial_flow.csv

from pathlib import Path

import pandas as pd


SOURCE_FILE = "서울시 상권분석서비스(길단위인구-상권).csv"
OUTPUT_FILE = "cleaned_commercial_flow.csv"

RAW_COLUMNS = [
    "기준_년분기_코드",
    "상권_코드",
    "상권_코드_명",
    "총_유동인구_수",
    "연령대_20_유동인구_수",
    "연령대_30_유동인구_수",
    "연령대_40_유동인구_수",
    "연령대_60_이상_유동인구_수",
    "시간대_06_11_유동인구_수",
    "시간대_11_14_유동인구_수",
    "시간대_14_17_유동인구_수",
    "시간대_17_21_유동인구_수",
]

COLUMN_MAPPING = {
    "기준_년분기_코드": "base_year_quarter_code",
    "상권_코드": "commercial_code",
    "상권_코드_명": "commercial_name",
    "총_유동인구_수": "total_flow",
    "연령대_20_유동인구_수": "age_20_flow",
    "연령대_30_유동인구_수": "age_30_flow",
    "연령대_40_유동인구_수": "age_40_flow",
    "연령대_60_이상_유동인구_수": "age_60_plus_flow",
    "시간대_06_11_유동인구_수": "flow_06_11",
    "시간대_11_14_유동인구_수": "flow_11_14",
    "시간대_14_17_유동인구_수": "flow_14_17",
    "시간대_17_21_유동인구_수": "flow_17_21",
}

NUMERIC_COLUMNS = [
    "base_year_quarter_code",
    "commercial_code",
    "total_flow",
    "age_20_flow",
    "age_30_flow",
    "age_40_flow",
    "age_60_plus_flow",
    "flow_06_11",
    "flow_11_14",
    "flow_14_17",
    "flow_17_21",
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

    dataframe["commercial_id"] = (
        dataframe["base_year_quarter_code"].astype("Int64").astype(str)
        + "_"
        + dataframe["commercial_code"].astype("Int64").astype(str)
    )

    dataframe["age_20_40_flow"] = (
        dataframe["age_20_flow"] + dataframe["age_30_flow"] + dataframe["age_40_flow"]
    )
    dataframe["age_20_40_ratio"] = safe_divide(dataframe["age_20_40_flow"], dataframe["total_flow"]).round(6)
    dataframe["age_60_plus_ratio"] = safe_divide(dataframe["age_60_plus_flow"], dataframe["total_flow"]).round(6)
    dataframe["morning_flow_score"] = safe_divide(dataframe["flow_06_11"], dataframe["total_flow"]).round(6)
    dataframe["afternoon_flow_score"] = safe_divide(
        dataframe["flow_11_14"] + dataframe["flow_14_17"] + dataframe["flow_17_21"],
        dataframe["total_flow"],
    ).round(6)

    dataframe = dataframe[
        (dataframe["commercial_name"] != "")
        & (dataframe["commercial_id"] != "")
    ].copy()
    dataframe = dataframe.drop_duplicates(subset=["commercial_id"]).copy()

    column_order = [
        "commercial_id",
        "base_year_quarter_code",
        "commercial_code",
        "commercial_name",
        "total_flow",
        "age_20_flow",
        "age_30_flow",
        "age_40_flow",
        "age_60_plus_flow",
        "flow_06_11",
        "flow_11_14",
        "flow_14_17",
        "flow_17_21",
        "age_20_40_flow",
        "age_20_40_ratio",
        "age_60_plus_ratio",
        "morning_flow_score",
        "afternoon_flow_score",
    ]

    dataframe = dataframe[column_order]
    dataframe.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"Saved cleaned commercial flow data: {output_path}")
    print(f"Rows: {len(dataframe)}")


if __name__ == "__main__":
    main()
