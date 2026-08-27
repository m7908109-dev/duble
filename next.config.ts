import type { NextConfig } from "next";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  typescript: {
    ignoreBuildErrors: true,
  },
  reactStrictMode: false,
  // Proxy /api/* to the Python FastAPI backend (port 8000) for local dev.
  // In production behind the Caddy gateway, requests with XTransformPort are
  // routed directly to the backend by Caddy; the rewrite is harmless there.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
