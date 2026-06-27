import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Keep the demo build green regardless of lint state.
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: false },
};

export default nextConfig;
