# Reads: data/서울시 지하철 호선별 역별 시간대별 승하차 인원 정보.csv
# Writes: data/processed/cleaned_subway.csv

from pathlib import Path

import pandas as pd


SOURCE_FILE = "서울시 지하철 호선별 역별 시간대별 승하차 인원 정보.csv"
OUTPUT_FILE = "cleaned_subway.csv"

RAW_COLUMNS = [
    "사용월",
    "호선명",
    "지하철역",
    "06시-07시 승차인원",
    "06시-07시 하차인원",
    "07시-08시 승차인원",
    "07시-08시 하차인원",
    "08시-09시 승차인원",
    "08시-09시 하차인원",
    "09시-10시 승차인원",
    "09시-10시 하차인원",
    "12시-13시 승차인원",
    "12시-13시 하차인원",
    "13시-14시 승차인원",
    "13시-14시 하차인원",
    "14시-15시 승차인원",
    "14시-15시 하차인원",
    "15시-16시 승차인원",
    "15시-16시 하차인원",
    "16시-17시 승차인원",
    "16시-17시 하차인원",
    "17시-18시 승차인원",
    "17시-18시 하차인원",
]

COLUMN_MAPPING = {
    "사용월": "use_month",
    "호선명": "line_name",
    "지하철역": "station_name",
    "06시-07시 승차인원": "in_06_07",
    "06시-07시 하차인원": "out_06_07",
    "07시-08시 승차인원": "in_07_08",
    "07시-08시 하차인원": "out_07_08",
    "08시-09시 승차인원": "in_08_09",
    "08시-09시 하차인원": "out_08_09",
    "09시-10시 승차인원": "in_09_10",
    "09시-10시 하차인원": "out_09_10",
    "12시-13시 승차인원": "in_12_13",
    "12시-13시 하차인원": "out_12_13",
    "13시-14시 승차인원": "in_13_14",
    "13시-14시 하차인원": "out_13_14",
    "14시-15시 승차인원": "in_14_15",
    "14시-15시 하차인원": "out_14_15",
    "15시-16시 승차인원": "in_15_16",
    "15시-16시 하차인원": "out_15_16",
    "16시-17시 승차인원": "in_16_17",
    "16시-17시 하차인원": "out_16_17",
    "17시-18시 승차인원": "in_17_18",
    "17시-18시 하차인원": "out_17_18",
}

NUMERIC_COLUMNS = [
    "in_06_07",
    "out_06_07",
    "in_07_08",
    "out_07_08",
    "in_08_09",
    "out_08_09",
    "in_09_10",
    "out_09_10",
    "in_12_13",
    "out_12_13",
    "in_13_14",
    "out_13_14",
    "in_14_15",
    "out_14_15",
    "in_15_16",
    "out_15_16",
    "in_16_17",
    "out_16_17",
    "in_17_18",
    "out_17_18",
]


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

    for column in ("use_month", "line_name", "station_name"):
        dataframe[column] = dataframe[column].fillna("").astype(str).str.strip()

    dataframe = dataframe[
        (dataframe["use_month"] != "")
        & (dataframe["line_name"] != "")
        & (dataframe["station_name"] != "")
    ].copy()

    for column in NUMERIC_COLUMNS:
        dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce").fillna(0).astype(int)

    dataframe = (
        dataframe.groupby(["use_month", "line_name", "station_name"], as_index=False)[NUMERIC_COLUMNS]
        .sum()
    )

    dataframe["station_id"] = (
        dataframe["use_month"] + "_" + dataframe["line_name"] + "_" + dataframe["station_name"]
    )
    dataframe["morning_total_in"] = dataframe[["in_06_07", "in_07_08", "in_08_09", "in_09_10"]].sum(axis=1)
    dataframe["morning_total_out"] = dataframe[["out_06_07", "out_07_08", "out_08_09", "out_09_10"]].sum(axis=1)
    dataframe["afternoon_total_in"] = dataframe[
        ["in_12_13", "in_13_14", "in_14_15", "in_15_16", "in_16_17", "in_17_18"]
    ].sum(axis=1)
    dataframe["afternoon_total_out"] = dataframe[
        ["out_12_13", "out_13_14", "out_14_15", "out_15_16", "out_16_17", "out_17_18"]
    ].sum(axis=1)

    column_order = [
        "station_id",
        "use_month",
        "line_name",
        "station_name",
        "in_06_07",
        "out_06_07",
        "in_07_08",
        "out_07_08",
        "in_08_09",
        "out_08_09",
        "in_09_10",
        "out_09_10",
        "in_12_13",
        "out_12_13",
        "in_13_14",
        "out_13_14",
        "in_14_15",
        "out_14_15",
        "in_15_16",
        "out_15_16",
        "in_16_17",
        "out_16_17",
        "in_17_18",
        "out_17_18",
        "morning_total_in",
        "morning_total_out",
        "afternoon_total_in",
        "afternoon_total_out",
    ]

    dataframe = dataframe[column_order]
    dataframe.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"Saved cleaned subway data: {output_path}")
    print(f"Rows: {len(dataframe)}")


if __name__ == "__main__":
    main()
