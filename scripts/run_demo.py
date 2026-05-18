from pprint import pprint

from message_rules import recommend_messages
from recommender import recommend_places


LINE = "=" * 100
SUBLINE = "-" * 100


def run_case(time_slot: str, place_type: str, target_age_group: str) -> None:
    print(LINE)
    print("Demo Case")
    print(f"time_slot: {time_slot}")
    print(f"place_type: {place_type}")
    print(f"target_age_group: {target_age_group}")

    places = recommend_places(time_slot, place_type, target_age_group)
    messages = recommend_messages(place_type, target_age_group)

    print(SUBLINE)
    print("Recommended Places Top 3")
    pprint(places)

    print(SUBLINE)
    print("Recommended Messages Top 3")
    pprint(messages)


def main() -> None:
    run_case("morning", "subway", "20_40")
    run_case("afternoon", "park", "20_40")
    run_case("afternoon", "senior_friendly", "60_plus")
    print(LINE)


if __name__ == "__main__":
    main()
