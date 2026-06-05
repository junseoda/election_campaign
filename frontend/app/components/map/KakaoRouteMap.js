"use client";

import { useEffect, useMemo, useRef, useState } from "react";

const DEFAULT_EMPTY_MAP_CENTER = { lat: 37.55, lng: 126.99 };
const SDK_SCRIPT_ID = "kakao-map-sdk";
const KAKAO_SDK_BASE_URL = "https://dapi.kakao.com/v2/maps/sdk.js";
const MAP_STATUS_LABELS = {
  connected: "Kakao Map Connected",
  fallback: "Fallback Map Preview",
  loading: "Map Loading",
  unavailable: "Map Unavailable",
};
const ENABLE_KAKAO_MAP_DEBUG =
  process.env.NODE_ENV !== "production" || process.env.NEXT_PUBLIC_KAKAO_MAP_DEBUG === "true";

function normalizeAppKey(appKey) {
  return typeof appKey === "string" ? appKey.trim() : "";
}

function getAppKeyLabel(appKey) {
  const normalized = normalizeAppKey(appKey);
  if (!normalized) {
    return "missing";
  }
  return `${normalized.slice(0, 4)}...(${normalized.length})`;
}

function isLikelyKakaoAppKey(appKey) {
  const normalized = normalizeAppKey(appKey);
  return /^[A-Za-z0-9_-]{20,64}$/.test(normalized) && !/^https?:\/\//i.test(normalized);
}

function buildKakaoSdkSrc(appKey) {
  return `${KAKAO_SDK_BASE_URL}?appkey=${encodeURIComponent(normalizeAppKey(appKey))}&autoload=false&libraries=services`;
}

function buildMaskedKakaoSdkSrc(appKey) {
  return `${KAKAO_SDK_BASE_URL}?appkey=${getAppKeyLabel(appKey)}&autoload=false&libraries=services`;
}

function getKakaoAppKeyCandidates() {
  return [
    { name: "NEXT_PUBLIC_KAKAO_JAVASCRIPT_KEY", value: normalizeAppKey(process.env.NEXT_PUBLIC_KAKAO_JAVASCRIPT_KEY) },
    { name: "NEXT_PUBLIC_KAKAO_MAP_API_KEY", value: normalizeAppKey(process.env.NEXT_PUBLIC_KAKAO_MAP_API_KEY) },
    { name: "NEXT_PUBLIC_KAKAO_MAP_KEY", value: normalizeAppKey(process.env.NEXT_PUBLIC_KAKAO_MAP_KEY) },
    { name: "NEXT_PUBLIC_KAKAO_MAP_JS_KEY", value: normalizeAppKey(process.env.NEXT_PUBLIC_KAKAO_MAP_JS_KEY) },
  ];
}

function getKakaoAppKeyConfig() {
  const candidates = getKakaoAppKeyCandidates();
  const valid = candidates.find(({ value }) => isLikelyKakaoAppKey(value));
  return {
    appKey: valid?.value || "",
    envName: valid?.name || "",
    invalidNames: candidates
      .filter(({ value }) => value && !isLikelyKakaoAppKey(value))
      .map(({ name }) => name),
    hasAnyConfiguredValue: candidates.some(({ value }) => Boolean(value)),
  };
}

function warnKakaoMap(message, details = {}) {
  if (typeof console === "undefined") {
    return;
  }
  console.warn(`[KakaoMap] ${message}`, details);
}

function debugKakaoMap(message, details = {}) {
  if (!ENABLE_KAKAO_MAP_DEBUG || typeof console === "undefined") {
    return;
  }
  console.debug(`[KakaoMap] ${message}`, details);
}

function debugKakaoMapDiagnostics(message, container, map) {
  if (!ENABLE_KAKAO_MAP_DEBUG) {
    return;
  }
  debugKakaoMap(message, getTileDiagnostics(container, map));
}

function waitForKakaoMapsLoad(kakao, details = {}) {
  return new Promise((resolve, reject) => {
    if (!kakao?.maps?.load) {
      reject(new Error("kakao.maps.load is unavailable"));
      return;
    }

    try {
      kakao.maps.load(() => {
        debugKakaoMap("kakao.maps.load completed", {
          ...details,
          hasMapConstructor: Boolean(kakao?.maps?.Map),
          hasRoadmapType: kakao?.maps?.MapTypeId?.ROADMAP !== undefined && kakao?.maps?.MapTypeId?.ROADMAP !== null,
        });
        resolve(kakao);
      });
    } catch (error) {
      reject(error);
    }
  });
}

function toFiniteNumber(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function getValidMapCoord(latValue, lngValue) {
  const lat = toFiniteNumber(latValue);
  const lng = toFiniteNumber(lngValue);
  if (lat === null || lng === null) {
    return null;
  }

  // Route markers must come from exact Seoul-area coordinates, never from borrowed fallback positions.
  if (lat < 37.0 || lat > 38.0 || lng < 126.0 || lng > 128.0) {
    return null;
  }

  return { lat, lng };
}

function getContainerMetrics(container) {
  if (!container) {
    return {
      clientWidth: 0,
      clientHeight: 0,
      rectWidth: 0,
      rectHeight: 0,
    };
  }

  const rect = container.getBoundingClientRect();
  return {
    clientWidth: container.clientWidth,
    clientHeight: container.clientHeight,
    rectWidth: Math.round(rect.width),
    rectHeight: Math.round(rect.height),
  };
}

function hasRenderableSize(metrics) {
  return metrics.clientWidth > 0 && metrics.clientHeight > 0 && metrics.rectWidth > 0 && metrics.rectHeight > 0;
}

function getMapTypeId(map) {
  try {
    return typeof map?.getMapTypeId === "function" ? map.getMapTypeId() : "unavailable";
  } catch (error) {
    return `unavailable: ${error?.message || String(error)}`;
  }
}

function forceRoadmap(kakao, map) {
  const roadmapType = kakao?.maps?.MapTypeId?.ROADMAP;
  if (roadmapType !== undefined && roadmapType !== null && typeof map?.setMapTypeId === "function") {
    map.setMapTypeId(roadmapType);
  }
}

function enableMapInteractions(map) {
  if (typeof map?.setDraggable === "function") {
    map.setDraggable(true);
  }
  if (typeof map?.setZoomable === "function") {
    map.setZoomable(true);
  }
}

function addZoomControl(kakao, map) {
  if (!kakao?.maps?.ZoomControl || !kakao.maps.ControlPosition?.RIGHT || typeof map?.addControl !== "function") {
    return;
  }

  const zoomControl = new kakao.maps.ZoomControl();
  map.addControl(zoomControl, kakao.maps.ControlPosition.RIGHT);
}

function getMapRuntimeState(map) {
  if (!map) {
    return {
      center: null,
      level: null,
      mapTypeId: getMapTypeId(map),
    };
  }

  try {
    const center = typeof map.getCenter === "function" ? map.getCenter() : null;
    return {
      center: center ? {
        lat: typeof center.getLat === "function" ? center.getLat() : null,
        lng: typeof center.getLng === "function" ? center.getLng() : null,
      } : null,
      level: typeof map.getLevel === "function" ? map.getLevel() : null,
      mapTypeId: getMapTypeId(map),
    };
  } catch (error) {
    return {
      center: null,
      level: null,
      mapTypeId: getMapTypeId(map),
      error: error?.message || String(error),
    };
  }
}

function extractCssUrlValues(value = "") {
  const urls = [];
  const pattern = /url\((["']?)(.*?)\1\)/gi;
  let match = pattern.exec(value);
  while (match) {
    if (match[2]) {
      urls.push(match[2]);
    }
    match = pattern.exec(value);
  }
  return urls;
}

function isKakaoUiImageUrl(url = "") {
  return /\/mapjsapi\/images\//i.test(url) ||
    /(?:transparent|bg_tile|white|m_bi|openhand|closedhand|cursor|control|marker)/i.test(url);
}

function isActualMapTileUrl(url = "") {
  if (!url || isKakaoUiImageUrl(url)) {
    return false;
  }
  return /\/\/map[0-4]\.daumcdn\.net\//i.test(url) ||
    /\/\/mts\.daumcdn\.net\//i.test(url) ||
    (/\/\/t[1-4]\.daumcdn\.net\//i.test(url) && /\/(?:map|map_2d|map_2d_hd|map_k3f|tiles?)\//i.test(url));
}

function getTileDiagnostics(container, map) {
  if (!container || typeof window === "undefined") {
    return {
      hasWindowKakao: false,
      hasKakaoMaps: false,
      mapCreated: Boolean(map),
      innerImgCount: 0,
      tileCandidateCount: 0,
      actualTileCount: 0,
      mapTypeId: getMapTypeId(map),
      mapState: getMapRuntimeState(map),
    };
  }

  const images = Array.from(container.querySelectorAll("img"));
  const allElements = Array.from(container.querySelectorAll("img, div"));
  const imageSources = images.map((image) => image.getAttribute("src") || "").filter(Boolean);
  const backgroundSources = allElements.flatMap((element) => {
    const style = window.getComputedStyle(element);
    return extractCssUrlValues(style.backgroundImage || "");
  });
  const allSources = [...new Set([...imageSources, ...backgroundSources])];
  const actualTileSources = allSources.filter(isActualMapTileUrl);
  const kakaoUiImageSources = allSources.filter((src) => /daumcdn|kakao/i.test(src) && !isActualMapTileUrl(src));

  return {
    hasWindowKakao: Boolean(window.kakao),
    hasKakaoMaps: Boolean(window.kakao?.maps),
    mapCreated: Boolean(map),
    innerImgCount: images.length,
    tileCandidateCount: actualTileSources.length,
    actualTileCount: actualTileSources.length,
    actualTileSources,
    kakaoUiImageCount: kakaoUiImageSources.length,
    kakaoUiImageSources,
    tileSources: allSources,
    mapTypeId: getMapTypeId(map),
    mapState: getMapRuntimeState(map),
    containerSize: getContainerMetrics(container),
  };
}

function normalizeCoord(stop) {
  const originalCoord = getValidMapCoord(stop.lat, stop.lng);
  if (originalCoord) {
    return {
      ...originalCoord,
      hasExactCoord: true,
      coordSource: stop.coordinate_source || "original",
      coordinateStatus: stop.coordinate_status || "original",
    };
  }

  const mapPositionCoord = getValidMapCoord(stop.map_position?.lat, stop.map_position?.lng);
  if (mapPositionCoord) {
    return {
      ...mapPositionCoord,
      hasExactCoord: true,
      coordSource: stop.coordinate_source || "map_position",
      coordinateStatus: stop.coordinate_status || "original",
    };
  }

  return null;
}

export function normalizeStops(stops = []) {
  return stops.map((stop, index) => {
    const sequence = Number(stop.sequence ?? stop.order ?? stop.rank ?? index + 1) || index + 1;
    const placeName = stop.display_place_name || stop.place_name || stop.recommended_place_name || "장소 확인";
    const district = stop.district || stop.recommended_district || "";
    const placeType = stop.place_type || stop.recommended_place_type || "기타";
    const coord = normalizeCoord({ ...stop, place_name: placeName, district });
    const routeItemId = stop.route_item_id || stop.id || `stop-${sequence}`;

    return {
      ...stop,
      id: routeItemId,
      route_item_id: routeItemId,
      sequence,
      order: sequence,
      time: stop.time || stop.start_time || "",
      place_name: placeName,
      display_place_name: placeName,
      raw_place_name: stop.raw_place_name || stop.place_name || placeName,
      district,
      address: stop.address || "",
      place_type: placeType,
      reason: stop.explanation || stop.reason || stop.recommendation_reason || stop.sequence_reason || "",
      fit_label: stop.fit_label || "",
      score: stop.score,
      lat: coord?.lat ?? null,
      lng: coord?.lng ?? null,
      coordinate_status: stop.coordinate_status || coord?.coordinateStatus || "",
      coordinate_source: stop.coordinate_source || coord?.coordSource || "missing",
      kakao_place_name: stop.kakao_place_name,
      kakao_address_name: stop.kakao_address_name,
      kakao_road_address_name: stop.kakao_road_address_name,
      hasExactCoord: Boolean(coord?.hasExactCoord),
      coordSource: coord?.coordSource || "missing",
      has_coordinates: Boolean(coord),
    };
  }).filter((stop) => stop.has_coordinates).sort((a, b) => a.sequence - b.sequence);
}

function getCoordBadge(stop) {
  if (!stop) {
    return "";
  }
  if (stop.coordSource === "original" || stop.coordSource === "map_position") {
    return "";
  }
  if (stop.coordinate_status === "geocoded") {
    return "Kakao 검색 좌표";
  }
  if (stop.coordinate_status === "cached") {
    return "저장된 좌표";
  }
  if (stop.coordinate_status === "merged_static") {
    return "기존 데이터 좌표";
  }
  return "";
}

function getMapCenter(stops) {
  const validStops = stops.filter((stop) => getValidMapCoord(stop.lat, stop.lng));
  if (!validStops.length) {
    return DEFAULT_EMPTY_MAP_CENTER;
  }

  const total = validStops.reduce(
    (acc, stop) => ({
      lat: acc.lat + Number(stop.lat),
      lng: acc.lng + Number(stop.lng),
    }),
    { lat: 0, lng: 0 }
  );

  return {
    lat: total.lat / validStops.length,
    lng: total.lng / validStops.length,
  };
}

function getCoordSummary(stops = []) {
  return stops.reduce((summary, stop) => {
    if (getValidMapCoord(stop.lat, stop.lng)) {
      summary.valid += 1;
    } else {
      summary.invalid += 1;
    }
    if (stop.coordSource) {
      summary.bySource[stop.coordSource] = (summary.bySource[stop.coordSource] || 0) + 1;
    }
    return summary;
  }, { valid: 0, invalid: 0, bySource: {} });
}

function getFallbackBounds(stops = []) {
  const validStops = stops.filter((stop) => getValidMapCoord(stop.lat, stop.lng));
  if (!validStops.length) {
    return null;
  }

  const lats = validStops.map((stop) => Number(stop.lat));
  const lngs = validStops.map((stop) => Number(stop.lng));
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);
  return {
    minLat,
    maxLat,
    minLng,
    maxLng,
    latSpan: Math.max(0.004, maxLat - minLat),
    lngSpan: Math.max(0.004, maxLng - minLng),
  };
}

function getFallbackMarkerStyle(stop, bounds) {
  if (!bounds || !getValidMapCoord(stop.lat, stop.lng)) {
    return { left: "50%", top: "50%" };
  }

  const left = 12 + ((Number(stop.lng) - bounds.minLng) / bounds.lngSpan) * 76;
  const top = 88 - ((Number(stop.lat) - bounds.minLat) / bounds.latSpan) * 76;
  return {
    left: `${Math.max(8, Math.min(92, left))}%`,
    top: `${Math.max(8, Math.min(92, top))}%`,
  };
}

function StaticFallbackMarkerPreview({ stops = [], selectedStop, onSelectStop }) {
  const bounds = getFallbackBounds(stops);
  if (!stops.length || !bounds) {
    return null;
  }

  return (
    <div className="staticFallbackMapCanvas" data-static-route-map="true">
      <div className="staticFallbackRouteLine" aria-hidden="true" />
      {stops.map((stop) => (
        <button
          type="button"
          key={stop.id}
          className={`kakao-route-marker ${selectedStop?.id === stop.id ? "selected" : ""}`}
          data-route-item-id={stop.route_item_id || stop.id}
          data-route-order={stop.sequence}
          data-place-name={stop.place_name}
          data-district-normalized={stop.district_normalized || stop.district || ""}
          style={getFallbackMarkerStyle(stop, bounds)}
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onSelectStop?.(stop.id);
          }}
        >
          <span>{stop.sequence}</span>
        </button>
      ))}
      {selectedStop ? (
        <div className="map-floating-card staticFallbackInfo">
          <div>
            <span className="map-badge">{selectedStop.sequence} · {selectedStop.time || "time pending"}</span>
          </div>
          <strong>{selectedStop.place_name}</strong>
          <p>{selectedStop.district || "Seoul"} · {selectedStop.place_type}</p>
        </div>
      ) : null}
    </div>
  );
}

function fitMapToStops(kakao, map, stops, compact) {
  forceRoadmap(kakao, map);
  map.relayout();

  const validStops = stops.filter((stop) => getValidMapCoord(stop.lat, stop.lng));

  if (!validStops.length) {
    map.setCenter(new kakao.maps.LatLng(DEFAULT_EMPTY_MAP_CENTER.lat, DEFAULT_EMPTY_MAP_CENTER.lng));
    map.setLevel(compact ? 8 : 7);
    return;
  }

  if (validStops.length === 1) {
    map.setCenter(new kakao.maps.LatLng(validStops[0].lat, validStops[0].lng));
    map.setLevel(compact ? 7 : 5);
    return;
  }

  const bounds = new kakao.maps.LatLngBounds();
  validStops.forEach((stop) => {
    bounds.extend(new kakao.maps.LatLng(stop.lat, stop.lng));
  });
  map.setBounds(
    bounds,
    compact ? 24 : 60,
    compact ? 24 : 64,
    compact ? 24 : 152,
    compact ? 24 : 64
  );
}

function loadKakaoSdk(appKey) {
  const normalizedAppKey = normalizeAppKey(appKey);
  if (!normalizedAppKey) {
    warnKakaoMap("Kakao map API key is missing");
    return Promise.reject(new Error("Kakao map API key is missing"));
  }

  if (!isLikelyKakaoAppKey(normalizedAppKey)) {
    warnKakaoMap("Kakao map API key looks invalid", {
      appKey: getAppKeyLabel(normalizedAppKey),
      expected: "Kakao JavaScript key, not a URL",
    });
    return Promise.reject(new Error("Kakao map API key looks invalid"));
  }

  if (typeof window === "undefined" || typeof document === "undefined") {
    warnKakaoMap("Kakao map SDK can only be loaded in the browser");
    return Promise.reject(new Error("browser-only"));
  }

  if (window.kakao?.maps) {
    return waitForKakaoMapsLoad(window.kakao, {
      scriptSrc: "existing-window-kakao",
      autoload: false,
      libraries: "services",
    });
  }

  if (window.__kakaoMapSdkPromise) {
    return window.__kakaoMapSdkPromise;
  }

  window.__kakaoMapSdkPromise = new Promise((resolve, reject) => {
    const sdkSrc = buildKakaoSdkSrc(normalizedAppKey);
    const maskedSdkSrc = buildMaskedKakaoSdkSrc(normalizedAppKey);
    let existingScript = document.getElementById(SDK_SCRIPT_ID);

    debugKakaoMap("sdk script requested", {
      scriptSrc: maskedSdkSrc,
      autoload: false,
      libraries: "services",
      existingScript: Boolean(existingScript),
    });

    if (existingScript && existingScript.src && existingScript.src !== sdkSrc) {
      existingScript.remove();
      existingScript = null;
    }

    if (existingScript?.dataset.kakaoSdkStatus === "error") {
      existingScript.remove();
      existingScript = null;
    }

    const rejectWithLog = (message, error) => {
      window.__kakaoMapSdkPromise = null;
      warnKakaoMap(message, {
        appKey: getAppKeyLabel(normalizedAppKey),
        scriptSrc: maskedSdkSrc,
        error: error?.message || String(error || message),
      });
      reject(error instanceof Error ? error : new Error(message));
    };

    const resolveLoadedSdk = () => {
      if (!window.kakao) {
        rejectWithLog(
          "Kakao map SDK loaded but window.kakao is undefined",
          new Error("Kakao map SDK loaded but window.kakao is undefined")
        );
        return;
      }

      if (!window.kakao.maps) {
        rejectWithLog(
          "Kakao map SDK loaded but window.kakao.maps is undefined",
          new Error("Kakao map SDK loaded but window.kakao.maps is undefined")
        );
        return;
      }

      waitForKakaoMapsLoad(window.kakao, {
        scriptSrc: maskedSdkSrc,
        autoload: false,
        libraries: "services",
      }).then((loadedKakao) => {
        if (!loadedKakao?.maps?.Map) {
          rejectWithLog(
            "Kakao map SDK loaded but kakao.maps.Map is unavailable",
            new Error("Kakao map SDK loaded but kakao.maps.Map is unavailable")
          );
          return;
        }
        resolve(loadedKakao);
      }).catch((error) => {
        rejectWithLog("Kakao map SDK maps.load failed", error);
      });
    };

    const script = existingScript || document.createElement("script");

    script.id = SDK_SCRIPT_ID;
    script.src = sdkSrc;
    script.async = true;
    script.dataset.kakaoSdkStatus = "loading";
    script.onload = () => {
      script.dataset.kakaoSdkStatus = "loaded";
      resolveLoadedSdk();
    };
    script.onerror = () => {
      script.dataset.kakaoSdkStatus = "error";
      rejectWithLog("Kakao map SDK script failed to load", new Error("Kakao map SDK script failed to load"));
    };

    if (!existingScript) {
      document.head.appendChild(script);
      return;
    }

    if (existingScript.dataset.kakaoSdkStatus === "loaded") {
      window.setTimeout(resolveLoadedSdk, 0);
      return;
    }
  });

  return window.__kakaoMapSdkPromise;
}

function clearOverlays(overlaysRef) {
  overlaysRef.current.forEach(({ overlay, element, handler }) => {
    if (element && handler) {
      element.removeEventListener("click", handler);
    }
    overlay.setMap(null);
  });
  overlaysRef.current = [];
}

function createMarkerElement(stop, selected) {
  const element = document.createElement("button");
  element.type = "button";
  element.className = `kakao-route-marker ${selected ? "selected" : ""}`;
  element.dataset.routeItemId = stop.route_item_id || stop.id;
  element.dataset.routeOrder = String(stop.sequence);
  element.dataset.placeName = stop.place_name;
  element.dataset.districtNormalized = stop.district_normalized || stop.district || "";
  element.setAttribute("aria-label", `${stop.sequence}번 ${stop.place_name} 선택`);
  element.innerHTML = `<span>${stop.sequence}</span>`;
  return element;
}

function getFallbackTitle(loadError) {
  if (loadError) {
    return "지도 미리보기로 표시 중";
  }
  return "지도 설정 전 미리보기";
}

function MapStateBadge({ status }) {
  const safeStatus = MAP_STATUS_LABELS[status] ? status : "unavailable";
  return (
    <span
      className={`mapStateBadge ${safeStatus}`}
      data-map-status-badge="true"
      data-map-status={safeStatus}
    >
      {MAP_STATUS_LABELS[safeStatus]}
    </span>
  );
}

function MapFallback({
  stops,
  selectedStop,
  onSelectStop,
  compact,
  loadError,
  noCoordinateCount = 0,
  totalStopCount = stops.length + noCoordinateCount,
  coordinateLoading = false,
  coordinateStatusMessage = "",
}) {
  const title = getFallbackTitle(loadError);
  const fallbackStatus = coordinateLoading
    ? "loading"
    : stops.length
      ? "fallback"
      : "unavailable";

  return (
    <div
      className={`kakao-map-card fallback ${compact ? "compact" : ""}`}
      data-kakao-route-map="fallback"
      data-map-status={fallbackStatus}
    >
      <div className="map-skeleton soft">
        <div className="mapToolbar">
          <MapStateBadge status={fallbackStatus} />
          <span>{title}</span>
          <span>{coordinateStatusMessage || (stops.length ? `${stops.length}곳` : "추천 전")}</span>
          {totalStopCount > 0 ? <span>전체 {totalStopCount}곳 · 지도 {stops.length}곳</span> : null}
          {noCoordinateCount > 0 ? <span>좌표 확인 필요 {noCoordinateCount}개</span> : null}
        </div>
        <StaticFallbackMarkerPreview
          stops={stops}
          selectedStop={selectedStop}
          onSelectStop={onSelectStop}
        />
        <div className="fallbackRouteList">
          {stops.length ? stops.map((stop) => (
            <button
              type="button"
              key={stop.id}
              data-route-item-id={stop.route_item_id || stop.id}
              data-route-order={stop.sequence}
              data-place-name={stop.place_name}
              data-district-normalized={stop.district_normalized || stop.district || ""}
              className={selectedStop?.id === stop.id ? "active" : ""}
              onClick={() => onSelectStop?.(stop.id)}
            >
              <span>{stop.sequence}</span>
              <strong>{stop.place_name}</strong>
              <small>{stop.time || "시간 확인"} · {stop.district || "서울"} · {stop.place_type}</small>
            </button>
          )) : (
            <p>추천 동선을 생성하면 지도에 방문 지점이 표시됩니다.</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default function KakaoRouteMap({
  stops = [],
  selectedStopId,
  onSelectStop,
  className = "",
  compact = false,
  startLabel = "",
  noCoordinateCount = 0,
  totalStopCount,
  coordinateLoading = false,
  coordinateStatusMessage = "",
}) {
  const appKeyConfig = useMemo(() => getKakaoAppKeyConfig(), []);
  const appKey = appKeyConfig.appKey;
  const appKeyIssue = appKey ? "" : (appKeyConfig.hasAnyConfiguredValue ? "invalid-key" : "missing-key");
  const mapRef = useRef(null);
  const kakaoMapRef = useRef(null);
  const overlaysRef = useRef([]);
  const polylineRef = useRef(null);
  const [isLoading, setIsLoading] = useState(Boolean(appKey));
  const [isReady, setIsReady] = useState(false);
  const [isRuntimeConnected, setIsRuntimeConnected] = useState(false);
  const [loadError, setLoadError] = useState("");

  const normalizedStops = useMemo(() => normalizeStops(stops), [stops]);
  const visibleTotalStopCount = Number.isFinite(Number(totalStopCount))
    ? Number(totalStopCount)
    : normalizedStops.length + Number(noCoordinateCount || 0);
  const mapStatusMessage = coordinateStatusMessage || (
    coordinateLoading
      ? "추천 장소의 지도 좌표를 확인하는 중입니다."
      : `${normalizedStops.length}개 추천 장소를 지도에 표시했습니다.`
  );
  const selectedStop = useMemo(
    () => normalizedStops.find((stop) => stop.id === selectedStopId || stop.route_item_id === selectedStopId) || (selectedStopId ? null : normalizedStops[0]),
    [normalizedStops, selectedStopId]
  );
  const stopPositionKey = useMemo(
    () => normalizedStops.map((stop) => `${stop.id}:${stop.place_name}:${stop.lat}:${stop.lng}`).join("|"),
    [normalizedStops]
  );

  useEffect(() => {
    debugKakaoMap("component mounted", {
      compact,
      hasAppKey: Boolean(appKey),
      appKeyEnvName: appKeyConfig.envName || "none",
      stopsLength: normalizedStops.length,
      coordSummary: getCoordSummary(normalizedStops),
      selectedStopId,
    });
  }, [appKey, appKeyConfig.envName, compact, normalizedStops.length, selectedStopId]);

  useEffect(() => {
    if (appKeyConfig.invalidNames.length) {
      warnKakaoMap("Some Kakao map environment variables look invalid", {
        invalidNames: appKeyConfig.invalidNames,
        selectedEnv: appKeyConfig.envName || "none",
        expected: "Kakao JavaScript key, not a URL or server key label",
      });
    }

    if (!appKey) {
      warnKakaoMap(appKeyIssue === "invalid-key" ? "Kakao map API key looks invalid" : "Kakao map API key is missing", {
        configuredEnvNames: getKakaoAppKeyCandidates()
          .filter(({ value }) => Boolean(value))
          .map(({ name }) => name),
      });
      setIsLoading(false);
      setIsRuntimeConnected(false);
      setLoadError(appKeyIssue);
      return;
    }

    if (typeof window === "undefined") {
      return;
    }

    if (!mapRef.current) {
      warnKakaoMap("Kakao map container is missing");
      setIsLoading(false);
      setIsRuntimeConnected(false);
      setLoadError("container-missing");
      return;
    }

    let cancelled = false;
    let initFrame = 0;
    let initTimer = 0;
    const diagnosticTimers = [];

    const clearScheduledWork = () => {
      if (initFrame) {
        window.cancelAnimationFrame(initFrame);
        initFrame = 0;
      }
      if (initTimer) {
        window.clearTimeout(initTimer);
        initTimer = 0;
      }
      diagnosticTimers.forEach((timer) => window.clearTimeout(timer));
      diagnosticTimers.length = 0;
    };

    const scheduleDiagnostics = (container, map, label) => {
      if (!ENABLE_KAKAO_MAP_DEBUG) {
        return;
      }

      [0, 240, 900].forEach((delay) => {
        const timer = window.setTimeout(() => {
          if (cancelled || kakaoMapRef.current !== map) {
            return;
          }
          forceRoadmap(window.kakao, map);
          map.relayout();
          debugKakaoMapDiagnostics(label, container, map);
        }, delay);
        diagnosticTimers.push(timer);
      });
    };

    setIsLoading(true);
    setIsRuntimeConnected(false);
    setLoadError("");

    loadKakaoSdk(appKey)
      .then((kakao) => {
        if (cancelled || !mapRef.current) {
          return;
        }

        debugKakaoMap("sdk ready", {
          hasWindowKakao: Boolean(window.kakao),
          hasKakaoMaps: Boolean(kakao?.maps),
          hasMapConstructor: Boolean(kakao?.maps?.Map),
          hasRoadmapType: kakao?.maps?.MapTypeId?.ROADMAP !== undefined && kakao?.maps?.MapTypeId?.ROADMAP !== null,
        });

        const initializeMap = (attempt = 0) => {
          if (cancelled || !mapRef.current || kakaoMapRef.current) {
            return;
          }

          const container = mapRef.current;
          const metrics = getContainerMetrics(container);
          debugKakaoMap("map container size", { attempt, ...metrics });

          if (!hasRenderableSize(metrics) && attempt < 8) {
            initFrame = window.requestAnimationFrame(() => {
              initTimer = window.setTimeout(() => initializeMap(attempt + 1), 100);
            });
            return;
          }

          try {
            const center = getMapCenter(normalizedStops);
            const safeCenter = getValidMapCoord(center.lat, center.lng) || DEFAULT_EMPTY_MAP_CENTER;
            debugKakaoMap("map center input", {
              requestedCenter: center,
              safeCenter,
              centerIsValid: Boolean(getValidMapCoord(center.lat, center.lng)),
              coordSummary: getCoordSummary(normalizedStops),
            });
            const map = new kakao.maps.Map(container, {
              center: new kakao.maps.LatLng(safeCenter.lat, safeCenter.lng),
              level: 4,
              mapTypeId: kakao.maps.MapTypeId.ROADMAP,
              draggable: true,
              scrollwheel: true,
              disableDoubleClickZoom: false,
            });

            kakaoMapRef.current = map;
            forceRoadmap(kakao, map);
            enableMapInteractions(map);
            addZoomControl(kakao, map);

            if (ENABLE_KAKAO_MAP_DEBUG) {
              debugKakaoMap("map created", {
                ...getTileDiagnostics(container, map),
                center: safeCenter,
              });
            }
            scheduleDiagnostics(container, map, "tile diagnostics");

            const immediateRelayoutTimer = window.setTimeout(() => {
              if (!cancelled && kakaoMapRef.current === map) {
                forceRoadmap(kakao, map);
                map.relayout();
                map.setCenter(new kakao.maps.LatLng(safeCenter.lat, safeCenter.lng));
                forceRoadmap(kakao, map);
                debugKakaoMapDiagnostics("post-create relayout 0ms", container, map);
              }
            }, 0);
            diagnosticTimers.push(immediateRelayoutTimer);

            const delayedRelayoutTimer = window.setTimeout(() => {
              if (!cancelled && kakaoMapRef.current === map) {
                forceRoadmap(kakao, map);
                map.relayout();
                map.setCenter(new kakao.maps.LatLng(safeCenter.lat, safeCenter.lng));
                debugKakaoMapDiagnostics("post-create relayout 300ms", container, map);
              }
            }, 300);
            diagnosticTimers.push(delayedRelayoutTimer);

            const fitBoundsTimer = window.setTimeout(() => {
              if (!cancelled && kakaoMapRef.current === map) {
                forceRoadmap(kakao, map);
                fitMapToStops(kakao, map, normalizedStops, compact);
                debugKakaoMapDiagnostics("post-layout diagnostics", container, map);
              }
            }, 420);
            diagnosticTimers.push(fitBoundsTimer);

            const hasConnectedRuntime = Boolean(window.kakao?.maps && kakaoMapRef.current);
            if (!hasConnectedRuntime) {
              setIsReady(false);
              setIsRuntimeConnected(false);
              setLoadError("runtime-unavailable");
              setIsLoading(false);
              return;
            }

            setIsReady(true);
            setIsRuntimeConnected(true);
            setIsLoading(false);
          } catch (error) {
            warnKakaoMap("Kakao map initialization failed", {
              appKey: getAppKeyLabel(appKey),
              error: error?.message || String(error),
              containerSize: getContainerMetrics(mapRef.current),
            });
            setIsRuntimeConnected(false);
            setLoadError("init-failed");
            setIsLoading(false);
          }
        };

        initFrame = window.requestAnimationFrame(() => {
          initTimer = window.setTimeout(() => initializeMap(), 100);
        });
      })
      .catch((error) => {
        warnKakaoMap("Kakao map SDK loading failed", {
          appKey: getAppKeyLabel(appKey),
          error: error?.message || String(error),
        });
        setIsRuntimeConnected(false);
        setLoadError("sdk-failed");
        setIsLoading(false);
      });

    return () => {
      cancelled = true;
      clearScheduledWork();
      clearOverlays(overlaysRef);
      if (polylineRef.current) {
        polylineRef.current.setMap(null);
        polylineRef.current = null;
      }
      kakaoMapRef.current = null;
    };
  }, [appKey, appKeyConfig.envName, appKeyConfig.invalidNames, appKeyIssue, compact]);

  useEffect(() => {
    if (!isReady || typeof window === "undefined") {
      return;
    }

    const verifyRuntimeConnection = () => {
      const connected = Boolean(kakaoMapRef.current && window.kakao?.maps);
      setIsRuntimeConnected(connected);
      if (!connected) {
        clearOverlays(overlaysRef);
        if (polylineRef.current) {
          polylineRef.current.setMap(null);
          polylineRef.current = null;
        }
        kakaoMapRef.current = null;
        setIsReady(false);
        setIsLoading(false);
        setLoadError("runtime-unavailable");
      }
    };

    verifyRuntimeConnection();
    const interval = window.setInterval(verifyRuntimeConnection, 1200);
    return () => {
      window.clearInterval(interval);
    };
  }, [isReady]);

  useEffect(() => {
    if (!isReady || !kakaoMapRef.current || typeof window === "undefined" || !window.kakao?.maps) {
      return;
    }

    const kakao = window.kakao;
    const map = kakaoMapRef.current;
    clearOverlays(overlaysRef);

    if (polylineRef.current) {
      polylineRef.current.setMap(null);
      polylineRef.current = null;
    }

    normalizedStops.forEach((stop) => {
      const position = new kakao.maps.LatLng(stop.lat, stop.lng);
      const selected = stop.id === selectedStop?.id;
      const element = createMarkerElement(stop, selected);
      const handler = (event) => {
        event.preventDefault();
        event.stopPropagation();
        onSelectStop?.(stop.id);
      };
      element.addEventListener("click", handler);

      const overlay = new kakao.maps.CustomOverlay({
        position,
        content: element,
        yAnchor: 1.18,
        zIndex: selected ? 80 : 20,
      });
      overlay.setMap(map);
      overlaysRef.current.push({ overlay, element, handler });
    });

    if (normalizedStops.length >= 2) {
      const linePath = normalizedStops.map((stop) => new kakao.maps.LatLng(stop.lat, stop.lng));
      const polyline = new kakao.maps.Polyline({
        path: linePath,
        strokeWeight: compact ? 2 : 3,
        strokeColor: "#f59e0b",
        strokeOpacity: compact ? 0.75 : 0.82,
        strokeStyle: "solid",
      });
      polyline.setMap(map);
      polylineRef.current = polyline;
    }

    forceRoadmap(kakao, map);
    map.relayout();
    if (ENABLE_KAKAO_MAP_DEBUG) {
      debugKakaoMap("map overlay update", {
        normalizedStops: normalizedStops.length,
        markerStops: normalizedStops.length,
        selectedStopId: selectedStop?.id || null,
        ...getTileDiagnostics(mapRef.current, map),
      });
    }

    const relayoutTimer = window.setTimeout(() => {
      if (!kakaoMapRef.current || kakaoMapRef.current !== map) {
        return;
      }
      forceRoadmap(kakao, map);
      map.relayout();
      debugKakaoMapDiagnostics("post-marker relayout", mapRef.current, map);
    }, 200);

    return () => {
      window.clearTimeout(relayoutTimer);
      clearOverlays(overlaysRef);
      if (polylineRef.current) {
        polylineRef.current.setMap(null);
        polylineRef.current = null;
      }
    };
  }, [isReady, normalizedStops, selectedStop?.id, onSelectStop, compact]);

  useEffect(() => {
    if (!isReady || !kakaoMapRef.current || typeof window === "undefined" || !window.kakao?.maps) {
      return;
    }

    const kakao = window.kakao;
    const map = kakaoMapRef.current;
    forceRoadmap(kakao, map);
    fitMapToStops(kakao, map, normalizedStops, compact);

    const relayoutTimer = window.setTimeout(() => {
      if (!kakaoMapRef.current || kakaoMapRef.current !== map) {
        return;
      }
      forceRoadmap(kakao, map);
      fitMapToStops(kakao, map, normalizedStops, compact);
      debugKakaoMapDiagnostics("routeStops relayout", mapRef.current, map);
    }, 220);

    return () => {
      window.clearTimeout(relayoutTimer);
    };
  }, [isReady, stopPositionKey, compact, normalizedStops]);

  useEffect(() => {
    if (!isReady || !selectedStop || !kakaoMapRef.current || typeof window === "undefined" || !window.kakao?.maps) {
      return;
    }
    const kakao = window.kakao;
    const map = kakaoMapRef.current;
    forceRoadmap(kakao, map);
    map.relayout();
    map.panTo(new kakao.maps.LatLng(selectedStop.lat, selectedStop.lng));
  }, [isReady, selectedStop?.id, selectedStop?.lat, selectedStop?.lng]);

  useEffect(() => {
    if (!isReady || !kakaoMapRef.current || typeof window === "undefined" || !window.kakao?.maps) {
      return;
    }

    let resizeTimer = 0;
    const handleResize = () => {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(() => {
        if (!kakaoMapRef.current) {
          return;
        }
        forceRoadmap(window.kakao, kakaoMapRef.current);
        fitMapToStops(window.kakao, kakaoMapRef.current, normalizedStops, compact);
        debugKakaoMapDiagnostics("window resize relayout", mapRef.current, kakaoMapRef.current);
      }, 120);
    };

    window.addEventListener("resize", handleResize);
    return () => {
      window.clearTimeout(resizeTimer);
      window.removeEventListener("resize", handleResize);
    };
  }, [isReady, stopPositionKey, compact, normalizedStops]);

  if (!appKey || loadError || (isReady && !isRuntimeConnected)) {
    return (
      <MapFallback
        stops={normalizedStops}
        selectedStop={selectedStop}
        onSelectStop={onSelectStop}
        compact={compact}
        loadError={loadError}
        noCoordinateCount={noCoordinateCount}
        totalStopCount={visibleTotalStopCount}
        coordinateLoading={coordinateLoading}
        coordinateStatusMessage={mapStatusMessage}
      />
    );
  }

  const mapRuntimeStatus = isRuntimeConnected ? "connected" : "loading";

  return (
    <div
      className={`kakao-map-card ${compact ? "compact" : ""} ${className}`}
      data-kakao-route-map="mounted"
      data-map-status={mapRuntimeStatus}
    >
      <div
        className="kakao-map-container"
        ref={mapRef}
        data-kakao-map-container="true"
        style={{ minHeight: compact ? 285 : 430 }}
      />
      {isLoading ? (
        <div className="map-skeleton">
          <strong>지도를 불러오고 있어요</strong>
          <span />
          <span />
        </div>
      ) : null}
      {!compact ? (
        <div className="kakao-map-overlay map-top-left">
          <strong>지도 기반 동선</strong>
          {startLabel ? <span>출발 · {startLabel}</span> : null}
        </div>
      ) : null}
      <div className="kakao-map-overlay map-top-right">
        <MapStateBadge status={mapRuntimeStatus} />
        <strong>{compact ? `${normalizedStops.length}곳` : mapStatusMessage}</strong>
        {!compact && visibleTotalStopCount > 0 ? <span>전체 {visibleTotalStopCount}곳 · 지도 {normalizedStops.length}곳</span> : null}
        {noCoordinateCount > 0 ? <span>좌표 확인 필요 {noCoordinateCount}개</span> : null}
      </div>
      {selectedStop && !compact ? (
        <div className="map-floating-card">
          <div>
            <span className="map-badge">{selectedStop.sequence} · {selectedStop.time || "시간 확인"}</span>
            {getCoordBadge(selectedStop) ? <span className="map-badge muted">{getCoordBadge(selectedStop)}</span> : null}
          </div>
          <strong>{selectedStop.place_name}</strong>
          <p>{selectedStop.district || "서울"} · {selectedStop.place_type}</p>
          {selectedStop.reason ? <small>{selectedStop.reason}</small> : null}
        </div>
      ) : null}
      {!compact ? (
        <div className="map-legend">
          <span><i className="legend-dot orange" />추천 장소</span>
          <span><i className="legend-dot dark" />선택 장소</span>
          <span><i className="legend-dot muted" />좌표 확인 필요</span>
        </div>
      ) : null}
    </div>
  );
}
