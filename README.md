# 서울시장 선거 캠페인 장소 추천 MVP

서울 공공데이터와 후보 공식 일정 Gold Set을 활용해 캠페인 유세 장소를 추천하고, 추천 결과를 재현 가능한 방식으로 평가하는 프로젝트입니다.

## 평가 Gold Set

입력 파일은 통합 Gold Set CSV 1개만 사용합니다.

```bash
data/full_정원오_gold_set_20260309_20260516.csv
```

이 파일은 2026-03-09부터 2026-05-16까지 정원오 후보 공식 일정표 이미지에서 구축한 Gold Set입니다. 기존의 3개 기간별 CSV를 따로 읽지 않고, 통합 파일 1개를 기준으로 평가 데이터를 만듭니다.

## Gold Label 기준

- `3`: 실제 오프라인 방문, 장소성 명확, 유권자 접촉 가능성 높음. 장소 추천 평가의 strong positive입니다.
- `2`: 공약발표, 정책간담회, 협약식, 직능단체, 종교행사 등 장소 의미는 있으나 직접 유세 장소성은 약한 보조 정답입니다.
- `1`: 방송, 유튜브, 온라인 라이브 등 장소 추천보다 메시지 추천에 가까운 약한 정답입니다.
- `0`: 순수 온라인 또는 장소 정보 부족으로 장소 추천 평가에서 제외합니다.

이번 평가는 추천시스템의 핵심 장소 추천 성능을 확인하기 위해 `gold_label_0_3 == 3`인 오프라인 일정만 strong positive로 사용합니다. 방송, 유튜브, 온라인 일정은 장소 추천 평가에서 제외합니다. `2`점 데이터는 향후 weak positive 평가로, `1`점 데이터는 향후 메시지 추천 평가로 확장할 수 있습니다.

## Gold Set 평가 테이블 생성

```bash
python src/build_gold_eval_set.py \
  --input data/full_정원오_gold_set_20260309_20260516.csv \
  --output_dir output
```

Windows에서 `python` 명령이 Microsoft Store 실행 별칭으로 연결되어 있으면 같은 명령을 `py`로 실행하면 됩니다.

생성 파일:

- `output/gold_set_all_merged.csv`: 통합 Gold Set을 로딩, 중복 제거, 날짜/시간 정리한 전체 데이터
- `output/gold_set_strong_place_only.csv`: `3`점 오프라인 장소 추천 평가용 strong positive 데이터
- `output/gold_set_evaluation_queries.csv`: `query_id`, 평가 문맥, 정답 장소, relevance를 포함한 평가 query 테이블
- `output/gold_set_summary.json`: 전체 row 수, strong positive 수, 기간 범위, 자치구/장소유형/일정유형별 분포

평가 query의 `query_id` 형식은 `YYYY-MM-DD_HH:MM_자치구`입니다.

## 추천 결과 CSV 생성

Gold 평가 query를 기존 추천 알고리즘에 연결해 평가 스크립트가 읽을 수 있는 추천 결과 CSV를 만듭니다.

```bash
py src/generate_recommendation_results.py \
  --gold output/gold_set_evaluation_queries.csv \
  --output output/recommendation_results.csv \
  --top_k 10 \
  --model baseline
```

생성 파일:

- `output/recommendation_results.csv`

컬럼:

- `query_id`
- `rank`
- `recommended_place_name`
- `recommended_district`
- `recommended_place_type`
- `score`

`query_id`는 Gold query의 값을 그대로 사용합니다. 기존 추천 알고리즘의 scoring 로직은 유지하고, 평가용 생성 단계에서 Gold query의 시간, 장소 유형, target voter group, 자치구를 기존 추천기 입력에 맞게 변환합니다.

## Raw Baseline 후보 고정

모델 variant 비교 실험에서는 먼저 기존 rule-based 추천기가 계산한 원시 후보군을 고정 저장합니다. 이 단계의 `baseline_score`는 기존 추천기의 원래 `final_score` 출력값이며, 어떤 feature bonus도 더하지 않습니다.

```bash
py src/generate_raw_baseline_recommendations.py \
  --gold output/gold_set_evaluation_queries.csv \
  --output output/raw_baseline_recommendations.csv \
  --top_k 50
```

생성 파일:

- `output/raw_baseline_recommendations.csv`

주요 컬럼:

- `query_id`
- `date`
- `time`
- `district`
- `place_type`
- `target_voter_group`
- `context_tags`
- `raw_rank`
- `recommended_place_name`
- `recommended_district`
- `recommended_place_type`
- `baseline_score`
- `place_id`
- `candidate_source`

## 모델 Variant 비교 실험

논문용 비교 실험은 5개 추천 모델을 같은 Gold query, 같은 raw baseline 후보군, 같은 K 값으로 평가합니다. 이 단계에서는 기존 추천기를 다시 실행하지 않고 `output/raw_baseline_recommendations.csv`만 읽어 재랭킹합니다.

- `baseline`: 기존 rule-based 추천 알고리즘
- `district_weighted`: query 자치구와 후보 장소 자치구가 같으면 점수 가중
- `place_type_weighted`: Gold query 장소 유형과 후보 장소 유형이 유사하면 점수 가중
- `time_weighted`: query 시간대와 후보 장소 유형의 시간 적합도가 맞으면 점수 가중
- `proposed`: district, place type, time, context tags, target voter group 가중 결합

전체 실험 실행:

```bash
py src/run_model_experiments.py \
  --gold output/gold_set_evaluation_queries.csv \
  --raw output/raw_baseline_recommendations.csv \
  --output_dir output/experiments \
  --top_k 10 \
  --k 1 3 5 10
```

모델별 출력 구조:

```text
output/experiments/
  baseline/
    recommendation_results.csv
    evaluation_result.csv
    evaluation_result_summary.csv
  district_weighted/
    recommendation_results.csv
    evaluation_result.csv
    evaluation_result_summary.csv
  place_type_weighted/
    recommendation_results.csv
    evaluation_result.csv
    evaluation_result_summary.csv
  time_weighted/
    recommendation_results.csv
    evaluation_result.csv
    evaluation_result_summary.csv
  proposed/
    recommendation_results.csv
    evaluation_result.csv
    evaluation_result_summary.csv
  model_comparison.csv
```

최종 비교표 `output/experiments/model_comparison.csv`는 논문 표로 바로 옮길 수 있도록 모델별 `Precision@1/3/5/10`, `Recall@1/3/5/10`, `NDCG@1/3/5/10` 컬럼을 한 행에 정리합니다.

모델별 `recommendation_results.csv`에는 디버깅을 위해 `baseline_score`, `district_bonus`, `place_type_bonus`, `time_bonus`, `context_bonus`, `target_bonus`, 최종 `score`가 함께 저장됩니다.

## Reranking Weight 최적화 실험

성능 개선 실험은 raw baseline 후보군을 고정한 뒤 feature 기반 reranking weight만 탐색합니다. 따라서 기존 rule-based 추천기의 `baseline_score`는 실험 기준선으로 보존되고, 모든 모델은 동일한 후보군에서 출발합니다.

실행:

```bash
py src/optimize_reranking_weights.py \
  --gold output/gold_set_evaluation_queries.csv \
  --raw output/raw_baseline_recommendations.csv \
  --existing_comparison output/experiments/model_comparison.csv \
  --output_dir output/experiments_optimized \
  --top_k 10 \
  --k 1 3 5 10 \
  --search_mode random \
  --n_trials 300 \
  --random_state 42
```

최적화 대상 모델은 `optimized_proposed`입니다. 최종 점수는 다음 구조입니다.

```text
final_score =
  baseline_score * baseline_weight
  + district_bonus * district_weight
  + place_type_bonus * place_type_weight
  + time_bonus * time_weight
  + context_bonus * context_weight
  + target_bonus * target_weight
  + rank_bonus * rank_weight
```

가중치 탐색은 random search를 사용하며, 기본 300 trial을 평가합니다. 최적화 기준은 논문용 종합 점수입니다.

```text
optimization_score =
  0.35 * NDCG@10
  + 0.25 * P@1
  + 0.20 * P@3
  + 0.10 * P@5
  + 0.10 * R@10
```

과적합 방지를 위해 query_id 기준으로 train 70%, validation 30% split을 만들고 `random_state=42`를 고정합니다. 가중치는 train split에서 탐색하고, 선택된 best weight를 validation과 full 70개 query에 다시 평가합니다.

출력 구조:

```text
output/experiments_optimized/
  weight_search_results.csv
  best_weights.json
  model_comparison_optimized.csv
  raw_candidate_coverage.csv
  optimized_proposed/
    recommendation_results.csv
    evaluation_result.csv
    evaluation_result_summary.csv
    feature_contribution_summary.csv
    hit_analysis.csv
  split_evaluation/
    train_result_summary.csv
    validation_result_summary.csv
    full_result_summary.csv
```

`raw_candidate_coverage.csv`는 정답 장소가 raw 후보군 Top50 안에 존재하는지 분석합니다. 정답이 raw 후보군에 없으면 reranking만으로는 맞출 수 없으므로, 논문에서는 후보군 생성 단계의 한계로 해석할 수 있습니다.

## Candidate Generation 한계 분석

최적화된 reranking 이후에도 Recall@10이 0.2714에서 더 오르지 않는 이유를 확인하기 위해 raw 후보군 coverage와 hit/miss를 분석합니다.

```bash
py src/analyze_candidate_generation.py \
  --gold output/gold_set_evaluation_queries.csv \
  --coverage output/experiments_optimized/raw_candidate_coverage.csv \
  --hit output/experiments_optimized/optimized_proposed/hit_analysis.csv \
  --raw output/raw_baseline_recommendations.csv \
  --output_dir output/experiments_optimized
```

출력 파일:

- `output/experiments_optimized/candidate_generation_diagnosis.csv`
- `output/experiments_optimized/missing_gold_by_place_type.csv`
- `output/experiments_optimized/missing_gold_by_district.csv`
- `output/experiments_optimized/hit_vs_miss_summary.csv`

현재 분석 결과, strong positive 70개 query 중 51개는 정답 장소가 raw Top50 후보군에 없고, raw 후보군에 포함된 19개 query는 optimized reranking에서 모두 Top10에 진입했습니다. 따라서 현재 성능의 주요 병목은 reranking보다 candidate generation 단계입니다.

주요 누락 유형:

- `공원`: 11/11개 누락. 하천 산책로, 산 정상/팔각정, 광장, 생활권 야외공간 후보군 확장이 필요합니다.
- `체육시설`: 6/6개 누락. 공공체육시설, 학교/학생체육관, 생활체육 행사장 데이터가 필요합니다.
- `복지시설`: 5/5개 누락. 노인복지시설 외에 종합사회복지관, 장애인복지관, 구립 복지시설을 통합해야 합니다.
- `정책현장`, `노동현장`, `재개발/도시개발현장`, `교통거점`: 현재 MVP 후보 source로 충분히 표현되지 않아 별도 POI/source가 필요합니다.
- `전통시장`: coverage는 상대적으로 높지만, 시장 입구/남문/북문, 통칭, 별칭 불일치가 남아 alias table이 필요합니다.

논문 해석 예시:

```text
Optimized reranking improved early precision and NDCG by promoting district- and context-consistent candidates within the fixed raw candidate set. However, Recall@10 did not improve beyond 0.2714 because only 19 of 70 strong-positive Gold queries had their true venue included in the raw Top-50 candidate pool. This indicates that the main bottleneck after reranking optimization is candidate generation coverage, especially for parks, sports facilities, welfare facilities, policy sites, labor sites, redevelopment sites, and non-station transportation nodes.
```

## 추천 결과 평가

추천시스템 출력은 다음 형식의 CSV로 저장합니다.

```bash
output/recommendation_results.csv
```

필수 컬럼:

- `query_id`
- `rank`
- `recommended_place_name`
- `recommended_district`
- `recommended_place_type`
- `score`

평가 실행:

```bash
python src/evaluate_recommendations.py \
  --gold output/gold_set_evaluation_queries.csv \
  --recommendations output/recommendation_results.csv \
  --output output/evaluation_result.csv \
  --k 1 3 5 10
```

출력 파일:

- `output/evaluation_result.csv`: query별, K별 Precision/Recall/NDCG 상세 결과
- `output/evaluation_result_summary.csv`: K별 macro-average 요약 결과

## 평가 지표

- `Precision@K`: 각 query에서 상위 K개 추천 중 정답 장소로 매칭된 비율
- `Recall@K`: 각 query의 실제 정답 장소 중 상위 K개 추천에 포함된 비율
- `NDCG@K`: relevance를 반영한 순위 품질 지표

NDCG 계산식:

```text
DCG@K = sum((2^rel - 1) / log2(rank + 1))
```

IDCG는 query별 정답 relevance를 이상적으로 정렬해 계산합니다. 현재 strong set의 relevance는 모두 `3`이지만, 평가 코드는 향후 `2`점, `1`점까지 포함하는 확장 평가에도 사용할 수 있게 작성되어 있습니다.

## 장소명 매칭

추천 장소명과 Gold Set 장소명은 다음 순서로 비교합니다.

1. exact match: 원문 장소명이 완전히 같은 경우
2. normalized match: 공백, 괄호, 특수문자 제거 후 같은 경우
3. partial match: 한쪽 장소명이 다른 한쪽에 포함되는 경우
4. district constraint: `recommended_district`가 비어 있지 않으면 Gold Set의 `district`와 같아야 매칭합니다.

결과 CSV는 모두 `utf-8-sig`로 저장해 Excel과 pandas 양쪽에서 안정적으로 열 수 있게 했습니다.

## 웹 시연 API 및 대시보드

기존 `backend/`와 `frontend/`를 유지한 상태에서 Gold Set 평가 산출물을 읽는 웹 시연 레이어를 추가했습니다. 이 레이어는 기존 `output/` CSV를 읽기 전용으로 사용하며, baseline/proposed/optimized 실험 결과를 덮어쓰지 않습니다.

### 백엔드 실행

필요 패키지 설치:

```bash
py -m pip install -r backend/requirements.txt
```

FastAPI 서버 실행:

```bash
py -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

기존 API:

- `POST /recommend`: 기존 rule-based 단일 장소 추천
- `POST /route`: 기존 하루 유세 동선 추천

Gold Set 평가/시연 API:

- `GET /optimized/queries`: `output/gold_set_evaluation_queries.csv`의 70개 strong positive query 목록
- `GET /optimized/recommendations?query_id=...&limit=10`: `optimized_proposed` Top-10 추천 결과와 bonus 디버깅 컬럼
- `GET /evaluation/dashboard`: `model_comparison_optimized.csv`, split 평가, feature contribution 요약
- `GET /coverage/dashboard`: raw 후보군 coverage, 누락 장소 유형/자치구/일정 유형 진단

### 프론트엔드 실행

```bash
cd frontend
npm run dev
```

브라우저에서 확인:

- `http://127.0.0.1:3000/`: 캠프비서 AI 홈 대시보드
- `http://127.0.0.1:3000/demo`: Gold query별 `optimized_proposed` 추천 Top-10 화면
- `http://127.0.0.1:3000/evaluation`: 모델 성능 비교 및 candidate generation 병목 대시보드

프론트엔드는 `NEXT_PUBLIC_API_BASE_URL`이 있으면 해당 값을 API 서버 주소로 사용하고, 없으면 기본값 `http://127.0.0.1:8000`을 사용합니다.

### 캠프비서 AI 모바일 UI

프론트엔드는 `캠프비서 AI` 콘셉트에 맞춰 모바일 우선 운영 도구 형태로 정리했습니다.

- `/`: 오늘의 운영 홈 대시보드. 다음 일정, Gold query 수, raw 후보군 수, Hit@10, 주간 활동, 지도 프리뷰를 표시합니다.
- `/demo`: AI 장소 추천 화면. Gold query를 선택하면 `optimized_proposed` Top-10 추천, 추천 이유, `baseline_score`와 feature bonus breakdown을 확인할 수 있습니다.
- `/evaluation`: 평가 대시보드. `model_comparison_optimized.csv`, raw candidate coverage, 누락 장소 유형, feature contribution을 시각화합니다.

공통 UI 컴포넌트는 `frontend/app/components/camp/CampUI.js`에 모아두었고, 색상과 모바일 카드/탭/차트 스타일은 `frontend/app/globals.css`의 디자인 토큰으로 관리합니다. Tailwind를 새로 설치하지 않고도 Tailwind식 토큰 구조와 재사용 컴포넌트 구조를 따르도록 구성했습니다.

### 제품형 UI 고도화

출시 가능한 웹앱에 가깝게 보이도록 Apple Human Interface Guidelines에 가까운 절제된 디자인 시스템을 적용했습니다.

- 디자인 토큰: `#F5F5F7` 계열 off-white 배경, 흰색 surface, `#1D1D1F` 텍스트, `#FF9500` 오렌지 accent를 사용합니다.
- 레이아웃: 모바일은 하단 탭 기반 앱 구조, 데스크톱은 좌측 사이드 내비게이션과 2-column dashboard 구조를 사용합니다.
- 상태 처리: API loading, error, empty 상태를 공통 `LoadingState`, `ErrorState`, `EmptyState` 컴포넌트로 처리합니다.
- 데이터 시각화: 외부 차트 의존성 없이 CSS 기반 bar chart, metric chart, missing place type chart를 사용합니다.
- 접근성: focus-visible, aria-label, 충분한 색 대비, safe-area bottom padding을 반영했습니다.
- 제품용 카피: `raw 후보군`, `hit@10`, `candidate generation coverage`처럼 내부 실험 용어가 먼저 보이지 않도록 `초기 후보군`, `Top-10 적중`, `후보군 포함률` 등으로 정리했습니다.
- 핵심 지표 표시: Gold Set 186, Strong Positive 70, Raw Candidates 2,871, P@1 0.0714, P@3 0.0571, P@5 0.0457, R@10 0.2714, NDCG@10 0.1682, raw recall@50 27.1%가 실제 CSV/API 기반으로 표시되도록 보강했습니다.

Production build 확인:

```bash
cd frontend
npm run build
```

교수님 시연 추천 순서:

1. `/`에서 `캠프비서 AI`의 제품 포지셔닝과 핵심 지표를 보여줍니다.
2. `/demo`에서 Gold query를 선택하고 optimized_proposed Top-10 추천, 추천 이유, score breakdown을 설명합니다.
3. `/evaluation`에서 baseline 대비 optimized_proposed 개선폭과 NDCG@10을 보여줍니다.
4. 같은 화면의 coverage bottleneck 카드에서 Recall@10 한계가 raw candidate coverage에 의해 제한된다는 점을 설명합니다.
5. Missing Place Type Chart를 통해 공원, 체육시설, 복지시설 등 후보군 생성 단계 보강 필요성을 후속 과제로 제시합니다.

데이터 누락 시 확인할 것:

1. FastAPI 서버가 `py -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload`로 실행 중인지 확인합니다.
2. `output/gold_set_summary.json`, `output/raw_baseline_recommendations.csv`, `output/experiments_optimized/model_comparison_optimized.csv`, `output/experiments_optimized/raw_candidate_coverage.csv`가 존재하는지 확인합니다.
3. API 연결은 다음 명령으로 확인할 수 있습니다.

```bash
curl http://127.0.0.1:8000/optimized/queries
curl http://127.0.0.1:8000/optimized/recommendations
curl http://127.0.0.1:8000/evaluation/dashboard
curl http://127.0.0.1:8000/coverage/dashboard
```

### 웹 시연에서 읽는 실제 산출물

- `output/gold_set_evaluation_queries.csv`
- `output/experiments_optimized/optimized_proposed/recommendation_results.csv`
- `output/experiments_optimized/model_comparison_optimized.csv`
- `output/experiments_optimized/raw_candidate_coverage.csv`
- `output/experiments_optimized/candidate_generation_diagnosis.csv`
- `output/experiments_optimized/missing_gold_by_place_type.csv`
- `output/experiments_optimized/missing_gold_by_district.csv`
- `output/experiments_optimized/hit_vs_miss_summary.csv`

따라서 웹 화면은 mock 데이터가 아니라, Gold Set 평가 파이프라인과 optimized reranking 실험에서 생성된 실제 CSV 결과를 그대로 시각화합니다. 논문 시연 흐름은 다음과 같이 구성할 수 있습니다.

1. Gold Set strong positive query 70개를 기준으로 평가 query를 생성한다.
2. raw baseline 후보군 Top50을 고정해 동일 후보군에서 reranking 실험을 수행한다.
3. `optimized_proposed`가 early precision과 NDCG@10을 개선하는지 확인한다.
4. `raw_candidate_coverage.csv`와 candidate generation 진단 파일로 Recall@10 병목이 후보군 생성 coverage에 있음을 설명한다.
5. 웹 대시보드에서 query별 추천 결과, feature bonus, 모델 비교표, 누락 장소 유형을 함께 제시한다.

## 선거비서 AI User App 구조

웹 시연의 첫 경험을 연구/평가 화면이 아니라 후보자와 캠프 실무자가 사용할 수 있는 운영 앱으로 재구성했습니다. 서비스명은 `선거비서 AI`이며, 사용자용 기능과 논문/개발자용 평가 화면을 분리합니다.

라우트 구조:

- `/`: 후보자용 운영 홈. 내일 동선 추천 CTA, 다음 추천 일정, 지도 preview, 추천 타임라인 preview, 운영 인사이트를 표시합니다.
- `/route`: 하루 유세 동선 추천 화면. 시작 위치, 날짜, 시간, 방문 자치구, 타깃 유권자, 캠페인 목적, 선호 장소 유형을 입력하면 지도 preview와 시간대별 타임라인을 생성합니다.
- `/recommend`: 단일 평가 기준 일정 기반 Top-K 장소 추천 상세 화면. 기존 `/demo`와 같은 optimized 추천 결과를 제품용 경로로 제공합니다.
- `/demo`: 기존 연구용 링크 호환을 위해 유지합니다.
- `/evaluation`: 논문/개발자용 Gold Set 평가 대시보드. Precision@K, Recall@K, NDCG@K, 모델 비교, 후보군 포함률 병목, 누락 장소 유형 분석을 표시합니다.

### 동선 추천 API

새로운 API는 기존 `POST /route` MVP 엔드포인트를 깨지 않고 `/route/...` 하위에 추가했습니다.

- `GET /route/options`: 동선 추천 폼에 필요한 자치구, 타깃 유권자, 캠페인 목적, 장소 유형, 기본 요청값을 반환합니다.
- `POST /route/recommend`: 입력 조건을 받아 하루 유세 동선을 추천합니다.
- `GET /route/sample`: 교수님 시연과 프론트 초기 화면에 사용할 기본 동선 추천 결과를 반환합니다.

예시:

```bash
curl -X POST http://127.0.0.1:8000/route/recommend \
  -H "Content-Type: application/json" \
  -d "{\"date\":\"2026-05-20\",\"start_time\":\"09:00\",\"end_time\":\"18:00\",\"start_location\":\"성동구청\",\"districts\":[\"성동구\",\"중구\"],\"target_voter_group\":\"직장인\",\"campaign_goal\":\"퇴근인사\",\"preferred_place_types\":[\"교통거점\",\"골목상권\",\"전통시장\"],\"num_visits\":5,\"avoid_duplicates\":true}"
```

### 동선 추천 로직

`backend/services/route_service.py`는 기존 optimized 추천 결과와 raw baseline 후보군을 읽기 전용으로 사용합니다. 기존 `baseline_score`와 평가 CSV는 수정하지 않습니다.

동선 점수 구조:

```text
route_score =
  optimized_place_score
  + time_slot_fit_score
  + target_voter_fit_score
  + district_fit_score
  + diversity_bonus
  - duplicate_visit_penalty
  - travel_distance_penalty
```

- `optimized_place_score`: `output/experiments_optimized/optimized_proposed/recommendation_results.csv`의 최종 추천 점수 또는 raw baseline 후보 점수를 재사용합니다.
- `time_slot_fit_score`: 출근/오전/점심/오후/퇴근 시간대별로 교통거점, 전통시장, 골목상권, 공원, 복지시설, 정책현장 적합도를 반영합니다.
- `target_voter_fit_score`: 직장인, 청년, 상인, 노년층, 가족/어린이, 지역주민과 장소 유형의 적합도를 반영합니다.
- `district_fit_score`: 희망 자치구 일치와 인접 생활권을 반영합니다.
- `diversity_bonus`: 하루 일정 안에서 장소 유형과 자치구가 지나치게 반복되지 않도록 보정합니다.
- `duplicate_visit_penalty`: 사용자가 중복 감점을 켠 경우 `output/gold_set_strong_place_only.csv`를 최근 방문 이력처럼 사용해 동일 장소, 동일 자치구, 동일 유형 반복을 감점합니다.
- `travel_distance_penalty`: 좌표가 부족한 현재 단계에서는 같은 자치구/인접 자치구/먼 자치구 기준으로 mock 이동 시간을 계산합니다.

### 지도 Mock 및 확장 계획

현재 산출물에는 모든 장소의 위경도가 안정적으로 포함되어 있지 않으므로 `/route` 화면은 `map_position.mock_x`, `map_position.mock_y`를 사용하는 CSS 기반 지도 preview를 제공합니다.

구조는 다음 컴포넌트로 분리되어 있습니다.

- `RouteMapPreview`
- `RouteMarker`
- `RoutePath`
- `MapFloatingCard`

향후 확장 계획:

- geocoding으로 `address` 또는 장소명을 `lat/lng`로 변환
- Leaflet + OpenStreetMap `TileLayer`, `Marker`, `Polyline` 연동
- 실제 이동 시간은 OSRM, Kakao/Naver Directions API 등으로 교체
- 후보자의 현재 위치는 브라우저 Geolocation 또는 수동 입력 둘 다 지원

### 최신 교수님 시연 순서

1. `/`에서 `선거비서 AI`가 후보자용 운영 앱으로 동작한다는 점을 보여줍니다.
2. `/route`에서 시작 위치, 날짜, 자치구, 타깃 유권자를 입력하고 하루 유세 동선을 생성합니다.
3. 지도 preview에서 번호 마커와 연결선을 설명하고, 타임라인에서 추천 이유와 점수 구성을 보여줍니다.
4. `/recommend`에서 단일 장소 Top-K 추천과 score breakdown을 확인합니다.
5. `/evaluation`에서 논문용 Gold Set 평가 결과와 `optimized_proposed` 성능 수치를 설명합니다.
6. coverage 병목 카드와 missing place type chart를 통해 현재 한계와 후보군 생성 개선 방향을 제시합니다.

검증 명령:

```bash
py -m py_compile backend/main.py backend/services/dashboard_service.py backend/services/route_service.py

cd frontend
npm run build
```

확인해야 하는 핵심 성능 수치는 기존과 동일합니다.

- `P@1 = 0.0714`
- `P@3 = 0.0571`
- `P@5 = 0.0457`
- `R@10 = 0.2714`
- `NDCG@10 = 0.1682`
