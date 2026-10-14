"use client";

import { createContext, memo, useContext, type ButtonHTMLAttributes, type MouseEvent } from "react";
import type { WordSuggestion } from "@researchly/contract";
import { categoryMeta, sectionLabel } from "@/lib/categories";
import { dictionaryCandidate, isRuleId } from "@/lib/settings";
import { CategoryBadge } from "../CategoryIcon";
import { REASONING_LABEL } from "../SuggestionCard";
import { TableEvidence } from "../TableEvidence";

export interface CardNote {
  tone: "ok" | "info" | "problem";
  text: string;
}

export interface WordCardActions {
  onMute: (s: WordSuggestion) => void;
  onAddWord: (s: WordSuggestion, word: string) => void;
}

interface Props {
  suggestion: WordSuggestion;
  active: boolean;
  /** The fix was applied in the document: the card stays, its actions go. */
  applied: boolean;
  /**
   * An edit in this paragraph may have moved the words, or an Apply ended in
   * an unknown state: no Apply until the document is checked again, so a
   * possibly-made edit is never repeated blindly (Codex review R3).
   */
  stale?: boolean;
  note: CardNote | null;
  onSelect: (s: WordSuggestion) => void;
  onApply: (s: WordSuggestion) => void;
  /** Signed in only. Absent signed out: the card has no account actions. */
  actions: WordCardActions | null;
}

/**
 * Word is busy with another action, or a check is running: every card's
 * buttons say so and do nothing. A context rather than a card prop, so the
 * switch on and off around each "Show in document" re-renders these
 * buttons, not every card (2026-10-14 performance pass: on 1,200 cards a
 * click on one card re-rendered all of them twice).
 */
export const WordBusyContext = createContext(false);

function BusyButton({ onPress, ...rest }: Omit<ButtonHTMLAttributes<HTMLButtonElement>, "onClick" | "type"> & { onPress: () => void }) {
  const busy = useContext(WordBusyContext);
  return (
    <button
      type="button"
      {...rest}
      aria-disabled={busy || undefined}
      onClick={() => {
        if (!busy) onPress();
      }}
    />
  );
}

const MAX_QUOTE = 140;

function quote(text: string): string {
  const t = text.replace(/\s+/g, " ").trim();
  return t.length > MAX_QUOTE ? `${t.slice(0, MAX_QUOTE - 1)}…` : t;
}

/**
 * One suggestion in the taskpane. Reads like the web checker's card
 * (DESIGN.md): category and section, what was noticed, the flagged words,
 * the revision (your call), the explanation in everyday words, the full
 * reasoning behind a disclosure, then the source. Clicking the card selects
 * the words in the document; "Apply" appears only when the engine proposed
 * a concrete revision.
 */
export const WordCard = memo(function WordCard({ suggestion: s, active, applied, stale = false, note, onSelect, onApply, actions }: Props) {
  const meta = categoryMeta(s.category);
  const section = sectionLabel(s.section);
  const msgId = `wmsg-${s.id}`;
  const word = actions && s.tier === "spelling" ? dictionaryCandidate(s.text) : null;
  const mutable = Boolean(actions) && isRuleId(s.rule_id);
  const hasFix = s.replacement !== null && s.replacement !== undefined;
  const plain = s.plain.trim() || s.why.trim();
  const reasoning = s.plain.trim() && s.why.trim() && s.why.trim() !== plain ? s.why.trim() : null;

  const onClick = (e: MouseEvent<HTMLElement>) => {
    if ((e.target as HTMLElement).closest("button, summary, a, .why-body")) return;
    onSelect(s);
  };

  return (
    <article
      className={`card card-${meta.id} wcard${active ? " is-active" : ""}${applied ? " is-applied" : ""}`}
      aria-labelledby={msgId}
      onClick={onClick}
      data-testid="word-card"
      data-rule={s.rule_id}
      data-tier={s.tier}
      data-category={meta.id}
      data-paragraph={s.location.paragraph}
      data-stale={stale || undefined}
    >
      <div className="card-head">
        <CategoryBadge category={meta.id} />
        {section ? (
          <span className="card-section">
            <span className="sr-only">Section: </span>
            {section}
          </span>
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
      {s.table_evidence ? <TableEvidence evidence={s.table_evidence} /> : null}
      {hasFix ? (
        <p className="card-repl">
          <span className="card-repl-label">Suggested revision (your call):</span>{" "}
          {s.replacement === "" ? <em>remove this</em> : <q>{s.replacement}</q>}
        </p>
      ) : null}
      {plain ? (
        <p className="card-plain" data-testid="card-plain">
          {plain}
        </p>
      ) : null}
      {reasoning ? (
        <details className="why" data-testid="card-reasoning">
          <summary>{REASONING_LABEL}</summary>
          <div className="why-body">
            <p>{reasoning}</p>
          </div>
        </details>
      ) : null}
      <p className="card-source">
        <span className="card-source-label">Source:</span> <cite>{s.source}</cite>
      </p>

      {note ? (
        <p className={`wcard-note wcard-note-${note.tone}`} role={note.tone === "problem" ? "alert" : "status"} data-testid="card-note">
          {note.text}
        </p>
      ) : null}

      <div className="wcard-actions">
        <BusyButton
          className="btn btn-quiet btn-compact"
          aria-describedby={msgId}
          onPress={() => onSelect(s)}
          data-testid="select-in-document"
        >
          Show in document
        </BusyButton>
        {hasFix && !applied && !stale ? (
          <BusyButton
            className="btn btn-secondary btn-compact"
            aria-describedby={msgId}
            onPress={() => onApply(s)}
            data-testid="apply-fix"
          >
            {s.replacement === "" ? "Remove in document" : "Apply in document"}
          </BusyButton>
        ) : null}
      </div>

      {actions && (mutable || word) ? (
        <div className="card-foot card-actions">
          {mutable ? (
            <BusyButton
              className="btn-link btn-link-quiet"
              aria-describedby={msgId}
              onPress={() => actions.onMute(s)}
              data-testid="mute-rule"
            >
              Mute this rule
            </BusyButton>
          ) : null}
          {word ? (
            <BusyButton className="btn-link btn-link-quiet" onPress={() => actions.onAddWord(s, word)} data-testid="add-word">
              <span>
                Add <q translate="no">{word}</q> to dictionary
              </span>
            </BusyButton>
          ) : null}
        </div>
      ) : null}
    </article>
  );
});
