import type { NextConfig } from "next";

// Next.js 16: Turbopack is the default bundler — no --turbopack flag needed.
// Cache Components (replaces PPR) can be enabled via: cacheComponents: true
const API_URL = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

const nextConfig: NextConfig = {
  // turbopack: {}, // top-level in Next.js 16 (was experimental.turbopack in v15)
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  rewrites: async () => {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${API_URL}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
