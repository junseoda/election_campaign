# Reads: data/서울시 전통시장 현황.csv
# Writes: data/processed/cleaned_market.csv

from pathlib import Path

import pandas as pd


SOURCE_FILE = "서울시 전통시장 현황.csv"
OUTPUT_FILE = "cleaned_market.csv"

RAW_COLUMNS = [
    "자치구",
    "시장명",
    "형태",
    "주소",
    "건물형(연면적)",
    "점포수(빈점포제외)",
]

COLUMN_MAPPING = {
    "자치구": "district_name",
    "시장명": "market_name",
    "형태": "market_type",
    "주소": "market_address",
    "건물형(연면적)": "floor_area",
    "점포수(빈점포제외)": "store_count",
}


def read_csv_with_fallback(file_path: Path, usecols: list[str]) -> pd.DataFrame:
    last_error = None

    for encoding in ("utf-8", "cp949"):
        try:
            return pd.read_csv(file_path, encoding=encoding, usecols=usecols, low_memory=False)
        except Exception as error:
            last_error = error

    raise RuntimeError(f"failed to read {file_path.name}: {last_error}")


def slug_text(value: str) -> str:
    return str(value).strip().replace(" ", "_").replace("/", "_")


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    source_path = project_root / "data" / SOURCE_FILE
    output_dir = project_root / "data" / "processed"
    output_path = output_dir / OUTPUT_FILE

    output_dir.mkdir(parents=True, exist_ok=True)

    dataframe = read_csv_with_fallback(source_path, RAW_COLUMNS)
    dataframe = dataframe.rename(columns=COLUMN_MAPPING)

    for column in ("district_name", "market_name", "market_type", "market_address"):
        dataframe[column] = dataframe[column].fillna("").astype(str).str.strip()

    dataframe["floor_area"] = pd.to_numeric(dataframe["floor_area"], errors="coerce").fillna(0.0)
    dataframe["store_count"] = pd.to_numeric(dataframe["store_count"], errors="coerce").fillna(0).astype(int)

    dataframe = dataframe[
        (dataframe["district_name"] != "")
        & (dataframe["market_name"] != "")
        & (dataframe["market_address"] != "")
    ].copy()

    dataframe = dataframe.drop_duplicates(
        subset=["district_name", "market_name", "market_address"]
    ).copy()

    dataframe["market_id_base"] = dataframe.apply(
        lambda row: f"{slug_text(row['district_name'])}_{slug_text(row['market_name'])}",
        axis=1,
    )
    dataframe["market_id_order"] = dataframe.groupby("market_id_base").cumcount() + 1
    dataframe["market_id"] = dataframe.apply(
        lambda row: row["market_id_base"]
        if row["market_id_order"] == 1
        else f"{row['market_id_base']}_{row['market_id_order']}",
        axis=1,
    )

    dataframe = dataframe[
        [
            "market_id",
            "market_name",
            "district_name",
            "market_address",
            "market_type",
            "floor_area",
            "store_count",
        ]
    ].copy()

    dataframe.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"Saved cleaned market data: {output_path}")
    print(f"Rows: {len(dataframe)}")


if __name__ == "__main__":
    main()
