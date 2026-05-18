# Reads: data/서울시 사회복지시설(노인여가복지시설) 목록.csv
# Writes: data/processed/cleaned_senior.csv

from pathlib import Path

import pandas as pd


SOURCE_FILE = "서울시 사회복지시설(노인여가복지시설) 목록.csv"
OUTPUT_FILE = "cleaned_senior.csv"

RAW_COLUMNS = [
    "시설코드",
    "시설명",
    "시설종류상세명(시설종류)",
    "시군구코드",
    "시군구명",
    "시설주소",
]

COLUMN_MAPPING = {
    "시설코드": "senior_id",
    "시설명": "facility_name",
    "시설종류상세명(시설종류)": "facility_type",
    "시군구코드": "district_code",
    "시군구명": "district_name",
    "시설주소": "facility_address",
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

    for column in dataframe.columns:
        dataframe[column] = dataframe[column].fillna("").astype(str).str.strip()

    dataframe = dataframe[
        (dataframe["senior_id"] != "")
        & (dataframe["facility_name"] != "")
        & (dataframe["facility_type"] != "")
        & (dataframe["district_code"] != "")
        & (dataframe["district_name"] != "")
        & (dataframe["facility_address"] != "")
    ].copy()

    dataframe = dataframe.drop_duplicates(subset=["senior_id"]).copy()

    column_order = [
        "senior_id",
        "facility_name",
        "facility_type",
        "district_code",
        "district_name",
        "facility_address",
    ]

    dataframe = dataframe[column_order]
    dataframe.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"Saved cleaned senior data: {output_path}")
    print(f"Rows: {len(dataframe)}")


if __name__ == "__main__":
    main()
