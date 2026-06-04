"use client";

// Demo fallback data is only used to keep the route/map demo inspectable when
// the live API or public CSV candidate rows do not include usable coordinates.
// It must not be used by evaluation metrics or ranking calculations.
export const DEMO_FALLBACK_ROUTE_SOURCE = "demo_fallback_route";
export const DEMO_FALLBACK_COORDINATE_SOURCE = "demo_fallback_static";
export const KNOWN_SEOUL_COORDINATE_SOURCE = "known_seoul_static";

export const DEMO_FALLBACK_DISTRICT = "\uc131\ub3d9\uad6c";

export const DEMO_FALLBACK_REQUEST = {
  date: "2026-05-20",
  start_time: "09:00",
  end_time: "18:00",
  start_location: "\uc131\ub3d9\uad6c\uccad",
  districts: [DEMO_FALLBACK_DISTRICT],
  target_voter_group: "\uc9c1\uc7a5\uc778",
  campaign_goal: "\ud1f4\uadfc\uc778\uc0ac",
  preferred_place_types: [
    "\uad50\ud1b5\uac70\uc810",
    "\uace8\ubaa9\uc0c1\uad8c",
    "\uc804\ud1b5\uc2dc\uc7a5",
    "\uacf5\uc6d0",
    "\uc815\ucc45\ud604\uc7a5",
  ],
  num_visits: 5,
  avoid_duplicates: true,
};

export const DEMO_FALLBACK_ROUTE_STOPS = [
  {
    place_name: "\uc655\uc2ed\ub9ac\uc5ed \uad11\uc7a5",
    district: DEMO_FALLBACK_DISTRICT,
    place_type: "\uad50\ud1b5\uac70\uc810",
    address: "\uc11c\uc6b8\ud2b9\ubcc4\uc2dc \uc131\ub3d9\uad6c \uc655\uc2ed\ub9ac\uad11\uc7a5\ub85c 17",
    lat: 37.561268,
    lng: 127.037103,
    time: "09:00",
    estimated_travel_time_from_previous: "0\ubd84",
  },
  {
    place_name: "\uc131\uc218\uc5ed 3\ubc88 \ucd9c\uad6c",
    district: DEMO_FALLBACK_DISTRICT,
    place_type: "\uad50\ud1b5\uac70\uc810",
    address: "\uc11c\uc6b8\ud2b9\ubcc4\uc2dc \uc131\ub3d9\uad6c \uc544\ucc28\uc0b0\ub85c 100",
    lat: 37.54459,
    lng: 127.05596,
    time: "11:00",
    estimated_travel_time_from_previous: "18\ubd84",
  },
  {
    place_name: "\uc11c\uc6b8\uc232 \uc778\uadfc",
    district: DEMO_FALLBACK_DISTRICT,
    place_type: "\uacf5\uc6d0",
    address: "\uc11c\uc6b8\ud2b9\ubcc4\uc2dc \uc131\ub3d9\uad6c \ub69d\uc12c\ub85c 273",
    lat: 37.544388,
    lng: 127.037442,
    time: "13:00",
    estimated_travel_time_from_previous: "16\ubd84",
  },
  {
    place_name: "\ub9c8\uc7a5\ucd95\uc0b0\ubb3c\uc2dc\uc7a5",
    district: DEMO_FALLBACK_DISTRICT,
    place_type: "\uc804\ud1b5\uc2dc\uc7a5",
    address: "\uc11c\uc6b8\ud2b9\ubcc4\uc2dc \uc131\ub3d9\uad6c \ub9c8\uc7a5\ub85c31\uae38 40",
    lat: 37.568693,
    lng: 127.041404,
    time: "15:00",
    estimated_travel_time_from_previous: "15\ubd84",
  },
  {
    place_name: "\uc131\ub3d9\uad6c\uccad \uc778\uadfc",
    district: DEMO_FALLBACK_DISTRICT,
    place_type: "\uc815\ucc45\ud604\uc7a5",
    address: "\uc11c\uc6b8\ud2b9\ubcc4\uc2dc \uc131\ub3d9\uad6c \uace0\uc0b0\uc790\ub85c 270",
    lat: 37.563423,
    lng: 127.036965,
    time: "17:00",
    estimated_travel_time_from_previous: "12\ubd84",
  },
];

const KNOWN_ROUTE_COORDINATES = [
  ...DEMO_FALLBACK_ROUTE_STOPS.map((stop) => ({
    ...stop,
    coordinate_source: DEMO_FALLBACK_COORDINATE_SOURCE,
    coordinate_status: DEMO_FALLBACK_COORDINATE_SOURCE,
    is_demo_fallback_route: true,
  })),
  {
    place_name: "\uc11c\uc6b8\uc232",
    district: DEMO_FALLBACK_DISTRICT,
    lat: 37.544388,
    lng: 127.037442,
    coordinate_source: KNOWN_SEOUL_COORDINATE_SOURCE,
    coordinate_status: KNOWN_SEOUL_COORDINATE_SOURCE,
  },
  {
    place_name: "\uc751\ubd09\uacf5\uc6d0",
    district: DEMO_FALLBACK_DISTRICT,
    lat: 37.548156,
    lng: 127.029776,
    coordinate_source: KNOWN_SEOUL_COORDINATE_SOURCE,
    coordinate_status: KNOWN_SEOUL_COORDINATE_SOURCE,
  },
  {
    place_name: "\uae08\ud638\uadfc\ub9b0\uacf5\uc6d0",
    district: DEMO_FALLBACK_DISTRICT,
    lat: 37.54884,
    lng: 127.0236,
    coordinate_source: KNOWN_SEOUL_COORDINATE_SOURCE,
    coordinate_status: KNOWN_SEOUL_COORDINATE_SOURCE,
  },
  {
    place_name: "\uc7a5\ucda9\uccb4\uc721\uad00",
    district: "\uc911\uad6c",
    lat: 37.558188,
    lng: 127.006751,
    coordinate_source: KNOWN_SEOUL_COORDINATE_SOURCE,
    coordinate_status: KNOWN_SEOUL_COORDINATE_SOURCE,
  },
];

function normalizePlaceKey(value) {
  return String(value || "")
    .replace(/\([^)]*\)/g, "")
    .replace(/\s+/g, "")
    .trim()
    .toLowerCase();
}

function normalizeDistrictKey(value) {
  return String(value || "").replace(/\s+/g, "").trim();
}

const KNOWN_COORDINATE_BY_DISTRICT_AND_NAME = new Map();
const KNOWN_COORDINATE_BY_NAME = new Map();

KNOWN_ROUTE_COORDINATES.forEach((coordinate) => {
  const nameKey = normalizePlaceKey(coordinate.place_name);
  const districtKey = normalizeDistrictKey(coordinate.district);
  if (!nameKey || !Number.isFinite(coordinate.lat) || !Number.isFinite(coordinate.lng)) {
    return;
  }
  KNOWN_COORDINATE_BY_NAME.set(nameKey, coordinate);
  if (districtKey) {
    KNOWN_COORDINATE_BY_DISTRICT_AND_NAME.set(`${districtKey}::${nameKey}`, coordinate);
  }
});

export function getKnownRouteCoordinate(item = {}) {
  const districtKey = normalizeDistrictKey(
    item.district_normalized ||
      item.recommended_district_normalized ||
      item.district ||
      item.recommended_district
  );
  const names = [
    item.place_name,
    item.display_place_name,
    item.raw_place_name,
    item.recommended_place_name,
    item.name,
    item.title,
  ].filter(Boolean);

  for (const name of names) {
    const nameKey = normalizePlaceKey(name);
    const districtMatch = KNOWN_COORDINATE_BY_DISTRICT_AND_NAME.get(`${districtKey}::${nameKey}`);
    if (districtMatch) {
      return districtMatch;
    }
    const nameMatch = KNOWN_COORDINATE_BY_NAME.get(nameKey);
    if (nameMatch && (!districtKey || normalizeDistrictKey(nameMatch.district) === districtKey)) {
      return nameMatch;
    }
  }

  return null;
}

export function hasDemoFallbackDistrict(selectedDistricts = []) {
  const values = Array.isArray(selectedDistricts) ? selectedDistricts : selectedDistricts ? [selectedDistricts] : [];
  if (!values.length) {
    return true;
  }
  return values.map(normalizeDistrictKey).includes(normalizeDistrictKey(DEMO_FALLBACK_DISTRICT));
}

export function buildDemoFallbackRoutePayload(request = {}, meta = {}) {
  const requestedVisits = Number(request.num_visits) || DEMO_FALLBACK_ROUTE_STOPS.length;
  const mergedRequest = {
    ...DEMO_FALLBACK_REQUEST,
    ...request,
    districts: hasDemoFallbackDistrict(request.districts)
      ? [DEMO_FALLBACK_DISTRICT]
      : (Array.isArray(request.districts) ? request.districts : DEMO_FALLBACK_REQUEST.districts),
    num_visits: Math.min(requestedVisits, DEMO_FALLBACK_ROUTE_STOPS.length),
  };
  const timeline = DEMO_FALLBACK_ROUTE_STOPS
    .slice(0, mergedRequest.num_visits)
    .map((stop, index) => ({
      ...stop,
      id: `demo-fallback-route-${index + 1}`,
      order: index + 1,
      sequence: index + 1,
      start_time: stop.time,
      district_normalized: stop.district,
      district_match: true,
      source: DEMO_FALLBACK_ROUTE_SOURCE,
      candidate_source: DEMO_FALLBACK_ROUTE_SOURCE,
      coordinate_status: DEMO_FALLBACK_COORDINATE_SOURCE,
      coordinate_source: DEMO_FALLBACK_COORDINATE_SOURCE,
      is_demo_fallback_route: true,
      is_fallback: false,
      score: Number((2.65 - index * 0.04).toFixed(2)),
      map_position: { lat: stop.lat, lng: stop.lng },
      sequence_reason: "\uc9c0\ub3c4 \uc2dc\uc5f0\uc744 \uc704\ud574 \uc2e4\uc81c \uc11c\uc6b8 \uc88c\ud45c\uac00 \uc788\ub294 \ub370\ubaa8 fallback \uc77c\uc815\uc73c\ub85c \ubd84\ub9ac\ud588\uc2b5\ub2c8\ub2e4.",
      recommendation_reason: "\uc2e4\uc2dc\uac04 API \uc88c\ud45c\uac00 \uc5c6\uc744 \ub54c\ub9cc \uc0ac\uc6a9\ud558\ub294 \uc2dc\uc5f0\uc6a9 \ub3d9\uc120\uc785\ub2c8\ub2e4.",
    }));

  return {
    static_fallback: true,
    demo_fallback: true,
    fallback_message: "\uc2e4\uc2dc\uac04 API \uc5f0\uacb0\uc774 \uc5c6\uc744 \ub54c \uc9c0\ub3c4 \uc2dc\uc5f0\uc744 \uc704\ud574 \ubd84\ub9ac\ub41c \ub370\ubaa8 fallback \ub3d9\uc120\uc744 \ud45c\uc2dc\ud569\ub2c8\ub2e4.",
    request: mergedRequest,
    summary: {
      date: mergedRequest.date,
      start_location: mergedRequest.start_location,
      start_location_district: DEMO_FALLBACK_DISTRICT,
      target_voter_group: mergedRequest.target_voter_group,
      campaign_goal: mergedRequest.campaign_goal,
      num_visits: timeline.length,
      place_type_diversity: new Set(timeline.map((item) => item.place_type)).size,
      model: "static_demo_route",
    },
    timeline,
    insights: [
      "\ub370\ubaa8 fallback \ub3d9\uc120\uc740 \ud504\ub860\ud2b8 \uc2dc\uc5f0 \uc804\uc6a9\uc774\uba70 \ud3c9\uac00 \uc9c0\ud45c \uacc4\uc0b0\uc5d0 \uc0ac\uc6a9\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.",
      "\uc88c\ud45c\uac00 \uc788\ub294 \ub300\ud45c \uc7a5\uc18c\ub9cc marker\ub85c \ud45c\uc2dc\ud569\ub2c8\ub2e4.",
    ],
    debug: {
      source: meta.source || DEMO_FALLBACK_ROUTE_SOURCE,
      selected_districts: [DEMO_FALLBACK_DISTRICT],
      requested_visit_count: requestedVisits,
      returned_count: timeline.length,
      real_candidate_count: timeline.length,
      fallback_candidate_count: 0,
      fallback_used: true,
      fallback_stage: DEMO_FALLBACK_ROUTE_SOURCE,
      coordinate_demo_fallback: true,
      source_counts: { [DEMO_FALLBACK_ROUTE_SOURCE]: timeline.length },
      warnings: [],
    },
    map: {
      mode: "demo_fallback_preview",
      start_location: mergedRequest.start_location,
      start_district: DEMO_FALLBACK_DISTRICT,
    },
  };
}
