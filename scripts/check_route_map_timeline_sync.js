const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(__dirname, "..");
const routePagePath = path.join(repoRoot, "frontend", "app", "route", "page.js");
const coordinateModulePath = path.join(repoRoot, "frontend", "app", "components", "camp", "routeCoordinateEnrichment.js");
const kakaoMapPath = path.join(repoRoot, "frontend", "app", "components", "map", "KakaoRouteMap.js");

const fallbackPattern = /fallback|district_fallback_seed|synthetic_district_fallback|후보 부족|안전 fallback/i;
const allowedStatuses = new Set(["original", "merged_static", "cached", "geocoded"]);
const allowedSources = new Set(["original", "static", "kakao_address_search", "kakao_keyword_search", "cache"]);

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function toNumberOrNull(value) {
  if (value === undefined || value === null || value === "") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function hasValidCoordinates(item) {
  const lat = toNumberOrNull(item.lat);
  const lng = toNumberOrNull(item.lng);
  return lat !== null && lng !== null && lat >= 37 && lat <= 38 && lng >= 126 && lng <= 128;
}

function isFallbackCandidate(item) {
  return Boolean(item.is_fallback) ||
    fallbackPattern.test(item.source || "") ||
    fallbackPattern.test(item.candidate_source || "") ||
    fallbackPattern.test(item.coordinate_source || "");
}

function getCoordinateStatus(item) {
  if (!hasValidCoordinates(item)) {
    return item.coordinate_status || "not_found";
  }
  return item.coordinate_status || "original";
}

function getCoordinateSource(item) {
  if (!hasValidCoordinates(item)) {
    return item.coordinate_source || "missing";
  }
  return item.coordinate_source || "original";
}

function isMarkerEligible(item) {
  return Boolean(
    item.route_item_id &&
      item.place_name &&
      item.district_normalized &&
      hasValidCoordinates(item) &&
      allowedStatuses.has(getCoordinateStatus(item)) &&
      allowedSources.has(getCoordinateSource(item)) &&
      !isFallbackCandidate(item) &&
      getCoordinateStatus(item) !== "district_mismatch_geocode_rejected"
  );
}

function displayName(item) {
  const compact = String(item.place_name || "").replace(/\s+/g, "");
  const displayMap = {
    강남: "강남역 일대",
    성수: "성수역 일대",
    홍대: "홍대입구역 일대",
    신촌: "신촌역 일대",
    왕십리: "왕십리역 광장",
    청량리: "청량리역 일대",
    여의도: "여의도역·여의도공원 일대",
    잠실: "잠실역 일대",
    건대: "건대입구역 일대",
    사당: "사당역 일대",
    노량진: "노량진역 일대",
  };
  return item.display_place_name || displayMap[compact] || item.place_name || `${item.district_normalized || item.district} 주요 유세 지점`;
}

function normalizeTimeline(items) {
  return items.map((item, index) => {
    const district = item.district_normalized || item.district || "자치구 확인";
    const placeName = item.place_name || item.name || item.title || `${district} 주요 유세 지점`;
    const routeItemId = item.route_item_id || item.id || `${index + 1}-${district}-${placeName}`;
    const lat = toNumberOrNull(item.lat ?? item.latitude ?? item.y);
    const lng = toNumberOrNull(item.lng ?? item.longitude ?? item.x);
    const normalized = {
      ...item,
      route_item_id: routeItemId,
      id: routeItemId,
      order: index + 1,
      sequence: index + 1,
      place_name: placeName,
      raw_place_name: item.raw_place_name || placeName,
      district,
      district_normalized: district,
      lat,
      lng,
      source: item.source || "backend_api",
      candidate_source: item.candidate_source || item.source || "backend_api",
      coordinate_status: item.coordinate_status || (hasValidCoordinates({ lat, lng }) ? "original" : "not_found"),
      coordinate_source: item.coordinate_source || (hasValidCoordinates({ lat, lng }) ? "original" : "missing"),
    };
    normalized.display_place_name = displayName(normalized);
    normalized.has_coordinates = hasValidCoordinates(normalized);
    normalized.is_fallback = isFallbackCandidate(normalized);
    return normalized;
  });
}

function buildMarkers(timeline) {
  return timeline
    .map((item) => ({
      route_item_id: item.route_item_id,
      order: item.order,
      sequence: item.sequence,
      place_name: item.display_place_name || item.place_name,
      raw_place_name: item.raw_place_name || item.place_name,
      district_normalized: item.district_normalized,
      lat: item.lat,
      lng: item.lng,
      source: item.source,
      candidate_source: item.candidate_source,
      coordinate_status: item.coordinate_status,
      coordinate_source: item.coordinate_source,
      is_fallback: item.is_fallback,
    }))
    .filter(isMarkerEligible);
}

function runCase(testCase) {
  const timeline = normalizeTimeline(testCase.items);
  const markers = buildMarkers(timeline);
  const noCoordinateItems = timeline.filter((item) => !isMarkerEligible(item));

  assert(timeline.length === testCase.items.length, `${testCase.name}: timeline item was dropped`);

  markers.forEach((marker) => {
    const item = timeline.find((candidate) => candidate.route_item_id === marker.route_item_id);
    assert(item, `${testCase.name}: marker ${marker.order} has no timeline item`);
    assert(item.order === marker.order, `${testCase.name}: marker order ${marker.order} does not match timeline order ${item.order}`);
    assert(item.district_normalized === marker.district_normalized, `${testCase.name}: district mismatch at marker ${marker.order}`);
    assert(testCase.districts.includes(marker.district_normalized), `${testCase.name}: marker district ${marker.district_normalized} is outside selected districts`);
  });

  timeline.forEach((item) => {
    assert(testCase.districts.includes(item.district_normalized), `${testCase.name}: timeline district ${item.district_normalized} is outside selected districts`);
    if (!isMarkerEligible(item)) {
      assert(!markers.some((marker) => marker.route_item_id === item.route_item_id), `${testCase.name}: non-eligible item ${item.route_item_id} rendered as marker`);
    }
  });

  const markerOrders = markers.map((marker) => marker.order);
  assert(
    markerOrders.every((order) => timeline[order - 1]?.order === order),
    `${testCase.name}: marker numbering does not preserve full recommendation rank`
  );

  return {
    name: testCase.name,
    result_count: timeline.length,
    marker_count: markers.length,
    no_coord_count: noCoordinateItems.length,
    marker_orders: markerOrders,
    timeline_orders: timeline.map((item) => item.order),
    status: "PASS",
  };
}

function checkSourceInvariants() {
  const routePage = fs.readFileSync(routePagePath, "utf8");
  const coordinateModule = fs.readFileSync(coordinateModulePath, "utf8");
  const kakaoMap = fs.readFileSync(kakaoMapPath, "utf8");

  assert(routePage.includes("const routeTimeline = useMemo(() => route?.timeline || [], [route])"), "routeTimeline is not the route page source of truth");
  assert(routePage.includes("const mapMarkers = useMemo(() => buildRouteMarkers(routeTimeline), [routeTimeline])"), "mapMarkers are not derived from routeTimeline");
  assert(routePage.includes("stops={mapMarkers}"), "KakaoRouteMap is not fed by mapMarkers");
  assert(routePage.includes("<CoordinateQualityPanel"), "route page does not show coordinate marker/no-coordinate summary");
  assert(coordinateModule.includes("export function isMarkerEligible"), "shared marker eligibility function is missing");
  assert(coordinateModule.includes("fallback_coordinate_rejected"), "fallback coordinates are not explicitly rejected");
  assert(coordinateModule.includes("district_mismatch_geocode_rejected"), "district mismatch geocode rejection status is missing");
  assert(!/FALLBACK_COORDS|DISTRICT_CENTER_COORDS|place_fallback|district_fallback|seoul_fallback/.test(kakaoMap), "KakaoRouteMap still contains fallback coordinate rendering");
}

const cases = [
  {
    name: "강남구 + 서초구",
    districts: ["강남구", "서초구"],
    items: [
      { place_name: "강남", district: "강남구", place_type: "교통거점", lat: null, lng: null, source: "backend_api" },
      { place_name: "선릉역 일대", district: "강남구", place_type: "교통거점", lat: 37.5045, lng: 127.049, source: "backend_api" },
      { place_name: "고속터미널역 일대", district: "서초구", place_type: "교통거점", lat: 37.5049, lng: 127.0049, source: "backend_api" },
    ],
  },
  {
    name: "성북구 + 송파구",
    districts: ["성북구", "송파구"],
    items: [
      { place_name: "성신여대입구역 일대", district: "성북구", place_type: "교통거점", lat: 37.5927, lng: 127.0165, source: "backend_api" },
      { place_name: "잠실", district: "송파구", place_type: "교통거점", lat: 37.5133, lng: 127.1002, source: "backend_api" },
      { place_name: "석촌호수 일대", district: "송파구", place_type: "공원", lat: null, lng: null, source: "backend_api" },
    ],
  },
  {
    name: "용산구 + 강남구",
    districts: ["용산구", "강남구"],
    items: [
      { place_name: "용산역 광장", district: "용산구", place_type: "교통거점", lat: 37.5298, lng: 126.9648, source: "backend_api" },
      { place_name: "강남역 일대", district: "강남구", place_type: "교통거점", lat: 37.498, lng: 127.0276, source: "backend_api" },
    ],
  },
  {
    name: "중구 + 동대문구",
    districts: ["중구", "동대문구"],
    items: [
      { place_name: "남대문시장 입구", district: "중구", place_type: "전통시장", lat: 37.5592, lng: 126.9777, source: "district_fallback_seed", explanation: "fallback seed" },
      { place_name: "약수역 일대", district: "중구", place_type: "교통거점", lat: 37.5547, lng: 127.0106, source: "backend_api" },
      { place_name: "청량리", district: "동대문구", place_type: "교통거점", lat: 37.5802, lng: 127.0469, source: "backend_api" },
    ],
  },
  {
    name: "마포구 + 영등포구",
    districts: ["마포구", "영등포구"],
    items: [
      { place_name: "홍대", district: "마포구", place_type: "교통거점", lat: 37.5572, lng: 126.9245, source: "backend_api" },
      { place_name: "여의도", district: "영등포구", place_type: "교통거점", lat: 37.5219, lng: 126.9245, source: "backend_api" },
      { place_name: "문래동 상권", district: "영등포구", place_type: "골목상권", coordinate_status: "district_mismatch_geocode_rejected", coordinate_source: "district_mismatch_rejected", lat: 37.56, lng: 127.03, source: "backend_api" },
    ],
  },
];

try {
  checkSourceInvariants();
  const results = cases.map(runCase);
  console.log(JSON.stringify({ status: "PASS", cases: results }, null, 2));
} catch (error) {
  console.error(JSON.stringify({ status: "FAIL", message: error.message }, null, 2));
  process.exitCode = 1;
}
