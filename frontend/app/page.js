"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AppShell,
  ButtonLink,
  Card,
  EmptyState,
  ErrorState,
  HeroHeader,
  HeroMetricStack,
  InsightCard,
  LoadingState,
  MetricCard,
  RouteTimeline,
  ScheduleTimeline,
  Section,
  Tag,
  fetchJson,
  formatMetric,
  formatNumber,
  formatPercent,
  postJson,
} from "./components/camp/CampUI";
import KakaoRouteMap from "./components/map/KakaoRouteMap";


const FLOW_STEPS = [
  {
    title: "시작 위치 입력",
    description: "후보자의 현재 위치 또는 내일 출발지를 기준으로 하루 운영을 시작합니다.",
  },
  {
    title: "시간대별 후보 추천",
    description: "출근, 점심, 오후, 퇴근 시간대에 맞는 장소 유형을 우선 배치합니다.",
  },
  {
    title: "중복 방문 감점",
    description: "최근 방문 이력이 있는 장소는 우선순위를 낮춰 새로운 접촉 지점을 찾습니다.",
  },
  {
    title: "지도와 타임라인 확인",
    description: "추천된 지점을 번호 마커와 캠프 일정표 형태로 동시에 확인합니다.",
  },
];


function getRecentQueries(queries) {
  return [...queries]
    .sort((a, b) => `${b.date} ${b.time}`.localeCompare(`${a.date} ${a.time}`))
    .slice(0, 4);
}


export default function HomeDashboardPage() {
  const [queries, setQueries] = useState([]);
  const [recommendationData, setRecommendationData] = useState(null);
  const [routeData, setRouteData] = useState(null);
  const [evaluation, setEvaluation] = useState(null);
  const [coverage, setCoverage] = useState(null);
  const [selectedHomeStopId, setSelectedHomeStopId] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  const loadHomeData = useCallback(async () => {
    try {
      setIsLoading(true);
      setErrorMessage("");
      const queryPayload = await fetchJson("/api/optimized/queries?limit=100");
      const firstQueryId = queryPayload.queries?.[0]?.query_id;
      const [recommendationPayload, routePayload, evaluationPayload, coveragePayload] = await Promise.all([
        postJson("/api/recommend", {
          query_id: firstQueryId,
          limit: 10,
        }),
        fetchJson("/api/route/sample"),
        fetchJson("/api/evaluation/dashboard"),
        fetchJson("/api/coverage/dashboard?limit=8"),
      ]);

      setQueries(queryPayload.queries || []);
      setRecommendationData(recommendationPayload);
      setRouteData(routePayload);
      setEvaluation(evaluationPayload);
      setCoverage(coveragePayload);
      setSelectedHomeStopId(`stop-${routePayload?.timeline?.[0]?.order || 1}`);
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHomeData();
  }, [loadHomeData]);

  const recentQueries = useMemo(() => getRecentQueries(queries), [queries]);
  const topRecommendation = recommendationData?.recommendations?.[0];
  const routeTimeline = routeData?.timeline || [];
  const routeStops = routeTimeline.map((item) => ({
    ...item,
    id: `stop-${item.order}`,
    sequence: item.order,
    reason: item.recommendation_reason,
  }));
  const nextRouteItem = routeTimeline[0];
  const optimizedMetrics = evaluation?.optimized_metrics || {};
  const goldSummary = evaluation?.gold_summary || {};
  const coverageSummary = coverage?.summary || {};
  const goldTotal = goldSummary.total_rows ?? 186;
  const strongPositive = goldSummary.strong_place_rows ?? 70;
  const rawCandidates = coverageSummary.raw_candidate_row_count ?? 2871;
  const pAt1 = optimizedMetrics["P@1"] ?? 0.0714285714285714;
  const ndcgAt10 = optimizedMetrics["NDCG@10"] ?? 0.1681966142662297;
  const rawRecall = coverageSummary.raw_candidate_recall_at_50 ?? 0.2714285714285714;
  const routeDistricts = [...new Set(routeTimeline.map((item) => item.district).filter(Boolean))];
  return (
    <AppShell active="home">
      <HeroHeader
        eyebrow="Campaign Strategy Dashboard"
        title="서울시 공공데이터 기반 유세 전략 추천 시스템"
        description="실제 후보 일정과 도시 데이터를 결합해 유세 장소와 하루 동선을 추천하고, 추천 성능을 정량적으로 평가합니다."
        primaryAction={<ButtonLink href="/recommend">장소 추천 시작</ButtonLink>}
        secondaryAction={
          <>
            <ButtonLink href="/route" variant="secondary">동선 추천 보기</ButtonLink>
            <ButtonLink href="/evaluation" variant="secondary">평가 대시보드 보기</ButtonLink>
          </>
        }
        meta={
          <HeroMetricStack
            metrics={[
              { label: "내일 추천 일정", value: formatNumber(routeTimeline.length || 5), caption: "시간대별 방문 지점" },
              { label: "시작 위치", value: routeData?.summary?.start_location_district || "성동구", caption: routeData?.summary?.start_location || "성동구청" },
              { label: "중복 방문 감점", value: routeData?.summary?.avoid_duplicates ? "적용 중" : "미적용", caption: "최근 방문 이력 반영" },
            ]}
          />
        }
      />

      {errorMessage ? <ErrorState message={errorMessage} onRetry={loadHomeData} /> : null}
      {isLoading ? <LoadingState title="추천 데이터를 준비하고 있어요" /> : null}

      {!isLoading && !errorMessage ? (
        <>
          <section className="metricGrid homeMetrics" aria-label="핵심 실험 지표">
            <MetricCard label="단일 장소 추천" value={formatNumber(recommendationData?.recommendations?.length || 10)} caption="조건별 Top-K 후보지" tone="amber" />
            <MetricCard label="하루 동선 추천" value={formatNumber(routeTimeline.length || 5)} caption="지도와 타임라인 동시 확인" />
            <MetricCard label="Gold Set 평가" value={formatNumber(goldTotal)} caption="실제 후보 공개 일정" tone="blue" />
            <MetricCard label="NDCG@10" value={formatMetric(ndcgAt10)} caption="평가 대시보드에서 재현" tone="green" />
          </section>

          <div className="dashboardGrid">
            <div className="dashboardMain">
              <Card className="nextScheduleCard">
                <div className="cardHeaderLine">
                  <Tag tone="amber">다음 일정</Tag>
                  <span>{nextRouteItem?.time || "09:00"}</span>
                </div>
                <h2>{nextRouteItem?.place_name || topRecommendation?.recommended_place_name || "추천 장소 확인"}</h2>
                <p>{nextRouteItem?.district || topRecommendation?.recommended_district || "서울"} · {nextRouteItem?.place_type || topRecommendation?.recommended_place_type || "장소 유형"}</p>
                <p>{nextRouteItem?.recommendation_reason || "시간대, 지역, 타깃 유권자 조건을 반영해 다음 방문 지점을 추천합니다."}</p>
                <a href="/route" className="buttonLink secondary">동선 보기</a>
              </Card>
              <InsightCard
                eyebrow="운영 인사이트"
                title="최근 방문이 적은 지역을 우선 확인합니다."
                description="퇴근 시간대에는 교통거점과 상권 접점을 더 높게 봅니다."
              />
              <Section
                eyebrow="오늘의 추천 타임라인"
                title="시간대별 운영 미리보기"
                description="추천 동선의 앞부분을 일정표처럼 확인합니다."
                className="embeddedSection"
              >
                <RouteTimeline items={routeTimeline.slice(0, 4)} selectedOrder={routeTimeline[0]?.order || 1} />
              </Section>
            </div>
            <div className="dashboardSide">
              <div
                className="mapPreviewLink"
                role="button"
                tabIndex={0}
                aria-label="동선 지도 미리보기 열기"
                onClick={(event) => {
                  if (event.target.closest(".kakao-route-marker")) {
                    return;
                  }
                  window.location.href = "/route";
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    window.location.href = "/route";
                  }
                }}
              >
                <div className="mapToolbar inline">
                  <Tag tone="amber">동선 지도 미리보기</Tag>
                  <span>지도 기반 위치 확인</span>
                </div>
                <KakaoRouteMap
                  stops={routeStops}
                  selectedStopId={selectedHomeStopId}
                  onSelectStop={(stopId) => setSelectedHomeStopId(stopId)}
                  startLabel={routeData?.summary?.start_location || "성동구청"}
                  compact
                />
              </div>
              <Section
                eyebrow="동선 구성"
                title="하루 동선을 만드는 방식"
                description="후보 장소를 유지하고, 운영 조건으로 순위를 조정합니다."
                className="embeddedSection"
              >
                <div className="flowGrid compactFlow">
                  {FLOW_STEPS.map((step, index) => (
                    <Card key={step.title} className="flowCard">
                      <span>{String(index + 1).padStart(2, "0")}</span>
                      <h3>{step.title}</h3>
                      <p>{step.description}</p>
                    </Card>
                  ))}
                </div>
              </Section>
              <InsightCard
                eyebrow="추천 품질"
                title={`후보 일정 ${formatNumber(goldTotal)}건을 참고합니다.`}
                description="추천 품질과 연구 지표는 평가 대시보드에서 확인할 수 있습니다."
                tone="blue"
              />
            </div>
          </div>

          <Section
            eyebrow="Core Features"
            title="캠프 전략 회의에 바로 올릴 수 있는 세 가지 화면"
            description="장소 추천, 하루 동선, 알고리즘 평가를 한 흐름으로 확인합니다."
          >
            <div className="featureGrid">
              <InsightCard
                eyebrow="단일 장소 추천"
                title="조건에 맞는 유세 후보지를 빠르게 비교합니다."
                description="자치구, 시간대, 장소 유형, 타깃 유권자 조건을 기준으로 추천 근거를 함께 제공합니다."
                tone="blue"
              />
              <InsightCard
                eyebrow="하루 동선 추천"
                title="지도 marker와 일정 타임라인을 같은 순서로 검토합니다."
                description="좌표 확보 여부와 방문 순서를 함께 보여주어 실제 일정 확정에 필요한 리스크를 줄입니다."
                tone="green"
              />
              <InsightCard
                eyebrow="알고리즘 평가"
                title="Gold Set 기반 성능과 후보군 병목을 분리해 설명합니다."
                description="Precision@K, Recall@K, NDCG@K, Composite Similarity를 한 대시보드에서 해석합니다."
              />
            </div>
          </Section>

          <Section
            eyebrow="데이터 기반"
            title="실제 후보 일정과 공공데이터를 함께 사용합니다"
            description="추천 결과는 임의로 만든 데모 숫자가 아니라 평가용 Gold Set과 후보군 coverage 분석을 기준으로 해석합니다."
            action={<Tag tone="blue">검증 데이터</Tag>}
          >
            {recentQueries.length ? (
              <ScheduleTimeline items={recentQueries} />
            ) : (
              <EmptyState title="표시할 일정이 없습니다" message="gold_set_evaluation_queries.csv를 확인해주세요." />
            )}
          </Section>

          <Section
            eyebrow="운영/평가 분리"
            title="운영과 연구를 분리해 보여줍니다"
            description="사용 화면은 동선 중심, 성능 해석은 평가 화면에서 확인합니다."
          >
            <div className="insightGrid">
              <InsightCard
                eyebrow="운영 화면"
                title="후보자는 오늘/내일 어디로 갈지 먼저 확인합니다."
                description="지도 preview, 다음 일정, 추천 타임라인을 통해 캠프 운영 판단을 빠르게 돕습니다."
                tone="green"
              />
              <InsightCard
                eyebrow="연구 화면"
                title="성능 수치와 coverage 병목은 평가 대시보드에서 분리해 설명합니다."
                description={`검증 데이터 ${formatNumber(goldTotal)}건, 초기 후보 장소 ${formatNumber(rawCandidates)}개 row를 기반으로 재현 가능한 실험 결과를 유지합니다.`}
              />
            </div>
          </Section>
        </>
      ) : null}
    </AppShell>
  );
}
