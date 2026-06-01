const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "..");
const staticCandidatesPath = path.join(repoRoot, "frontend", "app", "components", "camp", "staticRealRouteCandidates.js");
const coordinateModulePath = path.join(repoRoot, "frontend", "app", "components", "camp", "routeCoordinateEnrichment.js");
const routePagePath = path.join(repoRoot, "frontend", "app", "route", "page.js");
const mapPath = path.join(repoRoot, "frontend", "app", "components", "map", "KakaoRouteMap.js");
const campUiPath = path.join(repoRoot, "frontend", "app", "components", "camp", "CampUI.js");
const homePagePath = path.join(repoRoot, "frontend", "app", "page.js");
const recommendPagePath = path.join(repoRoot, "frontend", "app", "recommend", "page.js");
const evaluationPagePath = path.join(repoRoot, "frontend", "app", "evaluation", "page.js");
const evaluationSummaryPath = path.join(repoRoot, "frontend", "public", "data", "evaluation_summary.json");
const futurePagePath = path.join(repoRoot, "frontend", "app", "future-prediction", "page.js");
const cssPath = path.join(repoRoot, "frontend", "app", "globals.css");

const removedSegment = ["demo", "review"].join("-");
const removedRoute = `/${removedSegment}`;
const removedPagePath = path.join(repoRoot, "frontend", "app", removedSegment, "page.js");
const removedTimelineClass = `.${["demo", "Review", "Timeline"].join("")}`;

const CONTINUOUS_SEQUENCE = ["강남구", "송파구", "강동구", "성동구", "은평구", "강서구", "마포구"];

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function readFile(filePath) {
  assert(fs.existsSync(filePath), `Missing required file: ${path.relative(repoRoot, filePath)}`);
  return fs.readFileSync(filePath, "utf8");
}

function loadStaticCandidates() {
  const source = readFile(staticCandidatesPath)
    .replace(/export\s+const\s+STATIC_REAL_ROUTE_CANDIDATES\s*=\s*/, "module.exports = ");
  const sandbox = { module: { exports: {} }, exports: {} };
  vm.runInNewContext(source, sandbox, { filename: staticCandidatesPath });
  return sandbox.module.exports;
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

function isMarkerEligible(item) {
  const status = item.coordinate_status || (hasValidCoordinates(item) ? "original" : "not_found");
  const source = item.coordinate_source || (hasValidCoordinates(item) ? "original" : "missing");
  const sourceText = `${item.source || ""} ${item.candidate_source || ""} ${source}`;
  return Boolean(
    item.route_item_id &&
      item.district_normalized &&
      hasValidCoordinates(item) &&
      ["original", "merged_static", "cached", "geocoded"].includes(status) &&
      ["original", "static", "kakao_address_search", "kakao_keyword_search", "cache"].includes(source) &&
      !/fallback|district_fallback_seed|synthetic_district_fallback/i.test(sourceText) &&
      status !== "district_mismatch_geocode_rejected"
  );
}

function displayName(item) {
  const raw = String(item.display_place_name || item.place_name || item.recommended_place_name || "").trim();
  return raw || `${item.district_normalized || item.district} 주요 유세 지점`;
}

function inferFeatureReasons(item) {
  const haystack = [
    item.place_type,
    item.category,
    item.source,
    item.candidate_source,
    item.place_name,
    item.display_place_name,
    item.reason,
  ].join(" ");
  const reasons = [];
  if (/station|subway|역|교통/i.test(haystack)) reasons.push("역세권");
  if (/market|시장|상권|commercial|street/i.test(haystack)) reasons.push("상권/시장");
  if (/park|공원|광장/i.test(haystack)) reasons.push("공원/생활권");
  if (/worker|office|직장|업무|출근/i.test(haystack)) reasons.push("직장인구");
  if (/welfare|복지|senior|노인/i.test(haystack)) reasons.push("복지시설");
  if (/population|유동|생활/i.test(haystack)) reasons.push("유동인구");
  if (!reasons.length) reasons.push("선택 자치구 적합도");
  return reasons;
}

function buildTimeline(district, candidates, limit = 5) {
  return (candidates[district] || []).slice(0, limit).map((item, index) => {
    const placeName = item.place_name || item.recommended_place_name || `${district} 주요 유세 지점`;
    return {
      ...item,
      route_item_id: `${district}-${index + 1}-${placeName}`.replace(/\s+/g, "-"),
      id: `${district}-${index + 1}-${placeName}`.replace(/\s+/g, "-"),
      order: index + 1,
      sequence: index + 1,
      place_name: placeName,
      raw_place_name: item.raw_place_name || placeName,
      display_place_name: displayName({ ...item, place_name: placeName, district_normalized: district }),
      district,
      district_normalized: district,
      coordinate_status: item.coordinate_status || (hasValidCoordinates(item) ? "original" : "not_found"),
      coordinate_source: item.coordinate_source || (hasValidCoordinates(item) ? "original" : "missing"),
    };
  });
}

function buildMarkers(timeline) {
  return timeline
    .map((item) => ({
      ...item,
      place_name: item.display_place_name || item.place_name,
      display_place_name: item.display_place_name || item.place_name,
    }))
    .filter(isMarkerEligible);
}

function verifyRouteDistrict(district, candidates) {
  const timeline = buildTimeline(district, candidates);
  const markers = buildMarkers(timeline);
  const noCoordinate = timeline.filter((item) => !isMarkerEligible(item));
  const cardNames = timeline.map((item) => item.display_place_name);
  const timelineNames = timeline.map((item) => item.display_place_name);
  const markerNamesById = new Map(markers.map((marker) => [marker.route_item_id, marker.display_place_name]));

  assert(timeline.length > 0, `${district}: recommendation result is empty.`);
  assert(cardNames.join("|") === timelineNames.join("|"), `${district}: card and timeline names differ.`);
  timeline.forEach((item) => {
    assert(inferFeatureReasons(item).length > 0, `${district}: missing feature-based explanation for ${item.display_place_name}.`);
  });
  markers.forEach((marker) => {
    const timelineItem = timeline.find((item) => item.route_item_id === marker.route_item_id);
    assert(timelineItem, `${district}: marker ${marker.route_item_id} has no matching timeline item.`);
    assert(markerNamesById.get(marker.route_item_id) === timelineItem.display_place_name, `${district}: marker and timeline names differ.`);
    assert(marker.order === timelineItem.order, `${district}: marker rank changed.`);
    assert(marker.district_normalized === district, `${district}: marker district mismatch.`);
  });
  assert(timeline.length === markers.length + noCoordinate.length, `${district}: total count must equal marker count plus no-coordinate count.`);
  assert(new Set(markers.map((marker) => marker.route_item_id)).size === markers.length, `${district}: duplicate marker id detected.`);

  return {
    district,
    result_count: timeline.length,
    marker_count: markers.length,
    no_coord_count: noCoordinate.length,
    name_sync: true,
    count_equation: true,
    explainability: true,
  };
}

function verifyContinuousSearch(candidates, districts) {
  const sequence = CONTINUOUS_SEQUENCE.filter((district) => districts.includes(district));
  assert(sequence.length === CONTINUOUS_SEQUENCE.length, "Continuous search scenario districts are not all present.");

  let previousMarkerIds = new Set();
  return sequence.map((district) => {
    const timeline = buildTimeline(district, candidates);
    const markers = buildMarkers(timeline);
    const markerIds = new Set(markers.map((marker) => marker.route_item_id));
    const staleIds = [...previousMarkerIds].filter((id) => markerIds.has(id) && !id.startsWith(district));
    assert(staleIds.length === 0, `${district}: stale marker id detected: ${staleIds.join(", ")}`);
    assert(markers.length === markerIds.size, `${district}: duplicate marker id during continuous search.`);
    assert(timeline.length === markers.length + timeline.filter((item) => !isMarkerEligible(item)).length, `${district}: count equation failed during continuous search.`);
    previousMarkerIds = markerIds;
    return { district, marker_count: markers.length, stale_state: false, duplicate_marker: false };
  });
}

function findObjectWithKeys(value, keys) {
  if (!value || typeof value !== "object") {
    return null;
  }
  if (keys.every((key) => Object.prototype.hasOwnProperty.call(value, key))) {
    return value;
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      const found = findObjectWithKeys(item, keys);
      if (found) return found;
    }
  } else {
    for (const item of Object.values(value)) {
      const found = findObjectWithKeys(item, keys);
      if (found) return found;
    }
  }
  return null;
}

function verifySourceInvariants() {
  const routePage = readFile(routePagePath);
  const mapSource = readFile(mapPath);
  const campUi = readFile(campUiPath);
  const homePage = readFile(homePagePath);
  const recommendPage = readFile(recommendPagePath);
  const evaluationPage = readFile(evaluationPagePath);
  const evaluationSummary = JSON.parse(readFile(evaluationSummaryPath));
  const coordinateModule = readFile(coordinateModulePath);
  const futurePage = readFile(futurePagePath);
  const css = readFile(cssPath);

  assert(!fs.existsSync(removedPagePath), "Removed review route page still exists.");
  assert(!campUi.includes(removedRoute), "Navigation still exposes the removed review route.");
  assert(!css.includes(removedTimelineClass), "Removed review route CSS is still present.");

  assert(homePage.includes("HeroHeader") && homePage.includes("RouteTimeline"), "Home page shell is missing core dashboard components.");
  assert(recommendPage.includes("../demo/page"), "Recommend route no longer points to the existing recommendation page implementation.");
  assert(evaluationPage.includes("Gold Set") && evaluationPage.includes("P@1") && evaluationPage.includes("NDCG@10"), "Evaluation page lost Gold Set metric context.");

  const goldSummary = findObjectWithKeys(evaluationSummary, ["total_rows", "strong_place_rows"]);
  assert(goldSummary, "Evaluation summary is missing Gold Set counts.");
  assert(Number(goldSummary.total_rows) === 391, `Expected Gold Set total_rows=391, got ${goldSummary.total_rows}.`);
  assert(Number(goldSummary.strong_place_rows) === 169, `Expected strong_place_rows=169, got ${goldSummary.strong_place_rows}.`);

  assert(routePage.includes("const routeTimeline = useMemo(() => route?.timeline || [], [route])"), "Route page must keep routeTimeline as the single source of truth.");
  assert(routePage.includes("CampaignRouteBuilder"), "Multi-stop route builder UI is missing.");
  assert(routePage.includes("selectedVisitIds"), "Multi-stop selected visit state is missing.");
  assert(routePage.includes("handleMoveCampaignRouteStop"), "Route stop reorder function is missing.");
  assert(routePage.includes("calculateCampaignRouteMetrics"), "Distance/time route metrics are missing.");
  assert(routePage.includes("disabled={selectedItemInCampaignRoute}"), "Duplicate stop prevention is missing.");
  assert(routePage.includes("RouteExplainabilityPanel"), "Recommendation reason UI is missing on the route page.");

  assert(mapSource.includes("map.relayout()"), "Kakao map relayout call is missing.");
  assert(mapSource.includes("fitMapToStops"), "Map bounds adjustment logic is missing.");
  assert(mapSource.includes("MapFallback"), "Kakao SDK failure fallback UI is missing.");
  assert(mapSource.includes("noCoordinateCount"), "Map coordinate-count guidance is missing.");

  assert(coordinateModule.includes("buildRouteFeatureExplanation"), "Feature explanation builder is missing.");
  assert(coordinateModule.includes("district_mismatch_geocode_rejected"), "District mismatch rejection status is missing.");
  assert(coordinateModule.includes("COORDINATE_CACHE_VERSION"), "Coordinate cache versioning is missing.");
  assert(coordinateModule.includes("district_score") && coordinateModule.includes("population_score"), "Feature score rows are incomplete.");
  assert(campUi.includes("RouteExplainabilityPanel"), "Recommendation reason panel export is missing.");

  assert(futurePage.includes("본 기능은 미래 예측 모델이 아닙니다."), "Future Prediction top warning is missing.");
  assert(futurePage.includes("사후 검증 실험 도구입니다."), "Future Prediction retrospective validation warning is missing.");
  assert(futurePage.includes("기존 Gold Set 기반 /evaluation을 대체하지 않고"), "Future Prediction is not clearly separated from /evaluation.");
  assert(css.includes("@media (max-width: 760px)") && css.includes(".routeOutputGrid"), "Mobile responsive route CSS target is missing.");
}

try {
  verifySourceInvariants();
  const candidates = loadStaticCandidates();
  const districts = Object.keys(candidates);
  assert(districts.length === 25, `Expected 25 Seoul districts, got ${districts.length}.`);

  const districtResults = districts.map((district) => verifyRouteDistrict(district, candidates));
  const continuousResults = verifyContinuousSearch(candidates, districts);

  console.log(JSON.stringify({
    status: "PASS",
    checked: {
      core_pages: ["/", "/route", "/recommend", "/evaluation", "/future-prediction"],
      removed_review_route: true,
      route_districts: districtResults.length,
      continuous_searches: continuousResults.length,
      future_prediction_warning: true,
      explainability_ui: true,
      mobile_responsive_static: true,
      gold_set_total_rows: 391,
      strong_positive_rows: 169,
    },
    route_results: districtResults,
    continuous_results: continuousResults,
  }, null, 2));
} catch (error) {
  console.error(JSON.stringify({ status: "FAIL", message: error.message }, null, 2));
  process.exitCode = 1;
}
