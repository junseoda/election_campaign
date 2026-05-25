# Codex 작업 요약 보고서

## 1. 전체 개발 요약

이 프로젝트는 “서울시 공공데이터와 실제 후보 일정 기반 유세 장소 추천 시스템”으로, 단순 시각화 웹앱이 아니라 데이터 수집, 후보 장소 생성, 추천, 평가, 병목 분석, 시각화/웹앱 시연까지 연결된 파이프라인으로 구현되어 있다. 원본 서울시 공공데이터는 전처리 스크립트를 거쳐 지하철, 공원, 전통시장, 노인복지시설, 상권 유동인구, 직장인구, 생활인구 feature 테이블로 정리된다. 실제 후보 공개 일정표에서 구축한 정원오 후보 Gold Set 186건 중 오프라인 장소 추천 strong positive 70건을 평가 query로 만들고, 기존 rule-based 추천기가 생성한 raw Top50 후보군을 고정한다. 이후 baseline, district/place/time/proposed, optimized_proposed 모델을 같은 raw 후보군에서 재랭킹해 Precision@K, Recall@K, NDCG@K로 비교한다. 실험 결과 optimized_proposed는 NDCG@10을 0.1105에서 0.1682로 올렸지만 Recall@10은 0.2714로 유지되어 병목이 재랭킹보다 candidate generation coverage에 있음을 분석했다. 프론트엔드는 Next.js App Router 기반의 `/route`, `/recommend`, `/evaluation`, `/map` 화면과 Kakao 지도 연동을 제공하며, 백엔드는 FastAPI로 추천/평가/동선 API를 제공한다. Git 기준 작업 트리는 깨끗하고, 최근 커밋은 Vercel/Render 배포 설정, Kakao 지도 CSP 및 타일 렌더링, 드래그 인터랙션, route UI 정리 중심이다.

## 2. 전체 시스템 구조

| 계층 | 관련 파일 | 핵심 역할 | 입력 데이터 | 출력 데이터 |
|---|---|---|---|---|
| 데이터 입력 계층 | `data/*.csv`, `data/full_정원오_gold_set_20260309_20260516.csv`, `gold set수작업/...csv` | 서울시 원본 공공데이터와 실제 후보 일정 Gold Set 보관 | 지하철 승하차, 공원, 시장, 복지시설, 상권/직장/생활인구, 후보 일정 | 원본 CSV |
| 데이터 처리 구조 | `scripts/clean_*.py`, `scripts/build_aux_feature_summary.py`, `data/processed/*.csv`, `data/processed/aux_feature_summary.json` | 원본 컬럼 표준화, 숫자 변환, 중복 제거, 보조 feature 요약 | 원본 CSV | cleaned CSV, aux summary |
| 후보 장소 생성 계층 | `scripts/recommender.py`, `src/generate_recommendation_results.py`, `src/generate_raw_baseline_recommendations.py` | 장소 유형별 후보 생성, Gold query를 추천기 입력으로 변환, raw Top50 고정 | Gold query, cleaned CSV | `output/raw_baseline_recommendations.csv`, `output/recommendation_results.csv` |
| 추천 알고리즘 계층 | `scripts/recommender.py`, `scripts/message_rules.py`, `scripts/route_planner.py` | time/age/context/facility/interaction 기반 rule-based weighted scoring | time_slot, place_type, target_age_group | 장소 Top-K, 메시지, 기본 동선 |
| 재랭킹 및 최적화 계층 | `src/run_model_experiments.py`, `src/optimize_reranking_weights.py` | fixed raw candidate 기반 variant 재랭킹, random/grid weight search | raw baseline, Gold query | `model_comparison.csv`, `model_comparison_optimized.csv`, `best_weights.json` |
| 평가 계층 | `src/build_gold_eval_set.py`, `src/evaluate_recommendations.py` | strong positive 70건 구성, P@K/R@K/NDCG@K 계산 | 통합 Gold Set, 추천 결과 CSV | `gold_set_evaluation_queries.csv`, `evaluation_result*.csv` |
| 분석 계층 | `src/analyze_candidate_generation.py`, `output/experiments_optimized/*diagnosis*.csv` | raw 후보군 coverage, hit/miss, 누락 장소 유형/자치구 분석 | raw coverage, hit_analysis, Gold query | `candidate_generation_diagnosis.csv`, `missing_gold_by_place_type.csv` |
| 백엔드 API 계층 | `backend/main.py`, `backend/services/dashboard_service.py`, `backend/services/route_service.py` | 추천/평가/coverage/동선 API 제공, CSV 읽기 전용 서비스 | output CSV, route 요청 | JSON API |
| 프론트엔드 시각화 계층 | `frontend/app/page.js`, `frontend/app/route/page.js`, `frontend/app/demo/page.js`, `frontend/app/evaluation/page.js`, `frontend/app/map/page.js`, `frontend/app/components/*` | 운영 앱, 단일 추천, 평가 대시보드, 지도/타임라인 시연 | FastAPI JSON 또는 정적 fallback JSON | 웹 화면 |
| 배포 계층 | `frontend/next.config.mjs`, `frontend/DEPLOYMENT.md`, `.vercel/project.json`, `render.yaml` | Next.js/Vercel, FastAPI/Render 배포 설정, CSP/CORS | env, build config | 배포 가능한 프론트/백엔드 |

확인 사항: 루트 `package.json`은 없음. 실제 Node 설정은 `frontend/package.json`에만 있다. 사용자가 적은 `frontend/components/KakaoRouteMap.js`는 실제로 없고, 구현 파일은 `frontend/app/components/map/KakaoRouteMap.js`이며 `frontend/app/components/RouteMap.js`가 re-export한다. 사용자가 적은 `output/experiments/model_comparison_optimized.csv`와 `output/experiments/optimized_proposed/hit_analysis.csv`도 실제 경로는 각각 `output/experiments_optimized/model_comparison_optimized.csv`, `output/experiments_optimized/optimized_proposed/hit_analysis.csv`다.

## 3. 주요 구현 기능

| 기능명 | 구현 위치 | 핵심 코드/파일 | 입력 데이터 | 출력 결과 | 사용자가 보는 화면 | 논문에서 설명 가능한 기술적 의미 |
|---|---|---|---|---|---|---|
| 단일 장소 추천 기능 | 백엔드 `/recommend`, 프론트 `/recommend` | `backend/main.py`, `scripts/recommender.py`, `frontend/app/demo/page.js`, `frontend/app/recommend/page.js` | time/place/target 또는 Gold query | Top-K 장소, 점수 breakdown | `/recommend` | 공공데이터 feature 기반 장소 랭킹 |
| 후보자 동선 추천 기능 | `/route/recommend`, `/route/sample` | `backend/services/route_service.py`, `frontend/app/route/page.js` | 날짜, 시간, 출발지, 자치구, 타깃, 목적, 선호 장소 | 시간대별 방문 지점, 점수 구성, 이동 부담 | `/route` | 단일 추천을 하루 운영 동선으로 확장 |
| 평가 대시보드 | `/evaluation/dashboard`, `/coverage/dashboard` | `backend/services/dashboard_service.py`, `frontend/app/evaluation/page.js` | 실험 CSV, Gold summary, coverage CSV | 모델 비교, coverage, 누락 유형 시각화 | `/evaluation` | 추천시스템 평가와 병목 분석을 한 화면에 제시 |
| Kakao 지도 기반 경로 시각화 | 프론트 지도 컴포넌트 | `frontend/app/components/map/KakaoRouteMap.js`, `frontend/next.config.mjs` | route stops, env key | 지도, marker, polyline, fallback map | `/route`, `/map`, `/` | 추천 결과를 공간적 동선으로 시연 |
| 장소명 normalization | route service, evaluator | `backend/services/route_service.py:place_name_normalizer`, `src/evaluate_recommendations.py:normalize_place_key` | 추상 장소명, Gold 장소명 | 실제 유세 지점식 표시, robust matching | `/route`, 평가 CSV | 장소명 alias/표기 차이 대응 |
| raw baseline 후보군 생성 | 평가 pipeline | `src/generate_raw_baseline_recommendations.py` | Gold query 70건, 기존 recommender | raw Top50 후보군 2,871 row | 평가/대시보드 내부 | 재랭킹 실험의 공정성 확보 |
| model variant 재랭킹 | 실험 pipeline | `src/run_model_experiments.py` | fixed raw candidate | baseline/district/place/time/proposed 결과 | `/evaluation` | 동일 후보군 조건에서 feature 기여 비교 |
| weight search 최적화 | 실험 pipeline | `src/optimize_reranking_weights.py` | raw candidate, Gold query | optimized_proposed, best_weights | `/evaluation` | 설명 가능한 가중치 탐색 기반 성능 개선 |
| candidate generation 병목 분석 | 분석 pipeline | `src/analyze_candidate_generation.py` | raw coverage, hit_analysis | 누락 장소 유형/자치구/활동 유형 분석 | `/evaluation` | 성능 한계를 재랭킹과 후보군 생성으로 분해 |
| 정적 데모 fallback | 프론트 배포 | `frontend/public/data/*.json`, `CampUI.js` | 정적 JSON | API 미연결 시 데모 데이터 | 전체 프론트 | 배포 환경에서도 시연 안정성 확보 |

## 4. 추천 알고리즘 구현 요약

`query`는 `output/gold_set_evaluation_queries.csv`의 한 행이다. 주요 필드는 `query_id`, `date`, `time`, `district`, `place_type`, `campaign_activity_type`, `target_voter_group`, `context_tags`, `place_name`, `relevance`다. `candidate place`는 `scripts/recommender.py`가 `cleaned_subway.csv`, `cleaned_parks.csv`, `cleaned_market.csv`, `cleaned_senior.csv` 등에서 생성한 후보 장소이며, raw 실험에서는 `output/raw_baseline_recommendations.csv`의 `recommended_place_name`, `recommended_district`, `recommended_place_type`, `baseline_score`, `raw_rank`로 고정된다.

원 추천기의 feature score는 `time_match_score`, `age_match_score`, `context_score`, `facility_score`, `interaction_score`다. 장소 유형별 가중치는 `scripts/recommender.py`의 `PLACE_TYPE_WEIGHTS`에 정의되어 있으며, 예를 들어 subway는 time 비중 0.45, park는 facility 비중 0.38, senior는 age/facility 비중이 크다. 원 추천기의 `final_score`는 다음 구조다.

```text
final_score =
  time_match_score * w_time
  + age_match_score * w_age
  + context_score * w_context
  + facility_score * w_facility
  + interaction_score * w_interaction
```

재랭킹 실험의 `baseline_score`는 raw candidate 생성 시 기존 추천기의 `final_score`를 그대로 저장한 값이다. 실험 코드에서는 `district_score`, `place_type_score`, `time_score`, `context_score`, `target_score`, `rank_score`가 각각 `district_bonus`, `place_type_bonus`, `time_bonus`, `context_bonus`, `target_bonus`, `rank_bonus`라는 컬럼명으로 구현되어 있다.

| 점수 | 코드명 | 정의 |
|---|---|---|
| baseline_score | `baseline_score` | 기존 rule-based 추천기의 최종 점수 |
| district_score | `district_bonus` | query 자치구와 후보 자치구 일치 1.0, 인접 0.45, 권역 동일 0.25 |
| place_type_score | `place_type_bonus` | Gold 문맥에서 추론한 장소 범주와 후보 유형 일치 또는 관련도 |
| time_score | `time_bonus` | 시간대별 후보 유형 적합도. 출근/퇴근은 subway, 점심/오후는 market/park 등 |
| context_score | `context_bonus` | `context_tags`, target, 후보명/source의 키워드 또는 의미 범주 일치 |
| target_score | `target_bonus` | 노년층-복지, 상인-시장, 직장인-교통, 가족-공원 등 타깃 적합도 |
| rank_score | `rank_bonus` | `1 - ((raw_rank - 1) / 49)`, raw 순위를 약하게 보존 |

optimized reranking의 최종 점수는 `src/optimize_reranking_weights.py`의 `rerank_candidates()`에 구현되어 있다.

```text
score =
  baseline_score * baseline_weight
  + district_bonus * district_weight
  + place_type_bonus * place_type_weight
  + time_bonus * time_weight
  + context_bonus * context_weight
  + target_bonus * target_weight
  + rank_bonus * rank_weight
```

`best_weights.json` 기준 최적 가중치는 `baseline=1.0`, `district=0.5`, `place_type=0.3`, `time=0.1`, `context=0.2`, `target=0.05`, `rank=0.05`다. raw candidate generation은 후보를 새로 만드는 단계이고, reranking은 이미 생성된 raw 후보군 내부 순서를 바꾸는 단계다. `baseline`은 기존 점수만 사용하고, `proposed`는 district/place/time/context/target 보정을 단순 결합하며, `optimized_proposed`는 train split에서 탐색한 가중치를 적용한다. 이 구조는 rule-based이지만 query, candidate, relevance, ranked list, P@K/R@K/NDCG@K를 갖추었기 때문에 추천시스템 평가 구조로 확장되어 있다.

의사코드:

```text
for query in gold_queries:
    candidate_pool = run_existing_recommenders(query)  # raw generation
    raw_top50 = freeze(candidate_pool, baseline_score)

for model in variants:
    for candidate in raw_top50[query]:
        features = calc_district/place/time/context/target/rank(candidate, query)
        score = weighted_sum(baseline_score, features)
    ranked_top10 = sort_by(score)
    evaluate ranked_top10 against gold place
```

## 5. 평가 파이프라인 구현 요약

Gold Set 입력은 `data/full_정원오_gold_set_20260309_20260516.csv`이며, `src/build_gold_eval_set.py`가 이를 읽어 평가용 CSV를 생성한다. strong positive 70건은 `gold_label_0_3 == 3`, `online_offline`이 오프라인, `use_for_place_recommendation`이 참, `place_name`, `district`, `address`가 비어 있지 않고 “확인 필요/해당 없음”이 아닌 조건으로 선별된다. 전체 Gold Set은 186건이고 기간은 2026-03-09부터 2026-05-16까지다.

`query_id`는 `YYYY-MM-DD_HH:MM_자치구` 형식으로 생성된다. raw baseline 후보군은 `src/generate_raw_baseline_recommendations.py`가 query별 후보를 최대 50개 저장하며, 실제 산출물은 70 query, 2,871 row, query당 13~50개 후보다. raw 후보군 고정의 의미는 모든 모델이 동일 후보군에서 출발해 재랭킹만 비교한다는 것이다.

평가는 `src/evaluate_recommendations.py`에서 query별로 exact, normalized, partial match를 순서대로 수행하고, 후보 자치구가 있으면 Gold 자치구와 같아야 한다. Precision@K는 `hits / K`, Recall@K는 `hits / total_relevant`, NDCG@K는 `(2^rel - 1) / log2(rank + 1)` 기반 DCG를 IDCG로 나누어 계산한다. 현재 strong positive는 query당 관련 장소 1개와 relevance 3으로 구성되어 있으나, 코드는 향후 약한 positive까지 확장 가능하다.

weight search는 `src/optimize_reranking_weights.py`가 수행한다. query_id 기준 train 49건, validation 21건으로 분할하고, `random_state=42`, `search_mode=random`, 요청 trial 300개에 required trial 3개가 더해져 총 303 trial이 평가되었다. 최적화 목적식은 `0.35*NDCG@10 + 0.25*P@1 + 0.20*P@3 + 0.10*P@5 + 0.10*R@10`이다. best weight와 train/validation/full metric은 `output/experiments_optimized/best_weights.json`에 저장된다.

CSV 저장 구조는 다음과 같다.

| 파일 | 내용 |
|---|---|
| `output/gold_set_all_merged.csv` | 정리된 전체 Gold Set 186건 |
| `output/gold_set_strong_place_only.csv` | strong positive 70건 |
| `output/gold_set_evaluation_queries.csv` | 평가 query 70건 |
| `output/raw_baseline_recommendations.csv` | 고정 raw 후보군 2,871건 |
| `output/experiments/model_comparison.csv` | baseline/proposed 계열 비교 |
| `output/experiments_optimized/model_comparison_optimized.csv` | optimized_proposed 포함 비교 |
| `output/experiments_optimized/optimized_proposed/hit_analysis.csv` | query별 hit@1/3/5/10 및 reason_estimate |
| `output/experiments_optimized/raw_candidate_coverage.csv` | raw Top50에 정답 포함 여부 |
| `output/experiments_optimized/candidate_generation_diagnosis.csv` | 병목 진단 |

## 6. 실험 결과 요약

`output/experiments_optimized/model_comparison_optimized.csv` 기준 실제 수치다.

| Model | P@1 | P@3 | P@5 | Recall@10 | NDCG@10 |
|---|---:|---:|---:|---:|---:|
| baseline | 0.0286 | 0.0095 | 0.0200 | 0.2714 | 0.1105 |
| district_weighted | 0.0429 | 0.0286 | 0.0371 | 0.2714 | 0.1334 |
| place_type_weighted | 0.0286 | 0.0095 | 0.0200 | 0.2714 | 0.1105 |
| time_weighted | 0.0286 | 0.0095 | 0.0200 | 0.2714 | 0.1105 |
| proposed | 0.0429 | 0.0286 | 0.0371 | 0.2714 | 0.1334 |
| optimized_proposed | 0.0714 | 0.0571 | 0.0457 | 0.2714 | 0.1682 |

요청 수치와 파일 수치 일치 여부:

| 항목 | 확인값 | 일치 여부 |
|---|---:|---|
| baseline NDCG@10 | 0.1105 | 일치 |
| proposed NDCG@10 | 0.1334 | 일치 |
| optimized_proposed NDCG@10 | 0.1682 | 일치 |
| optimized_proposed P@1 | 0.0714 | 일치 |
| optimized_proposed P@3 | 0.0571 | 일치 |
| optimized_proposed P@5 | 0.0457 | 일치 |
| Recall@10 | 0.2714 | 일치 |
| raw candidate recall@50 | 0.2714 | 일치 |
| raw 후보군에 정답이 없는 query 수 | 51 | 일치 |
| raw 후보군에 정답이 포함된 query 수 | 19 | 일치 |

## 7. candidate generation 병목 분석

reranking 최적화는 후보군 내 정답의 상위 배치를 개선했다. 그러나 Recall@10은 baseline, proposed, optimized_proposed 모두 0.2714로 개선되지 않았다. 이유는 strong positive 70개 중 51개 query의 실제 방문 장소가 raw Top50 후보군에 존재하지 않았기 때문이다. 반대로 raw 후보군에 정답이 포함된 19개 query는 optimized reranking에서 모두 Top10에 진입했다. 따라서 현재 시스템의 주된 성능 병목은 reranking이 아니라 candidate generation coverage 부족이다.

장소 유형별 누락 분석은 `output/experiments_optimized/missing_gold_by_place_type.csv` 기준이다.

| 장소 유형 | Gold 수 | raw 누락 | raw coverage | Top10 hit | 보강 방향 |
|---|---:|---:|---:|---:|---|
| 공원 | 11 | 11 | 0.0000 | 0 | 하천 산책로, 산 정상/팔각정, 광장, 생활권 야외공간 POI 확장 |
| 골목상권 | 10 | 7 | 0.3000 | 3 | 골목상권/상점가/먹자골목 데이터와 상권명 alias 추가 |
| 전통시장 | 21 | 6 | 0.7143 | 15 | 시장 출입구/남문/북문, 통칭, 별칭 alias 확장 |
| 체육시설 | 6 | 6 | 0.0000 | 0 | 공공체육시설, 학교/학생체육관, 생활체육 행사장 데이터 추가 |
| 복지시설 | 5 | 5 | 0.0000 | 0 | 종합사회복지관, 장애인복지관, 구립 복지시설 통합 |
| 정책현장 | 5 | 5 | 0.0000 | 0 | 공공시설, 도시문제 현장, 생활 SOC 후보 추가 |
| 노동현장 | 4 | 4 | 0.0000 | 0 | 노조, 산업단지, 사업장 밀집지, 근로자센터 후보군 구축 |
| 교통거점 | 3 | 3 | 0.0000 | 0 | 지하철 외 사거리, 광장, 도로 결절점, 버스 환승거점 추가 |
| 재개발/도시개발현장 | 3 | 3 | 0.0000 | 0 | 정비사업구역, 재개발/재건축 사업지 위치 데이터 추가 |
| 종교시설 | 1 | 1 | 0.0000 | 0 | 종교시설 POI와 종교행사 장소 후보군 구축 |
| 어린이/가족시설 | 1 | 0 | 1.0000 | 1 | 어린이공원, 가족센터, 보육/돌봄시설 후보군 추가 |

활동 유형 기준으로는 `현장방문` 18건이 모두 raw 후보군에서 누락되었고, `지역상권방문`은 25건 중 17건이 raw에 포함되어 상대적으로 양호했다. 논문에서는 “재랭킹 모델은 후보군 내부 정렬 품질을 개선했으나, Recall 상한은 raw candidate coverage에 의해 제한되었다”라고 해석할 수 있다.

## 8. 프론트엔드 및 시연 기능 요약

| 화면 | 구현 파일 | 구현 내용 | 시연 포인트 |
|---|---|---|---|
| `/` | `frontend/app/page.js` | 선거비서 AI 홈, 다음 일정, route preview, 평가 데이터 요약 | 후보자 운영 앱처럼 시작해 프로젝트가 사용자 문제를 겨냥함을 보여줌 |
| `/route` | `frontend/app/route/page.js`, `KakaoRouteMap.js` | 시작 위치/시간/자치구/타깃/목적/장소 유형 입력, 하루 동선 추천, 저장/공유/교체 UI | 실제 캠프 운영 도구처럼 조건 입력 후 지도와 타임라인 표시 |
| `/recommend` | `frontend/app/recommend/page.js`, `frontend/app/demo/page.js` | Gold query 선택, optimized_proposed Top-K 추천, score breakdown | 단일 추천 결과와 추천 근거 설명 |
| `/evaluation` | `frontend/app/evaluation/page.js` | 모델 비교, P@K/R@K/NDCG, raw coverage, missing place type chart | 논문 실험 결과와 candidate generation 병목 설명 |
| `/map` | `frontend/app/map/page.js` | 추천 동선 지도 전용 화면, 장소 유형 필터, 선택 카드 | 지도 기반 시연 보조 화면 |

Kakao 지도 연동은 `NEXT_PUBLIC_KAKAO_MAP_API_KEY`와 legacy `NEXT_PUBLIC_KAKAO_MAP_JS_KEY`를 지원한다. `KakaoRouteMap.js`는 SDK 로딩, app key 형식 검증, Kakao `CustomOverlay` 번호 마커, `Polyline`, zoom control, drag/zoom 활성화, tile diagnostics, fallback 좌표, 자치구 중심 fallback, 지도 로딩 실패 시 preview fallback을 구현한다. `frontend/next.config.mjs`는 Kakao/Daum CDN을 `script-src`, `script-src-elem`, `style-src`, `img-src`, `connect-src`에 허용한다. 모바일/데스크톱 반응형은 `AppShell`, 하단 탭, desktop sidebar, route workspace, map layout CSS로 구현되어 있다. Vercel은 `.vercel/project.json`과 `frontend/DEPLOYMENT.md` 기준 project link 및 설정 파일이 존재하지만, 실제 최신 배포 성공 여부는 Vercel dashboard 또는 CLI 확인이 필요하다.

추천 시연 순서는 `/` → `/route` → `/recommend` → `/evaluation`이 가장 자연스럽다. 먼저 제품형 화면으로 관심을 잡고, 단일 추천과 동선 추천을 보여준 뒤, 마지막에 실험 수치와 한계를 논문 관점으로 설명한다.

## 9. 해결한 주요 문제와 버그

| 문제 | 원인 | 수정 파일 | 해결 방식 | 기술적 의미 |
|---|---|---|---|---|
| 장소명이 자치구명만 표시됨 | 추천 후보가 추상 지명 또는 역명만 반환 | `backend/services/route_service.py` | `place_name_normalizer()`로 역 출구/광장/시장 입구 형태 보정 | 시연 장소가 실제 유세 지점처럼 보임 |
| 주소가 없을 때 빈값 표시 | raw/optimized CSV에 address가 항상 없음 | `backend/services/route_service.py`, `frontend/app/route/page.js` | `주소 확인 필요` fallback | 데이터 결측에도 UI 안정성 확보 |
| Kakao 지도 흰 타일 | CSP와 tile source, SDK 초기화 문제 | `frontend/next.config.mjs`, `KakaoRouteMap.js` | Kakao/Daum CDN 허용, roadmap 강제, relayout, diagnostics 추가 | 외부 지도 SDK 운영 안정화 |
| CSP에서 Kakao/Daum 리소스 차단 | 초기 CSP가 map tile/CDN을 충분히 허용하지 않음 | `frontend/next.config.mjs` | `dapi.kakao.com`, `*.kakao.com`, `*.kakaocdn.net`, `*.daumcdn.net`, `map*.daumcdn.net`, `mts.daumcdn.net` 허용 | 배포 환경 보안 정책과 지도 리소스 양립 |
| 마커 순서 표시 문제 | 지도 overlay 이벤트와 selected state 갱신 불안정 | `KakaoRouteMap.js`, `frontend/app/globals.css` | `CustomOverlay` 버튼 marker, zIndex, click handler 정리 | 동선 순서와 선택 장소를 명확히 표시 |
| polyline 경로 표시 문제 | marker 업데이트와 line lifecycle 분리 미흡 | `KakaoRouteMap.js` | overlay clear, `Polyline` 재생성, cleanup 구현 | 지도 기반 route 시각화 완성 |
| 지도 drag 불가 | overlay/상위 클릭 레이어가 map interaction을 막음 | `frontend/app/route/page.js`, `frontend/app/globals.css`, `KakaoRouteMap.js` | draggable/zoomable 활성화, overlay 이벤트 정리, CSS pointer-events 조정 | 지도 UX 개선 |
| 평가 대시보드 문구 과다 | 연구용 banner/내부 문구가 시연 화면을 어지럽힘 | `frontend/app/evaluation/page.js`, `CampUI.js` | unused public dashboard banner 제거 | 발표 화면 집중도 향상 |
| raw baseline과 재랭킹 실험 혼재 | 매번 추천기를 실행하면 공정 비교가 어려움 | `src/generate_raw_baseline_recommendations.py`, `src/run_model_experiments.py` | raw Top50 고정 후 동일 후보군 재랭킹 | 논문 실험의 재현성과 공정성 강화 |
| 후보군 병목 원인 불명확 | NDCG 개선과 Recall 정체의 원인이 분리되지 않음 | `src/analyze_candidate_generation.py` | raw coverage, hit_analysis, 누락 유형/자치구 분석 | 성능 한계를 공격받을 때 방어 가능 |

## 10. Git commit / 변경 이력 요약

초기 확인 명령 결과: `git status`는 clean, `git diff --stat`은 출력 없음, 최근 20개 커밋은 모두 `main` 및 `origin/main`에 존재한다.

### 알고리즘/평가 파이프라인

| 커밋 | 변경 파일 | 구현/수정 내용 | 졸업프로젝트 의미 |
|---|---|---|---|
| `2bac187` Initial deployment-ready campaign recommender project | `src/*.py`, `scripts/*.py`, `output/**`, `docs/**` | Gold Set, raw baseline, 평가/최적화/병목 분석 스크립트와 결과물 최초 포함 | 논문용 추천/평가 파이프라인의 핵심 기반 |

### 데이터 처리

| 커밋 | 변경 파일 | 구현/수정 내용 | 졸업프로젝트 의미 |
|---|---|---|---|
| `2bac187` | `data/processed/*.csv`, `scripts/clean_*.py` | 전처리 결과와 cleaning scripts 추가 | 공공데이터를 추천 feature로 변환 |
| `41a1658` Prepare FastAPI backend for Render deployment | `backend/data/processed/*.csv`, `backend/output/**` | Render rootDir 배포를 위해 backend 하위에도 처리 데이터와 output 복제 | 백엔드 단독 배포 가능성 확보 |

### 프론트엔드 UI

| 커밋 | 변경 파일 | 구현/수정 내용 | 졸업프로젝트 의미 |
|---|---|---|---|
| `544c003` Add static demo fallbacks for frontend deployment | `CampUI.js`, `/demo`, `/evaluation`, `/map`, `/route`, `frontend/public/data/*.json` | API 미연결 시 정적 데이터 fallback | 발표 시 네트워크/API 장애 방어 |
| `599c292` Fix route recommendation state and map updates | `CampUI.js`, `/route/page.js` | route response 정규화, 선택 stop, map update 정리 | 동선 추천 시연 안정화 |
| `94a2441` Clean candidate route page UI | `CampUI.js`, `/route/page.js` | route page 문구와 UI 정리 | 사용자용 운영 앱에 가깝게 정리 |
| `e677a78` Remove unused public dashboard banners | `CampUI.js`, `/evaluation/page.js` | 불필요 banner 제거 | 평가 화면 발표 집중도 개선 |

### 지도/시각화

| 커밋 | 변경 파일 | 구현/수정 내용 | 졸업프로젝트 의미 |
|---|---|---|---|
| `ed50fec` Allow Kakao Maps in CSP | `frontend/next.config.mjs` | Kakao Maps CSP 허용 | 배포 환경 지도 로딩 시작점 |
| `1b1bc93` Allow Daum CDN for Kakao Maps CSP | `frontend/next.config.mjs` | Daum CDN tile 허용 | 흰 타일 문제 완화 |
| `7684662` Render Kakao map without route coordinates | `KakaoRouteMap.js` | 좌표가 부족해도 fallback으로 지도 표시 | 데이터 결측 방어 |
| `f6a1ce5` Harden Kakao map SDK loading | `KakaoRouteMap.js`, CSS, `/map` | SDK 로딩 실패/브라우저 조건/초기화 안정화 | 지도 컴포넌트 운영 안정성 |
| `f81b458` Validate Kakao map public key | `KakaoRouteMap.js` | public key 형식 검증 | 배포 환경 설정 오류 조기 탐지 |
| `7bbe31f` Fix Kakao map CSP and tile rendering | `KakaoRouteMap.js`, `next.config.mjs` | CSP와 tile rendering 보강 | 실제 지도 타일 로딩 개선 |
| `dd084d3` Fix Kakao map tile layer initialization | `KakaoRouteMap.js`, CSS | 지도 layer 초기화/relayout 보강 | 흰 화면 대응 |
| `9b3986a` Add Kakao map tile layer diagnostics | `KakaoRouteMap.js` | tile source diagnostics 추가 | 원인 분석 가능성 확보 |
| `4386456` Fix route map layout overflow | `globals.css` | route map 레이아웃 overflow 수정 | 화면 깨짐 방지 |
| `aab868f` Validate Kakao map coordinates and tile diagnostics | `KakaoRouteMap.js` | 서울 범위 좌표 검증, tile diagnostics 확대 | 잘못된 좌표와 지도 오류 방어 |
| `8683eec` Reduce Kakao map production diagnostics | `KakaoRouteMap.js` | production log 축소 | 배포 로그 노이즈 감소 |
| `7518a36` Restore Kakao map interactions | `KakaoRouteMap.js`, CSS | drag/zoom interaction 복구 | 지도 조작 가능 |
| `929a709` Fix Kakao map drag overlay events | `globals.css` | overlay event 문제 수정 | 지도 드래그 UX 개선 |
| `daa55c2` Fix Kakao map drag interactions | `globals.css`, `/route/page.js` | drag interaction 최종 정리 | 시연 중 지도 조작 안정 |

### 배포/설정

| 커밋 | 변경 파일 | 구현/수정 내용 | 졸업프로젝트 의미 |
|---|---|---|---|
| `2bac187` | `frontend/package.json`, `frontend/next.config.mjs`, `frontend/DEPLOYMENT.md`, `backend/requirements.txt` | Next.js/FastAPI 배포 가능 구조 | 프로젝트를 웹앱으로 시연 가능 |
| `41a1658` | `render.yaml`, `backend/main.py` | Render backend 배포 설정, CORS origin 구성 | API 배포 기반 |

### 최근 수정 파일 목록

파일 timestamp 기준 최근 수정 주요 소스는 `frontend/app/evaluation/page.js`, `frontend/app/components/camp/CampUI.js`, `frontend/app/route/page.js`, `frontend/app/globals.css`, `frontend/app/components/map/KakaoRouteMap.js`, `frontend/next.config.mjs`, `frontend/app/map/page.js`, `backend/main.py`, `backend/services/route_service.py`, `backend/services/dashboard_service.py`, `render.yaml`이다. 로그 파일과 `.next`, `node_modules`, `__pycache__`는 분석에서 제외했다.

## 11. 논문에 넣을 수 있는 기술적 기여 정리

### 기술적 기여 1. 실제 후보 일정 기반 Gold Set 구축
- 설명: 정원오 후보 공개 일정표를 통합 Gold Set 186건으로 정리하고, 장소 추천 평가용 strong positive 70건을 선별했다.
- 구현 근거: `data/full_정원오_gold_set_20260309_20260516.csv`, `src/build_gold_eval_set.py`, `output/gold_set_summary.json`
- 관련 파일: `output/gold_set_all_merged.csv`, `output/gold_set_evaluation_queries.csv`
- 논문 문장 예시: “본 연구는 실제 후보 공개 일정표에서 구축한 Gold Set 186건 중 오프라인 방문 장소성이 명확한 70건을 strong positive로 정의하여 추천 성능 평가에 사용하였다.”

### 기술적 기여 2. 공공데이터 기반 후보 장소 pool 구성
- 설명: 지하철, 공원, 전통시장, 노인복지시설 및 상권/직장/생활인구 데이터를 전처리해 후보 장소와 보조 feature를 구성했다.
- 구현 근거: `scripts/clean_*.py`, `data/processed/*.csv`, `scripts/build_aux_feature_summary.py`
- 관련 파일: `cleaned_subway.csv` 79,787 rows, `cleaned_market.csv` 433 rows, `cleaned_parks.csv` 132 rows, `cleaned_senior.csv` 238 rows
- 논문 문장 예시: “서울시 공공데이터를 장소 유형별 후보 pool로 정규화하고, 시간대 및 유권자 맥락을 반영할 수 있도록 상권 유동인구, 직장인구, 생활인구 통계를 보조 feature로 사용하였다.”

### 기술적 기여 3. context-aware weighted ranking recommender 구현
- 설명: time, age, context, facility, interaction feature와 장소 유형별 가중치를 사용하는 설명 가능한 추천기를 구현했다.
- 구현 근거: `scripts/recommender.py`, `PLACE_TYPE_WEIGHTS`, `apply_weighted_score()`
- 관련 파일: `scripts/message_rules.py`, `scripts/route_planner.py`
- 논문 문장 예시: “추천기는 장소 유형별 특성을 반영한 weighted scoring 구조를 사용하여 시간대, 유권자 집단, 장소 맥락, 시설 규모, 상호작용 효과를 결합하였다.”

### 기술적 기여 4. raw candidate 고정 기반 공정한 재랭킹 실험 구조
- 설명: 기존 추천기로 query별 raw Top50 후보군을 고정한 뒤 모든 variant를 같은 후보군에서 비교했다.
- 구현 근거: `src/generate_raw_baseline_recommendations.py`, `src/run_model_experiments.py`
- 관련 파일: `output/raw_baseline_recommendations.csv`
- 논문 문장 예시: “모델 간 비교의 공정성을 위해 baseline 추천기가 생성한 raw candidate set을 고정하고, 이후 실험은 동일 후보군에 대한 재랭킹으로만 수행하였다.”

### 기술적 기여 5. weight search 기반 optimized reranking
- 설명: district/place/time/context/target/rank feature weight를 random search로 탐색해 optimized_proposed 모델을 만들었다.
- 구현 근거: `src/optimize_reranking_weights.py`, `best_weights.json`
- 관련 파일: `weight_search_results.csv`, `model_comparison_optimized.csv`
- 논문 문장 예시: “NDCG@10과 early precision을 함께 고려한 목적식을 사용해 feature weight를 탐색함으로써, baseline 대비 NDCG@10을 0.1105에서 0.1682로 개선하였다.”

### 기술적 기여 6. candidate generation 병목 분석
- 설명: Recall@10 정체 원인을 raw 후보군 coverage 부족으로 분해했다.
- 구현 근거: `src/analyze_candidate_generation.py`, `raw_candidate_coverage.csv`
- 관련 파일: `missing_gold_by_place_type.csv`, `candidate_generation_diagnosis.csv`
- 논문 문장 예시: “정답 장소가 raw Top50 후보군에 포함된 19개 query는 모두 optimized Top10에 진입했으므로, 현재 성능 병목은 재랭킹보다 후보군 생성 coverage에 있다.”

### 기술적 기여 7. 웹 기반 추천/평가 시연 시스템 구현
- 설명: FastAPI와 Next.js로 추천, 동선, 평가, 지도 시각화를 연결했다.
- 구현 근거: `backend/main.py`, `frontend/app/*`, `frontend/app/components/map/KakaoRouteMap.js`
- 관련 파일: `frontend/public/data/*.json`, `render.yaml`, `frontend/DEPLOYMENT.md`
- 논문 문장 예시: “제안 시스템은 추천 결과와 평가 지표를 웹 대시보드로 제공하여, 개별 추천의 설명 가능성과 전체 모델 성능을 동시에 시연할 수 있도록 구현되었다.”

## 12. 심사 발표용 1분 요약

“제 졸업프로젝트는 단순 시각화 웹앱이 아니라, 서울시 공공데이터와 실제 후보 공개 일정표 기반 Gold Set을 연결한 유세 장소 추천 시스템입니다. 먼저 지하철, 공원, 전통시장, 복지시설, 상권 유동인구 같은 데이터를 전처리해 후보 장소 pool을 만들고, 실제 후보 공개 일정표 기반 Gold Set에서 장소성이 명확한 70건을 strong positive로 선별했습니다. 그 다음 후보 장소 생성, 추천, 평가, 병목 분석까지 연결된 파이프라인을 만들었고, 추천 결과는 Precision@K, Recall@K, NDCG@K로 평가했습니다. 특히 raw candidate를 고정한 재랭킹 실험을 통해 baseline, proposed, optimized_proposed를 공정하게 비교했고, optimized 모델은 NDCG@10을 0.1105에서 0.1682로 개선했습니다. 다만 Recall@10은 0.2714에서 더 오르지 않았는데, 분석 결과 정답 장소가 raw Top50 후보군에 없는 query가 51개였기 때문입니다. 그래서 현재 성능 한계는 reranking보다 candidate generation coverage에 있음도 실험적으로 확인했습니다.”

## 13. 심사 발표용 시연 순서

1. 프로젝트 문제 정의 설명
   말할 내용: “선거 캠프가 하루 일정과 유세 장소를 정할 때 데이터 기반 근거가 부족하다는 문제에서 출발했습니다.”
2. 데이터셋 및 Gold Set 설명
   말할 내용: “서울시 공공데이터를 후보 장소 pool로 만들고, 실제 후보 공개 일정표 186건 중 strong positive 70건을 평가에 사용했습니다.”
3. `/recommend`에서 단일 추천 시연
   말할 내용: “이 화면은 선택된 일정 문맥에 대해 Top-K 후보 장소와 점수 근거를 보여줍니다.”
4. `/route`에서 후보자 동선 추천 시연
   말할 내용: “출발지, 시간, 자치구, 타깃을 입력하면 시간대별 방문 순서를 만들고 지도 marker와 polyline으로 확인합니다.”
5. `/evaluation`에서 모델별 성능 비교 설명
   말할 내용: “baseline, proposed, optimized_proposed를 같은 raw 후보군에서 비교했고, NDCG@10이 0.1105에서 0.1682로 개선되었습니다.”
6. candidate generation 병목 분석 설명
   말할 내용: “Recall@10이 유지된 이유는 70건 중 51건의 정답 장소가 raw 후보군에 없었기 때문입니다. covered 19건은 모두 Top10에 들어갔습니다.”
7. 향후 보완 방향 설명
   말할 내용: “다음 개선은 가중치 조정보다 공원, 체육시설, 복지시설, 정책현장, 노동현장 후보군 coverage 확장입니다.”

## 14. 현재 개발물의 한계

- rule-based weighted ranking은 설명 가능하지만, 실제 유세 성과나 사용자 반응을 학습하지 못한다.
- 후보 장소 pool coverage가 부족하다. raw Top50 recall@50이 0.2714라서 Recall@10 상한 자체가 낮다.
- Gold Set이 정원오 후보 1명 기반이라 후보/지역/선거 유형 일반화가 제한된다.
- 장소명 alias 매칭이 부족하다. 시장 입구, 남문/북문, 통칭, 광장, 하천 산책로 등 세부 POI가 약하다.
- 공원/체육시설/복지시설/정책현장/노동현장 데이터가 현재 MVP 후보 source로 충분하지 않다.
- Kakao 지도는 표시와 동선 preview는 가능하지만, 실제 routing optimization이나 실시간 교통/도보 경로 최적화는 아니다.
- route service의 이동 시간은 같은 자치구/인접 자치구/먼 자치구 기반 mock penalty다.
- 실제 선거 캠프의 피드백이나 현장 성과 데이터가 반영되지 않았다.
- weight search가 Gold Set에 과적합될 가능성이 있다. train/validation split은 있으나 표본 70건으로 작다.
- 실제 Vercel 최신 배포 성공 여부는 파일상 설정만 확인했고 live deployment는 확인 필요하다.
- 검증에서 Python compile은 통과했으나, `npm run build`는 sandbox에서 `spawn EPERM`, 외부 실행은 120초 timeout으로 완료 확인이 안 되었다.

## 15. 남은 보완 작업 우선순위

| 우선순위 | 작업명 | 예상 효과 | 수정할 파일 | 논문 반영 내용 | 심사 방어 포인트 |
|---:|---|---|---|---|---|
| 1 | candidate source 확장 우선 적용 | Recall 상한 개선 가능성 가장 큼 | `scripts/clean_*.py`, `scripts/recommender.py`, `src/generate_raw_baseline_recommendations.py` | candidate generation coverage 개선 실험 | “현재 병목을 근거로 우선순위를 정했다” |
| 2 | 장소명 alias table 구축 | 전통시장/상권/공원 입구명 매칭 개선 | 새 `data/processed/place_aliases.csv`, `src/evaluate_recommendations.py`, `route_service.py` | alias normalization ablation | “실제 일정표 표기와 공공데이터 명칭 불일치를 해결했다” |
| 3 | raw recall@50 개선 전후 비교 | 실험 결과 해석 강화 | `src/analyze_candidate_generation.py`, output CSV | coverage before/after table | “NDCG뿐 아니라 Recall 상한을 개선했다” |
| 4 | Vercel/Render live deployment 재검증 | 발표 리스크 감소 | `frontend/DEPLOYMENT.md`, `render.yaml`, env 설정 | 배포 재현 절차 | “심사장에서 로컬 없이 URL 시연 가능” |
| 5 | frontend build timeout 원인 확인 | 배포 안정성 강화 | `frontend/package.json`, `next.config.mjs`, Kakao map component | 빌드 검증 기록 | “구현뿐 아니라 운영 가능성을 확인했다” |
| 6 | route optimization 고도화 | 동선 추천 완성도 향상 | `backend/services/route_service.py`, `KakaoRouteMap.js` | routing heuristic 한계 및 개선 | “현재는 preview, 향후 OSRM/Kakao Directions로 확장” |
| 7 | Gold Set 후보 추가 | 일반화 방어력 향상 | `data/full_*.csv`, `src/build_gold_eval_set.py` | multi-candidate evaluation | “한 후보 편향을 줄였다” |

## 16. 최종 평가

| 항목 | 점수 | 근거 |
|---|---:|---|
| 데이터 파이프라인 | 8/10 | 원본 공공데이터 전처리와 Gold Set 생성 구조가 명확하다. 다만 후보 source coverage가 부족하다. |
| 추천 알고리즘 구현 | 7/10 | 설명 가능한 weighted scoring과 재랭킹 feature가 구현되어 있다. 학습 기반 모델은 아니다. |
| 평가 파이프라인 | 9/10 | Gold query, fixed raw candidate, P@K/R@K/NDCG@K, hit/miss 분석까지 재현 가능하다. |
| 실험 재현성 | 8/10 | CSV 산출물과 스크립트가 갖춰져 있고 random_state도 고정된다. 다만 표본 70건과 weight search 과적합 위험이 있다. |
| 프론트엔드 시연 완성도 | 8/10 | `/route`, `/recommend`, `/evaluation`, `/map`과 Kakao 지도, 정적 fallback이 있다. build 완료 확인은 필요하다. |
| 배포 완성도 | 7/10 | Vercel/Render 설정과 project link가 있다. 실제 최신 배포 성공 여부는 확인 필요하다. |
| 코드 구조 | 8/10 | `src`, `scripts`, `backend`, `frontend`, `output` 역할이 비교적 분리되어 있다. 일부 데이터가 backend에도 복제되어 중복은 있다. |
| 논문 반영 가능성 | 9/10 | Gold Set, fixed raw candidate, optimized reranking, coverage bottleneck이 논문 기여로 바로 사용 가능하다. |
| 심사 발표 방어력 | 8/10 | 성능 개선뿐 아니라 한계 원인을 수치로 설명할 수 있다. live build/deploy 확인이 약점이다. |
| 전체 졸업프로젝트 구현 완성도 | 8/10 | 추천 시스템 연구물과 웹 시연물의 연결이 잘 되어 있다. 남은 핵심은 후보군 coverage 확장과 배포 검증이다. |

검증 로그: `py -m py_compile`은 `backend/main.py`, backend services, 주요 `src/*.py`에 대해 성공했다. `npm run build`는 기본 sandbox에서 `spawn EPERM`으로 실패했고, escalated 실행은 120초 timeout으로 완료 확인하지 못했다.
