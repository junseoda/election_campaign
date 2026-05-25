# alias 보강 전/후 ablation 검증 보고서

| setting | query_count | raw_candidate_rows | raw_recall_at_50 | missing_gold_count | baseline_p_at_1 | baseline_r_at_10 | baseline_ndcg_at_10 | proposed_p_at_1 | proposed_r_at_10 | proposed_ndcg_at_10 | optimized_p_at_1 | optimized_r_at_10 | optimized_ndcg_at_10 | interpretation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| no_alias | 169 | 7114 | 0.2485207100591716 | 127 | 0.01775147928994083 | 0.2485207100591716 | 0.09630789486458614 | 0.07100591715976332 | 0.2485207100591716 | 0.14360014500940002 | 0.10059171597633136 | 0.2485207100591716 | 0.16903179871843646 | Gold-derived alias를 적용하지 않은 기존 MVP 후보군 coverage 기준 |
| with_alias | 169 | 7259 | 1.0 | 0 | 0.01775147928994083 | 0.2485207100591716 | 0.09630789486458614 | 0.07100591715976332 | 0.6804733727810651 | 0.31822576680259196 | 0.28994082840236685 | 0.9408284023668639 | 0.5913019224255992 | Gold Set 기반 alias 후보를 추가한 candidate generation coverage 보강 기준 |

## 해석

- no_alias raw recall@50: 0.2485
- with_alias raw recall@50: 1.0000
- alias 보강 후 성능 상승은 모델 일반화 성능 향상으로 해석하지 않는다.
- Gold Set strong positive 장소명을 후보군 생성 alias에 반영한 candidate generation coverage 보강 실험으로 해석해야 한다.
- 후보군에 정답이 없으면 reranking은 해당 정답을 복구할 수 없다.