/**
 * Engine responses for the mocked e2e runs. Each is a typed object that
 * `satisfies` the contract, so a contract change breaks the build of the
 * tests instead of silently drifting.
 */
import type {
  AnalyzeRequest,
  AnalyzeResponse,
  DocumentType,
  ErrorResponse,
  ProfileChoice,
  ProfileInfo,
  ReviewReport,
  RuleInfo,
  Suggestion,
  TierHealth,
} from "@researchly/contract";
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

/* ---------- S4: article types and the reviewer's brief ---------- */

/** GET /v1/rules `profiles`, as the engine lists them (packages/core/researchly/profiles.py), in display order. */
export const PROFILES: ProfileChoice[] = [
  { id: "auto", label: "Auto", summary: "Guess from the headings; otherwise general." },
  { id: "general", label: "General", summary: "Any research prose: every check on, sections from the headings." },
  { id: "manuscript", label: "Research article", summary: "A journal article with introduction, methods, results and discussion." },
  { id: "thesis-chapter", label: "Thesis chapter", summary: "One chapter of a thesis; sections as the chapter has them." },
  { id: "abstract", label: "Abstract", summary: "An abstract on its own: the six-move check runs on the whole text." },
  { id: "commentary", label: "Commentary", summary: "An opinion or perspective piece: argued, not reported." },
  { id: "policy-brief", label: "Policy brief", summary: "Evidence for decision-makers: context, evidence, options, recommendations." },
  { id: "grant", label: "Grant proposal", summary: "Aims, background and approach for a funder." },
  { id: "response-to-reviewers", label: "Response to reviewers", summary: "Point-by-point replies; the manuscript's own checks do not apply." },
];

export const COMMENTARY_NOTE =
  "Checked as a commentary: it may argue assertively, so the hedging prompts are off; no research gap is expected; there is no abstract to judge.";

/** The profile a check ran under, as the engine reports it for a requested type ("auto" guesses from the sample's headings). */
export function profileFor(type: DocumentType | null | undefined): ProfileInfo {
  if (!type || type === "auto") return { id: "manuscript", label: "Research article", guessed: true, note: "", rules_off: [] };
  const choice = PROFILES.find((p) => p.id === type)!;
  const commentary = type === "commentary";
  return {
    id: type,
    label: choice.label,
    guessed: false,
    note: commentary ? COMMENTARY_NOTE : "",
    rules_off: commentary ? ["AB801", "AB802", "C302", "C303", "D902"] : [],
  };
}

export const REVIEW_SOURCE =
  "M. Wallace & A. Wray (2016), Critical Reading and Writing for Postgraduates, 3rd ed., SAGE; Amriit's learnings from scientific-writing training (Researchly notes)";

/** The critical reader's brief for SAMPLE_TEXT. Synthetic; the evidence sentences are the sample's own. */
export const REVIEW: ReviewReport = {
  source: REVIEW_SOURCE,
  sections: ["introduction", "methods", "discussion"],
  words: 74,
  questions: [
    {
      id: "A",
      question: "Why am I reading this?",
      verdict: "Yours to answer: what do you need from this document?",
      points: ["The brief below reads it as a sceptical reader would, from the evidence in the text alone."],
      evidence: [],
    },
    {
      id: "B",
      question: "What are the authors trying to achieve?",
      verdict: "No sentence says what this document sets out to answer.",
      points: ["Where does the reader learn what question this document answers? One sentence near the end of the introduction usually does it."],
      evidence: [],
    },
    {
      id: "C",
      question: "What are they claiming?",
      verdict: "1 causal claim the design must carry.",
      points: ["vector control reduces transmission"],
      evidence: ["It is clearly proven that vector control reduces transmission."],
    },
    {
      id: "D",
      question: "How convincing are the claims?",
      verdict: "3 things weaken the claims; see the points.",
      points: [
        "No gap statement found: the reader is not told what was missing before this work, so the demand for it is unstated.",
        "Calibration: balanced (1.5:1) (hedges 4.05 per 100 words against boosters 2.7).",
        "1 overclaiming verb such as 'prove' or 'conclusively': reserve strong verbs for strong evidence.",
        "No limitations section: the reviewer will supply the rebuttal instead.",
      ],
      evidence: [],
    },
    {
      id: "E",
      question: "What use can be made of this?",
      verdict: "No sentence says what a reader can do with this.",
      points: ["The ending never widens back out: say what should change in the field or in practice, and for whom."],
      evidence: ["This could potentially suggest seasonal forcing."],
    },
  ],
  top_rules: [
    { id: "S010", short: "Repeated word", count: 2 },
    { id: "C201", short: "Booster overclaims certainty", count: 1 },
  ],
};

/** show_preferences: false — the engine withholds preferences and reports how many. */
export const happyResponse = {
  schema_version: "1",
  signed_in: false,
  warnings: [],
  suggestions: withoutPrefs,
  counts: countsOf(withoutPrefs),
  hidden_preferences: prefsOnly.length,
  metrics,
  sections_detected: ["introduction", "methods", "discussion"],
  health: healthy,
  engine,
  elapsed_ms: 412,
  mode: "revise",
  hidden_by_mode: 0,
  profile: profileFor("auto"),
  review: REVIEW,
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

/** Code-point offset of `needle` in SAMPLE_TEXT (Python indices, as the engine counts). */
function cp(needle: string): number {
  const i = SAMPLE_TEXT.indexOf(needle);
  if (i < 0) throw new Error(`fixture needle not found: ${needle}`);
  return Array.from(SAMPLE_TEXT.slice(0, i)).length;
}

/** A document-wide suggestion (rule scope "document"): one spelling of a compound differs elsewhere. Synthetic. */
export const compoundSuggestion: Suggestion = {
  id: "e2e-compound-1",
  rule_id: "W211",
  rule_name: "Compound spelled two ways",
  category: "convention",
  tier: "craft",
  span: { start: cp("South-East"), end: cp("South-East") + "South-East".length, line: 2, col: 42 },
  section: "introduction",
  message: "‘South-East’ is also written ‘Southeast’ elsewhere in this text.",
  why: "A compound written two ways reads as two terms. Pick one spelling and use it throughout.",
  plain: "In everyday words: the same advice, written for a reader who knows their science but not the grammar terms.",
  source: "The Craft of Scientific Writing §6",
  learn_ref: null,
  replacement: null,
  fix_safety: "review",
  confidence: 1,
  text: "South-East",
};

/** The happy response plus one document-wide suggestion (9 shown). */
export const withDocumentWideResponse = {
  ...happyResponse,
  suggestions: [...withoutPrefs, compoundSuggestion],
  counts: countsOf([...withoutPrefs, compoundSuggestion]),
} satisfies AnalyzeResponse;

/** GET /v1/rules, as the mocked engine answers it: scopes for the rules the fixtures use. */
export const RULES_REGISTRY: RuleInfo[] = ["C201", "P110", "V305", "V310", "G110", "C120", "S010", "D401", "C205", "P120", "W211"].map((id) => ({
  id,
  name: id,
  short: "A synthetic rule for the e2e suite.",
  why: "w",
  plain: "In everyday words: the same advice, written for a reader who knows their science but not the grammar terms.",
  source: "s",
  category: "improvement",
  tier: "craft",
  fix_safety: "review",
  scope: id === "W211" ? "document" : "sentence",
}));

/** Pick the right success fixture for a request, as the real engine would: preferences, the profile asked for, the brief only when asked. */
export function responseFor(req: AnalyzeRequest): AnalyzeResponse {
  const base = req.options?.show_preferences ? withPreferencesResponse : happyResponse;
  return { ...base, profile: profileFor(req.options?.document_type), review: req.options?.review ? REVIEW : null };
}
