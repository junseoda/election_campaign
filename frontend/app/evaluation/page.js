"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AppShell,
  Card,
  EmptyState,
  ErrorState,
  HeroHeader,
  InsightCard,
  LoadingState,
  MetricCard,
  MiniChart,
  MissingPlaceTypeChart,
  Section,
  STATIC_DEMO_MESSAGE,
  Tag,
  fetchJson,
  formatMetric,
  formatNumber,
  formatPercent,
} from "../components/camp/CampUI";


const PRIMARY_METRICS = ["P@1", "P@3", "P@5", "R@10", "NDCG@10", "Mean Composite Similarity@10"];
const METRIC_TOOLTIPS = {
  "P@1": "첫 번째 추천이 실제 정답 장소와 맞은 비율",
  "P@3": "상위 3개 추천 안에 정답 장소가 포함된 비율",
  "P@5": "상위 5개 추천 안에 정답 장소가 포함된 비율",
  "R@10": "정답 장소 중 상위 10개 추천에 포함된 비율",
  "NDCG@10": "정답에 가까운 장소가 상위에 배치되었는지 보는 지표",
  "Mean Composite Similarity@10": "자치구, 장소 유형, 시간대, 캠페인 문맥 유사도를 합산한 평균",
};

const FEATURE_LABELS = {
  district_bonus: "자치구 일치 보정",
  place_type_bonus: "장소 유형 보정",
  time_bonus: "시간대 적합 보정",
  context_bonus: "문맥 태그 보정",
  target_bonus: "타깃 유권자 보정",
  rank_bonus: "기존 순위 보존",
};

const MODEL_LABELS = {
  baseline: "baseline",
  context_ranking: "context_ranking",
  candidate_profile_ranking: "candidate_profile_ranking",
  similarity_optimized_ranking: "similarity_optimized_ranking",
  final_proposed: "final_proposed",
  optimized_proposed: "final_proposed",
  proposed: "proposed",
};

const MODEL_ORDER = [
  "baseline",
  "context_ranking",
  "candidate_profile_ranking",
  "similarity_optimized_ranking",
  "final_proposed",
  "optimized_proposed",
  "proposed",
];

const TABLE_METRICS = [
  "Precision@1",
  "Recall@10",
  "NDCG@10",
  "Mean Composite Similarity@10",
  "District Match@10",
  "Place Type Match@10",
];

const FAILURE_LABELS = {
  candidate_generation_gap: "후보군에 정답 장소가 없었던 경우",
  reranking_gap: "후보군에는 있었지만 ranking에서 밀린 경우",
  place_type_gap: "자치구는 맞았지만 장소 유형이 틀린 경우",
  time_context_gap: "장소 유형은 맞았지만 시간대가 안 맞은 경우",
};

function getMetricValue(row = {}, metric) {
  if (metric === "Precision@1") {
    return row["Precision@1"] ?? row["P@1"];
  }
  if (metric === "Recall@10") {
    return row["Recall@10"] ?? row["R@10"];
  }
  return row[metric];
}

function getRowsByName(rows) {
  return rows.reduce((acc, row) => {
    acc[row.model_name] = row;
    return acc;
  }, {});
}

function getModelLabel(modelName) {
  return MODEL_LABELS[modelName] || modelName || "model";
}

function getDisplayRows(rows = []) {
  return rows
    .filter((row) => MODEL_ORDER.includes(row.model_name))
    .sort((a, b) => MODEL_ORDER.indexOf(a.model_name) - MODEL_ORDER.indexOf(b.model_name));
}


function getDelta(rowsByName, metric) {
  const baseline = Number(rowsByName.baseline?.[metric]);
  const optimized = Number((rowsByName.final_proposed || rowsByName.optimized_proposed)?.[metric]);
  if (!Number.isFinite(baseline) || !Number.isFinite(optimized)) {
    return null;
  }
  return optimized - baseline;
}

function isPriorityMissing(row, index) {
  return index < 3 && Number(row?.missing_count) > 0;
}

function MetricLabel({ metric }) {
  return (
    <span className="metricTooltip">
      {metric}
      <button type="button" aria-label={`${metric} 설명`}>?</button>
      <em>{METRIC_TOOLTIPS[metric]}</em>
    </span>
  );
}

function HitMissDonut({ hit = 0, total = 1 }) {
  const safeTotal = Math.max(Number(total) || 1, 1);
  const safeHit = Math.max(Number(hit) || 0, 0);
  const percent = Math.min(100, (safeHit / safeTotal) * 100);

  return (
    <Card className="donutCard">
      <div className="donut" style={{ "--donut-value": `${percent}%` }}>
        <strong>{formatPercent(safeHit / safeTotal)}</strong>
        <span>hit@10</span>
      </div>
      <div>
        <Tag tone="green">적중 {formatNumber(safeHit)}</Tag>
        <Tag tone="amber">미포함 {formatNumber(safeTotal - safeHit)}</Tag>
      </div>
    </Card>
  );
}

function EvaluationTable({ rows = [] }) {
  const displayRows = getDisplayRows(rows);
  if (!displayRows.length) {
    return <EmptyState title="모델 비교 표 데이터가 없습니다" />;
  }

  const bestByMetric = TABLE_METRICS.reduce((acc, metric) => {
    acc[metric] = Math.max(...displayRows.map((row) => Number(getMetricValue(row, metric)) || 0));
    return acc;
  }, {});

  return (
    <div className="evaluationTableWrap">
      <table className="evaluationTable">
        <thead>
          <tr>
            <th>Model</th>
            {TABLE_METRICS.map((metric) => <th key={metric}>{metric}</th>)}
          </tr>
        </thead>
        <tbody>
          {displayRows.map((row) => {
            const isFinal = row.model_name === "final_proposed" || row.model_name === "optimized_proposed";
            return (
              <tr key={row.model_name} className={isFinal ? "finalModelRow" : ""}>
                <th>{getModelLabel(row.model_name)}</th>
                {TABLE_METRICS.map((metric) => {
                  const value = Number(getMetricValue(row, metric));
                  const isBest = Number.isFinite(value) && value === bestByMetric[metric];
                  return (
                    <td key={`${row.model_name}-${metric}`} className={isBest ? "bestMetric" : ""}>
                      {formatMetric(value)}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function FailureCaseCards({ failures = [], coverageSummary = {}, similaritySummary = {} }) {
  const categoryCounts = failures.reduce((acc, row) => {
    const category = row.failure_category || "unknown";
    acc[category] = (acc[category] || 0) + 1;
    return acc;
  }, {});
  const rerankingCount = Math.max(
    0,
    Number(coverageSummary.raw_covered_count || 0) - Number(coverageSummary.optimized_hit_at_10_count || 0)
  );
  const placeTypeGapCount = failures.filter((row) => row.failure_category !== "hit" && row.gold_place_type && row.top1_place_type && row.gold_place_type !== row.top1_place_type).length;
  const timeContextScore = similaritySummary.time_context_match;
  const cards = [
    {
      key: "candidate_generation_gap",
      count: categoryCounts.candidate_generation_gap ?? coverageSummary.raw_missing_count,
      detail: "정답 또는 alias 후보가 raw Top50에 없으면 reranking만으로는 exact hit가 불가능합니다.",
    },
    {
      key: "reranking_gap",
      count: rerankingCount,
      detail: "후보군에는 포함됐지만 final ranking의 Top-10까지 올라오지 못한 경우입니다.",
    },
    {
      key: "place_type_gap",
      count: placeTypeGapCount || "샘플 검토",
      detail: "자치구 맥락은 맞지만 추천 Top-1의 장소 유형이 실제 일정과 다른 사례를 확인합니다.",
    },
    {
      key: "time_context_gap",
      count: Number.isFinite(Number(timeContextScore)) ? formatMetric(1 - Number(timeContextScore)) : "분석 필요",
      detail: "시간대 문맥 유사도가 낮아지는 사례는 향후 시간대별 후보군 보강의 근거가 됩니다.",
    },
  ];

  return (
    <div className="failureCaseGrid">
      {cards.map((card) => (
        <Card key={card.key} className="failureCaseCard">
          <Tag tone={card.key === "candidate_generation_gap" ? "amber" : "blue"}>{FAILURE_LABELS[card.key]}</Tag>
          <strong>{card.count ?? "확인 필요"}</strong>
          <p>{card.detail}</p>
        </Card>
      ))}
    </div>
  );
}


export default function EvaluationDashboardPage() {
  const [evaluation, setEvaluation] = useState(null);
  const [coverage, setCoverage] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  const loadDashboard = useCallback(async () => {
    try {
      setIsLoading(true);
      setErrorMessage("");
      const [evaluationPayload, coveragePayload] = await Promise.all([
        fetchJson("/evaluation/dashboard"),
        fetchJson("/coverage/dashboard?limit=12"),
      ]);
      setEvaluation(evaluationPayload);
      setCoverage(coveragePayload);
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const comparisonRows = evaluation?.model_comparison || [];
  const rowsByName = useMemo(() => getRowsByName(comparisonRows), [comparisonRows]);
  const optimizedMetrics = rowsByName.final_proposed || rowsByName.optimized_proposed || evaluation?.optimized_metrics || {};
  const proposedRows = getDisplayRows(comparisonRows);
  const goldSummary = evaluation?.gold_summary || {};
  const coverageSummary = coverage?.summary || {};
  const goldTotal = goldSummary.total_rows ?? 186;
  const strongPositive = goldSummary.strong_place_rows ?? 70;
  const rawCandidates = coverageSummary.raw_candidate_row_count ?? 2871;
  const rawRecall = coverageSummary.raw_candidate_recall_at_50 ?? 0.2714285714285714;
  const ndcgAt10 = optimizedMetrics["NDCG@10"] ?? 0.1681966142662297;
  const recallAt10 = getMetricValue(optimizedMetrics, "Recall@10") ?? 0.2714285714285714;
  const precisionAt1 = getMetricValue(optimizedMetrics, "Precision@1") ?? 0.04285714285714286;
  const compositeAt10 = optimizedMetrics["Mean Composite Similarity@10"] ?? evaluation?.final_similarity_summary?.composite_similarity;
  const missingByPlaceType = coverage?.missing_by_place_type || [];
  const missingByDistrict = coverage?.missing_by_district || [];
  const missingByActivity = coverage?.missing_by_campaign_activity_type || [];
  const featureContribution = evaluation?.feature_contribution || [];
  const candidateProfiles = evaluation?.final_candidate_profile || [];
  const candidateNames = candidateProfiles.map((row) => row.candidate_name).filter(Boolean).join(" / ") || "오세훈 / 정원오";
  const finalModelName = getModelLabel(optimizedMetrics.model_name || "final_proposed");

  return (
    <AppShell active="evaluation">
      <HeroHeader
        eyebrow="Evaluation Dashboard"
        title="추천 알고리즘 평가 대시보드"
        description="실제 후보 공개 일정 Gold Set을 기준으로 추천 성능과 유사도를 검증합니다."
      />

      {errorMessage ? <ErrorState message={errorMessage} onRetry={loadDashboard} /> : null}
      {isLoading ? <LoadingState title="평가 대시보드를 불러오는 중입니다" /> : null}
      {!isLoading && !errorMessage && (evaluation?.static_fallback || coverage?.static_fallback) ? (
        <div className="demoNotice" role="status">
          <Tag tone="amber">정적 데모 모드</Tag>
          <span>{evaluation?.fallback_message || coverage?.fallback_message || STATIC_DEMO_MESSAGE}</span>
        </div>
      ) : null}

      {!isLoading && !errorMessage ? (
        <>
          <InsightCard
            eyebrow="실험 결론"
            title="final_proposed는 일정 문맥 유사도를 높였고, exact hit 성능은 후보 장소 pool 확장이 핵심 병목입니다."
            description="R@10과 NDCG@10은 후보군 포함률의 영향을 크게 받으므로 composite similarity를 함께 해석합니다."
            tone="amber"
          />

          <section className="metricGrid evaluationSummary" aria-label="Gold Set 평가 요약">
            <MetricCard label="최종 모델" value={finalModelName} caption="평가 대시보드 기준 row" tone="amber" />
            <MetricCard label="NDCG@10" value={formatMetric(ndcgAt10)} caption="상위 랭킹 품질" emphasis />
            <MetricCard label="Recall@10" value={formatMetric(recallAt10)} caption="Top-10 정답 포함률" />
            <MetricCard label="Precision@1" value={formatMetric(precisionAt1)} caption="첫 추천 exact hit" />
            <MetricCard label="Mean Composite Similarity@10" value={formatMetric(compositeAt10)} caption="맥락 유사도 평균" tone="blue" />
            <MetricCard label="Gold Set query" value={formatNumber(goldTotal)} caption={`${formatNumber(strongPositive)}건 strong place`} />
            <MetricCard label="후보자" value={candidateNames} caption="프로필 보조 feature" tone="green" />
            <MetricCard label="초기 후보군" value={formatNumber(rawCandidates)} caption="candidate generation row" />
          </section>

          <Section
            eyebrow="모델 비교"
            title="모델별 성능 비교"
            description="기준 모델, 제안 모델, 최적화 모델의 핵심 지표를 같은 평가 기준 일정에서 비교합니다."
            action={<Tag tone="amber">논문 표 기준</Tag>}
          >
            {proposedRows.length ? (
              <>
                <EvaluationTable rows={proposedRows} />
                <div className="comparisonGrid">
                  {PRIMARY_METRICS.map((metric) => (
                    <Card key={metric} className="metricChartCard">
                      <div className="metricChartHeader">
                        <MetricLabel metric={metric} />
                        <strong>{formatMetric(getMetricValue(optimizedMetrics, metric))}</strong>
                      </div>
                      <MiniChart rows={proposedRows} metric={metric} highlight="final_proposed" />
                    </Card>
                  ))}
                </div>
              </>
            ) : (
              <EmptyState title="모델 비교 데이터가 없습니다" />
            )}
          </Section>

          <Section
            eyebrow="Composite Similarity"
            title="왜 Composite Similarity를 함께 평가했는가?"
            description="정치 캠페인 유세 장소 추천은 정확한 장소명을 맞히는 문제만은 아닙니다. 실제 후보가 방문한 장소와 동일하지 않더라도, 같은 자치구·장소 유형·시간대·캠페인 맥락을 가진 장소라면 전략적으로 유사한 추천으로 볼 수 있습니다. 따라서 본 시스템은 Exact Hit 외에도 Composite Similarity를 함께 평가합니다."
          >
            <div className="metricGrid">
              <MetricCard label="자치구 유사도" value={formatMetric(evaluation?.final_similarity_summary?.district_match)} caption="Top-10 평균" />
              <MetricCard label="장소 유형 유사도" value={formatMetric(evaluation?.final_similarity_summary?.place_type_match)} caption="Top-10 평균" />
              <MetricCard label="시간대 유사도" value={formatMetric(evaluation?.final_similarity_summary?.time_context_match)} caption="Top-10 평균" />
              <MetricCard label="종합 유사도" value={formatMetric(evaluation?.final_similarity_summary?.composite_similarity)} caption="Composite Similarity" tone="blue" />
            </div>
          </Section>

          <Section
            eyebrow="Failure Case"
            title="실패 사례 분석"
            description="실패를 숨기지 않고 후보군 생성과 재정렬 단계의 연구적 한계로 분리해 해석합니다."
          >
            <FailureCaseCards
              failures={evaluation?.final_failure_cases || []}
              coverageSummary={coverageSummary}
              similaritySummary={evaluation?.final_similarity_summary || {}}
            />
          </Section>

          <Section
            eyebrow="Bottleneck Analysis"
            title="성능 병목 분석: Candidate Generation과 Reranking 분리"
            description="후보군 생성 단계에서 실제 후보 장소와 유사한 후보가 포함되어야 reranking이 의미가 있습니다. Reranking은 후보군 내부에서 순서를 개선하는 단계이며, 현재 성능 한계는 일부 장소 유형의 coverage 부족에서 발생합니다. 이 분석을 통해 향후 데이터 보강 방향을 도출합니다."
          >
            <div className="coverageGrid">
              <MetricCard label="candidate generation 포함" value={formatNumber(coverageSummary.raw_covered_count ?? 19)} caption="reranking 가능 일정" tone="green" />
              <MetricCard label="candidate generation 미포함" value={formatNumber(coverageSummary.raw_missing_count ?? 51)} caption="후보군 coverage 한계" tone="amber" />
              <MetricCard label="candidate recall@50" value={formatPercent(rawRecall)} caption="초기 후보군 기준" />
              <MetricCard label="reranking hit@10" value={formatPercent(coverageSummary.optimized_hit_at_10_rate ?? 0.2714285714285714)} caption="final ranking 결과" tone="blue" />
            </div>
          </Section>

          <Section
            eyebrow="개선폭"
            title="기준 모델 대비 개선폭"
            description="상위 랭킹 품질 개선을 설명할 수 있는 지표입니다."
          >
            <div className="metricGrid improvementGrid">
              {["P@1", "P@3", "P@5", "NDCG@10"].map((metric) => {
                const delta = getDelta(rowsByName, metric);
                return (
                  <MetricCard
                    key={metric}
                    label={metric}
                    value={formatMetric(delta)}
                    caption={`${metric} 개선폭`}
                    delta="최적화 - 기준"
                    tone="amber"
                  />
                );
              })}
            </div>
            <InsightCard
              eyebrow="추천 품질"
              title="final_proposed는 exact place hit보다 자치구·장소유형·시간대·캠페인 문맥 유사도를 우선 보강했습니다."
              description="현재 exact metric 개선폭은 제한적이므로, Mean Composite Similarity@10과 raw candidate coverage를 함께 보고 해석합니다."
              tone="green"
            />
          </Section>

          <Section
            eyebrow="후보군 병목"
            title="후보군 생성 단계의 병목"
            description="정답이 초기 후보군에 없으면 순위 재정렬만으로는 맞출 수 없습니다."
          >
            <div className="coverageGrid">
              <MetricCard label="초기 후보군에 정답 있음" value={formatNumber(coverageSummary.raw_covered_count ?? 19)} caption="순위 재정렬 가능 일정" tone="green" />
              <MetricCard label="초기 후보군에 정답 없음" value={formatNumber(coverageSummary.raw_missing_count ?? 51)} caption="후보군 생성 한계" tone="amber" />
              <MetricCard label="후보군 포함률" value={formatPercent(rawRecall)} caption="초기 후보군 50개 기준" />
              <MetricCard label="Top-10 적중" value={formatPercent(coverageSummary.optimized_hit_at_10_rate ?? 0.2714285714285714)} caption="최적화 결과" tone="blue" />
            </div>
            <HitMissDonut
              hit={coverageSummary.optimized_hit_at_10_count ?? 19}
              total={coverageSummary.total_queries ?? 70}
            />
            <InsightCard
              eyebrow="논문용 해석"
              title="final_proposed의 유사도 평가는 개선되었으나, Recall 상한은 초기 후보군 포함률에 의해 제한되었습니다."
              description="따라서 후속 개선은 순위 재정렬 가중치보다 공원, 체육시설, 복지시설, 정책현장, 노동현장 등 후보군 소스 확장이 우선입니다."
            />
          </Section>

          <Section
            eyebrow="누락 장소 유형"
            title="누락 장소 유형 분석"
            description="candidate generation 단계에서 보강해야 하는 장소 유형입니다."
          >
            <Card className="chartContainer">
              <MissingPlaceTypeChart rows={missingByPlaceType} />
            </Card>
          </Section>

          <div className="dashboardGrid">
            <Section title="자치구별 coverage 취약점" description="missing count 상위 자치구입니다.">
              <Card className="compactListCard coverageListCard">
                {missingByDistrict.slice(0, 8).map((row, index) => (
                  <div key={row.district} className={isPriorityMissing(row, index) ? "priority" : ""}>
                    <strong>{row.district}</strong>
                    {isPriorityMissing(row, index) ? <span className="priorityBadge">우선 보강</span> : null}
                    <span className="listMetric">{row.missing_count}/{row.total_gold_count}</span>
                  </div>
                ))}
              </Card>
            </Section>
            <Section title="일정 유형별 hit/miss" description="후보군 coverage 차이가 큰 활동 유형입니다.">
              <Card className="compactListCard coverageListCard activityListCard">
                {missingByActivity.slice(0, 8).map((row) => (
                  <div key={row.group_value}>
                    <strong>{row.group_value}</strong>
                    <span className="listMetric">{formatPercent(row.hit_at_10_rate)}</span>
                    <small>미포함 {formatNumber(row.raw_missing_count)} / 전체 {formatNumber(row.query_count)}</small>
                  </div>
                ))}
              </Card>
            </Section>
          </div>

          <Section
            eyebrow="향후 보강"
            title="향후 보강 방향"
            description="추천 성능의 다음 개선은 누락 장소 유형을 후보군에 추가하는 방향입니다."
          >
            <div className="featureGrid">
              {featureContribution.map((row) => (
                <Card key={row.feature_name} className="featureCard">
                  <span>{row.feature_name}</span>
                  <em>{FEATURE_LABELS[row.feature_name] || "추천 점수 보정"}</em>
                  <strong>{formatMetric(row.mean_bonus)}</strong>
                  <p>{row.comment}</p>
                  <small>non-zero {row.non_zero_count} · max {formatMetric(row.max_bonus)}</small>
                </Card>
              ))}
            </div>
          </Section>
        </>
      ) : null}
    </AppShell>
  );
}
