const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(__dirname, "..");

const files = {
  coordinateModule: path.join(repoRoot, "frontend", "app", "components", "camp", "routeCoordinateEnrichment.js"),
  kakaoMap: path.join(repoRoot, "frontend", "app", "components", "map", "KakaoRouteMap.js"),
  routePage: path.join(repoRoot, "frontend", "app", "route", "page.js"),
  backendRouteService: path.join(repoRoot, "backend", "services", "route_service.py"),
};

function read(filePath) {
  return fs.readFileSync(filePath, "utf8");
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

try {
  const coordinateModule = read(files.coordinateModule);
  const kakaoMap = read(files.kakaoMap);
  const routePage = read(files.routePage);
  const backendRouteService = read(files.backendRouteService);

  const forbiddenCoordinateProviders = [
    /FALLBACK_COORDS/,
    /DISTRICT_CENTER_COORDS/,
    /BOROUGH_CENTER_COORDS/,
    /DUMMY_COORDS/,
    /place_fallback/i,
    /seoul_fallback/i,
    /districtCenter/i,
    /centerCoordinates/i,
  ];

  for (const pattern of forbiddenCoordinateProviders) {
    assert(!pattern.test(coordinateModule), `fake coordinate provider found in routeCoordinateEnrichment.js: ${pattern}`);
    assert(!pattern.test(kakaoMap), `fake coordinate provider found in KakaoRouteMap.js: ${pattern}`);
    assert(!pattern.test(routePage), `fake coordinate provider found in route page: ${pattern}`);
  }

  assert(coordinateModule.includes("fallback_coordinate_rejected"), "fallback candidates with coordinates are not explicitly rejected before marker rendering");
  assert(coordinateModule.includes("function hasDisallowedMarkerSource"), "marker eligibility does not block disallowed coordinate sources");
  assert(coordinateModule.includes("!hasDisallowedMarkerSource(item)"), "marker eligibility does not enforce disallowed-source blocking");
  assert(coordinateModule.includes("district_mismatch_geocode_rejected"), "district mismatch geocoding rejection status is missing");
  assert(coordinateModule.includes("COORDINATE_CACHE_VERSION"), "coordinate cache does not include a version");
  assert(coordinateModule.includes("서울 ${district} ${placeName}"), "Kakao keyword search query does not include Seoul and district context");
  assert(!/권역 기준 위치로 표시/.test(backendRouteService), "backend still tells users that missing coordinates are shown with area-level positions");
  assert(/좌표가 없는 후보는 추천 결과와 타임라인에는 유지되며, 지도 marker에서는 제외됩니다/.test(backendRouteService), "backend missing-coordinate warning is not marker-safe");

  console.log(JSON.stringify({
    status: "PASS",
    checked_files: Object.values(files).map((filePath) => path.relative(repoRoot, filePath)),
  }, null, 2));
} catch (error) {
  console.error(JSON.stringify({ status: "FAIL", message: error.message }, null, 2));
  process.exitCode = 1;
}
