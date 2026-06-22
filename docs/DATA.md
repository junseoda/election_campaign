# Data

> Data sources and processed artifacts used by the recommender and evaluation pipeline.

## 데이터 원칙

- README와 문서는 저장소에서 확인 가능한 processed/output 파일만 설명합니다.
- 원본 대용량 데이터, 민감 가능성이 있는 자료, 비공개 key는 공개 저장소에 포함하지 않는 것을 원칙으로 합니다.
- Gold Set의 장소명과 주소는 평가와 failure analysis에만 사용하며 ranking score에는 사용하지 않습니다.

## Processed Data

| File | 용도 |
| --- | --- |
| `data/processed/cleaned_subway.csv` | 지하철 승하차 기반 유세 후보 생성 |
| `data/processed/cleaned_parks.csv` | 공원 기반 후보 생성 |
| `data/processed/cleaned_market.csv` | 전통시장 기반 후보 생성 |
| `data/processed/cleaned_senior.csv` | 노인여가복지시설 기반 후보 생성 |
| `data/processed/cleaned_commercial_flow.csv` | 상권 유동인구 context 보정 |
| `data/processed/cleaned_worker_population.csv` | 직장인구 context 보정 |
| `data/processed/cleaned_living_population.csv` | 생활인구 context 보정 |
| `data/processed/aux_feature_summary.json` | 보조 feature 요약값 |
| `data/processed/place_aliases.csv` | 평가용 장소명 alias 보조 |

동일한 processed 데이터 일부는 백엔드 실행 편의를 위해 `backend/data/processed/`에도 있습니다.

## Gold Set

`gold set수작업/`과 `output/gold_set_*.csv`에는 후보 공개 일정 기반 Gold Set 및 평가 query가 포함되어 있습니다.

주요 산출물:

- `output/gold_set_all_merged.csv`
- `output/gold_set_strong_place_only.csv`
- `output/gold_set_evaluation_queries.csv`
- `output/gold_set_summary.json`

Gold label 기준은 기존 README와 평가 스크립트에서 사용한 방식과 동일하게, 오프라인 방문/장소성이 명확한 일정을 strong positive로 사용합니다.

## Evaluation Outputs

| File | 설명 |
| --- | --- |
| `output/final_ranking_model_comparison.csv` | 최종 모델 variant별 평가 결과 |
| `output/final_similarity_evaluation.csv` | 추천 결과와 Gold Set의 유사도 평가 |
| `output/final_candidate_coverage_analysis.csv` | raw candidate coverage 분석 |
| `output/final_failure_case_analysis.csv` | failure case 유형 분석 |
| `output/final_explainability_samples.csv` | 추천 설명 샘플 |
| `output/final_evaluation_summary.md` | 최종 ranking 평가 요약 |

## Data Leakage 방지

`src/final_ranking_pipeline.py` 기준으로 Gold Set의 실제 장소명, normalized key, 주소는 ranking score 계산에 사용하지 않습니다. 해당 값들은 평가 hit 판정, raw coverage 분석, failure case 판정에만 사용합니다.

## 보완 필요

- 원본 데이터 출처와 다운로드 일자를 별도 표로 정리
- 데이터 라이선스 확인
- `gold set수작업/`의 파일명과 원본 자료 공개 적합성 검토
- 대용량 원본 자료는 필요 시 Git LFS 또는 비공개 스토리지로 분리
