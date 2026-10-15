/**
 * The evidence behind the reviewer's brief and the narrative map, placed in
 * the text (Codex review #3). The engine sends each placed sentence as an
 * EvidenceSpan: code-point offsets into the checked text (like a
 * suggestion's span), the quoted sentence, UTF-16 offsets, and for a
 * project of several files the file and the line. Pure helpers,
 * unit-tested in tests/unit/evidence.test.tsx.
 */
import type { EvidenceLink, EvidenceSpan, ScopeInfo, Suggestion } from "@researchly/contract";

/** Highlight ids for evidence start with this, so they never clash with a suggestion's id. */
const PREFIX = "evidence~";

export function evidenceId(span: Pick<EvidenceSpan, "start" | "end">): string {
  return `${PREFIX}${span.start}-${span.end}`;
}

export function isEvidenceId(id: string): boolean {
  return id.startsWith(PREFIX);
}

/** Whether a span can be shown: a real, non-empty stretch inside the checked text. */
export function placeable(span: EvidenceSpan | null | undefined, textLength: number): span is EvidenceSpan {
  return !!span && Number.isInteger(span.start) && Number.isInteger(span.end) && span.end > span.start && span.end <= textLength;
}

/**
 * The span as a highlight: a stand-in suggestion for resolveSpans() and
 * segment(), outlined in the text (never tinted: it is evidence, not a
 * finding). Its fields beyond the span are placeholders nothing renders.
 */
export function evidenceHighlight(span: EvidenceSpan): Suggestion {
  return {
    id: evidenceId(span),
    rule_id: "",
    rule_name: "",
    category: "improvement",
    tier: "lens",
    span: { start: span.start, end: span.end, line: span.line ?? 0, col: span.col ?? 0 },
    text: "",
    section: "",
    message: "",
    why: "",
    plain: "",
    source: "",
    fix_safety: "review",
    confidence: 1,
  };
}

/** "sections/discussion.tex, line 3" for a project of several files; null for one file. */
export function filePlace(span: Pick<EvidenceSpan, "file" | "file_line">): string | null {
  const file = (span.file ?? "").trim();
  if (!file) return null;
  return span.file_line ? `${file}, line ${span.file_line.toLocaleString("en-GB")}` : file;
}

/** The small word beside a claim's evidence, in the brief's vocabulary: never colour alone. */
export function evidenceStatusWord(status: EvidenceLink["evidence_status"]): string | null {
  if (status === "detected") return "found nearby";
  if (status === "not_detected") return "not detected";
  return null;
}

/** A stable key for a "Show in text" button, so focus can come back to it. */
export function showKey(where: string, span: Pick<EvidenceSpan, "start" | "end">): string {
  return `${where}:${span.start}-${span.end}`;
}

/* ---------- scope (Codex review #4) ---------- */

export type ScopeChoice = "auto" | "whole" | "chapter" | "excerpt";

export const SCOPE_OPTIONS: readonly { value: ScopeChoice; label: string }[] = [
  { value: "auto", label: "Auto" },
  { value: "whole", label: "Whole document" },
  { value: "chapter", label: "Chapter" },
  { value: "excerpt", label: "Excerpt" },
];

/** The line saying what the check assumed, or null from an engine that does not say. */
export function scopeNote(scope: ScopeInfo | null | undefined): string | null {
  const note = (scope?.note ?? "").trim();
  return note || null;
}
