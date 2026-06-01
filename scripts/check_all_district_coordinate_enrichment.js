const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "..");
const staticCandidatesPath = path.join(repoRoot, "frontend", "app", "components", "camp", "staticRealRouteCandidates.js");

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

function normalizeDistrict(text) {
  const value = String(text || "").replace(/서울특별시|서울시|서울/g, "").replace(/\s+/g, "");
  return SEOUL_DISTRICTS.find((district) => value.includes(district)) || "";
}

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

function isSeoulResult(result) {
  return /서울|서울특별시|서울시/.test(`${result.address_name || ""} ${result.road_address_name || ""}`);
}

function extractDistrictFromKakaoResult(result) {
  return normalizeDistrict([
    result.address_name,
    result.road_address_name,
    result.place_name,
  ].filter(Boolean).join(" "));
}

function pickBestKakaoResult(results, expectedDistrict) {
  let districtMismatchRejected = 0;
  for (const result of results || []) {
    if (!hasValidLatLng(result.y, result.x) || !isSeoulResult(result)) {
      continue;
    }
    const resultDistrict = extractDistrictFromKakaoResult(result);
    if (resultDistrict === expectedDistrict) {
      return { picked: result, districtMismatchRejected };
    }
    if (resultDistrict && resultDistrict !== expectedDistrict) {
      districtMismatchRejected += 1;
    }
  }
  return { picked: null, districtMismatchRejected };
}

function getDifferentDistrict(district) {
  return SEOUL_DISTRICTS.find((candidate) => candidate !== district) || "중구";
}

function mockKakaoResults(item) {
  const district = item.district_normalized;
  const coord = DISTRICT_SAMPLE_COORDS[district] || { lat: 37.55, lng: 126.99 };
  return [
    {
      place_name: item.place_name,
      address_name: `서울특별시 ${getDifferentDistrict(district)} 테스트 불일치`,
      road_address_name: "",
      y: 37.55,
      x: 126.99,
    },
    {
      place_name: item.place_name,
      address_name: `서울특별시 ${district} ${item.place_name}`,
      road_address_name: `서울특별시 ${district} ${item.address || ""}`,
      y: coord.lat,
      x: coord.lng,
    },
  ];
}

function loadStaticRealRouteCandidates() {
  const source = fs.readFileSync(staticCandidatesPath, "utf8");
  const match = source.match(/export const STATIC_REAL_ROUTE_CANDIDATES\s*=\s*({[\s\S]*?});?\s*$/);
  if (!match) {
    throw new Error("Could not parse STATIC_REAL_ROUTE_CANDIDATES");
  }
  return vm.runInNewContext(`(${match[1]})`);
}

function getRoutesForDistricts(allDistricts) {
  const candidatesByDistrict = loadStaticRealRouteCandidates();
  return Object.fromEntries(allDistricts.map((district) => {
    const timeline = (candidatesByDistrict[district] || []).slice(0, 5).map((item, index) => ({
      ...item,
      order: index + 1,
      sequence: index + 1,
      route_item_id: `static-${district}-${index + 1}`,
      id: `static-${district}-${index + 1}`,
      district,
      district_normalized: district,
    }));
    return [district, { timeline }];
  }));
}

function normalizeTimeline(payload) {
  return (payload.timeline || []).map((item, index) => {
    const district = normalizeDistrict(item.district_normalized || item.district);
    const routeItemId = item.route_item_id || item.id || `route-${index + 1}-${district}-${item.place_name}`;
    const lat = item.lat ?? item.latitude ?? item.y ?? null;
    const lng = item.lng ?? item.longitude ?? item.x ?? null;
    const valid = hasValidLatLng(lat, lng);
    return {
      ...item,
      route_item_id: routeItemId,
      id: routeItemId,
      order: index + 1,
      sequence: index + 1,
      place_name: item.place_name || item.name || "장소 확인",
      district_normalized: district,
      lat: valid ? Number(lat) : null,
      lng: valid ? Number(lng) : null,
      coordinate_status: valid ? (item.coordinate_status || "original") : "not_found",
      coordinate_source: valid ? (item.coordinate_source || "original") : "missing",
    };
  });
}

function enrichTimelineWithMockKakao(timeline) {
  let districtMismatchRejectedCount = 0;
  const enriched = timeline.map((item) => {
    if (isFallback(item)) {
      return {
        ...item,
        lat: null,
        lng: null,
        coordinate_status: "not_found",
        coordinate_source: "fallback_coordinate_rejected",
      };
    }
    if (hasValidLatLng(item.lat, item.lng)) {
      return item;
    }
    const { picked, districtMismatchRejected } = pickBestKakaoResult(mockKakaoResults(item), item.district_normalized);
    districtMismatchRejectedCount += districtMismatchRejected;
    if (!picked) {
      return {
        ...item,
        lat: null,
        lng: null,
        coordinate_status: districtMismatchRejected ? "district_mismatch_geocode_rejected" : "not_found",
        coordinate_source: districtMismatchRejected ? "district_mismatch_rejected" : "kakao_search_failed",
      };
    }
    return {
      ...item,
      lat: Number(picked.y),
      lng: Number(picked.x),
      coordinate_status: "geocoded",
      coordinate_source: "kakao_keyword_search",
      kakao_place_name: picked.place_name,
      kakao_address_name: picked.address_name,
      kakao_road_address_name: picked.road_address_name,
    };
  });
  return { enriched, districtMismatchRejectedCount };
}

function canRenderMarker(item) {
  return Boolean(
    item.route_item_id &&
      item.place_name &&
      item.district_normalized &&
      hasValidLatLng(item.lat, item.lng) &&
      ALLOWED_STATUSES.has(item.coordinate_status) &&
      ALLOWED_SOURCES.has(item.coordinate_source) &&
      !isFallback(item) &&
      item.coordinate_status !== "district_mismatch_geocode_rejected"
  );
}

function count(items, predicate) {
  return items.filter(predicate).length;
}

function runDistrict(district, payload) {
  const timeline = normalizeTimeline(payload);
  const { enriched, districtMismatchRejectedCount } = enrichTimelineWithMockKakao(timeline);
  const markers = enriched.filter(canRenderMarker);
  const markerTimelineIdMismatch = markers.filter((marker) => !enriched.some((item) => item.route_item_id === marker.route_item_id && item.order === marker.order)).length;
  const actualMismatchCount = count(enriched, (item) => item.district_normalized !== district) +
    count(markers, (item) => item.district_normalized !== district) +
    markerTimelineIdMismatch;
  return {
    district,
    result_count: enriched.length,
    marker_count: markers.length,
    no_coord_count: enriched.length - markers.length,
    geocoded_count: count(enriched, (item) => item.coordinate_status === "geocoded"),
    cached_count: count(enriched, (item) => item.coordinate_status === "cached"),
    not_found_count: count(enriched, (item) => ["not_found", "address_missing", "kakao_sdk_not_loaded"].includes(item.coordinate_status)),
    district_mismatch_rejected_count: districtMismatchRejectedCount + count(enriched, (item) => item.coordinate_status === "district_mismatch_geocode_rejected"),
    actual_mismatch_count: actualMismatchCount,
    status: enriched.length > 0 && actualMismatchCount === 0 ? "PASS" : "FAIL",
  };
}

function main() {
  const payloads = getRoutesForDistricts(SEOUL_DISTRICTS);
  const rows = SEOUL_DISTRICTS.map((district) => runDistrict(district, payloads[district] || {}));
  const header = [
    "district",
    "result_count",
    "marker_count",
    "no_coord_count",
    "geocoded_count",
    "cached_count",
    "not_found_count",
    "district_mismatch_rejected_count",
    "actual_mismatch_count",
    "status",
  ];
  console.log(header.join(","));
  rows.forEach((row) => console.log(header.map((key) => row[key]).join(",")));
  const failed = rows.filter((row) => row.status !== "PASS");
  if (failed.length) {
    console.error(`FAIL: ${failed.length} districts failed coordinate enrichment validation.`);
    process.exitCode = 1;
  }
}

try {
  main();
} catch (error) {
  console.error(`FAIL: ${error.message}`);
  process.exitCode = 1;
}
