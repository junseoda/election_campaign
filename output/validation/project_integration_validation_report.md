# Gold Set 확장 통합 검증 보고서

## 1. 검증 목적

정원오 확장 일정과 오세훈 신규 일정을 기존 추천시스템 평가 파이프라인에 통합한 결과가 데이터, 실험, 웹앱 관점에서 재현 가능한지 검증한다.

## 2. 검증 대상 파일

- `output/gold_set_all_candidates.csv`
- `output/gold_set_evaluation_queries_all_candidates.csv`
- `output/raw_baseline_recommendations_all_candidates_no_alias.csv`
- `output/raw_baseline_recommendations_all_candidates_with_alias.csv`
- `output/experiments_all_candidates*/model_comparison.csv`
- `output/diagnosis_all_candidates/*.csv`
- `data/processed/place_aliases.csv`

## 3. 데이터 통합 검증 결과

| check_name | severity | passed | actual | expected | detail |
| --- | --- | --- | --- | --- | --- |
| final_gold_row_count | CRITICAL | True | 391 | 391 |  |
| new_gold_row_count | CRITICAL | True | 205 | 205 |  |
| candidate_name_domain | CRITICAL | True | 오세훈;정원오 | 정원오;오세훈 |  |
| gold_id_duplicate_count | CRITICAL | True | 0 | 0 |  |
| required_gold_columns | CRITICAL | True |  | none |  |
| date_format_yyyy_mm_dd | CRITICAL | True | 0 | 0 |  |
| gold_label_domain | CRITICAL | True | 0 | 0 |  |
| online_offline_domain | CRITICAL | True | 0 | 0 |  |
| use_for_place_recommendation_bool_parseable | CRITICAL | True | 0 | 0 |  |
| source_image_empty_count | CRITICAL | True | 0 | 0 |  |
| strong_place_name_empty_count | CRITICAL | True | 0 | 0 |  |
| strong_district_empty_count | CRITICAL | True | 0 | 0 |  |
| recomputed_strong_query_count | CRITICAL | True | 169 | 169 |  |
| query_count_jungwono | CRITICAL | True | 107 | 107 |  |
| query_count_ohsehoon | CRITICAL | True | 62 | 62 |  |
| evaluation_query_count_all | CRITICAL | True | 169 | 169 |  |
| evaluation_query_count_jungwono_file | CRITICAL | True | 107 | 107 |  |
| evaluation_query_count_ohsehoon_file | CRITICAL | True | 62 | 62 |  |
| query_id_duplicate_count | CRITICAL | True | 0 | 0 |  |
| existing_jungwono_rows_preserved | CRITICAL | True | 0 | 0 |  |
| existing_jungwono_normalized_metadata_differences | INFO | True | 4 | documented | Stable row keys are preserved; strict metadata differences are expected from district/time normalization. |
| ohsehoon_20260523_missing_logged | WARNING | True | log=True;report=True | log=True;report=True |  |
| alias_table_rows | INFO | True | 184 | >=184 |  |
| new_rows_review_required | WARNING | True | 205 | 205 | Manual transcription/address review remains required |

## 4. 평가 파이프라인 검증 결과

| model_name | metric | expected | actual | abs_diff | status |
| --- | --- | --- | --- | --- | --- |
| baseline | P@1 | 0.0178 | 0.01775147928994083 | 4.8520710059170996e-05 | PASS |
| baseline | R@10 | 0.2485 | 0.2485207100591716 | 2.071005917159141e-05 | PASS |
| baseline | NDCG@10 | 0.0963 | 0.09630789486458614 | 7.894864586147077e-06 | PASS |
| proposed | P@1 | 0.071 | 0.07100591715976332 | 5.917159763321744e-06 | PASS |
| proposed | R@10 | 0.6805 | 0.6804733727810651 | 2.662721893487152e-05 | PASS |
| proposed | NDCG@10 | 0.3182 | 0.31822576680259196 | 2.5766802591975502e-05 | PASS |
| optimized_proposed | P@1 | 0.2899 | 0.28994082840236685 | 4.082840236685481e-05 | PASS |
| optimized_proposed | R@10 | 0.9408 | 0.9408284023668639 | 2.8402366863966577e-05 | PASS |
| optimized_proposed | NDCG@10 | 0.5913 | 0.5913019224255992 | 1.9224255991545647e-06 | PASS |

## 5. alias 보강 전/후 ablation 결과

| setting | query_count | raw_candidate_rows | raw_recall_at_50 | missing_gold_count | baseline_p_at_1 | baseline_r_at_10 | baseline_ndcg_at_10 | proposed_p_at_1 | proposed_r_at_10 | proposed_ndcg_at_10 | optimized_p_at_1 | optimized_r_at_10 | optimized_ndcg_at_10 | interpretation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| no_alias | 169 | 7114 | 0.2485207100591716 | 127 | 0.01775147928994083 | 0.2485207100591716 | 0.09630789486458614 | 0.07100591715976332 | 0.2485207100591716 | 0.14360014500940002 | 0.10059171597633136 | 0.2485207100591716 | 0.16903179871843646 | Gold-derived alias를 적용하지 않은 기존 MVP 후보군 coverage 기준 |
| with_alias | 169 | 7259 | 1.0 | 0 | 0.01775147928994083 | 0.2485207100591716 | 0.09630789486458614 | 0.07100591715976332 | 0.6804733727810651 | 0.31822576680259196 | 0.28994082840236685 | 0.9408284023668639 | 0.5913019224255992 | Gold Set 기반 alias 후보를 추가한 candidate generation coverage 보강 기준 |

alias 보강 후 성능 상승은 모델 일반화 성능이 아니라 Gold-derived alias를 후보군 생성에 반영한 coverage 보강 효과로 해석해야 한다.

## 6. Candidate Generation 병목 분석

후보군 생성 단계에서 정답 후보가 포함되지 않으면 reranking 단계는 해당 정답을 복구할 수 없다. 따라서 추천 시스템의 성능 상한은 candidate generation coverage에 의해 제한된다.

## 7. 웹앱/백엔드 회귀 테스트

| endpoint | status_code | success | error_message | response_key_summary |
| --- | --- | --- | --- | --- |
| GET /health | 200 | True |  | status |
| POST /recommend | 200 | True |  | input;places;messages |
| GET /route/sample | 200 | True |  | summary;timeline;insights;map |
| GET /evaluation/dashboard | 200 | True |  | source_files;model_comparison;optimized_metrics;best_weights;gold_summary;split_summaries;feature_contribution |
| GET /coverage/dashboard | 200 | True |  | source_files;summary;diagnosis;missing_by_place_type;missing_by_district;missing_by_campaign_activity_type |

`frontend_build_check.md`에 frontend build 산출물 존재 여부를 기록했다.

## 8. 샘플 추천 Trace

| query_id | candidate_name | date | district | place_type | gold_place_name | raw_no_alias_in_top50 | raw_no_alias_best_rank | raw_with_alias_in_top50 | raw_with_alias_best_rank | baseline_top10_rank | baseline_top10_places | proposed_top10_rank | proposed_top10_places | optimized_proposed_top10_rank | optimized_proposed_top10_places |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OH_20260429_1030_성동구_쌍리단길생문시장_OH_0008 | 오세훈 | 2026-04-29 | 성동구 | 골목상권 | 쌍리단길·생문시장 | False |  | True | 22 |  | 남대문시장 \| 동대문종합시장 \| 장안 마실 골목형상점가 \| 천호로데오거리상점가 \| 마장축산물시장 \| 성동용답상가시장 \| 송정벚꽃골목형상점가 \| 사근살곶이골목형상점가시장 \| 금남시장 \| 뚝도시장 |  | 남대문시장 \| 마장축산물시장 \| 성동용답상가시장 \| 송정벚꽃골목형상점가 \| 사근살곶이골목형상점가시장 \| 금남시장 \| 뚝도시장 \| 마장동축산물시장 \| 성수동 골목상권 \| 성수동 카페거리 | 7 | 성수동 골목상권 \| 마장축산물시장 \| 마장동축산물시장 \| 성수동 카페거리 \| 성수역 \| 성수역 3번출구 앞 \| 쌍리단길·생문시장 \| 아지오 성수점 \| 성동용답상가시장 \| 송정벚꽃골목형상점가 |
| OH_20260501_1140_종로구_서울배달라이더현장_OH_0016 | 오세훈 | 2026-05-01 | 종로구 | 노동현장 | 서울배달라이더 현장 | False |  | True | 13 |  | 종로노인종합복지관 \| 낙산근린공원 \| 북악산도시자연공원 \| 인왕산도시자연공원 \| 세종로공원 \| 경희궁 \| 삼청근린공원 \| 광화문시민열린마당 \| 와룡근린공원 \| 사직근린공원 |  | 종로노인종합복지관 \| 낙산근린공원 \| 북악산도시자연공원 \| 인왕산도시자연공원 \| 동대문종합시장 \| 세종로공원 \| 경희궁 \| 삼청근린공원 \| 광화문시민열린마당 \| 와룡근린공원 | 10 | 종로노인종합복지관 \| 동대문종합시장 \| 낙산근린공원 \| 북악산도시자연공원 \| 인왕산도시자연공원 \| 세종로공원 \| 경희궁 \| 광화문광장 감사의정원 \| 대학로 마로니에공원 \| 서울배달라이더 현장 |
| JG_20260310_1740_중구_황학시장입구_JG_0006 | 정원오 | 2026-03-10 | 중구 | 전통시장 | 황학시장 입구 | False |  | True | 14 |  | 남대문시장 \| 평화시장 \| 삼익패션타운 \| 동평화시장 \| 청평화시장 \| 신평화패션타운 \| 방산시장 \| 광희패션몰 \| 통일상가 \| 중부시장 |  | 남대문시장 \| 평화시장 \| 삼익패션타운 \| 동평화시장 \| 청평화시장 \| 신평화패션타운 \| 방산시장 \| 광희패션몰 \| 통일상가 \| 중부시장 |  | 남대문시장 \| 평화시장 \| 삼익패션타운 \| 동평화시장 \| 청평화시장 \| 신평화패션타운 \| 방산시장 \| 광희패션몰 \| 통일상가 \| 중부시장 |
| JG_20260311_1510_영등포구_영등포전통시장남문_JG_0009 | 정원오 | 2026-03-11 | 영등포구 | 전통시장 | 영등포전통시장 남문 | True | 7 | True | 7 | 7 | 남대문시장 \| 동대문종합시장 \| 장안 마실 골목형상점가 \| 영등포유통상가 \| 영등포시장기계공구상가 \| 영등포청과시장 \| 영등포전통시장 \| 대림중앙시장 \| 우리시장 \| 선유로운골목형상점가 | 5 | 영등포유통상가 \| 남대문시장 \| 영등포시장기계공구상가 \| 영등포청과시장 \| 영등포전통시장 \| 대림중앙시장 \| 우리시장 \| 선유로운골목형상점가 \| 영등포 지하상가 \| 영등포전통시장 남문 | 2 | 영등포유통상가 \| 영등포전통시장 \| 영등포전통시장 남문 \| 영등포시장기계공구상가 \| 영등포청과시장 \| 대림중앙시장 \| 우리시장 \| 선유로운골목형상점가 \| 영등포 지하상가 \| 화곡본동시장 |
| OH_20260502_0930_성북구_상경청년자취방_OH_0022 | 오세훈 | 2026-05-02 | 성북구 | 정책현장 | 상경청년 자취방 | False |  | True | 15 |  | 시립성북노인종합복지관 \| 청량공원 \| 개운산근린공원 \| 성북근린공원 \| 월곡달빛오거리골목형상점가 \| 석계음식문화거리 \| 종암북바위길골목형상점가 \| 돈암시장 \| 정릉시장 \| 성북천골목형상점가 |  | 시립성북노인종합복지관 \| 청량공원 \| 개운산근린공원 \| 성북근린공원 \| 월곡달빛오거리골목형상점가 \| 석계음식문화거리 \| 종암북바위길골목형상점가 \| 돈암시장 \| 정릉시장 \| 성북천골목형상점가 | 5 | 시립성북노인종합복지관 \| 청량공원 \| 개운산근린공원 \| 성북근린공원 \| 상경청년 자취방 \| 월곡달빛오거리골목형상점가 \| 석계음식문화거리 \| 종암북바위길골목형상점가 \| 돈암시장 \| 정릉시장 |

## 9. 검증 결론

- 최종 판단: **PASS WITH WARNINGS**
- 평가 수치와 alias 전/후 coverage 변화는 CSV 기준으로 재현된다.
- 논문에는 gold-derived alias expansion의 한계를 반드시 별도로 표기해야 한다.

## 10. 후속 개선 필요사항

- 신규 수동 전사 row의 상세 주소 검수
- 외부 POI 기반 alias 일반화
- 후보별 evaluation UI 필터
- alias 보강 전/후 결과 분리 표기