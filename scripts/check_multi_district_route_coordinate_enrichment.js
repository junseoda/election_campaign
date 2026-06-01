const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "..");
const staticCandidatesPath = path.join(repoRoot, "frontend", "app", "components", "camp", "staticRealRouteCandidates.js");
const COMBOS = [
  ["강남구", "서초구"],
  ["성북구", "송파구"],
  ["용산구", "강남구"],
  ["중구", "동대문구"],
  ["마포구", "영등포구"],
];
const SEOUL_DISTRICTS = [
  "종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구",
  "성북구", "강북구", "도봉구", "노원구", "은평구", "서대문구", "마포구",
  "양천구", "강서구", "구로구", "금천구", "영등포구", "동작구", "관악구",
  "서초구", "강남구", "송파구", "강동구",
];
const DISTRICT_SAMPLE_COORDS = Object.fromEntries(
  SEOUL_DISTRICTS.map((district, index) => [
    district,
    {
      lat: 37.45 + (index % 9) * 0.025,
      lng: 126.78 + Math.floor(index / 9) * 0.11,
    },
  ])
);

const ALLOWED_STATUSES = new Set(["original", "merged_static", "cached", "geocoded"]);
const ALLOWED_SOURCES = new Set(["original", "static", "kakao_address_search", "kakao_keyword_search", "cache"]);
const FALLBACK_PATTERN = /fallback|district_fallback_seed|synthetic_district_fallback/i;

function hasValidLatLng(lat, lng) {
  const y = Number(lat);
  const x = Number(lng);
  return Number.isFinite(y) && Number.isFinite(x) && y >= 37 && y <= 38 && x >= 126 && x <= 128;
}

function isFallback(item) {
  return Boolean(item.is_fallback) ||
    FALLBACK_PATTERN.test(item.source || "") ||
    FALLBACK_PATTERN.test(item.candidate_source || "") ||
    FALLBACK_PATTERN.test(item.coordinate_source || "");
}

function canRenderMarker(item) {
  return Boolean(
    item.route_item_id &&
      item.place_name &&
      item.district_normalized &&
      hasValidLatLng(item.lat, item.lng) &&
      ALLOWED_STATUSES.has(item.coordinate_status || "original") &&
      ALLOWED_SOURCES.has(item.coordinate_source || "original") &&
      !isFallback(item) &&
      item.coordinate_status !== "district_mismatch_geocode_rejected"
  );
}

function loadStaticRealRouteCandidates() {
  const source = fs.readFileSync(staticCandidatesPath, "utf8");
  const match = source.match(/export const STATIC_REAL_ROUTE_CANDIDATES\s*=\s*({[\s\S]*?});?\s*$/);
  if (!match) {
    throw new Error("Could not parse STATIC_REAL_ROUTE_CANDIDATES");
  }
  return vm.runInNewContext(`(${match[1]})`);
}

function getRouteForCombo(districts) {
  const candidatesByDistrict = loadStaticRealRouteCandidates();
  const timeline = districts.flatMap((district) =>
    (candidatesByDistrict[district] || []).slice(0, 3).map((item) => ({
      ...item,
      district,
      district_normalized: district,
    }))
  ).slice(0, 6).map((item, index) => ({
    ...item,
    order: index + 1,
    sequence: index + 1,
    route_item_id: `static-${districts.join("-")}-${index + 1}`,
    id: `static-${districts.join("-")}-${index + 1}`,
  }));
  return { timeline };
}

function normalizeTimeline(payload) {
  return (payload.timeline || []).map((item, index) => {
    const lat = item.lat ?? item.latitude ?? item.y ?? null;
    const lng = item.lng ?? item.longitude ?? item.x ?? null;
    const valid = hasValidLatLng(lat, lng);
    const routeItemId = item.route_item_id || item.id || `route-${index + 1}-${item.district_normalized || item.district}-${item.place_name}`;
    return {
      ...item,
      route_item_id: routeItemId,
      id: routeItemId,
      order: index + 1,
      sequence: index + 1,
      place_name: item.place_name || "장소 확인",
      district_normalized: item.district_normalized || item.district || "",
      lat: valid && !isFallback(item) ? Number(lat) : null,
      lng: valid && !isFallback(item) ? Number(lng) : null,
      coordinate_status: valid && !isFallback(item) ? (item.coordinate_status || "original") : "not_found",
      coordinate_source: valid && !isFallback(item) ? (item.coordinate_source || "original") : "missing",
    };
  });
}

function enrichTimelineWithMockKakao(timeline) {
  return timeline.map((item, index) => {
    if (hasValidLatLng(item.lat, item.lng)) {
      return item;
    }
    if (index % 3 === 2) {
      return {
        ...item,
        lat: null,
        lng: null,
        coordinate_status: "not_found",
        coordinate_source: "kakao_search_failed",
      };
    }
    const coord = DISTRICT_SAMPLE_COORDS[item.district_normalized] || { lat: 37.55, lng: 126.99 };
    return {
      ...item,
      lat: coord.lat,
      lng: coord.lng,
      coordinate_status: "geocoded",
      coordinate_source: "kakao_keyword_search",
      kakao_address_name: `서울특별시 ${item.district_normalized} ${item.place_name}`,
    };
  });
}

function runCombo(districts) {
  const payload = getRouteForCombo(districts);
  const timeline = enrichTimelineWithMockKakao(normalizeTimeline(payload));
  const markers = timeline.filter(canRenderMarker);
  const outsideTimeline = timeline.filter((item) => !districts.includes(item.district_normalized));
  const outsideMarkers = markers.filter((item) => !districts.includes(item.district_normalized));
  const markerTimelineMismatch = markers.filter((marker) => !timeline.some((item) => item.route_item_id === marker.route_item_id && item.order === marker.order));
  const districtDistribution = timeline.reduce((counts, item) => {
    counts[item.district_normalized] = (counts[item.district_normalized] || 0) + 1;
    return counts;
  }, {});
  const actualMismatchCount = outsideTimeline.length + outsideMarkers.length + markerTimelineMismatch.length;
  return {
    districts: districts.join("+"),
    result_count: timeline.length,
    marker_count: markers.length,
    no_coord_count: timeline.length - markers.length,
    geocoded_count: timeline.filter((item) => item.coordinate_status === "geocoded").length,
    district_distribution: JSON.stringify(districtDistribution),
    actual_mismatch_count: actualMismatchCount,
    status: timeline.length > 0 && actualMismatchCount === 0 ? "PASS" : "FAIL",
  };
}

try {
  const rows = COMBOS.map(runCombo);
  const header = ["districts", "result_count", "marker_count", "no_coord_count", "geocoded_count", "district_distribution", "actual_mismatch_count", "status"];
  console.log(header.join(","));
  rows.forEach((row) => console.log(header.map((key) => row[key]).join(",")));
  const failed = rows.filter((row) => row.status !== "PASS");
  if (failed.length) {
    console.error(`FAIL: ${failed.length} multi-district cases failed.`);
    process.exitCode = 1;
  }
} catch (error) {
  console.error(`FAIL: ${error.message}`);
  process.exitCode = 1;
}
