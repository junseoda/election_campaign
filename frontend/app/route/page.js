"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AppShell,
  Card,
  EmptyState,
  ErrorState,
  HeroHeader,
  LoadingState,
  MetricCard,
  RouteTimeline,
  Section,
  Tag,
  buildChecklist,
  buildShortReason,
  fetchJson,
  formatNumber,
  getActivityType,
  getFitLabel,
  getStopId,
  getTimeRange,
  postJson,
} from "../components/camp/CampUI";
import KakaoRouteMap from "../components/map/KakaoRouteMap";

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];
const SAVED_STOPS_KEY = "campaign-route-saved-stops";

function getDayLabel(dateValue) {
  const parsed = new Date(`${dateValue}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return "요일 확인";
  }
  return WEEKDAYS[parsed.getDay()];
}

function toggleArrayValue(values, value) {
  if (values.includes(value)) {
    return values.filter((item) => item !== value);
  }
  return [...values, value];
}

function normalizeRequest(form) {
  return {
    ...form,
    num_visits: Number(form.num_visits) || 5,
    districts: form.districts || [],
    preferred_place_types: form.preferred_place_types || [],
    avoid_duplicates: Boolean(form.avoid_duplicates),
  };
}

function firstValue(...values) {
  return values.find((value) => value !== undefined && value !== null && value !== "") ?? "";
}

function toNumberOrNull(value) {
  if (value === undefined || value === null || value === "") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function normalizeTags(value) {
  if (Array.isArray(value)) {
    return value.filter(Boolean).map(String);
  }
  if (typeof value === "string") {
    return value.split(/[;,]/).map((item) => item.trim()).filter(Boolean);
  }
  return [];
}

function extractCoordinates(item = {}) {
  const sources = [
    [item.lat, item.lng],
    [item.latitude, item.longitude],
    [item.map_lat, item.map_lng],
    [item.y, item.x],
    [item.coord_y, item.coord_x],
    [item.map_position?.lat, item.map_position?.lng],
    [item.coordinates?.lat, item.coordinates?.lng],
    [item.position?.lat, item.position?.lng],
  ];

  for (const [latValue, lngValue] of sources) {
    const lat = toNumberOrNull(latValue);
    const lng = toNumberOrNull(lngValue);
    if (lat !== null && lng !== null) {
      return { lat, lng };
    }
  }

  return { lat: null, lng: null };
}

function getRouteItems(payload = {}) {
  const candidates = [
    payload.timeline,
    payload.route,
    payload.stops,
    payload.recommendations,
    payload.items,
    payload.data?.timeline,
    payload.data?.route,
    payload.data?.stops,
    payload.data?.items,
  ];
  return candidates.find(Array.isArray) || [];
}

function normalizeRouteStop(item = {}, index = 0) {
  const nestedPlace = item.place || item.recommendation || item.candidate || {};
  const order = Number(firstValue(item.order, item.sequence, item.rank, index + 1)) || index + 1;
  const coords = extractCoordinates(item);
  const score = toNumberOrNull(firstValue(item.score, item.final_score, item.suitability_score, item.final_variant_score, nestedPlace.score));
  const reason = firstValue(
    item.reason,
    item.recommendation_reason,
    item.gold_label_reason,
    item.sequence_reason,
    Array.isArray(nestedPlace.reason) ? nestedPlace.reason.join(" / ") : nestedPlace.reason
  );
  const startTime = firstValue(item.start_time, item.time, item.visit_time);
  const stop = {
    ...item,
    id: String(firstValue(item.id, item.stop_id, item.query_id, `stop-${order}`)),
    order,
    sequence: order,
    place_name: firstValue(item.place_name, item.name, item.title, item.recommended_place_name, nestedPlace.name, "장소 확인"),
    district: firstValue(item.district, item.gu, item.region, item.recommended_district, nestedPlace.district, "자치구 확인"),
    district_normalized: firstValue(item.district_normalized, item.recommended_district_normalized, nestedPlace.district_normalized),
    district_match: firstValue(item.district_match, nestedPlace.district_match, true),
    place_type: firstValue(item.place_type, item.type, item.category, item.recommended_place_type, nestedPlace.place_type, nestedPlace.type, "장소 유형"),
    start_time: startTime,
    end_time: firstValue(item.end_time),
    time: startTime,
    address: firstValue(item.address, item.road_address, nestedPlace.address, "주소 확인 필요"),
    lat: coords.lat,
    lng: coords.lng,
    score,
    reason,
    tags: normalizeTags(firstValue(item.tags, item.context_tags)),
  };

  return {
    ...stop,
    fit_label: getFitLabel(stop.score),
    sequence_reason: firstValue(item.sequence_reason, reason),
    recommendation_reason: firstValue(item.recommendation_reason, reason),
    map_position: item.map_position || (coords.lat !== null && coords.lng !== null ? { lat: coords.lat, lng: coords.lng } : undefined),
  };
}

function buildRouteStops(timeline = []) {
  return timeline.map(normalizeRouteStop).sort((a, b) => a.order - b.order);
}

function normalizeRoutePayload(payload = {}, request = {}, previousRoute = null) {
  const timeline = buildRouteStops(getRouteItems(payload));
  if (!timeline.length) {
    return null;
  }

  const placeTypeDiversity = new Set(timeline.map((item) => item.place_type).filter(Boolean)).size;
  const summary = {
    ...(previousRoute?.summary || {}),
    ...(payload.summary || {}),
    date: firstValue(payload.summary?.date, request.date, previousRoute?.summary?.date),
    start_location: firstValue(payload.summary?.start_location, request.start_location, previousRoute?.summary?.start_location),
    target_voter_group: firstValue(payload.summary?.target_voter_group, request.target_voter_group, payload.target_age_group, previousRoute?.summary?.target_voter_group),
    campaign_goal: firstValue(payload.summary?.campaign_goal, request.campaign_goal, previousRoute?.summary?.campaign_goal),
    num_visits: timeline.length,
    place_type_diversity: Number(payload.summary?.place_type_diversity) || placeTypeDiversity,
  };

  return {
    ...payload,
    request: {
      ...(previousRoute?.request || {}),
      ...(payload.request || {}),
      ...request,
    },
    summary,
    timeline,
    insights: Array.isArray(payload.insights) ? payload.insights : previousRoute?.insights || [],
  };
}

function getCoordinateCount(stops = []) {
  return stops.filter((stop) => Number.isFinite(Number(stop.lat)) && Number.isFinite(Number(stop.lng))).length;
}

function debugRoute(message, details = {}) {
  if (process.env.NODE_ENV !== "production") {
    console.debug(`[RouteRecommendation] ${message}`, details);
  }
}

function warnRoute(message, details = {}) {
  console.warn(`[RouteRecommendation] ${message}`, details);
}

function buildShareText(route, selectedItem) {
  const summary = route?.summary || {};
  const timeline = route?.timeline || [];
  const lines = timeline.map((item) => `${item.time} ${item.place_name} (${item.district} · ${item.place_type})`);
  return [
    `[선거비서 AI] ${summary.date || "추천 일정"} 하루 유세 동선`,
    `출발: ${summary.start_location || "확인 필요"}`,
    `선택 일정: ${selectedItem?.time || ""} ${selectedItem?.place_name || ""}`.trim(),
    ...lines,
  ].filter(Boolean).join("\n");
}

function buildSwapOptions(item) {
  const district = item?.district || "성동구";
  const placeType = item?.place_type || "교통거점";
  const base = [
    { place_name: "왕십리역 광장", district: "성동구", place_type: "교통거점", address: "서울 성동구 왕십리광장로", reason: "출퇴근 유동 인구가 많아 짧은 인사에 적합합니다." },
    { place_name: "성동구청 앞 광장", district: "성동구", place_type: "정책현장", address: "서울 성동구 고산자로 270", reason: "공공 민원과 생활 이슈를 듣기 좋은 지점입니다." },
    { place_name: "서울숲 입구", district: "성동구", place_type: "공원", address: "서울 성동구 뚝섬로 273", reason: "생활권 주민과 가족 단위 유권자 접점이 있습니다." },
    { place_name: "남대문시장 입구", district: "중구", place_type: "전통시장", address: "서울 중구 남대문시장4길", reason: "상인과 생활 유권자를 만나는 상권 동선입니다." },
    { place_name: "약수노인복지관", district: "중구", place_type: "복지시설", address: "서울 중구 다산로", reason: "복지 메시지를 차분히 확인하기 좋은 장소입니다." },
  ];

  const sameDistrict = base.filter((candidate) =>
    candidate.place_name !== item?.place_name &&
    candidate.district === district
  );
  const sameType = sameDistrict.filter((candidate) => candidate.place_type === placeType);
  return [...sameType, ...sameDistrict].slice(0, 4);
}

function RouteForm({ form, options, onChange, onToggleArray, onSubmit, isSubmitting, isDirty, lastUpdated }) {
  const districts = options?.districts || [];
  const targetGroups = options?.target_voter_groups || [];
  const campaignGoals = options?.campaign_goals || [];
  const placeTypes = options?.place_types || [];
  const selectedDistricts = form.districts || [];
  const selectedPlaceTypes = form.preferred_place_types || [];

  return (
    <Card className="routeFormCard">
      <div className="cardHeaderLine">
        <div>
          <Tag tone="amber">동선 조건</Tag>
          <h2>하루 유세 조건</h2>
        </div>
        <Tag tone="blue">{getDayLabel(form.date)}요일</Tag>
      </div>
      <form onSubmit={onSubmit} className="routeForm">
        <details className="routeFormSection" open>
          <summary>기본 일정</summary>
          <div className="formGrid two">
            <label>
              <span>날짜</span>
              <input type="date" value={form.date} onChange={(event) => onChange("date", event.target.value)} required />
            </label>
            <label>
              <span>방문 지점</span>
              <select value={form.num_visits} onChange={(event) => onChange("num_visits", Number(event.target.value))} aria-label="하루 방문 개수">
                {[4, 5, 6, 7, 8].map((value) => (
                  <option key={value} value={value}>{value}곳</option>
                ))}
              </select>
            </label>
          </div>
          <div className="formGrid two">
            <label>
              <span>시작 시간</span>
              <input type="time" value={form.start_time} onChange={(event) => onChange("start_time", event.target.value)} required />
            </label>
            <label>
              <span>종료 시간</span>
              <input type="time" value={form.end_time} onChange={(event) => onChange("end_time", event.target.value)} required />
            </label>
          </div>
          <label>
            <span>출발지</span>
            <input
              type="text"
              value={form.start_location}
              onChange={(event) => onChange("start_location", event.target.value)}
              placeholder="예: 성동구청, 왕십리역, 서울시청"
              required
            />
          </label>
        </details>

        <details className="routeFormSection" open>
          <summary>방문 지역</summary>
          <fieldset>
            <legend>희망 자치구</legend>
            <div className="chipSelectGrid">
              {districts.map((district) => (
                <button
                  key={district}
                  type="button"
                  className={selectedDistricts.includes(district) ? "selected" : ""}
                  onClick={() => onToggleArray("districts", district)}
                >
                  {district}
                </button>
              ))}
            </div>
          </fieldset>
        </details>

        <details className="routeFormSection" open>
          <summary>타깃과 목적</summary>
          <div className="formGrid two">
            <label>
              <span>타깃</span>
              <select value={form.target_voter_group} onChange={(event) => onChange("target_voter_group", event.target.value)}>
                {targetGroups.map((group) => (
                  <option key={group} value={group}>{group}</option>
                ))}
              </select>
            </label>
            <label>
              <span>목적</span>
              <select value={form.campaign_goal} onChange={(event) => onChange("campaign_goal", event.target.value)}>
                {campaignGoals.map((goal) => (
                  <option key={goal} value={goal}>{goal}</option>
                ))}
              </select>
            </label>
          </div>
          <fieldset>
            <legend>선호 장소</legend>
            <div className="chipSelectGrid">
              {placeTypes.map((placeType) => (
                <button
                  key={placeType}
                  type="button"
                  className={selectedPlaceTypes.includes(placeType) ? "selected" : ""}
                  onClick={() => onToggleArray("preferred_place_types", placeType)}
                >
                  {placeType}
                </button>
              ))}
            </div>
          </fieldset>
        </details>

        <details className="routeFormSection">
          <summary>고급 설정</summary>
          <label className="toggleRow">
            <input type="checkbox" checked={form.avoid_duplicates} onChange={(event) => onChange("avoid_duplicates", event.target.checked)} />
            <span>
              <strong>최근 방문 장소 중복 감점</strong>
              <small>반복 방문 우선순위를 낮춰 새 접점을 찾습니다.</small>
            </span>
          </label>
        </details>

        <div className="stickySubmitBox">
          <div>
            {isDirty ? <Tag tone="amber">조건 변경됨</Tag> : <Tag tone="green">조건 반영됨</Tag>}
            {lastUpdated ? <small>마지막 업데이트: {lastUpdated}</small> : null}
          </div>
          <button type="submit" className="wideActionButton" disabled={isSubmitting}>
            {isSubmitting ? "동선 생성 중..." : isDirty ? "조건 반영하고 추천" : "동선 추천받기"}
          </button>
        </div>
      </form>
    </Card>
  );
}

function RouteActionPanel({ isSaved, onSave, onShare, onRecommend, onSwap, isSubmitting }) {
  return (
    <div className="routeActionPanel">
      <button type="button" onClick={onSave}>{isSaved ? "저장됨" : "일정 저장"}</button>
      <button type="button" onClick={onShare}>공유</button>
      <button type="button" onClick={onRecommend} disabled={isSubmitting}>{isSubmitting ? "생성 중" : "다시 추천"}</button>
      <button type="button" onClick={onSwap}>장소 교체</button>
    </div>
  );
}

function RouteSummary({ route }) {
  const summary = route?.summary || {};
  const timeline = route?.timeline || [];
  const districts = [...new Set(timeline.map((item) => item.district).filter(Boolean))];
  const placeTypes = [...new Set(timeline.map((item) => item.place_type).filter(Boolean))];

  return (
    <section className="metricGrid routeSummaryGrid" aria-label="동선 추천 요약">
      <MetricCard label="방문 지점" value={formatNumber(summary.num_visits || timeline.length)} caption="추천된 하루 일정" tone="amber" />
      <MetricCard label="운영 시간" value={summary.estimated_total_time || "확인 필요"} caption={`${summary.date || ""} ${summary.day_of_week || ""}`.trim()} />
      <MetricCard label="주요 타깃" value={summary.target_voter_group || "확인 필요"} caption={summary.campaign_goal || "캠페인 목적"} tone="blue" />
      <MetricCard label="장소 유형" value={formatNumber(summary.place_type_diversity || placeTypes.length)} caption={districts.join(", ") || "자치구 확인"} tone="green" />
    </section>
  );
}

function RouteWarnings({ route }) {
  const warnings = [...new Set(route?.debug?.warnings || [])].filter(Boolean).slice(0, 3);
  if (!warnings.length) {
    return null;
  }

  return (
    <div className="routeWarningList" role="status" aria-label="동선 추천 보정 안내">
      {warnings.map((warning) => (
        <span key={warning}>{warning}</span>
      ))}
    </div>
  );
}

function SwapPlaceModal({ item, options, onClose, onSwap }) {
  if (!item) {
    return null;
  }

  return (
    <div className="modalBackdrop" role="presentation" onMouseDown={onClose}>
      <section className="swapModal" role="dialog" aria-modal="true" aria-label="장소 교체" onMouseDown={(event) => event.stopPropagation()}>
        <div className="cardHeaderLine">
          <div>
            <Tag tone="amber">장소 교체</Tag>
            <h2>{item.time} 일정 대체 후보</h2>
          </div>
          <button type="button" className="iconTextButton" onClick={onClose}>닫기</button>
        </div>
        <p>{item.district} · {item.place_type} 조건에 가까운 후보입니다.</p>
        <div className="swapOptionList">
          {options.map((option) => (
            <article key={option.place_name}>
              <div>
                <strong>{option.place_name}</strong>
                <span>{option.district} · {option.place_type}</span>
                <p>{option.reason}</p>
              </div>
              <button type="button" onClick={() => onSwap(option)}>이 장소로 교체</button>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

export default function RoutePlannerPage() {
  const [options, setOptions] = useState(null);
  const [form, setForm] = useState(null);
  const [route, setRoute] = useState(null);
  const [selectedStopId, setSelectedStopId] = useState("stop-1");
  const [savedStopIds, setSavedStopIds] = useState([]);
  const [errorMessage, setErrorMessage] = useState("");
  const [toastMessage, setToastMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [lastUpdated, setLastUpdated] = useState("");
  const [isSwapOpen, setIsSwapOpen] = useState(false);
  const timelineRefs = useRef({});
  const previousDistrictsKeyRef = useRef(null);

  const routeStops = useMemo(() => buildRouteStops(route?.timeline || []), [route]);
  const districtsKey = useMemo(() => JSON.stringify(form?.districts || []), [form?.districts]);
  const selectedItem = useMemo(
    () => routeStops.find((item) => item.id === selectedStopId) || routeStops[0],
    [routeStops, selectedStopId]
  );
  const swapOptions = useMemo(() => buildSwapOptions(selectedItem), [selectedItem]);

  const showToast = useCallback((message) => {
    setToastMessage(message);
    window.setTimeout(() => setToastMessage(""), 2200);
  }, []);

  const handleSelectStop = useCallback((stopId, shouldScroll = true) => {
    setSelectedStopId(stopId);
    if (shouldScroll) {
      window.setTimeout(() => {
        timelineRefs.current[stopId]?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 80);
    }
  }, []);

  const loadInitialData = useCallback(async () => {
    try {
      setIsLoading(true);
      setErrorMessage("");
      const [optionsPayload, samplePayload] = await Promise.all([
        fetchJson("/route/options"),
        fetchJson("/route/sample"),
      ]);
      const normalizedSample = normalizeRoutePayload(samplePayload, samplePayload?.request || optionsPayload.default_request || {});
      if (!normalizedSample) {
        throw new Error("초기 동선 데이터에 방문 지점이 없습니다.");
      }
      setOptions(optionsPayload);
      setForm(optionsPayload.default_request || normalizedSample.request || {});
      setRoute(normalizedSample);
      setSelectedStopId(normalizedSample.timeline[0]?.id || "stop-1");
      setLastUpdated("방금 전");
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  useEffect(() => {
    if (!form) {
      return;
    }
    if (previousDistrictsKeyRef.current === null) {
      previousDistrictsKeyRef.current = districtsKey;
      return;
    }
    if (previousDistrictsKeyRef.current !== districtsKey) {
      previousDistrictsKeyRef.current = districtsKey;
      setRoute(null);
      setSelectedStopId("stop-1");
      setIsSwapOpen(false);
      setLastUpdated("");
    }
  }, [districtsKey, form]);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(SAVED_STOPS_KEY);
      setSavedStopIds(raw ? JSON.parse(raw) : []);
    } catch (error) {
      setSavedStopIds([]);
    }
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(SAVED_STOPS_KEY, JSON.stringify(savedStopIds));
    } catch (error) {
      // localStorage is optional for the demo state.
    }
  }, [savedStopIds]);

  const handleChange = useCallback((key, value) => {
    setForm((current) => ({ ...current, [key]: value }));
    setIsDirty(true);
  }, []);

  const handleToggleArray = useCallback((key, value) => {
    setForm((current) => ({
      ...current,
      [key]: toggleArrayValue(current?.[key] || [], value),
    }));
    setIsDirty(true);
  }, []);

  const runRecommendation = useCallback(async () => {
    if (!form) {
      return;
    }

    const requestPayload = normalizeRequest(form);
    console.log("[Route Recommend Request]", requestPayload);
    try {
      setIsSubmitting(true);
      const payload = await postJson("/route/recommend", requestPayload);
      if (typeof window !== "undefined") {
        window.__lastRouteDebug = payload.debug || null;
      }
      console.log("[Route Recommend Response Debug]", payload.debug || payload);
      debugRoute("route response received", {
        endpoint: "/route/recommend",
        responseKeys: Object.keys(payload || {}),
        rawItemCount: getRouteItems(payload).length,
      });
      const normalizedPayload = normalizeRoutePayload(payload, requestPayload, route);
      if (!normalizedPayload) {
        throw new Error("동선 API 응답에 방문 지점이 없습니다.");
      }
      setRoute(normalizedPayload);
      if (typeof window !== "undefined") {
        window.__lastNormalizedRouteDebug = normalizedPayload.debug || null;
      }
      setSelectedStopId(normalizedPayload.timeline[0]?.id || "stop-1");
      setIsDirty(false);
      setLastUpdated("방금 전");
      debugRoute("route state normalized", {
        normalizedStopsLength: normalizedPayload.timeline.length,
        markerStopsLength: getCoordinateCount(normalizedPayload.timeline),
        selectedStopId: normalizedPayload.timeline[0]?.id,
      });
      const districts = (form.districts || []).slice(0, 2).join("·") || normalizedPayload?.summary?.start_location_district || "서울";
      showToast(`${districts} / ${form.target_voter_group || "타깃"} 조건으로 ${normalizedPayload.timeline.length}개 일정을 추천했습니다.`);
    } catch (error) {
      warnRoute("route recommendation failed; keeping current route", {
        endpoint: "/route/recommend",
        message: error.message,
      });
    } finally {
      setIsSubmitting(false);
    }
  }, [form, route, showToast]);

  const handleSubmit = useCallback((event) => {
    event.preventDefault();
    runRecommendation();
  }, [runRecommendation]);

  const handleSave = useCallback(() => {
    if (!selectedItem) {
      return;
    }
    setSavedStopIds((current) => current.includes(selectedItem.id) ? current : [...current, selectedItem.id]);
    showToast("선택 일정을 저장했습니다.");
  }, [selectedItem, showToast]);

  const handleShare = useCallback(async () => {
    const text = buildShareText(route, selectedItem);
    try {
      await navigator.clipboard.writeText(text);
      showToast("공유용 일정 요약을 복사했습니다.");
    } catch (error) {
      showToast("공유용 일정 요약을 준비했습니다.");
    }
  }, [route, selectedItem, showToast]);

  const handleSwap = useCallback((option) => {
    if (!selectedItem) {
      return;
    }

    setRoute((current) => {
      if (!current) {
        return current;
      }

      return {
        ...current,
        timeline: (current.timeline || []).map((item, index) => {
          if (getStopId(item, index) !== selectedItem.id) {
            return item;
          }
          return {
            ...item,
            place_name: option.place_name,
            district: option.district,
            place_type: option.place_type,
            address: option.address,
            recommendation_reason: option.reason,
            sequence_reason: `${option.place_name}으로 교체했습니다. 같은 시간대에 배치 가능한 대체 후보입니다.`,
            score: Number.isFinite(Number(item.score)) ? Math.max(0, Number(item.score) - 0.03) : item.score,
          };
        }),
      };
    });
    setIsSwapOpen(false);
    showToast(`${option.place_name}으로 일정을 교체했습니다.`);
  }, [selectedItem, showToast]);

  const isSaved = selectedItem ? savedStopIds.includes(selectedItem.id) : false;

  return (
    <AppShell active="route">
      <HeroHeader
        eyebrow="AI 기반 하루 유세 동선"
        title={<>하루 유세 동선<br />만들기</>}
        description="출발지, 방문 지역, 타깃을 입력하면 시간대별 방문 순서를 추천합니다."
      />

      {errorMessage ? <ErrorState message={errorMessage} onRetry={loadInitialData} /> : null}
      {isLoading ? <LoadingState title="동선 추천 데이터를 준비하고 있어요" /> : null}

      {!isLoading && !errorMessage && form ? (
        <>
          <div className="routeWorkspace">
            <aside className="routeControlPane">
              <RouteForm
                form={form}
                options={options || {}}
                onChange={handleChange}
                onToggleArray={handleToggleArray}
                onSubmit={handleSubmit}
                isSubmitting={isSubmitting}
                isDirty={isDirty}
                lastUpdated={lastUpdated}
              />
            </aside>

            <section className="routeResultPane">
              <RouteSummary route={route} />
              <RouteWarnings route={route} />
              <div className="routeOutputGrid">
                <KakaoRouteMap
                  stops={routeStops}
                  selectedStopId={selectedStopId}
                  onSelectStop={(stopId) => handleSelectStop(stopId, true)}
                  startLabel={route?.summary?.start_location || form.start_location}
                />
                <Card className="selectedRouteCard">
                  <div className="cardHeaderLine">
                    <Tag tone="amber">현재 일정</Tag>
                    {isSaved ? <Tag tone="blue">저장됨</Tag> : null}
                  </div>
                  {selectedItem ? (
                    <>
                      <h2>{selectedItem.place_name}</h2>
                      <p>{getTimeRange(selectedItem.time)} · {selectedItem.district} · {selectedItem.place_type}</p>
                      <span className="selectedScore">{getFitLabel(selectedItem.score)}</span>
                      <div className="selectedMetaList">
                        <span>{getActivityType(selectedItem)}</span>
                        <span>{buildChecklist(selectedItem).join(" / ")}</span>
                      </div>
                      <p>{buildShortReason(selectedItem)}</p>
                      <RouteActionPanel
                        isSaved={isSaved}
                        onSave={handleSave}
                        onShare={handleShare}
                        onRecommend={runRecommendation}
                        onSwap={() => setIsSwapOpen(true)}
                        isSubmitting={isSubmitting}
                      />
                    </>
                  ) : (
                    <EmptyState title="선택된 일정이 없습니다" />
                  )}
                </Card>
              </div>

              <Section
                eyebrow="Timeline"
                title="추천 타임라인"
                description="몇 시에 어디를 갈지 먼저 확인합니다."
              >
                <RouteTimeline
                  items={routeStops}
                  selectedStopId={selectedStopId}
                  onSelect={(stopId) => handleSelectStop(stopId, false)}
                  itemRefs={timelineRefs}
                  savedStopIds={savedStopIds}
                  showScoreDetails={false}
                />
              </Section>
            </section>
          </div>

          <div className="mobileActionBar" aria-label="동선 추천 빠른 액션">
            <button type="button" onClick={handleSave}>{isSaved ? "저장됨" : "저장"}</button>
            <button type="button" onClick={handleShare}>공유</button>
            <button type="button" onClick={runRecommendation} disabled={isSubmitting}>다시 추천</button>
            <button type="button" onClick={() => setIsSwapOpen(true)}>더보기</button>
          </div>
          {isSwapOpen ? (
            <SwapPlaceModal
              item={selectedItem}
              options={swapOptions}
              onClose={() => setIsSwapOpen(false)}
              onSwap={handleSwap}
            />
          ) : null}
          {toastMessage ? <div className="toastMessage" role="status">{toastMessage}</div> : null}
        </>
      ) : null}
    </AppShell>
  );
}
