"use client";

import type { ChecklistItem } from "@researchly/contract";
import {
  canConfirm,
  itemStatus,
  notCountedLine,
  partState,
  sectionAbsentLine,
  shownParts,
  type ChecklistMark,
} from "@/lib/checklists";

/**
 * What a checklist item rests on, the same on the website, in Word and on
 * paper (Codex review N1): for a compound question each part with its
 * state ("Found", with the sentence that may report it, or "Needs your
 * check"); for a single question the sentence quoted in the serif; for an
 * item not yet found the plain reason it matters; then, quietly, a section
 * the document does not have and a matching sentence the engine did not
 * count, in the engine's own words. Nothing for an item the writer marked
 * not applicable: that is their call, and the status says so.
 */
export function ChecklistDetail({ item: it, mark }: { item: ChecklistItem; mark: ChecklistMark | undefined }) {
  if (mark === "not_applicable") return null;
  const status = itemStatus(it);
  const parts = shownParts(it);
  const evidence = (it.evidence ?? "").trim();
  const plain = it.plain.trim();
  const absent = sectionAbsentLine(it);
  const aside = it.not_counted && it.not_counted.quote.trim() ? it.not_counted : null;
  return (
    <>
      {parts.length > 0 ? (
        <ul className="checklist-parts" data-testid="checklist-parts">
          {parts.map((p) => {
            const quote = p.found ? (p.evidence ?? "").trim() : "";
            return (
              <li key={p.label} className="checklist-part" data-testid="checklist-part" data-found={p.found ? "true" : "false"}>
                <p className="checklist-part-line">
                  <span className="checklist-part-state">{partState(p)}:</span> {p.label}
                </p>
                {quote ? (
                  <blockquote className="checklist-evidence">
                    <span className="sr-only">Possible evidence: </span>
                    <q>{quote}</q>
                  </blockquote>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : status === "found" && evidence ? (
        <blockquote className="checklist-evidence">
          <span className="sr-only">Possible evidence: </span>
          <q>{evidence}</q>
        </blockquote>
      ) : null}
      {status !== "found" && plain ? <p className="checklist-plain">{plain}</p> : null}
      {absent ? (
        <p className="checklist-absent" data-testid="checklist-absent">
          {absent}
        </p>
      ) : null}
      {aside ? (
        <p className="checklist-aside" data-testid="checklist-not-counted" data-reason={aside.reason}>
          <span>{notCountedLine(aside)}</span> <q>{aside.quote.trim()}</q>
        </p>
      ) : null}
    </>
  );
}

/**
 * The writer's two calls on an item, for this check only (never stored,
 * never sent): "Confirmed by me" where the engine found possible evidence,
 * and "Not applicable" on every item. Toggle buttons (aria-pressed), each
 * described by the item's topic so a screen reader hears which item; the
 * label never changes, the pressed state is said by aria-pressed and shown
 * by a tick and weight, never by colour alone.
 */
export function ChecklistMarkButtons({
  item,
  mark,
  onMark,
  describedBy,
}: {
  item: ChecklistItem;
  mark: ChecklistMark | undefined;
  onMark: (id: string, mark: ChecklistMark) => void;
  describedBy: string;
}) {
  return (
    <p className="checklist-marks">
      {canConfirm(item) ? (
        <button
          type="button"
          className="btn-link btn-link-quiet checklist-mark checklist-confirm"
          aria-pressed={mark === "confirmed"}
          aria-describedby={describedBy}
          onClick={() => onMark(item.id, "confirmed")}
          data-testid="checklist-confirm"
        >
          Confirmed by me
        </button>
      ) : null}
      <button
        type="button"
        className="btn-link btn-link-quiet checklist-mark checklist-na"
        aria-pressed={mark === "not_applicable"}
        aria-describedby={describedBy}
        onClick={() => onMark(item.id, "not_applicable")}
        data-testid="checklist-na"
      >
        Not applicable
      </button>
    </p>
  );
}
