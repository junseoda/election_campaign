"use client";

import {
  DEMO_FALLBACK_COORDINATE_SOURCE,
  DEMO_FALLBACK_ROUTE_SOURCE,
  KNOWN_SEOUL_COORDINATE_SOURCE,
  getKnownRouteCoordinate,
} from "./demoFallbackRoute";
import { STATIC_REAL_ROUTE_CANDIDATES } from "./staticRealRouteCandidates";

export const SEOUL_DISTRICTS = [
  "종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구",
  "성북구", "강북구", "도봉구", "노원구", "은평구", "서대문구", "마포구",
  "양천구", "강서구", "구로구", "금천구", "영등포구", "동작구", "관악구",
  "서초구", "강남구", "송파구", "강동구",
];

const SEOUL_DISTRICT_ALIASES = Object.fromEntries(
  SEOUL_DISTRICTS.map((district) => [district.replace(/구$/, ""), district])
);
const KAKAO_SDK_SCRIPT_ID = "kakao-map-sdk";
const KAKAO_SDK_BASE_URL = "https://dapi.kakao.com/v2/maps/sdk.js";
const COORDINATE_CACHE_PREFIX = "route-coord";
const COORDINATE_CACHE_VERSION = "v2";
const FALLBACK_SOURCE_PATTERN = /fallback|district_fallback_seed|synthetic_district_fallback/i;
const ADDRESS_MISSING_PATTERN = /주소\s*확인\s*필요|장소\s*확인|확인\s*필요/i;

const ABSTRACT_PLACE_DISPLAY_NAMES = {
  강남: "강남역 일대",
  강남역: "강남역 일대",
  성수: "성수역 일대",
  성수역: "성수역 일대",
  홍대: "홍대입구역 일대",
  홍대입구: "홍대입구역 일대",
  신촌: "신촌역 일대",
  신촌역: "신촌역 일대",
  왕십리: "왕십리역 광장",
  왕십리역: "왕십리역 광장",
  청량리: "청량리역 일대",
  청량리역: "청량리역 일대",
  여의도: "여의도역·여의도공원 일대",
  여의도역: "여의도역·여의도공원 일대",
  잠실: "잠실역 일대",
  잠실역: "잠실역 일대",
  건대: "건대입구역 일대",
  건대입구: "건대입구역 일대",
  건대입구역: "건대입구역 일대",
  사당: "사당역 일대",
  사당역: "사당역 일대",
  노량진: "노량진역 일대",
  노량진역: "노량진역 일대",
};

const COORDINATE_STATUS_LABELS = {
  [DEMO_FALLBACK_COORDINATE_SOURCE]: "Demo Fallback",
  [KNOWN_SEOUL_COORDINATE_SOURCE]: "Known Seoul Coordinate",
  original: "지도 표시 가능",
  merged_static: "지도 표시 가능",
  cached: "저장된 좌표 사용",
  geocoded: "Kakao 검색 좌표",
  not_found: "좌표 확인 필요",
  address_missing: "주소 확인 필요",
  kakao_sdk_not_loaded: "지도 서비스를 불러오지 못했습니다",
  invalid_lat_lng: "좌표 형식 오류",
  district_mismatch_geocode_rejected: "검색 결과의 자치구가 달라 지도 표시 제외",
};

const COORDINATE_STATUS_DETAILS = {
  [DEMO_FALLBACK_COORDINATE_SOURCE]: "Demo fallback route coordinates are used only for the route/map demo.",
  [KNOWN_SEOUL_COORDINATE_SOURCE]: "A known Seoul coordinate matched this exact place name.",
  original: "원본 데이터에 포함된 좌표를 사용합니다.",
  merged_static: "검증된 기존 후보 데이터의 좌표를 사용합니다.",
  cached: "이전에 자치구 검증을 통과한 Kakao 좌표를 사용합니다.",
  geocoded: "Kakao 검색 결과 중 서울시와 선택 자치구가 일치한 좌표입니다.",
  not_found: "Kakao 검색으로 검증 가능한 좌표를 찾지 못했습니다.",
  address_missing: "주소가 없어 장소명과 자치구 기준으로만 검색했습니다.",
  kakao_sdk_not_loaded: "지도 SDK 또는 Kakao services 로딩에 실패했습니다.",
  invalid_lat_lng: "좌표값이 숫자 형식 또는 서울 범위를 벗어났습니다.",
  district_mismatch_geocode_rejected: "검색 결과가 다른 자치구로 확인되어 marker에서 제외했습니다.",
};

const FEATURE_SCORE_ROWS = [
  ["district_score", "district score", "선택 자치구와 추천 후보의 지역 적합도"],
  ["market_score", "market score", "전통시장·골목상권·상권 활성도 근거"],
  ["park_score", "park score", "공원·생활권 접점 근거"],
  ["worker_score", "worker score", "직장인구·출퇴근 접점 근거"],
  ["population_score", "population score", "유동인구·생활인구 접점 근거"],
];

const FEATURE_REASON_RULES = [
  {
    label: "역세권",
    matches: /교통|station|subway|역|출구/i,
    reason: "역세권이라 출퇴근·환승 유동인구와 짧게 접촉하기 좋습니다.",
  },
  {
    label: "유동인구 높음",
    matches: /교통|상권|시장|공원|station|subway|market|commercial|park/i,
    reason: "생활 동선과 겹치는 지점이라 현장 인사 노출이 큽니다.",
  },
  {
    label: "직장인구 밀집",
    matches: /직장|퇴근|출근|업무|오피스|office|worker/i,
    reason: "직장인 타깃 메시지를 전달하기 좋은 시간대·장소 조건입니다.",
  },
  {
    label: "상권 활성도 높음",
    matches: /상권|시장|골목|market|commercial|street/i,
    reason: "상인·생활소비자와 지역경제 메시지를 연결하기 좋습니다.",
  },
  {
    label: "전통시장 존재",
    matches: /전통시장|시장|market/i,
    reason: "전통시장 방문은 상인 간담과 생활물가 메시지에 적합합니다.",
  },
  {
    label: "공원 존재",
    matches: /공원|park|숲|광장/i,
    reason: "공원·광장형 장소라 가족 단위와 생활권 주민 접점이 있습니다.",
  },
  {
    label: "복지시설 밀집",
    matches: /복지|노인|senior|welfare/i,
    reason: "복지·돌봄 정책을 현장에서 설명하기 좋은 후보지입니다.",
  },
];

export const MARKER_COORDINATE_STATUSES = new Set([
  "original",
  "merged_static",
  "cached",
  "geocoded",
  DEMO_FALLBACK_COORDINATE_SOURCE,
  KNOWN_SEOUL_COORDINATE_SOURCE,
]);
export const MARKER_COORDINATE_SOURCES = new Set([
  "original",
  "static",
  "kakao_address_search",
  "kakao_keyword_search",
  "cache",
  DEMO_FALLBACK_COORDINATE_SOURCE,
  KNOWN_SEOUL_COORDINATE_SOURCE,
]);

export function normalizeDistrictFromText(value) {
  if (value === undefined || value === null) {
    return "";
  }

  const text = String(value)
    .trim()
    .replaceAll("서울특별시", "")
    .replaceAll("서울시", "")
    .replaceAll("서울", "")
    .trim();

  if (!text) {
    return "";
  }

  for (const part of text.split(/\s+/)) {
    const token = part.trim().replace(/[,.()[\]{}]/g, "");
    if (SEOUL_DISTRICTS.includes(token)) {
      return token;
    }
    if (SEOUL_DISTRICT_ALIASES[token]) {
      return SEOUL_DISTRICT_ALIASES[token];
    }
    if (!token.endsWith("구") && SEOUL_DISTRICTS.includes(`${token}구`)) {
      return `${token}구`;
    }
  }

  if (SEOUL_DISTRICTS.includes(text)) {
    return text;
  }
  if (SEOUL_DISTRICT_ALIASES[text]) {
    return SEOUL_DISTRICT_ALIASES[text];
  }
  if (!text.endsWith("구") && SEOUL_DISTRICTS.includes(`${text}구`)) {
    return `${text}구`;
  }

  const compact = text.replace(/\s+/g, "");
  return SEOUL_DISTRICTS.find((district) => compact.includes(district)) || "";
}

export function normalizeDistrict(value) {
  return normalizeDistrictFromText(value);
}

function toNumberOrNull(value) {
  if (value === undefined || value === null || value === "") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function hasValidLatLng(latValue, lngValue) {
  const lat = toNumberOrNull(latValue);
  const lng = toNumberOrNull(lngValue);
  return (
    lat !== null &&
    lng !== null &&
    lat >= 37.0 &&
    lat <= 38.0 &&
    lng >= 126.0 &&
    lng <= 128.0
  );
}

export function getItemLatLng(item = {}) {
  const sources = [
    [item.lat, item.lng],
    [item.latitude, item.longitude],
    [item.y, item.x],
    [item.map_lat, item.map_lng],
    [item.coord_y, item.coord_x],
    [item.map_position?.lat, item.map_position?.lng],
    [item.coordinates?.lat, item.coordinates?.lng],
    [item.coordinates?.y, item.coordinates?.x],
    [item.position?.lat, item.position?.lng],
    [item.position?.y, item.position?.x],
    [item.geocoded?.lat, item.geocoded?.lng],
    [item.geocoded?.y, item.geocoded?.x],
    [item.geocode?.lat, item.geocode?.lng],
    [item.geocode?.y, item.geocode?.x],
    [item.address_coordinate?.lat, item.address_coordinate?.lng],
    [item.address_coordinate?.y, item.address_coordinate?.x],
    [item.kakao_result?.lat, item.kakao_result?.lng],
    [item.kakao_result?.y, item.kakao_result?.x],
    [item.kakao?.lat, item.kakao?.lng],
    [item.kakao?.y, item.kakao?.x],
  ];

  for (const [latValue, lngValue] of sources) {
    const lat = toNumberOrNull(latValue);
    const lng = toNumberOrNull(lngValue);
    if (hasValidLatLng(lat, lng)) {
      return { lat, lng };
    }
  }

  return { lat: null, lng: null };
}

export function hasValidCoordinates(item = {}) {
  return hasValidLatLng(item.lat, item.lng);
}

function normalizePlaceKey(placeName) {
  return String(placeName || "")
    .trim()
    .replace(/\s+/g, "")
    .toLowerCase();
}

function getCompactPlaceName(placeName) {
  return String(placeName || "").replace(/\s+/g, "").trim();
}

export function normalizePlaceName(place = {}) {
  const rawPlaceName = typeof place === "string" ? place : getCandidatePlaceName(place);
  const district = typeof place === "string" ? "" : getCandidateDistrict(place);
  const compact = getCompactPlaceName(rawPlaceName);

  if (!compact || ["확인필요", "장소확인", "해당없음", "nan", "none", "null"].includes(compact.toLowerCase())) {
    return district ? `${district} 주요 유세 지점` : "서울 주요 유세 지점";
  }

  if (ABSTRACT_PLACE_DISPLAY_NAMES[compact]) {
    return ABSTRACT_PLACE_DISPLAY_NAMES[compact];
  }

  return String(rawPlaceName || "").trim();
}

export function withDisplayPlaceName(item = {}) {
  const rawPlaceName = getCandidatePlaceName(item);
  const displayPlaceName = normalizePlaceName(item);
  return {
    ...item,
    raw_place_name: item.raw_place_name || rawPlaceName || displayPlaceName,
    display_place_name: item.display_place_name || displayPlaceName,
  };
}

function clamp01(value, fallback = 0) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return fallback;
  }
  return Math.max(0, Math.min(1, numeric));
}

function firstFiniteNumber(...values) {
  for (const value of values) {
    const numeric = Number(value);
    if (Number.isFinite(numeric)) {
      return numeric;
    }
  }
  return null;
}

function getFeatureText(item = {}) {
  return [
    item.display_place_name,
    item.place_name,
    item.raw_place_name,
    item.place_type,
    item.recommended_place_type,
    item.campaign_activity_type,
    item.target_voter_group,
    item.campaign_goal,
    item.context_tags,
    Array.isArray(item.tags) ? item.tags.join(" ") : item.tags,
    item.address,
    item.explanation,
    item.recommendation_reason,
    item.reason,
  ].filter(Boolean).join(" ");
}

function inferFeatureScores(item = {}) {
  const text = getFeatureText(item);
  const breakdown = item.score_breakdown || {};
  const districtScore = firstFiniteNumber(
    item.district_score,
    breakdown.district_score,
    breakdown.district_fit_score,
    item.district_bonus,
    item.district_match === false ? 0.25 : 0.9
  );
  const marketScore = firstFiniteNumber(
    item.market_score,
    breakdown.market_score,
    /시장|상권|market|commercial/i.test(text) ? 0.88 : 0.24
  );
  const parkScore = firstFiniteNumber(
    item.park_score,
    breakdown.park_score,
    /공원|park|숲|광장/i.test(text) ? 0.86 : 0.22
  );
  const workerScore = firstFiniteNumber(
    item.worker_score,
    item.worker_population_score,
    breakdown.worker_score,
    breakdown.worker_population_score,
    /직장|출근|퇴근|교통|역|office|worker|subway|station/i.test(text) ? 0.8 : 0.38
  );
  const populationScore = firstFiniteNumber(
    item.population_score,
    item.living_population_score,
    item.flow_score,
    breakdown.population_score,
    breakdown.living_population_score,
    /유동|생활|교통|시장|상권|공원|역|flow|population/i.test(text) ? 0.82 : 0.58
  );

  return {
    district_score: clamp01(districtScore, 0.65),
    market_score: clamp01(marketScore, 0.24),
    park_score: clamp01(parkScore, 0.22),
    worker_score: clamp01(workerScore, 0.38),
    population_score: clamp01(populationScore, 0.58),
  };
}

export function buildRouteFeatureExplanation(item = {}) {
  const text = getFeatureText(item);
  const scoreMap = inferFeatureScores(item);
  const matchedReasons = FEATURE_REASON_RULES
    .filter((rule) => rule.matches.test(text))
    .map((rule) => ({ label: rule.label, reason: rule.reason }));

  const reasons = matchedReasons.length ? matchedReasons : [
    {
      label: "선택 자치구 적합",
      reason: "선택한 자치구 안에서 운영 가능한 실제 유세 후보로 유지했습니다.",
    },
    {
      label: "생활권 접점",
      reason: "시간대와 장소 유형을 함께 고려해 현장 접촉 가능성이 있는 후보입니다.",
    },
  ];

  const score_components = FEATURE_SCORE_ROWS.map(([key, label, description]) => ({
    key,
    label,
    description,
    value: scoreMap[key],
  }));

  return {
    headline: `${reasons[0].label} 근거가 있는 추천입니다.`,
    reasons: reasons.slice(0, 4),
    score_components,
  };
}

function getCandidateDistrict(item = {}) {
  return normalizeDistrictFromText(
    item.district_normalized ||
      item.recommended_district_normalized ||
      item.district ||
      item.recommended_district ||
      item.gu ||
      item.region ||
      item.address ||
      item.road_address ||
      item.location
  );
}

function getCandidatePlaceName(item = {}) {
  return item.place_name || item.recommended_place_name || item.name || item.title || "";
}

function isFallbackCoordinateCandidate(item = {}) {
  return Boolean(item.is_fallback) || FALLBACK_SOURCE_PATTERN.test(item.source || item.candidate_source || "");
}

function isDemoFallbackCoordinateCandidate(item = {}) {
  return Boolean(item.is_demo_fallback_route) ||
    item.source === DEMO_FALLBACK_ROUTE_SOURCE ||
    item.candidate_source === DEMO_FALLBACK_ROUTE_SOURCE ||
    item.coordinate_source === DEMO_FALLBACK_COORDINATE_SOURCE ||
    item.coordinate_status === DEMO_FALLBACK_COORDINATE_SOURCE ||
    (item.candidate_source === "static_fallback" && hasValidLatLng(item.lat, item.lng));
}

function canApplyKnownCoordinate(item = {}) {
  return isDemoFallbackCoordinateCandidate(item) || !isFallbackCoordinateCandidate(item);
}

function getNormalizedCoordinatePayload(item = {}, options = {}) {
  const direct = getItemLatLng(item);
  if (hasValidLatLng(direct.lat, direct.lng)) {
    const isDemoFallback = isDemoFallbackCoordinateCandidate(item);
    return {
      lat: direct.lat,
      lng: direct.lng,
      coordinate_status: item.coordinate_status || (isDemoFallback ? DEMO_FALLBACK_COORDINATE_SOURCE : "original"),
      coordinate_source: item.coordinate_source || (isDemoFallback ? DEMO_FALLBACK_COORDINATE_SOURCE : "original"),
      is_demo_fallback_route: Boolean(item.is_demo_fallback_route) || isDemoFallback,
    };
  }

  if (options.allowKnownCoordinates === false || !canApplyKnownCoordinate(item)) {
    return {
      lat: null,
      lng: null,
      coordinate_status: item.coordinate_status || "not_found",
      coordinate_source: item.coordinate_source || "missing",
      is_demo_fallback_route: Boolean(item.is_demo_fallback_route),
    };
  }

  const known = getKnownRouteCoordinate(item);
  if (!known || !hasValidLatLng(known.lat, known.lng)) {
    return {
      lat: null,
      lng: null,
      coordinate_status: item.coordinate_status || "not_found",
      coordinate_source: item.coordinate_source || "missing",
      is_demo_fallback_route: Boolean(item.is_demo_fallback_route),
    };
  }

  return {
    lat: Number(known.lat),
    lng: Number(known.lng),
    coordinate_status: known.coordinate_status || KNOWN_SEOUL_COORDINATE_SOURCE,
    coordinate_source: known.coordinate_source || KNOWN_SEOUL_COORDINATE_SOURCE,
    is_demo_fallback_route: Boolean(item.is_demo_fallback_route) || Boolean(known.is_demo_fallback_route),
    kakao_place_name: item.kakao_place_name || known.place_name,
    kakao_address_name: item.kakao_address_name || known.address || "",
    kakao_road_address_name: item.kakao_road_address_name || known.road_address || "",
  };
}

export function normalizeRouteStops(items = [], options = {}) {
  return (Array.isArray(items) ? items : []).map((item) => {
    const normalized = getNormalizedCoordinatePayload(item, options);
    const hasCoordinates = hasValidLatLng(normalized.lat, normalized.lng);
    return {
      ...item,
      ...("kakao_place_name" in normalized ? { kakao_place_name: normalized.kakao_place_name } : {}),
      ...("kakao_address_name" in normalized ? { kakao_address_name: normalized.kakao_address_name } : {}),
      ...("kakao_road_address_name" in normalized ? { kakao_road_address_name: normalized.kakao_road_address_name } : {}),
      lat: hasCoordinates ? normalized.lat : null,
      lng: hasCoordinates ? normalized.lng : null,
      has_coordinates: hasCoordinates,
      coordinate_status: normalized.coordinate_status,
      coordinate_source: normalized.coordinate_source,
      is_demo_fallback_route: normalized.is_demo_fallback_route,
      map_position: hasCoordinates ? { lat: normalized.lat, lng: normalized.lng } : undefined,
    };
  });
}

function buildStaticCoordinateIndex(extraSources = []) {
  const index = new Map();
  const staticSources = [
    ...Object.values(STATIC_REAL_ROUTE_CANDIDATES).flat(),
    ...(Array.isArray(extraSources) ? extraSources : []),
  ];

  staticSources.forEach((candidate) => {
    if (!candidate || isFallbackCoordinateCandidate(candidate)) {
      return;
    }
    const district = getCandidateDistrict(candidate);
    const placeName = getCandidatePlaceName(candidate);
    const { lat, lng } = getItemLatLng(candidate);
    if (!district || !placeName || !hasValidLatLng(lat, lng)) {
      return;
    }
    index.set(`${district}::${normalizePlaceKey(placeName)}`, {
      lat,
      lng,
      district_normalized: district,
      coordinate_status: "merged_static",
      coordinate_source: "static",
      kakao_place_name: candidate.kakao_place_name || placeName,
      kakao_address_name: candidate.kakao_address_name || candidate.address || candidate.road_address || "",
      kakao_road_address_name: candidate.kakao_road_address_name || candidate.road_address || "",
    });
  });

  return index;
}

function buildCoordinateCacheKey(item = {}) {
  const district = item.district_normalized || normalizeDistrictFromText(item.district);
  const placeName = item.place_name || item.recommended_place_name || "";
  const address = item.address || item.road_address || "";
  return `${COORDINATE_CACHE_PREFIX}::${COORDINATE_CACHE_VERSION}::${district}::${placeName}::${address}`;
}

function canUseLocalStorage() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function readCoordinateCache(item = {}) {
  if (!canUseLocalStorage()) {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(buildCoordinateCacheKey(item));
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw);
    return parsed?.version === COORDINATE_CACHE_VERSION ? parsed : null;
  } catch (error) {
    return null;
  }
}

function writeCoordinateCache(item = {}) {
  if (!canUseLocalStorage()) {
    return;
  }

  try {
    const value = {
      version: COORDINATE_CACHE_VERSION,
      lat: item.lat,
      lng: item.lng,
      district_normalized: item.district_normalized,
      coordinate_status: item.coordinate_status,
      coordinate_source: item.coordinate_source,
      kakao_place_name: item.kakao_place_name,
      kakao_address_name: item.kakao_address_name,
      kakao_road_address_name: item.kakao_road_address_name,
      updated_at: new Date().toISOString(),
    };
    window.localStorage.setItem(buildCoordinateCacheKey(item), JSON.stringify(value));
  } catch (error) {
    // Cache failure must not block recommendation rendering.
  }
}

function getKakaoAppKey() {
  const primary = process.env.NEXT_PUBLIC_KAKAO_MAP_API_KEY || "";
  const legacy = process.env.NEXT_PUBLIC_KAKAO_MAP_JS_KEY || "";
  return String(primary || legacy).trim();
}

function buildKakaoSdkSrc(appKey) {
  const params = new URLSearchParams({
    appkey: appKey,
    autoload: "false",
    libraries: "services",
  });
  return `${KAKAO_SDK_BASE_URL}?${params.toString()}`;
}

function isLikelyKakaoAppKey(appKey) {
  return /^[A-Za-z0-9_-]{20,64}$/.test(String(appKey || "").trim()) && !/^https?:\/\//i.test(appKey);
}

function waitForKakaoMapsLoad(kakao) {
  return new Promise((resolve, reject) => {
    if (!kakao?.maps?.load) {
      reject(new Error("kakao.maps.load is unavailable"));
      return;
    }
    try {
      kakao.maps.load(() => resolve(kakao));
    } catch (error) {
      reject(error);
    }
  });
}

export async function ensureKakaoMapsServicesLoaded() {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return null;
  }

  if (window.kakao?.maps?.services?.Places && window.kakao?.maps?.services?.Geocoder) {
    return window.kakao;
  }

  const appKey = getKakaoAppKey();
  if (!isLikelyKakaoAppKey(appKey)) {
    return null;
  }

  if (window.__kakaoMapSdkPromise) {
    try {
      const kakao = await window.__kakaoMapSdkPromise;
      return kakao?.maps?.services ? kakao : null;
    } catch (error) {
      return null;
    }
  }

  window.__kakaoMapSdkPromise = new Promise((resolve, reject) => {
    const sdkSrc = buildKakaoSdkSrc(appKey);
    let script = document.getElementById(KAKAO_SDK_SCRIPT_ID);
    if (script && script.src && script.src !== sdkSrc) {
      script.remove();
      script = null;
    }

    const resolveLoadedSdk = () => {
      if (!window.kakao?.maps) {
        reject(new Error("Kakao maps SDK did not expose window.kakao.maps"));
        return;
      }
      waitForKakaoMapsLoad(window.kakao)
        .then((kakao) => resolve(kakao))
        .catch(reject);
    };

    if (!script) {
      script = document.createElement("script");
      script.id = KAKAO_SDK_SCRIPT_ID;
      script.src = sdkSrc;
      script.async = true;
      script.dataset.kakaoSdkStatus = "loading";
      script.onload = () => {
        script.dataset.kakaoSdkStatus = "loaded";
        resolveLoadedSdk();
      };
      script.onerror = () => {
        script.dataset.kakaoSdkStatus = "error";
        reject(new Error("Kakao maps SDK failed to load"));
      };
      document.head.appendChild(script);
      return;
    }

    if (script.dataset.kakaoSdkStatus === "loaded") {
      window.setTimeout(resolveLoadedSdk, 0);
      return;
    }

    script.addEventListener("load", resolveLoadedSdk, { once: true });
    script.addEventListener("error", () => reject(new Error("Kakao maps SDK failed to load")), { once: true });
  });

  try {
    const kakao = await window.__kakaoMapSdkPromise;
    return kakao?.maps?.services ? kakao : null;
  } catch (error) {
    window.__kakaoMapSdkPromise = null;
    return null;
  }
}

function extractDistrictFromKakaoResult(result = {}) {
  const text = [
    result.address_name,
    result.road_address_name,
    result.place_name,
    result.address?.region_2depth_name,
    result.road_address?.region_2depth_name,
    result.address?.address_name,
    result.road_address?.address_name,
  ].filter(Boolean).join(" ");

  return normalizeDistrictFromText(text);
}

function isSeoulKakaoResult(result = {}) {
  const text = [
    result.address_name,
    result.road_address_name,
    result.address?.region_1depth_name,
    result.road_address?.region_1depth_name,
    result.address?.address_name,
    result.road_address?.address_name,
  ].filter(Boolean).join(" ");

  return /서울|서울특별시|서울시/.test(text);
}

export function pickBestKakaoResult(results = [], expectedDistrict) {
  return pickBestKakaoResultWithMeta(results, expectedDistrict).picked;
}

function pickBestKakaoResultWithMeta(results = [], expectedDistrict) {
  const normalizedExpected = normalizeDistrictFromText(expectedDistrict);
  if (!normalizedExpected) {
    return {
      picked: null,
      districtRejectedCount: 0,
      nonSeoulRejectedCount: 0,
      invalidCoordinateCount: 0,
      hadResults: Boolean(results?.length),
    };
  }

  let districtRejectedCount = 0;
  let nonSeoulRejectedCount = 0;
  let invalidCoordinateCount = 0;
  for (const result of results || []) {
    if (!hasValidLatLng(result.y, result.x)) {
      invalidCoordinateCount += 1;
      continue;
    }

    if (!isSeoulKakaoResult(result)) {
      nonSeoulRejectedCount += 1;
      continue;
    }

    const resultDistrict = extractDistrictFromKakaoResult(result);
    if (resultDistrict === normalizedExpected) {
      return { picked: result, districtRejectedCount, nonSeoulRejectedCount, invalidCoordinateCount, hadResults: true };
    }

    const addressText = [
      result.address_name,
      result.road_address_name,
      result.address?.address_name,
      result.road_address?.address_name,
    ].filter(Boolean).join(" ");
    if (addressText.includes(normalizedExpected)) {
      return { picked: result, districtRejectedCount, nonSeoulRejectedCount, invalidCoordinateCount, hadResults: true };
    }

    if (resultDistrict && resultDistrict !== normalizedExpected) {
      districtRejectedCount += 1;
    }
  }

  return { picked: null, districtRejectedCount, nonSeoulRejectedCount, invalidCoordinateCount, hadResults: Boolean(results?.length) };
}

function buildKakaoResultPayload(result, coordinateSource) {
  if (!result || !hasValidLatLng(result.y, result.x)) {
    return null;
  }

  return {
    ...result,
    coordinate_source: coordinateSource,
    y: Number(result.y),
    x: Number(result.x),
  };
}

function buildDistrictRejectedPayload(meta, coordinateSource) {
  if (!meta.hadResults || !meta.districtRejectedCount) {
    return null;
  }
  return {
    coordinate_source: coordinateSource,
    district_mismatch_rejected: true,
    rejected_count: meta.districtRejectedCount,
    non_seoul_rejected_count: meta.nonSeoulRejectedCount || 0,
    invalid_coordinate_count: meta.invalidCoordinateCount || 0,
  };
}

export async function searchKakaoKeyword(query, expectedDistrict) {
  const kakao = await ensureKakaoMapsServicesLoaded();
  if (!kakao?.maps?.services?.Places || !query) {
    return {
      coordinate_source: "kakao_keyword_search",
      kakao_sdk_not_loaded: true,
    };
  }

  return new Promise((resolve) => {
    const places = new kakao.maps.services.Places();
    places.keywordSearch(query, (results, status) => {
      if (status !== kakao.maps.services.Status.OK) {
        resolve({
          coordinate_source: "kakao_keyword_search",
          search_not_found: true,
          kakao_status: status,
        });
        return;
      }

      const meta = pickBestKakaoResultWithMeta(results, expectedDistrict);
      resolve(buildKakaoResultPayload(meta.picked, "kakao_keyword_search") || buildDistrictRejectedPayload(meta, "kakao_keyword_search"));
    });
  });
}

export async function searchKakaoAddress(query, expectedDistrict) {
  const kakao = await ensureKakaoMapsServicesLoaded();
  if (!kakao?.maps?.services?.Geocoder || !query) {
    return {
      coordinate_source: "kakao_address_search",
      kakao_sdk_not_loaded: true,
    };
  }

  return new Promise((resolve) => {
    const geocoder = new kakao.maps.services.Geocoder();
    geocoder.addressSearch(query, (results, status) => {
      if (status !== kakao.maps.services.Status.OK) {
        resolve({
          coordinate_source: "kakao_address_search",
          search_not_found: true,
          kakao_status: status,
        });
        return;
      }

      const meta = pickBestKakaoResultWithMeta(results, expectedDistrict);
      resolve(buildKakaoResultPayload(meta.picked, "kakao_address_search") || buildDistrictRejectedPayload(meta, "kakao_address_search"));
    });
  });
}

async function searchKakaoAddressOrKeyword({ query, expectedDistrict, mode }) {
  if (mode === "address") {
    return searchKakaoAddress(query, expectedDistrict);
  }
  return searchKakaoKeyword(query, expectedDistrict);
}

function normalizeCoordinateFields(item = {}, status = "original", source = "original") {
  const coords = getItemLatLng(item);
  return {
    ...item,
    lat: coords.lat,
    lng: coords.lng,
    has_coordinates: hasValidLatLng(coords.lat, coords.lng),
    coordinate_status: item.coordinate_status || status,
    coordinate_source: item.coordinate_source || source,
    map_position: hasValidLatLng(coords.lat, coords.lng) ? { lat: coords.lat, lng: coords.lng } : undefined,
  };
}

function buildCoordinateDebug(reason, extra = {}) {
  return {
    cache_version: COORDINATE_CACHE_VERSION,
    reason,
    ...extra,
  };
}

function hasMissingAddress(address) {
  return !String(address || "").trim() || ADDRESS_MISSING_PATTERN.test(String(address || ""));
}

export async function enrichRouteItemCoordinates(item = {}, options = {}) {
  const district = normalizeDistrictFromText(item.district_normalized || item.district);
  const placeName = item.place_name || item.recommended_place_name || item.name || "";
  const baseItem = {
    ...withDisplayPlaceName(item),
    district_normalized: district,
  };

  if (!district || !placeName) {
    return {
      ...baseItem,
      lat: null,
      lng: null,
      has_coordinates: false,
      coordinate_status: "not_found",
      coordinate_source: "missing_required_fields",
      coordinate_debug: buildCoordinateDebug("missing_required_fields", { district, place_name: placeName }),
      map_position: undefined,
    };
  }

  const normalizedBase = normalizeRouteStops([baseItem])[0] || baseItem;
  const existingCoords = getItemLatLng(normalizedBase);
  if (hasValidLatLng(existingCoords.lat, existingCoords.lng)) {
    return normalizeCoordinateFields(
      { ...normalizedBase, lat: existingCoords.lat, lng: existingCoords.lng },
      normalizedBase.coordinate_status || "original",
      normalizedBase.coordinate_source || "original"
    );
  }

  if (isFallbackCoordinateCandidate(normalizedBase) && !isDemoFallbackCoordinateCandidate(normalizedBase)) {
    return {
      ...normalizedBase,
      lat: null,
      lng: null,
      has_coordinates: false,
      coordinate_status: "not_found",
      coordinate_source: "fallback_coordinate_rejected",
      coordinate_debug: buildCoordinateDebug("fallback_coordinate_rejected"),
      map_position: undefined,
    };
  }

  const staticIndex = options.staticCoordinateIndex || buildStaticCoordinateIndex(options.coordinateSources);
  const staticMatch = staticIndex.get(`${district}::${normalizePlaceKey(placeName)}`);
  if (staticMatch && hasValidLatLng(staticMatch.lat, staticMatch.lng) && staticMatch.district_normalized === district) {
    return {
      ...normalizedBase,
      ...staticMatch,
      has_coordinates: true,
      coordinate_debug: buildCoordinateDebug("static_coordinate_match"),
      map_position: { lat: staticMatch.lat, lng: staticMatch.lng },
    };
  }

  const cached = readCoordinateCache(normalizedBase);
  if (
    cached &&
    cached.district_normalized === district &&
    hasValidLatLng(cached.lat, cached.lng)
  ) {
    return {
      ...normalizedBase,
      lat: Number(cached.lat),
      lng: Number(cached.lng),
      has_coordinates: true,
      coordinate_status: "cached",
      coordinate_source: cached.coordinate_source || "cache",
      kakao_place_name: cached.kakao_place_name,
      kakao_address_name: cached.kakao_address_name,
      kakao_road_address_name: cached.kakao_road_address_name,
      coordinate_debug: buildCoordinateDebug("cache_hit"),
      map_position: { lat: Number(cached.lat), lng: Number(cached.lng) },
    };
  }

  let kakaoResult = null;
  let rejectedCount = 0;
  let sdkMissingCount = 0;
  let notFoundCount = 0;
  const attempts = [];
  const address = String(normalizedBase.address || normalizedBase.road_address || "").trim();
  if (!hasMissingAddress(address)) {
    const addressResult = await searchKakaoAddressOrKeyword({
      query: address,
      expectedDistrict: district,
      mode: "address",
    });
    attempts.push({ mode: "address", query: address, status: addressResult?.coordinate_source || "not_attempted" });
    if (addressResult?.district_mismatch_rejected) {
      rejectedCount += Number(addressResult.rejected_count || 0);
    } else if (addressResult?.kakao_sdk_not_loaded) {
      sdkMissingCount += 1;
    } else if (addressResult?.search_not_found) {
      notFoundCount += 1;
    } else {
      kakaoResult = addressResult;
    }
  } else {
    attempts.push({ mode: "address", query: "", status: "address_missing" });
  }

  if (!kakaoResult) {
    const keywordQuery = `서울 ${district} ${placeName}`;
    const keywordResult = await searchKakaoAddressOrKeyword({
      query: keywordQuery,
      expectedDistrict: district,
      mode: "keyword",
    });
    attempts.push({ mode: "keyword", query: keywordQuery, status: keywordResult?.coordinate_source || "not_attempted" });
    if (keywordResult?.district_mismatch_rejected) {
      rejectedCount += Number(keywordResult.rejected_count || 0);
    } else if (keywordResult?.kakao_sdk_not_loaded) {
      sdkMissingCount += 1;
    } else if (keywordResult?.search_not_found) {
      notFoundCount += 1;
    } else {
      kakaoResult = keywordResult;
    }
  }

  if (!kakaoResult) {
    const status = rejectedCount > 0
      ? "district_mismatch_geocode_rejected"
      : sdkMissingCount > 0
        ? "kakao_sdk_not_loaded"
        : hasMissingAddress(address)
          ? "address_missing"
          : "not_found";
    return {
      ...normalizedBase,
      lat: null,
      lng: null,
      has_coordinates: false,
      coordinate_status: status,
      coordinate_source: rejectedCount > 0
        ? "district_mismatch_rejected"
        : sdkMissingCount > 0
          ? "kakao_sdk_not_loaded"
          : "kakao_search_failed",
      coordinate_rejected_count: rejectedCount,
      coordinate_debug: buildCoordinateDebug(status, {
        attempts,
        district_mismatch_rejected_count: rejectedCount,
        sdk_missing_count: sdkMissingCount,
        search_not_found_count: notFoundCount,
      }),
      map_position: undefined,
    };
  }

  const enriched = {
    ...normalizedBase,
    lat: Number(kakaoResult.y),
    lng: Number(kakaoResult.x),
    has_coordinates: true,
    coordinate_status: "geocoded",
    coordinate_source: kakaoResult.coordinate_source,
    kakao_place_name: kakaoResult.place_name || placeName,
    kakao_address_name: kakaoResult.address_name || kakaoResult.address?.address_name || "",
    kakao_road_address_name: kakaoResult.road_address_name || kakaoResult.road_address?.address_name || "",
    coordinate_rejected_count: rejectedCount,
    coordinate_debug: buildCoordinateDebug("kakao_geocoded", {
      attempts,
      district_mismatch_rejected_count: rejectedCount,
    }),
    map_position: { lat: Number(kakaoResult.y), lng: Number(kakaoResult.x) },
  };
  writeCoordinateCache(enriched);
  return enriched;
}

export async function enrichRouteTimelineCoordinates(timeline = [], options = {}) {
  const staticCoordinateIndex = buildStaticCoordinateIndex(options.coordinateSources);
  const enriched = [];

  for (const item of timeline) {
    const enrichedItem = await enrichRouteItemCoordinates(item, {
      ...options,
      staticCoordinateIndex,
    });
    enriched.push({
      ...enrichedItem,
      feature_explanation: buildRouteFeatureExplanation(enrichedItem),
      coordinate_status_label: getCoordinateStatusLabel(enrichedItem.coordinate_status),
      coordinate_status_detail: getCoordinateStatusDetail(enrichedItem.coordinate_status),
    });
  }

  return enriched;
}

function hasAllowedMarkerCoordinateMeta(item = {}) {
  const status = item.coordinate_status || (hasValidCoordinates(item) ? "original" : "not_found");
  const source = item.coordinate_source || (hasValidCoordinates(item) ? "original" : "missing");
  return MARKER_COORDINATE_STATUSES.has(status) && MARKER_COORDINATE_SOURCES.has(source);
}

function hasDisallowedMarkerSource(item = {}) {
  if (isDemoFallbackCoordinateCandidate(item)) {
    return false;
  }
  return Boolean(item.is_fallback) ||
    FALLBACK_SOURCE_PATTERN.test(item.source || "") ||
    FALLBACK_SOURCE_PATTERN.test(item.candidate_source || "") ||
    FALLBACK_SOURCE_PATTERN.test(item.coordinate_source || "") ||
    item.coordinate_status === "district_mismatch_geocode_rejected";
}

export function isMarkerEligible(item = {}) {
  return Boolean(
    item.route_item_id &&
      item.place_name &&
      item.district_normalized &&
      hasValidCoordinates(item) &&
      hasAllowedMarkerCoordinateMeta(item) &&
      !hasDisallowedMarkerSource(item)
  );
}

export const canRenderRouteMarker = isMarkerEligible;

export function buildRouteMarkersFromTimeline(timeline = []) {
  return timeline
    .map((item, index) => ({
      id: item.route_item_id,
      route_item_id: item.route_item_id,
      order: Number(item.order ?? item.sequence ?? item.rank ?? index + 1) || index + 1,
      sequence: Number(item.sequence ?? item.order ?? item.rank ?? index + 1) || index + 1,
      place_name: item.display_place_name || item.place_name,
      display_place_name: item.display_place_name || item.place_name,
      raw_place_name: item.raw_place_name || item.place_name,
      district: item.district,
      district_normalized: item.district_normalized,
      address: item.address,
      lat: item.lat,
      lng: item.lng,
      source: item.source,
      coordinate_status: item.coordinate_status,
      coordinate_source: item.coordinate_source,
      kakao_place_name: item.kakao_place_name,
      kakao_address_name: item.kakao_address_name,
      kakao_road_address_name: item.kakao_road_address_name,
      is_fallback: item.is_fallback,
      explanation: item.explanation,
      reason: item.explanation,
      time: item.time,
      start_time: item.start_time,
      place_type: item.place_type,
      score: item.score,
      fit_label: item.fit_label,
      has_coordinates: hasValidCoordinates(item),
    }))
    .filter((marker) => {
      const item = timeline.find((candidate, index) =>
        (candidate.route_item_id === marker.route_item_id) &&
        ((Number(candidate.order ?? candidate.sequence ?? candidate.rank ?? index + 1) || index + 1) === marker.order)
      );
      return Boolean(
        item &&
          isMarkerEligible(marker) &&
          marker.route_item_id === item.route_item_id &&
          marker.district_normalized === item.district_normalized
      );
    });
}

export function buildNoCoordinateItemsFromTimeline(timeline = []) {
  return timeline.filter((item) => !isMarkerEligible(item));
}

export function getCoordinateStatusCounts(timeline = []) {
  return timeline.reduce((counts, item) => {
    const status = item.coordinate_status || (hasValidCoordinates(item) ? "original" : "not_found");
    counts[status] = (counts[status] || 0) + 1;
    return counts;
  }, {});
}

export function getCoordinateSourceCounts(timeline = []) {
  return timeline.reduce((counts, item) => {
    const source = item.coordinate_source || (hasValidCoordinates(item) ? "original" : "missing");
    counts[source] = (counts[source] || 0) + 1;
    return counts;
  }, {});
}

export function getCoordinateStatusMessage({
  coordinateLoading = false,
  totalCount = 0,
  markerCount = 0,
  noCoordinateCount = 0,
} = {}) {
  if (coordinateLoading) {
    return "추천 장소의 지도 좌표를 확인하는 중입니다.";
  }
  if (totalCount > 0 && markerCount === totalCount) {
    return `전체 ${totalCount}개 중 ${markerCount}개를 지도에 표시했습니다.`;
  }
  if (markerCount > 0 && noCoordinateCount > 0) {
    return `전체 ${totalCount}개 중 ${markerCount}개만 지도에 표시됩니다. ${noCoordinateCount}개는 좌표 확인이 필요해 추천 결과에는 유지하고 marker에서만 제외했습니다.`;
  }
  if (totalCount > 0 && markerCount === 0) {
    return "추천 장소는 생성되었지만 검증된 좌표가 없어 marker를 표시하지 않습니다. 타임라인에서 좌표 확인 필요 항목을 확인해주세요.";
  }
  return "추천 조건을 입력하면 지도 표시 가능 여부를 확인합니다.";
}

export function getCoordinateStatusLabel(status) {
  return COORDINATE_STATUS_LABELS[status] || COORDINATE_STATUS_LABELS.not_found;
}

export function getCoordinateStatusDetail(status) {
  return COORDINATE_STATUS_DETAILS[status] || COORDINATE_STATUS_DETAILS.not_found;
}

export function getCoordinateDebugSummary(timeline = []) {
  const markers = buildRouteMarkersFromTimeline(timeline);
  const noCoordinateItems = buildNoCoordinateItemsFromTimeline(timeline);
  return {
    result_count: timeline.length,
    marker_count: markers.length,
    no_coord_count: noCoordinateItems.length,
    noCoordinate_count: noCoordinateItems.length,
    status_counts: getCoordinateStatusCounts(timeline),
    source_counts: getCoordinateSourceCounts(timeline),
    geocoded_count: timeline.filter((item) => item.coordinate_status === "geocoded").length,
    cached_count: timeline.filter((item) => item.coordinate_status === "cached").length,
    not_found_count: timeline.filter((item) => ["not_found", "address_missing", "kakao_sdk_not_loaded"].includes(item.coordinate_status)).length,
    district_mismatch_rejected_count: timeline.reduce((sum, item) => sum + Number(item.coordinate_rejected_count || (item.coordinate_status === "district_mismatch_geocode_rejected" ? 1 : 0)), 0),
    rejected_count: timeline.reduce((sum, item) => sum + Number(item.coordinate_rejected_count || (item.coordinate_status === "district_mismatch_geocode_rejected" ? 1 : 0)), 0),
  };
}
