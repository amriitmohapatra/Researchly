/**
 * Recording a check for the writer's progress view (S4), from the website:
 * only signed in, only when they switched "Keep my progress" on, and fire
 * and forget. Counts only (lib/progress.ts decides the row); a failure is
 * swallowed here and never reaches the results.
 *
 * A recheck of unchanged text is not recorded again (Codex review N2):
 * changing a control (the article type, the checklist, preferences) re-runs
 * the check on the same words, and recording it would count the same draft
 * twice. The comparison uses a short in-memory key of the text, held in this
 * page only: never stored, never sent, gone on reload.
 */
import type { AnalyzeResponse } from "@researchly/contract";
import { recordProgress } from "./progress";

type Source = Parameters<typeof recordProgress>[0];
type Recorder = (data: Source, keep: boolean) => Promise<unknown>;

let lastRecorded: string | null = null;

/** A short in-memory key for a text (FNV-1a over its UTF-16 units, plus its length). Never stored or sent. */
export function textKey(text: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return `${text.length}:${h.toString(36)}`;
}

/** True, and remembered, for text not recorded just before; false for the same text again. */
export function claimText(key: string | null | undefined): boolean {
  if (!key) return true;
  if (key === lastRecorded) return false;
  lastRecorded = key;
  return true;
}

/** For tests: forget the last recorded text. */
export function resetRecorded(): void {
  lastRecorded = null;
}

export function recordCheck(
  data: Source & Pick<AnalyzeResponse, "suggestions">,
  opts: { signedIn: boolean; keep: boolean; textKey?: string | null },
  record: Recorder = recordProgress,
): void {
  if (!opts.signedIn || !opts.keep) return;
  if (!claimText(opts.textKey)) return;
  try {
    void record(data, true).catch(() => undefined);
  } catch {
    /* never let progress affect a check */
  }
}
