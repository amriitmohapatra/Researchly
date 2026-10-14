"use client";

import type { TableEvidence as Evidence } from "@researchly/contract";
import { cellPlace, roundingNote } from "@/lib/table-evidence";

interface Props {
  evidence: Evidence;
  /** Website only: highlight the cell in the text. Absent where the cell cannot be shown. */
  onShowCell?: (() => void) | null;
}

/**
 * The cell an X401 card compared (Codex review #7): where it is, what it
 * holds, and what the sentence says, side by side. Numbers only, in the
 * table's own words; nothing is judged here that the message has not said.
 */
export function TableEvidence({ evidence: ev, onShowCell }: Props) {
  const rounding = roundingNote(ev);
  return (
    <div className="card-table" data-testid="card-table-evidence">
      <p className="card-table-place">
        <span className="sr-only">The table cell: </span>
        {cellPlace(ev)}
      </p>
      <dl className="card-table-values">
        <div>
          <dt>The table holds</dt>
          <dd data-testid="table-expected">{ev.expected}</dd>
        </div>
        <div>
          <dt>This sentence says</dt>
          <dd data-testid="table-quoted">{ev.quoted}</dd>
        </div>
      </dl>
      {rounding ? <p className="card-table-note">{rounding}</p> : null}
      {onShowCell ? (
        <button type="button" className="btn-link card-table-show" onClick={onShowCell} data-testid="show-cell">
          Show the cell
        </button>
      ) : null}
    </div>
  );
}
