/**
 * The one place supabase-js is loaded (scripts/check-boundary.mjs enforces it).
 *
 * - Browser only: `client-only` makes importing this from server code a build
 *   error, and the library itself is loaded with a dynamic import() on first
 *   use, so it is not even in the server render or in a build without
 *   accounts (S1 behaviour, no Supabase code path).
 * - PKCE: the email link's one-time code is exchanged for a session here, in
 *   the browser (detectSessionInUrl). Next.js server code never sees a token.
 * - The session lives in localStorage under `sb-<project-ref>-auth-token`, by
 *   supabase-js design. It is the only thing this app stores besides the
 *   format preference; document text is never stored.
 */
import "client-only";
import type { SupabaseClient } from "@supabase/supabase-js";
import { SUPABASE } from "./config";
import { hasStoredKey } from "./prefs";

let client: Promise<SupabaseClient> | null = null;

/**
 * Where supabase-js keeps this project's session (and, mid sign-in, the
 * PKCE verifier as `<key>-code-verifier`): its default storage key.
 */
export function authStorageKey(): string | null {
  const cfg = SUPABASE;
  if (!cfg) return null;
  return `sb-${new URL(cfg.url).hostname.split(".")[0]}-auth-token`;
}

/**
 * Whether supabase-js has anything stored in this browser for this project
 * (a session, or a sign-in under way). When it has nothing, the visitor is
 * signed out, and loading the library (about a quarter of a page's
 * JavaScript) only to be told so can wait for a sign-in (2026-10-14
 * performance pass).
 */
export function hasStoredAuth(): boolean {
  const key = authStorageKey();
  if (!key || typeof window === "undefined") return false;
  // Storage that cannot be read: let supabase-js decide, as before.
  return hasStoredKey(key) ?? true;
}

/** The shared client, or null in a build without accounts (or on the server). */
export function getSupabase(): Promise<SupabaseClient> | null {
  const cfg = SUPABASE;
  if (!cfg || typeof window === "undefined") return null;
  client ??= import("@supabase/supabase-js").then(({ createClient }) =>
    createClient(cfg.url, cfg.key, {
      auth: {
        flowType: "pkce",
        detectSessionInUrl: true,
        persistSession: true,
        autoRefreshToken: true,
      },
    }),
  );
  return client;
}
