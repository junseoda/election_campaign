from pprint import pprint

try:
    from scripts.recommender import recommend_places
except ImportError:
    from recommender import recommend_places


LINE = "=" * 100


def print_place_result(index: int, place: dict) -> None:
    print(f"{index}. name: {place.get('name')}")
    print(f"   score: {place.get('score')}")
    print("   reason:")

    reasons = place.get("reason", [])
    for reason in reasons:
        print(f"   - {reason}")


def run_case(title: str, time_slot: str, place_type: str, target_age_group: str) -> None:
    print(LINE)
    print(title)
    print(f"time_slot={time_slot}, place_type={place_type}, target_age_group={target_age_group}")
    print("Recommended places Top 3")

    results = recommend_places(time_slot, place_type, target_age_group)

    if not results:
        print("No recommendation results")
        return

    for index, place in enumerate(results, start=1):
        print_place_result(index, place)


def main() -> None:
    run_case("CASE 1: MARKET + 20_40", "afternoon", "market", "20_40")
    run_case("CASE 2: MARKET + 60_plus", "afternoon", "market", "60_plus")
    print(LINE)


if __name__ == "__main__":
    main()
