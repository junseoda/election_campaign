# Reads: data/서울시 주요 공원현황.csv
# Writes: data/processed/cleaned_parks.csv

from pathlib import Path

import pandas as pd


SOURCE_FILE = "서울시 주요 공원현황.csv"
OUTPUT_FILE = "cleaned_parks.csv"

RAW_COLUMNS = [
    "연번",
    "공원명",
    "면적",
    "주요시설",
    "지역",
    "공원주소",
    "X좌표(WGS84)",
    "Y좌표(WGS84)",
]

COLUMN_MAPPING = {
    "연번": "park_id",
    "공원명": "park_name",
    "면적": "area_sqm",
    "주요시설": "main_facilities",
    "지역": "region",
    "공원주소": "park_address",
    "X좌표(WGS84)": "longitude",
    "Y좌표(WGS84)": "latitude",
}


def read_csv_with_fallback(file_path: Path, usecols: list[str]) -> pd.DataFrame:
    last_error = None

    for encoding in ("utf-8", "cp949"):
        try:
            return pd.read_csv(file_path, encoding=encoding, usecols=usecols, low_memory=False)
        except Exception as error:
            last_error = error

    raise RuntimeError(f"failed to read {file_path.name}: {last_error}")


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    source_path = project_root / "data" / SOURCE_FILE
    output_dir = project_root / "data" / "processed"
    output_path = output_dir / OUTPUT_FILE

    output_dir.mkdir(parents=True, exist_ok=True)

    dataframe = read_csv_with_fallback(source_path, RAW_COLUMNS)
    dataframe = dataframe.rename(columns=COLUMN_MAPPING)

    dataframe["park_id"] = pd.to_numeric(dataframe["park_id"], errors="coerce")
    dataframe["park_name"] = dataframe["park_name"].fillna("").astype(str).str.strip()
    dataframe["main_facilities"] = dataframe["main_facilities"].fillna("").astype(str).str.strip()
    dataframe["region"] = dataframe["region"].fillna("").astype(str).str.strip()
    dataframe["park_address"] = dataframe["park_address"].fillna("").astype(str).str.strip()

    area_text = (
        dataframe["area_sqm"]
        .fillna("")
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.strip()
    )
    dataframe["area_sqm"] = pd.to_numeric(
        area_text.str.extract(r"^([0-9]+(?:\.[0-9]+)?)")[0],
        errors="coerce",
    ).fillna(0.0)

    dataframe["longitude"] = pd.to_numeric(dataframe["longitude"], errors="coerce")
    dataframe["latitude"] = pd.to_numeric(dataframe["latitude"], errors="coerce")

    dataframe = dataframe.dropna(subset=["park_id", "longitude", "latitude"]).copy()
    dataframe = dataframe[
        (dataframe["park_name"] != "")
        & (dataframe["park_address"] != "")
    ].copy()

    dataframe["park_id"] = dataframe["park_id"].astype(int)
    dataframe = dataframe.drop_duplicates(subset=["park_id"]).copy()

    column_order = [
        "park_id",
        "park_name",
        "area_sqm",
        "main_facilities",
        "region",
        "park_address",
        "longitude",
        "latitude",
    ]

    dataframe = dataframe[column_order]
    dataframe.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"Saved cleaned parks data: {output_path}")
    print(f"Rows: {len(dataframe)}")


if __name__ == "__main__":
    main()
