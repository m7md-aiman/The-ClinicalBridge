import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export so the whole site can be served by FastAPI as one app (and hosted anywhere).
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
