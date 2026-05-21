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


const PRIMARY_METRICS = ["P@1", "P@3", "P@5", "R@10", "NDCG@10"];
const METRIC_TOOLTIPS = {
  "P@1": "첫 번째 추천이 실제 정답 장소와 맞은 비율",
  "P@3": "상위 3개 추천 안에 정답 장소가 포함된 비율",
  "P@5": "상위 5개 추천 안에 정답 장소가 포함된 비율",
  "R@10": "정답 장소 중 상위 10개 추천에 포함된 비율",
  "NDCG@10": "정답에 가까운 장소가 상위에 배치되었는지 보는 지표",
};

const FEATURE_LABELS = {
  district_bonus: "자치구 일치 보정",
  place_type_bonus: "장소 유형 보정",
  time_bonus: "시간대 적합 보정",
  context_bonus: "문맥 태그 보정",
  target_bonus: "타깃 유권자 보정",
  rank_bonus: "기존 순위 보존",
};


function getRowsByName(rows) {
  return rows.reduce((acc, row) => {
    acc[row.model_name] = row;
    return acc;
  }, {});
}


function getDelta(rowsByName, metric) {
  const baseline = Number(rowsByName.baseline?.[metric]);
  const optimized = Number(rowsByName.optimized_proposed?.[metric]);
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
  const optimizedMetrics = rowsByName.optimized_proposed || evaluation?.optimized_metrics || {};
  const proposedRows = comparisonRows.filter((row) =>
    ["baseline", "proposed", "optimized_proposed"].includes(row.model_name)
  );
  const goldSummary = evaluation?.gold_summary || {};
  const coverageSummary = coverage?.summary || {};
  const goldTotal = goldSummary.total_rows ?? 186;
  const strongPositive = goldSummary.strong_place_rows ?? 70;
  const rawCandidates = coverageSummary.raw_candidate_row_count ?? 2871;
  const rawRecall = coverageSummary.raw_candidate_recall_at_50 ?? 0.2714285714285714;
  const ndcgAt10 = optimizedMetrics["NDCG@10"] ?? 0.1681966142662297;
  const missingByPlaceType = coverage?.missing_by_place_type || [];
  const missingByDistrict = coverage?.missing_by_district || [];
  const missingByActivity = coverage?.missing_by_campaign_activity_type || [];
  const featureContribution = evaluation?.feature_contribution || [];

  return (
    <AppShell active="evaluation">
      <HeroHeader
        eyebrow="Gold Set 기반 성능 평가"
        title="추천 품질을 확인합니다"
        description="실제 후보 일정으로 추천 결과를 검증합니다."
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
            title="재랭킹 모델은 상위 추천 품질을 개선했지만, 추가 성능 향상은 후보 장소 pool 확장이 핵심입니다."
            description="R@10은 동일해 후보군 생성 단계의 coverage 한계가 남아 있습니다."
            tone="amber"
          />

          <section className="metricGrid evaluationSummary" aria-label="Gold Set 평가 요약">
            <MetricCard label="검증 일정" value={formatNumber(goldTotal)} caption="전체 일정" />
            <MetricCard label="정답 장소" value={formatNumber(strongPositive)} caption="오프라인 장소 정답" tone="amber" />
            <MetricCard label="초기 후보군" value={formatNumber(rawCandidates)} caption="기본 모델 후보 row" />
            <MetricCard label="NDCG@10" value={formatMetric(ndcgAt10)} caption="최적화 모델" emphasis />
          </section>

          <Section
            eyebrow="모델 비교"
            title="모델별 성능 비교"
            description="기준 모델, 제안 모델, 최적화 모델의 핵심 지표를 같은 평가 기준 일정에서 비교합니다."
            action={<Tag tone="amber">논문 표 기준</Tag>}
          >
            {proposedRows.length ? (
              <div className="comparisonGrid">
                {PRIMARY_METRICS.map((metric) => (
                  <Card key={metric} className="metricChartCard">
                    <div className="metricChartHeader">
                      <MetricLabel metric={metric} />
                      <strong>{formatMetric(optimizedMetrics[metric])}</strong>
                    </div>
                    <MiniChart rows={proposedRows} metric={metric} />
                  </Card>
                ))}
              </div>
            ) : (
              <EmptyState title="모델 비교 데이터가 없습니다" />
            )}
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
              title="최적화 모델은 후보군 내 정답 장소의 상위 배치를 개선했습니다."
              description="R@10은 동일하지만 P@1, P@3, P@5, NDCG@10이 개선되어, 새로운 정답 유입보다 기존 후보군 내부의 순위 품질 개선으로 해석됩니다."
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
              title="최적화 모델은 후보군 내 정답 장소의 상위 배치를 개선했으나, Recall 상한은 초기 후보군 포함률에 의해 제한되었습니다."
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
