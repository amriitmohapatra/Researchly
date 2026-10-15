/**
 * The live check (S4d R3, used by R4 in Word and R5 on the website): send
 * the paragraphs that changed after a typing pause, with a revision, and
 * keep only the replies that still describe the text on screen.
 *
 * The network call itself lives in lib/engine.ts (the one audited path that
 * sends text, scripts/check-boundary.mjs). This file holds the parts every
 * surface shares: the call with its options, the batch limits and the
 * stale-reply rule. Nothing here is stored.
 */
import {
  MAX_LIVE_CHARS,
  MAX_LIVE_HEADING_CHARS,
  MAX_LIVE_PARAGRAPHS,
  type CheckParagraphsRequest,
  type CheckParagraphsResponse,
  type LiveParagraph,
  type TierHealth,
} from "@researchly/contract";
import { ENGINE_URL } from "./config";
import { postCheckParagraphs, type CheckResult, type EngineAuth } from "./engine";

export interface CheckParagraphsOptions {
  /** The engine to ask (default: the hosted one). */
  engineUrl?: string;
  /** The signed-in caller's token source; null or omitted for anonymous use and for "This computer". */
  auth?: EngineAuth | null;
  signal?: AbortSignal;
}

/** POST /v1/check-paragraphs: the contract's request in, its response out (or a CheckError). */
export function checkParagraphs(
  request: CheckParagraphsRequest,
  opts: CheckParagraphsOptions = {},
): Promise<CheckResult<CheckParagraphsResponse>> {
  return postCheckParagraphs(request, opts.engineUrl ?? ENGINE_URL, opts.auth ?? null, opts.signal);
}

/** How long the writer must pause before a live check is sent. */
export const LIVE_PAUSE_MS = 1_500;

/** A paragraph waiting to be checked: its request form. */
export type LiveCandidate = LiveParagraph;

/**
 * The next batch within the contract's limits: at most 50 paragraphs and
 * 20,000 characters together, in the order given. A paragraph too long to
 * send at all is returned in `tooLong` (it is never sent live; the full
 * check still reads it). The rest wait for the next round.
 */
export function takeBatch<T extends { text: string }>(
  candidates: readonly T[],
  limits: { paragraphs: number; chars: number } = { paragraphs: MAX_LIVE_PARAGRAPHS, chars: MAX_LIVE_CHARS },
): { batch: T[]; rest: T[]; tooLong: T[] } {
  const batch: T[] = [];
  const rest: T[] = [];
  const tooLong: T[] = [];
  let chars = 0;
  for (const c of candidates) {
    if (c.text.length > limits.chars) {
      tooLong.push(c);
      continue;
    }
    if (batch.length < limits.paragraphs && chars + c.text.length <= limits.chars && rest.length === 0) {
      batch.push(c);
      chars += c.text.length;
    } else {
      rest.push(c);
    }
  }
  return { batch, rest, tooLong };
}

/** A heading as the contract takes it: trimmed, at most 300 characters. */
export function liveHeading(text: string | null | undefined): string {
  return (text ?? "").trim().slice(0, MAX_LIVE_HEADING_CHARS);
}

/**
 * Whether a reply may still be painted: it answers the revision that was
 * sent, and nothing reset the surface since (a full check, a changed
 * setting, underlines switched off). Each paragraph's text is checked
 * separately, just before painting.
 */
export function isCurrentReply(
  reply: Pick<CheckParagraphsResponse, "revision">,
  sent: { revision: number; generation: number },
  now: { generation: number },
): boolean {
  return reply.revision === sent.revision && sent.generation === now.generation;
}

/** Partial state's reason in plain words: which part of the checking was off ("Grammar was not checked"). */
export function partialReason(health: readonly TierHealth[]): string {
  // The learned tier is optional and usually absent: its absence is not "part of the checking was off".
  const down = health.filter((t) => !t.ok && t.tier !== "gec" && t.state !== "disabled");
  if (down.length === 0) return "";
  const names = down.map((t) => t.label || t.tier);
  const list = names.length === 1 ? names[0]! : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
  return `${list} ${names.length === 1 ? "was" : "were"} not checked`;
}
