"use client";

import { useMemo, useState } from "react";
import {
  AppShell,
  Card,
  EmptyState,
  ErrorState,
  HeroHeader,
  Section,
  Tag,
  getFitLabel,
  postJson,
} from "../components/camp/CampUI";
import KakaoRouteMap from "../components/map/KakaoRouteMap";
import {
  SEOUL_DISTRICTS,
  buildNoCoordinateItemsFromTimeline,
  buildRouteMarkersFromTimeline,
  enrichRouteTimelineCoordinates,
  getCoordinateStatusMessage,
  getCoordinateStatusDetail,
  getCoordinateStatusLabel,
  getItemLatLng,
  hasValidLatLng,
  normalizePlaceName as normalizeDisplayPlaceName,
  normalizeDistrictFromText,
} from "../components/camp/routeCoordinateEnrichment";

const TARGET_GROUPS = ["직장인", "상인", "생활 유권자", "청년", "고령층"];
const CAMPAIGN_GOALS = ["퇴근인사", "지역상권방문", "생활불편청취", "정책홍보"];
const PLACE_TYPES = ["교통거점", "골목상권", "전통시장", "공원", "복지시설"];
const DEFAULT_ACTUAL_CSV = [
  "date,time,district,place_name,address,event_title,candidate_name",
  "2026-06-01,18:00,강남구,강남역 11번 출구,서울 강남구 강남대로,퇴근길 집중 유세,정원오",
  "2026-06-01,19:00,강남구,코엑스 앞,서울 강남구 영동대로,시민 인사,정원오",
].join("\n");

function formatInputDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function addDays(dateValue, days) {
  const base = new Date(`${dateValue}T00:00:00`);
  if (Number.isNaN(base.getTime())) {
    return formatInputDate(new Date());
  }
  base.setDate(base.getDate() + days);
  return formatInputDate(base);
}

function defaultForm() {
  const today = formatInputDate(new Date());
  return {
    forecast_date: today,
    target_date: addDays(today, 2),
    candidate_name: "정원오",
    districts: ["강남구"],
    target_voter_group: "직장인",
    campaign_goal: "퇴근인사",
    preferred_place_types: ["교통거점", "골목상권", "전통시장"],
    top_k: 5,
    random_seed: `${today}-${addDays(today, 2)}-정원오`,
  };
}

function getRouteItems(payload = {}) {
  const candidates = [
    payload.timeline,
    payload.route,
    payload.stops,
    payload.recommendations,
    payload.items,
    payload.data?.timeline,
    payload.data?.route,
    payload.data?.stops,
    payload.data?.items,
  ];
  return candidates.find(Array.isArray) || [];
}

function getFirstValue(...values) {
  return values.find((value) => value !== undefined && value !== null && value !== "") ?? "";
}

function hashString(value) {
  let hash = 2166136261;
  for (const char of String(value)) {
    hash ^= char.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function seededRandom(seed, salt) {
  let value = hashString(`${seed}::${salt}`) || 1;
  value ^= value << 13;
  value ^= value >>> 17;
  value ^= value << 5;
  return ((value >>> 0) % 100000) / 100000;
}

function toggleArrayValue(values, value) {
  return values.includes(value)
    ? values.filter((item) => item !== value)
    : [...values, value];
}

function normalizePlaceName(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/\s+/g, "")
    .replace(/일대|앞|출구|광장|역/g, "");
}

function normalizePredictionItem(item = {}, index = 0, form = {}) {
  const rawPlaceName = getFirstValue(item.place_name, item.recommended_place_name, item.name, item.title, "");
  const district = normalizeDistrictFromText(getFirstValue(
    item.district_normalized,
    item.recommended_district_normalized,
    item.district,
    item.recommended_district
  ));
  const displayPlaceName = normalizeDisplayPlaceName({
    ...item,
    place_name: rawPlaceName,
    district,
    district_normalized: district,
  });
  const placeName = rawPlaceName || displayPlaceName;
  const placeType = getFirstValue(item.place_type, item.recommended_place_type, item.type, "장소 유형");
  const coords = getItemLatLng(item);
  const routeItemId = item.route_item_id || item.id || `prediction-${index + 1}-${district}-${placeName}`.replace(/\s+/g, "-");
  const predictionId = `pred-${form.forecast_date}-${form.target_date}-${hashString(`${routeItemId}-${form.random_seed}`).toString(16)}`;
  const coordinateStatus = hasValidLatLng(coords.lat, coords.lng) ? (item.coordinate_status || "original") : "not_found";

  return {
    ...item,
    id: routeItemId,
    route_item_id: routeItemId,
    prediction_id: predictionId,
    rank: index + 1,
    order: index + 1,
    sequence: index + 1,
    time: item.time || item.start_time || `${String(9 + index * 2).padStart(2, "0")}:00`,
    place_name: placeName,
    raw_place_name: rawPlaceName || placeName,
    display_place_name: displayPlaceName,
    district: district || "자치구 확인",
    district_normalized: district,
    place_type: placeType,
    address: getFirstValue(item.address, item.road_address, item.location, "주소 확인 필요"),
    lat: coords.lat,
    lng: coords.lng,
    score: Number(item.score ?? item.final_score ?? item.final_variant_score ?? 0),
    source: item.source || item.candidate_source || "route_recommendation",
    coordinate_status: coordinateStatus,
    coordinate_source: hasValidLatLng(coords.lat, coords.lng) ? (item.coordinate_source || "original") : "missing",
    coordinate_status_label: getCoordinateStatusLabel(coordinateStatus),
    coordinate_status_detail: getCoordinateStatusDetail(coordinateStatus),
    fit_label: getFitLabel(item.score ?? item.final_score ?? item.final_variant_score),
    explanation: item.explanation || item.reason || item.recommendation_reason || "추천 후보군 상위 장소입니다.",
  };
}

function selectControlledTopK(items, form) {
  const topK = Math.max(1, Number(form.top_k) || 5);
  const poolSize = Math.min(items.length, Math.max(topK, topK * 3));
  return items
    .slice(0, poolSize)
    .map((item, index) => ({
      ...item,
      source_rank: index + 1,
      controlled_random_score: seededRandom(form.random_seed, `${item.place_name}-${index}`),
    }))
    .sort((a, b) => a.controlled_random_score - b.controlled_random_score || Number(b.score || 0) - Number(a.score || 0))
    .slice(0, topK)
    .map((item, index) => ({
      ...item,
      rank: index + 1,
      order: index + 1,
      sequence: index + 1,
      prediction_id: `${item.prediction_id}-${index + 1}`,
    }));
}

function parseActualCsv(csvText) {
  const lines = String(csvText || "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (lines.length < 2) {
    return [];
  }
  const headers = lines[0].split(",").map((header) => header.trim());
  return lines.slice(1).map((line) => {
    const cells = line.split(",").map((cell) => cell.trim());
    return headers.reduce((row, header, index) => {
      row[header] = cells[index] || "";
      return row;
    }, {});
  });
}

function getMatch(rec, actualRows) {
  const recName = normalizePlaceName(rec.display_place_name || rec.place_name);
  const recAddress = normalizePlaceName(`${rec.address || ""} ${rec.kakao_address_name || ""} ${rec.kakao_road_address_name || ""}`);

  let best = { match_type: "no_match", relevance_score: 0, actual: null };
  actualRows.forEach((actual) => {
    const actualName = normalizePlaceName(getFirstValue(actual.place_name, actual.actual_visit_place_name));
    const actualDistrict = normalizeDistrictFromText(getFirstValue(actual.district, actual.actual_visit_district));
    const actualAddress = normalizePlaceName(getFirstValue(actual.address, actual.actual_visit_address));
    let current = { match_type: "no_match", relevance_score: 0, actual };

    if (recName && actualName && recName === actualName) {
      current = { match_type: "exact_place_match", relevance_score: 3, actual };
    } else if (recName && actualName && (recName.includes(actualName) || actualName.includes(recName))) {
      current = { match_type: "alias_match", relevance_score: 3, actual };
    } else if (recAddress && actualAddress && (recAddress.includes(actualAddress) || actualAddress.includes(recAddress))) {
      current = { match_type: "same_address_match", relevance_score: 2, actual };
    } else if (actualDistrict && actualDistrict === rec.district_normalized) {
      current = { match_type: "same_district_place_type_match", relevance_score: 1, actual };
    }

    if (current.relevance_score > best.relevance_score) {
      best = current;
    }
  });

  return best;
}

function evaluatePredictions(predictions, actualRows, form) {
  const filteredActual = actualRows.filter((row) => {
    const actualDate = getFirstValue(row.date, row.actual_visit_date, row.visit_date);
    const sameDate = !actualDate || actualDate === form.target_date;
    const sameCandidate = !row.candidate_name || row.candidate_name === form.candidate_name;
    const district = normalizeDistrictFromText(getFirstValue(row.district, row.actual_visit_district));
    const districtAllowed = !form.districts.length || form.districts.includes(district);
    return sameDate && sameCandidate && districtAllowed;
  });

  const matched = predictions.map((rec) => ({
    ...rec,
    ...getMatch(rec, filteredActual),
  }));
  const topK = Math.max(1, Number(form.top_k) || predictions.length || 1);
  const directMatches = matched.filter((item) => item.relevance_score >= 2);
  const dcg = matched.reduce((sum, item, index) => (
    sum + ((2 ** item.relevance_score - 1) / Math.log2(index + 2))
  ), 0);
  const idealRelevance = matched.map((item) => item.relevance_score).sort((a, b) => b - a);
  const idcg = idealRelevance.reduce((sum, relevance, index) => (
    sum + ((2 ** relevance - 1) / Math.log2(index + 2))
  ), 0);
  const firstDirectMatchIndex = matched.findIndex((item) => item.relevance_score >= 2);

  return {
    actual_count: filteredActual.length,
    hit_at_k: directMatches.length > 0 ? 1 : 0,
    precision_at_k: directMatches.length / topK,
    recall_at_k: filteredActual.length ? Math.min(directMatches.length, filteredActual.length) / filteredActual.length : 0,
    ndcg_at_k: idcg ? dcg / idcg : 0,
    mrr: firstDirectMatchIndex >= 0 ? 1 / (firstDirectMatchIndex + 1) : 0,
    matched_recommendations: matched.filter((item) => item.relevance_score > 0),
    unmatched_recommendations: matched.filter((item) => item.relevance_score === 0),
  };
}

function MetricTile({ label, value }) {
  return (
    <div className="predictionMetricTile">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default function FuturePredictionPage() {
  const [form, setForm] = useState(defaultForm);
  const [predictions, setPredictions] = useState([]);
  const [actualCsv, setActualCsv] = useState(DEFAULT_ACTUAL_CSV);
  const [evaluation, setEvaluation] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [isPredicting, setIsPredicting] = useState(false);
  const [isCoordinateLoading, setIsCoordinateLoading] = useState(false);

  const mapMarkers = useMemo(() => buildRouteMarkersFromTimeline(predictions), [predictions]);
  const noCoordinateItems = useMemo(() => buildNoCoordinateItemsFromTimeline(predictions), [predictions]);
  const coordinateStatusMessage = useMemo(
    () => getCoordinateStatusMessage({
      coordinateLoading: isCoordinateLoading,
      totalCount: predictions.length,
      markerCount: mapMarkers.length,
      noCoordinateCount: noCoordinateItems.length,
    }),
    [isCoordinateLoading, mapMarkers.length, noCoordinateItems.length, predictions.length]
  );

  const updateForm = (key, value) => {
    setForm((current) => {
      const next = { ...current, [key]: value };
      if (key === "forecast_date" || key === "target_date" || key === "candidate_name") {
        next.random_seed = `${next.forecast_date}-${next.target_date}-${next.candidate_name}`;
      }
      return next;
    });
  };

  const runPrediction = async () => {
    try {
      setIsPredicting(true);
      setIsCoordinateLoading(false);
      setErrorMessage("");
      setEvaluation(null);
      setPredictions([]);

      const poolSize = Math.max(Number(form.top_k) * 3, Number(form.top_k));
      const payload = {
        date: form.target_date,
        start_time: "09:00",
        end_time: "20:00",
        start_location: form.districts[0] || "서울",
        districts: form.districts,
        target_voter_group: form.target_voter_group,
        campaign_goal: form.campaign_goal,
        preferred_place_types: form.preferred_place_types,
        num_visits: poolSize,
        visit_count: poolSize,
        avoid_duplicates: true,
      };

      const response = await postJson("/api/route", payload);
      const normalized = getRouteItems(response).map((item, index) => normalizePredictionItem(item, index, form));
      const controlled = selectControlledTopK(normalized, form);
      setIsCoordinateLoading(true);
      const enriched = await enrichRouteTimelineCoordinates(controlled, {
        coordinateSources: getRouteItems(response),
      });
      setPredictions(enriched);
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsCoordinateLoading(false);
      setIsPredicting(false);
    }
  };

  const runEvaluation = () => {
    const actualRows = parseActualCsv(actualCsv);
    setEvaluation(evaluatePredictions(predictions, actualRows, form));
  };

  return (
    <AppShell active="future">
      <HeroHeader
        eyebrow="Prediction Lab"
        title="Future Prediction Lab"
        description="미래 후보 유세 일정 사후 검증 실험. 기존 Gold Set 기반 /evaluation을 대체하지 않고, 실제 일정 공개 이후 추천 결과와 비교하는 별도 실험입니다."
      />

      <div className="predictionWarningBanner" role="note">
        <strong>본 기능은 미래 예측 모델이 아닙니다.</strong>
        <span>실제 후보 일정 공개 후 추천 결과와 비교하는 사후 검증 실험 도구입니다.</span>
      </div>

      {errorMessage ? <ErrorState message={errorMessage} onRetry={runPrediction} /> : null}

      <div className="predictionLabGrid">
        <Card className="predictionPanel">
          <div className="cardHeaderLine">
            <div>
              <Tag tone="amber">예측 설정</Tag>
              <h2>Top-K 생성 조건</h2>
            </div>
            <Tag tone="blue">seeded</Tag>
          </div>
          <div className="formGrid two">
            <label>
              <span>forecast_date</span>
              <input type="date" value={form.forecast_date} onChange={(event) => updateForm("forecast_date", event.target.value)} />
            </label>
            <label>
              <span>target_date</span>
              <input type="date" value={form.target_date} onChange={(event) => updateForm("target_date", event.target.value)} />
            </label>
          </div>
          <div className="formGrid two">
            <label>
              <span>candidate_name</span>
              <input value={form.candidate_name} onChange={(event) => updateForm("candidate_name", event.target.value)} />
            </label>
            <label>
              <span>top_k</span>
              <input type="number" min="1" max="10" value={form.top_k} onChange={(event) => updateForm("top_k", Number(event.target.value))} />
            </label>
          </div>
          <label>
            <span>random_seed</span>
            <input value={form.random_seed} onChange={(event) => updateForm("random_seed", event.target.value)} />
          </label>
          <div className="choiceBlock">
            <span>districts</span>
            <div className="choiceGrid compact">
              {SEOUL_DISTRICTS.map((district) => (
                <button
                  type="button"
                  key={district}
                  className={form.districts.includes(district) ? "active" : ""}
                  onClick={() => updateForm("districts", toggleArrayValue(form.districts, district))}
                >
                  {district}
                </button>
              ))}
            </div>
          </div>
          <div className="formGrid two">
            <label>
              <span>target_voter_group</span>
              <select value={form.target_voter_group} onChange={(event) => updateForm("target_voter_group", event.target.value)}>
                {TARGET_GROUPS.map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <label>
              <span>campaign_goal</span>
              <select value={form.campaign_goal} onChange={(event) => updateForm("campaign_goal", event.target.value)}>
                {CAMPAIGN_GOALS.map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
          </div>
          <div className="choiceBlock">
            <span>preferred_place_types</span>
            <div className="choiceGrid">
              {PLACE_TYPES.map((placeType) => (
                <button
                  type="button"
                  key={placeType}
                  className={form.preferred_place_types.includes(placeType) ? "active" : ""}
                  onClick={() => updateForm("preferred_place_types", toggleArrayValue(form.preferred_place_types, placeType))}
                >
                  {placeType}
                </button>
              ))}
            </div>
          </div>
          <button type="button" className="wideActionButton" disabled={isPredicting || !form.districts.length} onClick={runPrediction}>
            {isPredicting ? "예측 생성 중" : "미래 유세 장소 예측하기"}
          </button>
        </Card>

        <Card className="predictionPanel">
          <div className="cardHeaderLine">
            <div>
              <Tag tone="green">사후 비교</Tag>
              <h2>실제 후보 일정 입력</h2>
            </div>
          </div>
          <p className="helperText">CSV 최소 컬럼: date,time,district,place_name,address,event_title. 실제 일정 데이터가 입력된 이후에만 평가 지표가 의미를 가집니다.</p>
          <textarea
            className="actualScheduleInput"
            value={actualCsv}
            onChange={(event) => setActualCsv(event.target.value)}
            rows={9}
          />
          <button type="button" className="wideActionButton secondary" disabled={!predictions.length} onClick={runEvaluation}>
            실제 일정과 비교 평가하기
          </button>
        </Card>
      </div>

      <Section
        eyebrow="Prediction"
        title="예측 추천 결과"
        description="과거 후보 동선과 현재 추천 시스템을 바탕으로 특정 날짜와 자치구의 Top-K 후보를 생성합니다. 좌표가 없는 후보는 결과에는 포함하고 지도 marker에서만 제외합니다."
      >
        {predictions.length ? (
          <>
            <div className="predictionMapGrid">
              <KakaoRouteMap
                stops={mapMarkers}
                totalStopCount={predictions.length}
                noCoordinateCount={noCoordinateItems.length}
                coordinateLoading={isCoordinateLoading}
                coordinateStatusMessage={coordinateStatusMessage}
                startLabel={form.districts.join(" · ")}
              />
              <Card className="predictionPanel">
                <div className="cardHeaderLine">
                  <Tag tone="blue">좌표 상태</Tag>
                  <strong>{mapMarkers.length}/{predictions.length} 지도 표시</strong>
                </div>
                <ul className="noCoordinateList">
                  {noCoordinateItems.length ? noCoordinateItems.map((item) => (
                    <li key={item.prediction_id || item.route_item_id}>
                      <strong>{item.rank || item.order}번 {item.display_place_name || item.place_name}</strong>
                      <span>{item.district_normalized} · {getCoordinateStatusLabel(item.coordinate_status)}</span>
                      <small>{getCoordinateStatusDetail(item.coordinate_status)}</small>
                    </li>
                  )) : <li>모든 추천 장소가 지도에 표시됩니다.</li>}
                </ul>
              </Card>
            </div>
            <div className="responsiveTableWrap">
              <table className="predictionTable">
                <thead>
                  <tr>
                    <th>rank</th>
                    <th>recommended_place_name</th>
                    <th>district</th>
                    <th>place_type</th>
                    <th>score</th>
                    <th>reason</th>
                    <th>coordinate_status</th>
                    <th>map</th>
                    <th>prediction_id</th>
                  </tr>
                </thead>
                <tbody>
                  {predictions.map((item) => (
                    <tr key={item.prediction_id}>
                      <td>{item.rank}</td>
                      <td>
                        <strong>{item.display_place_name || item.place_name}</strong>
                        {item.raw_place_name && item.raw_place_name !== (item.display_place_name || item.place_name) ? <small className="tableSubText">원본: {item.raw_place_name}</small> : null}
                      </td>
                      <td>{item.district_normalized}</td>
                      <td>{item.place_type}</td>
                      <td>{Number(item.score || 0).toFixed(3)}</td>
                      <td>{item.explanation}</td>
                      <td>{getCoordinateStatusLabel(item.coordinate_status)}</td>
                      <td>{mapMarkers.some((marker) => marker.route_item_id === item.route_item_id) ? "가능" : "좌표 확인 필요"}</td>
                      <td>{item.prediction_id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <EmptyState title="예측 결과가 아직 없습니다" description="예측 설정을 선택한 뒤 Top-K 후보를 생성하세요." />
        )}
      </Section>

      <Section
        eyebrow="Evaluation"
        title="평가 결과"
        description="본 시스템의 정량 평가는 기존 Gold Set 기반 /evaluation에서 수행하고, /future-prediction은 향후 실제 후보 일정이 공개된 뒤 추천 결과와 비교하기 위한 사후 검증 도구로 분리했습니다."
      >
        {evaluation ? (
          <>
            <div className="predictionMetricGrid">
              <MetricTile label="Hit@K" value={evaluation.hit_at_k.toFixed(0)} />
              <MetricTile label="Precision@K" value={evaluation.precision_at_k.toFixed(3)} />
              <MetricTile label="Recall@K" value={evaluation.recall_at_k.toFixed(3)} />
              <MetricTile label="NDCG@K" value={evaluation.ndcg_at_k.toFixed(3)} />
              <MetricTile label="MRR" value={evaluation.mrr.toFixed(3)} />
            </div>
            <div className="predictionListGrid">
              <Card className="predictionPanel">
                <div className="cardHeaderLine">
                  <Tag tone="green">matched place list</Tag>
                  <strong>{evaluation.matched_recommendations.length}개</strong>
                </div>
                <ul className="noCoordinateList">
                  {evaluation.matched_recommendations.length ? evaluation.matched_recommendations.map((item) => (
                    <li key={`matched-${item.prediction_id}`}>
                      <strong>{item.rank}위 {item.display_place_name || item.place_name}</strong>
                      <span>{item.match_type} · relevance {item.relevance_score}</span>
                      <small>{item.actual?.place_name || item.actual?.actual_visit_place_name || "-"}</small>
                    </li>
                  )) : <li>직접 일치 또는 부분 일치한 추천이 없습니다.</li>}
                </ul>
              </Card>
              <Card className="predictionPanel">
                <div className="cardHeaderLine">
                  <Tag tone="amber">unmatched recommendation list</Tag>
                  <strong>{evaluation.unmatched_recommendations.length}개</strong>
                </div>
                <ul className="noCoordinateList">
                  {evaluation.unmatched_recommendations.length ? evaluation.unmatched_recommendations.map((item) => (
                    <li key={`unmatched-${item.prediction_id}`}>
                      <strong>{item.rank}위 {item.display_place_name || item.place_name}</strong>
                      <span>{item.district_normalized} · {item.place_type}</span>
                      <small>입력된 실제 일정과 장소명이 일치하지 않았습니다.</small>
                    </li>
                  )) : <li>모든 추천이 실제 일정과 연결되었습니다.</li>}
                </ul>
              </Card>
            </div>
            <div className="responsiveTableWrap">
              <table className="predictionTable">
                <thead>
                  <tr>
                    <th>rank</th>
                    <th>recommended</th>
                    <th>matched actual</th>
                    <th>match_type</th>
                    <th>relevance_score</th>
                  </tr>
                </thead>
                <tbody>
                  {[...evaluation.matched_recommendations, ...evaluation.unmatched_recommendations].map((item) => (
                    <tr key={`eval-${item.prediction_id}`}>
                      <td>{item.rank}</td>
                      <td>{item.display_place_name || item.place_name}</td>
                      <td>{item.actual?.place_name || item.actual?.actual_visit_place_name || "-"}</td>
                      <td>{item.match_type}</td>
                      <td>{item.relevance_score}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <EmptyState title="비교 평가 전입니다" description="실제 일정 CSV를 붙여넣고 비교 평가를 실행하세요." />
        )}
      </Section>
    </AppShell>
  );
}
