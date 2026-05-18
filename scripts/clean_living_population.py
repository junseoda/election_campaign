# Reads: data/행정동 단위 서울 생활인구(내국인).csv
# Writes: data/processed/cleaned_living_population.csv

from pathlib import Path

import pandas as pd


SOURCE_FILE = "행정동 단위 서울 생활인구(내국인).csv"
OUTPUT_FILE = "cleaned_living_population.csv"

RAW_COLUMNS = [
    "기준일ID",
    "시간대구분",
    "행정동코드",
    "총생활인구수",
    "남자20세부터24세생활인구수",
    "남자25세부터29세생활인구수",
    "남자30세부터34세생활인구수",
    "남자35세부터39세생활인구수",
    "남자40세부터44세생활인구수",
    "남자60세부터64세생활인구수",
    "남자65세부터69세생활인구수",
    "남자70세이상생활인구수",
    "여자20세부터24세생활인구수",
    "여자25세부터29세생활인구수",
    "여자30세부터34세생활인구수",
    "여자35세부터39세생활인구수",
    "여자40세부터44세생활인구수",
    "여자60세부터64세생활인구수",
    "여자65세부터69세생활인구수",
    "여자70세이상생활인구수",
]

COLUMN_MAPPING = {
    "기준일ID": "date_id",
    "시간대구분": "time_code",
    "행정동코드": "admin_dong_code",
    "총생활인구수": "total_living_population",
    "남자20세부터24세생활인구수": "male_age_20_24_population",
    "남자25세부터29세생활인구수": "male_age_25_29_population",
    "남자30세부터34세생활인구수": "male_age_30_34_population",
    "남자35세부터39세생활인구수": "male_age_35_39_population",
    "남자40세부터44세생활인구수": "male_age_40_44_population",
    "남자60세부터64세생활인구수": "male_age_60_64_population",
    "남자65세부터69세생활인구수": "male_age_65_69_population",
    "남자70세이상생활인구수": "male_age_70_plus_population",
    "여자20세부터24세생활인구수": "female_age_20_24_population",
    "여자25세부터29세생활인구수": "female_age_25_29_population",
    "여자30세부터34세생활인구수": "female_age_30_34_population",
    "여자35세부터39세생활인구수": "female_age_35_39_population",
    "여자40세부터44세생활인구수": "female_age_40_44_population",
    "여자60세부터64세생활인구수": "female_age_60_64_population",
    "여자65세부터69세생활인구수": "female_age_65_69_population",
    "여자70세이상생활인구수": "female_age_70_plus_population",
}

NUMERIC_COLUMNS = list(COLUMN_MAPPING.values())

AGE_20_40_COLUMNS = [
    "male_age_20_24_population",
    "male_age_25_29_population",
    "male_age_30_34_population",
    "male_age_35_39_population",
    "male_age_40_44_population",
    "female_age_20_24_population",
    "female_age_25_29_population",
    "female_age_30_34_population",
    "female_age_35_39_population",
    "female_age_40_44_population",
]

AGE_60_PLUS_COLUMNS = [
    "male_age_60_64_population",
    "male_age_65_69_population",
    "male_age_70_plus_population",
    "female_age_60_64_population",
    "female_age_65_69_population",
    "female_age_70_plus_population",
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

    for column in NUMERIC_COLUMNS:
        dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce").fillna(0.0)

    dataframe["date_id"] = dataframe["date_id"].astype("Int64")
    dataframe["time_code"] = dataframe["time_code"].astype("Int64")
    dataframe["admin_dong_code"] = dataframe["admin_dong_code"].astype("Int64")

    dataframe["age_20_40_population"] = dataframe[AGE_20_40_COLUMNS].sum(axis=1)
    dataframe["age_60_plus_population"] = dataframe[AGE_60_PLUS_COLUMNS].sum(axis=1)
    dataframe["morning_living_population"] = dataframe["total_living_population"].where(
        dataframe["time_code"].between(6, 10),
        0.0,
    )
    dataframe["afternoon_living_population"] = dataframe["total_living_population"].where(
        dataframe["time_code"].between(11, 17),
        0.0,
    )

    grouped = (
        dataframe.groupby(["date_id", "admin_dong_code"], as_index=False)[
            [
                "total_living_population",
                "age_20_40_population",
                "age_60_plus_population",
                "morning_living_population",
                "afternoon_living_population",
            ]
        ]
        .sum()
    )

    grouped["daytime_living_population"] = (
        grouped["morning_living_population"] + grouped["afternoon_living_population"]
    )
    grouped["age_20_40_ratio"] = safe_divide(
        grouped["age_20_40_population"],
        grouped["total_living_population"],
    ).round(6)
    grouped["age_60_plus_ratio"] = safe_divide(
        grouped["age_60_plus_population"],
        grouped["total_living_population"],
    ).round(6)
    grouped["morning_score"] = safe_divide(
        grouped["morning_living_population"],
        grouped["daytime_living_population"],
    ).round(6)
    grouped["afternoon_score"] = safe_divide(
        grouped["afternoon_living_population"],
        grouped["daytime_living_population"],
    ).round(6)

    grouped = grouped[
        (grouped["date_id"].notna())
        & (grouped["admin_dong_code"].notna())
        & (grouped["total_living_population"] > 0)
    ].copy()

    grouped["living_population_id"] = (
        grouped["date_id"].astype("Int64").astype(str)
        + "_"
        + grouped["admin_dong_code"].astype("Int64").astype(str)
    )

    column_order = [
        "living_population_id",
        "date_id",
        "admin_dong_code",
        "total_living_population",
        "age_20_40_population",
        "age_60_plus_population",
        "age_20_40_ratio",
        "age_60_plus_ratio",
        "morning_living_population",
        "afternoon_living_population",
        "daytime_living_population",
        "morning_score",
        "afternoon_score",
    ]

    grouped = grouped[column_order].sort_values(
        by=["date_id", "admin_dong_code"],
        ascending=[True, True],
    )
    grouped.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"Saved cleaned living population data: {output_path}")
    print(f"Rows: {len(grouped)}")


if __name__ == "__main__":
    main()
