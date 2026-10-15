import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // e2e runs its own dev server beside yours without fighting over .next
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
  output: "standalone",
  devIndicators: false,
};

export default nextConfig;
