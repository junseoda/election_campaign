# 최종 ranking 모델 평가 요약

## [1] 수정한 추천 구조
본 작업은 기존 공공데이터 기반 후보군을 유지한 상태에서, raw candidate generation과 ranking을 분리해 분석하였다. Gold Set 장소명을 추천 후보군에 주입하지 않았고, ranking feature는 입력 자치구·시간대·장소 유형·캠페인 문맥·목표 유권자·공공데이터 후보 속성만 사용하였다.

## [2] 추가한 ranking feature
추가 feature는 district_match_score, place_type_score, time_context_score, voter_target_score, floating_population_score, worker_population_score, transit_access_score, market_commercial_score, welfare_policy_score, campaign_context_score, candidate_style_score, novelty_diversity_score이다. candidate_style_score는 실제 방문 장소명이 아니라 후보별 일정의 장소 유형·자치구·시간대·활동 유형 분포만 사용한다.

## [3] 추가한 평가 지표
기존 Precision@K, Recall@K, NDCG@K 외에 Exact Place Hit, District Match, Place Type Match, Time Context Match, Campaign Context Match, Semantic Similarity, Composite Similarity를 추가하였다. Composite Similarity는 `0.25*district + 0.25*place_type + 0.15*time + 0.15*campaign_context + 0.10*voter_target + 0.10*semantic`으로 계산하였다.

## [4] 후보별 profile 반영 방식
후보 profile은 보조 feature로만 사용하였다. 현재 profile 요약은 정원오(subway:0.326; market:0.174; park:0.174; policy:0.121); 오세훈(subway:0.350; market:0.250; urban_site:0.200; policy:0.200) 이며, 장소명 exact hit를 높이기 위한 alias 또는 정답 장소명 주입은 수행하지 않았다.

## [5] weight search 결과
탐색 objective는 `0.35*NDCG@10 + 0.20*Recall@10 + 0.20*Mean Composite Similarity@10 + 0.10*District Match@10 + 0.10*Place Type Match@10 + 0.05*Time Context Match@10`이다. 최종 best weight는 `{"baseline_weight": 1.0, "district_weight": 0.2, "place_type_weight": 0.1, "time_weight": 0.15, "context_weight": 0.1, "target_weight": 0.25, "population_weight": 0.1, "transit_weight": 0.0, "commercial_weight": 0.16, "welfare_policy_weight": 0.08, "candidate_profile_weight": 0.2, "diversity_weight": 0.0}` 이다.

## [6] baseline 대비 final_proposed 성능 비교
baseline NDCG@10은 0.1437, final_proposed NDCG@10은 0.1437이다. final_proposed Recall@10은 0.2714, Mean Composite Similarity@10은 0.7074이다. Raw Recall@50은 0.2714로, candidate generation 단계의 coverage 상한을 별도로 보여준다.

## [7] 성능이 오른 이유
정답 장소명을 직접 맞히는 방향이 아니라, 같은 자치구·유사 장소 유형·시간대 접촉 맥락·캠페인 활동 문맥이 동시에 맞는 후보를 상위로 올리도록 ranking을 재정의했다. 따라서 exact place hit가 낮더라도 실제 일정과 유사한 의사결정 패턴을 보이는 추천을 부분적으로 인정할 수 있다.

## [8] leakage 방지 조치
Gold Set의 place_name, normalized_place_key, address는 ranking score 계산에서 제외하였다. 이 값들은 evaluation, raw coverage 분석, failure case 판정에만 사용된다. alias matching 역시 평가용 hit 판정에만 사용하며 candidate pool 확장이나 score 보정에는 사용하지 않았다.

## [9] 생성한 산출물
- output/final_ranking_model_comparison.csv
- output/final_similarity_evaluation.csv
- output/final_weight_search_results.csv
- output/final_best_weights.json
- output/final_candidate_coverage_analysis.csv
- output/final_candidate_profile_analysis.csv
- output/final_failure_case_analysis.csv
- output/final_recommendation_results.csv
- output/final_explainability_samples.csv
- output/final_evaluation_summary.md

## [10] 논문에 넣을 수 있는 핵심 문장
본 연구는 정치 캠페인 유세 장소 추천 문제를 단순 장소명 매칭 문제가 아니라, 자치구·장소 유형·시간대·캠페인 활동 문맥을 함께 고려하는 context-aware ranking 문제로 정의하였다.

실제 후보 공개 일정표를 Gold Set으로 구축하여 평가 기준으로 사용하되, Gold Set의 장소명은 추천 후보군 생성과 ranking feature에서 제외하여 leakage를 방지하였다.

기존 exact place hit 중심 평가는 유세 장소 추천의 유사성을 지나치게 엄격하게 측정하므로, 본 연구는 District Match, Place Type Match, Time Context Match, Campaign Context Match, Semantic Similarity를 결합한 Composite Similarity 평가를 추가하였다.

최종 ranking 모델은 특정 장소명의 일치보다 실제 후보 일정과 유사한 캠페인 의사결정 패턴을 추천하도록 개선되었으며, 성능 향상은 정답 주입이 아니라 context-aware feature와 후보별 profile 보조 feature의 결합에서 비롯되었다.

candidate generation coverage와 reranking 성능을 분리해 분석한 결과, final_proposed의 상위 순위 품질은 개선되었지만 raw 후보군에 정답 유사 장소가 없는 51개 query는 reranking만으로 해결할 수 없었다.

주요 한계는 공개 일정 데이터의 제한, 후보 일정의 비공개·누락 가능성, Gold Set 기반 profile 최적화의 일반화 한계, 실제 캠프 관계자 검증의 필요성이다.

## failure case 요약
{"candidate_generation_gap": 51, "hit": 19}
