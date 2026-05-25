"""Build reviewable Gold Set drafts from extracted schedule images.

Korean OCR is only used when a local Tesseract installation has `kor` language
data.  If Korean OCR is unavailable, the script writes strict review-required
placeholder rows so uncertain image content is never treated as a confirmed
Gold label.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from normalize_gold_set import (  # noqa: E402
    GOLD_COLUMNS,
    REVIEW_COLUMNS,
    assign_gold_label,
    infer_campaign_activity_type,
    infer_place_type,
    infer_target_voter_group,
    normalize_candidate_name,
    normalize_date,
    normalize_district,
    normalize_place_name,
    normalize_time,
)


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
TIME_PATTERN = re.compile(r"(오전|오후|AM|PM|am|pm)?\s*(\d{1,2})(?:[:：시]\s*(\d{1,2}))?")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create reviewable Gold Set draft CSVs from schedule images.")
    parser.add_argument("--input_dir", required=True, help="data/raw/schedules root")
    parser.add_argument("--output_dir", default="output/gold_set_drafts", help="Draft CSV output directory")
    parser.add_argument("--candidate", default="", help="Optional candidate filter")
    parser.add_argument("--tesseract", default="", help="Optional Tesseract executable path")
    return parser.parse_args()


def clean_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def image_date_from_path(path: Path) -> str:
    for part in [path.stem, *[parent.name for parent in path.parents]]:
        match = re.search(r"(20\d{6})", part)
        if match:
            return normalize_date(match.group(1))
        match = re.search(r"(?<!\d)(\d{4})(?!\d)", part)
        if match:
            return normalize_date(f"2026{match.group(1)}")
    return ""


def candidate_from_path(path: Path) -> str:
    text = " ".join([path.stem, *[parent.name for parent in path.parents]])
    return normalize_candidate_name(text)


def find_tesseract(explicit_path: str = "") -> str | None:
    if explicit_path and Path(explicit_path).exists():
        return explicit_path
    candidates = [
        "tesseract",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for candidate in candidates:
        try:
            completed = subprocess.run(
                [candidate, "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=10,
            )
            if completed.returncode == 0:
                return candidate
        except (OSError, subprocess.SubprocessError):
            continue
    return None


def tesseract_has_korean(tesseract_path: str) -> bool:
    try:
        completed = subprocess.run(
            [tesseract_path, "--list-langs"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return any(line.strip() == "kor" for line in completed.stdout.splitlines())


def run_ocr(image_path: Path, tesseract_path: str | None, has_korean: bool) -> tuple[str, str]:
    if not tesseract_path:
        return "", "OCR unavailable: tesseract executable not found"
    if not has_korean:
        return "", "OCR unavailable: Korean language data 'kor' is not installed"
    try:
        completed = subprocess.run(
            [tesseract_path, str(image_path), "stdout", "-l", "kor+eng", "--psm", "6"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return "", "OCR unavailable: tesseract timed out"
    except OSError as exc:
        return "", f"OCR unavailable: {exc}"
    if completed.returncode != 0:
        return "", f"OCR unavailable: {completed.stderr.strip()}"
    return completed.stdout.strip(), ""


def split_schedule_lines(ocr_text: str) -> list[str]:
    lines = [re.sub(r"\s+", " ", line).strip() for line in ocr_text.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return []

    schedule_lines: list[str] = []
    buffer = ""
    for line in lines:
        if TIME_PATTERN.search(line):
            if buffer:
                schedule_lines.append(buffer.strip())
            buffer = line
        else:
            buffer = f"{buffer} {line}".strip() if buffer else line
    if buffer:
        schedule_lines.append(buffer.strip())
    return schedule_lines


def parse_event_line(line: str) -> dict[str, str]:
    time_match = TIME_PATTERN.search(line)
    time_text = normalize_time(time_match.group(0)) if time_match else ""
    event_text = line[time_match.end() :].strip(" -:：") if time_match else line

    place_name = ""
    bracket_match = re.search(r"[(@（](.*?)[)）]", event_text)
    if bracket_match:
        place_name = bracket_match.group(1).strip()
    elif "@" in event_text:
        place_name = event_text.split("@", maxsplit=1)[1].strip()
    elif "-" in event_text:
        place_name = event_text.rsplit("-", maxsplit=1)[-1].strip()

    return {
        "time": time_text,
        "event_title": event_text,
        "place_name": normalize_place_name(place_name),
        "district": normalize_district("", event_text, place_name),
    }


def build_rows_for_image(image_path: Path, tesseract_path: str | None, has_korean: bool) -> list[dict[str, object]]:
    source_image = image_path.name
    candidate = candidate_from_path(image_path)
    schedule_date = image_date_from_path(image_path)
    ocr_text, ocr_note = run_ocr(image_path, tesseract_path, has_korean)
    schedule_lines = split_schedule_lines(ocr_text)

    rows: list[dict[str, object]] = []
    if not schedule_lines:
        rows.append(
            {
                "gold_id": "",
                "candidate_name": candidate,
                "date": schedule_date,
                "day_of_week": "",
                "d_day": "",
                "time": "",
                "district": "",
                "place_name": "",
                "address": "",
                "event_title": "",
                "place_type": "",
                "campaign_activity_type": "",
                "online_offline": "unknown",
                "target_voter_group": "",
                "context_tags": "",
                "gold_label_0_3": 0,
                "gold_label_reason": "OCR 결과가 없어 수동 검수 전까지 장소 추천 평가에서 제외함",
                "use_for_place_recommendation": False,
                "use_for_message_recommendation": False,
                "source_image": source_image,
                "review_required": True,
                "review_reason": ocr_note or "OCR text empty; manual review required",
                "ocr_text": ocr_note or ocr_text,
            }
        )
        return rows

    for line in schedule_lines:
        parsed = parse_event_line(line)
        row = {
            "gold_id": "",
            "candidate_name": candidate,
            "date": schedule_date,
            "day_of_week": "",
            "d_day": "",
            "time": parsed["time"],
            "district": parsed["district"],
            "place_name": parsed["place_name"],
            "address": "",
            "event_title": parsed["event_title"],
            "place_type": infer_place_type(parsed["event_title"]),
            "campaign_activity_type": infer_campaign_activity_type(parsed["event_title"]),
            "online_offline": "",
            "target_voter_group": infer_target_voter_group(parsed["event_title"]),
            "context_tags": "",
            "gold_label_0_3": "",
            "gold_label_reason": "",
            "use_for_place_recommendation": "",
            "use_for_message_recommendation": "",
            "source_image": source_image,
            "review_required": True,
            "review_reason": "OCR 기반 초안이므로 사람 검수 필요",
            "ocr_text": line,
        }
        row["gold_label_0_3"] = assign_gold_label(pd.Series(row))
        rows.append(row)
    return rows


def iter_images(input_dir: Path, candidate_filter: str = "") -> list[Path]:
    candidate = normalize_candidate_name(candidate_filter)
    images = [path for path in input_dir.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS]
    if candidate:
        images = [path for path in images if candidate_from_path(path) == candidate]
    return sorted(images, key=lambda path: (candidate_from_path(path), image_date_from_path(path), path.name))


def date_range_label(rows: pd.DataFrame) -> str:
    dates = sorted(date for date in rows["date"].astype(str).tolist() if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date))
    if not dates:
        return datetime.now().strftime("%Y%m%d")
    return f"{dates[0].replace('-', '')}_{dates[-1].replace('-', '')}"


def save_outputs(rows: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    if rows.empty:
        rows = pd.DataFrame(columns=[*GOLD_COLUMNS, *REVIEW_COLUMNS])

    for candidate, group in rows.groupby("candidate_name", dropna=False):
        candidate_name = normalize_candidate_name(candidate) or "unknown"
        label = date_range_label(group)
        path = output_dir / f"new_gold_set_draft_{candidate_name}_{label}.csv"
        group.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"draft: {path} rows={len(group)}")

    review_path = output_dir.parent / "new_gold_set_review_required.csv"
    rows[rows["review_required"].astype(bool)].to_csv(review_path, index=False, encoding="utf-8-sig")
    print(f"review: {review_path}")


def run(input_dir: Path, output_dir: Path, candidate_filter: str, tesseract: str) -> None:
    tesseract_path = find_tesseract(tesseract)
    has_korean = bool(tesseract_path and tesseract_has_korean(tesseract_path))
    images = iter_images(input_dir, candidate_filter)
    all_rows: list[dict[str, object]] = []
    for image_path in images:
        all_rows.extend(build_rows_for_image(image_path, tesseract_path, has_korean))

    rows = pd.DataFrame(all_rows, columns=[*GOLD_COLUMNS, *REVIEW_COLUMNS])
    save_outputs(rows, output_dir)

    print("=== schedule image draft build ===")
    print(f"images: {len(images)}")
    print(f"rows: {len(rows)}")
    print(f"tesseract: {tesseract_path or 'not found'}")
    print(f"korean OCR available: {has_korean}")
    print(f"review required: {int(rows['review_required'].astype(bool).sum()) if len(rows) else 0}")


def main() -> int:
    args = parse_args()
    run(Path(args.input_dir), Path(args.output_dir), args.candidate, args.tesseract)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
