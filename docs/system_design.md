# System Design

## 1. 프로젝트 목표

서울시 공공데이터를 활용해 시간대, 장소 유형, 타깃 연령대에 맞는 유세 장소와 메시지를 추천하는 파일럿 MVP를 구현하는 것이 목표다.  
현재 시스템은 복잡한 머신러닝 모델 대신 설명 가능한 rule-based + weighted scoring 구조를 사용해, 발표와 검증이 쉬운 형태로 설계되어 있다.

## 2. 현재 MVP 기능

- 단일 추천
  - 입력: `time_slot`, `place_type`, `target_age_group`
  - 출력: 추천 장소 Top 3, 점수, 추천 이유, 메시지 Top 3
- 동선 추천
  - 입력: `target_age_group`, `route_template`
  - 출력: 시간대별 추천 장소와 메시지를 묶은 하루 유세 동선
- API 제공
  - `/health`, `/recommend`, `/route`
- 웹 데모 제공
  - 단일 추천과 동선 추천을 브라우저에서 바로 실행 가능

## 3. 데이터셋 구성

### 핵심 추천 데이터셋

- 지하철 승하차 데이터
  - 출근/오후 시간대 유동량 기반 장소 추천
- 주요 공원 데이터
  - 공원 규모, 시설 정보 기반 추천
- 노인여가복지시설 데이터
  - `senior_friendly` 장소 추천
- 전통시장 데이터
  - 생활권 중심 유세 장소 추천

### 보조 데이터셋

- 상권 유동인구 데이터
  - 시간대 맥락 보정
- 상권 직장인구 데이터
  - `20_40`, `60_plus` 연령 보정
- 행정동 생활인구 데이터
  - 시간대/연령대 생활권 맥락 보정

### 데이터 처리 방식

- 원본 CSV는 `data` 폴더에 저장
- 전처리 결과는 `data/processed`에 저장
- 추천기는 `cleaned_*.csv`와 `aux_feature_summary.json`을 직접 읽어 사용
- DB 없이 로컬 CSV 기반으로 동작

## 4. Weighted Scoring 추천 구조

추천기는 장소 유형별로 후보를 만든 뒤, 아래 4개 feature를 계산한다.

- `time_match_score`
  - 입력 시간대와 장소의 시간대 적합성
- `age_match_score`
  - 타깃 연령대와 장소 맥락의 적합성
- `context_score`
  - 장소 유형, 지역 맥락, 상권/생활인구 보조 정보
- `facility_score`
  - 장소 자체의 물리적 규모나 활용성

최종 점수는 weighted sum 구조를 사용한다.

```text
final_score =
  w1 * time_match_score
  + w2 * age_match_score
  + w3 * context_score
  + w4 * facility_score
```

장소 유형별로 가중치는 다르게 설정되어 있다.

- `subway`
  - 시간대 유동량 비중이 가장 큼
- `park`
  - 시설/공원 규모와 맥락 비중이 큼
- `senior_friendly`
  - 연령 적합성과 시설 적합성 비중이 큼
- `market`
  - 점포 수, 연면적, 시장 유형 비중이 큼

또한 `aux_feature_summary.json`의 평균 요약값을 약한 보조 보정치로 사용한다.

- commercial flow
- worker population
- living population

이 보정치는 기존 핵심 점수를 대체하지 않고, `age_match_score`와 `context_score`를 소폭 조정하는 용도로만 사용한다.

## 5. 메시지 추천 구조

메시지 추천은 `scripts/message_rules.py`의 rule-based 모듈로 구성되어 있다.

- `subway + 20_40`
  - 청년 일자리
  - 출퇴근 교통 개선
  - 주거비 부담 완화
- `park + 20_40`
  - 가족 친화 정책
  - 여가/문화 인프라 확대
  - 생활체육·공원 개선
- `senior_friendly + 60_plus`
  - 어르신 복지 강화
  - 의료 접근성 개선
  - 교통약자 이동 편의 확대
- 그 외 조합
  - 기본 fallback 메시지 사용

즉, 현재 메시지 추천은 정교한 NLP 모델이 아니라 장소 유형과 연령대 조합에 따라 설명 가능한 정책 카테고리를 반환하는 구조다.

## 6. Route Planner 구조

동선 추천은 `scripts/route_planner.py`에서 수행한다.

### 입력

- `target_age_group`
- `route_template`

### 지원 템플릿

- `default`
  - 07:00 / subway
  - 11:00 / park
  - 14:00 / senior_friendly
  - 18:00 / subway
- `neighborhood_focus`
  - 10:00 / market
  - 13:00 / park
  - 15:00 / senior_friendly
  - 18:00 / subway

### 동작 방식

- 각 슬롯마다 `recommend_places()` 호출
- 각 슬롯마다 `recommend_messages()` 호출
- 상위 1개 장소를 선택
- 이미 선택된 장소명은 중복 제거
- 결과를 시간 순서 리스트로 반환

즉, route planner는 추천 엔진을 여러 번 호출해 하루 일정 형태로 묶는 orchestration 계층이다.

## 7. API 구성

FastAPI 기반 백엔드가 `backend/main.py`에 구현되어 있다.

### 엔드포인트

- `GET /health`
  - 상태 확인
- `POST /recommend`
  - 입력: `time_slot`, `place_type`, `target_age_group`
  - 출력: `input`, `places`, `messages`
- `POST /route`
  - 입력: `target_age_group`, `route_template`
  - 출력: `target_age_group`, `route_template`, `route`

### 특징

- Pydantic 모델로 요청/응답 검증
- 잘못된 입력은 400 계열 에러로 처리
- CORS 허용으로 Next.js 프론트와 직접 연동 가능

## 8. 프론트 구성

프론트는 Next.js 단일 페이지 앱으로 구성되어 있다.

### 주요 화면

- Single Recommendation
  - `time_slot`, `place_type`, `target_age_group` 선택
  - `/recommend` 호출
- Campaign Route
  - `target_age_group`, `route_template` 선택
  - `/route` 호출

### 화면 출력

- 입력 요약
- 추천 장소 Top 3
- 추천 메시지 Top 3
- 시간대별 route 카드
- 로딩 상태와 에러 상태 표시

발표용 MVP에 맞춰 복잡한 페이지 분리 없이 한 화면에서 모든 기능을 시연할 수 있게 설계했다.

## 9. 향후 고도화 방향

- 실제 위치 매핑 고도화
  - 지하철역, 공원, 시장, 복지시설과 행정동/상권을 더 정확히 연결
- 더 세밀한 시간대 모델링
  - weekday/weekend, 세부 시간 슬롯 반영
- 개인화/학습 기반 추천
  - 실제 반응 데이터나 유세 성과 데이터를 이용한 랭킹 학습
- 메시지 추천 고도화
  - rule-based를 넘어 LLM 또는 텍스트 분류 모델 활용
- 운영 데이터 연결
  - 일정 관리, 현장 피드백, 로그 수집 기능 추가
- 시각화 강화
  - 지도 기반 route 표시, 실험 비교 대시보드 제공

현재 MVP는 “설명 가능하고 빠르게 시연 가능한 추천 시스템”에 초점을 맞춘 상태이며, 이후에는 데이터 연결성과 정교한 점수 학습이 주요 확장 방향이다.
