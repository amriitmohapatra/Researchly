"use client";

import { memo, type MouseEvent } from "react";
import type { Suggestion } from "@researchly/contract";
import { categoryMeta, sectionLabel, tierLabel } from "@/lib/categories";
import { CategoryBadge } from "./CategoryIcon";

interface Props {
  suggestion: Suggestion;
  active: boolean;
  /** False when the span could not be placed in the text (out of range). */
  placeable: boolean;
  onShowInText: (id: string) => void;
}

const MAX_QUOTE = 160;

function quote(text: string): string {
  const t = text.replace(/\s+/g, " ").trim();
  return t.length > MAX_QUOTE ? `${t.slice(0, MAX_QUOTE - 1)}…` : t;
}

export const SuggestionCard = memo(function SuggestionCard({ suggestion: s, active, placeable, onShowInText }: Props) {
  const meta = categoryMeta(s.category);
  const section = sectionLabel(s.section);
  const msgId = `msg-${s.id}`;

  // Mouse convenience: clicking the card's body jumps to the text. Keyboard
  // users have the explicit "Show in text" button.
  const onClick = (e: MouseEvent<HTMLElement>) => {
    if (!placeable) return;
    if ((e.target as HTMLElement).closest("button, summary, a, .why-body")) return;
    onShowInText(s.id);
  };

  return (
    <article
      id={`card-${s.id}`}
      className={`card card-${meta.id}${active ? " is-active" : ""}`}
      aria-labelledby={msgId}
      tabIndex={-1}
      onClick={onClick}
      data-testid="suggestion-card"
      data-category={meta.id}
    >
      <div className="card-head">
        <CategoryBadge category={meta.id} />
        {section ? (
          <span className="card-section">
            <span className="sr-only">Section: </span>
            {section}
          </span>
        ) : null}
        {placeable ? (
          <button type="button" className="btn-link card-jump" onClick={() => onShowInText(s.id)}>
            Show in text
          </button>
        ) : null}
      </div>
      <p className="card-msg" id={msgId}>
        {s.message}
      </p>
      {s.text.trim() ? (
        <p className="card-quote">
          <span className="sr-only">Flagged text: </span>
          <q>{quote(s.text)}</q>
        </p>
      ) : null}
      {s.replacement !== null && s.replacement !== undefined ? (
        <p className="card-repl">
          <span className="card-repl-label">Suggested revision (your call):</span>{" "}
          {s.replacement === "" ? <em>remove this</em> : <q>{s.replacement}</q>}
        </p>
      ) : null}
      <p className="card-source">
        <span className="card-source-label">Source</span> <cite>{s.source}</cite>
      </p>
      <div className="card-foot">
        <details className="why">
          <summary>Why?</summary>
          <div className="why-body">
            <p>{s.why}</p>
            <dl className="why-meta">
              <div>
                <dt>Rule</dt>
                <dd>
                  <span translate="no">{s.rule_id}</span> · {s.rule_name}
                </dd>
              </div>
              <div>
                <dt>Checked by</dt>
                <dd>{tierLabel(s.tier)}</dd>
              </div>
            </dl>
          </div>
        </details>
      </div>
    </article>
  );
});
