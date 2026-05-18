from pprint import pprint

try:
    from scripts.recommender import recommend_places
    from scripts.route_planner import build_campaign_route
except ImportError:
    from recommender import recommend_places
    from route_planner import build_campaign_route


LINE = "=" * 100

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


def print_header(title: str) -> None:
    print(LINE)
    print(title)


def summarize_route(route: list[dict]) -> list[dict]:
    summarized = []

    for slot in route:
        summarized.append(
            {
                "time": slot.get("time"),
                "place_type": slot.get("place_type"),
                "place_name": (slot.get("place") or {}).get("name"),
                "messages": slot.get("messages", []),
            }
        )

    return summarized


def run_single_recommendation_experiments() -> None:
    print_header("Single Recommendation Experiments")

    for index, (time_slot, place_type, target_age_group) in enumerate(
        SINGLE_RECOMMENDATION_CASES,
        start=1,
    ):
        print(f"[CASE {index}] recommend_places({time_slot!r}, {place_type!r}, {target_age_group!r})")
        results = recommend_places(time_slot, place_type, target_age_group)
        pprint(results)
        print()


def run_route_experiments() -> None:
    print_header("Campaign Route Experiments")

    for index, (target_age_group, route_template) in enumerate(ROUTE_CASES, start=1):
        print(f"[CASE {index}] build_campaign_route({target_age_group!r}, route_template={route_template!r})")
        route = build_campaign_route(target_age_group, route_template=route_template)
        pprint(summarize_route(route))
        print()


def main() -> None:
    run_single_recommendation_experiments()
    run_route_experiments()
    print(LINE)


if __name__ == "__main__":
    main()
