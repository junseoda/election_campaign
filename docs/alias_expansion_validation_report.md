# Alias Expansion Validation Report

생성일: 2026-05-22

## 1. 검증 목적

이 문서는 alias 기반 후보군 확장이 실제로 공공데이터와 일정표 사이의 명칭 불일치를 줄인 것인지, 또는 Gold Set 정답을 과도하게 주입한 것인지 검증한다. 결론부터 말하면, alias expansion은 성능을 크게 높였지만 현재 alias table은 수작업 seed와 Gold place name에 매우 가까운 row가 많아 **과적합 가능성이 높다**. 논문에는 성능 개선 수치를 쓰되, "Gold Set 확장 후 재검증 필요"를 명시해야 한다.

## 2. Alias Row 분류 결과

총 alias row 수는 65개다. Gold place_name과 완전 동일하거나 거의 동일한 row는 58개이고, 공공 POI source에서 직접 확인되지 않으면서 단일 Gold query와만 강하게 매칭되는 의심 row는 46개다.

### Primary Class Count

| primary_class | count |
| --- | --- |
| gold_specific_alias 의심 | 58 |
| station_exit_alias | 4 |
| manual_seed | 1 |
| common_name_alias | 1 |
| district_landmark_alias | 1 |

### Multi-label Count

| label | count |
| --- | --- |
| manual_seed | 65 |
| gold_specific_alias 의심 | 58 |
| district_landmark_alias | 18 |
| common_name_alias | 18 |
| station_exit_alias | 12 |
| public_poi_alias | 10 |

## 3. Gold-specific Alias 의심 목록

아래 row는 alias_name 또는 canonical_name이 Gold Set의 place_name과 거의 같다. 이 자체가 모두 잘못은 아니다. 실제 장소명을 normalization table에 넣을 수는 있다. 그러나 현재처럼 같은 Gold query를 맞추기 위해 수작업으로 들어간 흔적이 강하면 평가 성능이 낙관적으로 측정될 수 있다.

| alias_row_id | canonical_name | alias_name | place_type | matched_gold_query_ids | matched_gold_place_names | public_source_matches | max_gold_similarity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 남대문시장 | 남대문시장 입구 | 전통시장 | 2026-04-25_11:40_중구 | 남대문시장 | market | 1.0 |
| 2 | 남대문시장 | 남대문시장 남문 | 전통시장 | 2026-04-25_11:40_중구 | 남대문시장 | market | 1.0 |
| 3 | 남대문시장 | 남대문시장 회현역 방면 | 전통시장 | 2026-04-25_11:40_중구 | 남대문시장 | market | 1.0 |
| 4 | 황학시장 | 황학시장 입구 | 전통시장 | 2026-03-10_17:40_중구 | 황학시장 입구 | market | 1.0 |
| 5 | 영등포전통시장 | 영등포전통시장 남문 | 전통시장 | 2026-03-11_15:10_영등포구 | 영등포전통시장 남문 | market | 1.0 |
| 6 | 대림중앙시장 | 대림중앙시장 | 전통시장 | 2026-03-11_16:20_영등포구 | 대림중앙시장 | market | 1.0 |
| 7 | 공릉도깨비시장 | 공릉도깨비시장 | 전통시장 | 2026-03-13_15:30_노원구 | 공릉도깨비시장 |  | 1.0 |
| 8 | 동원시장 | 동원시장 | 전통시장 | 2026-04-09_15:00_중랑구 | 동원시장 | market | 1.0 |
| 9 | 우림시장 | 우림시장 | 전통시장 | 2026-04-09_15:50_중랑구 | 우림시장 | market | 1.0 |
| 10 | 가락몰 농수산물시장 | 가락몰 농수산물시장 | 전통시장 | 2026-04-17_07:30_송파구 | 가락몰 농수산물시장 |  | 1.0 |
| 11 | 가락몰 농수산물시장 | 가락시장 농수산물시장 | 전통시장 | 2026-04-17_07:30_송파구 | 가락몰 농수산물시장 |  | 1.0 |
| 12 | 금천현대시장 | 금천 현대시장 | 전통시장 | 2026-04-30_15:00_금천구 | 금천 현대시장 |  | 1.0 |
| 13 | 건대 맛의거리 | 건대 맛의거리 | 골목상권 | 2026-03-25_18:15_광진구 | 건대 맛의거리 |  | 1.0 |
| 14 | 건대 맛의거리 | 건대입구 맛의거리 | 골목상권 | 2026-03-25_18:15_광진구 | 건대 맛의거리 |  | 1.0 |
| 15 | 성북천 상점가 | 성북천 상점가 | 골목상권 | 2026-04-06_18:00_성북구 | 성북천 상점가 |  | 1.0 |
| 16 | 북촌의 봄 | 북촌의 봄 | 골목상권 | 2026-04-15_10:55_종로구 | 북촌의 봄 |  | 1.0 |
| 17 | 아지오 성수점 | 아지오 성수점 | 골목상권 | 2026-04-24_14:45_성동구 | 아지오 성수점 |  | 1.0 |
| 18 | 서울고속버스터미널 지하상가 | 서울고속버스터미널 지하상가 | 골목상권 | 2026-04-27_11:00_서초구 | 서울고속버스터미널 지하상가 |  | 1.0 |
| 19 | 정동길 투썸플레이스 | 투썸플레이스 정동길점 | 골목상권 | 2026-05-14_14:00_중구 | 투썸플레이스 정동길점 |  | 1.0 |
| 20 | 성수역 | 성수역 3번출구 앞 | 골목상권 | 2026-05-16_12:30_성동구 | 성수역 3번출구 앞 |  | 1.0 |
| 28 | 도림천 | 도림천 | 공원 | 2026-03-26_16:00_관악구 | 도림천 | subway | 1.0 |
| 29 | 응봉산 팔각정 | 응봉산 팔각정 | 공원 | 2026-03-28_12:50_성동구 | 응봉산 팔각정 |  | 1.0 |
| 30 | 장안동 벚꽃길 | 장안동 벚꽃길 | 공원 | 2026-03-31_11:30_동대문구 | 장안동 벚꽃길 |  | 1.0 |
| 31 | 파리공원 | 파리공원 | 공원 | 2026-04-02_16:00_양천구 | 파리공원 |  | 1.0 |
| 32 | 양재천 수변무대 | 양재천 수변무대 일대 | 공원 | 2026-04-05_17:40_양천구 | 양재천 수변무대 일대 |  | 1.0 |

## 4. 단일 Gold Query 주입 의심 목록

다음 row는 public source match가 없고 단일 Gold query와만 거의 동일하게 매칭된다. 논문에는 이 row들을 포함한 성능을 "최종 일반화 성능"으로 주장하기보다 "coverage bottleneck을 확인하기 위한 alias-expanded candidate experiment"로 해석하는 것이 안전하다.

| alias_row_id | canonical_name | alias_name | place_type | matched_gold_query_ids | matched_gold_place_names | evidence |
| --- | --- | --- | --- | --- | --- | --- |
| 7 | 공릉도깨비시장 | 공릉도깨비시장 | 전통시장 | 2026-03-13_15:30_노원구 | 공릉도깨비시장 | source=manual_alias_seed \| near/exact Gold place match: 2026-03-13_15:30_노원구:공릉도깨비시장 \| single Gold query match with no public POI source match |
| 10 | 가락몰 농수산물시장 | 가락몰 농수산물시장 | 전통시장 | 2026-04-17_07:30_송파구 | 가락몰 농수산물시장 | source=manual_alias_seed \| near/exact Gold place match: 2026-04-17_07:30_송파구:가락몰 농수산물시장 \| single Gold query match with no public POI source match |
| 11 | 가락몰 농수산물시장 | 가락시장 농수산물시장 | 전통시장 | 2026-04-17_07:30_송파구 | 가락몰 농수산물시장 | canonical and alias names differ \| source=manual_alias_seed \| near/exact Gold place match: 2026-04-17_07:30_송파구:가락몰 농수산물시장 \| single Gold query match with no public POI source match |
| 12 | 금천현대시장 | 금천 현대시장 | 전통시장 | 2026-04-30_15:00_금천구 | 금천 현대시장 | source=manual_alias_seed \| near/exact Gold place match: 2026-04-30_15:00_금천구:금천 현대시장 \| single Gold query match with no public POI source match |
| 13 | 건대 맛의거리 | 건대 맛의거리 | 골목상권 | 2026-03-25_18:15_광진구 | 건대 맛의거리 | source=manual_alias_seed \| near/exact Gold place match: 2026-03-25_18:15_광진구:건대 맛의거리 \| single Gold query match with no public POI source match |
| 14 | 건대 맛의거리 | 건대입구 맛의거리 | 골목상권 | 2026-03-25_18:15_광진구 | 건대 맛의거리 | station/exit/intersection expression \| canonical and alias names differ \| source=manual_alias_seed \| near/exact Gold place match: 2026-03-25_18:15_광진구:건대 맛의거리 \| single Gold query match with no public POI source match |
| 15 | 성북천 상점가 | 성북천 상점가 | 골목상권 | 2026-04-06_18:00_성북구 | 성북천 상점가 | source=manual_alias_seed \| near/exact Gold place match: 2026-04-06_18:00_성북구:성북천 상점가 \| single Gold query match with no public POI source match |
| 16 | 북촌의 봄 | 북촌의 봄 | 골목상권 | 2026-04-15_10:55_종로구 | 북촌의 봄 | source=manual_alias_seed \| near/exact Gold place match: 2026-04-15_10:55_종로구:북촌의 봄 \| single Gold query match with no public POI source match |
| 17 | 아지오 성수점 | 아지오 성수점 | 골목상권 | 2026-04-24_14:45_성동구 | 아지오 성수점 | source=manual_alias_seed \| near/exact Gold place match: 2026-04-24_14:45_성동구:아지오 성수점 \| single Gold query match with no public POI source match |
| 18 | 서울고속버스터미널 지하상가 | 서울고속버스터미널 지하상가 | 골목상권 | 2026-04-27_11:00_서초구 | 서울고속버스터미널 지하상가 | source=manual_alias_seed \| near/exact Gold place match: 2026-04-27_11:00_서초구:서울고속버스터미널 지하상가 \| single Gold query match with no public POI source match |
| 19 | 정동길 투썸플레이스 | 투썸플레이스 정동길점 | 골목상권 | 2026-05-14_14:00_중구 | 투썸플레이스 정동길점 | canonical and alias names differ \| source=manual_alias_seed \| near/exact Gold place match: 2026-05-14_14:00_중구:투썸플레이스 정동길점 \| single Gold query match with no public POI source match |
| 20 | 성수역 | 성수역 3번출구 앞 | 골목상권 | 2026-05-16_12:30_성동구 | 성수역 3번출구 앞 | station/exit/intersection expression \| canonical and alias names differ \| source=manual_alias_seed \| near/exact Gold place match: 2026-05-16_12:30_성동구:성수역 3번출구 앞 \| single Gold query match with no public POI source match |
| 29 | 응봉산 팔각정 | 응봉산 팔각정 | 공원 | 2026-03-28_12:50_성동구 | 응봉산 팔각정 | landmark or public facility expression \| source=manual_alias_seed \| near/exact Gold place match: 2026-03-28_12:50_성동구:응봉산 팔각정 \| single Gold query match with no public POI source match |
| 30 | 장안동 벚꽃길 | 장안동 벚꽃길 | 공원 | 2026-03-31_11:30_동대문구 | 장안동 벚꽃길 | source=manual_alias_seed \| near/exact Gold place match: 2026-03-31_11:30_동대문구:장안동 벚꽃길 \| single Gold query match with no public POI source match |
| 31 | 파리공원 | 파리공원 | 공원 | 2026-04-02_16:00_양천구 | 파리공원 | landmark or public facility expression \| source=manual_alias_seed \| near/exact Gold place match: 2026-04-02_16:00_양천구:파리공원 \| single Gold query match with no public POI source match |
| 32 | 양재천 수변무대 | 양재천 수변무대 일대 | 공원 | 2026-04-05_17:40_양천구 | 양재천 수변무대 일대 | landmark or public facility expression \| canonical and alias names differ \| source=manual_alias_seed \| near/exact Gold place match: 2026-04-05_17:40_양천구:양재천 수변무대 일대 \| single Gold query match with no public POI source match |
| 33 | 홍제천 인공폭포 | 홍제천 인공폭포 | 공원 | 2026-04-08_17:55_서대문구 | 홍제천 인공폭포 | landmark or public facility expression \| source=manual_alias_seed \| near/exact Gold place match: 2026-04-08_17:55_서대문구:홍제천 인공폭포 \| single Gold query match with no public POI source match |
| 34 | 불암산철쭉동산 | 불암산철쭉동산 | 공원 | 2026-04-19_14:40_노원구 | 불암산철쭉동산 | landmark or public facility expression \| source=manual_alias_seed \| near/exact Gold place match: 2026-04-19_14:40_노원구:불암산철쭉동산 \| single Gold query match with no public POI source match |
| 35 | 불광천 | 불광천 | 공원 | 2026-04-22_18:00_은평구 | 불광천 | source=manual_alias_seed \| near/exact Gold place match: 2026-04-22_18:00_은평구:불광천 \| single Gold query match with no public POI source match |
| 36 | 잠수대교 남단 | 잠수대교 남단 | 공원 | 2026-04-25_09:00_서초구 | 잠수대교 남단 | source=manual_alias_seed \| near/exact Gold place match: 2026-04-25_09:00_서초구:잠수대교 남단 \| single Gold query match with no public POI source match |
| 37 | 샛강생태공원 | 샛강생태공원 | 공원 | 2026-05-09_11:45_영등포구 | 샛강생태공원 | landmark or public facility expression \| source=manual_alias_seed \| near/exact Gold place match: 2026-05-09_11:45_영등포구:샛강생태공원 \| single Gold query match with no public POI source match |
| 38 | 먹골역 7번출구 | 먹골역 7번출구 앞 | 공원 | 2026-05-15_14:40_중랑구 | 먹골역 7번출구 앞 | station/exit/intersection expression \| canonical and alias names differ \| source=manual_alias_seed \| near/exact Gold place match: 2026-05-15_14:40_중랑구:먹골역 7번출구 앞 \| single Gold query match with no public POI source match |
| 39 | 잠실학생체육관 | 잠실학생체육관 | 체육시설 | 2026-03-19_10:00_송파구 | 잠실학생체육관 | landmark or public facility expression \| source=manual_alias_seed \| near/exact Gold place match: 2026-03-19_10:00_송파구:잠실학생체육관 \| single Gold query match with no public POI source match |
| 40 | 마들스포츠타운 | 마들스포츠타운 | 체육시설 | 2026-04-04_10:00_노원구 | 마들스포츠타운 | source=manual_alias_seed \| near/exact Gold place match: 2026-04-04_10:00_노원구:마들스포츠타운 \| single Gold query match with no public POI source match |
| 41 | 서울월드컵경기장 | 마포구 월드컵로 251 | 체육시설 | 2026-05-02_07:00_마포구 | 마포구 월드컵로 251 | canonical and alias names differ \| source=manual_alias_seed \| near/exact Gold place match: 2026-05-02_07:00_마포구:마포구 월드컵로 251 \| single Gold query match with no public POI source match |
| 42 | 효창운동장 | 효창운동장 | 체육시설 | 2026-05-03_08:30_용산구 | 효창운동장 | landmark or public facility expression \| source=manual_alias_seed \| near/exact Gold place match: 2026-05-03_08:30_용산구:효창운동장 \| single Gold query match with no public POI source match |
| 43 | 잠실종합운동장 | 잠실종합운동장 | 체육시설 | 2026-05-05_13:00_송파구 | 잠실종합운동장 | landmark or public facility expression \| source=manual_alias_seed \| near/exact Gold place match: 2026-05-05_13:00_송파구:잠실종합운동장 \| single Gold query match with no public POI source match |
| 44 | 잠실실내체육관 | 잠실실내체육관 | 체육시설 | 2026-05-16_10:00_송파구 | 잠실실내체육관 | landmark or public facility expression \| source=manual_alias_seed \| near/exact Gold place match: 2026-05-16_10:00_송파구:잠실실내체육관 \| single Gold query match with no public POI source match |
| 46 | 궁동종합사회복지관 | 궁동종합사회복지관 | 복지시설 | 2026-03-16_14:00_구로구 | 궁동종합사회복지관 | source=manual_alias_seed \| near/exact Gold place match: 2026-03-16_14:00_구로구:궁동종합사회복지관 \| single Gold query match with no public POI source match |
| 47 | 광야홈리스복지센터 | 광야홈리스복지센터 | 복지시설 | 2026-04-26_11:55_영등포구 | 광야홈리스복지센터 | source=manual_alias_seed \| near/exact Gold place match: 2026-04-26_11:55_영등포구:광야홈리스복지센터 \| single Gold query match with no public POI source match |

## 5. Public-only vs Alias-expanded 성능

public-only는 alias 후보를 제외하고 기존 공공데이터 후보만 사용한 결과이며, alias-expanded는 alias 후보를 포함한 결과다.

| metric | public_only | alias_expanded | alias_only_contribution |
| --- | --- | --- | --- |
| P@1 | 0.0714285714285714 | 0.2857142857142857 | 0.2142857142857143 |
| P@3 | 0.0571428571428571 | 0.1952380952380952 | 0.1380952380952381 |
| P@10 | 0.0271428571428571 | 0.0928571428571428 | 0.0657142857142857 |
| R@10 | 0.2714285714285714 | 0.9285714285714286 | 0.6571428571428573 |
| NDCG@10 | 0.1681966142662297 | 0.5873196597395748 | 0.4191230454733451 |

핵심 변화는 P@1 0.0714 -> 0.2857, R@10 0.2714 -> 0.9286, NDCG@10 0.1682 -> 0.5873이다. 이 변화는 candidate generation coverage 개선 효과를 보여주지만, alias table의 Gold-specific 성격 때문에 일반화 성능으로는 보수적으로 해석해야 한다.

## 6. Top10 Hit Contribution

after optimized Top10 hit 전체는 65개다. 이 중 기존 public-only optimized에서도 맞춘 hit는 19개이고, public-only에서는 못 맞췄지만 alias 후보가 Top10에서 맞춘 새 hit는 46개다. 기타 public/matching 변화로 분류된 새 hit는 0개다.

| contribution_category | query_count |
| --- | --- |
| new_hit_from_alias_candidate | 46 |
| public_candidate_already_hit | 19 |
| not_hit_after_expansion | 5 |

### Alias로 새로 맞춘 예시

| query_id | gold_place_name | matched_place_name | matched_rank | matched_source | matched_method |
| --- | --- | --- | --- | --- | --- |
| 2026-03-13_14:50_노원구 | 구립수락노인종합복지관 | 구립수락노인종합복지관 | 2 | alias_table:manual_alias_seed | exact |
| 2026-03-13_15:30_노원구 | 공릉도깨비시장 | 공릉도깨비시장 | 3 | alias_table:manual_alias_seed | exact |
| 2026-03-16_14:00_구로구 | 궁동종합사회복지관 | 궁동종합사회복지관 | 2 | alias_table:manual_alias_seed | exact |
| 2026-03-19_10:00_송파구 | 잠실학생체육관 | 잠실학생체육관 | 4 | alias_table:manual_alias_seed | exact |
| 2026-03-24_17:00_광화문 | 세종대로 사거리 광화문 광장 | 세종대로 사거리 광화문광장 | 1 | alias_table:manual_alias_seed | normalized |
| 2026-03-25_18:15_광진구 | 건대 맛의거리 | 건대 맛의거리 | 9 | alias_table:manual_alias_seed | exact |
| 2026-03-26_16:00_관악구 | 도림천 | 도림천 | 4 | alias_table:manual_alias_seed | exact |
| 2026-03-28_12:50_성동구 | 응봉산 팔각정 | 응봉산 팔각정 | 4 | alias_table:manual_alias_seed | exact |
| 2026-03-31_11:30_동대문구 | 장안동 벚꽃길 | 장안동 벚꽃길 | 1 | alias_table:manual_alias_seed | exact |
| 2026-04-02_16:00_양천구 | 파리공원 | 파리공원 | 1 | alias_table:manual_alias_seed | exact |
| 2026-04-04_10:00_노원구 | 마들스포츠타운 | 마들스포츠타운 | 1 | alias_table:manual_alias_seed | exact |
| 2026-04-05_17:40_양천구 | 양재천 수변무대 일대 | 양재천 수변무대 | 2 | alias_table:manual_alias_seed | alias |
| 2026-04-06_18:00_성북구 | 성북천 상점가 | 성북천 상점가 | 7 | alias_table:manual_alias_seed | exact |
| 2026-04-08_17:55_서대문구 | 홍제천 인공폭포 | 홍제천 인공폭포 | 1 | alias_table:manual_alias_seed | exact |
| 2026-04-17_07:30_송파구 | 가락몰 농수산물시장 | 가락몰 농수산물시장 | 2 | alias_table:manual_alias_seed | exact |
| 2026-04-17_15:30_강동구 | 명일동 싱크홀 현장 | 명일동 싱크홀 현장 | 3 | alias_table:manual_alias_seed | exact |
| 2026-04-17_16:00_강동구 | 고덕비즈밸리 | 고덕비즈밸리 | 1 | alias_table:manual_alias_seed | exact |
| 2026-04-17_16:35_강동구 | 고덕비즈밸리역 공사현장 | 고덕비즈밸리역 공사현장 | 1 | alias_table:manual_alias_seed | exact |
| 2026-04-19_14:40_노원구 | 불암산철쭉동산 | 불암산철쭉동산 | 2 | alias_table:manual_alias_seed | exact |
| 2026-04-22_18:00_은평구 | 불광천 | 불광천 | 2 | alias_table:manual_alias_seed | exact |

## 7. Leave-One-Place-Type-Out 검증

아래 ablation은 after optimized best weights를 고정한 상태에서 특정 place_type alias 후보만 제거한 결과다. 따라서 weight 재탐색 효과가 아니라 candidate coverage 제거 효과를 본다.

| ablation | removed_place_type | raw_recall@50 | missing_count | R@10 | NDCG@10 | P@1 | delta_raw_recall@50 | delta_R@10 | delta_NDCG@10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| alias_expanded_all |  | 0.9857142857142858 | 1.0 | 0.9285714285714286 | 0.5873196597395748 | 0.2857142857142857 | 0.0 | 0.0 | 0.0 |
| remove_전통시장_alias | 전통시장 | 0.9 | 7.0 | 0.8857142857142857 | 0.5660748463012966 | 0.2857142857142857 | -0.08571428571428574 | -0.04285714285714293 | -0.02124481343827822 |
| remove_공원_alias | 공원 | 0.8285714285714286 | 12.0 | 0.7714285714285715 | 0.47039367495479545 | 0.21428571428571427 | -0.15714285714285714 | -0.15714285714285714 | -0.11692598478477934 |
| remove_교통거점_alias | 교통거점 | 0.9428571428571428 | 4.0 | 0.8857142857142857 | 0.544462516882432 | 0.24285714285714285 | -0.04285714285714293 | -0.04285714285714293 | -0.042857142857142816 |
| remove_복지시설_alias | 복지시설 | 0.9142857142857143 | 6.0 | 0.8571428571428571 | 0.542253248770185 | 0.2857142857142857 | -0.07142857142857151 | -0.07142857142857151 | -0.04506641096938979 |

전통시장 alias 제거는 영향이 상대적으로 작고, 공원 alias 제거는 raw recall@50과 R@10을 크게 낮춘다. 이는 공원/하천/산책로 계열이 기존 public candidate source에서 매우 부족했음을 의미한다. 복지시설과 교통거점도 alias 의존도가 확인된다.

## 8. 결론

1. Alias expansion은 public-only 대비 R@10과 NDCG@10을 크게 높였다.
2. 그러나 alias table의 상당수가 Gold place_name과 거의 동일하고, 일부는 단일 Gold query만을 겨냥한 것처럼 보인다.
3. 따라서 alias-expanded 결과는 "후보군 coverage 개선 시 성능 상한이 크게 올라간다"는 병목 검증 결과로 사용하는 것이 타당하다.
4. 논문 최종 성능으로는 public-only 결과와 alias-expanded 결과를 함께 제시하고, alias-expanded는 Gold Set 확장 전의 보강 실험으로 명시해야 한다.

## 9. 논문에 쓸 수 있는 보수적 해석 문장

Alias 확장은 실제 후보 일정표에 기록된 장소명과 공공데이터 후보명 사이의 표기 차이, 출입구 표현, 광장·산책로·상권명 표현 차이를 줄이기 위한 정규화 방법이다. 실험 결과 alias-expanded candidate pool에서 raw candidate recall@50과 R@10이 크게 상승하여, 본 시스템의 주요 병목이 reranking보다 candidate generation coverage에 있음을 확인하였다. 다만 현재 alias table은 수작업 seed이며 일부 row가 Gold Set 장소명과 매우 유사하므로, 해당 결과를 일반화 성능으로 단정하기보다는 coverage bottleneck을 확인하는 보강 실험으로 해석해야 한다. 향후 추가 후보자와 기간의 Gold Set을 구축한 뒤 동일한 alias 규칙을 고정한 상태에서 재평가하여 과적합 가능성을 검증할 필요가 있다.

## 10. 산출물

- Alias row classification: `output/improved/alias_validation/alias_row_classification.csv`
- Gold-specific suspects: `output/improved/alias_validation/gold_specific_alias_suspects.csv`
- Single-query suspects: `output/improved/alias_validation/single_query_gold_specific_suspects.csv`
- Performance split: `output/improved/alias_validation/performance_public_vs_alias.csv`
- Hit contribution: `output/improved/alias_validation/alias_hit_contribution.csv`
- Leave-one-type-out: `output/improved/alias_validation/leave_one_place_type_out.csv`
