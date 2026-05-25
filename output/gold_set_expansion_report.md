# Gold Set 확장 보고서

## 1. 입력 데이터

### 기존 Gold Set 파일 목록

| 파일 | 로드 row |
|---|---:|
| `data/full_정원오_gold_set_20260309_20260516.csv` | 186 |
| `gold set수작업/정원오 유세일정 csv 추출 set/full_정원오_gold_set_20260309_20260516.csv` | 186 |
| `gold set수작업/정원오 유세일정 csv 추출 set/정원오_gold_set_20260309_20260405.csv` | 54 |
| `gold set수작업/정원오 유세일정 csv 추출 set/정원오_gold_set_20260406_20260428.csv` | 64 |
| `gold set수작업/정원오 유세일정 csv 추출 set/정원오_gold_set_20260429_20260516.csv` | 68 |
| `output/gold_set_all_merged.csv` | 186 |

자동 탐색 결과 중복 포함 744 row를 읽었고, dedupe 후 기존 고유 row는 186건이다.

### 새 ZIP 파일 목록

| 후보자 | ZIP | 이미지 수 | 날짜 범위 | 누락 이미지 날짜 |
|---|---|---:|---|---|
| 정원오 | `gold set수작업/정원오_일정_20260517~20260525.zip` | 9 | 2026-05-17 ~ 2026-05-25 | 없음 |
| 오세훈 | `gold set수작업/오세훈_일정_20260427~20260525.zip` | 28 | 2026-04-27 ~ 2026-05-25 | 2026-05-23 |

오세훈 2026-05-23 이미지는 ZIP 내부에 없어 `output/schedule_image_extraction_log.csv`에 `missing_image`로 기록했다.

## 2. Gold Set 생성 결과

| 구분 | 전체 row | label 0 | label 1 | label 2 | label 3 | strong positive | 장소 query |
|---|---:|---:|---:|---:|---:|---:|---:|
| 기존 정원오 | 186 | 3 | 42 | 71 | 70 | 70 | 70 |
| 신규 정원오 | 58 | 1 | 3 | 17 | 37 | 37 | 37 |
| 신규 오세훈 | 147 | 3 | 9 | 73 | 62 | 62 | 62 |
| 최종 통합 | 391 | 7 | 54 | 161 | 169 | 169 | 169 |

메시지 추천용 row는 최종 통합 기준 384건이며, 신규 데이터 기준 201건이다.

## 3. 정규화 및 검수 결과

한글 OCR 언어 데이터(`kor`)가 설치되어 있지 않아 자동 OCR 확정 추출 성공 건수는 0건이다. 대신 이미지 원문을 육안 검수해 `output/gold_set_drafts/manual_reviewed_new_gold_set_20260427_20260525.csv`를 만들었다.

| 항목 | 건수 |
|---|---:|
| 자동 OCR 확정 추출 성공 | 0 |
| 수동 전사 신규 row | 205 |
| review_required=True | 205 |
| 상세 주소 확인 필요 | 205 |
| district 누락 또는 장소추천 제외 온라인/방송 row | 12 |
| place_name 불명확 | 0 |

주소가 작은 글씨로만 제공된 경우가 많아 `address=확인 필요`와 review 사유를 남겼다. 장소 추천 query 생성은 `gold_label_0_3 == 3`, offline, place_name 존재, district 존재 조건만 통과시켰다.

## 4. 기존 Gold Set과의 통합 결과

| 항목 | row |
|---|---:|
| 통합 전 기존 로드 row | 744 |
| 기존 고유 row | 186 |
| 신규 추가 row | 205 |
| 중복 제거 row | 558 |
| 최종 통합 row | 391 |

최종 산출물은 `output/gold_set_all_candidates.csv`, `output/gold_set_jungwono_extended.csv`, `output/gold_set_ohsehoon.csv`에 저장했다. `gold_id`는 후보별로 `JG_0001`, `OH_0001` 형식으로 재부여했으며 중복은 없다.

## 5. 추천 알고리즘 평가 결과

| model | P@1 | P@3 | P@5 | P@10 | R@1 | R@3 | R@5 | R@10 | NDCG@1 | NDCG@3 | NDCG@5 | NDCG@10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0.0178 | 0.0079 | 0.0154 | 0.0249 | 0.0178 | 0.0237 | 0.0769 | 0.2485 | 0.0178 | 0.0215 | 0.0429 | 0.0963 |
| proposed | 0.0710 | 0.0671 | 0.0793 | 0.0680 | 0.0710 | 0.2012 | 0.3964 | 0.6805 | 0.0710 | 0.1469 | 0.2264 | 0.3182 |
| optimized_proposed | 0.2899 | 0.2032 | 0.1420 | 0.0941 | 0.2899 | 0.6095 | 0.7101 | 0.9408 | 0.2899 | 0.4745 | 0.5150 | 0.5913 |

가중치 최적화 결과는 `output/experiments_all_candidates/optimized/best_weights.json`에 저장했다. 최적 가중치는 district 0.7, place_type 0.3, context 0.2, baseline 1.0이다.

## 6. Candidate Generation 병목 분석

| 상태 | raw candidate recall@50 | raw 후보군에 정답 없음 | 후보군에는 있으나 optimized Top10 실패 |
|---|---:|---:|---:|
| alias 보강 전 | 0.2485 | 127 | - |
| alias 보강 후 | 1.0000 | 0 | 10 |

alias 보강 전 주요 누락 place_type은 교통거점 32건, 공원 21건, 정책현장 16건, 전통시장 13건, 골목상권 12건, 재개발/도시개발현장 10건이었다.

이번 작업에서 `data/processed/place_aliases.csv`에 신규 strong-positive 장소 및 역/시장/공원/상권 변형 119건을 추가했다. 이 개선은 candidate generation coverage 개선이며, reranking 성능 개선과 구분해서 해석해야 한다.

## 7. 논문 반영용 해석

이번 확장은 정원오 단일 후보의 공개 일정 기반 Gold Set을 정원오 확장 데이터와 오세훈 신규 후보 데이터로 넓혔다. 동일한 서울시장 선거 맥락에서 후보별 일정 패턴과 유세 장소 선택을 비교할 수 있게 되었고, 기존 평가가 한 후보의 일정 스타일에 과도하게 맞춰질 수 있는 한계를 완화했다.

실험은 raw candidate pool 생성과 reranking 단계를 분리해 보여준다. alias 보강 전에는 raw Top50에 실제 방문 장소가 포함되지 않는 query가 127건이었고, 이 경우 reranking은 정답을 복구할 수 없다. alias table과 후보군 source 보강 후 raw recall@50은 1.0이 되었으며, 남은 오류는 후보군 내부의 상위 배치 문제로 해석된다.

따라서 추천 성능의 상한은 단순 가중치 조정만이 아니라 실제 후보 방문 장소가 raw candidate pool에 포함되는지, 즉 candidate generation coverage에 크게 의존한다. reranking은 후보군 안에 존재하는 정답을 상위로 올리는 데 효과적이지만, 후보군 자체에 없는 정답을 생성하지는 못한다.
