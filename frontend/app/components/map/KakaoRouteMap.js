"use client";

import { useEffect, useMemo, useRef, useState } from "react";

const SEOUL_CITY_HALL = { lat: 37.5665, lng: 126.978 };
const SDK_SCRIPT_ID = "kakao-map-sdk";
const KAKAO_SDK_BASE_URL = "https://dapi.kakao.com/v2/maps/sdk.js";

export const FALLBACK_COORDS = {
  "성동구청": { lat: 37.5634, lng: 127.0369 },
  "성동구청 앞 광장": { lat: 37.5634, lng: 127.0369 },
  "성수역 3번 출구 앞": { lat: 37.5446, lng: 127.0557 },
  "왕십리역 광장": { lat: 37.5612, lng: 127.0371 },
  "서울숲 입구": { lat: 37.5444, lng: 127.0374 },
  "서울시청": { lat: 37.5665, lng: 126.978 },
  "서울시청 앞 광장": { lat: 37.5665, lng: 126.978 },
  "시청역 5번 출구 앞": { lat: 37.5658, lng: 126.9769 },
  "남대문시장": { lat: 37.5592, lng: 126.9777 },
  "남대문시장 입구": { lat: 37.5592, lng: 126.9777 },
  "동대문종합시장 입구": { lat: 37.57, lng: 127.0089 },
  "약수노인복지관": { lat: 37.5547, lng: 127.0106 },
  "강남역 11번 출구 앞": { lat: 37.498, lng: 127.0276 },
  "서울시립동대문노인종합복지관": { lat: 37.5873, lng: 127.05 },
  "홍대입구역 9번 출구 앞": { lat: 37.5572, lng: 126.9245 },
  "여의도역 5번 출구 앞": { lat: 37.5219, lng: 126.9245 },
  "건대입구역 2번 출구 앞": { lat: 37.5404, lng: 127.0692 },
  "신림역 4번 출구 앞": { lat: 37.4842, lng: 126.9297 },
  "잠실역 8번 출구 앞": { lat: 37.5133, lng: 127.1002 },
};

export const DISTRICT_CENTER_COORDS = {
  "종로구": { lat: 37.5735, lng: 126.9788 },
  "중구": { lat: 37.5636, lng: 126.9976 },
  "용산구": { lat: 37.5384, lng: 126.9654 },
  "성동구": { lat: 37.5634, lng: 127.0369 },
  "광진구": { lat: 37.5384, lng: 127.0823 },
  "동대문구": { lat: 37.5744, lng: 127.0396 },
  "중랑구": { lat: 37.6063, lng: 127.0927 },
  "성북구": { lat: 37.5894, lng: 127.0167 },
  "강북구": { lat: 37.6396, lng: 127.0257 },
  "도봉구": { lat: 37.6688, lng: 127.0471 },
  "노원구": { lat: 37.6542, lng: 127.0568 },
  "은평구": { lat: 37.6027, lng: 126.9291 },
  "서대문구": { lat: 37.5791, lng: 126.9368 },
  "마포구": { lat: 37.5663, lng: 126.9019 },
  "양천구": { lat: 37.5169, lng: 126.8664 },
  "강서구": { lat: 37.5509, lng: 126.8495 },
  "구로구": { lat: 37.4955, lng: 126.8877 },
  "금천구": { lat: 37.4569, lng: 126.8955 },
  "영등포구": { lat: 37.5264, lng: 126.8962 },
  "동작구": { lat: 37.5124, lng: 126.9393 },
  "관악구": { lat: 37.4784, lng: 126.9516 },
  "서초구": { lat: 37.4836, lng: 127.0326 },
  "강남구": { lat: 37.5172, lng: 127.0473 },
  "송파구": { lat: 37.5145, lng: 127.1059 },
  "강동구": { lat: 37.5301, lng: 127.1238 },
};

function isFiniteCoord(value) {
  return Number.isFinite(Number(value));
}

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
  return `${KAKAO_SDK_BASE_URL}?appkey=${encodeURIComponent(normalizeAppKey(appKey))}&autoload=false`;
}

function buildMaskedKakaoSdkSrc(appKey) {
  return `${KAKAO_SDK_BASE_URL}?appkey=${getAppKeyLabel(appKey)}&autoload=false`;
}

function warnKakaoMap(message, details = {}) {
  if (typeof console === "undefined") {
    return;
  }
  console.warn(`[KakaoMap] ${message}`, details);
}

function debugKakaoMap(message, details = {}) {
  if (typeof console === "undefined") {
    return;
  }
  console.debug(`[KakaoMap] ${message}`, details);
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
  if (kakao?.maps?.MapTypeId?.ROADMAP && typeof map?.setMapTypeId === "function") {
    map.setMapTypeId(kakao.maps.MapTypeId.ROADMAP);
  }
}

function getTileDiagnostics(container, map) {
  if (!container || typeof window === "undefined") {
    return {
      innerImgCount: 0,
      tileCandidateCount: 0,
      mapTypeId: getMapTypeId(map),
    };
  }

  const images = Array.from(container.querySelectorAll("img"));
  const tileCandidates = Array.from(container.querySelectorAll("img, div")).filter((element) => {
    const src = element.getAttribute("src") || "";
    const style = window.getComputedStyle(element);
    const backgroundImage = style.backgroundImage || "";
    return /daumcdn|kakao|tile|map/i.test(`${src} ${backgroundImage}`);
  });

  return {
    innerImgCount: images.length,
    tileCandidateCount: tileCandidates.length,
    mapTypeId: getMapTypeId(map),
    containerSize: getContainerMetrics(container),
  };
}

function normalizeCoord(stop) {
  if (isFiniteCoord(stop.lat) && isFiniteCoord(stop.lng)) {
    return {
      lat: Number(stop.lat),
      lng: Number(stop.lng),
      hasExactCoord: true,
      coordSource: "original",
    };
  }

  if (isFiniteCoord(stop.map_position?.lat) && isFiniteCoord(stop.map_position?.lng)) {
    return {
      lat: Number(stop.map_position.lat),
      lng: Number(stop.map_position.lng),
      hasExactCoord: true,
      coordSource: "map_position",
    };
  }

  const placeFallback = FALLBACK_COORDS[stop.place_name] || FALLBACK_COORDS[stop.recommended_place_name];
  if (placeFallback) {
    return {
      ...placeFallback,
      hasExactCoord: false,
      coordSource: "place_fallback",
    };
  }

  const districtFallback = DISTRICT_CENTER_COORDS[stop.district] || DISTRICT_CENTER_COORDS[stop.recommended_district];
  if (districtFallback) {
    return {
      ...districtFallback,
      hasExactCoord: false,
      coordSource: "district_fallback",
    };
  }

  return {
    ...SEOUL_CITY_HALL,
    hasExactCoord: false,
    coordSource: "seoul_fallback",
  };
}

export function normalizeStops(stops = []) {
  return stops.map((stop, index) => {
    const sequence = Number(stop.sequence ?? stop.order ?? stop.rank ?? index + 1) || index + 1;
    const placeName = stop.place_name || stop.recommended_place_name || "장소 확인";
    const district = stop.district || stop.recommended_district || "";
    const placeType = stop.place_type || stop.recommended_place_type || "기타";
    const coord = normalizeCoord({ ...stop, place_name: placeName, district });

    return {
      ...stop,
      id: stop.id || `stop-${sequence}`,
      sequence,
      time: stop.time || stop.start_time || "",
      place_name: placeName,
      district,
      address: stop.address || "",
      place_type: placeType,
      reason: stop.reason || stop.recommendation_reason || stop.sequence_reason || "",
      fit_label: stop.fit_label || "",
      score: stop.score,
      ...coord,
    };
  }).sort((a, b) => a.sequence - b.sequence);
}

function getCoordBadge(stop) {
  if (!stop) {
    return "";
  }
  if (stop.coordSource === "original" || stop.coordSource === "map_position") {
    return "";
  }
  if (stop.coordSource === "district_fallback") {
    return "권역 기준 위치";
  }
  return "좌표 확인 필요";
}

function getMapCenter(stops) {
  if (!stops.length) {
    return SEOUL_CITY_HALL;
  }

  const total = stops.reduce(
    (acc, stop) => ({
      lat: acc.lat + stop.lat,
      lng: acc.lng + stop.lng,
    }),
    { lat: 0, lng: 0 }
  );

  return {
    lat: total.lat / stops.length,
    lng: total.lng / stops.length,
  };
}

function fitMapToStops(kakao, map, stops, compact) {
  forceRoadmap(kakao, map);
  map.relayout();

  if (!stops.length) {
    map.setCenter(new kakao.maps.LatLng(SEOUL_CITY_HALL.lat, SEOUL_CITY_HALL.lng));
    map.setLevel(compact ? 8 : 7);
    return;
  }

  if (stops.length === 1) {
    map.setCenter(new kakao.maps.LatLng(stops[0].lat, stops[0].lng));
    map.setLevel(compact ? 7 : 5);
    return;
  }

  const bounds = new kakao.maps.LatLngBounds();
  stops.forEach((stop) => {
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
    return new Promise((resolve) => {
      window.kakao.maps.load(() => resolve(window.kakao));
    });
  }

  if (window.__kakaoMapSdkPromise) {
    return window.__kakaoMapSdkPromise;
  }

  window.__kakaoMapSdkPromise = new Promise((resolve, reject) => {
    const sdkSrc = buildKakaoSdkSrc(normalizedAppKey);
    const maskedSdkSrc = buildMaskedKakaoSdkSrc(normalizedAppKey);
    let existingScript = document.getElementById(SDK_SCRIPT_ID);

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

      try {
        window.kakao.maps.load(() => {
          if (!window.kakao?.maps?.Map) {
            rejectWithLog(
              "Kakao map SDK loaded but kakao.maps.Map is unavailable",
              new Error("Kakao map SDK loaded but kakao.maps.Map is unavailable")
            );
            return;
          }
          resolve(window.kakao);
        });
      } catch (error) {
        rejectWithLog("Kakao map SDK maps.load failed", error);
      }
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
  element.setAttribute("aria-label", `${stop.sequence}번 ${stop.place_name} 선택`);
  element.innerHTML = `<span>${stop.sequence}</span>`;
  return element;
}

function getFallbackTitle(loadError) {
  if (loadError === "missing-key") {
    return "지도 API 키가 설정되지 않았습니다.";
  }
  if (loadError === "invalid-key") {
    return "지도 API 키 형식이 올바르지 않습니다.";
  }
  if (loadError) {
    return "카카오맵을 불러오지 못해 미리보기 지도로 표시합니다.";
  }
  return "지도 설정 전 미리보기";
}

function MapFallback({ stops, selectedStop, onSelectStop, compact, loadError }) {
  const title = getFallbackTitle(loadError);

  return (
    <div className={`kakao-map-card fallback ${compact ? "compact" : ""}`}>
      <div className="map-skeleton soft">
        <div className="mapToolbar">
          <span className="tag amber">{title}</span>
          <span>{stops.length ? `${stops.length}곳` : "추천 전"}</span>
        </div>
        <div className="fallbackRouteList">
          {stops.length ? stops.map((stop) => (
            <button
              type="button"
              key={stop.id}
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
}) {
  const primaryAppKey = normalizeAppKey(process.env.NEXT_PUBLIC_KAKAO_MAP_API_KEY);
  const legacyAppKey = normalizeAppKey(process.env.NEXT_PUBLIC_KAKAO_MAP_JS_KEY);
  const appKey = isLikelyKakaoAppKey(primaryAppKey)
    ? primaryAppKey
    : isLikelyKakaoAppKey(legacyAppKey)
      ? legacyAppKey
      : "";
  const appKeyIssue = appKey ? "" : (primaryAppKey || legacyAppKey ? "invalid-key" : "missing-key");
  const hasInvalidPrimaryAppKey = Boolean(primaryAppKey && !isLikelyKakaoAppKey(primaryAppKey));
  const mapRef = useRef(null);
  const kakaoMapRef = useRef(null);
  const overlaysRef = useRef([]);
  const polylineRef = useRef(null);
  const [isLoading, setIsLoading] = useState(Boolean(appKey));
  const [isReady, setIsReady] = useState(false);
  const [loadError, setLoadError] = useState("");

  const normalizedStops = useMemo(() => normalizeStops(stops), [stops]);
  const selectedStop = useMemo(
    () => normalizedStops.find((stop) => stop.id === selectedStopId) || normalizedStops[0],
    [normalizedStops, selectedStopId]
  );
  const stopPositionKey = useMemo(
    () => normalizedStops.map((stop) => `${stop.id}:${stop.lat}:${stop.lng}`).join("|"),
    [normalizedStops]
  );

  useEffect(() => {
    if (hasInvalidPrimaryAppKey) {
      warnKakaoMap("NEXT_PUBLIC_KAKAO_MAP_API_KEY looks invalid", {
        appKey: getAppKeyLabel(primaryAppKey),
        expected: "Kakao JavaScript key, not a URL",
        fallback: isLikelyKakaoAppKey(legacyAppKey) ? "NEXT_PUBLIC_KAKAO_MAP_JS_KEY" : "none",
      });
    }

    if (!appKey) {
      warnKakaoMap(appKeyIssue === "invalid-key" ? "Kakao map API key looks invalid" : "Kakao map API key is missing", {
        primary: getAppKeyLabel(primaryAppKey),
        legacy: getAppKeyLabel(legacyAppKey),
      });
      setIsLoading(false);
      setLoadError(appKeyIssue);
      return;
    }

    if (typeof window === "undefined") {
      return;
    }

    if (!mapRef.current) {
      warnKakaoMap("Kakao map container is missing");
      setIsLoading(false);
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
      [0, 240, 900].forEach((delay) => {
        const timer = window.setTimeout(() => {
          if (cancelled || kakaoMapRef.current !== map) {
            return;
          }
          forceRoadmap(window.kakao, map);
          map.relayout();
          debugKakaoMap(label, getTileDiagnostics(container, map));
        }, delay);
        diagnosticTimers.push(timer);
      });
    };

    setIsLoading(true);
    setLoadError("");

    loadKakaoSdk(appKey)
      .then((kakao) => {
        if (cancelled || !mapRef.current) {
          return;
        }

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
            const centerLatLng = new kakao.maps.LatLng(center.lat, center.lng);
            const map = new kakao.maps.Map(container, {
              center: centerLatLng,
              level: 4,
              mapTypeId: kakao.maps.MapTypeId.ROADMAP,
              draggable: !compact,
              scrollwheel: !compact,
            });

            kakaoMapRef.current = map;
            forceRoadmap(kakao, map);
            map.relayout();
            map.setCenter(centerLatLng);

            debugKakaoMap("map created", getTileDiagnostics(container, map));
            scheduleDiagnostics(container, map, "tile diagnostics");

            window.requestAnimationFrame(() => {
              if (!cancelled && kakaoMapRef.current === map) {
                forceRoadmap(kakao, map);
                map.relayout();
                fitMapToStops(kakao, map, normalizedStops, compact);
                debugKakaoMap("post-layout diagnostics", getTileDiagnostics(container, map));
              }
            });

            setIsReady(true);
            setIsLoading(false);
          } catch (error) {
            warnKakaoMap("Kakao map initialization failed", {
              appKey: getAppKeyLabel(appKey),
              error: error?.message || String(error),
              containerSize: getContainerMetrics(mapRef.current),
            });
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
  }, [appKey, appKeyIssue, compact, hasInvalidPrimaryAppKey, legacyAppKey, primaryAppKey]);

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
    debugKakaoMap("map overlay update", {
      normalizedStops: normalizedStops.length,
      markerStops: normalizedStops.length,
      selectedStopId: selectedStop?.id || null,
      ...getTileDiagnostics(mapRef.current, map),
    });

    const relayoutTimer = window.setTimeout(() => {
      if (!kakaoMapRef.current || kakaoMapRef.current !== map) {
        return;
      }
      forceRoadmap(kakao, map);
      map.relayout();
      debugKakaoMap("post-marker relayout", getTileDiagnostics(mapRef.current, map));
    }, 200);

    return () => {
      window.clearTimeout(relayoutTimer);
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
      debugKakaoMap("routeStops relayout", getTileDiagnostics(mapRef.current, map));
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
        debugKakaoMap("window resize relayout", getTileDiagnostics(mapRef.current, kakaoMapRef.current));
      }, 120);
    };

    window.addEventListener("resize", handleResize);
    return () => {
      window.clearTimeout(resizeTimer);
      window.removeEventListener("resize", handleResize);
    };
  }, [isReady, stopPositionKey, compact, normalizedStops]);

  if (!appKey || loadError) {
    return (
      <MapFallback
        stops={normalizedStops}
        selectedStop={selectedStop}
        onSelectStop={onSelectStop}
        compact={compact}
        loadError={loadError}
      />
    );
  }

  return (
    <div className={`kakao-map-card ${compact ? "compact" : ""} ${className}`}>
      <div className="kakao-map-container" ref={mapRef} />
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
        {compact ? `${normalizedStops.length}곳` : `${normalizedStops.length}개 추천 장소`}
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
