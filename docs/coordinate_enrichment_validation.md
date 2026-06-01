# Coordinate Enrichment Validation

## 좌표 보강이 필요한 이유

추천 API는 장소명과 자치구를 안정적으로 반환하지만, 일부 후보는 `lat/lng`가 없다. 지도 marker를 무리하게 찍으면 시연에서 잘못된 자치구가 표시될 수 있으므로, 추천 결과와 지도 표시 가능 여부를 분리한다.

“본 시스템은 지도 marker의 신뢰성을 위해 임의 fallback 좌표나 자치구 중심 좌표를 사용하지 않는다. 따라서 Kakao 검색 및 자치구 검증을 통과하지 못한 후보는 추천 결과에는 유지하되 지도 marker에서는 제외한다.”

## Kakao 검색 순서

공통 모듈 `frontend/app/components/camp/routeCoordinateEnrichment.js`가 `/route`와 `/future-prediction`에서 재사용된다.

1. 원본 데이터에 유효한 서울권 좌표가 있으면 우선 사용한다.
2. 검증된 기존 후보 데이터에 같은 `district + place_name` 좌표가 있으면 사용한다.
3. localStorage cache에서 version, place_name, address, district가 일치하고 district 검증을 통과한 좌표만 사용한다.
4. 주소가 있으면 Kakao `addressSearch`를 먼저 시도한다.
5. 주소 검색 실패 또는 주소 누락 시 `서울 + 자치구 + 장소명`으로 Kakao `keywordSearch`를 수행한다.

## District-Safe Matching 원칙

Kakao 검색 결과는 상단부터 순회하되 다음 조건을 모두 만족하는 첫 결과만 채택한다.

- 서울시 결과일 것
- 후보의 선택 자치구와 일치할 것
- `lat/lng`가 숫자이고 서울권 범위일 것

검색 결과가 다른 자치구이면 `district_mismatch_geocode_rejected`로 기록하고 marker로 사용하지 않는다. SDK 미로드, 검색 실패, 좌표 형식 오류, 주소 누락은 `coordinate_debug`와 사용자용 상태 라벨로 분리한다.

## localStorage Cache 구조

캐시 key는 `route-coord::v2::{district}::{place_name}::{address}` 형태이다. 값에는 `version`, `lat`, `lng`, `district_normalized`, `coordinate_status`, `coordinate_source`, Kakao 주소 메타데이터, `updated_at`을 저장한다.

`version`이 맞지 않거나 자치구가 불일치하면 캐시는 무시한다. 이 구조는 장소명이 같아도 주소 또는 자치구가 다른 좌표를 재사용하는 문제를 줄인다.

## Marker Eligibility 기준

marker는 `isMarkerEligible(item)`이 true인 경우에만 생성한다.

- `route_item_id`, 장소명, 자치구가 존재해야 한다.
- `lat/lng`가 유효한 서울권 숫자여야 한다.
- 좌표 상태가 `original`, `merged_static`, `cached`, `geocoded` 중 하나여야 한다.
- 좌표 source가 `original`, `static`, `kakao_address_search`, `kakao_keyword_search`, `cache` 중 하나여야 한다.
- fallback 후보, synthetic 후보, district mismatch 후보는 좌표가 있어도 marker에서 제외한다.

marker 번호는 전체 추천 순위를 유지한다. 예를 들어 1번 후보가 좌표 없음이고 2번 후보만 좌표가 있으면 marker에는 `2`가 표시된다.

## 25개 자치구 검증 결과 요약

`scripts/check_all_district_coordinate_enrichment.js`는 25개 자치구 단일 선택을 자동 검증한다. 기록 컬럼은 `district`, `result_count`, `marker_count`, `no_coord_count`, `geocoded_count`, `cached_count`, `not_found_count`, `district_mismatch_rejected_count`, `actual_mismatch_count`, `status`이다.

통과 기준은 추천 결과가 1개 이상이고, 실제 자치구 mismatch가 0이며, marker/timeline id mismatch가 없어야 한다. 모든 후보가 marker가 될 필요는 없지만, 좌표 없는 후보가 추천 결과에서 사라지면 안 된다.

복수 자치구 검증은 `scripts/check_multi_district_route_coordinate_enrichment.js`가 수행하며 다음 조합을 포함한다.

- 강남구 + 서초구
- 성북구 + 송파구
- 용산구 + 강남구
- 중구 + 동대문구
- 마포구 + 영등포구

## 남은 한계

Kakao 검색으로도 좌표를 찾지 못하거나, 검색 결과의 자치구가 후보 자치구와 다르면 지도에는 표시하지 않는다. 주소가 없는 추상 장소명은 `display_place_name`을 보정하더라도 실제 좌표 검색에는 실패할 수 있다.

## 잘못된 fallback 좌표를 사용하지 않는 이유

자치구 중심 좌표나 임의 fallback 좌표를 marker로 찍으면 지도상으로는 장소가 존재하는 것처럼 보인다. 이는 교수님/심사 관점에서 성능 과장으로 해석될 수 있고, 실제 캠프 운영에서도 잘못된 현장 안내가 된다. 따라서 본 시스템은 추천 품질과 지도 좌표 신뢰성을 분리해 표현한다.
