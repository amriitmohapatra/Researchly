import path from "node:path";
import type { NextConfig } from "next";
import { normaliseEngineUrl } from "./lib/config";
import { STATIC_SECURITY_HEADERS } from "./lib/security";

// Fail the build early on a malformed engine URL rather than shipping a page
// whose every check fails.
normaliseEngineUrl(process.env.NEXT_PUBLIC_ENGINE_URL);

// The monorepo root: lets Turbopack compile ../../packages/contract (the
// generated API types and MAX_CONTENT_CHARS) as first-party source.
const repoRoot = path.join(__dirname, "..", "..");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  turbopack: { root: repoRoot },
  outputFileTracingRoot: repoRoot,
  async headers() {
    return [{ source: "/:path*", headers: [...STATIC_SECURITY_HEADERS] }];
  },
};

export default nextConfig;
