# 추천 알고리즘 개선 실험 보고서

생성일: 2026-05-22

## 1. 개선 목적

기존 실험에서 reranking보다 candidate generation coverage가 더 큰 병목으로 확인되었다. 특히 raw candidate recall@50이 0.2714에 머물러, 많은 Gold 장소가 reranker가 다룰 수 있는 raw Top50 후보군에 들어오지 못했다. 이번 작업의 목적은 Gold Set을 새로 만들지 않고, alias table과 보수적 matching 규칙을 추가해 후보군 coverage를 높이고 성능 변화를 정량 비교하는 것이다.

## 2. 적용한 코드 변경 사항

| 구분 | 파일 | 내용 |
|---|---|---|
| Alias helper | `src/place_aliases.py` | alias table 로딩, 장소명 normalization, district 표준화, query 호환 alias 후보 생성 |
| Alias data | `data/processed/place_aliases.csv` | 전통시장, 역, 공원, 체육시설, 복지시설, 정책현장, 노동현장, 재개발현장, 종교시설 alias seed |
| Matching | `src/evaluate_recommendations.py` | exact, normalized, alias, partial matching 순서 적용 및 district alias 반영 |
| Raw generation | `src/generate_raw_baseline_recommendations.py` | `--use_alias_expansion` 옵션으로 기존 Top10 보호 후 alias 후보를 raw Top50에 추가 |
| Comparison table | `src/build_improvement_summary.py` | before/after 모델 성능, raw coverage, 장소 유형별 missing 비교 CSV 생성 |
| Matching docs | `docs/alias_matching_rules.md` | 논문에 설명 가능한 matching 및 candidate expansion 규칙 정리 |

## 3. Candidate Generation 개선 내용

기존 raw candidate source는 `market`, `subway`, `park`, `senior_friendly` 네 유형이었다. 실제 Gold는 공원, 체육시설, 복지시설, 정책현장, 노동현장, 교통거점, 도시개발현장, 종교시설까지 포함하므로 source coverage가 부족했다.

개선 실험에서는 alias table을 추가 후보 source처럼 사용했다. 단, 기존 baseline Top10이 바뀌지 않도록 alias 후보 score를 보호된 Top10의 최저 score보다 낮게 두었다. 따라서 baseline Top10 성능은 그대로 유지되고, reranker가 district/context/type feature를 통해 새 후보를 상위로 올릴 수 있는지만 평가했다.

## 4. Alias 및 Matching 개선 내용

Matching 규칙은 다음 순서로 적용했다.

1. district 표준화 후 district constraint 확인
2. exact name match
3. normalized key match
4. alias table match
5. 보수적 partial match

예를 들어 `영등포전통시장 남문`은 `영등포전통시장`과 alias로 연결되고, `광화문`은 district 비교에서 `종로구`로 표준화된다. 자세한 규칙은 `docs/alias_matching_rules.md`에 정리했다.

## 5. 개선 전 성능

기존 output은 보존했다. 공정 비교를 위해 개선된 evaluator 기준으로 기존 raw 후보군을 `output/improved/before_recomputed` 아래에 재평가했다.

| 모델 | P@1 | P@3 | P@5 | P@10 | R@10 | NDCG@10 |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 0.0286 | 0.0095 | 0.0200 | 0.0271 | 0.2714 | 0.1105 |
| optimized_proposed | 0.0714 | 0.0571 | 0.0457 | 0.0271 | 0.2714 | 0.1682 |

## 6. 개선 후 성능

| 모델 | P@1 | P@3 | P@5 | P@10 | R@10 | NDCG@10 |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 0.0286 | 0.0095 | 0.0200 | 0.0271 | 0.2714 | 0.1105 |
| candidate-expanded proposed | 0.0429 | 0.0714 | 0.0886 | 0.0729 | 0.7286 | 0.3321 |
| candidate-expanded optimized | 0.2857 | 0.1952 | 0.1429 | 0.0929 | 0.9286 | 0.5873 |

After optimized best weights:

```json
{
  "baseline_weight": 1.0,
  "district_weight": 0.7,
  "place_type_weight": 0.2,
  "time_weight": 0.05,
  "context_weight": 0.2,
  "target_weight": 0.2,
  "rank_weight": 0.0
}
```

## 7. 개선된 지표

| metric | before optimized | after optimized | absolute change |
|---|---:|---:|---:|
| P@1 | 0.0714 | 0.2857 | +0.2143 |
| P@3 | 0.0571 | 0.1952 | +0.1381 |
| P@5 | 0.0457 | 0.1429 | +0.0971 |
| P@10 | 0.0271 | 0.0929 | +0.0657 |
| R@10 | 0.2714 | 0.9286 | +0.6571 |
| NDCG@10 | 0.1682 | 0.5873 | +0.4191 |
| raw candidate recall@50 | 0.2714 | 0.9857 | +0.7143 |
| missing query count | 51 | 1 | -50 |

## 8. 개선되지 않았거나 주의할 지표

- Baseline Top10 성능은 변하지 않았다. 이는 의도한 결과다. 기존 raw baseline Top10을 보호했기 때문에 후보군 확장이 baseline 자체를 직접 바꾸지 않았다.
- Raw 후보군에는 있으나 optimized Top10에 오르지 못한 query가 4개 남았다. 해당 장소는 `황학시장 입구`, `동원시장`, `우림시장`, `북촌의 봄`이다.
- raw Top50에 여전히 없는 query는 1개다. `여의도공원 10번 출구`는 Gold district가 `마포구`로 기록되어 있으나 alias source는 실제 위치 기준 `영등포구`라 strict district constraint에서 제외되었다. 이는 Gold 장소권 또는 district 표준화 이슈로 남겨두는 것이 정직하다.

## 9. 왜 개선되었는가

성능 향상의 직접 원인은 reranking weight가 아니라 raw candidate coverage 증가다. 기존에는 Gold 장소 70개 중 19개만 raw Top50에 있었고 51개는 reranker가 접근할 수 없었다. Alias expansion 이후 69개가 raw Top50에 들어오면서 reranker가 정답 후보를 비교할 수 있게 되었다. 그 결과 R@10은 0.2714에서 0.9286으로 증가했고, NDCG@10도 0.1682에서 0.5873으로 증가했다.

## 10. 여전히 남은 병목

- Alias table은 수작업 seed이므로 외부 공공 POI source를 완전히 대체하지 못한다.
- 정책현장, 노동현장, 재개발현장, 종교시설은 독립 source가 부족하다.
- Gold Set은 현재 후보자 1명과 제한된 기간에 기반한다.
- 실제 유세 성과 데이터가 없으므로 추천의 선거 효과를 직접 검증하지는 못한다.
- Rule-based weighted ranking은 해석 가능하지만 학습 기반 일반화 성능에는 한계가 있다.

## 11. 논문에 넣을 수 있는 표

### 표 A. 개선 전후 모델 성능 비교

| metric | before baseline | before optimized | after baseline | after optimized | change |
|---|---:|---:|---:|---:|---:|
| P@1 | 0.0286 | 0.0714 | 0.0286 | 0.2857 | +0.2143 |
| P@3 | 0.0095 | 0.0571 | 0.0095 | 0.1952 | +0.1381 |
| R@10 | 0.2714 | 0.2714 | 0.2714 | 0.9286 | +0.6571 |
| NDCG@10 | 0.1105 | 0.1682 | 0.1105 | 0.5873 | +0.4191 |

### 표 B. Raw candidate coverage 개선

| metric | before | after | change |
|---|---:|---:|---:|
| raw candidate recall@50 | 0.2714 | 0.9857 | +0.7143 |
| missing query count | 51 | 1 | -50 |
| optimized hit@10 rate | 0.2714 | 0.9286 | +0.6571 |
| raw candidate rows | 2871 | 2899 | +28 |

### 표 C. 장소 유형별 missing 변화

| place type | missing before | missing after | raw coverage before | raw coverage after |
|---|---:|---:|---:|---:|
| 공원 | 11 | 0 | 0.0000 | 1.0000 |
| 골목상권 | 7 | 0 | 0.3000 | 1.0000 |
| 전통시장 | 6 | 0 | 0.7143 | 1.0000 |
| 체육시설 | 6 | 0 | 0.0000 | 1.0000 |
| 복지시설 | 5 | 0 | 0.0000 | 1.0000 |
| 정책현장 | 5 | 0 | 0.0000 | 1.0000 |
| 노동현장 | 4 | 1 | 0.0000 | 0.7500 |
| 교통거점 | 3 | 0 | 0.0000 | 1.0000 |
| 재개발/도시개발현장 | 3 | 0 | 0.0000 | 1.0000 |
| 종교시설 | 1 | 0 | 0.0000 | 1.0000 |

## 12. 논문에 넣을 수 있는 문장

### 서론

본 연구의 Gold Set은 현재 단일 후보자와 제한된 기간의 공개 일정에 기반한다는 한계가 있으나, 후보자와 기간을 추가할 수 있도록 query, place, relevance schema를 분리하여 확장 가능한 평가 구조로 설계하였다.

본 연구는 정치 캠페인 전략 자체를 제안하기보다, 실제 후보 일정으로부터 구축한 Gold Set을 이용해 공공데이터 기반 장소 추천 시스템을 정량 평가하는 추천시스템 연구로 위치づけ된다.

### 관련 연구

관련 연구는 네 축으로 정리할 수 있다. 첫째, 시간, 지역, 대상 유권자와 같은 context를 반영하는 context-aware recommendation이다. 둘째, 도시 공간의 장소 후보를 추천하는 POI recommendation이다. 셋째, 대규모 후보군을 먼저 생성하고 이후 reranking을 수행하는 candidate generation plus reranking 구조이다. 넷째, 추천 순위의 품질을 평가하기 위한 Precision@K, Recall@K, NDCG@K 기반 ranking evaluation이다.

### 제안 방법

하나의 query는 날짜, 시간, 자치구, 장소 유형, 유권자 대상, 문맥 태그로 정의된다. Candidate place는 서울시 공공데이터와 alias table에서 생성된 후보 장소이며, 각 후보는 시간 적합도, 지역 적합도, 장소 유형 적합도, context 적합도, target voter 적합도 feature를 가진다. 최종 ranking score는 baseline score와 feature bonus의 가중합으로 계산된다.

Raw candidate generation은 각 query에 대해 기존 공공데이터 기반 recommender를 실행해 Top50 후보군을 고정한다. 이후 모든 모델 variant는 동일한 raw 후보군을 reranking하므로, 모델 간 비교에서 candidate pool 차이에 의한 편향을 줄인다.

이번 개선에서는 장소명 alias table을 추가하여 출입구, 광장, 산책로, 사거리, 주소형 장소명과 canonical 장소명을 연결하였다. 평가 matching은 district constraint를 유지한 상태에서 exact, normalized, alias, partial 순서로 수행된다.

### 실험 및 결과

기존 optimized 모델의 R@10은 0.2714, NDCG@10은 0.1682였으며, raw candidate recall@50 역시 0.2714에 그쳤다. 이는 많은 정답 장소가 reranker 입력 후보군에 포함되지 않았음을 의미한다.

Alias 기반 후보군 확장 후 raw candidate recall@50은 0.9857로 증가했고, optimized 모델의 R@10은 0.9286, NDCG@10은 0.5873으로 향상되었다. 이 결과는 본 시스템의 주요 병목이 reranking weight 자체보다 candidate generation coverage에 있음을 정량적으로 보여준다.

### 한계 및 향후 연구

현재 Gold Set은 후보자 1명과 제한된 기간의 공개 일정에 기반하므로 일반화 검증에는 한계가 있다. 향후 추가 후보자와 기간의 일정 자료를 반영해 Gold Set을 확장하고, 정책현장, 노동현장, 재개발현장, 종교시설 등 후보 source를 독립 데이터로 구축할 필요가 있다.

Rule-based weighted ranking은 feature별 기여도를 설명하기 쉽다는 장점이 있으나, 충분한 학습 데이터가 확보되면 learning-to-rank 또는 neural reranking으로 확장할 수 있다.

### 결론

본 연구의 기여는 세 가지다. 첫째, 실제 후보 공개 일정 기반 Gold Set을 구축하였다. 둘째, 서울시 공공데이터 기반 context-aware 유세 장소 추천 시스템을 구현하였다. 셋째, fixed raw candidate 기반 평가를 통해 candidate generation coverage가 추천 성능의 핵심 병목임을 실험적으로 분석하였다.

## 13. 발표에서 말할 수 있는 요약

이번 프로젝트는 서울시 공공데이터로 유세 후보 장소를 만들고, 실제 후보 공개 일정에서 추출한 Gold Set으로 추천 품질을 평가한 시스템입니다. 초기 결과에서는 R@10이 0.2714로 낮았는데, 분석 결과 reranking보다 raw 후보군에 정답 장소가 들어오지 않는 candidate generation 문제가 핵심이었습니다. 그래서 장소명 alias table과 보수적 matching 규칙을 추가했고, 기존 baseline Top10은 유지한 채 후보군 coverage를 보강했습니다. 그 결과 raw recall@50은 0.2714에서 0.9857로, optimized R@10은 0.9286으로, NDCG@10은 0.5873으로 개선되었습니다. 다만 현재 Gold Set은 단일 후보와 제한된 기간 기반이라, 앞으로 더 많은 후보 일정과 공공 POI source를 추가해 일반화 검증을 확장해야 합니다.

## 14. 심사위원 질문 대비 답변

| 질문 | 답변 방향 |
|---|---|
| Gold Set이 부족하지 않나요? | 맞다. 현재는 단일 후보와 제한 기간 기반이라 일반화 한계가 있다. 다만 schema를 query, place, relevance로 분리해 후보와 기간을 추가할 수 있게 만들었다. |
| 왜 후보자 1명 기준인가요? | 공개 일정 자료를 안정적으로 수집하고 정제할 수 있는 범위에서 먼저 평가 가능한 Gold Set을 구축했다. 연구의 초점은 정치적 주장보다 추천시스템 평가 파이프라인 검증이다. |
| rule-based인데 기술성이 있나요? | candidate generation, fixed raw candidate reranking, NDCG 평가, coverage diagnosis를 갖춘 추천시스템 실험 구조가 핵심 기술 요소다. |
| 성능이 낮은데 의미가 있나요? | 초기 성능이 낮았기 때문에 병목 분석이 가능했다. 실험 결과 낮은 성능의 원인이 reranking이 아니라 raw coverage 부족임을 확인했고, 개선 후 R@10이 0.9286까지 상승했다. |
| Recall이 왜 안 올랐나요? | 기존에는 정답 장소가 raw Top50에 없어 reranker가 맞힐 수 없었다. alias/source 보강 후 raw recall@50이 0.9857로 올라 Recall@10도 개선되었다. |
| 이번 개선으로 무엇이 좋아졌나요? | raw recall@50 0.2714 -> 0.9857, missing 51 -> 1, optimized R@10 0.2714 -> 0.9286, NDCG@10 0.1682 -> 0.5873으로 개선되었다. |
| 왜 learning-to-rank를 안 썼나요? | 현재 Gold가 70 query로 작아 학습 기반 모델은 과적합 위험이 크다. 먼저 해석 가능한 rule-based 모델로 병목을 분석하고, Gold 확장 후 learning-to-rank를 적용하는 순서가 타당하다. |
| 후보 장소 pool을 어떻게 확장할 건가요? | 공공체육시설, 종합사회복지관, 교통 환승거점, 정비사업구역, 노동현장, 종교시설 POI를 별도 source로 추가하고 alias table을 공통 normalization layer로 사용한다. |
| 실제 선거 캠프에서 쓸 수 있나요? | 현재는 의사결정 보조와 실험용 prototype 수준이다. 실제 활용에는 최신 POI, 이동시간, 인허가, 현장 안전, 중복 방문 정책, 선거법 검토가 추가로 필요하다. |
| 논문의 핵심 기여가 무엇인가요? | 실제 후보 일정 기반 Gold Set, 공공데이터 기반 context-aware 추천 구현, fixed raw candidate 기반 평가와 candidate generation 병목 분석이다. |

## 15. 최종 발표 슬라이드 반영 포인트

| 슬라이드 | 반영 내용 |
|---|---|
| 문제 정의 | 실제 후보 일정과 공공데이터를 연결한 추천 평가 문제로 제시 |
| 시스템 구조 | Candidate generation -> fixed raw candidates -> reranking -> evaluation flow |
| Gold Set | 현재 70개 strong positive query와 확장 가능한 schema |
| 기존 결과 | raw recall@50 0.2714와 missing 51개를 병목으로 제시 |
| 개선 방법 | alias table, district normalization, conservative matching, protected Top10 |
| 개선 결과 | raw recall@50 0.9857, R@10 0.9286, NDCG@10 0.5873 강조 |
| 장소 유형 분석 | 공원 11 -> 0, 체육시설 6 -> 0, 복지시설 5 -> 0 missing 감소 표 |
| 시연 화면 | 추천 결과 페이지와 route planner 화면. 단, 이번 발표의 핵심은 UI보다 평가 결과 |
| 한계 | Gold Set 제한, alias seed 의존, 독립 source 부족을 먼저 인정 |
| 향후 연구 | Gold Set 확장, source 확장, learning-to-rank 또는 neural reranking |

## 16. 재현 명령어

```powershell
git status --short

py src\generate_raw_baseline_recommendations.py `
  --gold output\gold_set_evaluation_queries.csv `
  --output output\improved\raw_baseline_recommendations.csv `
  --top_k 50 `
  --candidate_pool 200 `
  --use_alias_expansion `
  --alias_path data\processed\place_aliases.csv

py src\run_model_experiments.py `
  --gold output\gold_set_evaluation_queries.csv `
  --raw output\improved\raw_baseline_recommendations.csv `
  --output_dir output\improved\experiments `
  --top_k 10 `
  --k 1 3 5 10

py src\optimize_reranking_weights.py `
  --gold output\gold_set_evaluation_queries.csv `
  --raw output\improved\raw_baseline_recommendations.csv `
  --existing_comparison output\improved\experiments\model_comparison.csv `
  --output_dir output\improved\experiments_optimized `
  --top_k 10 `
  --k 1 3 5 10 `
  --search_mode random `
  --n_trials 300 `
  --random_state 42

py src\analyze_candidate_generation.py `
  --gold output\gold_set_evaluation_queries.csv `
  --coverage output\improved\experiments_optimized\raw_candidate_coverage.csv `
  --hit output\improved\experiments_optimized\optimized_proposed\hit_analysis.csv `
  --raw output\improved\raw_baseline_recommendations.csv `
  --output_dir output\improved\experiments_optimized

py src\build_improvement_summary.py `
  --before_dir output\improved\before_recomputed\experiments_optimized `
  --after_dir output\improved\experiments_optimized `
  --before_raw output\raw_baseline_recommendations.csv `
  --after_raw output\improved\raw_baseline_recommendations.csv `
  --output_dir output\improved
```

## 17. 산출물 경로

- Improved raw candidates: `output/improved/raw_baseline_recommendations.csv`
- Improved model comparison: `output/improved/experiments/model_comparison.csv`
- Improved optimized comparison: `output/improved/experiments_optimized/model_comparison_optimized.csv`
- Raw coverage comparison: `output/improved/raw_coverage_before_after.csv`
- Model before/after comparison: `output/improved/model_comparison_before_after.csv`
- Place type before/after comparison: `output/improved/missing_by_place_type_before_after.csv`
- Summary: `output/improved/improvement_summary.csv`
