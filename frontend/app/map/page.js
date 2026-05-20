"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AppShell,
  Card,
  EmptyState,
  ErrorState,
  HeroHeader,
  LoadingState,
  MetricCard,
  Section,
  STATIC_DEMO_MESSAGE,
  Tag,
  buildShortReason,
  fetchJson,
  formatNumber,
  getFitLabel,
  getStopId,
  getTimeRange,
} from "../components/camp/CampUI";
import KakaoRouteMap from "../components/map/KakaoRouteMap";

const FILTERS = ["전체", "교통거점", "전통시장", "복지시설", "공원", "기타"];

function hasCoordinates(stop = {}) {
  return (
    Number.isFinite(Number(stop.lat)) && Number.isFinite(Number(stop.lng))
  ) || (
    Number.isFinite(Number(stop.map_position?.lat)) &&
    Number.isFinite(Number(stop.map_position?.lng))
  );
}

function buildStops(timeline = []) {
  return timeline.map((item, index) => ({
    ...item,
    id: getStopId(item, index),
    sequence: item.order || index + 1,
    reason: buildShortReason(item),
    fit_label: getFitLabel(item.score),
  }));
}

function matchesFilter(stop, filter) {
  if (filter === "전체") {
    return true;
  }
  if (filter === "기타") {
    return !["교통거점", "전통시장", "복지시설", "공원"].includes(stop.place_type);
  }
  return stop.place_type === filter;
}

export default function MapPreviewPage() {
  const [route, setRoute] = useState(null);
  const [selectedStopId, setSelectedStopId] = useState("stop-1");
  const [filter, setFilter] = useState("전체");
  const [errorMessage, setErrorMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  const stops = useMemo(() => buildStops(route?.timeline || []), [route]);
  const filteredStops = useMemo(() => stops.filter((stop) => matchesFilter(stop, filter)), [stops, filter]);
  const markerStops = useMemo(() => filteredStops.filter(hasCoordinates), [filteredStops]);
  const selectedStop = useMemo(
    () => stops.find((stop) => stop.id === selectedStopId) || filteredStops[0] || stops[0],
    [stops, filteredStops, selectedStopId]
  );

  const loadMapData = useCallback(async () => {
    try {
      setIsLoading(true);
      setErrorMessage("");
      const payload = await fetchJson("/route/sample");
      setRoute(payload);
      setSelectedStopId(`stop-${payload?.timeline?.[0]?.order || 1}`);
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMapData();
  }, [loadMapData]);

  useEffect(() => {
    if (!stops.length || typeof window === "undefined") {
      return;
    }

    const params = new URLSearchParams(window.location.search);
    const place = params.get("place");
    const district = params.get("district");
    const matched = stops.find((stop) =>
      (!place || stop.place_name.includes(place) || place.includes(stop.place_name)) &&
      (!district || stop.district === district)
    );
    if (matched) {
      setSelectedStopId(matched.id);
      setFilter("전체");
    }
  }, [stops]);

  useEffect(() => {
    if (!filteredStops.length) {
      return;
    }
    if (!filteredStops.some((stop) => stop.id === selectedStopId)) {
      setSelectedStopId(filteredStops[0].id);
    }
  }, [filteredStops, selectedStopId]);

  const districts = [...new Set(stops.map((stop) => stop.district).filter(Boolean))];

  return (
    <AppShell active="map">
      <HeroHeader
        eyebrow="지도 기반 위치 확인"
        title="추천 동선 미리보기"
        description="추천된 방문 지점을 지도에서 확인합니다."
        meta={
          <div>
            <span>표시 장소</span>
            <strong>{formatNumber(stops.length || 0)}</strong>
            <small>{districts.join(", ") || "자치구 확인"}</small>
          </div>
        }
      />

      {errorMessage ? <ErrorState message={errorMessage} onRetry={loadMapData} /> : null}
      {isLoading ? <LoadingState title="지도 데이터를 준비하고 있어요" /> : null}
      {!isLoading && !errorMessage && route?.static_fallback ? (
        <div className="demoNotice" role="status">
          <Tag tone="amber">정적 데모 모드</Tag>
          <span>{route.fallback_message || STATIC_DEMO_MESSAGE}</span>
        </div>
      ) : null}

      {!isLoading && !errorMessage ? (
        <div className="mapPageGrid">
          <section className="mapMainPane">
            <div className="mapFilterBar" aria-label="장소 유형 필터">
              {FILTERS.map((item) => (
                <button
                  key={item}
                  type="button"
                  className={filter === item ? "selected" : ""}
                  onClick={() => setFilter(item)}
                >
                  {item}
                </button>
              ))}
            </div>
            <KakaoRouteMap
              stops={markerStops}
              selectedStopId={selectedStopId}
              onSelectStop={setSelectedStopId}
              startLabel={route?.summary?.start_location || "성동구청"}
            />
            <Card className="mapLegendCard">
              <div><span className="legend-dot orange" />추천 장소</div>
              <div><span className="legend-dot dark" />선택 장소</div>
              <div><span className="legend-dot muted" />좌표 확인 필요</div>
            </Card>
          </section>

          <aside className="mapSidePane">
            <section className="metricGrid compactMetrics">
              <MetricCard label="표시 장소" value={`${formatNumber(filteredStops.length)}곳`} caption="지도에 표시된 방문 지점" tone="amber" />
              <MetricCard label="정렬 기준" value="추천 순서" caption="시간대별 방문 흐름" />
            </section>

            <Card className="selectedRouteCard">
              <Tag tone="amber">선택 장소</Tag>
              {selectedStop ? (
                <>
                  <h2>{selectedStop.place_name}</h2>
                  <p>{getTimeRange(selectedStop.time)} · {selectedStop.district} · {selectedStop.place_type}</p>
                  <span className="selectedScore">{selectedStop.fit_label}</span>
                  <p>{selectedStop.reason}</p>
                </>
              ) : (
                <EmptyState title="선택된 장소가 없습니다" />
              )}
            </Card>

            <Section
              eyebrow="추천 장소"
              title="추천 장소 목록"
              description="목록을 누르면 지도 marker가 함께 바뀝니다."
              className="embeddedSection"
            >
              <div className="mapStopList">
                {filteredStops.map((stop) => (
                  <button
                    type="button"
                    key={stop.id}
                    className={selectedStopId === stop.id ? "active" : ""}
                    onClick={() => setSelectedStopId(stop.id)}
                  >
                    <span>{stop.sequence}</span>
                    <div>
                      <strong>{stop.place_name}</strong>
                      <small>{stop.time || "시간 확인"} · {stop.district} · {stop.place_type}</small>
                      {!hasCoordinates(stop) ? <small className="coordWarning">좌표 확인 필요</small> : null}
                    </div>
                    <em>{stop.fit_label}</em>
                  </button>
                ))}
                {!filteredStops.length ? <EmptyState title="필터에 맞는 장소가 없습니다" /> : null}
              </div>
            </Section>
          </aside>
        </div>
      ) : null}
    </AppShell>
  );
}
