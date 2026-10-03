/**
 * Engine responses for the mocked e2e runs. Each is a typed object that
 * `satisfies` the contract, so a contract change breaks the build of the
 * tests instead of silently drifting.
 */
import type { AnalyzeRequest, AnalyzeResponse, ErrorResponse, Suggestion, TierHealth } from "@researchly/contract";
import { SAMPLE_SUGGESTIONS, SAMPLE_TEXT } from "./sample";

export { SAMPLE_TEXT };

export const ENGINE = "http://127.0.0.1:8099";

const healthy: TierHealth[] = [
  { tier: "parser", label: "Parser", ok: true, state: "ready", detail: "spaCy en_core_web_sm", remedy: "" },
  { tier: "spelling", label: "Spelling", ok: true, state: "ready", detail: "SymSpell + scientific lexicon", remedy: "" },
  { tier: "grammar", label: "Grammar", ok: true, state: "ready", detail: "LanguageTool sidecar", remedy: "" },
  // Missing learned tier is normal in this build and must NOT produce a banner.
  {
    tier: "gec",
    label: "Learned corrections",
    ok: false,
    state: "missing",
    detail: "no local model in this build (the tier abstains entirely)",
    remedy: "",
  },
];

const metrics = {
  sentences: 9,
  words: 74,
  mean_sentence_len: 8.2,
  long_sentences: 0,
  nominalizations_per_100w: 2.7,
  hedges_per_100w: 4.05,
  boosters_per_100w: 2.7,
  self_mention_per_100w: 1.35,
  hedge_booster_balance: "balanced (1.5:1)",
  passive_share_by_section: { methods: 0.67, discussion: 0.0 },
} satisfies AnalyzeResponse["metrics"];

const engine = { service_version: "0.1.0", core_version: "0.8.0", rules_loaded: 87 } satisfies AnalyzeResponse["engine"];

function countsOf(list: Suggestion[]): Record<string, number> {
  const c: Record<string, number> = {};
  for (const s of list) c[s.category] = (c[s.category] ?? 0) + 1;
  return c;
}

const withoutPrefs = SAMPLE_SUGGESTIONS.filter((s) => s.category !== "preference");
const prefsOnly = SAMPLE_SUGGESTIONS.filter((s) => s.category === "preference");

/** show_preferences: false — the engine withholds preferences and reports how many. */
export const happyResponse = {
  schema_version: "1",
  suggestions: withoutPrefs,
  counts: countsOf(withoutPrefs),
  hidden_preferences: prefsOnly.length,
  metrics,
  sections_detected: ["introduction", "methods", "discussion"],
  health: healthy,
  engine,
  elapsed_ms: 412,
} satisfies AnalyzeResponse;

/** show_preferences: true */
export const withPreferencesResponse = {
  ...happyResponse,
  suggestions: SAMPLE_SUGGESTIONS,
  counts: countsOf(SAMPLE_SUGGESTIONS),
  hidden_preferences: 0,
} satisfies AnalyzeResponse;

export const degradedGrammarResponse = {
  ...happyResponse,
  health: healthy.map((t) =>
    t.tier === "grammar"
      ? {
          ...t,
          ok: false,
          state: "error",
          detail: "LanguageTool did not respond in time",
          remedy: "Grammar checks return automatically once it recovers; check again in a minute",
        }
      : t,
  ),
} satisfies AnalyzeResponse;

export const emptyResponse = {
  ...happyResponse,
  suggestions: [],
  counts: {},
  hidden_preferences: 0,
} satisfies AnalyzeResponse;

export const error413 = {
  error: { code: "payload_too_large", message: "Document too large", request_id: "req-413-7d1c" },
} satisfies ErrorResponse;

export const error429 = {
  error: { code: "rate_limited", message: "Rate limited", request_id: "req-429-0b2e" },
} satisfies ErrorResponse;

export const error500 = {
  error: { code: "internal", message: "Engine error", request_id: "req-500-a9f3c2" },
} satisfies ErrorResponse;

export const error422 = {
  error: { code: "invalid_request", message: "format must be one of: plain, markdown, latex", request_id: "req-422-11aa" },
} satisfies ErrorResponse;

/** Pick the right success fixture for a request, as the real engine would. */
export function responseFor(req: AnalyzeRequest): AnalyzeResponse {
  return req.options?.show_preferences ? withPreferencesResponse : happyResponse;
}
