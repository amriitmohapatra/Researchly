"use client";

import type { ReactNode } from "react";
import type { EvidenceSpan, ReviewQuestion } from "@researchly/contract";
import { briefStatusWord, timesPhrase, type BriefState } from "@/lib/profiles";
import { EvidenceLinks, type ShowInText } from "./EvidenceLinks";

interface Props {
  state: BriefState;
  /** When the surface has a Draft/Revise control: switches to Revise and checks again. */
  onSwitchToRevise?: () => void;
  /** "Show in text" on each sentence a question rests on (Codex review #3); absent on paper. */
  onShowInText?: ShowInText | null;
  /** Whether this surface can show a span (the website: in the checked text; Word: with a location). */
  canShow?: (span: EvidenceSpan) => boolean;
  /** What the check assumed about how much of the document this is, with its override (Codex review #4). */
  scopeLine?: ReactNode;
}

/**
 * The critical reader's brief (S4): five questions a sceptical reader asks
 * of any document, each answered from the text alone. Read top to bottom
 * as a document: the question with a small word saying what its answer
 * rests on (detected, not detected, not assessed, not applicable; Codex
 * review R4), the one-line verdict, the points behind it, and the
 * sentences it rests on, quoted. Then the checks that fired most, the
 * engine's disclaimer (the brief does not establish whether the science is
 * sound), and the source as a reference, set like a card's. Never a score:
 * no numbers but a rule's tally, no meters, no colour by verdict or status.
 * Question A is the writer's to answer and is rendered as the engine gives it.
 */
export function ReviewBrief({ state, onSwitchToRevise, onShowInText = null, canShow, scopeLine = null }: Props) {
  if (state.kind === "needs_revise") {
    return (
      <p className="brief-line" data-testid="brief-needs-revise">
        <span>The reviewer&rsquo;s brief reads the whole document, so it needs Revise mode.</span>
        {onSwitchToRevise ? (
          <button type="button" className="btn-link" onClick={onSwitchToRevise} data-testid="brief-switch-revise">
            Switch to Revise
          </button>
        ) : null}
      </p>
    );
  }
  if (state.kind === "missing") {
    return (
      <p className="brief-line" data-testid="brief-missing">
        This engine did not return a brief for this check.
      </p>
    );
  }
  const r = state.review;
  return (
    <div className="brief" data-testid="brief">
      <p className="help brief-intro">
        Five questions a critical reader asks of any document, answered from your text alone. Not a score.
      </p>
      {scopeLine}
      <ol className="brief-questions">
        {r.questions.map((q) => (
          <li key={q.id} className="brief-q" data-testid="brief-question" data-question={q.id}>
            <Question q={q} onShow={onShowInText} canShow={canShow} />
          </li>
        ))}
      </ol>
      {(r.top_rules?.length ?? 0) > 0 ? (
        <section className="brief-rules" aria-labelledby="brief-rules-title" data-testid="brief-rules">
          <h4 id="brief-rules-title" className="col-title">
            Most frequent checks
          </h4>
          <ul className="brief-rules-list">
            {r.top_rules!.map((t) => (
              <li key={t.id}>
                <span>{t.short}</span> <span className="brief-rule-count">{timesPhrase(t.count)}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {r.disclaimer?.trim() ? (
        <p className="brief-disclaimer" data-testid="brief-disclaimer">
          {r.disclaimer.trim()}
        </p>
      ) : null}
      <p className="card-source brief-source">
        <span className="card-source-label">Source:</span> <cite>{r.source}</cite>
      </p>
    </div>
  );
}

function Question({
  q,
  onShow,
  canShow,
}: {
  q: ReviewQuestion;
  onShow: ShowInText | null;
  canShow?: (span: EvidenceSpan) => boolean;
}) {
  const points = (q.points ?? []).filter((p) => p.trim());
  // Placed sentences replace the bare quotes they repeat; an older engine's quotes still show.
  const links = (q.links ?? []).filter((l) => l.claim && l.claim.text.trim());
  const evidence = links.length > 0 ? [] : (q.evidence ?? []).filter((e) => e.trim());
  const status = briefStatusWord(q.status);
  return (
    <>
      <h3 className="brief-q-title">
        <span className="brief-q-letter" aria-hidden="true">
          {q.id}
        </span>
        <span>
          <span className="sr-only">Question {q.id}: </span>
          {q.question}
          {status ? (
            <>
              {" "}
              <span className="sr-only">(</span>
              <span className="brief-q-status" data-testid="brief-status" data-status={q.status}>
                {status}
              </span>
              <span className="sr-only">)</span>
            </>
          ) : null}
        </span>
      </h3>
      <p className="brief-verdict">{q.verdict}</p>
      {points.length > 0 ? (
        <ul className="brief-points">
          {points.map((p, i) => (
            <li key={i}>{p}</li>
          ))}
        </ul>
      ) : null}
      <EvidenceLinks links={links} where={q.id} onShow={onShow} canShow={canShow} />
      {evidence.length > 0 ? (
        <ul className="brief-evidence" aria-label={`Evidence for question ${q.id}, quoted from your text`}>
          {evidence.map((e, i) => (
            <li key={i}>
              <q>{e.trim()}</q>
            </li>
          ))}
        </ul>
      ) : null}
    </>
  );
}
