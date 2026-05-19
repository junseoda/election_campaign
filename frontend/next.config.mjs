import path from "node:path";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");

const connectSources = [
  "'self'",
  "https://*.kakao.com",
  "https://dapi.kakao.com",
  "https://election-campaign-coral.vercel.app",
  "https://election-campaign-junseodas-projects.vercel.app",
  "https://election-campaign-git-main-junseodas-projects.vercel.app",
  "https://*.onrender.com",
  "https://*.railway.app",
  "https://*.up.railway.app",
  "http://localhost:8000",
  "http://127.0.0.1:8000",
  ...(apiBaseUrl ? [apiBaseUrl] : []),
];

const contentSecurityPolicy = [
  "default-src 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://dapi.kakao.com https://*.kakao.com https://*.kakaocdn.net",
  "script-src-elem 'self' 'unsafe-inline' https://dapi.kakao.com https://*.kakao.com https://*.kakaocdn.net",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https://*.kakao.com https://*.kakaocdn.net https://*.daumcdn.net",
  `connect-src ${connectSources.join(" ")}`,
  "font-src 'self' data:",
  "worker-src 'self' blob:",
  "upgrade-insecure-requests",
].join("; ");

const securityHeaders = [
  {
    key: "Content-Security-Policy",
    value: contentSecurityPolicy,
  },
];

const nextConfig = {
  outputFileTracingRoot: path.join(process.cwd()),
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
