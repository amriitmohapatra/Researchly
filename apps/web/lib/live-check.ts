/**
 * The live check (S4d R3/R5; docs/inline-review-design.md §5): a few
 * paragraphs, each with its nearest heading and a revision number, sent
 * after a typing pause to `POST /v1/check-paragraphs`. The engine answers
 * with sentence-level suggestions whose `begin`/`end` are UTF-16 offsets
 * within the paragraph (JavaScript string indices).
 *
 * The request leaves from lib/engine.ts (the one audited path that sends
 * text); this file only shapes and checks it. Nothing is stored.
 */
import "client-only";
import type { CheckParagraphsRequest, CheckParagraphsResponse } from "@researchly/contract";
import { postEngineJson, type CheckResult, type EngineAuth } from "./engine";

/**
 * How long one live check may take before the page calls the engine
 * unreachable. Far above the engine's budget (p95 under 800 ms for a
 * 200-word paragraph), far below a full check's.
 */
export const LIVE_TIMEOUT_MS = 15_000;

export interface LiveCheckOptions {
  engineUrl?: string;
  /** The account's token source (signed in), or null. */
  auth?: EngineAuth | null;
  signal?: AbortSignal;
  timeoutMs?: number;
}

function isNat(v: unknown): v is number {
  return typeof v === "number" && Number.isInteger(v) && v >= 0;
}

/** Enough to draw underlines safely: every suggestion has an id, a category and a usable range. */
export function looksLikeCheckParagraphsResponse(body: unknown): body is CheckParagraphsResponse {
  if (typeof body !== "object" || body === null) return false;
  const b = body as Record<string, unknown>;
  if (!isNat(b.revision) || !Array.isArray(b.paragraphs) || !Array.isArray(b.health)) return false;
  return b.paragraphs.every((p: unknown) => {
    if (typeof p !== "object" || p === null) return false;
    const para = p as Record<string, unknown>;
    return (
      typeof para.id === "string" &&
      Array.isArray(para.suggestions) &&
      para.suggestions.every((s: unknown) => {
        if (typeof s !== "object" || s === null) return false;
        const x = s as Record<string, unknown>;
        return (
          typeof x.id === "string" &&
          typeof x.category === "string" &&
          typeof x.message === "string" &&
          isNat(x.begin) &&
          isNat(x.end) &&
          (x.end as number) >= (x.begin as number)
        );
      })
    );
  });
}

/** POST /v1/check-paragraphs. Throws only when `signal` aborts (the caller superseded it). */
export async function checkParagraphs(
  request: CheckParagraphsRequest,
  opts: LiveCheckOptions = {},
): Promise<CheckResult<CheckParagraphsResponse>> {
  return postEngineJson("/v1/check-paragraphs", request, looksLikeCheckParagraphsResponse, {
    engineUrl: opts.engineUrl,
    auth: opts.auth,
    signal: opts.signal,
    timeoutMs: opts.timeoutMs ?? LIVE_TIMEOUT_MS,
  });
}
