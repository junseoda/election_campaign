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
  RecommendationCard,
  Section,
  STATIC_DEMO_MESSAGE,
  Tag,
  fetchJson,
} from "../components/camp/CampUI";

function QuerySelector({ queries, selectedQueryId, selectedQuery, onChange, isDirty, isLoading }) {
  const chips = [
    selectedQuery?.date,
    selectedQuery?.time,
    selectedQuery?.district,
    selectedQuery?.place_type,
    selectedQuery?.target_voter_group,
  ].filter(Boolean);

  return (
    <Card className="querySelectorCard">
      <div className="cardHeaderLine">
        <label htmlFor="query-select">추천 조건</label>
        {isLoading ? <Tag tone="amber">조건 반영 중</Tag> : isDirty ? <Tag tone="amber">조건 변경됨</Tag> : <Tag tone="green">반영됨</Tag>}
      </div>
      <select
        id="query-select"
        value={selectedQueryId}
        onChange={(event) => onChange(event.target.value)}
        aria-label="추천 조건 선택"
      >
        {queries.map((query) => (
          <option key={query.query_id} value={query.query_id}>
            {query.date} {query.time} · {query.district} · {query.place_type}
          </option>
        ))}
      </select>
      <div className="chipRow">
        {chips.map((chip) => <Tag key={chip}>{chip}</Tag>)}
      </div>
    </Card>
  );
}

function QueryConditionCard({ query, coverage }) {
  const contextTags = String(query?.context_tags || "")
    .split(";")
    .map((tag) => tag.trim())
    .filter(Boolean)
    .slice(0, 5);

  return (
    <Card className="queryConditionCard">
      <div className="cardHeaderLine">
        <Tag tone="amber">선택 조건</Tag>
        <Tag tone={coverage?.in_raw_top50 ? "green" : "neutral"}>
          {coverage?.in_raw_top50 ? "검증 데이터 기반" : "추가 후보 검토"}
        </Tag>
      </div>
      <h2>{query?.district || "지역 선택"} · {query?.time || "시간 확인"}</h2>
      <p>{query?.evaluation_context || "조건을 선택하면 추천 맥락이 표시됩니다."}</p>
      <div className="conditionGrid">
        <div>
          <span>날짜</span>
          <strong>{query?.date || "확인 필요"}</strong>
        </div>
        <div>
          <span>장소 유형</span>
          <strong>{query?.place_type || "확인 필요"}</strong>
        </div>
        <div>
          <span>타깃</span>
          <strong>{query?.target_voter_group || "확인 필요"}</strong>
        </div>
        <div>
          <span>참고 장소</span>
          <strong>{query?.place_name || "확인 필요"}</strong>
        </div>
      </div>
      <div className="chipRow">
        {contextTags.length ? contextTags.map((tag) => <Tag key={tag}>{tag}</Tag>) : <Tag>상황 태그 없음</Tag>}
        <Tag tone="blue">실제 일정 기반</Tag>
      </div>
    </Card>
  );
}

export default function OptimizedDemoPage() {
  const [queries, setQueries] = useState([]);
  const [selectedQueryId, setSelectedQueryId] = useState("");
  const [recommendationData, setRecommendationData] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [isLoadingQueries, setIsLoadingQueries] = useState(true);
  const [isLoadingRecommendations, setIsLoadingRecommendations] = useState(false);
  const [isConditionDirty, setIsConditionDirty] = useState(false);

  const loadQueries = useCallback(async () => {
    try {
      setIsLoadingQueries(true);
      setErrorMessage("");
      const payload = await fetchJson("/optimized/queries?limit=100");
      const loadedQueries = payload.queries || [];
      setQueries(loadedQueries);
      setSelectedQueryId((current) => current || loadedQueries[0]?.query_id || "");
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsLoadingQueries(false);
    }
  }, []);

  const loadRecommendations = useCallback(async (queryId) => {
    if (!queryId) {
      return;
    }

    try {
      setIsLoadingRecommendations(true);
      setErrorMessage("");
      const payload = await fetchJson(`/optimized/recommendations?query_id=${encodeURIComponent(queryId)}&limit=10`);
      setRecommendationData(payload);
      setIsConditionDirty(false);
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsLoadingRecommendations(false);
    }
  }, []);

  useEffect(() => {
    loadQueries();
  }, [loadQueries]);

  useEffect(() => {
    loadRecommendations(selectedQueryId);
  }, [loadRecommendations, selectedQueryId]);

  const selectedQuery = useMemo(
    () => queries.find((query) => query.query_id === selectedQueryId) || recommendationData?.query,
    [queries, selectedQueryId, recommendationData]
  );
  const recommendations = recommendationData?.recommendations || [];
  const topRecommendation = recommendations[0];
  const compactRecommendations = recommendations.slice(1);
  const hitAnalysis = recommendationData?.hit_analysis?.[0];
  const coverage = recommendationData?.coverage?.[0];

  const handleQueryChange = useCallback((queryId) => {
    setSelectedQueryId(queryId);
    setIsConditionDirty(true);
  }, []);

  return (
    <AppShell active="recommend">
      <HeroHeader
        eyebrow="최적화 모델"
        title="유세 장소 추천"
        description="날짜, 시간, 지역, 장소 유형을 기준으로 후보지를 정렬합니다."
        meta={
          <div className="topKMeta">
            <span>Top-K</span>
            <strong>{recommendations.length}</strong>
            <small>추천 결과</small>
          </div>
        }
      />

      {errorMessage ? <ErrorState message={errorMessage} onRetry={() => selectedQueryId ? loadRecommendations(selectedQueryId) : loadQueries()} /> : null}
      {isLoadingQueries ? <LoadingState title="추천 조건을 준비하고 있어요" /> : null}
      {!isLoadingQueries && !errorMessage && recommendationData?.static_fallback ? (
        <div className="demoNotice" role="status">
          <Tag tone="amber">정적 데모 모드</Tag>
          <span>{recommendationData.fallback_message || STATIC_DEMO_MESSAGE}</span>
        </div>
      ) : null}

      {!isLoadingQueries && !errorMessage ? (
        <div className="recommendationWorkspace">
          <aside className="queryPane">
            <QuerySelector
              queries={queries}
              selectedQueryId={selectedQueryId}
              selectedQuery={selectedQuery}
              onChange={handleQueryChange}
              isDirty={isConditionDirty}
              isLoading={isLoadingRecommendations}
            />
            <QueryConditionCard query={selectedQuery} coverage={coverage} />
            <section className="metricGrid compactMetrics">
              <MetricCard label="모델" value="최적화 모델" caption="운영 조건 반영" tone="amber" />
              <MetricCard label="추천 수" value={`${recommendations.length}개`} caption="Top-K 결과" />
              <MetricCard
                label="참고 일정"
                value={hitAnalysis?.hit_at_10 ? "포함" : "확장 필요"}
                caption={hitAnalysis?.hit_at_10 ? "추천 목록에 포함" : "후보 장소 보강 필요"}
                tone={hitAnalysis?.hit_at_10 ? "green" : "neutral"}
              />
              <MetricCard
                label="정답 일치"
                value={hitAnalysis?.hit_at_10 ? `${hitAnalysis?.best_hit_rank || "-"}위` : "일치 없음"}
                caption="검증 데이터 기준"
                tone="blue"
              />
            </section>
            <InsightCard
              eyebrow="추천 방식"
              title="후보 장소를 유지하고 운영 조건으로 순위를 조정합니다."
              description="지역, 장소 유형, 시간대, 타깃 조건을 짧게 반영합니다."
            />
          </aside>

          <section className="rankingPane">
            <Section
              eyebrow="추천 결과"
              title="추천 결과"
              description="1위는 크게, 나머지는 빠르게 비교할 수 있게 정리했습니다."
              action={<Tag tone="amber">적합도순</Tag>}
            >
              {isLoadingRecommendations ? <LoadingState title="추천 조건을 반영하고 있어요" lines={2} /> : null}
              {!isLoadingRecommendations && topRecommendation ? (
                <div className="rankingList">
                  <RecommendationCard item={topRecommendation} query={selectedQuery} featured />
                  {compactRecommendations.map((item) => (
                    <RecommendationCard
                      key={`${item.query_id}-${item.rank}-${item.recommended_place_name}`}
                      item={item}
                      query={selectedQuery}
                    />
                  ))}
                </div>
              ) : null}
              {!isLoadingRecommendations && !recommendations.length ? (
                <EmptyState title="추천 결과가 없습니다" message="추천 결과 CSV를 확인해주세요." />
              ) : null}
            </Section>
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
