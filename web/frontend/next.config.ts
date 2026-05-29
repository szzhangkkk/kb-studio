import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  distDir: "dist",
  trailingSlash: true,
  images: { unoptimized: true },
  async rewrites() {
    return [
      { source: "/kb/:path*", destination: "http://localhost:8000/kb/:path*" },
      { source: "/config/:path*", destination: "http://localhost:8000/config/:path*" },
      { source: "/providers", destination: "http://localhost:8000/providers" },
      { source: "/providers/:path*", destination: "http://localhost:8000/providers/:path*" },
      { source: "/test-connection", destination: "http://localhost:8000/test-connection" },
      { source: "/tools/:path*", destination: "http://localhost:8000/tools/:path*" },
      { source: "/mcp/:path*", destination: "http://localhost:8000/mcp/:path*" },
      { source: "/scheduler/:path*", destination: "http://localhost:8000/scheduler/:path*" },
      { source: "/notifications/:path*", destination: "http://localhost:8000/notifications/:path*" },
      { source: "/notifications", destination: "http://localhost:8000/notifications" },
      { source: "/sources/:path*", destination: "http://localhost:8000/sources/:path*" },
      { source: "/sources", destination: "http://localhost:8000/sources" },
      { source: "/export/:path*", destination: "http://localhost:8000/export/:path*" },
      { source: "/import/:path*", destination: "http://localhost:8000/import/:path*" },
      { source: "/staleness", destination: "http://localhost:8000/staleness" },
      { source: "/memory/:path*", destination: "http://localhost:8000/memory/:path*" },
      { source: "/suggestions/:path*", destination: "http://localhost:8000/suggestions/:path*" },
      { source: "/suggestions", destination: "http://localhost:8000/suggestions" },
    ];
  },
};

export default nextConfig;
