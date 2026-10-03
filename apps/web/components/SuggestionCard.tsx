"use client";

import { memo, type MouseEvent } from "react";
import type { Suggestion } from "@researchly/contract";
import { categoryMeta, sectionLabel, tierLabel } from "@/lib/categories";
import { dictionaryCandidate, isRuleId } from "@/lib/settings";
import { CategoryBadge } from "./CategoryIcon";

interface Props {
  suggestion: Suggestion;
  active: boolean;
  /** False when the span could not be placed in the text (out of range). */
  placeable: boolean;
  onShowInText: (id: string) => void;
  /** For a multi-file upload: the file and line the suggestion is in. */
  location?: string | null;
  /** Signed in only: account actions. Absent signed out, so the card is exactly as in S1. */
  actions?: CardActions | null;
}

export interface CardActions {
  onMute: (s: Suggestion) => void;
  /** Only offered for spelling suggestions whose flagged text is one dictionary word. */
  onAddWord: (s: Suggestion, word: string) => void;
  /** An account action is in flight: buttons are announced as unavailable. */
  busy: boolean;
}

const MAX_QUOTE = 160;

function quote(text: string): string {
  const t = text.replace(/\s+/g, " ").trim();
  return t.length > MAX_QUOTE ? `${t.slice(0, MAX_QUOTE - 1)}…` : t;
}

export const SuggestionCard = memo(function SuggestionCard({
  suggestion: s,
  active,
  placeable,
  onShowInText,
  location,
  actions,
}: Props) {
  const meta = categoryMeta(s.category);
  const section = sectionLabel(s.section);
  const msgId = `msg-${s.id}`;
  const word = actions && s.tier === "spelling" ? dictionaryCandidate(s.text) : null;
  // Only ids the settings table accepts can be muted (e.g. "G101").
  const mutable = isRuleId(s.rule_id);
  const hasActions = Boolean(actions && (mutable || word));

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
      {location ? (
        <p className="card-location" data-testid="card-location">
          <span className="sr-only">In file: </span>
          {location}
        </p>
      ) : null}
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
      <div className={`card-foot${hasActions ? " card-foot-actions" : ""}`}>
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
        {actions && hasActions ? (
          <div className="card-actions">
            {mutable ? (
              <button
                type="button"
                className="btn-link btn-link-quiet"
                aria-describedby={msgId}
                aria-disabled={actions.busy || undefined}
                onClick={() => {
                  if (!actions.busy) actions.onMute(s);
                }}
                data-testid="mute-rule"
              >
                Mute this rule
              </button>
            ) : null}
            {word ? (
              <button
                type="button"
                className="btn-link btn-link-quiet"
                aria-disabled={actions.busy || undefined}
                onClick={() => {
                  if (!actions.busy) actions.onAddWord(s, word);
                }}
                data-testid="add-word"
              >
                {/* One text run: a flex button would drop the spaces between separate nodes. */}
                <span>
                  Add <q translate="no">{word}</q> to dictionary
                </span>
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </article>
  );
});
