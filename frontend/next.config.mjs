import path from "node:path";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");
const appEnv = process.env.NEXT_PUBLIC_APP_ENV || process.env.NODE_ENV;
const isProductionLike = Boolean(process.env.VERCEL) || appEnv === "production";

function isLocalUrl(value) {
  if (!value) {
    return false;
  }
  try {
    const hostname = new URL(value).hostname.toLowerCase();
    return ["localhost", "127.0.0.1", "::1", "0.0.0.0"].includes(hostname);
  } catch (error) {
    return true;
  }
}

const safeApiBaseUrl = apiBaseUrl && !(isProductionLike && isLocalUrl(apiBaseUrl)) ? apiBaseUrl : "";

const daumMapSources = [
  "https://*.daumcdn.net",
  "https://t1.daumcdn.net",
  "https://t2.daumcdn.net",
  "https://t3.daumcdn.net",
  "https://t4.daumcdn.net",
  "https://map.daumcdn.net",
  "https://map0.daumcdn.net",
  "https://map1.daumcdn.net",
  "https://map2.daumcdn.net",
  "https://map3.daumcdn.net",
  "https://map4.daumcdn.net",
  "https://mts.daumcdn.net",
];

const connectSources = [
  "'self'",
  "https://*.kakao.com",
  "https://dapi.kakao.com",
  ...daumMapSources,
  "https://election-campaign-coral.vercel.app",
  "https://election-campaign-junseodas-projects.vercel.app",
  "https://election-campaign-git-main-junseodas-projects.vercel.app",
  "https://*.onrender.com",
  "https://*.railway.app",
  "https://*.up.railway.app",
  ...(!isProductionLike ? ["http://localhost:8000", "http://127.0.0.1:8000"] : []),
  ...(safeApiBaseUrl ? [safeApiBaseUrl] : []),
];

const contentSecurityPolicy = [
  "default-src 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  `script-src 'self' 'unsafe-inline' 'unsafe-eval' https://dapi.kakao.com https://*.kakao.com https://*.kakaocdn.net ${daumMapSources.join(" ")}`,
  `script-src-elem 'self' 'unsafe-inline' 'unsafe-eval' https://dapi.kakao.com https://*.kakao.com https://*.kakaocdn.net ${daumMapSources.join(" ")}`,
  `style-src 'self' 'unsafe-inline' https://*.kakao.com https://*.kakaocdn.net ${daumMapSources.join(" ")}`,
  `img-src 'self' data: blob: https://*.kakao.com https://*.kakaocdn.net ${daumMapSources.join(" ")}`,
  `connect-src ${connectSources.join(" ")}`,
  "font-src 'self' data:",
  "worker-src 'self' blob:",
  "child-src 'self' blob:",
  "upgrade-insecure-requests",
].join("; ");

const securityHeaders = [
  {
    key: "Content-Security-Policy",
    value: contentSecurityPolicy,
  },
];

const nextConfig = {
  outputFileTracingRoot: path.resolve(process.cwd(), ".."),
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};


export default nextConfig;
