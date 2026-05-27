import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    ppr: "incremental",
  },
  rewrites: async () => {
    return [
      {
        source: "/api/:path*",
        destination: "http://api.localhost:8888/api/:path*", // Proxy to FastAPI in local dev
      },
    ];
  },
};

export default nextConfig;
