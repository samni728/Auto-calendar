import type { NextConfig } from "next";

const apiProxyTarget = process.env.API_PROXY_TARGET?.replace(/\/$/, "");
const allowedDevOrigins = process.env.NEXT_ALLOWED_DEV_ORIGINS
  ?.split(",")
  .map((origin) => origin.trim())
  .filter(Boolean);

const nextConfig: NextConfig = {
  agentRules: false,
  allowedDevOrigins,
  outputFileTracingRoot: process.cwd(),
  async rewrites() {
    if (!apiProxyTarget) return [];
    return [
      { source: "/api/:path*", destination: `${apiProxyTarget}/api/:path*` },
      { source: "/healthz", destination: `${apiProxyTarget}/healthz` },
    ];
  },
};

export default nextConfig;
