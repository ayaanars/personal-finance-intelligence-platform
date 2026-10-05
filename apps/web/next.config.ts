import type { NextConfig } from "next";

const apiOrigin = process.env.LEDGERX_API_ORIGIN || "http://127.0.0.1:8000";
if (process.env.VERCEL_ENV === "production") {
  const origin = new URL(apiOrigin);
  if (origin.protocol !== "https:" || origin.origin !== apiOrigin || origin.username || origin.password) {
    throw new Error("Production LEDGERX_API_ORIGIN must be an exact HTTPS origin");
  }
}

const nextConfig: NextConfig = {
  reactStrictMode: true,
  agentRules: false,
  turbopack: { root: process.cwd() },
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiOrigin}/api/v1/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Cache-Control", value: "no-store" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};
export default nextConfig;
