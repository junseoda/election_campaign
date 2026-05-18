# Reads recommendation outputs from recommender.py and route_planner.py
# Writes markdown tables to docs/experiment_results.md

from pathlib import Path

try:
    from scripts.recommender import recommend_places
    from scripts.route_planner import build_campaign_route
except ImportError:
    from recommender import recommend_places
    from route_planner import build_campaign_route


SINGLE_RECOMMENDATION_CASES = [
    ("morning", "subway", "20_40"),
    ("afternoon", "park", "20_40"),
    ("afternoon", "senior_friendly", "60_plus"),
    ("afternoon", "market", "20_40"),
    ("afternoon", "market", "60_plus"),
]

ROUTE_CASES = [
    ("20_40", "default"),
    ("20_40", "neighborhood_focus"),
    ("60_plus", "default"),
    ("60_plus", "neighborhood_focus"),
]

PLACE_TYPE_LABELS = {
    "subway": "subway",
    "park": "park",
    "market": "전통시장",
    "senior_friendly": "senior_friendly",
}

ROUTE_TEMPLATE_LABELS = {
    "default": "기본 동선",
    "neighborhood_focus": "생활권 중심 동선",
}


def escape_markdown(value: object) -> str:
    text = str(value)
    return text.replace("|", "\\|").replace("\n", "<br>")


def format_place_summary(place: dict | None) -> str:
    if not place:
        return "-"

    name = place.get("name", "-")
    score = place.get("score", "-")
    return f"{name} ({score})"


def format_reason_summary(place: dict | None) -> str:
    if not place:
        return "-"

    reasons = place.get("reason", [])
    if not reasons:
        return "-"

    return "; ".join(str(reason) for reason in reasons[:2])


def format_message_titles(messages: list[dict]) -> str:
    titles = [str(message.get("message", "")).strip() for message in messages if message.get("message")]
    if not titles:
        return "-"

    return ", ".join(titles[:2])


def build_markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    row_lines = [
        "| " + " | ".join(escape_markdown(cell) for cell in row) + " |"
        for row in rows
    ]
    return "\n".join([header_line, separator_line, *row_lines])


def build_single_recommendation_rows() -> list[list[str]]:
    rows: list[list[str]] = []

    for index, (time_slot, place_type, target_age_group) in enumerate(
        SINGLE_RECOMMENDATION_CASES,
        start=1,
    ):
        results = recommend_places(time_slot, place_type, target_age_group)
        top_1 = results[0] if len(results) > 0 else None
        top_2 = results[1] if len(results) > 1 else None
        top_3 = results[2] if len(results) > 2 else None

        rows.append(
            [
                f"CASE {index}",
                time_slot,
                PLACE_TYPE_LABELS.get(place_type, place_type),
                target_age_group,
                format_place_summary(top_1),
                format_place_summary(top_2),
                format_place_summary(top_3),
                format_reason_summary(top_1),
            ]
        )

    return rows


def build_route_rows() -> list[list[str]]:
    rows: list[list[str]] = []

    for index, (target_age_group, route_template) in enumerate(ROUTE_CASES, start=1):
        route = build_campaign_route(target_age_group, route_template=route_template)
        route_summary_parts = []

        for slot in route:
            place_name = (slot.get("place") or {}).get("name", "-")
            message_titles = format_message_titles(slot.get("messages", []))
            route_summary_parts.append(
                f"{slot.get('time')} / {PLACE_TYPE_LABELS.get(slot.get('place_type'), slot.get('place_type'))} / "
                f"{place_name} / {message_titles}"
            )

        rows.append(
            [
                f"CASE {index}",
                target_age_group,
                ROUTE_TEMPLATE_LABELS.get(route_template, route_template),
                "<br>".join(route_summary_parts),
            ]
        )

    return rows


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    docs_dir = project_root / "docs"
    output_path = docs_dir / "experiment_results.md"

    docs_dir.mkdir(parents=True, exist_ok=True)

    single_table = build_markdown_table(
        [
            "Case",
            "time_slot",
            "place_type",
            "target_age_group",
            "Top 1",
            "Top 2",
            "Top 3",
            "Top 1 key reason",
        ],
        build_single_recommendation_rows(),
    )

    route_table = build_markdown_table(
        [
            "Case",
            "target_age_group",
            "route_template",
            "Route summary",
        ],
        build_route_rows(),
    )

    content = "\n".join(
        [
            "# Experiment Results",
            "",
            "## Single Recommendation Cases",
            "",
            single_table,
            "",
            "## Campaign Route Cases",
            "",
            route_table,
            "",
        ]
    )

    output_path.write_text(content, encoding="utf-8")

    print(f"Saved experiment markdown tables: {output_path}")


if __name__ == "__main__":
    main()
