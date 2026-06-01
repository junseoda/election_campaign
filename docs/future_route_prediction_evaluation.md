# Future Route Prediction Evaluation

`/future-prediction`은 후보자의 미래 유세 장소를 Top-K로 예측하고, 이후 실제 후보 일정이 공개되었을 때 사후적으로 비교하기 위한 실험 페이지이다.

“/future-prediction은 기존 Gold Set 기반 정량 평가를 대체하지 않는다. 이 페이지는 미래 특정 날짜에 대한 추천 결과를 저장하고, 이후 실제 후보 일정이 공개되었을 때 사후적으로 비교하기 위한 실험 도구이다.”

## 기존 `/evaluation`과의 차이

기존 `/evaluation`은 과거 후보 일정으로 구축한 Gold Set과 output CSV를 이용해 논문용 정량 평가를 수행한다. 기존 성능 수치와 CSV는 보존해야 하며, 모델 비교와 재현성 검증의 기준이다.

신규 `/future-prediction`은 운영 시점의 추천 결과를 먼저 생성한 뒤, 실제 일정이 뒤늦게 공개되면 붙여넣은 CSV와 비교한다. 따라서 기존 Gold Set 평가를 대체하지 않고 캠프 실무 활용 가능성을 보여주는 보조 실험이다.

## 입력 데이터 형식

예측 조건은 다음 값을 사용한다.

- `forecast_date`: 예측 결과를 생성한 날짜
- `target_date`: 실제로 후보가 움직일 것으로 예측하는 날짜
- `candidate_name`: 후보자명
- `districts`: 예측 대상 자치구 목록
- `top_k`: 생성할 추천 개수
- `random_seed`: 같은 조건에서 재현 가능한 실험을 위한 seed

실제 일정 CSV의 최소 컬럼은 다음과 같다.

```csv
date,time,district,place_name,address,event_title,candidate_name
2026-06-01,18:00,강남구,강남역 11번 출구,서울 강남구 강남대로,퇴근길 집중 유세,정원오
```

기존 호환을 위해 `actual_visit_date`, `actual_visit_place_name`, `actual_visit_district`, `actual_visit_address` 컬럼도 읽을 수 있다.

## 추천 결과 생성 방식

페이지는 기존 `/route/recommend` API를 호출해 후보군을 넓게 가져온 뒤, `forecast_date`, `target_date`, `candidate_name`, `random_seed`를 바탕으로 Top-K를 재현 가능하게 선택한다. 추천 결과에는 ranking, 장소명, 자치구, 장소 유형, 추천 점수, 추천 이유, 좌표 상태를 함께 표시한다.

좌표는 `/route`와 같은 공통 좌표 보강 모듈을 사용한다. Kakao 검색과 자치구 검증을 통과한 좌표만 지도 marker로 표시하고, 좌표가 없는 후보는 추천 결과 표와 좌표 확인 필요 목록에 유지한다.

## 실제 일정 붙여넣기 방식

실제 후보 일정이 공개되면 CSV 텍스트를 붙여넣고 “실제 일정과 비교 평가하기”를 실행한다. 평가 전에는 지표가 의미를 갖지 않는다. 후보자명, 대상 날짜, 선택 자치구가 일치하는 실제 일정만 비교 대상으로 사용한다.

## 평가 지표

- `Hit@K`: Top-K 안에 실제 방문 장소와 직접 일치하는 추천이 하나 이상 있으면 1, 없으면 0이다.
- `Precision@K`: Top-K 추천 중 직접 hit로 인정된 추천의 비율이다.
- `NDCG@K`: 장소 일치 정도를 순위 할인하여 계산한다. 상위 추천에서 맞을수록 높다.
- `MRR`: 첫 번째 직접 일치 추천의 역순위이다.

일치 점수는 exact/alias match를 3점, 같은 주소 또는 같은 시설군을 2점, 같은 자치구와 유형을 1점, 불일치를 0점으로 둔다. 기본 hit 기준은 `relevance_score >= 2`이다.

## 한계점

실제 일정 데이터가 없으면 지표는 예시 또는 UI 동작 확인 이상의 의미를 갖지 않는다. 장소명 표기가 다르면 alias 규칙으로도 일부 매칭이 누락될 수 있다. 좌표가 없는 추천은 평가에는 포함되지만 지도 marker로는 표시되지 않는다.

## 논문/발표용 안전 문장

본 시스템의 정량 평가는 기존 Gold Set 기반 `/evaluation`에서 수행하고, `/future-prediction`은 향후 실제 후보 일정이 공개된 뒤 추천 결과와 비교하기 위한 사후 검증 도구로 분리하였다.

기존 Gold Set 평가는 모델 성능 비교와 재현성 검증을 위한 논문용 평가이며, future prediction 평가는 실제 운영 시나리오를 보여주는 보조 실험이다.

미래 일정 예측 지표는 실제 후보 일정 데이터가 입력된 이후에만 해석 가능하며, 기존 논문용 성능 수치를 대체하지 않는다.
