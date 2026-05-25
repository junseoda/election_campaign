"""Merge existing and newly reviewed Gold Set CSV files without overwriting originals."""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

import pandas as pd

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from normalize_gold_set import GOLD_COLUMNS, normalize_dataframe, read_csv_with_fallback  # noqa: E402


DEFAULT_EXISTING_PATTERNS = [
    "data/**/*gold_set*.csv",
    "gold set수작업/**/*gold_set*.csv",
    "output/gold_set_all_merged.csv",
]

SKIP_NAME_TOKENS = [
    "evaluation_queries",
    "strong_place",
    "summary",
    "raw_baseline",
    "merge_report",
    "review_required",
    "draft",
    "all_candidates",
    "jungwono_extended",
    "ohsehoon",
    "normalized_new",
]

CANDIDATE_PREFIX = {"정원오": "JG", "오세훈": "OH"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge existing and new Gold Set CSV files.")
    parser.add_argument("--existing_glob", default="", help="Glob for existing Gold Set CSV files")
    parser.add_argument("--new", required=True, help="New normalized/reviewed Gold Set CSV")
    parser.add_argument("--output_all", default="output/gold_set_all_candidates.csv")
    parser.add_argument("--output_jungwono", default="output/gold_set_jungwono_extended.csv")
    parser.add_argument("--output_ohsehoon", default="output/gold_set_ohsehoon.csv")
    parser.add_argument("--report", default="output/gold_set_merge_report.csv")
    return parser.parse_args()


def is_gold_schema(path: Path) -> bool:
    if any(token in path.name for token in SKIP_NAME_TOKENS):
        return False
    try:
        columns = read_csv_with_fallback(path).columns
    except Exception:
        return False
    return all(column in columns for column in GOLD_COLUMNS)


def expand_patterns(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        paths.extend(Path(path) for path in glob.glob(pattern, recursive=True))
    unique = sorted({path.resolve(): path for path in paths if path.is_file()}.values(), key=lambda path: str(path))
    return unique


def discover_existing(existing_glob: str) -> list[Path]:
    patterns = [existing_glob] if existing_glob else DEFAULT_EXISTING_PATTERNS
    candidates = [path for path in expand_patterns(patterns) if is_gold_schema(path)]
    if not candidates and existing_glob:
        candidates = [path for path in expand_patterns(DEFAULT_EXISTING_PATTERNS) if is_gold_schema(path)]
    return candidates


def load_gold_files(paths: list[Path], source_group: str) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    frames: list[pd.DataFrame] = []
    report_rows: list[dict[str, object]] = []
    for path in paths:
        df = read_csv_with_fallback(path)
        report_rows.append(
            {
                "source_group": source_group,
                "file_path": str(path),
                "input_rows": len(df),
                "loaded": True,
                "note": "",
            }
        )
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=GOLD_COLUMNS), report_rows
    return pd.concat(frames, ignore_index=True), report_rows


def duplicate_key(df: pd.DataFrame) -> pd.Series:
    key_columns = ["candidate_name", "date", "time", "district", "place_name", "event_title", "source_image"]
    return df[key_columns].fillna("").astype(str).agg("|".join, axis=1)


def assign_gold_ids(df: pd.DataFrame) -> pd.DataFrame:
    merged = df.copy().sort_values(["candidate_name", "date", "time", "district", "place_name"]).reset_index(drop=True)
    ids: list[str] = []
    counters: dict[str, int] = {}
    for candidate in merged["candidate_name"].astype(str):
        prefix = CANDIDATE_PREFIX.get(candidate, "CD")
        counters[prefix] = counters.get(prefix, 0) + 1
        ids.append(f"{prefix}_{counters[prefix]:04d}")
    merged["gold_id"] = ids
    return merged


def save_candidate_outputs(merged: pd.DataFrame, output_jungwono: Path, output_ohsehoon: Path) -> None:
    jung = merged[merged["candidate_name"].eq("정원오")].copy()
    oh = merged[merged["candidate_name"].eq("오세훈")].copy()
    output_jungwono.parent.mkdir(parents=True, exist_ok=True)
    output_ohsehoon.parent.mkdir(parents=True, exist_ok=True)
    jung[GOLD_COLUMNS].to_csv(output_jungwono, index=False, encoding="utf-8-sig")
    oh[GOLD_COLUMNS].to_csv(output_ohsehoon, index=False, encoding="utf-8-sig")


def run(
    existing_glob: str,
    new_path: Path,
    output_all: Path,
    output_jungwono: Path,
    output_ohsehoon: Path,
    report_path: Path,
) -> None:
    existing_paths = discover_existing(existing_glob)
    existing_raw, report_rows = load_gold_files(existing_paths, "existing")

    new_raw = read_csv_with_fallback(new_path) if new_path.exists() else pd.DataFrame(columns=GOLD_COLUMNS)
    report_rows.append(
        {
            "source_group": "new",
            "file_path": str(new_path),
            "input_rows": len(new_raw),
            "loaded": new_path.exists(),
            "note": "",
        }
    )

    combined_raw = pd.concat([existing_raw, new_raw], ignore_index=True)
    combined = normalize_dataframe(combined_raw)
    before_dedupe = len(combined)
    combined["_dedupe_key"] = duplicate_key(combined)
    combined = combined.drop_duplicates("_dedupe_key", keep="first").drop(columns=["_dedupe_key"]).reset_index(drop=True)
    duplicate_removed = before_dedupe - len(combined)
    merged = assign_gold_ids(combined)

    output_all.parent.mkdir(parents=True, exist_ok=True)
    merged[GOLD_COLUMNS].to_csv(output_all, index=False, encoding="utf-8-sig")
    save_candidate_outputs(merged, output_jungwono, output_ohsehoon)

    report = pd.DataFrame(report_rows)
    summary_rows = pd.DataFrame(
        [
            {"source_group": "summary", "file_path": "existing_files", "input_rows": len(existing_raw), "loaded": True, "note": ""},
            {"source_group": "summary", "file_path": "new_file", "input_rows": len(new_raw), "loaded": True, "note": ""},
            {
                "source_group": "summary",
                "file_path": "duplicate_removed",
                "input_rows": duplicate_removed,
                "loaded": True,
                "note": "candidate/date/time/district/place/event/source_image key",
            },
            {"source_group": "summary", "file_path": "final_rows", "input_rows": len(merged), "loaded": True, "note": ""},
        ]
    )
    report = pd.concat([report, summary_rows], ignore_index=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(report_path, index=False, encoding="utf-8-sig")

    print("=== gold set merge ===")
    print(f"existing files: {len(existing_paths)}")
    print(f"existing rows: {len(existing_raw)}")
    print(f"new rows: {len(new_raw)}")
    print(f"duplicates removed: {duplicate_removed}")
    print(f"final rows: {len(merged)}")
    print(f"output all: {output_all}")


def main() -> int:
    args = parse_args()
    run(
        existing_glob=args.existing_glob,
        new_path=Path(args.new),
        output_all=Path(args.output_all),
        output_jungwono=Path(args.output_jungwono),
        output_ohsehoon=Path(args.output_ohsehoon),
        report_path=Path(args.report),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
