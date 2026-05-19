"use client";

const NAV_ITEMS = [
  { key: "home", label: "홈", href: "/", caption: "운영 홈" },
  { key: "route", label: "동선", href: "/route", caption: "하루 일정" },
  { key: "recommend", label: "추천", href: "/recommend", caption: "장소 추천" },
  { key: "map", label: "지도", href: "/map", caption: "동선 미리보기" },
  { key: "evaluation", label: "평가", href: "/evaluation", caption: "추천 품질 확인" },
];

const ACTIVITY_BY_TYPE = {
  교통거점: "출퇴근 인사",
  전통시장: "상권 방문",
  골목상권: "상권 방문",
  복지시설: "복지시설 방문",
  공원: "생활권 인사",
  정책현장: "정책 현장 방문",
  체육시설: "생활체육 현장",
};

const PLACE_TYPE_LABELS = {
  subway: "교통거점",
  station: "교통거점",
  market: "전통시장",
  traditional_market: "전통시장",
  senior_welfare: "복지시설",
  welfare: "복지시설",
  park: "공원",
  policy_site: "정책현장",
  sports: "체육시설",
};

const SCORE_ROWS = [
  ["optimized_place_score", "장소 기본점"],
  ["time_slot_fit_score", "시간대 보정"],
  ["target_voter_fit_score", "타깃 보정"],
  ["district_fit_score", "자치구 보정"],
  ["start_location_fit_score", "출발지 보정"],
  ["diversity_bonus", "다양성 보정"],
  ["duplicate_visit_penalty", "중복 방문"],
  ["travel_distance_penalty", "이동 부담"],
];

const RECOMMEND_SCORE_ROWS = [
  ["baseline_score", "기본 점수"],
  ["district_bonus", "자치구 보정"],
  ["place_type_bonus", "장소 유형 보정"],
  ["time_bonus", "시간대 보정"],
  ["context_bonus", "문맥 보정"],
  ["target_bonus", "타깃 보정"],
  ["rank_bonus", "순위 보정"],
];

export function formatNumber(value) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) {
    return "확인 필요";
  }
  return numericValue.toLocaleString("ko-KR");
}

export function formatMetric(value, digits = 4) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) {
    return "확인 필요";
  }
  return numericValue.toFixed(digits);
}

export function formatPercent(value, digits = 1) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) {
    return "확인 필요";
  }
  return `${(numericValue * 100).toFixed(digits)}%`;
}

export function getFitLabel(score) {
  const numericScore = Number(score);
  if (!Number.isFinite(numericScore)) {
    return "적합도 확인";
  }
  if (numericScore >= 2.7) {
    return "적합도 높음";
  }
  if (numericScore >= 2.3) {
    return "적합도 보통";
  }
  return "보조 후보";
}

export function getActivityType(item = {}) {
  return item.campaign_activity_type || ACTIVITY_BY_TYPE[item.place_type] || "현장 방문";
}

export function getPlaceTypeLabel(value) {
  return PLACE_TYPE_LABELS[value] || value || "장소 유형";
}

export function getTargetLabel(item = {}) {
  return item.target_voter_group || item.target || "생활 유권자";
}

export function getTimeRange(timeValue, minutes = 35) {
  const [hour, minute] = String(timeValue || "09:00").split(":").map((part) => Number(part));
  if (!Number.isFinite(hour) || !Number.isFinite(minute)) {
    return timeValue || "시간 확인";
  }
  const start = (hour * 60) + minute;
  const end = Math.min((23 * 60) + 59, start + minutes);
  const format = (value) => `${String(Math.floor(value / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`;
  return `${format(start)} - ${format(end)}`;
}

export function buildShortReason(item = {}) {
  const placeType = item.place_type || "현장";
  const target = getTargetLabel(item);
  const time = String(item.time || "");

  if (placeType === "교통거점") {
    return time < "12:00" ? "출근길 생활·교통 불편을 듣기 좋은 지점입니다." : "퇴근길 유동 인구와 만나는 지점입니다.";
  }
  if (placeType === "전통시장" || placeType === "골목상권") {
    return `${target}과 상권 이야기를 나누기 좋은 동선입니다.`;
  }
  if (placeType === "복지시설") {
    return "돌봄·복지 메시지를 현장에서 확인하기 좋습니다.";
  }
  if (placeType === "공원") {
    return "생활권 주민과 짧게 인사하기 좋은 열린 공간입니다.";
  }
  return item.recommendation_reason || "시간대와 지역 조건에 맞는 후보지입니다.";
}

export function buildChecklist(item = {}) {
  const type = item.place_type || "";
  if (type === "교통거점") {
    return ["명함", "피켓", "촬영 인력"];
  }
  if (type === "전통시장" || type === "골목상권") {
    return ["명함", "상인 간담 메모", "동행 인력"];
  }
  if (type === "복지시설") {
    return ["방문 확인", "정책자료", "소규모 인원"];
  }
  return ["명함", "현수막", "촬영 인력"];
}

export function getStopId(item = {}, index = 0) {
  return item.id || `stop-${item.sequence || item.order || index + 1}`;
}

export const STATIC_DEMO_MESSAGE = "실시간 API 서버에 연결할 수 없어 저장된 데모 데이터를 표시합니다.";

const API_TIMEOUT_MS = 10000;
const STATIC_DATA_CACHE = {};

function getApiBaseUrl() {
  return (process.env.NEXT_PUBLIC_API_BASE_URL || "").trim();
}

function isLocalApiUrl(apiBaseUrl) {
  if (!apiBaseUrl) {
    return true;
  }

  try {
    const hostname = new URL(apiBaseUrl).hostname.toLowerCase();
    return ["localhost", "127.0.0.1", "::1", "0.0.0.0"].includes(hostname);
  } catch (error) {
    return true;
  }
}

function shouldUseStaticFallback(apiBaseUrl) {
  return !apiBaseUrl || isLocalApiUrl(apiBaseUrl);
}

async function loadStaticData(fileName) {
  if (!STATIC_DATA_CACHE[fileName]) {
    STATIC_DATA_CACHE[fileName] = fetch(`/data/${fileName}`, { cache: "force-cache" }).then((response) => {
      if (!response.ok) {
        throw new Error(STATIC_DEMO_MESSAGE);
      }
      return response.json();
    });
  }

  return STATIC_DATA_CACHE[fileName];
}

function cloneStaticPayload(payload) {
  return JSON.parse(JSON.stringify(payload));
}

function getRequestUrl(path) {
  return new URL(path, "https://static.local");
}

function getLimit(url, fallback = 10) {
  const parsed = Number(url.searchParams.get("limit"));
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function parseRequestBody(body) {
  if (!body) {
    return {};
  }
  if (typeof body === "string") {
    try {
      return JSON.parse(body);
    } catch (error) {
      return {};
    }
  }
  if (typeof body === "object") {
    return body;
  }
  return {};
}

function withStaticMeta(payload) {
  return {
    ...payload,
    static_fallback: true,
    fallback_message: STATIC_DEMO_MESSAGE,
  };
}

async function getOptimizedFallback(path) {
  const url = getRequestUrl(path);
  const data = await loadStaticData("recommendation_results.json");

  if (url.pathname === "/optimized/queries") {
    const limit = getLimit(url, data.queries?.length || 100);
    return withStaticMeta({
      count: data.count || data.queries?.length || 0,
      source_files: data.source_files || {},
      queries: (data.queries || []).slice(0, limit),
    });
  }

  if (url.pathname === "/optimized/recommendations") {
    const limit = getLimit(url, 10);
    const requestedQueryId = url.searchParams.get("query_id");
    const query =
      (data.queries || []).find((item) => item.query_id === requestedQueryId) ||
      (data.queries || [])[0] ||
      {};
    const queryId = query.query_id || requestedQueryId;
    const recommendations = (data.optimized_recommendations || [])
      .filter((item) => !queryId || item.query_id === queryId)
      .slice(0, limit);
    const coverage = (data.coverage || []).filter((item) => !queryId || item.query_id === queryId).slice(0, 1);
    const hitAnalysis = (data.hit_analysis || []).filter((item) => !queryId || item.query_id === queryId).slice(0, 1);

    return withStaticMeta({
      model_name: "optimized_proposed_static",
      query,
      recommendations,
      coverage,
      hit_analysis: hitAnalysis,
      best_weights: data.best_weights || {},
      source_files: data.source_files || {},
    });
  }

  return null;
}

async function getRouteFallback(path, body) {
  const url = getRequestUrl(path);
  const data = await loadStaticData("map_routes.json");

  if (url.pathname === "/route/options") {
    return withStaticMeta(cloneStaticPayload(data.route_options || {}));
  }

  if (url.pathname === "/route/sample") {
    return withStaticMeta(cloneStaticPayload(data.sample_route || {}));
  }

  if (url.pathname === "/route/recommend") {
    const request = parseRequestBody(body);
    const route = cloneStaticPayload(data.sample_route || {});
    const requestedVisits = Number(request.num_visits) || route.timeline?.length || 5;
    const timeline = (route.timeline || [])
      .slice(0, requestedVisits)
      .map((item, index) => ({ ...item, order: index + 1 }));

    return withStaticMeta({
      ...route,
      request: {
        ...(route.request || {}),
        ...request,
        num_visits: timeline.length,
      },
      summary: {
        ...(route.summary || {}),
        date: request.date || route.summary?.date,
        start_location: request.start_location || route.summary?.start_location,
        target_voter_group: request.target_voter_group || route.summary?.target_voter_group,
        campaign_goal: request.campaign_goal || route.summary?.campaign_goal,
        num_visits: timeline.length,
        model: "static_demo_route",
      },
      timeline,
      insights: [
        "현재 정적 데모 모드로 실행 중입니다.",
        ...((route.insights || []).slice(0, 2)),
      ],
    });
  }

  return null;
}

async function getEvaluationFallback(path) {
  const url = getRequestUrl(path);
  const data = await loadStaticData("evaluation_summary.json");

  if (url.pathname === "/evaluation/dashboard") {
    return withStaticMeta(cloneStaticPayload(data.evaluation_dashboard || {}));
  }

  if (url.pathname === "/coverage/dashboard") {
    const limit = getLimit(url, 12);
    const coverage = cloneStaticPayload(data.coverage_dashboard || {});
    coverage.missing_by_place_type = (coverage.missing_by_place_type || []).slice(0, limit);
    coverage.missing_by_district = (coverage.missing_by_district || []).slice(0, limit);
    coverage.missing_by_campaign_activity_type = (coverage.missing_by_campaign_activity_type || []).slice(0, limit);
    return withStaticMeta(coverage);
  }

  return null;
}

async function getStaticFallback(path, body) {
  const url = getRequestUrl(path);

  if (url.pathname.startsWith("/optimized/")) {
    return getOptimizedFallback(path);
  }
  if (url.pathname.startsWith("/route/")) {
    return getRouteFallback(path, body);
  }
  if (url.pathname === "/evaluation/dashboard" || url.pathname === "/coverage/dashboard") {
    return getEvaluationFallback(path);
  }

  return null;
}

async function tryStaticFallback(path, body) {
  try {
    return await getStaticFallback(path, body);
  } catch (error) {
    return null;
  }
}

export async function fetchJson(path, options = {}) {
  const apiBaseUrl = getApiBaseUrl();

  if (shouldUseStaticFallback(apiBaseUrl)) {
    const staticPayload = await tryStaticFallback(path, options.body);
    if (staticPayload) {
      return staticPayload;
    }
    throw new Error(STATIC_DEMO_MESSAGE);
  }

  let response;
  const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
  const timeoutId = controller ? globalThis.setTimeout(() => controller.abort(), API_TIMEOUT_MS) : null;

  try {
    response = await fetch(`${apiBaseUrl.replace(/\/$/, "")}${path}`, {
      cache: "no-store",
      ...options,
      signal: controller?.signal || options.signal,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(options.headers || {}),
      },
    });
  } catch (error) {
    const staticPayload = await tryStaticFallback(path, options.body);
    if (staticPayload) {
      return staticPayload;
    }
    throw new Error(STATIC_DEMO_MESSAGE);
  } finally {
    if (timeoutId) {
      globalThis.clearTimeout(timeoutId);
    }
  }

  if (!response.ok) {
    const staticPayload = await tryStaticFallback(path, options.body);
    if (staticPayload) {
      return staticPayload;
    }
    if (response.status === 404) {
      throw new Error("필요한 데이터 파일을 찾을 수 없습니다.");
    }
    throw new Error(`${path} 요청 실패 (${response.status})`);
  }

  return response.json();
}

export async function postJson(path, payload) {
  return fetchJson(path, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function AppShell({ active = "home", children }) {
  return (
    <main className="appShell">
      <aside className="desktopSidebar" aria-label="선거비서 AI 데스크톱 내비게이션">
        <a href="/" className="brandLockup" aria-label="선거비서 AI 홈">
          <span className="brandMark">AI</span>
          <span>
            <strong>선거비서 AI</strong>
            <small>현장 운영 보조</small>
          </span>
        </a>
        <nav className="sidebarNav">
          {NAV_ITEMS.map((item) => (
            <a key={item.key} href={item.href} className={active === item.key ? "active" : ""}>
              <span>{item.label}</span>
              <small>{item.caption}</small>
            </a>
          ))}
        </nav>
        <div className="sidebarNote">
          <span>운영 + 평가</span>
          <strong>후보자용 운영 화면과 추천 품질 평가를 함께 제공합니다.</strong>
          <p>동선 추천은 실제 후보 일정 데이터를 참고하고, 평가 수치는 별도 대시보드에서 확인합니다.</p>
        </div>
      </aside>
      <div className="appContent">{children}</div>
      <BottomNavigation active={active} />
    </main>
  );
}

export function BottomNavigation({ active }) {
  return (
    <nav className="bottomNav" aria-label="선거비서 AI 하단 내비게이션">
      {NAV_ITEMS.map((item) => (
        <a key={item.key} href={item.href} className={active === item.key ? "active" : ""}>
          <span className="navGlyph" aria-hidden="true" />
          <span>{item.label}</span>
        </a>
      ))}
    </nav>
  );
}

export function HeroHeader({ eyebrow, title, description, primaryAction, secondaryAction, meta }) {
  return (
    <header className="heroHeader">
      <div>
        {eyebrow ? <span className="eyebrowLabel">{eyebrow}</span> : null}
        <h1>{title}</h1>
        {description ? <p>{description}</p> : null}
        {(primaryAction || secondaryAction) ? (
          <div className="heroActions">
            {primaryAction}
            {secondaryAction}
          </div>
        ) : null}
      </div>
      {meta ? <div className="heroMeta">{meta}</div> : null}
    </header>
  );
}

export function HeroMetricStack({ metrics = [] }) {
  return (
    <div className="heroMetricStack" aria-label="핵심 운영 요약">
      {metrics.map((metric) => (
        <div key={metric.label}>
          <span>{metric.label}</span>
          <strong>{metric.value}</strong>
          {metric.caption ? <small>{metric.caption}</small> : null}
        </div>
      ))}
    </div>
  );
}

export function Section({ eyebrow, title, description, action, children, className = "" }) {
  return (
    <section className={`sectionBlock ${className}`}>
      <SectionHeader eyebrow={eyebrow} title={title} description={description} action={action} />
      {children}
    </section>
  );
}

export function SectionHeader({ eyebrow, title, description, action }) {
  return (
    <div className="sectionHeader">
      <div>
        {eyebrow ? <span>{eyebrow}</span> : null}
        <h2>{title}</h2>
        {description ? <p>{description}</p> : null}
      </div>
      {action ? <div className="sectionAction">{action}</div> : null}
    </div>
  );
}

export function Card({ className = "", children, ...props }) {
  return <section className={`card ${className}`} {...props}>{children}</section>;
}

export function Tag({ tone = "neutral", children }) {
  return <span className={`tag ${tone}`}>{children}</span>;
}

export const Pill = Tag;

export function ButtonLink({ href, variant = "primary", children }) {
  return (
    <a href={href} className={`buttonLink ${variant}`}>
      {children}
    </a>
  );
}

export function MetricCard({ label, value, caption, delta, tone = "neutral", emphasis = false }) {
  return (
    <Card className={`metricCard ${tone} ${emphasis ? "emphasis" : ""}`}>
      <div className="metricTop">
        <span>{label}</span>
        {delta ? <em>{delta}</em> : null}
      </div>
      <strong>{value}</strong>
      {caption ? <small>{caption}</small> : null}
    </Card>
  );
}

export function StatCard(props) {
  return <MetricCard {...props} />;
}

export function InsightCard({ eyebrow = "Insight", title, description, tone = "amber", children }) {
  return (
    <Card className={`insightCard ${tone}`}>
      <Tag tone={tone}>{eyebrow}</Tag>
      <h2>{title}</h2>
      {description ? <p>{description}</p> : null}
      {children}
    </Card>
  );
}

export function LoadingState({ title = "추천 데이터를 준비하고 있어요", lines = 3 }) {
  return (
    <div className="statePanel" role="status" aria-live="polite">
      <strong>{title}</strong>
      <div className="skeletonStack">
        {Array.from({ length: lines }).map((_, index) => (
          <span key={index} />
        ))}
      </div>
    </div>
  );
}

export function ErrorState({ title = "데이터를 불러오지 못했습니다", message, onRetry }) {
  return (
    <div className="statePanel error" role="alert">
      <strong>{title}</strong>
      <p>{message || STATIC_DEMO_MESSAGE}</p>
      {onRetry ? (
        <button type="button" onClick={onRetry}>
          다시 시도
        </button>
      ) : null}
    </div>
  );
}

export function EmptyState({ title = "표시할 데이터가 없습니다", message }) {
  return (
    <div className="statePanel empty">
      <strong>{title}</strong>
      {message ? <p>{message}</p> : null}
    </div>
  );
}

export function NextRecommendationCard({ query, recommendation }) {
  const placeName = recommendation?.recommended_place_name || query?.place_name || "추천 장소 없음";
  const district = recommendation?.recommended_district || query?.district || "자치구 확인";
  const placeType = getPlaceTypeLabel(recommendation?.recommended_place_type || query?.place_type);

  return (
    <Card className="nextRecommendationCard">
      <div className="cardHeaderLine">
        <Tag tone="amber">다음 추천</Tag>
        <span>{query?.time || "시간 확인"}</span>
      </div>
      <h2>{placeName}</h2>
      <p>{district} · {placeType}</p>
      <div className="recommendationMeta">
        <span>
          적합도
          <strong>{getFitLabel(recommendation?.score)}</strong>
        </span>
        <span>
          모델
          <strong>최적화 모델</strong>
        </span>
      </div>
    </Card>
  );
}

export function WeeklyActivityChart({ data = [] }) {
  const maxValue = Math.max(...data.map((item) => Number(item.value) || 0), 1);

  if (!data.length) {
    return <EmptyState title="주간 활동 데이터가 없습니다" />;
  }

  return (
    <Card className="weeklyChartCard">
      <SectionHeader title="주간 활동" description="검증 일정의 요일별 방문 흐름입니다." />
      <div className="barChart" aria-label="주간 활동 막대 차트">
        {data.map((item) => {
          const height = Math.max(16, ((Number(item.value) || 0) / maxValue) * 96);
          return (
            <div key={item.label} className={item.active ? "active" : ""}>
              <span style={{ height: `${height}px` }} />
              <small>{item.label}</small>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

export function ScheduleTimeline({ items = [] }) {
  if (!items.length) {
    return <EmptyState title="일정 데이터가 없습니다" message="검증 일정 CSV를 확인해주세요." />;
  }

  return (
    <div className="timelineList">
      {items.map((item) => (
        <article key={item.query_id} className="timelineItem">
          <time>{item.time}</time>
          <div>
            <h3>{item.place_name}</h3>
            <p>{item.district} · {item.place_type}</p>
            <div className="chipRow">
              <Tag>{item.campaign_activity_type}</Tag>
              <Tag tone="blue">{item.target_voter_group || "타깃 확인"}</Tag>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}

export function MiniMapCard({ points = [] }) {
  const positions = [
    ["16%", "60%"],
    ["34%", "45%"],
    ["54%", "34%"],
    ["68%", "58%"],
    ["45%", "73%"],
    ["79%", "31%"],
  ];

  return (
    <Card className="mapPreviewCard">
      <div className="mapToolbar">
        <Tag tone="amber">동선 지도 미리보기</Tag>
        <span>지도 기반 위치 확인</span>
      </div>
      <div className="mapCanvas" aria-label="서울 유세 장소 분포 미리보기">
        <div className="mapRiver" />
        <div className="mapRoad roadA" />
        <div className="mapRoad roadB" />
        <div className="mapRoute" />
        <span className="mapLabel labelA">영등포</span>
        <span className="mapLabel labelB">중구</span>
        <span className="mapLabel labelC">성동</span>
        {positions.map(([left, top], index) => (
          <span key={`${left}-${top}`} className={`clusterMarker ${index === 0 ? "selected" : ""}`} style={{ left, top }}>
            {points[index]?.count || index + 1}
          </span>
        ))}
      </div>
      <div className="mapBottomSheet">
        <strong>{points[0]?.name || "추천 장소를 선택하세요"}</strong>
        <p>{points[0]?.district || "서울"} · 방문 지점의 위치를 빠르게 확인합니다.</p>
        <a href="/route">동선 추천 보기</a>
      </div>
    </Card>
  );
}

export function RouteScoreBreakdown({ breakdown = {}, score }) {
  const maxValue = Math.max(...SCORE_ROWS.map(([key]) => Math.abs(Number(breakdown?.[key]) || 0)), 0.01);

  return (
    <div className="scoreBreakdown routeScoreBreakdown" aria-label="동선 점수 구성">
      {SCORE_ROWS.map(([key, label]) => {
        const rawValue = Number(breakdown?.[key]) || 0;
        return (
          <div key={key} className={`scoreBreakdownRow ${rawValue < 0 ? "negative" : ""}`}>
            <div>
              <span>{label}</span>
              <strong>{formatMetric(rawValue)}</strong>
            </div>
            <i>
              <b style={{ width: `${Math.min(100, (Math.abs(rawValue) / maxValue) * 100)}%` }} />
            </i>
          </div>
        );
      })}
      <div className="scoreBreakdownFinal">
        <span>최종 점수</span>
        <strong>{formatMetric(score)}</strong>
      </div>
    </div>
  );
}

export function RouteTimeline({
  items = [],
  selectedOrder,
  selectedStopId,
  onSelect,
  itemRefs,
  savedStopIds = [],
}) {
  if (!items.length) {
    return <EmptyState title="추천 동선이 없습니다" message="조건을 입력하고 동선 추천을 실행해주세요." />;
  }

  return (
    <div className="routeTimelineList">
      {items.map((item, index) => {
        const stopId = getStopId(item, index);
        const isActive = selectedStopId ? selectedStopId === stopId : selectedOrder === item.order;
        const isSaved = savedStopIds.includes(stopId);

        return (
          <article
            key={stopId}
            ref={(node) => {
              if (itemRefs?.current) {
                itemRefs.current[stopId] = node;
              }
            }}
            className={`routeTimelineItem ${isActive ? "active" : ""}`}
          >
            {index > 0 ? (
              <div className="travelStep">
                <span />
                <p>권역 기준 이동 {item.estimated_travel_time_from_previous}</p>
              </div>
            ) : null}
            <div className="routeStepRow">
              <button type="button" onClick={() => onSelect?.(stopId)} className="routeTimeButton" aria-label={`${item.time} ${item.place_name} 선택`}>
                <time>{item.time}</time>
              </button>
              <div
                className="routeStepCard"
                onClick={() => onSelect?.(stopId)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect?.(stopId);
                  }
                }}
                role="button"
                tabIndex={0}
                aria-label={`${item.order}번째 일정 ${item.place_name} 선택`}
              >
                <div className="cardHeaderLine">
                  <div className="chipRow compact">
                    <Tag tone="amber">{item.order}번</Tag>
                    {isActive ? <Tag tone="green">현재 일정</Tag> : null}
                    {isSaved ? <Tag tone="blue">저장됨</Tag> : null}
                  </div>
                  <span className="scorePill">{getFitLabel(item.score)}</span>
                </div>
                <h3>{item.place_name}</h3>
                <p>{getTimeRange(item.time)} · {item.district} · {item.place_type}</p>
                <div className="timelineMetaGrid">
                  <span>{getActivityType(item)}</span>
                  <span>{getTargetLabel(item)}</span>
                  <span>{buildChecklist(item).join(" / ")}</span>
                </div>
                <p className="sequenceText">{buildShortReason(item)}</p>
                <details className="scoreDetails">
                  <summary>점수 구성 보기</summary>
                  <p className="reasonText expanded">{item.sequence_reason}</p>
                  <p className="reasonText expanded">{item.recommendation_reason}</p>
                  <RouteScoreBreakdown breakdown={item.score_breakdown} score={item.score} />
                </details>
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}

function getReasonBadges(item, query) {
  const badges = [];
  if (Number(item?.district_bonus) > 0) {
    badges.push(`${query?.district || item?.recommended_district || "자치구"} 일치`);
  }
  if (Number(item?.place_type_bonus) > 0) {
    badges.push(`${query?.place_type || getPlaceTypeLabel(item?.recommended_place_type)} 적합`);
  }
  if (Number(item?.time_bonus) > 0) {
    badges.push("시간대 접점");
  }
  if (Number(item?.context_bonus) > 0) {
    badges.push("상황 맥락 반영");
  }
  if (Number(item?.target_bonus) > 0) {
    badges.push("타깃 유권자 접점");
  }
  return badges.length ? badges.slice(0, 4) : ["기본 점수 우수", "운영 동선 배치 가능"];
}

export function buildRecommendationReason(item, query) {
  if (!item) {
    return "추천 결과가 없습니다.";
  }

  const fragments = [];
  if (Number(item.district_bonus) > 0) {
    fragments.push(`${query?.district || "선택 지역"} 조건과 일치`);
  }
  if (Number(item.place_type_bonus) > 0) {
    fragments.push(`${query?.place_type || getPlaceTypeLabel(item?.recommended_place_type)} 방문 목적에 적합`);
  }
  if (Number(item.time_bonus) > 0) {
    fragments.push("해당 시간대 접점 기대");
  }
  if (Number(item.context_bonus) > 0) {
    fragments.push("상황 태그와 장소 특성 일치");
  }
  if (Number(item.target_bonus) > 0) {
    fragments.push(`${query?.target_voter_group || "타깃 유권자"} 접점 반영`);
  }

  if (!fragments.length) {
    fragments.push("기본 점수가 안정적인 후보지");
  }

  return `${fragments.slice(0, 2).join(" · ")}. 현장 일정에 배치하기 좋은 후보입니다.`;
}

export function RecommendationCard({ item, query, featured = false }) {
  const reason = buildRecommendationReason(item, query);
  const badges = getReasonBadges(item, query);
  const placeType = getPlaceTypeLabel(item?.recommended_place_type);
  const mapHref = `/map?place=${encodeURIComponent(item?.recommended_place_name || "")}&district=${encodeURIComponent(item?.recommended_district || "")}`;

  return (
    <Card className={`recommendationCard ${featured ? "featured" : ""}`}>
      <div className="recommendationHeader">
        <span className="rankBadge">{item?.rank || "-"}</span>
        <div>
          {featured ? <Tag tone="amber">최우선 추천</Tag> : null}
          <h3>{item?.recommended_place_name || "추천 장소 없음"}</h3>
          <p>{item?.recommended_district || "자치구 확인"} · {placeType}</p>
        </div>
        <span className="scorePill">{getFitLabel(item?.score)}</span>
      </div>
      <div className="reasonBadgeRow">
        {badges.map((badge) => (
          <Tag key={badge} tone="amber">{badge}</Tag>
        ))}
      </div>
      {featured ? <p className="recommendUseText">추천 활용: {reason}</p> : <p className="reasonText">{reason}</p>}
      <div className="cardActionRow">
        <a className="buttonLink secondary compactButton" href={mapHref}>지도에서 보기</a>
        <details className="scoreDetails">
          <summary>추천 근거 보기</summary>
          <ScoreBreakdown item={item} />
        </details>
      </div>
    </Card>
  );
}

export const RecommendationResultCard = RecommendationCard;

export function ScoreBreakdown({ item }) {
  const values = RECOMMEND_SCORE_ROWS.map(([key]) => Math.max(0, Number(item?.[key]) || 0));
  const maxValue = Math.max(...values, 0.01);

  return (
    <div className="scoreBreakdown" aria-label="추천 점수 구성">
      {RECOMMEND_SCORE_ROWS.map(([key, label]) => {
        const value = Math.max(0, Number(item?.[key]) || 0);
        return (
          <div key={key} className="scoreBreakdownRow">
            <div>
              <span>{label}</span>
              <strong>{formatMetric(item?.[key])}</strong>
            </div>
            <i>
              <b style={{ width: `${Math.min(100, (value / maxValue) * 100)}%` }} />
            </i>
          </div>
        );
      })}
      <div className="scoreBreakdownFinal">
        <span>최종 점수</span>
        <strong>{formatMetric(item?.final_variant_score ?? item?.score)}</strong>
      </div>
    </div>
  );
}

export function MiniChart({ rows = [], metric = "NDCG@10", highlight = "optimized_proposed" }) {
  const maxValue = Math.max(...rows.map((row) => Number(row[metric]) || 0), 0.01);

  if (!rows.length) {
    return <EmptyState title="차트 데이터가 없습니다" />;
  }

  return (
    <div className="miniChart">
      {rows.map((row) => {
        const value = Number(row[metric]) || 0;
        return (
          <div key={`${row.model_name}-${metric}`} className={row.model_name === highlight ? "active" : ""}>
            <div>
              <strong>{row.model_name}</strong>
              <span>{formatMetric(value)}</span>
            </div>
            <i>
              <b style={{ width: `${Math.max(4, (value / maxValue) * 100)}%` }} />
            </i>
          </div>
        );
      })}
    </div>
  );
}

export function ModelComparisonChart({ rows = [] }) {
  return <MiniChart rows={rows} metric="NDCG@10" />;
}

export function MissingPlaceTypeChart({ rows = [] }) {
  const maxMissing = Math.max(...rows.map((row) => Number(row.missing_count) || 0), 1);

  if (!rows.length) {
    return <EmptyState title="누락 유형 데이터가 없습니다" />;
  }

  return (
    <div className="missingChart">
      {rows.slice(0, 9).map((row) => {
        const width = Math.max(4, ((Number(row.missing_count) || 0) / maxMissing) * 100);
        return (
          <div key={row.place_type}>
            <div className="missingChartHeader">
              <strong>{row.place_type}</strong>
              <span>{row.missing_count}/{row.total_gold_count}</span>
            </div>
            <i>
              <b style={{ width: `${width}%` }} />
            </i>
            <p>{row.candidate_generation_gap}</p>
          </div>
        );
      })}
    </div>
  );
}
