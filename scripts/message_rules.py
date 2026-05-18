def recommend_messages(place_type: str, target_age_group: str) -> list[dict]:
    normalized_place_type = str(place_type).strip().lower()
    normalized_target_age_group = str(target_age_group).strip()

    if normalized_place_type == "subway" and normalized_target_age_group == "20_40":
        return [
            {
                "message": "청년 일자리",
                "reason": "working-age commuters are likely to respond to jobs and economic opportunity messages",
            },
            {
                "message": "출퇴근 교통 개선",
                "reason": "subway locations are strongly tied to daily commuting pain points",
            },
            {
                "message": "주거비 부담 완화",
                "reason": "20_40 commuters often care about housing costs near work and transit",
            },
        ]

    if normalized_place_type == "park" and normalized_target_age_group == "20_40":
        return [
            {
                "message": "가족 친화 정책",
                "reason": "parks are effective places to connect with family-oriented daily life concerns",
            },
            {
                "message": "여가/문화 인프라 확대",
                "reason": "park visitors are likely to value leisure and cultural amenities in the neighborhood",
            },
            {
                "message": "생활체육·공원 개선",
                "reason": "the place context directly supports messages about exercise and park quality",
            },
        ]

    if normalized_place_type in {"senior", "senior_friendly"} and normalized_target_age_group == "60_plus":
        return [
            {
                "message": "어르신 복지 강화",
                "reason": "senior-friendly facilities align directly with welfare needs of older residents",
            },
            {
                "message": "의료 접근성 개선",
                "reason": "healthcare access is a core concern for many older adults",
            },
            {
                "message": "교통약자 이동 편의 확대",
                "reason": "mobility support is highly relevant in outreach for seniors and vulnerable riders",
            },
        ]

    return [
        {
            "message": "지역 맞춤 생활 정책",
            "reason": "used as a simple fallback when no specific rule is matched",
        }
    ]


def main() -> None:
    print("CASE 1: subway + 20_40")
    print(recommend_messages("subway", "20_40"))
    print()

    print("CASE 2: park + 20_40")
    print(recommend_messages("park", "20_40"))
    print()

    print("CASE 3: senior_friendly + 60_plus")
    print(recommend_messages("senior_friendly", "60_plus"))


if __name__ == "__main__":
    main()
