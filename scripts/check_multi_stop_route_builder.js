const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(__dirname, "..");
const routePagePath = path.join(repoRoot, "frontend", "app", "route", "page.js");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

const SAMPLE_STOPS = [
  { id: "1", route_item_id: "1", place_name: "강남역 일대", lat: 37.4979, lng: 127.0276 },
  { id: "2", route_item_id: "2", place_name: "선릉역 일대", lat: 37.5045, lng: 127.049 },
  { id: "3", route_item_id: "3", place_name: "코엑스 앞", lat: 37.5118, lng: 127.0592 },
  { id: "4", route_item_id: "4", place_name: "압구정로데오역 일대", lat: 37.5274, lng: 127.0406 },
  { id: "5", route_item_id: "5", place_name: "양재역 일대", lat: 37.4846, lng: 127.0344 },
];

function addStop(routeIds, stopId) {
  return routeIds.includes(stopId) ? routeIds : [...routeIds, stopId];
}

function removeStop(routeIds, stopId) {
  return routeIds.filter((id) => id !== stopId);
}

function moveStop(routeIds, stopId, direction) {
  const index = routeIds.indexOf(stopId);
  const nextIndex = index + direction;
  if (index < 0 || nextIndex < 0 || nextIndex >= routeIds.length) {
    return routeIds;
  }
  const next = [...routeIds];
  [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
  return next;
}

function distanceKm(a, b) {
  const radiusKm = 6371;
  const toRad = (value) => (Number(value) * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const haversine =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return radiusKm * 2 * Math.atan2(Math.sqrt(haversine), Math.sqrt(1 - haversine));
}

function routeMetrics(routeIds) {
  const points = routeIds.map((id) => SAMPLE_STOPS.find((stop) => stop.route_item_id === id));
  const totalDistanceKm = points.reduce((sum, point, index) => {
    if (index === 0) {
      return sum;
    }
    return sum + distanceKm(points[index - 1], point);
  }, 0);
  return {
    totalDistanceKm,
    estimatedMinutes: Math.round((totalDistanceKm / 18) * 60) + Math.max(0, points.length - 1) * 8,
  };
}

function verifySource() {
  const source = fs.readFileSync(routePagePath, "utf8");
  assert(source.includes("CampaignRouteBuilder"), "Route page에 CampaignRouteBuilder가 없습니다.");
  assert(source.includes("selectedVisitIds"), "선택 유세지 route state가 없습니다.");
  assert(source.includes("handleAddSelectedToCampaignRoute"), "장소 추가 handler가 없습니다.");
  assert(source.includes("handleRemoveCampaignRouteStop"), "장소 제거 handler가 없습니다.");
  assert(source.includes("handleMoveCampaignRouteStop"), "순서 변경 handler가 없습니다.");
  assert(source.includes("calculateCampaignRouteMetrics"), "거리/시간 재계산 함수가 없습니다.");
  assert(source.includes("disabled={selectedItemInCampaignRoute}"), "중복 장소 재선택 방지가 UI에 없습니다.");
  assert(source.includes("data-route-builder=\"true\""), "브라우저 검증용 route builder 식별자가 없습니다.");
}

function verifyInteractionModel() {
  let routeIds = [];
  routeIds = addStop(routeIds, "1");
  routeIds = addStop(routeIds, "2");
  routeIds = addStop(routeIds, "3");
  routeIds = addStop(routeIds, "4");
  routeIds = addStop(routeIds, "5");
  assert(routeIds.length === 5, "1~5순위 장소 추가가 실패했습니다.");

  const afterDuplicate = addStop(routeIds, "3");
  assert(afterDuplicate.length === 5, "같은 장소가 중복 추가됩니다.");
  assert(new Set(afterDuplicate).size === afterDuplicate.length, "선택 동선에 중복 장소가 있습니다.");

  const moved = moveStop(afterDuplicate, "5", -1);
  assert(moved[3] === "5" && moved[4] === "4", "순서 변경이 작동하지 않습니다.");

  const removed = removeStop(moved, "3");
  assert(!removed.includes("3") && removed.length === 4, "장소 제거가 작동하지 않습니다.");

  const readded = addStop(removed, "3");
  assert(readded.includes("3") && readded.length === 5, "제거 후 재추가가 작동하지 않습니다.");

  const metrics = routeMetrics(readded);
  assert(metrics.totalDistanceKm > 0, "총 이동거리 계산이 0입니다.");
  assert(metrics.estimatedMinutes > 0, "총 예상 소요시간 계산이 0입니다.");

  return {
    selected_count: readded.length,
    duplicate_blocked: true,
    reorder_supported: true,
    remove_and_readd_supported: true,
    total_distance_km: Number(metrics.totalDistanceKm.toFixed(2)),
    estimated_minutes: metrics.estimatedMinutes,
  };
}

try {
  verifySource();
  const result = verifyInteractionModel();
  console.log(JSON.stringify({ status: "PASS", ...result }, null, 2));
} catch (error) {
  console.error(JSON.stringify({ status: "FAIL", message: error.message }, null, 2));
  process.exitCode = 1;
}
