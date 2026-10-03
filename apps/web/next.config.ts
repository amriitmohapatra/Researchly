import path from "node:path";
import type { NextConfig } from "next";
import { normaliseEngineUrl, supabaseConfig } from "./lib/config";
import { STATIC_SECURITY_HEADERS } from "./lib/security";

// Fail the build early on a malformed engine URL rather than shipping a page
// whose every check fails.
normaliseEngineUrl(process.env.NEXT_PUBLIC_ENGINE_URL);
// Same for accounts: a set-but-malformed Supabase URL or key (or a secret
// key pasted where the publishable one belongs) stops the build.
supabaseConfig(process.env.NEXT_PUBLIC_SUPABASE_URL, process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY);

// The monorepo root: lets Turbopack compile ../../packages/contract (the
// generated API types and MAX_CONTENT_CHARS) as first-party source.
const repoRoot = path.join(__dirname, "..", "..");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The e2e suite builds the site twice (without and with accounts) side by
  // side; each build needs its own output directory.
  distDir: process.env.RESEARCHLY_DIST_DIR || ".next",
  poweredByHeader: false,
  turbopack: { root: repoRoot },
  outputFileTracingRoot: repoRoot,
  async headers() {
    return [{ source: "/:path*", headers: [...STATIC_SECURITY_HEADERS] }];
  },
};

export default nextConfig;
