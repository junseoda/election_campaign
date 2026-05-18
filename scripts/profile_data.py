from __future__ import annotations

from pathlib import Path

import pandas as pd

REPORT_HANDLE = None


def log(message: str = "") -> None:
    text = str(message)
    print(text)

    if REPORT_HANDLE is not None:
        REPORT_HANDLE.write(text)
        REPORT_HANDLE.write("\n")
        REPORT_HANDLE.flush()


def read_csv_with_fallback(file_path: Path) -> tuple[pd.DataFrame, str]:
    last_error: Exception | None = None

    for encoding in ("utf-8", "cp949"):
        try:
            dataframe = pd.read_csv(file_path, encoding=encoding, low_memory=False)
            return dataframe, encoding
        except Exception as error:
            last_error = error

    raise RuntimeError(f"could not read with utf-8 or cp949: {last_error}")


def estimate_candidate_keys(dataframe: pd.DataFrame) -> tuple[list[str], list[tuple[str, float, int]]]:
    row_count = len(dataframe)
    exact_keys: list[str] = []
    near_keys: list[tuple[str, float, int]] = []

    if row_count == 0:
        return exact_keys, near_keys

    for column in dataframe.columns:
        series = dataframe[column]
        non_null_count = int(series.notna().sum())
        unique_count = int(series.nunique(dropna=True))

        if non_null_count == row_count and unique_count == row_count:
            exact_keys.append(column)
            continue

        unique_ratio = unique_count / row_count
        duplicate_count = row_count - unique_count

        if non_null_count == row_count and unique_ratio >= 0.95:
            near_keys.append((column, unique_ratio, duplicate_count))

    near_keys.sort(key=lambda item: (-item[1], item[2], item[0]))
    return exact_keys, near_keys[:5]


def print_candidate_keys(dataframe: pd.DataFrame) -> None:
    exact_keys, near_keys = estimate_candidate_keys(dataframe)

    log("Candidate key estimate:")
    if exact_keys:
        log(f"- Exact unique columns: {', '.join(exact_keys)}")
        return

    if near_keys:
        for column, unique_ratio, duplicate_count in near_keys:
            log(
                f"- {column}: unique ratio {unique_ratio:.2%}, "
                f"estimated duplicates {duplicate_count}"
            )
        return

    log("- No likely single-column candidate key found")


def profile_csv(file_path: Path) -> None:
    dataframe, encoding = read_csv_with_fallback(file_path)
    row_count, column_count = dataframe.shape

    log("=" * 100)
    log(f"File: {file_path.name}")
    log(f"Full path: {file_path}")
    log(f"Encoding: {encoding}")
    log(f"Rows / Columns: {row_count} / {column_count}")
    log("Columns:")
    for column in dataframe.columns:
        log(f"- {column}")

    log("Missing values by column:")
    log(dataframe.isna().sum().to_string())

    log("Sample 5 rows:")
    if dataframe.empty:
        log("(empty dataframe)")
    else:
        with pd.option_context("display.max_columns", None, "display.width", 200):
            log(dataframe.head(5).to_string(index=False))

    print_candidate_keys(dataframe)


def main() -> None:
    global REPORT_HANDLE

    script_file = Path(__file__).resolve()
    cwd = Path.cwd().resolve()
    project_root = script_file.parent.parent
    data_dir = project_root / "data"
    report_path = project_root / "profiling_report.txt"
    data_dir_exists = data_dir.exists()
    csv_files = sorted(data_dir.rglob("*.csv")) if data_dir_exists else []

    REPORT_HANDLE = report_path.open("w", encoding="utf-8")

    try:
        log("PROFILE SCRIPT STARTED")
        log(f"__file__: {script_file}")
        log(f"cwd: {cwd}")
        log(f"project_root: {project_root}")
        log(f"data_dir: {data_dir}")
        log(f"data_dir exists: {data_dir_exists}")
        log(f"report_path: {report_path}")
        log("Discovered CSV files:")
        if csv_files:
            for file_path in csv_files:
                log(f"- {file_path}")
        else:
            log("- (none)")

        log(f"CSV files found: {len(csv_files)}")

        if not data_dir_exists:
            log(f"[ERROR] data directory not found: {data_dir}")
            return

        if not csv_files:
            log(f"[INFO] no CSV files found under data directory: {data_dir}")
            return

        failed_files: list[str] = []

        for index, file_path in enumerate(csv_files, start=1):
            log("-" * 100)
            log(f"[{index}/{len(csv_files)}] analyzing: {file_path.name}")
            try:
                profile_csv(file_path)
            except Exception as error:
                failed_files.append(file_path.name)
                log("=" * 100)
                log(f"[ERROR] failed to analyze file: {file_path.name}")
                log(f"[ERROR] details: {error}")

        log("=" * 100)
        log(f"Total CSV files: {len(csv_files)}")
        log(f"Succeeded: {len(csv_files) - len(failed_files)}")
        log(f"Failed: {len(failed_files)}")

        if failed_files:
            log("Failed files:")
            for file_name in failed_files:
                log(f"- {file_name}")
    finally:
        log("PROFILE SCRIPT FINISHED")
        REPORT_HANDLE.close()
        REPORT_HANDLE = None


if __name__ == "__main__":
    main()
