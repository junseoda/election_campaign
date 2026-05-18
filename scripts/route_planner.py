from collections import Counter
from functools import lru_cache
from itertools import product
from pathlib import Path
from pprint import pprint
import re

import pandas as pd

try:
    from scripts.message_rules import recommend_messages
    from scripts.recommender import recommend_places
except ImportError:
    from message_rules import recommend_messages
    from recommender import recommend_places


DEFAULT_SLOTS = [
    {"time": "07:00", "time_slot": "morning", "place_type": "subway"},
    {"time": "11:00", "time_slot": "afternoon", "place_type": "park"},
    {"time": "14:00", "time_slot": "afternoon", "place_type": "senior_friendly"},
    {"time": "18:00", "time_slot": "afternoon", "place_type": "subway"},
]

NEIGHBORHOOD_FOCUS_SLOTS = [
    {"time": "10:00", "time_slot": "morning", "place_type": "market"},
    {"time": "13:00", "time_slot": "afternoon", "place_type": "park"},
    {"time": "15:00", "time_slot": "afternoon", "place_type": "senior_friendly"},
    {"time": "18:00", "time_slot": "afternoon", "place_type": "subway"},
]

ROUTE_TEMPLATES = {
    "default": DEFAULT_SLOTS,
    "neighborhood_focus": NEIGHBORHOOD_FOCUS_SLOTS,
}

MARKET_MESSAGE_FALLBACKS = {
    "20_40": [
        {
            "message": "골목상권 활성화",
            "reason": "traditional markets are strong places to talk about local jobs and neighborhood commerce",
        },
        {
            "message": "생활밀착 물가 안정",
            "reason": "market visitors are closely connected to everyday household spending and price concerns",
        },
        {
            "message": "소상공인 지원 확대",
            "reason": "merchant-heavy spaces fit messages about small business support and local resilience",
        },
    ],
    "60_plus": [
        {
            "message": "전통시장 생활 편의 개선",
            "reason": "traditional markets are familiar daily destinations for many older residents",
        },
        {
            "message": "보행·이동 환경 개선",
            "reason": "market outreach naturally connects to walkability and mobility issues in the neighborhood",
        },
        {
            "message": "생활권 복지 접근성 강화",
            "reason": "market-centered outreach fits messages about nearby welfare and essential services",
        },
    ],
}

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
DISTRICT_TRAVEL_PENALTY = 0.05
TOP_K_CANDIDATES = 3
MEAN_PLACE_SCORE_WEIGHT = 0.78
INTERACTION_ROUTE_BONUS_WEIGHT = 0.04
DISTRICT_CONTINUITY_BONUS_WEIGHT = 0.03
ROUTE_DIVERSITY_BONUS_WEIGHT = 0.03


def normalize_name(value: str) -> str:
    return str(value).strip()


def extract_district(value: str) -> str | None:
    text = normalize_name(value)
    if not text:
        return None

    match = re.search(r"([가-힣]+구)", text)
    if match:
        return match.group(1)

    if text.endswith("구"):
        return text

    return None


def load_cleaned_csv(file_name: str) -> pd.DataFrame:
    file_path = PROCESSED_DIR / file_name
    if not file_path.exists():
        return pd.DataFrame()

    return pd.read_csv(file_path, encoding="utf-8-sig")


@lru_cache(maxsize=1)
def load_place_district_lookups() -> dict[str, dict[str, str]]:
    lookups = {
        "park": {},
        "senior_friendly": {},
        "market": {},
        "subway": {},
    }

    park_df = load_cleaned_csv("cleaned_parks.csv")
    for _, row in park_df.iterrows():
        place_name = normalize_name(row.get("park_name", ""))
        district_name = extract_district(row.get("region", "")) or extract_district(
            row.get("park_address", "")
        )
        if place_name and district_name:
            lookups["park"][place_name] = district_name

    senior_df = load_cleaned_csv("cleaned_senior.csv")
    for _, row in senior_df.iterrows():
        place_name = normalize_name(row.get("facility_name", ""))
        district_name = extract_district(row.get("district_name", "")) or extract_district(
            row.get("facility_address", "")
        )
        if place_name and district_name:
            lookups["senior_friendly"][place_name] = district_name

    market_df = load_cleaned_csv("cleaned_market.csv")
    for _, row in market_df.iterrows():
        place_name = normalize_name(row.get("market_name", ""))
        district_name = extract_district(row.get("district_name", "")) or extract_district(
            row.get("market_address", "")
        )
        if place_name and district_name:
            lookups["market"][place_name] = district_name

    return lookups


def get_place_district(place_type: str, place_name: str) -> str | None:
    normalized_place_type = normalize_name(place_type)
    normalized_place_name = normalize_name(place_name)

    if not normalized_place_name:
        return None

    lookups = load_place_district_lookups()
    return lookups.get(normalized_place_type, {}).get(normalized_place_name)


def resolve_place_district(place_type: str, place: dict | None) -> str | None:
    if not place:
        return None

    district_name = extract_district(place.get("district_name", ""))
    if district_name:
        return district_name

    if normalize_name(place_type) == "subway":
        return None

    return get_place_district(place_type, place.get("name", ""))


def calculate_travel_penalty(previous_district: str | None, current_district: str | None) -> float:
    if not previous_district or not current_district:
        return 0.0

    if previous_district == current_district:
        return 0.0

    return DISTRICT_TRAVEL_PENALTY


def add_reason_note(reason_list: list[str], note: str) -> None:
    if note not in reason_list:
        reason_list.append(note)


def build_adjusted_candidate(
    candidate: dict,
    place_type: str,
    previous_district: str | None,
) -> tuple[dict, str | None, float]:
    adjusted_candidate = dict(candidate)
    adjusted_candidate["reason"] = list(candidate.get("reason", []))
    adjusted_candidate["place_type"] = candidate.get("place_type", place_type)
    adjusted_candidate["score"] = float(candidate.get("score", 0.0))

    current_district = resolve_place_district(place_type, adjusted_candidate)
    adjusted_candidate["district_name"] = current_district
    travel_penalty = calculate_travel_penalty(previous_district, current_district)
    adjusted_score = max(0.0, float(adjusted_candidate["score"]) - travel_penalty)
    adjusted_candidate["score"] = round(adjusted_score, 4)

    if previous_district and current_district:
        if previous_district == current_district:
            add_reason_note(
                adjusted_candidate["reason"],
                "same district preferred for route continuity",
            )
        elif travel_penalty > 0:
            add_reason_note(
                adjusted_candidate["reason"],
                "route distance penalty applied",
            )

    return adjusted_candidate, current_district, adjusted_score


def pick_place(
    candidates: list[dict],
    place_type: str,
    used_place_names: set[str],
    previous_place: dict | None,
) -> tuple[dict | None, dict | None]:
    previous_district = None
    if previous_place:
        previous_district = previous_place.get("district")

    available_candidates = []
    for candidate in candidates:
        name = normalize_name(candidate.get("name", ""))
        if name and name not in used_place_names:
            available_candidates.append(candidate)

    if not available_candidates:
        available_candidates = candidates

    scored_candidates = []
    for candidate in available_candidates:
        adjusted_candidate, current_district, adjusted_score = build_adjusted_candidate(
            candidate,
            place_type,
            previous_district,
        )
        scored_candidates.append(
            (
                adjusted_score,
                float(candidate.get("score", 0.0)),
                normalize_name(candidate.get("name", "")),
                adjusted_candidate,
                current_district,
            )
        )

    if scored_candidates:
        scored_candidates.sort(
            key=lambda item: (-item[0], -item[1], item[2]),
        )
        _, _, name, adjusted_candidate, current_district = scored_candidates[0]
        if name:
            used_place_names.add(name)
        return adjusted_candidate, {"name": name, "district": current_district}

    return None, previous_place


def get_route_messages(place_type: str, target_age_group: str) -> list[dict]:
    messages = recommend_messages(place_type, target_age_group)

    if place_type != "market":
        return messages

    if len(messages) != 1:
        return messages

    fallback_reason = "used as a simple fallback when no specific rule is matched"
    if messages[0].get("reason") != fallback_reason:
        return messages

    return MARKET_MESSAGE_FALLBACKS.get(target_age_group, messages)


def build_greedy_route_from_slots(slots: list[dict], target_age_group: str) -> list[dict]:
    route = []
    used_place_names: set[str] = set()
    previous_place: dict | None = None

    for slot in slots:
        places = recommend_places(
            slot["time_slot"],
            slot["place_type"],
            target_age_group,
        )[:TOP_K_CANDIDATES]
        selected_place, previous_place = pick_place(
            places,
            slot["place_type"],
            used_place_names,
            previous_place,
        )
        messages = get_route_messages(slot["place_type"], target_age_group)

        route.append(
            {
                "time": slot["time"],
                "time_slot": slot["time_slot"],
                "place_type": slot["place_type"],
                "place": selected_place,
                "messages": messages,
            }
        )

    return route


def get_slot_candidates(slot: dict, target_age_group: str) -> list[dict | None]:
    places = recommend_places(
        slot["time_slot"],
        slot["place_type"],
        target_age_group,
    )[:TOP_K_CANDIDATES]

    if not places:
        return [None]

    return places


def is_valid_candidate_combination(candidate_combination: tuple[dict | None, ...]) -> bool:
    used_place_names: set[str] = set()

    for candidate in candidate_combination:
        if not candidate:
            continue

        place_name = normalize_name(candidate.get("name", ""))
        if not place_name:
            continue

        if place_name in used_place_names:
            return False

        used_place_names.add(place_name)

    return True


def build_route_from_candidate_combination(
    slots: list[dict],
    candidate_combination: tuple[dict | None, ...],
    target_age_group: str,
) -> list[dict]:
    route = []
    previous_district = None

    for slot, candidate in zip(slots, candidate_combination):
        selected_place = None

        if candidate:
            selected_place, previous_district, _ = build_adjusted_candidate(
                candidate,
                slot["place_type"],
                previous_district,
            )
        else:
            previous_district = None

        route.append(
            {
                "time": slot["time"],
                "time_slot": slot["time_slot"],
                "place_type": slot["place_type"],
                "place": selected_place,
                "messages": get_route_messages(slot["place_type"], target_age_group),
            }
        )

    return route


def evaluate_route_candidate(route: list[dict], target_age_group: str) -> tuple[float, list[str], float, float]:
    route_score, route_reason = build_route_quality_summary(route, target_age_group)
    mean_place_score = calculate_mean_place_score(route)
    average_interaction_score = calculate_average_interaction_score(route)
    return route_score, route_reason, mean_place_score, average_interaction_score


def build_best_route_from_slots(slots: list[dict], target_age_group: str) -> list[dict]:
    candidate_pools = [get_slot_candidates(slot, target_age_group) for slot in slots]

    best_route = None
    best_rank = None

    for candidate_combination in product(*candidate_pools):
        if not is_valid_candidate_combination(candidate_combination):
            continue

        route = build_route_from_candidate_combination(
            slots,
            candidate_combination,
            target_age_group,
        )
        route_score, _, mean_place_score, average_interaction_score = evaluate_route_candidate(
            route,
            target_age_group,
        )

        rank = (route_score, mean_place_score, average_interaction_score)
        if best_rank is None or rank > best_rank:
            best_rank = rank
            best_route = route

    if best_route is not None:
        return best_route

    return build_greedy_route_from_slots(slots, target_age_group)


def build_route_from_slots(slots: list[dict], target_age_group: str) -> list[dict]:
    return build_best_route_from_slots(slots, target_age_group)


def clamp_score(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def extract_interaction_score(place: dict | None) -> float | None:
    if not place:
        return None

    for reason in place.get("reason", []):
        matched = re.search(r"interaction_score=([0-9.]+)", str(reason))
        if matched:
            return clamp_score(float(matched.group(1)))

    return None


def calculate_average_interaction_score(route: list[dict]) -> float:
    interaction_scores = []

    for slot in route:
        interaction_score = extract_interaction_score(slot.get("place"))
        if interaction_score is not None:
            interaction_scores.append(interaction_score)

    if not interaction_scores:
        return 0.0

    return sum(interaction_scores) / len(interaction_scores)


def calculate_interaction_bonus(route: list[dict]) -> float:
    average_interaction_score = calculate_average_interaction_score(route)
    return average_interaction_score * INTERACTION_ROUTE_BONUS_WEIGHT


def calculate_mean_place_score(route: list[dict]) -> float:
    place_scores = [
        float(slot.get("place", {}).get("score", 0.0))
        for slot in route
        if slot.get("place")
    ]

    if not place_scores:
        return 0.0

    return sum(place_scores) / len(place_scores)


def calculate_district_continuity_bonus(route: list[dict]) -> float:
    comparable_pairs = 0
    same_district_pairs = 0

    for index in range(1, len(route)):
        previous_place = route[index - 1].get("place")
        current_place = route[index].get("place")
        previous_district = resolve_place_district(route[index - 1].get("place_type", ""), previous_place)
        current_district = resolve_place_district(route[index].get("place_type", ""), current_place)

        if not previous_district or not current_district:
            continue

        comparable_pairs += 1
        if previous_district == current_district:
            same_district_pairs += 1

    if comparable_pairs == 0:
        return 0.0

    continuity_ratio = same_district_pairs / comparable_pairs
    return continuity_ratio * DISTRICT_CONTINUITY_BONUS_WEIGHT


def calculate_district_repeat_penalty(route: list[dict]) -> float:
    districts = []

    for slot in route:
        place = slot.get("place")
        if not place:
            continue

        district = resolve_place_district(slot.get("place_type", ""), place)
        if district:
            districts.append(district)

    district_counts = Counter(districts)
    repeat_count = sum(count - 2 for count in district_counts.values() if count > 2)
    return repeat_count * 0.02


def calculate_place_type_repeat_penalty(route: list[dict]) -> float:
    place_types = [slot.get("place_type", "") for slot in route if slot.get("place")]
    place_type_counts = Counter(place_types)
    repeat_count = sum(count - 1 for count in place_type_counts.values() if count > 1)
    return repeat_count * 0.015


def calculate_target_coverage_bonus(route: list[dict], target_age_group: str) -> float:
    place_types = {slot.get("place_type", "") for slot in route if slot.get("place")}
    bonus = 0.0

    if target_age_group == "20_40":
        if "subway" in place_types:
            bonus += 0.02
        if "park" in place_types:
            bonus += 0.01
        if "market" in place_types:
            bonus += 0.015
    elif target_age_group == "60_plus":
        if "senior_friendly" in place_types:
            bonus += 0.02
        if "market" in place_types:
            bonus += 0.015
        if "park" in place_types:
            bonus += 0.01

    return min(bonus, 0.05)


def calculate_route_diversity_bonus(route: list[dict]) -> float:
    place_types = [slot.get("place_type", "") for slot in route if slot.get("place")]
    if not place_types:
        return 0.0

    diversity_ratio = len(set(place_types)) / len(place_types)
    return diversity_ratio * ROUTE_DIVERSITY_BONUS_WEIGHT


def calculate_route_score_components(route: list[dict], target_age_group: str) -> dict[str, float]:
    mean_place_score = calculate_mean_place_score(route)
    route_interaction_bonus = calculate_interaction_bonus(route)
    target_coverage_bonus = calculate_target_coverage_bonus(route, target_age_group)
    district_continuity_bonus = calculate_district_continuity_bonus(route)
    route_diversity_bonus = calculate_route_diversity_bonus(route)
    district_repeat_penalty = calculate_district_repeat_penalty(route)
    place_type_repeat_penalty = calculate_place_type_repeat_penalty(route)

    route_score = clamp_score(
        (mean_place_score * MEAN_PLACE_SCORE_WEIGHT)
        + route_interaction_bonus
        + target_coverage_bonus
        + district_continuity_bonus
        + route_diversity_bonus
        - district_repeat_penalty
        - place_type_repeat_penalty
    )

    return {
        "mean_place_score": mean_place_score,
        "route_interaction_bonus": route_interaction_bonus,
        "target_coverage_bonus": target_coverage_bonus,
        "district_continuity_bonus": district_continuity_bonus,
        "route_diversity_bonus": route_diversity_bonus,
        "district_repeat_penalty": district_repeat_penalty,
        "place_type_repeat_penalty": place_type_repeat_penalty,
        "route_score": route_score,
    }


def build_route_quality_summary(route: list[dict], target_age_group: str) -> tuple[float, list[str]]:
    components = calculate_route_score_components(route, target_age_group)
    route_score = components["route_score"]

    route_reason = []
    if components["mean_place_score"] > 0:
        route_reason.append("mean place score prioritized as the primary route quality signal")

    if components["route_interaction_bonus"] > 0:
        route_reason.append("interaction-aware route fit applied")

    if components["target_coverage_bonus"] > 0:
        route_reason.append("target-aligned route structure")

    if components["district_continuity_bonus"] > 0:
        route_reason.append("district continuity bonus applied")

    if components["route_diversity_bonus"] > 0:
        route_reason.append("route diversity bonus applied")

    if components["district_repeat_penalty"] > 0:
        route_reason.append("district repeat penalty applied")

    if components["place_type_repeat_penalty"] > 0:
        route_reason.append("place-type repeat penalty applied")

    if not route_reason:
        route_reason.append("baseline route quality calculated")

    return round(route_score, 4), route_reason


def build_campaign_route(
    target_age_group: str,
    route_template: str = "default",
    include_summary: bool = False,
) -> list[dict] | dict:
    normalized_template = str(route_template).strip().lower()

    if normalized_template not in ROUTE_TEMPLATES:
        raise ValueError("route_template must be one of: default, neighborhood_focus")

    route = build_route_from_slots(ROUTE_TEMPLATES[normalized_template], target_age_group)

    if not include_summary:
        return route

    route_score, route_reason = build_route_quality_summary(route, target_age_group)
    return {
        "route": route,
        "route_score": route_score,
        "route_reason": route_reason,
    }


def build_market_campaign_route(
    target_age_group: str,
    include_summary: bool = False,
) -> list[dict] | dict:
    return build_campaign_route(
        target_age_group,
        route_template="neighborhood_focus",
        include_summary=include_summary,
    )


def main() -> None:
    print("Default route example")
    print("target_age_group: 20_40")
    print("route_template: default")
    pprint(build_campaign_route("20_40", route_template="default", include_summary=True))
    print()
    print("Neighborhood focus route example")
    print("target_age_group: 60_plus")
    print("route_template: neighborhood_focus")
    pprint(
        build_campaign_route(
            "60_plus",
            route_template="neighborhood_focus",
            include_summary=True,
        )
    )


if __name__ == "__main__":
    main()
