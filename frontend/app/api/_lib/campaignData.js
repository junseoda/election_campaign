import fs from "node:fs";
import path from "node:path";

const CWD = process.cwd();
const FRONTEND_ROOT = fs.existsSync(path.join(CWD, "public", "data"))
  ? CWD
  : path.join(CWD, "frontend");
const PROJECT_ROOT = path.basename(FRONTEND_ROOT) === "frontend"
  ? path.resolve(FRONTEND_ROOT, "..")
  : FRONTEND_ROOT;
const PUBLIC_DATA_ROOT = path.join(FRONTEND_ROOT, "public", "data");
const jsonCache = new Map();
const csvCache = new Map();

const KNOWN_DISTRICTS = [
  "강남구", "강동구", "강북구", "강서구", "관악구", "광진구", "구로구", "금천구",
  "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구", "서초구", "성동구",
  "성북구", "송파구", "양천구", "영등포구", "용산구", "은평구", "종로구", "중구", "중랑구",
];

const SEED_PLACES = [
  {
    name: "왕십리역",
    district: "성동구",
    type: "subway",
    address: "서울 성동구 왕십리광장로",
    lat: 37.5613,
    lng: 127.0371,
  },
  {
    name: "성수동 골목상권",
    district: "성동구",
    type: "commercial",
    address: "서울 성동구 성수동 일대",
    lat: 37.5446,
    lng: 127.0557,
  },
  {
    name: "서울숲",
    district: "성동구",
    type: "park",
    address: "서울 성동구 뚝섬로 273",
    lat: 37.5444,
    lng: 127.0374,
  },
  {
    name: "남대문시장",
    district: "중구",
    type: "market",
    address: "서울 중구 남대문시장4길",
    lat: 37.5592,
    lng: 126.9777,
  },
  {
    name: "서울시청 광장",
    district: "중구",
    type: "public",
    address: "서울 중구 세종대로 110",
    lat: 37.5663,
    lng: 126.9779,
  },
  {
    name: "동대문디자인플라자",
    district: "중구",
    type: "public",
    address: "서울 중구 을지로 281",
    lat: 37.5665,
    lng: 127.0092,
  },
];

function projectPath(relativePath) {
  return path.join(PROJECT_ROOT, relativePath);
}

function publicDataPath(fileName) {
  return path.join(PUBLIC_DATA_ROOT, fileName);
}

function firstExisting(paths) {
  return paths.find((filePath) => fs.existsSync(filePath));
}

function readJsonFile(filePath, fallback = {}) {
  const cacheKey = `json:${filePath}`;
  if (jsonCache.has(cacheKey)) {
    return jsonCache.get(cacheKey);
  }
  try {
    const payload = JSON.parse(fs.readFileSync(filePath, "utf8"));
    jsonCache.set(cacheKey, payload);
    return payload;
  } catch (error) {
    jsonCache.set(cacheKey, fallback);
    return fallback;
  }
}

function readRecommendationData() {
  return readJsonFile(publicDataPath("recommendation_results.json"), {});
}

function readRouteData() {
  return readJsonFile(publicDataPath("map_routes.json"), {});
}

function readEvaluationData() {
  return readJsonFile(publicDataPath("evaluation_summary.json"), {});
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let inQuotes = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];
    if (char === '"' && inQuotes && next === '"') {
      cell += '"';
      index += 1;
      continue;
    }
    if (char === '"') {
      inQuotes = !inQuotes;
      continue;
    }
    if (char === "," && !inQuotes) {
      row.push(cell);
      cell = "";
      continue;
    }
    if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && next === "\n") {
        index += 1;
      }
      row.push(cell);
      if (row.some((value) => value !== "")) {
        rows.push(row);
      }
      row = [];
      cell = "";
      continue;
    }
    cell += char;
  }

  row.push(cell);
  if (row.some((value) => value !== "")) {
    rows.push(row);
  }

  if (rows.length < 2) {
    return [];
  }

  const headers = rows[0].map((header) => header.trim());
  return rows.slice(1).map((values) => (
    Object.fromEntries(headers.map((header, index) => [header, coerceCsvValue(values[index])]))
  ));
}

function coerceCsvValue(value) {
  const trimmed = String(value ?? "").trim();
  if (!trimmed) {
    return "";
  }
  if (trimmed === "true") {
    return true;
  }
  if (trimmed === "false") {
    return false;
  }
  const numeric = Number(trimmed);
  return Number.isFinite(numeric) && /^-?\d+(\.\d+)?$/.test(trimmed) ? numeric : trimmed;
}

function readCsvFirst(paths, limit = 500) {
  const filePath = firstExisting(paths);
  if (!filePath) {
    return { rows: [], filePath: null };
  }
  const cacheKey = `csv:${filePath}:${limit}`;
  if (!csvCache.has(cacheKey)) {
    const rows = parseCsv(fs.readFileSync(filePath, "utf8")).slice(0, limit);
    csvCache.set(cacheKey, rows);
  }
  return { rows: csvCache.get(cacheKey), filePath };
}

function cleanPayload(payload) {
  if (Array.isArray(payload)) {
    return payload.map(cleanPayload);
  }
  if (!payload || typeof payload !== "object") {
    return payload;
  }
  const next = {};
  for (const [key, value] of Object.entries(payload)) {
    if (key === "static_fallback" || key === "fallback_message") {
      continue;
    }
    next[key] = cleanPayload(value);
  }
  return next;
}

function toArray(value) {
  if (Array.isArray(value)) {
    return value;
  }
  if (value === undefined || value === null || value === "") {
    return [];
  }
  return [value];
}

function normalizeDistrict(value) {
  const text = String(value || "")
    .replaceAll("서울특별시", "")
    .replaceAll("서울시", "")
    .replaceAll("서울", "")
    .trim();
  if (!text) {
    return "";
  }
  const direct = KNOWN_DISTRICTS.find((district) => text.includes(district));
  if (direct) {
    return direct;
  }
  const compact = text.replace(/\s+/g, "");
  const alias = KNOWN_DISTRICTS.find((district) => compact.includes(district.replace("구", "")));
  return alias || text;
}

function normalizeDistricts(value) {
  const values = toArray(value).flatMap((item) => String(item).split(/[;,]/));
  return [...new Set(values.map(normalizeDistrict).filter(Boolean))];
}

function normalizeType(value) {
  const text = String(value || "").toLowerCase();
  if (/subway|station|역|교통/.test(text)) {
    return "subway";
  }
  if (/market|시장|상권|골목/.test(text)) {
    return "market";
  }
  if (/park|공원|광장/.test(text)) {
    return "park";
  }
  if (/senior|welfare|복지|노인|어르신/.test(text)) {
    return "senior";
  }
  if (/commercial|상업|상가/.test(text)) {
    return "commercial";
  }
  if (/public|policy|정책|청사|구청|시청|현장/.test(text)) {
    return "public";
  }
  return text || "public";
}

function numberOrNull(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function finiteNumber(value, fallback = 0) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

function isOperationalFallbackText(value) {
  return /실시간 API|연결할 수 없어|저장된 추천|저장된 데모|정적 데모|fallback/i.test(String(value || ""));
}

function bounded(value) {
  const numeric = finiteNumber(value, 0);
  if (numeric > 1) {
    return Math.min(1, numeric / 2);
  }
  return Math.max(0, Math.min(1, numeric));
}

function getRecommendationQuery(payload = {}) {
  const data = readRecommendationData();
  const queries = data.queries || [];
  const requestedQueryId = payload.query_id || payload.queryId;
  if (requestedQueryId) {
    const matched = queries.find((query) => query.query_id === requestedQueryId);
    if (matched) {
      return matched;
    }
  }

  const selectedDistricts = normalizeDistricts(payload.districts || payload.district || payload.selectedDistricts);
  const target = String(payload.target || payload.target_voter_group || payload.target_age_group || "").trim();
  const purpose = String(payload.purpose || payload.campaign_goal || payload.place_type || "").trim();
  const time = String(payload.time || payload.time_slot || "").trim();

  const scored = queries.map((query) => {
    let score = 0;
    if (selectedDistricts.length && selectedDistricts.includes(normalizeDistrict(query.district))) {
      score += 10;
    }
    if (target && String(query.target_voter_group || "").includes(target)) {
      score += 3;
    }
    if (purpose && `${query.place_type || ""} ${query.campaign_activity_type || ""}`.includes(purpose)) {
      score += 3;
    }
    if (time && String(query.time || "").startsWith(time.slice(0, 2))) {
      score += 2;
    }
    return { query, score };
  }).sort((a, b) => b.score - a.score);

  return scored[0]?.query || queries[0] || {
    query_id: "seed-query",
    district: selectedDistricts[0] || "성동구",
    time: time || "09:00",
    place_type: purpose || "교통거점",
    target_voter_group: target || "직장인",
  };
}

function recommendationReason(item = {}, query = {}) {
  const fragments = [];
  if (finiteNumber(item.district_bonus) > 0) {
    fragments.push(`${query.district || item.recommended_district} 조건과 일치`);
  }
  if (finiteNumber(item.place_type_bonus) > 0) {
    fragments.push(`${query.place_type || item.recommended_place_type} 목적과 적합`);
  }
  if (finiteNumber(item.time_bonus) > 0) {
    fragments.push(`${query.time || "선택 시간대"} 유동 특성 반영`);
  }
  if (finiteNumber(item.target_bonus) > 0) {
    fragments.push(`${query.target_voter_group || "타깃"} 접촉 가능성 반영`);
  }
  return `${fragments.slice(0, 3).join(" · ") || "서울시 공공데이터 기반 후보지"}. 추천 점수와 피처 기여도를 함께 고려했습니다.`;
}

function itemFeatures(item = {}) {
  return {
    floatingPopulation: bounded(item.rank_bonus ?? item.baseline_score),
    workingPopulation: bounded(item.target_bonus),
    transit: bounded(normalizeType(item.recommended_place_type) === "subway" ? item.place_type_bonus ?? 0.8 : item.time_bonus),
    market: bounded(normalizeType(item.recommended_place_type) === "market" ? item.place_type_bonus ?? 0.8 : item.context_bonus),
    park: bounded(normalizeType(item.recommended_place_type) === "park" ? item.place_type_bonus ?? 0.8 : 0.2),
    senior: bounded(normalizeType(item.recommended_place_type) === "senior" ? item.place_type_bonus ?? 0.8 : item.target_bonus),
  };
}

function recommendationToItem(item = {}, query = {}, index = 0) {
  const name = item.recommended_place_name || item.place_name || item.name || SEED_PLACES[index % SEED_PLACES.length].name;
  const district = normalizeDistrict(item.recommended_district || item.district || query.district) || "서울";
  const type = normalizeType(item.recommended_place_type || item.place_type || query.place_type);
  const lat = numberOrNull(item.lat ?? item.latitude ?? item.map_position?.lat);
  const lng = numberOrNull(item.lng ?? item.longitude ?? item.map_position?.lng);
  const rank = Number(item.rank || index + 1);
  const score = finiteNumber(item.final_variant_score ?? item.score ?? item.baseline_score, 1.0);
  const address = item.address || item.recommended_address || item.location || (query.place_name === name ? query.address : "") || `서울 ${district} ${name}`;

  return {
    ...item,
    id: String(item.id || item.place_id || `${query.query_id || "query"}-${rank}-${name}`),
    name,
    district,
    type,
    score,
    rank,
    reason: recommendationReason(item, query),
    features: itemFeatures(item),
    address,
    lat,
    lng,
    recommended_place_name: name,
    recommended_district: district,
    recommended_place_type: item.recommended_place_type || type,
    final_variant_score: score,
  };
}

function seedRecommendationItems(query = {}, count = 5, existing = []) {
  const used = new Set(existing.map((item) => `${item.name || item.recommended_place_name}|${item.district || item.recommended_district}`));
  const preferredDistrict = normalizeDistrict(query.district) || "성동구";
  const seeds = [
    ...SEED_PLACES.filter((place) => place.district === preferredDistrict),
    ...SEED_PLACES,
  ];
  return seeds
    .filter((place) => !used.has(`${place.name}|${place.district}`))
    .slice(0, count)
    .map((place, index) => recommendationToItem({
      recommended_place_name: place.name,
      recommended_district: place.district,
      recommended_place_type: place.type,
      address: place.address,
      lat: place.lat,
      lng: place.lng,
      rank: existing.length + index + 1,
      score: 1.05 - (index * 0.02),
      baseline_score: 0.6,
      district_bonus: place.district === preferredDistrict ? 1 : 0.45,
      place_type_bonus: 0.8,
      time_bonus: 0.6,
      target_bonus: 0.6,
      context_bonus: 0.5,
    }, query, existing.length + index));
}

export async function getRecommendationResponse(payload = {}) {
  const backend = await tryBackendRecommendation(payload);
  if (backend) {
    return backend;
  }

  const data = readRecommendationData();
  const query = getRecommendationQuery(payload);
  const limit = Math.max(5, Number(payload.limit || payload.top_n || 5));
  const queryId = query.query_id;
  const selectedDistricts = normalizeDistricts(payload.districts || payload.district || payload.selectedDistricts || query.district);
  const matchesDistrict = (item) => !selectedDistricts.length || selectedDistricts.includes(normalizeDistrict(item.recommended_district || item.district));
  let recommendations = (data.optimized_recommendations || [])
    .filter((item) => !queryId || item.query_id === queryId)
    .filter(matchesDistrict)
    .map((item, index) => recommendationToItem(item, query, index));

  if (recommendations.length < limit) {
    const broader = (data.optimized_recommendations || [])
      .filter(matchesDistrict)
      .map((item, index) => recommendationToItem(item, query, index))
      .filter((item) => !recommendations.some((current) => current.id === item.id));
    recommendations = [...recommendations, ...broader].slice(0, limit);
  }
  if (recommendations.length < limit) {
    recommendations = [...recommendations, ...seedRecommendationItems(query, limit - recommendations.length, recommendations)].slice(0, limit);
  }

  return {
    ok: true,
    source: "local-data",
    query,
    items: recommendations.slice(0, limit),
    recommendations: recommendations.slice(0, limit),
    coverage: (data.coverage || []).filter((row) => !queryId || row.query_id === queryId).slice(0, 1),
    hit_analysis: (data.hit_analysis || []).filter((row) => !queryId || row.query_id === queryId).slice(0, 1),
    best_weights: data.best_weights || {},
    message: null,
  };
}

function routeItemToSchedule(item = {}, index = 0) {
  const slot = item.slot || item.time || item.start_time || `${String(9 + index).padStart(2, "0")}:00`;
  const name = item.name || item.place_name || item.recommended_place_name || SEED_PLACES[index % SEED_PLACES.length].name;
  const district = normalizeDistrict(item.district || item.recommended_district) || "서울";
  const type = normalizeType(item.type || item.place_type || item.recommended_place_type);
  const lat = numberOrNull(item.lat ?? item.latitude ?? item.map_position?.lat);
  const lng = numberOrNull(item.lng ?? item.longitude ?? item.map_position?.lng);
  const score = finiteNumber(item.score ?? item.final_variant_score, 1.0);
  const rawReason = item.reason || item.recommendation_reason || item.sequence_reason;
  const reason = rawReason && !isOperationalFallbackText(rawReason)
    ? rawReason
    : `${district} ${name} 방문은 선택 조건과 시간대에 적합합니다.`;

  return {
    ...item,
    id: String(item.id || item.route_item_id || `route-${index + 1}-${name}`),
    order: index + 1,
    sequence: index + 1,
    slot,
    time: slot,
    name,
    place_name: name,
    district,
    type,
    place_type: item.place_type || type,
    reason,
    recommendation_reason: reason,
    sequence_reason: item.sequence_reason || reason,
    address: item.address || `서울 ${district} ${name}`,
    lat,
    lng,
    score,
    has_coordinates: Number.isFinite(lat) && Number.isFinite(lng),
  };
}

function buildRouteFromRecommendations(request = {}, count = 5) {
  const query = getRecommendationQuery(request);
  const data = readRecommendationData();
  const districts = normalizeDistricts(request.districts || request.district || request.selectedDistricts || query.district);
  const selected = districts[0] || normalizeDistrict(query.district) || "성동구";
  const recs = (data.optimized_recommendations || [])
    .filter((item) => normalizeDistrict(item.recommended_district) === selected)
    .slice(0, count)
    .map((item, index) => routeItemToSchedule(recommendationToItem(item, query, index), index));
  if (recs.length >= count) {
    return recs;
  }
  return [
    ...recs,
    ...seedRecommendationItems({ ...query, district: selected }, count - recs.length, recs).map(routeItemToSchedule),
  ].slice(0, count);
}

export async function getRouteResponse(payload = {}) {
  const backend = await tryBackendRoute(payload);
  if (backend) {
    return backend;
  }

  const routeData = readRouteData();
  const options = getRouteOptions();
  const defaultRequest = options.default_request || {};
  const request = {
    ...defaultRequest,
    ...payload,
    num_visits: Math.max(5, Number(payload.num_visits || payload.top_n || defaultRequest.num_visits || 5)),
  };
  const selectedDistricts = normalizeDistricts(request.districts || request.district || request.selectedDistricts);
  const sampleTimeline = (routeData.sample_route?.timeline || []).map(routeItemToSchedule);
  const sampleDistricts = new Set(sampleTimeline.map((item) => normalizeDistrict(item.district)));
  let schedule = sampleTimeline.length >= request.num_visits && (!selectedDistricts.length || selectedDistricts.some((district) => sampleDistricts.has(district)))
    ? sampleTimeline.filter((item) => !selectedDistricts.length || selectedDistricts.includes(normalizeDistrict(item.district)))
    : [];

  if (schedule.length < request.num_visits) {
    schedule = buildRouteFromRecommendations(request, request.num_visits);
  }
  schedule = schedule.slice(0, request.num_visits).map(routeItemToSchedule);
  const markerCount = schedule.filter((item) => Number.isFinite(item.lat) && Number.isFinite(item.lng)).length;
  const missingCoordinateCount = schedule.length - markerCount;
  const startDistrict = selectedDistricts[0] || normalizeDistrict(schedule[0]?.district) || "서울";
  const startName = request.start_location || routeData.sample_route?.summary?.start_location || "서울시청";

  return {
    ok: true,
    source: "local-data",
    start: {
      name: startName,
      district: startDistrict,
    },
    schedule,
    mapStats: {
      recommendedCount: schedule.length,
      markerCount,
      missingCoordinateCount,
    },
    request,
    summary: {
      ...(routeData.sample_route?.summary || {}),
      date: request.date,
      start_location: startName,
      start_location_district: startDistrict,
      target_voter_group: request.target_voter_group || request.target_age_group,
      campaign_goal: request.campaign_goal || request.purpose,
      num_visits: schedule.length,
      model: "next-api-local-data",
    },
    timeline: schedule,
    insights: [
      "Next.js API route에서 내부 정적 데이터와 평가 산출물을 연결했습니다.",
      "좌표가 없는 후보는 marker에서 제외하고 좌표 미확보 수로 계산합니다.",
    ],
    debug: {
      source: "local-data",
      selected_districts: selectedDistricts,
      returned_count: schedule.length,
      marker_count: markerCount,
      missing_coordinate_count: missingCoordinateCount,
    },
  };
}

export function getRouteOptions() {
  const data = readRouteData();
  const rawOptions = cleanPayload(data.route_options || {});
  const districts = (rawOptions.districts || KNOWN_DISTRICTS).filter((district) => KNOWN_DISTRICTS.includes(district));
  return {
    ...rawOptions,
    districts: districts.length ? districts : KNOWN_DISTRICTS,
    target_voter_groups: rawOptions.target_voter_groups || ["직장인", "상인", "지역주민", "노년층", "청년"],
    campaign_goals: rawOptions.campaign_goals || ["출근인사", "시장방문", "정책현장", "공원방문", "복지현장"],
    place_types: rawOptions.place_types || ["교통거점", "전통시장", "공원", "복지시설", "정책현장"],
    default_request: {
      date: "2026-05-20",
      start_time: "09:00",
      end_time: "18:00",
      start_location: "서울시청",
      districts: ["중구"],
      target_voter_group: "직장인",
      campaign_goal: "퇴근인사",
      preferred_place_types: ["교통거점", "전통시장", "정책현장"],
      num_visits: 5,
      avoid_duplicates: true,
      ...(rawOptions.default_request || {}),
      start_location: (rawOptions.default_request?.start_location || "").includes("?") ? "서울시청" : (rawOptions.default_request?.start_location || "서울시청"),
      districts: normalizeDistricts(rawOptions.default_request?.districts || ["중구"]).slice(0, 2),
    },
  };
}

export function getOptimizedQueries(limit = 100) {
  const data = readRecommendationData();
  const queries = data.queries || [];
  return {
    ok: true,
    source: "local-data",
    count: queries.length,
    source_files: data.source_files || {},
    queries: queries.slice(0, limit),
  };
}

export async function getSampleRoute() {
  return getRouteResponse(getRouteOptions().default_request);
}

export function getCoverageDashboard(limit = 12) {
  const data = cleanPayload(readEvaluationData().coverage_dashboard || {});
  return {
    ok: true,
    source: "local-data",
    ...data,
    missing_by_place_type: (data.missing_by_place_type || []).slice(0, limit),
    missing_by_district: (data.missing_by_district || []).slice(0, limit),
    missing_by_campaign_activity_type: (data.missing_by_campaign_activity_type || []).slice(0, limit),
  };
}

export function getEvaluationDashboard() {
  const data = cleanPayload(readEvaluationData().evaluation_dashboard || {});
  return {
    ok: true,
    source: "local-data",
    ...data,
  };
}

function compactSourcePath(filePath) {
  return filePath ? path.relative(PROJECT_ROOT, filePath).replaceAll(path.sep, "/") : null;
}

export function getEvaluationSummary() {
  const evaluationData = readEvaluationData();
  const modelComparisonCsv = readCsvFirst([
    projectPath("output/experiments_all_candidates/optimized/model_comparison_optimized.csv"),
    projectPath("output/experiments_optimized/model_comparison_optimized.csv"),
    projectPath("backend/output/experiments_optimized/model_comparison_optimized.csv"),
    projectPath("output/experiments_all_candidates/model_comparison_optimized.csv"),
  ]);
  const reproducibilityCsv = readCsvFirst([
    projectPath("output/validation/evaluation_metric_reproducibility.csv"),
  ]);
  const goldSetCsv = readCsvFirst([
    projectPath("output/validation/gold_set_validation_summary.csv"),
  ]);
  const aliasCsv = readCsvFirst([
    projectPath("output/validation/alias_ablation_summary.csv"),
  ]);
  const coverageCsv = readCsvFirst([
    projectPath("output/validation/raw_candidate_coverage_with_alias.csv"),
    projectPath("output/experiments_all_candidates/optimized/raw_candidate_coverage.csv"),
    projectPath("backend/output/experiments_optimized/raw_candidate_coverage.csv"),
  ]);

  const evaluationDashboard = getEvaluationDashboard();
  const coverageDashboard = getCoverageDashboard(12);
  const optimizedMetrics = evaluationDashboard.optimized_metrics || {};
  const metrics = reproducibilityCsv.rows.length
    ? reproducibilityCsv.rows
    : Object.entries(optimizedMetrics)
      .filter(([, value]) => Number.isFinite(Number(value)))
      .map(([metric, value]) => ({ metric, value }));

  return {
    ok: true,
    source: "local-data",
    metrics,
    modelComparison: modelComparisonCsv.rows.length ? modelComparisonCsv.rows : (evaluationDashboard.model_comparison || []),
    aliasAblation: aliasCsv.rows,
    goldSetSummary: goldSetCsv.rows.length ? goldSetCsv.rows : [evaluationDashboard.gold_summary || {}].filter((row) => Object.keys(row).length),
    coverage: coverageCsv.rows.length ? coverageCsv.rows : [coverageDashboard.summary || {}].filter((row) => Object.keys(row).length),
    evaluationDashboard,
    coverageDashboard,
    sourceFiles: {
      modelComparison: compactSourcePath(modelComparisonCsv.filePath) || "frontend/public/data/evaluation_summary.json",
      metrics: compactSourcePath(reproducibilityCsv.filePath) || "frontend/public/data/evaluation_summary.json",
      aliasAblation: compactSourcePath(aliasCsv.filePath),
      goldSetSummary: compactSourcePath(goldSetCsv.filePath) || "frontend/public/data/evaluation_summary.json",
      coverage: compactSourcePath(coverageCsv.filePath) || "frontend/public/data/evaluation_summary.json",
    },
  };
}

export function getHealth() {
  const recommendationData = readRecommendationData();
  const routeData = readRouteData();
  const evaluationData = readEvaluationData();
  return {
    ok: true,
    status: "ok",
    service: "campaign-recommender-next-api",
    source: "local-data",
    data: {
      recommendationQueries: recommendationData.queries?.length || 0,
      recommendations: recommendationData.optimized_recommendations?.length || 0,
      routeStops: routeData.sample_route?.timeline?.length || 0,
      modelRows: evaluationData.evaluation_dashboard?.model_comparison?.length || 0,
    },
  };
}

function isLocalUrl(value) {
  try {
    const hostname = new URL(value).hostname.toLowerCase();
    return ["localhost", "127.0.0.1", "::1", "0.0.0.0"].includes(hostname);
  } catch (error) {
    return true;
  }
}

function backendBaseUrl() {
  const configured = (process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "").trim().replace(/\/$/, "");
  if (!configured) {
    return "";
  }
  const productionLike = process.env.VERCEL || process.env.NODE_ENV === "production" || process.env.NEXT_PUBLIC_APP_ENV === "production";
  if (productionLike && isLocalUrl(configured)) {
    return "";
  }
  return configured;
}

async function tryJsonFetch(url, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 2500);
  try {
    const response = await fetch(url, {
      cache: "no-store",
      ...options,
      signal: controller.signal,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(options.headers || {}),
      },
    });
    if (!response.ok) {
      return null;
    }
    return response.json();
  } catch (error) {
    return null;
  } finally {
    clearTimeout(timeout);
  }
}

async function tryBackendRecommendation(payload) {
  const baseUrl = backendBaseUrl();
  if (!baseUrl) {
    return null;
  }
  const backendPayload = await tryJsonFetch(`${baseUrl}/recommend`, {
    method: "POST",
    body: JSON.stringify({
      time_slot: payload.time_slot || "morning",
      place_type: payload.place_type || "market",
      target_age_group: payload.target_age_group || "20_40",
      district: payload.district,
      districts: payload.districts,
      selectedDistricts: payload.selectedDistricts,
      top_n: Math.max(5, Number(payload.limit || payload.top_n || 5)),
    }),
  });
  if (!backendPayload?.places?.length) {
    return null;
  }
  const query = getRecommendationQuery(payload);
  const items = backendPayload.places.map((place, index) => recommendationToItem({
    ...place,
    recommended_place_name: place.name,
    recommended_district: place.district || place.district_name,
    recommended_place_type: place.place_type,
    lat: place.latitude,
    lng: place.longitude,
    rank: index + 1,
  }, query, index));
  return {
    ok: true,
    source: "backend-api",
    query,
    items,
    recommendations: items,
    messages: backendPayload.messages || [],
    message: null,
  };
}

async function tryBackendRoute(payload) {
  const baseUrl = backendBaseUrl();
  if (!baseUrl) {
    return null;
  }
  const backendPayload = await tryJsonFetch(`${baseUrl}/route/recommend`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  const rawItems = backendPayload?.timeline || backendPayload?.route || backendPayload?.items || [];
  if (!rawItems.length) {
    return null;
  }
  const schedule = rawItems.map(routeItemToSchedule);
  const markerCount = schedule.filter((item) => Number.isFinite(item.lat) && Number.isFinite(item.lng)).length;
  return {
    ok: true,
    source: "backend-api",
    start: {
      name: payload.start_location || backendPayload.summary?.start_location || "시작 위치",
      district: normalizeDistrict(payload.district || payload.districts?.[0] || backendPayload.summary?.start_location_district),
    },
    schedule,
    mapStats: {
      recommendedCount: schedule.length,
      markerCount,
      missingCoordinateCount: schedule.length - markerCount,
    },
    ...backendPayload,
    timeline: schedule,
  };
}
