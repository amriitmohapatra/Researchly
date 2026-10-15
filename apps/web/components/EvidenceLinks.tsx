"use client";

import type { EvidenceLink, EvidenceSpan } from "@researchly/contract";
import { evidenceStatusWord, filePlace, showKey } from "@/lib/evidence";

/** "Show in text": the website outlines the sentence, Word selects it. Absent (print, or nowhere to show it): no button. */
export type ShowInText = (span: EvidenceSpan, key: string) => void;

interface Props {
  links: readonly EvidenceLink[];
  /** Which question they belong to, for the accessible name and the button keys. */
  where: string;
  onShow?: ShowInText | null;
  /** Whether a span can be shown on this surface (in the checked text; a Word location). */
  canShow?: (span: EvidenceSpan) => boolean;
}

/**
 * The sentences a question of the brief rests on (Codex review #3): for
 * each, its kind in plain words, the writer's sentence quoted, and, for a
 * claim, the evidence proposed beside it, or what was not detected (never
 * a guessed link). "Show in text" on each sentence that can be placed.
 */
export function EvidenceLinks({ links, where, onShow = null, canShow }: Props) {
  if (links.length === 0) return null;
  return (
    <ul className="evl" aria-label={`Where question ${where} rests in your text`} data-testid="evidence-links">
      {links.map((l, i) => {
        const status = evidenceStatusWord(l.evidence_status);
        const weighed = l.evidence_status !== "not_applicable";
        return (
          <li
            key={`${l.kind}-${l.claim.start}-${i}`}
            className={`evl-item${weighed ? " evl-pair" : ""}`}
            data-testid="evidence-link"
            data-kind={l.kind}
          >
            <div className="evl-side">
              <p className="evl-label">{l.label}</p>
              <Quote span={l.claim} where={`${where}-claim-${i}`} onShow={onShow} canShow={canShow} />
            </div>
            {weighed ? (
              <div className="evl-side evl-evidence" data-testid="evidence-side" data-status={l.evidence_status}>
                <p className="evl-label">
                  Its evidence{status ? <span className="evl-status"> ({status})</span> : null}
                </p>
                {l.evidence ? <Quote span={l.evidence} where={`${where}-evidence-${i}`} onShow={onShow} canShow={canShow} /> : null}
                {l.evidence_note.trim() ? <p className="evl-note">{l.evidence_note.trim()}</p> : null}
              </div>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

/** The first words of a sentence, for a button's accessible name. */
export function shortQuote(text: string): string {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length <= 60 ? flat : `${flat.slice(0, 59).trimEnd()}…`;
}

/** One quoted sentence with its file and line (several files) and "Show in text". */
export function Quote({
  span,
  where,
  onShow,
  canShow,
}: {
  span: EvidenceSpan;
  where: string;
  onShow?: ShowInText | null;
  canShow?: (span: EvidenceSpan) => boolean;
}) {
  const place = filePlace(span);
  const key = showKey(where, span);
  const showable = !!onShow && (canShow ? canShow(span) : true);
  return (
    <div className="evl-quote">
      <blockquote className="evl-text">
        <q>{span.text.trim()}</q>
      </blockquote>
      {place || showable ? (
        <p className="evl-meta">
          {place ? <span className="evl-place">{place}</span> : null}
          {place && showable ? <span aria-hidden="true"> · </span> : null}
          {showable ? (
            <button
              type="button"
              className="btn-link evl-show"
              data-show-key={key}
              data-testid="show-evidence"
              aria-label={`Show in text: ${shortQuote(span.text)}`}
              onClick={() => onShow!(span, key)}
            >
              Show in text
            </button>
          ) : null}
        </p>
      ) : null}
    </div>
  );
}
