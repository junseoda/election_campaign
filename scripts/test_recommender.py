from pprint import pprint

from recommender import recommend_places


LINE = "=" * 100


def run_case(title: str, time_slot: str, place_type: str, target_age_group: str) -> None:
    print(LINE)
    print(title)
    print(
        f"recommend_places({time_slot!r}, {place_type!r}, {target_age_group!r})"
    )
    result = recommend_places(time_slot, place_type, target_age_group)
    pprint(result)


def main() -> None:
    run_case("CASE 1: SUBWAY", "morning", "subway", "20_40")
    run_case("CASE 2: PARK", "afternoon", "park", "20_40")
    run_case("CASE 3: SENIOR", "afternoon", "senior_friendly", "60_plus")
    print(LINE)


if __name__ == "__main__":
    main()
