# Evaluation

> Evaluation design for the campaign place recommender.

## 목표

이 프로젝트의 평가는 단순히 추천 결과가 실제 장소명과 정확히 일치하는지만 보는 것이 아니라, 유세 장소 추천 문제에서 중요한 의사결정 맥락을 함께 확인하는 것을 목표로 합니다.

평가 관점은 세 가지입니다.

- 실제 후보 일정 기반 Gold Set과의 exact / partial hit
- raw candidate generation 단계의 coverage
- 자치구, 장소 유형, 시간대, 캠페인 문맥, 대상 유권자 관점의 유사도

## Metrics

| Metric | 설명 |
| --- | --- |
| Precision@K | Top K 추천 중 정답 또는 관련 장소 비율 |
| Recall@K | Gold Set 정답이 Top K 추천 안에 포함되는 비율 |
| NDCG@K | 관련 추천이 상위에 배치되었는지 반영 |
| Raw Recall@50 / @100 | raw candidate pool 안에 정답 후보가 존재하는지 |
| District Match@10 | Top 10 추천의 자치구 맥락 일치도 |
| Place Type Match@10 | Top 10 추천의 장소 유형 일치도 |
| Time Context Match@10 | 시간대 맥락 일치도 |
| Campaign Context Match@10 | 캠페인 활동 문맥 일치도 |
| Mean Composite Similarity@10 | 여러 유사도 feature를 결합한 평균 |

## 현재 확인된 결과

`output/experiments_optimized/model_comparison_optimized.csv` 기준:

| Model | P@1 | P@3 | P@5 | R@10 | NDCG@10 | Optimization Score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 0.0286 | 0.0095 | 0.0200 | 0.2714 | 0.1105 | 0.0769 |
| district_weighted | 0.0429 | 0.0286 | 0.0371 | 0.2714 | 0.1334 | 0.0940 |
| proposed | 0.0429 | 0.0286 | 0.0371 | 0.2714 | 0.1334 | 0.0940 |
| optimized_proposed | 0.0714 | 0.0571 | 0.0457 | 0.2714 | 0.1682 | 0.1199 |

`output/final_ranking_model_comparison.csv`와 `output/final_evaluation_summary.md`에는 최종 ranking pipeline의 추가 평가 결과가 저장되어 있습니다.

## 재현 방법

```bash
py src/final_ranking_pipeline.py \
  --gold output/gold_set_evaluation_queries.csv \
  --raw output/raw_baseline_recommendations.csv \
  --output_dir output \
  --top_k 10 \
  --search_mode random \
  --n_trials 80 \
  --random_state 42
```

## 해석상 주의점

- Raw Recall이 낮으면 reranking만으로는 정답 장소를 맞출 수 없습니다.
- Exact place hit는 엄격한 지표이므로, 유세 장소 추천의 실무적 유사성을 보기 위해 composite similarity를 함께 확인합니다.
- Gold Set은 공개 일정 기반이므로, 비공개 일정이나 실제 캠프 내부 판단은 반영하지 못합니다.
- 현재 결과는 프로젝트 저장소의 산출물 기준이며, 원본 데이터 업데이트나 Gold Set 수정 시 달라질 수 있습니다.

## 향후 개선

- candidate generation coverage 개선
- 장소명 alias와 좌표 정합성 검증 강화
- 실제 사용자 또는 도메인 전문가 기반 relevance label 보강
- train/validation split 외 별도 기간 기반 holdout 평가 추가
