import http from "node:http";
import net from "node:net";
import next from "next";

const HOST = "127.0.0.1";
const START_PORT = Number(process.env.QA_PORT || 3100);
const PAGE_PATHS = ["/", "/recommend", "/route", "/evaluation"];
const FATAL_PATTERNS = [
  /Hydration failed/i,
  /Text content does not match server-rendered HTML/i,
  /Unhandled Runtime Error/i,
  /Application error/i,
];

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function findOpenPort(port) {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", (error) => {
      if (error.code === "EADDRINUSE") {
        findOpenPort(port + 1).then(resolve, reject);
      } else {
        reject(error);
      }
    });
    server.once("listening", () => {
      server.close(() => resolve(port));
    });
    server.listen(port, HOST);
  });
}

async function fetchWithTimeout(url, options = {}, timeoutMs = 10000) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(options.headers || {}),
      },
    });
  } finally {
    clearTimeout(timeout);
  }
}

async function waitForServer(baseUrl, timeoutMs = 60000) {
  const startedAt = Date.now();
  let lastError = null;
  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await fetchWithTimeout(`${baseUrl}/api/health`, {}, 3000);
      if (response.ok) {
        return;
      }
      lastError = new Error(`/api/health returned ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`Timed out waiting for ${baseUrl}: ${lastError?.message || "unknown error"}`);
}

async function getJson(baseUrl, path) {
  const response = await fetchWithTimeout(`${baseUrl}${path}`);
  assert(response.ok, `${path} returned HTTP ${response.status}`);
  return response.json();
}

async function postJson(baseUrl, path, body) {
  const response = await fetchWithTimeout(`${baseUrl}${path}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  assert(response.ok, `${path} returned HTTP ${response.status}`);
  return response.json();
}

async function assertPage(baseUrl, path) {
  const response = await fetchWithTimeout(`${baseUrl}${path}`);
  assert(response.ok, `${path} returned HTTP ${response.status}`);
  const html = await response.text();
  assert(!FATAL_PATTERNS.some((pattern) => pattern.test(html)), `${path} rendered a fatal error page`);
}

async function startNextServer(baseUrl) {
  const parsedUrl = new URL(baseUrl);
  const port = Number(parsedUrl.port);
  const app = next({
    dev: false,
    dir: process.cwd(),
    hostname: HOST,
    port,
  });
  const handle = app.getRequestHandler();
  await app.prepare();
  const server = http.createServer((request, response) => handle(request, response));
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, HOST, resolve);
  });
  return server;
}

async function main() {
  let serverLog = "";
  let server = null;
  const externalBaseUrl = process.env.QA_BASE_URL?.replace(/\/$/, "");
  const baseUrl = externalBaseUrl || `http://${HOST}:${await findOpenPort(START_PORT)}`;

  if (!externalBaseUrl) {
    process.env.NEXT_PUBLIC_API_BASE_URL = "";
    process.env.NEXT_PUBLIC_APP_ENV = "local";
    const originalError = console.error;
    console.error = (...args) => {
      serverLog += `${args.map(String).join(" ")}\n`;
      originalError(...args);
    };
    server = await startNextServer(baseUrl);
  }

  try {
    await waitForServer(baseUrl);

    const health = await getJson(baseUrl, "/api/health");
    assert(health.ok === true && health.status === "ok", "/api/health did not return ok");

    const recommendation = await postJson(baseUrl, "/api/recommend", {
      district: "성동구",
      time: "09:00",
      target: "직장인",
      purpose: "출근인사",
      limit: 5,
    });
    assert(recommendation.ok === true, "/api/recommend ok flag is false");
    assert(Array.isArray(recommendation.items) && recommendation.items.length >= 5, "/api/recommend returned fewer than 5 items");

    const route = await postJson(baseUrl, "/api/route", {
      start_location: "서울시청",
      districts: ["중구"],
      target_voter_group: "직장인",
      campaign_goal: "퇴근인사",
      num_visits: 5,
    });
    assert(route.ok === true, "/api/route ok flag is false");
    assert(Array.isArray(route.schedule) && route.schedule.length >= 5, "/api/route returned fewer than 5 schedule items");
    assert(route.mapStats?.recommendedCount === route.schedule.length, "route recommendedCount does not match schedule length");
    assert(
      route.mapStats.markerCount + route.mapStats.missingCoordinateCount === route.mapStats.recommendedCount,
      "route markerCount + missingCoordinateCount invariant failed",
    );

    const evaluation = await getJson(baseUrl, "/api/evaluation/summary");
    assert(evaluation.ok === true, "/api/evaluation/summary ok flag is false");
    assert(
      (Array.isArray(evaluation.metrics) && evaluation.metrics.length > 0) ||
        (Array.isArray(evaluation.modelComparison) && evaluation.modelComparison.length > 0),
      "/api/evaluation/summary returned no metrics or model comparison data",
    );

    for (const path of PAGE_PATHS) {
      await assertPage(baseUrl, path);
    }

    assert(!FATAL_PATTERNS.some((pattern) => pattern.test(serverLog)), "server log contains a fatal hydration/runtime pattern");

    console.log(`QA passed at ${baseUrl}`);
    console.log(`recommendations=${recommendation.items.length}`);
    console.log(`schedule=${route.schedule.length}, markers=${route.mapStats.markerCount}, missing=${route.mapStats.missingCoordinateCount}`);
    console.log(`metrics=${evaluation.metrics?.length || 0}, modelComparison=${evaluation.modelComparison?.length || 0}`);
  } finally {
    if (server) {
      await new Promise((resolve) => server.close(resolve));
    }
  }
}

main().catch((error) => {
  console.error(`QA failed: ${error.message}`);
  process.exitCode = 1;
});
