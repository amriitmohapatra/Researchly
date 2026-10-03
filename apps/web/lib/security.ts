/**
 * Security headers, defined once.
 *
 * - Static headers are applied to every response by next.config.ts.
 * - The Content-Security-Policy needs a fresh nonce per request (Next.js
 *   inlines its bootstrap scripts), so proxy.ts sets it using cspHeader().
 *
 * connect-src is the confidentiality control that matters most: even if a
 * script were injected, the browser could only send data to this origin, to
 * the engine and (in a build with accounts) to the Supabase project.
 */
import { engineOrigin } from "./config";

export interface CspOptions {
  nonce: string;
  engineUrl: string | undefined;
  /** The validated Supabase origin, only when accounts are configured (config.supabaseConfig). */
  supabaseUrl?: string | null;
  dev: boolean;
}

export function cspHeader({ nonce, engineUrl, supabaseUrl, dev }: CspOptions): string {
  const engine = engineOrigin(engineUrl);
  // Supabase (sign-in and the settings tables) is the only other origin the
  // page may talk to, and only in a build that has accounts (S2).
  const supabase = supabaseUrl ? new URL(supabaseUrl).origin : null;
  const directives: [string, string[]][] = [
    ["default-src", ["'self'"]],
    ["script-src", ["'self'", `'nonce-${nonce}'`, "'strict-dynamic'", ...(dev ? ["'unsafe-eval'"] : [])]],
    ["style-src", ["'self'", dev ? "'unsafe-inline'" : `'nonce-${nonce}'`]],
    ["img-src", ["'self'", "data:", "blob:"]],
    ["font-src", ["'self'"]],
    ["connect-src", ["'self'", engine, ...(supabase && supabase !== engine ? [supabase] : [])]],
    ["manifest-src", ["'self'"]],
    ["worker-src", ["'self'"]],
    ["object-src", ["'none'"]],
    ["base-uri", ["'none'"]],
    ["form-action", ["'self'"]],
    ["frame-ancestors", ["'none'"]],
  ];
  const parts = directives.map(([k, v]) => `${k} ${v.join(" ")}`);
  // Upgrading would turn a local http engine into an unreachable https one.
  if (!dev && engine.startsWith("https:") && (!supabase || supabase.startsWith("https:"))) {
    parts.push("upgrade-insecure-requests");
  }
  return parts.join("; ");
}

export const STATIC_SECURITY_HEADERS: readonly { key: string; value: string }[] = [
  { key: "Referrer-Policy", value: "no-referrer" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), payment=(), usb=(), browsing-topics=()",
  },
];

/** A nonce for one response: 128 random bits, base64. */
export function makeNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s);
}
