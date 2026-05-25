"""Extract candidate schedule images from ZIP files into a stable raw layout.

Examples:
    python src/extract_schedule_images.py --input "gold set수작업/오세훈_일정_20260427~20260525.zip" --candidate 오세훈
    python src/extract_schedule_images.py --input "gold set수작업/정원오_일정_20260517~20260525.zip" --candidate 정원오
"""

from __future__ import annotations

import argparse
import csv
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
DEFAULT_OUTPUT_DIR = Path("data/raw/schedules")
DEFAULT_LOG_PATH = Path("output/schedule_image_extraction_log.csv")


@dataclass(frozen=True)
class ImageEntry:
    zip_path: Path
    member_name: str
    candidate_name: str
    schedule_date: date
    output_path: Path
    status: str
    note: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract schedule images from candidate ZIP files.")
    parser.add_argument("--input", required=True, help="Input ZIP path")
    parser.add_argument("--candidate", default="", help="Candidate name override")
    parser.add_argument("--output_dir", default=str(DEFAULT_OUTPUT_DIR), help="Raw schedule image output root")
    parser.add_argument("--log", default=str(DEFAULT_LOG_PATH), help="CSV extraction log path")
    parser.add_argument("--year", type=int, default=2026, help="Election year used for MMDD-only filenames")
    return parser.parse_args()


def clean_candidate_name(value: str) -> str:
    text = str(value or "").strip()
    if "정원오" in text:
        return "정원오"
    if "오세훈" in text:
        return "오세훈"
    return text


def infer_candidate(zip_path: Path, member_name: str, override: str = "") -> str:
    candidate = clean_candidate_name(override)
    if candidate:
        return candidate

    combined = f"{zip_path.name} {member_name}"
    candidate = clean_candidate_name(combined)
    if candidate:
        return candidate
    raise ValueError(f"Could not infer candidate name from {zip_path} / {member_name}")


def infer_date_from_name(name: str, year: int = 2026) -> date | None:
    basename = Path(name).stem
    match_yyyymmdd = re.search(r"(20\d{6})", basename)
    if match_yyyymmdd:
        return datetime.strptime(match_yyyymmdd.group(1), "%Y%m%d").date()

    match_mmdd = re.search(r"(?<!\d)(\d{4})(?!\d)", basename)
    if match_mmdd:
        return datetime.strptime(f"{year}{match_mmdd.group(1)}", "%Y%m%d").date()
    return None


def infer_date_range_from_zip_name(zip_path: Path, year: int = 2026) -> tuple[date, date] | None:
    name = zip_path.name
    match = re.search(r"(20\d{6})\s*[~_-]\s*(20\d{6})", name)
    if match:
        return (
            datetime.strptime(match.group(1), "%Y%m%d").date(),
            datetime.strptime(match.group(2), "%Y%m%d").date(),
        )

    match = re.search(r"(\d{4})\s*[~_-]\s*(\d{4})", name)
    if match:
        return (
            datetime.strptime(f"{year}{match.group(1)}", "%Y%m%d").date(),
            datetime.strptime(f"{year}{match.group(2)}", "%Y%m%d").date(),
        )
    return None


def date_span(start: date, end: date) -> list[date]:
    days: list[date] = []
    cursor = start
    while cursor <= end:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def safe_member_basename(member_name: str) -> str:
    basename = Path(member_name.replace("\\", "/")).name
    if not basename:
        raise ValueError(f"ZIP member has no basename: {member_name}")
    return basename


def extract_zip(input_path: Path, output_root: Path, candidate_override: str, year: int) -> tuple[list[ImageEntry], list[dict[str, str]]]:
    if not input_path.exists():
        raise FileNotFoundError(f"ZIP file not found: {input_path}")

    rows: list[ImageEntry] = []
    missing_rows: list[dict[str, str]] = []
    seen_dates: set[date] = set()

    with zipfile.ZipFile(input_path) as archive:
        members = [
            name
            for name in archive.namelist()
            if not name.endswith("/") and Path(name).suffix.lower() in IMAGE_EXTENSIONS
        ]

        for member in sorted(members):
            schedule_date = infer_date_from_name(member, year=year)
            if schedule_date is None:
                missing_rows.append(
                    {
                        "zip_path": str(input_path),
                        "candidate_name": clean_candidate_name(candidate_override),
                        "date": "",
                        "status": "unparsed_filename",
                        "note": f"Could not parse date from image filename: {member}",
                    }
                )
                continue

            candidate = infer_candidate(input_path, member, candidate_override)
            seen_dates.add(schedule_date)
            output_dir = output_root / candidate / schedule_date.strftime("%Y%m%d")
            output_path = output_dir / safe_member_basename(member)

            if output_path.exists():
                rows.append(
                    ImageEntry(
                        zip_path=input_path,
                        member_name=member,
                        candidate_name=candidate,
                        schedule_date=schedule_date,
                        output_path=output_path,
                        status="skipped_exists",
                        note="File already exists; not overwritten",
                    )
                )
                continue

            output_dir.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, output_path.open("wb") as target:
                target.write(source.read())

            rows.append(
                ImageEntry(
                    zip_path=input_path,
                    member_name=member,
                    candidate_name=candidate,
                    schedule_date=schedule_date,
                    output_path=output_path,
                    status="extracted",
                    note="",
                )
            )

    candidate = clean_candidate_name(candidate_override) or (rows[0].candidate_name if rows else "")
    expected_range = infer_date_range_from_zip_name(input_path, year=year)
    if expected_range:
        for expected_date in date_span(*expected_range):
            if expected_date not in seen_dates:
                missing_rows.append(
                    {
                        "zip_path": str(input_path),
                        "candidate_name": candidate,
                        "date": expected_date.isoformat(),
                        "status": "missing_image",
                        "note": f"No image found for {candidate} {expected_date.isoformat()}",
                    }
                )

    return rows, missing_rows


def append_log(log_path: Path, extracted: list[ImageEntry], missing: list[dict[str, str]]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "zip_path",
        "member_name",
        "candidate_name",
        "date",
        "output_path",
        "status",
        "note",
    ]
    write_header = not log_path.exists()
    with log_path.open("a", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        for item in extracted:
            writer.writerow(
                {
                    "zip_path": str(item.zip_path),
                    "member_name": item.member_name,
                    "candidate_name": item.candidate_name,
                    "date": item.schedule_date.isoformat(),
                    "output_path": str(item.output_path),
                    "status": item.status,
                    "note": item.note,
                }
            )
        for item in missing:
            writer.writerow(
                {
                    "zip_path": item.get("zip_path", ""),
                    "member_name": "",
                    "candidate_name": item.get("candidate_name", ""),
                    "date": item.get("date", ""),
                    "output_path": "",
                    "status": item.get("status", ""),
                    "note": item.get("note", ""),
                }
            )


def run(input_path: Path, output_dir: Path, candidate: str, log_path: Path, year: int) -> None:
    extracted, missing = extract_zip(input_path, output_dir, candidate, year)
    append_log(log_path, extracted, missing)

    extracted_count = sum(1 for row in extracted if row.status == "extracted")
    skipped_count = sum(1 for row in extracted if row.status == "skipped_exists")
    print("=== schedule image extraction ===")
    print(f"zip: {input_path}")
    print(f"images found: {len(extracted)}")
    print(f"extracted: {extracted_count}")
    print(f"skipped existing: {skipped_count}")
    print(f"missing dates: {len([row for row in missing if row.get('status') == 'missing_image'])}")
    for row in missing:
        print(f"- {row.get('status')}: {row.get('candidate_name')} {row.get('date')} {row.get('note')}")
    print(f"log: {log_path}")


def main() -> int:
    args = parse_args()
    run(
        input_path=Path(args.input),
        output_dir=Path(args.output_dir),
        candidate=args.candidate,
        log_path=Path(args.log),
        year=args.year,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
