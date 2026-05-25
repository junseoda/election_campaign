"""Normalize campaign schedule Gold Set CSV files.

The base output keeps the existing Gold Set schema first and appends review
metadata only as auxiliary columns.  `merge_gold_sets.py` drops auxiliary
columns when it writes the final integrated Gold Set.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

import pandas as pd


GOLD_COLUMNS = [
    "gold_id",
    "candidate_name",
    "date",
    "day_of_week",
    "d_day",
    "time",
    "district",
    "place_name",
    "address",
    "event_title",
    "place_type",
    "campaign_activity_type",
    "online_offline",
    "target_voter_group",
    "context_tags",
    "gold_label_0_3",
    "gold_label_reason",
    "use_for_place_recommendation",
    "use_for_message_recommendation",
    "source_image",
]

REVIEW_COLUMNS = ["review_required", "review_reason", "ocr_text"]
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
ELECTION_DAY = date(2026, 6, 3)
UNKNOWN_VALUES = {"", "nan", "none", "null", "해당 없음", "확인 필요", "unknown", "미상"}
TRUE_VALUES = {"true", "t", "1", "yes", "y", "사용", "TRUE", "True", "예"}
FALSE_VALUES = {"false", "f", "0", "no", "n", "미사용", "FALSE", "False", "아니오", ""}

SEOUL_DISTRICTS = [
    "종로구",
    "중구",
    "용산구",
    "성동구",
    "광진구",
    "동대문구",
    "중랑구",
    "성북구",
    "강북구",
    "도봉구",
    "노원구",
    "은평구",
    "서대문구",
    "마포구",
    "양천구",
    "강서구",
    "구로구",
    "금천구",
    "영등포구",
    "동작구",
    "관악구",
    "서초구",
    "강남구",
    "송파구",
    "강동구",
]

DISTRICT_ALIASES = {
    "서울시청": "중구",
    "시청": "중구",
    "광화문": "종로구",
    "왕십리": "성동구",
    "성수": "성동구",
    "여의도": "영등포구",
    "신촌": "서대문구",
    "홍대": "마포구",
    "잠실": "송파구",
    "목동": "양천구",
    "고덕": "강동구",
    "마곡": "강서구",
    "청량리": "동대문구",
    "사당": "동작구",
    "신림": "관악구",
    "강남역": "강남구",
    "서울역": "중구",
}

PLACE_TYPE_RULES = [
    ("전통시장", ["시장", "전통시장", "상인회"]),
    ("골목상권", ["상권", "상점가", "먹자골목", "로데오", "거리"]),
    ("교통거점", ["역", "출구", "사거리", "버스", "환승", "출근", "퇴근", "지하철"]),
    ("공원", ["공원", "광장", "하천", "둘레길", "산책로"]),
    ("체육시설", ["체육", "운동장", "구장", "경기장", "스포츠"]),
    ("복지시설", ["복지", "노인", "어르신", "장애인", "종합사회복지관", "복지관"]),
    ("정책현장", ["공약", "정책", "발표", "민원", "현장"]),
    ("노동현장", ["노동", "노조", "근로", "산업", "일터"]),
    ("재개발/도시개발현장", ["재개발", "재건축", "도시개발", "정비사업", "주거"]),
    ("종교시설", ["교회", "성당", "사찰", "법회", "종교"]),
    ("직능단체", ["협회", "단체", "연합회", "간담회", "협약"]),
    ("방송/언론", ["방송", "라디오", "TV", "유튜브", "인터뷰", "토론", "기자회견"]),
    ("캠프/정당", ["캠프", "당사", "선대위", "회의"]),
]


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none"} else text


def normalize_candidate_name(value: object) -> str:
    text = clean_text(value)
    if "정원오" in text or text.lower() in {"jungwono", "gwon", "jeong"}:
        return "정원오"
    if "오세훈" in text or text.lower() in {"ohsehoon", "oh", "osehun"}:
        return "오세훈"
    return text


def normalize_date(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    text = re.sub(r"[./]", "-", text)
    if re.fullmatch(r"\d{8}", text):
        parsed = datetime.strptime(text, "%Y%m%d")
    else:
        parsed = pd.to_datetime(text, errors="coerce")
        if pd.isna(parsed):
            return text
    return pd.Timestamp(parsed).strftime("%Y-%m-%d")


def normalize_time(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    text = text.replace("：", ":").replace(".", ":")
    ampm = None
    if any(token in text for token in ["오전", "AM", "am"]):
        ampm = "am"
    if any(token in text for token in ["오후", "PM", "pm"]):
        ampm = "pm"
    text = re.sub(r"(오전|오후|AM|PM|am|pm)", "", text).strip()

    match = re.search(r"(\d{1,2})\s*:\s*(\d{1,2})", text)
    if not match:
        match = re.search(r"(?<!\d)(\d{1,2})(\d{2})(?!\d)", text)
    if not match:
        match = re.search(r"(?<!\d)(\d{1,2})시(?:\s*(\d{1,2})분?)?", text)
    if not match:
        return text

    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"
    return text


def normalize_district(value: object, *context_values: object) -> str:
    text = " ".join(clean_text(item) for item in (value, *context_values) if clean_text(item))
    if not text:
        return ""
    for district in SEOUL_DISTRICTS:
        if district in text:
            return district
    for alias, district in DISTRICT_ALIASES.items():
        if alias in text:
            return district
    return clean_text(value)


def normalize_place_name(value: object) -> str:
    text = unicodedata.normalize("NFKC", clean_text(value))
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"^(장소|방문지|위치)\s*[:：]\s*", "", text)
    return text.strip()


def infer_place_type(row_or_text: object) -> str:
    if isinstance(row_or_text, pd.Series):
        text = " ".join(
            clean_text(row_or_text.get(column, ""))
            for column in ["place_type", "place_name", "event_title", "context_tags", "campaign_activity_type"]
        )
    else:
        text = clean_text(row_or_text)
    for place_type, keywords in PLACE_TYPE_RULES:
        if any(keyword in text for keyword in keywords):
            return place_type
    return "기타/확인필요"


def infer_campaign_activity_type(row_or_text: object) -> str:
    if isinstance(row_or_text, pd.Series):
        text = " ".join(clean_text(row_or_text.get(column, "")) for column in ["event_title", "place_name", "context_tags"])
    else:
        text = clean_text(row_or_text)
    if any(keyword in text for keyword in ["출근", "퇴근", "인사"]):
        return "거리인사"
    if any(keyword in text for keyword in ["시장", "상권", "상점가"]):
        return "지역상권방문"
    if any(keyword in text for keyword in ["간담회", "대화", "타운홀"]):
        return "주민간담회"
    if any(keyword in text for keyword in ["협약", "협약식"]):
        return "정책협약"
    if any(keyword in text for keyword in ["발표", "공약", "기자회견"]):
        return "공약발표"
    if any(keyword in text for keyword in ["방송", "인터뷰", "라디오", "유튜브", "토론"]):
        return "방송출연"
    if any(keyword in text for keyword in ["예배", "미사", "법회", "종교"]):
        return "종교행사"
    if any(keyword in text for keyword in ["현장", "방문"]):
        return "현장방문"
    if any(keyword in text for keyword in ["회의", "선대위", "캠프"]):
        return "내부/정당행사"
    return "확인필요"


def infer_target_voter_group(row_or_text: object) -> str:
    if isinstance(row_or_text, pd.Series):
        text = " ".join(
            clean_text(row_or_text.get(column, ""))
            for column in ["target_voter_group", "place_type", "place_name", "event_title", "context_tags"]
        )
    else:
        text = clean_text(row_or_text)
    targets: list[str] = []
    if any(keyword in text for keyword in ["상인", "시장", "상권", "소상공인"]):
        targets.append("상인")
    if any(keyword in text for keyword in ["노인", "어르신", "복지", "60"]):
        targets.append("어르신")
    if any(keyword in text for keyword in ["청년", "대학", "캠퍼스"]):
        targets.append("청년")
    if any(keyword in text for keyword in ["노동", "근로", "노조"]):
        targets.append("노동자")
    if any(keyword in text for keyword in ["출근", "퇴근", "역", "교통"]):
        targets.append("직장인")
    if any(keyword in text for keyword in ["주민", "아파트", "재개발", "주거"]):
        targets.append("지역주민")
    if not targets:
        targets.append("일반시민")
    return ";".join(dict.fromkeys(targets))


def normalize_online_offline(value: object, row: pd.Series | None = None) -> str:
    text = clean_text(value)
    context = text
    if row is not None:
        context = " ".join([text, clean_text(row.get("event_title", "")), clean_text(row.get("place_type", ""))])
    lower_context = context.lower()
    if any(keyword in lower_context for keyword in ["hybrid"]):
        return "hybrid"
    if any(keyword in lower_context for keyword in ["offline", "in-person"]):
        return "offline"
    if any(keyword in lower_context for keyword in ["online", "youtube", "zoom"]):
        return "online"
    if any(keyword in context for keyword in ["온라인", "유튜브", "방송", "라디오", "인터뷰"]):
        return "online"
    if any(keyword in context for keyword in ["혼합", "하이브리드", "hybrid"]):
        return "hybrid"
    if any(keyword in context for keyword in ["오프라인", "방문", "시장", "역", "공원", "현장", "간담회", "행사"]):
        return "offline"
    return "unknown"


def coerce_bool(value: object) -> bool:
    text = clean_text(value)
    if isinstance(value, bool):
        return value
    if text in TRUE_VALUES or text.lower() in TRUE_VALUES:
        return True
    if text in FALSE_VALUES or text.lower() in FALSE_VALUES:
        return False
    return False


def normalize_context_tags(value: object, row: pd.Series | None = None) -> str:
    raw_tags = re.split(r"[;,/]", clean_text(value))
    tags = [tag.strip() for tag in raw_tags if tag.strip()]
    if row is not None:
        for column in ["place_type", "campaign_activity_type", "district"]:
            tag = clean_text(row.get(column, ""))
            if tag and tag not in UNKNOWN_VALUES:
                tags.append(tag)
        time_text = clean_text(row.get("time", ""))
        if re.fullmatch(r"\d{2}:\d{2}", time_text):
            hour = int(time_text[:2])
            if 5 <= hour < 12:
                tags.append("오전")
            elif 12 <= hour < 18:
                tags.append("오후")
            else:
                tags.append("저녁")
    return ";".join(dict.fromkeys(tags))


def assign_gold_label(row_or_text: object) -> int:
    if isinstance(row_or_text, pd.Series):
        text = " ".join(
            clean_text(row_or_text.get(column, ""))
            for column in [
                "event_title",
                "place_name",
                "place_type",
                "campaign_activity_type",
                "online_offline",
                "target_voter_group",
                "context_tags",
            ]
        )
        online_offline = normalize_online_offline(row_or_text.get("online_offline", ""), row_or_text)
        place_name = normalize_place_name(row_or_text.get("place_name", ""))
        district = normalize_district(row_or_text.get("district", ""), place_name, row_or_text.get("address", ""))
    else:
        text = clean_text(row_or_text)
        online_offline = normalize_online_offline(text)
        place_name = text
        district = ""

    if online_offline == "online":
        return 1 if any(keyword in text for keyword in ["방송", "인터뷰", "유튜브", "토론"]) else 0
    if not place_name or place_name in UNKNOWN_VALUES or not district:
        return 0
    if any(keyword in text for keyword in ["내부", "회의", "비공개", "이동"]):
        return 0
    if any(keyword in text for keyword in ["방송", "유튜브", "전화", "인터뷰"]):
        return 1
    if any(keyword in text for keyword in ["협약", "토론", "기자회견", "당사", "캠프", "종교", "예배", "미사"]):
        return 2
    if any(
        keyword in text
        for keyword in [
            "시장",
            "역",
            "출근",
            "퇴근",
            "거리",
            "상권",
            "공원",
            "복지",
            "체육",
            "현장",
            "재개발",
            "간담회",
            "방문",
            "노동",
        ]
    ):
        return 3
    return 2 if online_offline in {"offline", "hybrid"} else 0


def gold_label_reason(label: int, row: pd.Series) -> str:
    if label == 3:
        return "오프라인 방문이며 장소명과 지역 맥락이 있어 장소 추천 정답으로 적합함"
    if label == 2:
        return "장소 의미는 있으나 직접 유세 장소성은 보조적인 일정임"
    if label == 1:
        return "장소 추천보다 메시지 또는 미디어 노출 평가에 가까운 일정임"
    return "장소 정보가 부족하거나 온라인/내부 일정으로 장소 추천 평가에서 제외함"


def parse_date_from_source_image(value: object) -> str:
    text = clean_text(value)
    match = re.search(r"(20\d{6})", text)
    if match:
        return normalize_date(match.group(1))
    match = re.search(r"(?<!\d)(\d{4})(?!\d)", text)
    if match:
        return normalize_date(f"2026{match.group(1)}")
    return ""


def d_day_for(date_text: str) -> str:
    try:
        current = datetime.strptime(date_text, "%Y-%m-%d").date()
    except ValueError:
        return ""
    return f"D-{(ELECTION_DAY - current).days}"


def review_reason_for(row: pd.Series) -> str:
    reasons: list[str] = []
    place_name = clean_text(row.get("place_name", ""))
    district = clean_text(row.get("district", ""))
    address = clean_text(row.get("address", ""))
    if not place_name or place_name in UNKNOWN_VALUES or place_name in SEOUL_DISTRICTS:
        reasons.append("place_name 확인 필요")
    if not district or district not in SEOUL_DISTRICTS:
        reasons.append("district 확인 필요")
    if not address or address in UNKNOWN_VALUES:
        reasons.append("address 확인 필요")
    if clean_text(row.get("ocr_text", "")).startswith("OCR unavailable"):
        reasons.append("한글 OCR 미지원")
    return "; ".join(dict.fromkeys(reasons))


def read_csv_with_fallback(path: Path) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "cp949", "utf-8"):
        try:
            return pd.read_csv(path, encoding=encoding, dtype=str, keep_default_na=False)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def iter_input_csvs(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    paths = sorted(path for path in input_path.rglob("*.csv") if path.is_file())
    reviewed = [path for path in paths if "manual_reviewed" in path.name]
    if reviewed:
        return reviewed
    return paths


def ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    prepared = df.copy()
    for column in [*GOLD_COLUMNS, *REVIEW_COLUMNS]:
        if column not in prepared.columns:
            prepared[column] = ""
    return prepared


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    prepared = ensure_columns(df)
    prepared["candidate_name"] = prepared["candidate_name"].map(normalize_candidate_name)
    prepared["source_image"] = prepared["source_image"].map(clean_text)
    prepared["date"] = prepared.apply(
        lambda row: normalize_date(row["date"]) or parse_date_from_source_image(row["source_image"]),
        axis=1,
    )
    prepared["time"] = prepared["time"].map(normalize_time)
    prepared["place_name"] = prepared["place_name"].map(normalize_place_name)
    prepared["address"] = prepared["address"].map(clean_text)
    prepared["event_title"] = prepared["event_title"].map(clean_text)
    prepared["district"] = prepared.apply(
        lambda row: normalize_district(row["district"], row["place_name"], row["address"], row["event_title"]),
        axis=1,
    )

    missing_place_type = prepared["place_type"].map(clean_text).eq("")
    prepared.loc[missing_place_type, "place_type"] = prepared.loc[missing_place_type].apply(infer_place_type, axis=1)

    missing_activity = prepared["campaign_activity_type"].map(clean_text).eq("")
    prepared.loc[missing_activity, "campaign_activity_type"] = prepared.loc[missing_activity].apply(
        infer_campaign_activity_type,
        axis=1,
    )

    missing_target = prepared["target_voter_group"].map(clean_text).eq("")
    prepared.loc[missing_target, "target_voter_group"] = prepared.loc[missing_target].apply(
        infer_target_voter_group,
        axis=1,
    )

    prepared["online_offline"] = prepared.apply(
        lambda row: normalize_online_offline(row["online_offline"], row),
        axis=1,
    )

    missing_label = prepared["gold_label_0_3"].map(clean_text).eq("")
    prepared.loc[missing_label, "gold_label_0_3"] = prepared.loc[missing_label].apply(assign_gold_label, axis=1)
    prepared["gold_label_0_3"] = pd.to_numeric(prepared["gold_label_0_3"], errors="coerce").fillna(0).astype(int).clip(0, 3)

    missing_reason = prepared["gold_label_reason"].map(clean_text).eq("")
    prepared.loc[missing_reason, "gold_label_reason"] = prepared.loc[missing_reason].apply(
        lambda row: gold_label_reason(int(row["gold_label_0_3"]), row),
        axis=1,
    )

    prepared["use_for_place_recommendation"] = prepared.apply(
        lambda row: bool(
            int(row["gold_label_0_3"]) >= 2
            and row["online_offline"] in {"offline", "hybrid"}
            and clean_text(row["place_name"])
        ),
        axis=1,
    )
    prepared["use_for_message_recommendation"] = prepared.apply(
        lambda row: bool(int(row["gold_label_0_3"]) >= 1),
        axis=1,
    )
    prepared["context_tags"] = prepared.apply(lambda row: normalize_context_tags(row["context_tags"], row), axis=1)
    prepared["day_of_week"] = prepared["date"].map(
        lambda value: WEEKDAYS[datetime.strptime(value, "%Y-%m-%d").weekday()] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) else ""
    )
    prepared["d_day"] = prepared["date"].map(d_day_for)
    prepared["review_reason"] = prepared.apply(review_reason_for, axis=1)
    prepared["review_required"] = prepared["review_reason"].map(lambda value: bool(clean_text(value)))
    return prepared[[*GOLD_COLUMNS, *REVIEW_COLUMNS]]


def normalize_files(paths: Iterable[Path]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in paths:
        frame = read_csv_with_fallback(path)
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=[*GOLD_COLUMNS, *REVIEW_COLUMNS])
    return normalize_dataframe(pd.concat(frames, ignore_index=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize Gold Set draft/review CSV files.")
    parser.add_argument("--input", required=True, help="Input CSV file or directory of CSV files")
    parser.add_argument("--output", required=True, help="Normalized CSV output path")
    parser.add_argument("--review_output", default="", help="Optional review-only CSV output path")
    return parser.parse_args()


def run(input_path: Path, output_path: Path, review_output: Path | None = None) -> None:
    paths = iter_input_csvs(input_path)
    normalized = normalize_files(paths)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    normalized.to_csv(output_path, index=False, encoding="utf-8-sig")

    review_path = review_output or output_path.with_name(output_path.stem + "_review_required.csv")
    review_rows = normalized[normalized["review_required"].astype(bool)].copy()
    review_rows.to_csv(review_path, index=False, encoding="utf-8-sig")

    print("=== gold set normalization ===")
    print(f"input files: {len(paths)}")
    print(f"rows: {len(normalized)}")
    print(f"review required: {len(review_rows)}")
    print(f"output: {output_path}")
    print(f"review output: {review_path}")


def main() -> int:
    args = parse_args()
    run(
        input_path=Path(args.input),
        output_path=Path(args.output),
        review_output=Path(args.review_output) if args.review_output else None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
