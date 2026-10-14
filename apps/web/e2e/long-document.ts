/**
 * A synthetic thesis-sized document and its suggestions, generated from a
 * fixed seed (2026-10-14 performance pass): words drawn from the list below
 * (written for these tests; no real writing), with a suggestion cloned from
 * the sample cards every `every` words. Used by e2e/long-results.spec.ts
 * and the measurement in e2e/perf.spec.ts.
 */
import type { AnalyzeResponse, Suggestion } from "@researchly/contract";
import { happyResponse } from "./fixtures";
import { SAMPLE_SUGGESTIONS } from "./sample";

/** A small seeded PRNG (mulberry32): the same document every run. */
function rng(seed: number) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const VOCAB = (
  "the model was fitted to weekly counts of cases in each district and the posterior " +
  "median of the reproduction number varied across regions during the second wave while " +
  "reporting delays were estimated from the line list with a negative binomial likelihood " +
  "we used a renewal equation with a gamma serial interval and calibrated the prior " +
  "predictive check against hospital admissions under the baseline scenario"
).split(" ");
export const SECTIONS = ["introduction", "methods", "results", "discussion"] as const;
const TEMPLATES = SAMPLE_SUGGESTIONS.filter((s) => s.category !== "preference");

export function longDocument(words: number, every: number): { text: string; suggestions: Suggestion[] } {
  const r = rng(42);
  let text = "";
  let line = 1;
  let lineStart = 0;
  const out: Suggestion[] = [];
  const perSection = Math.ceil(words / SECTIONS.length);
  let n = 0;
  for (const section of SECTIONS) {
    text += `${section[0]!.toUpperCase()}${section.slice(1)}\n\n`;
    line += 2;
    lineStart = text.length;
    let inPara = 0;
    for (let w = 0; w < perSection; w++, n++) {
      const word = VOCAB[Math.floor(r() * VOCAB.length)]!;
      const start = text.length;
      text += inPara === 0 ? word[0]!.toUpperCase() + word.slice(1) : word;
      if (n % every === every - 1) {
        const t = TEMPLATES[out.length % TEMPLATES.length]!;
        out.push({
          ...t,
          id: `p${out.length.toString(16).padStart(6, "0")}`,
          span: { start, end: text.length, line, col: start - lineStart + 1 },
          text: text.slice(start, text.length),
          section,
        });
      }
      inPara++;
      if (inPara > 110 + Math.floor(r() * 60)) {
        text += ".\n\n";
        line += 2;
        lineStart = text.length;
        inPara = 0;
      } else text += r() < 0.07 ? ". " : " ";
    }
    text += ".\n\n";
    line += 2;
    lineStart = text.length;
  }
  return { text, suggestions: out };
}

/** The engine's answer for that document. */
export function longResponse(suggestions: Suggestion[]): AnalyzeResponse {
  const counts: Record<string, number> = {};
  for (const s of suggestions) counts[s.category] = (counts[s.category] ?? 0) + 1;
  return { ...happyResponse, suggestions, counts, sections_detected: [...SECTIONS], elapsed_ms: 9_000 };
}
