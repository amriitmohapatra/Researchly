/**
 * The Label page's model (S4 exit check): verdicts on flags, exported in
 * exactly the format ml/eval/label_precision.py reads. Pure and unit-tested.
 *
 * A label holds the paragraph number, the rule id, the category, the
 * section and the verdict. Never the paragraph, never the flagged words:
 * the Python reader refuses a label with any other field.
 *
 * Attempts (Codex review N3, 2026-10-14): each check of a paragraph is an
 * attempt with an opaque random id (never derived from the text), and each
 * label names its attempt and its flag's position in that check. A changed
 * verdict replaces the label with the same attempt and flag; checking the
 * paragraph again replaces every label an earlier attempt gave it (the page
 * says so before the check); a failed or cancelled check changes nothing.
 * So a reload, a recheck after an edit, or two flags of one rule can never
 * leave duplicates or orphans for the evaluator.
 */
import type { Category } from "@researchly/contract";

export type Verdict = "useful" | "wrong" | "unsure";
export const VERDICTS: readonly Verdict[] = ["useful", "wrong", "unsure"];

/** The sections a labelled paragraph can be checked as (the guide asks for a spread across them). */
export const LABEL_SECTIONS = [
  { id: "introduction", label: "Introduction" },
  { id: "methods", label: "Methods" },
  { id: "results", label: "Results" },
  { id: "discussion", label: "Discussion" },
  { id: "abstract", label: "Abstract" },
  { id: "conclusion", label: "Conclusion" },
] as const;
export type LabelSection = (typeof LABEL_SECTIONS)[number]["id"];

/** The guide's target: fifty paragraphs. */
export const TARGET_PARAGRAPHS = 50;

export interface Label {
  paragraph: number;
  rule_id: string;
  category: Category | string;
  section: string;
  verdict: Verdict;
  /** The check (attempt) the flag came from: an opaque random id. */
  attempt?: string;
  /** The flag's position among that check's flags (0-based). */
  flag?: number;
}

/** What the page keeps between reloads: the paragraph being labelled, its current attempt and the labels so far. */
export interface LabelSession {
  paragraph: number;
  labels: Label[];
  /** The check of this paragraph whose flags are on screen; null before the first, and after a reload (the text is gone). */
  attempt?: string | null;
}

export const EMPTY_SESSION: LabelSession = { paragraph: 1, labels: [], attempt: null };

const ATTEMPT = /^[a-z0-9]{6,16}$/;

/** An opaque attempt id: random, never derived from the paragraph. */
export function newAttemptId(random: () => number = Math.random): string {
  let id = "";
  for (let i = 0; i < 10; i++) id += "abcdefghijklmnopqrstuvwxyz0123456789"[Math.floor(random() * 36)];
  return id;
}

export function isVerdict(v: unknown): v is Verdict {
  return typeof v === "string" && (VERDICTS as readonly string[]).includes(v);
}

export function isLabelSection(v: unknown): v is LabelSection {
  return typeof v === "string" && LABEL_SECTIONS.some((s) => s.id === v);
}

const SHORT = /^[A-Za-z0-9_.-]{1,40}$/;

/** One stored label, re-built field by field so nothing else (and never text) survives a round trip. */
function toLabel(x: unknown): Label | null {
  if (typeof x !== "object" || x === null) return null;
  const o = x as Record<string, unknown>;
  if (!isVerdict(o.verdict) || typeof o.rule_id !== "string" || !SHORT.test(o.rule_id)) return null;
  if (typeof o.paragraph !== "number" || !Number.isInteger(o.paragraph) || o.paragraph < 1) return null;
  const category = typeof o.category === "string" && SHORT.test(o.category) ? o.category : "unknown";
  const section = typeof o.section === "string" && SHORT.test(o.section) ? o.section : "unknown";
  const label: Label = { paragraph: o.paragraph, rule_id: o.rule_id, category, section, verdict: o.verdict };
  if (typeof o.attempt === "string" && ATTEMPT.test(o.attempt) && typeof o.flag === "number" && Number.isInteger(o.flag) && o.flag >= 0) {
    label.attempt = o.attempt;
    label.flag = o.flag;
  }
  return label;
}

/** A stored session, or the empty one when the store is missing, from an older page or tampered with. */
export function normaliseSession(raw: unknown): LabelSession {
  if (typeof raw !== "object" || raw === null) return EMPTY_SESSION;
  const o = raw as Record<string, unknown>;
  const labels = Array.isArray(o.labels) ? o.labels.map(toLabel).filter((l): l is Label => l !== null) : [];
  const last = labels.reduce((m, l) => Math.max(m, l.paragraph), 0);
  const p = typeof o.paragraph === "number" && Number.isInteger(o.paragraph) && o.paragraph >= 1 ? o.paragraph : 1;
  // After a reload the paragraph's text is gone, so its flags cannot be shown
  // again: the attempt is closed, and the next check of it replaces its labels.
  return { paragraph: Math.max(p, last), labels, attempt: null };
}

/** How many paragraphs have at least one label. */
export function paragraphsLabelled(s: LabelSession): number {
  return new Set(s.labels.map((l) => l.paragraph)).size;
}

/** "12 of 50 paragraphs, 37 flags labelled" */
export function progressLine(s: LabelSession): string {
  const p = paragraphsLabelled(s);
  const n = s.labels.length;
  return `${p} of ${TARGET_PARAGRAPHS} paragraphs, ${n.toLocaleString("en-GB")} ${n === 1 ? "flag" : "flags"} labelled`;
}

/**
 * Labels the current paragraph already has from earlier checks (another
 * attempt, or one before a reload): checking it again replaces them.
 */
export function labelsToReplace(s: LabelSession): number {
  return s.labels.filter((l) => l.paragraph === s.paragraph && (!l.attempt || l.attempt !== s.attempt)).length;
}

/**
 * A check of the current paragraph succeeded: it becomes the attempt on
 * screen, and every label the paragraph had from other attempts goes.
 */
export function startAttempt(s: LabelSession, attempt: string): LabelSession {
  return {
    ...s,
    attempt,
    labels: s.labels.filter((l) => l.paragraph !== s.paragraph || l.attempt === attempt),
  };
}

/**
 * Give flag number `flag` of the attempt on screen a verdict: a changed mind
 * replaces the label with the same attempt and flag, never adds a second.
 * Nothing happens without an attempt on screen.
 */
export function setVerdict(
  s: LabelSession,
  card: { flag: number; rule_id: string; category: string },
  section: string,
  verdict: Verdict,
): LabelSession {
  if (!s.attempt) return s;
  const label: Label = {
    paragraph: s.paragraph,
    rule_id: card.rule_id,
    category: card.category,
    section,
    verdict,
    attempt: s.attempt,
    flag: card.flag,
  };
  const at = s.labels.findIndex((l) => l.paragraph === s.paragraph && l.attempt === s.attempt && l.flag === card.flag);
  if (at >= 0) {
    const labels = [...s.labels];
    labels[at] = label;
    return { ...s, labels };
  }
  return { ...s, labels: [...s.labels, label] };
}

/** The verdict flag number `flag` of the attempt on screen holds, if any. */
export function verdictOf(s: LabelSession, flag: number): Verdict | null {
  if (!s.attempt) return null;
  return s.labels.find((l) => l.paragraph === s.paragraph && l.attempt === s.attempt && l.flag === flag)?.verdict ?? null;
}

/** "Next paragraph": the next number, once the current one has a label (an unlabelled paragraph keeps its number). */
export function nextParagraph(s: LabelSession): LabelSession {
  return s.labels.some((l) => l.paragraph === s.paragraph) ? { ...s, paragraph: s.paragraph + 1, attempt: null } : s;
}

/** The exported file: `{"version": 1, "labels": [...]}`, the five fields of each label plus its attempt and flag position, nothing else. */
export function exportLabels(s: LabelSession): { version: 1; labels: Label[] } {
  return {
    version: 1,
    labels: s.labels.map((l) => ({
      paragraph: l.paragraph,
      rule_id: l.rule_id,
      category: l.category,
      section: l.section,
      verdict: l.verdict,
      ...(l.attempt && l.flag !== undefined ? { attempt: l.attempt, flag: l.flag } : {}),
    })),
  };
}

export const EXPORT_FILENAME = "researchly-labels.json";

/** The file's text: pretty enough to read, exactly what the Python reader loads. */
export function exportText(s: LabelSession): string {
  return `${JSON.stringify(exportLabels(s), null, 2)}\n`;
}

/** The text sent to the engine: the section's name as a heading line above the paragraph (the section decides the advice). */
export function labelContent(section: LabelSection, paragraph: string): string {
  const name = LABEL_SECTIONS.find((s) => s.id === section)?.label ?? "Introduction";
  return `${name}\n\n${paragraph.trim()}\n`;
}
