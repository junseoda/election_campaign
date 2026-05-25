# Alias and Matching Rules

## 목적

추천 후보명과 Gold Set 장소명은 같은 장소라도 출입구, 광장, 사거리, 산책로, 상점명, 주소형 표현으로 다르게 기록될 수 있다. 이 문서는 평가와 후보군 확장에 공통 적용하는 장소명 matching 규칙을 정리한다.

## 입력 자료

- Alias table: `data/processed/place_aliases.csv`
- Columns: `canonical_name`, `alias_name`, `district`, `place_type`, `source`, `note`
- Gold Set 자체는 수정하지 않는다.
- Alias table은 후보군 생성과 평가 matching 양쪽에서 같은 방식으로 사용한다.

## Matching 순서

1. District constraint
   - 추천 후보와 Gold 양쪽에 district가 있으면 district가 일치해야 한다.
   - 단, `광화문 -> 종로구`, `서울시청/시청 -> 중구`, `여의도 -> 영등포구`처럼 행정구가 아닌 장소권 표현은 표준 자치구로 변환한다.

2. Exact match
   - 원문 장소명이 완전히 같으면 hit로 본다.

3. Normalized match
   - 공백, 특수문자, 대소문자를 제거한 normalized key가 같으면 hit로 본다.

4. Alias match
   - alias table에서 같은 canonical key 또는 alias key로 연결되면 hit로 본다.
   - 예: `영등포전통시장`과 `영등포전통시장 남문`, `성수역`과 `성수역 3번출구 앞`.

5. Conservative partial match
   - normalized key 중 하나가 다른 하나를 포함하면 hit로 본다.
   - 너무 짧은 문자열에 의한 false positive를 줄이기 위해 길이 3 이상의 key에만 적용한다.

## Candidate Expansion 규칙

- 기존 raw baseline Top10은 보호한다.
- Alias 후보는 query district와 place_type이 호환될 때만 raw 후보군에 추가한다.
- Alias 후보 score는 보호된 Top10의 최저 baseline score보다 약간 낮게 배치해 기존 baseline Top10을 유지한다.
- Reranker는 district, place_type, time, context, target feature로 alias 후보를 Top10까지 끌어올릴 수 있다.

## 해석상 주의

- Alias table은 새 Gold Set이 아니다. Gold label과 relevance를 추가하거나 변경하지 않는다.
- 정책현장, 노동현장, 재개발 현장처럼 독립 공공 POI source가 아직 부족한 유형은 alias 기반 보강에 의존한다.
- 따라서 이번 결과는 "후보군 coverage가 개선되면 reranking 성능이 크게 오른다"는 병목 검증 결과로 해석해야 하며, 향후에는 공공시설, 노동현장, 도시개발, 종교시설 source를 실제 데이터로 확장해야 한다.
