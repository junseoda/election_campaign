from pathlib import Path

import pandas as pd


LINE = "=" * 100
SUBLINE = "-" * 100


def load_csv(file_path: Path) -> pd.DataFrame:
    return pd.read_csv(file_path, encoding="utf-8-sig")


def print_basic_info(dataset_name: str, dataframe: pd.DataFrame) -> None:
    print(LINE)
    print(f"dataset: {dataset_name}")
    print(f"shape: {dataframe.shape}")
    print(f"columns: {list(dataframe.columns)}")
    print("head(5):")
    print(dataframe.head(5).to_string(index=False))


def check_subway(file_path: Path) -> None:
    dataframe = load_csv(file_path)
    print_basic_info("cleaned_subway.csv", dataframe)

    print(SUBLINE)
    print("subway check")
    has_morning = "morning_total_in" in dataframe.columns
    has_afternoon = "afternoon_total_in" in dataframe.columns
    print(f"morning_total_in exists: {has_morning}")
    if has_morning:
        print(f"morning_total_in dtype: {dataframe['morning_total_in'].dtype}")
    print(f"afternoon_total_in exists: {has_afternoon}")
    if has_afternoon:
        print(f"afternoon_total_in dtype: {dataframe['afternoon_total_in'].dtype}")


def check_parks(file_path: Path) -> None:
    dataframe = load_csv(file_path)
    print_basic_info("cleaned_parks.csv", dataframe)

    print(SUBLINE)
    print("parks check")
    has_latitude = "latitude" in dataframe.columns
    has_longitude = "longitude" in dataframe.columns
    print(f"latitude exists: {has_latitude}")
    print(f"longitude exists: {has_longitude}")
    if has_latitude and has_longitude:
        print("coordinate sample (first 5):")
        print(dataframe[["latitude", "longitude"]].head(5).to_string(index=False))


def check_senior(file_path: Path) -> None:
    dataframe = load_csv(file_path)
    print_basic_info("cleaned_senior.csv", dataframe)

    print(SUBLINE)
    print("senior check")
    print(f"district_name exists: {'district_name' in dataframe.columns}")
    print(f"facility_type exists: {'facility_type' in dataframe.columns}")
    print("missing values by column:")
    print(dataframe.isna().sum().to_string())


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    processed_dir = project_root / "data" / "processed"

    subway_path = processed_dir / "cleaned_subway.csv"
    parks_path = processed_dir / "cleaned_parks.csv"
    senior_path = processed_dir / "cleaned_senior.csv"

    print(LINE)
    print("checking cleaned data")
    print(f"processed_dir: {processed_dir}")
    print(f"cleaned_subway.csv exists: {subway_path.exists()}")
    print(f"cleaned_parks.csv exists: {parks_path.exists()}")
    print(f"cleaned_senior.csv exists: {senior_path.exists()}")

    if subway_path.exists():
        check_subway(subway_path)
    else:
        print(LINE)
        print(f"missing file: {subway_path}")

    if parks_path.exists():
        check_parks(parks_path)
    else:
        print(LINE)
        print(f"missing file: {parks_path}")

    if senior_path.exists():
        check_senior(senior_path)
    else:
        print(LINE)
        print(f"missing file: {senior_path}")

    print(LINE)
    print("check finished")


if __name__ == "__main__":
    main()
