/**
 * The only code that sends document text anywhere. It runs in the browser
 * and talks straight to the engine (ADR-02 / ARCHITECTURE.md §5.3): the
 * Next.js server never receives the text. `client-only` makes importing
 * this module from server code a build error, and scripts/check-boundary.mjs
 * fails the lint if any route handler or server action appears.
 */
import "client-only";
import type { AnalyzeRequest, AnalyzeResponse, Format } from "@researchly/contract";
import { ENGINE_URL } from "./config";
import { badPayloadError, errorFromResponse, networkError, type CheckError } from "./errors";

export const ANALYZE_TIMEOUT_MS = 120_000;

export type CheckResult = { ok: true; data: AnalyzeResponse } | { ok: false; error: CheckError };

export interface CheckParams {
  content: string;
  format: Format;
  showPreferences: boolean;
  signal?: AbortSignal;
}

export function buildRequest(p: Pick<CheckParams, "content" | "format" | "showPreferences">): AnalyzeRequest {
  return {
    content: p.content,
    format: p.format,
    options: { show_preferences: p.showPreferences },
  };
}

/** Minimal structural check: enough to render safely, not a full schema validation. */
export function looksLikeAnalyzeResponse(body: unknown): body is AnalyzeResponse {
  if (typeof body !== "object" || body === null) return false;
  const b = body as Record<string, unknown>;
  return (
    Array.isArray(b.suggestions) &&
    Array.isArray(b.health) &&
    typeof b.hidden_preferences === "number" &&
    Array.isArray(b.sections_detected) &&
    b.suggestions.every(
      (s: unknown) =>
        typeof s === "object" &&
        s !== null &&
        typeof (s as { id?: unknown }).id === "string" &&
        typeof (s as { span?: { start?: unknown } }).span?.start === "number" &&
        typeof (s as { span?: { end?: unknown } }).span?.end === "number",
    )
  );
}

export async function analyze(p: CheckParams, engineUrl: string = ENGINE_URL): Promise<CheckResult> {
  const timeout = new AbortController();
  const timer = setTimeout(() => timeout.abort(), ANALYZE_TIMEOUT_MS);
  const signal = p.signal ? AbortSignal.any([p.signal, timeout.signal]) : timeout.signal;
  let res: Response;
  try {
    res = await fetch(`${engineUrl}/v1/analyze`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/json" },
      body: JSON.stringify(buildRequest(p)),
      // No cookies or credentials go to the engine in S1; no referrer either.
      credentials: "omit",
      referrerPolicy: "no-referrer",
      cache: "no-store",
      signal,
    });
  } catch (e) {
    clearTimeout(timer);
    if (p.signal?.aborted) throw e; // the user cancelled; caller handles it
    return { ok: false, error: networkError(timeout.signal.aborted, engineUrl) };
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) return { ok: false, error: errorFromResponse(res.status, body, res.headers) };
  if (!looksLikeAnalyzeResponse(body)) {
    return { ok: false, error: badPayloadError("The engine's answer was not in the expected shape.") };
  }
  if (body.schema_version !== "1") {
    return {
      ok: false,
      error: badPayloadError(`The engine speaks API version ${String(body.schema_version)}; this page expects version 1.`),
    };
  }
  return { ok: true, data: body };
}
