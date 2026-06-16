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
  RouteExplainabilityPanel,
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
import {
  buildNoCoordinateItemsFromTimeline,
  buildRouteMarkersFromTimeline,
  enrichRouteTimelineCoordinates,
  getCoordinateDebugSummary,
  getCoordinateStatusMessage,
  getCoordinateStatusDetail,
  getCoordinateStatusLabel,
  isMarkerEligible,
  normalizePlaceName,
  normalizeRouteStops,
} from "../components/camp/routeCoordinateEnrichment";
import KakaoRouteMap from "../components/map/KakaoRouteMap";

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];
const SAVED_STOPS_KEY = "campaign-route-saved-stops";
const CANDIDATE_PROFILES = [
  { value: "ohsehoon", label: "오세훈", note: "교통거점·정책현장 중심" },
  { value: "jungwono", label: "정원오", note: "상권·생활밀착 현장 중심" },
  { value: "general", label: "일반 후보", note: "균형형 캠페인 운영" },
];

function hasPublicApiBaseUrl() {
  const apiBaseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL || "").trim();
  if (!apiBaseUrl) {
    return false;
  }

  try {
    const hostname = new URL(apiBaseUrl).hostname.toLowerCase();
    return !["localhost", "127.0.0.1", "::1", "0.0.0.0"].includes(hostname);
  } catch (error) {
    return false;
  }
}

const HAS_PUBLIC_API_BASE_URL = hasPublicApiBaseUrl();

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
    candidate_profile: form.candidate_profile || "general",
    num_visits: Number(form.num_visits) || 5,
    districts: form.districts || [],
    preferred_place_types: form.preferred_place_types || [],
    avoid_duplicates: Boolean(form.avoid_duplicates),
  };
}

function getRouteCharacter(timeline = [], summary = {}) {
  const campaignGoal = String(summary.campaign_goal || "").toLowerCase();
  const placeTypes = timeline.map((item) => String(item.place_type || "").toLowerCase());
  if (campaignGoal.includes("출근") || campaignGoal.includes("퇴근") || placeTypes.some((type) => type.includes("교통") || type.includes("subway"))) {
    return "출퇴근 인사 중심";
  }
  if (placeTypes.some((type) => type.includes("시장") || type.includes("상권") || type.includes("market"))) {
    return "시장·상권 밀착형";
  }
  if (placeTypes.some((type) => type.includes("정책") || type.includes("복지") || type.includes("policy") || type.includes("welfare"))) {
    return "정책현장 방문형";
  }
  return "생활권 순회형";
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

const HIDDEN_FALLBACK_PHRASES = [
  "fallback",
  "district_fallback_seed",
  "synthetic fallback",
  "synthetic_district_fallback",
  "safe fallback",
  "후보 부족",
  "안전 fallback",
  "fallback 후보",
  "실시간 API",
  "연결할 수 없어",
  "저장된 추천",
  "저장된 데모",
  "정적 데모",
];

function containsHiddenFallbackText(value) {
  const text = String(value || "").toLowerCase();
  return HIDDEN_FALLBACK_PHRASES.some((phrase) => text.includes(phrase.toLowerCase()));
}

function getNaturalCampaignExplanation(item = {}) {
  const placeType = String(item.place_type || item.recommended_place_type || item.type || "").toLowerCase();

  if (placeType.includes("subway") || placeType.includes("station") || placeType.includes("교통")) {
    return "출퇴근 생활·교통 불편을 듣기 좋은 지점입니다.";
  }
  if (placeType.includes("market") || placeType.includes("시장") || placeType.includes("상권")) {
    return "지역 상권과 생활 동선을 함께 확인하기 좋은 장소입니다.";
  }
  if (placeType.includes("park") || placeType.includes("공원")) {
    return "생활 유권자와 접촉하기 좋은 현장입니다.";
  }

  return "지역 현안을 듣고 후보 메시지를 전달하기 좋은 장소입니다.";
}

function sanitizeUserExplanation(explanation, item = {}) {
  const text = String(explanation || "").trim();
  if (!text || containsHiddenFallbackText(text)) {
    return getNaturalCampaignExplanation(item);
  }
  return text;
}

function hasValidCoordinates(item = {}) {
  const lat = Number(item.lat);
  const lng = Number(item.lng);

  return (
    Number.isFinite(lat) &&
    Number.isFinite(lng) &&
    lat >= 37.0 &&
    lat <= 38.0 &&
    lng >= 126.0 &&
    lng <= 128.0
  );
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

function buildRouteItemId(item = {}, index = 0, placeName = "", district = "") {
  const stableId = firstValue(item.route_item_id, item.id, item.stop_id, item.query_id);
  if (stableId) {
    return String(stableId);
  }

  const slug = [index + 1, placeName || "unknown", district || "unknown"]
    .map((part) => String(part).trim().replace(/\s+/g, "-"))
    .join("-");
  return `route-${slug}`;
}

function normalizeRouteStop(item = {}, index = 0) {
  const nestedPlace = item.place || item.recommendation || item.candidate || {};
  const order = index + 1;
  const coords = extractCoordinates(item);
  const validCoords = hasValidCoordinates(coords) ? coords : { lat: null, lng: null };
  const score = toNumberOrNull(firstValue(item.score, item.final_score, item.suitability_score, item.final_variant_score, nestedPlace.score));
  const rawPlaceName = firstValue(item.place_name, item.name, item.title, item.recommended_place_name, nestedPlace.name, "");
  const district = firstValue(item.district, item.gu, item.region, item.recommended_district, nestedPlace.district, "자치구 확인");
  const districtNormalized = firstValue(item.district_normalized, item.recommended_district_normalized, nestedPlace.district_normalized, district);
  const displayPlaceName = normalizePlaceName({
    ...item,
    place_name: rawPlaceName,
    district,
    district_normalized: districtNormalized,
  });
  const placeName = rawPlaceName || displayPlaceName;
  const placeType = firstValue(item.place_type, item.type, item.category, item.recommended_place_type, nestedPlace.place_type, nestedPlace.type, "장소 유형");
  const source = firstValue(item.source, item.candidate_source, item.source_type, nestedPlace.source, "unknown");
  const rawReason = firstValue(
    item.explanation,
    item.reason,
    item.recommendation_reason,
    item.gold_label_reason,
    item.sequence_reason,
    Array.isArray(nestedPlace.reason) ? nestedPlace.reason.join(" / ") : nestedPlace.reason
  );
  const explanation = sanitizeUserExplanation(rawReason, { ...item, place_type: placeType });
  const startTime = firstValue(item.start_time, item.time, item.visit_time);
  const routeItemId = buildRouteItemId(item, index, placeName, districtNormalized || district);
  const stop = {
    ...item,
    id: routeItemId,
    route_item_id: routeItemId,
    order,
    sequence: order,
    place_name: placeName,
    raw_place_name: rawPlaceName || placeName,
    display_place_name: displayPlaceName,
    district,
    district_normalized: districtNormalized,
    district_match: firstValue(item.district_match, nestedPlace.district_match, true),
    place_type: placeType,
    start_time: startTime,
    end_time: firstValue(item.end_time),
    time: startTime,
    address: firstValue(item.address, item.road_address, item.location, nestedPlace.address, "주소 확인 필요"),
    lat: validCoords.lat,
    lng: validCoords.lng,
    coordinate_status: hasValidCoordinates(validCoords) ? firstValue(item.coordinate_status, "original") : firstValue(item.coordinate_status, "not_found"),
    coordinate_source: hasValidCoordinates(validCoords) ? firstValue(item.coordinate_source, "original") : firstValue(item.coordinate_source, "missing"),
    coordinate_status_label: getCoordinateStatusLabel(hasValidCoordinates(validCoords) ? firstValue(item.coordinate_status, "original") : firstValue(item.coordinate_status, "not_found")),
    coordinate_status_detail: getCoordinateStatusDetail(hasValidCoordinates(validCoords) ? firstValue(item.coordinate_status, "original") : firstValue(item.coordinate_status, "not_found")),
    kakao_place_name: item.kakao_place_name,
    kakao_address_name: item.kakao_address_name,
    kakao_road_address_name: item.kakao_road_address_name,
    score,
    source,
    candidate_source: firstValue(item.candidate_source, source),
    is_fallback: item.is_fallback === true || containsHiddenFallbackText(source),
    explanation,
    reason: explanation,
    has_coordinates: hasValidCoordinates(validCoords),
    tags: normalizeTags(firstValue(item.tags, item.context_tags)),
  };

  return {
    ...stop,
    fit_label: getFitLabel(stop.score),
    sequence_reason: sanitizeUserExplanation(firstValue(item.sequence_reason, explanation), stop),
    recommendation_reason: sanitizeUserExplanation(firstValue(item.recommendation_reason, explanation), stop),
    map_position: stop.has_coordinates ? { lat: stop.lat, lng: stop.lng } : undefined,
  };
}

function normalizeRouteTimeline(items = []) {
  return normalizeRouteStops(items.map(normalizeRouteStop));
}

function buildRouteMarkers(timeline = []) {
  return buildRouteMarkersFromTimeline(timeline);
}

function buildNoCoordinateItems(timeline = []) {
  return buildNoCoordinateItemsFromTimeline(timeline);
}

function normalizeRoutePayload(payload = {}, request = {}, previousRoute = null) {
  const timeline = normalizeRouteTimeline(getRouteItems(payload));
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

function getRouteDataMode(route = {}) {
  const source = String(route?.debug?.source || route?.source || "").toLowerCase();
  const hasFallbackRouteSource = /static|fallback|frontend_static_json/.test(source);
  const hasApiRouteSource = /api|backend|live/.test(source);
  if (!HAS_PUBLIC_API_BASE_URL) {
    return "Local Data";
  }
  if (route?.static_fallback || route?.demo_fallback || (hasFallbackRouteSource && !hasApiRouteSource)) {
    return "Local Data";
  }
  const timeline = Array.isArray(route?.timeline) ? route.timeline : [];
  const coordinateSourceCounts = route?.debug?.coordinate_enrichment?.source_counts || {};
  const coordinateSources = [
    ...Object.keys(coordinateSourceCounts),
    ...timeline.flatMap((item) => [item.coordinate_source, item.source, item.candidate_source]),
  ].filter(Boolean).map((value) => String(value).toLowerCase());
  const hasFrontendCoordinateSupport = coordinateSources.some((value) =>
    /known_seoul|merged_static|demo_fallback|fallback|frontend_static|static/.test(value)
  );
  if ((hasApiRouteSource && hasFallbackRouteSource) || hasFrontendCoordinateSupport) {
    return "Hybrid Mode";
  }
  return "Live API";
}

function getRouteDataModeTone(mode) {
  if (mode === "Live API") {
    return "green";
  }
  if (mode === "Hybrid Mode") {
    return "amber";
  }
  if (mode === "Local Data") {
    return "blue";
  }
  return "blue";
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
  const lines = timeline.map((item) => `${item.time} ${item.display_place_name || item.place_name} (${item.district} · ${item.place_type})`);
  return [
    `[선거비서 AI] ${summary.date || "추천 일정"} 하루 유세 동선`,
    `출발: ${summary.start_location || "확인 필요"}`,
    `선택 일정: ${selectedItem?.time || ""} ${selectedItem?.display_place_name || selectedItem?.place_name || ""}`.trim(),
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

const KNOWN_START_COORDINATES = {
  강남역: { lat: 37.4979, lng: 127.0276 },
  성동구청: { lat: 37.5634, lng: 127.0368 },
  왕십리역: { lat: 37.5613, lng: 127.0371 },
  서울시청: { lat: 37.5663, lng: 126.9779 },
};

function resolveStartCoordinate(startLocation = "") {
  const compact = String(startLocation || "").replace(/\s+/g, "");
  const matchedKey = Object.keys(KNOWN_START_COORDINATES).find((key) => compact.includes(key));
  return matchedKey ? KNOWN_START_COORDINATES[matchedKey] : null;
}

function getRouteStopCoordinate(stop = {}) {
  const lat = toNumberOrNull(stop.lat);
  const lng = toNumberOrNull(stop.lng);
  return hasValidCoordinates({ lat, lng }) ? { lat, lng } : null;
}

function getDistanceKm(pointA, pointB) {
  if (!pointA || !pointB) {
    return 0;
  }
  const radiusKm = 6371;
  const toRad = (value) => (Number(value) * Math.PI) / 180;
  const dLat = toRad(pointB.lat - pointA.lat);
  const dLng = toRad(pointB.lng - pointA.lng);
  const lat1 = toRad(pointA.lat);
  const lat2 = toRad(pointB.lat);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return radiusKm * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function calculateCampaignRouteMetrics(stops = [], startLocation = "") {
  const startCoordinate = resolveStartCoordinate(startLocation);
  const stopPoints = stops.map((stop) => {
    const coordinate = getRouteStopCoordinate(stop);
    return coordinate ? { type: "stop", id: stop.route_item_id || stop.id, ...coordinate } : null;
  });
  const points = [
    ...(startCoordinate ? [{ type: "start", ...startCoordinate }] : []),
    ...stopPoints,
  ].filter((point) => point && hasValidCoordinates(point));
  const missingCoordinateCount = stops.filter((stop) => !getRouteStopCoordinate(stop)).length + (stops.length && !startCoordinate ? 1 : 0);
  const totalDistanceKm = points.reduce((sum, point, index) => {
    if (index === 0) {
      return sum;
    }
    return sum + getDistanceKm(points[index - 1], point);
  }, 0);
  const estimatedMinutes = totalDistanceKm > 0
    ? Math.max(10, Math.round((totalDistanceKm / 18) * 60) + Math.max(0, stops.length - 1) * 8)
    : 0;

  return {
    totalDistanceKm,
    estimatedMinutes,
    missingCoordinateCount,
    calculatedSegmentCount: Math.max(0, points.length - 1),
  };
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
          <Tag tone="amber">동선 조건 설정</Tag>
          <h2>후보자의 하루 일정을 확정합니다</h2>
        </div>
        <Tag tone="blue">{getDayLabel(form.date)}요일</Tag>
      </div>
      <form onSubmit={onSubmit} className="routeForm">
        <details className="routeFormSection" open>
          <summary>기본 일정</summary>
          <label>
            <span>후보자 profile</span>
            <select value={form.candidate_profile || "general"} onChange={(event) => onChange("candidate_profile", event.target.value)}>
              {CANDIDATE_PROFILES.map((profile) => (
                <option key={profile.value} value={profile.value}>{profile.label} · {profile.note}</option>
              ))}
            </select>
            <small className="fieldHelper">후보자의 공개 일정 성향을 보조 feature로만 사용하고, 실제 장소명은 평가 feature에서 제외합니다.</small>
          </label>
          <div className="formGrid two">
            <label>
              <span>날짜</span>
              <input type="date" value={form.date} onChange={(event) => onChange("date", event.target.value)} required />
              <small className="fieldHelper">시연할 하루 유세 일정을 선택합니다.</small>
            </label>
            <label>
              <span>방문 지점</span>
              <select value={form.num_visits} onChange={(event) => onChange("num_visits", Number(event.target.value))} aria-label="하루 방문 개수">
                {[4, 5, 6, 7, 8].map((value) => (
                  <option key={value} value={value}>{value}곳</option>
                ))}
              </select>
              <small className="fieldHelper">지도와 타임라인에 표시할 추천 개수입니다.</small>
            </label>
          </div>
          <div className="formGrid two">
            <label>
              <span>시작 시간</span>
              <input type="time" value={form.start_time} onChange={(event) => onChange("start_time", event.target.value)} required />
              <small className="fieldHelper">출근, 점심, 오후, 퇴근 시간대에 따라 후보지가 달라집니다.</small>
            </label>
            <label>
              <span>종료 시간</span>
              <input type="time" value={form.end_time} onChange={(event) => onChange("end_time", event.target.value)} required />
              <small className="fieldHelper">하루 캠페인 운영 가능 시간을 제한합니다.</small>
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
            <small className="fieldHelper">후보자 이동 시작점을 입력하면 거리와 순서 판단에 반영됩니다.</small>
          </label>
        </details>

        <details className="routeFormSection" open>
          <summary>방문 지역</summary>
          <fieldset>
            <legend>희망 자치구</legend>
            <small className="fieldHelper">방문을 원하는 서울시 자치구를 하나 이상 선택하세요.</small>
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
              <small className="fieldHelper">청년, 직장인, 상인, 가족, 노년층 등 접촉 대상을 선택하세요.</small>
            </label>
            <label>
              <span>목적</span>
              <select value={form.campaign_goal} onChange={(event) => onChange("campaign_goal", event.target.value)}>
                {campaignGoals.map((goal) => (
                  <option key={goal} value={goal}>{goal}</option>
                ))}
              </select>
              <small className="fieldHelper">출근 인사, 시장 방문, 정책 현장 등 캠페인 목적입니다.</small>
            </label>
          </div>
          <fieldset>
            <legend>선호 장소</legend>
            <small className="fieldHelper">유세 메시지와 맞는 장소 유형을 선택하세요.</small>
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
            {isSubmitting ? "동선 생성 중..." : "동선 생성"}
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
  const routeCharacter = getRouteCharacter(timeline, summary);

  return (
    <section className="metricGrid routeSummaryGrid" aria-label="동선 추천 요약">
      <MetricCard label="방문 지점" value={formatNumber(summary.num_visits || timeline.length)} caption="추천된 하루 일정" tone="amber" />
      <MetricCard label="지도 표시" value={formatNumber(timeline.filter((item) => item.has_coordinates).length)} caption={`${timeline.length}곳 중 marker 가능`} />
      <MetricCard label="주요 타깃" value={summary.target_voter_group || "확인 필요"} caption={summary.campaign_goal || "캠페인 목적"} tone="blue" />
      <MetricCard label="동선 성격" value={routeCharacter} caption={districts.join(", ") || placeTypes.join(", ") || "자치구 확인"} tone="green" />
    </section>
  );
}

function RouteWarnings({ route }) {
  const warnings = [...new Set(route?.debug?.warnings || [])]
    .filter((warning) => warning && !containsHiddenFallbackText(warning))
    .slice(0, 3);
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

function CoordinateQualityPanel({ timeline = [], markers = [], noCoordinateItems = [], coordinateLoading = false }) {
  const invariantOk = timeline.length === markers.length + noCoordinateItems.length;
  const districtCounts = timeline.reduce((counts, item) => {
    const district = item.district_normalized || item.district || "자치구 확인";
    counts[district] = (counts[district] || 0) + 1;
    return counts;
  }, {});
  const districtEntries = Object.entries(districtCounts);
  const maxDistrict = districtEntries.reduce((best, entry) => entry[1] > (best?.[1] || 0) ? entry : best, null);
  const isSkewed = districtEntries.length >= 2 && maxDistrict?.[1] >= Math.ceil(timeline.length * 0.7);

  if (!timeline.length) {
    return (
      <Card className="routeCoordinatePanel">
        <div className="cardHeaderLine">
          <div>
            <Tag tone="amber">지도 표시 기준</Tag>
            <h2>추천 후 좌표 검증 결과가 표시됩니다</h2>
          </div>
        </div>
        <p className="helperText">검증된 실제 좌표가 있는 장소만 marker로 표시하고, 좌표가 없는 후보는 타임라인에 유지합니다.</p>
      </Card>
    );
  }

  return (
    <Card
      className="routeCoordinatePanel"
      data-route-coordinate-panel="true"
      data-route-invariant={invariantOk ? "ok" : "mismatch"}
      data-timeline-count={timeline.length}
      data-marker-count={markers.length}
      data-no-coordinate-count={noCoordinateItems.length}
    >
      <div className="cardHeaderLine">
        <div>
          <Tag tone={noCoordinateItems.length ? "amber" : "green"}>{coordinateLoading ? "좌표 확인 중" : "좌표 검증"}</Tag>
          <h2>지도 표시 현황</h2>
        </div>
        <strong>{markers.length}/{timeline.length} marker</strong>
      </div>
      <div className="coordinateMetricGrid">
        <span>전체 추천 후보 <strong>{timeline.length}</strong></span>
        <span>지도 marker <strong>{markers.length}</strong></span>
        <span>좌표 확인 필요 <strong>{noCoordinateItems.length}</strong></span>
      </div>
      <p className="helperText">
        Kakao 검색과 자치구 검증을 통과한 좌표만 지도에 표시합니다. 좌표가 없는 후보는 삭제하지 않고 아래 목록과 타임라인에서 확인할 수 있습니다.
      </p>
      {isSkewed ? (
        <p className="routeBalanceNotice">
          선택 자치구별 추천 분포가 {maxDistrict[0]}에 집중되어 있습니다. 시연에서는 자치구를 줄이거나 장소 유형을 넓혀 균형을 조정할 수 있습니다.
        </p>
      ) : null}
      {noCoordinateItems.length ? (
        <details className="coordinateIssueDetails" open>
          <summary>좌표 확인 필요 후보 {noCoordinateItems.length}개</summary>
          <ol className="coordinateIssueList">
            {noCoordinateItems.map((item) => (
              <li key={item.route_item_id || item.id}>
                <strong>{item.order}번 {item.display_place_name || item.place_name}</strong>
                <span>{item.district_normalized || item.district} · {getCoordinateStatusLabel(item.coordinate_status)}</span>
                <small>{item.address || "주소 확인 필요"}</small>
                <small>제외 사유: {item.coordinate_status_detail || getCoordinateStatusDetail(item.coordinate_status)}</small>
              </li>
            ))}
          </ol>
        </details>
      ) : null}
      <details className="coordinateIssueDetails">
        <summary>개발자용 좌표 debug</summary>
        <pre>{JSON.stringify(getCoordinateDebugSummary(timeline), null, 2)}</pre>
      </details>
    </Card>
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

function CampaignRouteBuilder({
  selectedItems = [],
  startLocation = "",
  onSelectStop,
  onMoveStop,
  onRemoveStop,
}) {
  const metrics = calculateCampaignRouteMetrics(selectedItems, startLocation);
  const duplicateCount = selectedItems.length - new Set(selectedItems.map((item) => item.route_item_id || item.id)).size;

  return (
    <Card
      className="campaignRouteBuilder"
      data-route-builder="true"
      data-selected-route-count={selectedItems.length}
      data-total-distance-km={metrics.totalDistanceKm.toFixed(2)}
    >
      <div className="cardHeaderLine">
        <div>
          <Tag tone="amber">시연 동선</Tag>
          <h2>선택 유세지로 실제 Route 만들기</h2>
        </div>
        <Tag tone={duplicateCount ? "amber" : "green"}>{selectedItems.length}/5 선택</Tag>
      </div>
      <div className="routeBuilderMetricGrid">
        <span>총 이동거리 <strong>{metrics.totalDistanceKm ? `${metrics.totalDistanceKm.toFixed(1)}km` : "계산 대기"}</strong></span>
        <span>예상 이동시간 <strong>{metrics.estimatedMinutes ? `${metrics.estimatedMinutes}분` : "계산 대기"}</strong></span>
        <span>계산 구간 <strong>{metrics.calculatedSegmentCount}</strong></span>
        <span>좌표 미확보 <strong>{Math.max(0, metrics.missingCoordinateCount)}</strong></span>
      </div>
      {selectedItems.length ? (
        <ol className="selectedCampaignRouteList">
          {selectedItems.map((item, index) => {
            const stopId = item.route_item_id || item.id;
            return (
              <li
                key={stopId}
                data-route-builder-item="true"
                data-route-item-id={stopId}
                data-route-order={index + 1}
                data-place-name={item.display_place_name || item.place_name}
              >
                <button type="button" className="routeBuilderSelect" onClick={() => onSelectStop?.(stopId)}>
                  <span>{index + 1}</span>
                  <strong>{item.display_place_name || item.place_name}</strong>
                  <small>{item.district} · {item.place_type} · {item.has_coordinates ? "거리 계산 가능" : getCoordinateStatusLabel(item.coordinate_status)}</small>
                </button>
                <div className="routeBuilderControls" aria-label={`${item.place_name} 순서 조정`}>
                  <button type="button" onClick={() => onMoveStop(stopId, -1)} disabled={index === 0}>위</button>
                  <button type="button" onClick={() => onMoveStop(stopId, 1)} disabled={index === selectedItems.length - 1}>아래</button>
                  <button type="button" onClick={() => onRemoveStop(stopId)}>제거</button>
                </div>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="helperText">추천 타임라인에서 장소를 선택한 뒤 현재 일정 카드의 “동선에 추가”를 눌러 1~5순위 유세 루트를 구성합니다.</p>
      )}
      <p className="helperText">
        같은 장소는 중복 추가하지 않으며, 제거 후 다시 추가할 수 있습니다. 거리와 시간은 검증된 좌표 구간만 기준으로 재계산합니다.
      </p>
    </Card>
  );
}

export default function RoutePlannerPage() {
  const [options, setOptions] = useState(null);
  const [form, setForm] = useState(null);
  const [route, setRoute] = useState(null);
  const [selectedStopIndex, setSelectedStopIndex] = useState(0);
  const [selectedVisitIds, setSelectedVisitIds] = useState([]);
  const [savedStopIds, setSavedStopIds] = useState([]);
  const [errorMessage, setErrorMessage] = useState("");
  const [toastMessage, setToastMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCoordinateLoading, setIsCoordinateLoading] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [lastUpdated, setLastUpdated] = useState("");
  const [isSwapOpen, setIsSwapOpen] = useState(false);
  const timelineRefs = useRef({});
  const previousDistrictsKeyRef = useRef(null);

  const routeTimeline = useMemo(() => route?.timeline || [], [route]);
  const routeDataMode = useMemo(() => getRouteDataMode(route), [route]);
  const mapMarkers = useMemo(() => buildRouteMarkers(routeTimeline), [routeTimeline]);
  const noCoordinateItems = useMemo(() => buildNoCoordinateItems(routeTimeline), [routeTimeline]);
  const districtsKey = useMemo(() => JSON.stringify(form?.districts || []), [form?.districts]);
  const selectedItem = useMemo(
    () => routeTimeline[selectedStopIndex] || routeTimeline[0] || null,
    [routeTimeline, selectedStopIndex]
  );
  const selectedStopId = selectedItem?.route_item_id || selectedItem?.id || "";
  const selectedMarker = useMemo(
    () => mapMarkers.find((marker) => marker.route_item_id === selectedItem?.route_item_id) || null,
    [mapMarkers, selectedItem?.route_item_id]
  );
  const selectedVisitSet = useMemo(() => new Set(selectedVisitIds), [selectedVisitIds]);
  const selectedCampaignRouteItems = useMemo(() => (
    selectedVisitIds
      .map((stopId) => routeTimeline.find((item) => item.route_item_id === stopId || item.id === stopId))
      .filter(Boolean)
  ), [routeTimeline, selectedVisitIds]);
  const selectedItemInCampaignRoute = selectedItem
    ? selectedVisitSet.has(selectedItem.route_item_id || selectedItem.id)
    : false;
  const selectedCanRenderMarker = selectedItem ? isMarkerEligible(selectedItem) : false;
  const coordinateStatusMessage = useMemo(
    () => getCoordinateStatusMessage({
      coordinateLoading: isCoordinateLoading,
      totalCount: routeTimeline.length,
      markerCount: mapMarkers.length,
      noCoordinateCount: noCoordinateItems.length,
    }),
    [isCoordinateLoading, mapMarkers.length, noCoordinateItems.length, routeTimeline.length]
  );
  const swapOptions = useMemo(() => buildSwapOptions(selectedItem), [selectedItem]);

  const showToast = useCallback((message) => {
    setToastMessage(message);
    window.setTimeout(() => setToastMessage(""), 2200);
  }, []);

  const handleSelectStopIndex = useCallback((index, shouldScroll = true) => {
    const safeIndex = Number.isInteger(index) && index >= 0 ? index : 0;
    const stopId = routeTimeline[safeIndex]?.route_item_id || routeTimeline[safeIndex]?.id || "";
    setSelectedStopIndex(safeIndex);
    if (shouldScroll) {
      window.setTimeout(() => {
        timelineRefs.current[stopId]?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 80);
    }
  }, [routeTimeline]);

  const handleSelectStop = useCallback((stopId, shouldScroll = true) => {
    const index = routeTimeline.findIndex((item) => item.route_item_id === stopId || item.id === stopId);
    if (index >= 0) {
      handleSelectStopIndex(index, shouldScroll);
    }
  }, [handleSelectStopIndex, routeTimeline]);

  const loadInitialData = useCallback(async () => {
    try {
      setIsLoading(true);
      setIsCoordinateLoading(false);
      setErrorMessage("");
      const [optionsPayload, samplePayload] = await Promise.all([
        fetchJson("/api/route/options"),
        fetchJson("/api/route/sample"),
      ]);
      const normalizedSample = normalizeRoutePayload(samplePayload, samplePayload?.request || optionsPayload.default_request || {});
      if (!normalizedSample) {
        throw new Error("초기 동선 데이터에 방문 지점이 없습니다.");
      }
      const initialRequest = samplePayload?.static_fallback || samplePayload?.demo_fallback
        ? (normalizedSample.request || optionsPayload.default_request || {})
        : (optionsPayload.default_request || normalizedSample.request || {});
      setOptions(optionsPayload);
      setForm({
        ...initialRequest,
        candidate_profile: initialRequest.candidate_profile || "general",
      });
      setIsCoordinateLoading(true);
      const enrichedTimeline = await enrichRouteTimelineCoordinates(normalizedSample.timeline, {
        coordinateSources: getRouteItems(samplePayload),
      });
      const enrichedSample = {
        ...normalizedSample,
        timeline: enrichedTimeline,
        debug: {
          ...(normalizedSample.debug || {}),
          data_mode: getRouteDataMode(normalizedSample),
          coordinate_enrichment: getCoordinateDebugSummary(enrichedTimeline),
        },
      };
      setRoute(enrichedSample);
      setSelectedStopIndex(0);
      setSelectedVisitIds([]);
      setLastUpdated("방금 전");
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsCoordinateLoading(false);
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
      setSelectedStopIndex(0);
      setSelectedVisitIds([]);
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

  useEffect(() => {
    if (selectedStopIndex >= routeTimeline.length && routeTimeline.length > 0) {
      setSelectedStopIndex(0);
    }
  }, [routeTimeline.length, selectedStopIndex]);

  useEffect(() => {
    const validIds = new Set(routeTimeline.map((item) => item.route_item_id || item.id));
    setSelectedVisitIds((current) => current.filter((stopId) => validIds.has(stopId)));
  }, [routeTimeline]);

  useEffect(() => {
    if (!routeTimeline.length) {
      return;
    }
    debugRoute("timeline normalized", routeTimeline.map((item) => ({
      order: item.order,
      id: item.route_item_id,
      place_name: item.place_name,
      display_place_name: item.display_place_name,
      district: item.district_normalized,
      lat: item.lat,
      lng: item.lng,
      source: item.source,
      is_fallback: item.is_fallback,
    })));
  }, [routeTimeline]);

  useEffect(() => {
    debugRoute("map markers", mapMarkers.map((marker) => ({
      order: marker.order,
      id: marker.route_item_id,
      place_name: marker.place_name,
      district: marker.district_normalized,
      lat: marker.lat,
      lng: marker.lng,
    })));
  }, [mapMarkers]);

  useEffect(() => {
    if (!routeTimeline.length) {
      return;
    }
    debugRoute("marker/timeline consistency", {
      timelineCount: routeTimeline.length,
      markerCount: mapMarkers.length,
      noCoordinateCount: noCoordinateItems.length,
      invariantOk: routeTimeline.length === mapMarkers.length + noCoordinateItems.length,
      markerOrders: mapMarkers.map((marker) => marker.order),
      timelineOrders: routeTimeline.map((item) => item.order),
      dataMode: routeDataMode,
    });
  }, [mapMarkers, noCoordinateItems.length, routeDataMode, routeTimeline]);

  useEffect(() => {
    debugRoute("selected stop", {
      selectedStopIndex,
      selectedStop: selectedItem?.display_place_name || selectedItem?.place_name,
      selectedMarker: selectedMarker?.place_name,
      sameId: Boolean(selectedItem?.route_item_id && selectedItem.route_item_id === selectedMarker?.route_item_id),
    });
  }, [selectedStopIndex, selectedItem, selectedMarker]);

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
    debugRoute("request payload", requestPayload);
    try {
      setIsSubmitting(true);
      setIsCoordinateLoading(false);
      setErrorMessage("");
      setIsSwapOpen(false);
      if (typeof window !== "undefined") {
        window.__lastRouteDebug = null;
        window.__lastNormalizedRouteDebug = null;
      }
      const payload = await postJson("/api/route", requestPayload);
      if (typeof window !== "undefined") {
        window.__lastRouteDebug = payload.debug || null;
      }
      debugRoute("response debug", payload.debug || payload);
      debugRoute("route response received", {
        endpoint: "/api/route",
        responseKeys: Object.keys(payload || {}),
        rawItemCount: getRouteItems(payload).length,
      });
      const normalizedPayload = normalizeRoutePayload(payload, requestPayload, route);
      if (!normalizedPayload) {
        throw new Error("동선 API 응답에 방문 지점이 없습니다.");
      }
      setIsCoordinateLoading(true);
      const enrichedTimeline = await enrichRouteTimelineCoordinates(normalizedPayload.timeline, {
        coordinateSources: getRouteItems(payload),
      });
      const enrichedPayload = {
        ...normalizedPayload,
        timeline: enrichedTimeline,
        debug: {
          ...(normalizedPayload.debug || {}),
          data_mode: getRouteDataMode(normalizedPayload),
          coordinate_enrichment: getCoordinateDebugSummary(enrichedTimeline),
        },
      };
      setRoute(enrichedPayload);
      setSelectedVisitIds([]);
      if (typeof window !== "undefined") {
        window.__lastNormalizedRouteDebug = enrichedPayload.debug || null;
      }
      setSelectedStopIndex(0);
      setIsDirty(false);
      setLastUpdated("방금 전");
      debugRoute("route state normalized", {
        normalizedStopsLength: enrichedPayload.timeline.length,
        markerStopsLength: getCoordinateDebugSummary(enrichedPayload.timeline).marker_count,
        selectedStopId: enrichedPayload.timeline[0]?.route_item_id,
        coordinate_enrichment: enrichedPayload.debug?.coordinate_enrichment,
      });
      const districts = (form.districts || []).slice(0, 2).join("·") || enrichedPayload?.summary?.start_location_district || "서울";
      showToast(`${districts} / ${form.target_voter_group || "타깃"} 조건으로 ${enrichedPayload.timeline.length}개 일정을 추천했습니다.`);
    } catch (error) {
      warnRoute("route recommendation failed; retained current route", {
        endpoint: "/api/route",
        message: error.message,
      });
      setErrorMessage(error.message || "동선 추천 중 오류가 발생했습니다.");
    } finally {
      setIsCoordinateLoading(false);
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
          if ((item.route_item_id || getStopId(item, index)) !== selectedItem.route_item_id) {
            return item;
          }
          const optionCoords = extractCoordinates(option);
          const safeCoords = hasValidCoordinates(optionCoords) ? optionCoords : { lat: null, lng: null };
          const explanation = sanitizeUserExplanation(option.reason, { ...item, ...option });
          const displayPlaceName = normalizePlaceName({
            ...option,
            district_normalized: option.district,
          });
          return {
            ...item,
            place_name: option.place_name,
            raw_place_name: option.place_name,
            display_place_name: displayPlaceName,
            district: option.district,
            district_normalized: option.district,
            place_type: option.place_type,
            address: option.address,
            lat: safeCoords.lat,
            lng: safeCoords.lng,
            map_position: hasValidCoordinates(safeCoords) ? { lat: safeCoords.lat, lng: safeCoords.lng } : undefined,
            has_coordinates: hasValidCoordinates(safeCoords),
            coordinate_status: hasValidCoordinates(safeCoords) ? "original" : "not_found",
            coordinate_source: hasValidCoordinates(safeCoords) ? "original" : "manual_swap_missing",
            coordinate_status_label: getCoordinateStatusLabel(hasValidCoordinates(safeCoords) ? "original" : "not_found"),
            coordinate_status_detail: getCoordinateStatusDetail(hasValidCoordinates(safeCoords) ? "original" : "not_found"),
            explanation,
            reason: explanation,
            recommendation_reason: explanation,
            sequence_reason: `${option.place_name}으로 교체했습니다. 같은 시간대에 배치 가능한 대체 후보입니다.`,
            score: Number.isFinite(Number(item.score)) ? Math.max(0, Number(item.score) - 0.03) : item.score,
          };
        }),
      };
    });
    setIsSwapOpen(false);
    showToast(`${option.place_name}으로 일정을 교체했습니다.`);
  }, [selectedItem, showToast]);

  const handleAddSelectedToCampaignRoute = useCallback(() => {
    if (!selectedItem) {
      return;
    }
    const stopId = selectedItem.route_item_id || selectedItem.id;
    setSelectedVisitIds((current) => {
      if (current.includes(stopId)) {
        return current;
      }
      return [...current, stopId];
    });
    showToast(`${selectedItem.display_place_name || selectedItem.place_name}을 시연 동선에 추가했습니다.`);
  }, [selectedItem, showToast]);

  const handleRemoveCampaignRouteStop = useCallback((stopId) => {
    setSelectedVisitIds((current) => current.filter((item) => item !== stopId));
    showToast("시연 동선에서 제거했습니다.");
  }, [showToast]);

  const handleMoveCampaignRouteStop = useCallback((stopId, direction) => {
    setSelectedVisitIds((current) => {
      const index = current.indexOf(stopId);
      const nextIndex = index + direction;
      if (index < 0 || nextIndex < 0 || nextIndex >= current.length) {
        return current;
      }
      const next = [...current];
      [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
      return next;
    });
  }, []);

  const isSaved = selectedItem ? savedStopIds.includes(selectedItem.id) : false;

  return (
    <AppShell active="route">
      <HeroHeader
        eyebrow="Route Planning Workspace"
        title="하루 유세 동선 설계"
        description="후보자의 하루 일정을 실제 캠프 실무 흐름에 맞춰 추천합니다."
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
              {route?.debug ? (
                <script
                  id="route-debug-json"
                  type="application/json"
                  dangerouslySetInnerHTML={{ __html: JSON.stringify(route.debug).replace(/</g, "\\u003c") }}
                />
              ) : null}
              <CoordinateQualityPanel
                timeline={routeTimeline}
                markers={mapMarkers}
                noCoordinateItems={noCoordinateItems}
                coordinateLoading={isCoordinateLoading}
              />
              <CampaignRouteBuilder
                selectedItems={selectedCampaignRouteItems}
                startLocation={form.start_location}
                onSelectStop={(stopId) => handleSelectStop(stopId, true)}
                onMoveStop={handleMoveCampaignRouteStop}
                onRemoveStop={handleRemoveCampaignRouteStop}
              />
              <div className="routeOutputGrid">
                <section className="routeMapPanel" aria-label="추천 동선 지도">
                  <div className="mapPanelHeader">
                    <div>
                      <Tag tone="amber">추천 동선 지도</Tag>
                      <h2>지도 marker와 방문 순서를 함께 확인합니다</h2>
                    </div>
                    <Tag tone={getRouteDataModeTone(routeDataMode)} data-route-data-mode={routeDataMode}>{routeDataMode}</Tag>
                    <div className="mapLegendCard compact">
                      <span><i className="legend-dot orange" />번호 marker = 방문 순서</span>
                      <span><i className="legend-dot muted" />좌표 확인 필요</span>
                    </div>
                  </div>
                  <KakaoRouteMap
                    stops={mapMarkers}
                    selectedStopId={selectedStopId}
                    onSelectStop={(stopId) => handleSelectStop(stopId, true)}
                    startLabel={route?.summary?.start_location || form.start_location}
                    noCoordinateCount={noCoordinateItems.length}
                    totalStopCount={routeTimeline.length}
                    coordinateLoading={isCoordinateLoading}
                    coordinateStatusMessage={coordinateStatusMessage}
                  />
                </section>
                <Card className="selectedRouteCard">
                  <div className="cardHeaderLine">
                    <Tag tone="amber">현재 일정</Tag>
                    {isSaved ? <Tag tone="blue">저장됨</Tag> : null}
                    {selectedItem && !selectedCanRenderMarker ? <Tag tone="amber">{getCoordinateStatusLabel(selectedItem.coordinate_status)}</Tag> : null}
                  </div>
                  {selectedItem ? (
                    <>
                      <h2>{selectedItem.display_place_name || selectedItem.place_name}</h2>
                      {selectedItem.raw_place_name && selectedItem.raw_place_name !== (selectedItem.display_place_name || selectedItem.place_name) ? (
                        <p className="rawPlaceName">원본 장소명: {selectedItem.raw_place_name}</p>
                      ) : null}
                      <p>{getTimeRange(selectedItem.time)} · {selectedItem.district} · {selectedItem.place_type}</p>
                      <p className="selectedAddress">{selectedItem.address || "주소 확인 필요"}</p>
                      <span className="selectedScore">{getFitLabel(selectedItem.score)}</span>
                      <div className="selectedMetaList">
                        <span>{getActivityType(selectedItem)}</span>
                        <span>{buildChecklist(selectedItem).join(" / ")}</span>
                        <span>{selectedCanRenderMarker ? "지도 marker 표시" : getCoordinateStatusDetail(selectedItem.coordinate_status)}</span>
                      </div>
                      <p>{buildShortReason(selectedItem)}</p>
                      <div className="selectedRouteActions">
                        <button
                          type="button"
                          onClick={handleAddSelectedToCampaignRoute}
                          disabled={selectedItemInCampaignRoute}
                        >
                          {selectedItemInCampaignRoute ? "동선에 포함됨" : "동선에 추가"}
                        </button>
                        <button
                          type="button"
                          onClick={() => handleRemoveCampaignRouteStop(selectedItem.route_item_id || selectedItem.id)}
                          disabled={!selectedItemInCampaignRoute}
                        >
                          동선에서 제거
                        </button>
                      </div>
                      <details className="scoreDetails selectedExplainability" open>
                        <summary>추천 이유 보기</summary>
                        <RouteExplainabilityPanel item={selectedItem} />
                      </details>
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
                description="카드, 지도 marker, 타임라인의 장소명과 순서를 같은 번호로 확인합니다."
              >
                <RouteTimeline
                  items={routeTimeline}
                  selectedStopIndex={selectedStopIndex}
                  selectedStopId={selectedStopId}
                  onSelect={(stopId, index) => handleSelectStopIndex(index, false)}
                  itemRefs={timelineRefs}
                  savedStopIds={savedStopIds}
                  showScoreDetails
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
