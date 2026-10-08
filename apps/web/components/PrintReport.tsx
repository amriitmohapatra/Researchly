"use client";

import { useMemo } from "react";
import type { AnalyzeResponse, SourceInfo, Suggestion } from "@researchly/contract";
import { categoryMeta, countByCategory, CATEGORIES, CATEGORY_ORDER, sectionLabel } from "@/lib/categories";
import { markNumbers, numberSuggestions, printedAt, reportTitle } from "@/lib/print";
import { briefState, profileLine } from "@/lib/profiles";
import { isDocumentWide, type ScopeMap } from "@/lib/scope";
import { resolveSpans, segment } from "@/lib/segments";
import { shownSuggestions } from "@/lib/view";
import { ReviewBrief } from "./ReviewBrief";

interface Props {
  data: AnalyzeResponse;
  submittedText: string;
  showPreferences: boolean;
  source?: SourceInfo | null;
  scopes?: ScopeMap | null;
  /** The moment the report was asked for; fixed by the caller so a re-render does not move it. */
  at: Date;
}

/**
 * One check on paper (S4): the text with its highlights numbered on the
 * left, the suggestions under the same numbers on the right, then the
 * reviewer's brief on its own page. Rendered only for printing (the
 * stylesheet hides it on screen and hides everything else on paper) and
 * mounted only while the print dialog is open, so a long document is not
 * laid out twice for nothing. Everything here is the same data the screen
 * shows; nothing is sent anywhere to make it.
 */
export function PrintReport({ data, submittedText, showPreferences, source, scopes = null, at }: Props) {
  const shown = useMemo(() => shownSuggestions(data, showPreferences), [data, showPreferences]);
  const inText = useMemo(() => shown.filter((s) => !isDocumentWide(s.rule_id, scopes)), [shown, scopes]);
  const wholeDocument = useMemo(() => shown.filter((s) => isDocumentWide(s.rule_id, scopes)), [shown, scopes]);
  const numbers = useMemo(() => numberSuggestions(inText, wholeDocument), [inText, wholeDocument]);
  const segments = useMemo(() => segment(submittedText, resolveSpans(submittedText, shown)), [submittedText, shown]);
  const counts = countByCategory(shown);
  const countLine = CATEGORY_ORDER.filter((c) => counts[c] > 0)
    .map((c) => `${counts[c]} ${(counts[c] === 1 ? CATEGORIES[c].label : CATEGORIES[c].plural).toLowerCase()}`)
    .join(", ");
  const sections = data.sections_detected.map(sectionLabel).filter((s): s is string => s !== null);
  const profile = profileLine(data.profile);
  const brief = briefState(data);

  const item = (s: Suggestion) => {
    const plain = s.plain.trim() || s.why.trim();
    return (
      <li key={s.id} className={`print-card print-card-${categoryMeta(s.category).id}`} data-testid="print-card">
        <p className="print-card-head">
          <span className="print-n">{numbers.get(s.id)}</span>
          <span className="print-cat">{categoryMeta(s.category).label}</span>
          {s.section && sectionLabel(s.section) ? <span className="print-sec">{sectionLabel(s.section)}</span> : null}
        </p>
        <p className="print-msg">{s.message}</p>
        {s.replacement !== null && s.replacement !== undefined ? (
          <p className="print-repl">Suggested revision (your call): {s.replacement === "" ? <em>remove this</em> : <q>{s.replacement}</q>}</p>
        ) : null}
        {plain ? <p className="print-plain">{plain}</p> : null}
        <p className="print-source">Source: {s.source}</p>
      </li>
    );
  };

  return (
    <div className="print-report" data-testid="print-report">
      <header className="print-head">
        <h1>{reportTitle(source)}</h1>
        <p className="print-meta">
          {printedAt(at)}
          {" · "}
          {shown.length === 0 ? "No suggestions" : `${shown.length} ${shown.length === 1 ? "suggestion" : "suggestions"}`}
          {countLine ? ` (${countLine})` : ""}
          {" · "}
          {sections.length > 0 ? `Sections: ${sections.join(", ")}` : "No section headings detected"}
          {data.mode === "draft" ? " · Draft mode" : ""}
        </p>
        {profile ? <p className="print-meta">{profile}</p> : null}
        <p className="print-key">
          Each highlight carries the number of its suggestion. Corrections are likely errors; improvements would read more
          easily revised; conventions are norms you may choose to follow; preferences are matters of taste.
        </p>
      </header>

      <section className="print-grid" aria-label="Your text and the suggestions, side by side">
        <div className="print-doc">
          <h2>{source ? "Your file, as Researchly read it" : "Your text"}</h2>
          <div className="print-text">
            {segments.map((s) => {
              if (s.kind === "point") {
                const ns = markNumbers(s, numbers);
                return ns.length > 0 ? (
                  <sup key={`p${s.at}`} className="print-ref">
                    {ns.join(",")}
                  </sup>
                ) : null;
              }
              if (s.ids.length === 0) return <span key={`t${s.start}`}>{s.text}</span>;
              const ns = markNumbers(s, numbers);
              return (
                <mark key={`m${s.start}`} className={`print-hl print-hl-${categoryMeta(s.category ?? "improvement").id}`} data-testid="print-mark">
                  {s.text}
                  {ns.length > 0 ? <sup className="print-ref">{ns.join(",")}</sup> : null}
                </mark>
              );
            })}
          </div>
        </div>
        <div className="print-list">
          <h2>Suggestions</h2>
          {inText.length === 0 && wholeDocument.length === 0 ? <p className="print-muted">None of the checks fired on this text.</p> : null}
          {inText.length > 0 ? <ol className="print-cards">{inText.map(item)}</ol> : null}
          {wholeDocument.length > 0 ? (
            <>
              <h3>Whole document</h3>
              <p className="print-muted">Checks that read the whole text, such as figure references and abbreviations defined once.</p>
              <ol className="print-cards">{wholeDocument.map(item)}</ol>
            </>
          ) : null}
        </div>
      </section>

      <section className="print-brief" aria-label="Reviewer's brief">
        <h2>Reviewer&rsquo;s brief</h2>
        {brief.kind === "ready" ? (
          <ReviewBrief state={brief} />
        ) : brief.kind === "needs_revise" ? (
          <p className="print-muted">This check ran in Draft mode, which has no brief. Check again in Revise mode to include it.</p>
        ) : (
          <p className="print-muted">This engine did not return a brief for this check.</p>
        )}
      </section>

      <footer className="print-foot">
        Made in your browser from one check by engine {data.engine.service_version} (core {data.engine.core_version}). Nothing
        was sent anywhere to produce this page, and Researchly stored nothing.
      </footer>
    </div>
  );
}
