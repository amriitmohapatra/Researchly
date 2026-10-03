/**
 * Where the engine lives. Inlined at build time (NEXT_PUBLIC_*), so the
 * browser — never a Next.js server route — calls it directly (ADR-02, §5.3).
 */
export const DEFAULT_ENGINE_URL = "http://localhost:8080";

/** Normalises an engine base URL: absolute http(s), no trailing slash, no path quirks. */
export function normaliseEngineUrl(raw: string | undefined): string {
  const value = (raw ?? "").trim() || DEFAULT_ENGINE_URL;
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error(`NEXT_PUBLIC_ENGINE_URL is not a valid absolute URL: ${JSON.stringify(value)}`);
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error(`NEXT_PUBLIC_ENGINE_URL must be http(s), got ${url.protocol}`);
  }
  return `${url.origin}${url.pathname.replace(/\/+$/, "")}`;
}

/** The origin only — what the Content-Security-Policy's connect-src allows. */
export function engineOrigin(raw: string | undefined): string {
  return new URL(normaliseEngineUrl(raw)).origin;
}

export const ENGINE_URL = normaliseEngineUrl(process.env.NEXT_PUBLIC_ENGINE_URL);
