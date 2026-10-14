"use client";

import { useId, useState } from "react";
import type { ChecklistItem, ChecklistReport } from "@researchly/contract";
import {
  checklistTally,
  editionLine,
  itemRefsLine,
  itemStatus,
  markAnnouncement,
  NO_MARKS,
  type ChecklistMark,
  type ChecklistMarks,
} from "@/lib/checklists";
import { itemStatusWord, type ChecklistState } from "@/lib/word/checklist";
import { ChecklistDetail, ChecklistMarkButtons } from "../ChecklistParts";

interface Props {
  state: ChecklistState;
  /** Switches to Revise and checks again (the pane's stage control). */
  onSwitchToRevise?: () => void;
  /** The writer's calls in this check: confirmed or not applicable (never stored, never sent). */
  marks?: ChecklistMarks;
  /** Presses or releases one of an item's calls. Without it the list has no controls. */
  onMark?: (id: string, mark: ChecklistMark) => void;
}

/**
 * The reporting checklist in the Word pane (S4c; cautious statuses since
 * Codex review N1): the website's checklist in a narrow column. The
 * guideline, "Selected themes of <edition> — not a full compliance check",
 * the tally in words and the engine's note; then one row per item with its
 * topic and status ("Found — please confirm", "Partly there", "Needs your
 * check", or the writer's call), the guideline's item numbers, the
 * question, and what it rests on: each part of a compound question with
 * its state, the writer's own sentence quoted, or the plain reason it
 * matters, with any sentence the engine did not count said quietly. The
 * writer can say "Confirmed by me" or "Not applicable" for this check;
 * neither is stored or sent. Reporting only, never the science. No meter,
 * no colour by status, no score.
 */
export function WordChecklist({ state, onSwitchToRevise, marks = NO_MARKS, onMark }: Props) {
  const idBase = useId();
  const [said, setSaid] = useState("");
  if (state.kind === "needs_revise") {
    return (
      <p className="brief-line" data-testid="checklist-needs-revise">
        <span>The reporting checklist reads the whole document, so it needs Revise mode.</span>
        {onSwitchToRevise ? (
          <button type="button" className="btn-link" onClick={onSwitchToRevise} data-testid="checklist-switch-revise">
            Switch to Revise
          </button>
        ) : null}
      </p>
    );
  }
  if (state.kind === "none_suggested") {
    return (
      <p className="brief-line" data-testid="checklist-none">
        Nothing in the text points to a reporting checklist. Choose one under Reporting checklist to check against it.
      </p>
    );
  }
  if (state.kind === "missing") {
    return (
      <p className="brief-line" data-testid="checklist-missing">
        This engine did not return a reporting checklist for this check.
      </p>
    );
  }
  const r = state.report;
  const mark = onMark
    ? (id: string, m: ChecklistMark) => {
        const it = r.items.find((x) => x.id === id);
        if (it) setSaid(markAnnouncement(it.topic, m, marks.get(id) !== m));
        onMark(id, m);
      }
    : undefined;
  return (
    <div className="wchecklist" data-testid="word-checklist">
      <h3 className="wchecklist-title">
        {r.label} <span className="wchecklist-design">for {r.design}</span>
      </h3>
      <p className="wchecklist-edition" data-testid="checklist-edition">
        {editionLine(r)}
      </p>
      <p className="wchecklist-tally" data-testid="checklist-tally">
        {checklistTally(r, marks)}
      </p>
      <p className="help wchecklist-note" data-testid="checklist-note">
        {r.note}
      </p>
      <ol className="wchecklist-items">
        {r.items.map((item) => (
          <Item key={item.id} item={item} report={r} mark={marks.get(item.id)} onMark={mark} titleId={`${idBase}-${item.id}`} />
        ))}
      </ol>
      <p className="card-source">
        <span className="card-source-label">Source:</span> <cite>{r.source}</cite>
      </p>
      {onMark ? (
        <p className="sr-only" role="status" aria-live="polite" aria-atomic="true" data-testid="checklist-live">
          {said}
        </p>
      ) : null}
    </div>
  );
}

function Item({
  item,
  report,
  mark,
  onMark,
  titleId,
}: {
  item: ChecklistItem;
  report: ChecklistReport;
  mark: ChecklistMark | undefined;
  onMark?: (id: string, mark: ChecklistMark) => void;
  titleId: string;
}) {
  const status = itemStatus(item);
  // The engine's prompt is set in italic; a found item and the writer's own call are set upright. Never a colour.
  const statusClass = !mark && status === "needs_check" ? "wchecklist-status wchecklist-status-check" : "wchecklist-status";
  return (
    <li className="wchecklist-item" data-testid="checklist-item" data-item={item.id} data-status={status} data-mark={mark ?? "none"}>
      <p className="wchecklist-topic">
        <span className="wchecklist-topic-name" id={titleId}>
          {item.topic}
        </span>
        <span className={statusClass} data-testid="checklist-status">
          {itemStatusWord(item, mark)}
        </span>
      </p>
      <p className="wchecklist-refs" data-testid="checklist-refs">
        {itemRefsLine(item, report)}
      </p>
      <p className="wchecklist-question">{item.question}</p>
      <ChecklistDetail item={item} mark={mark} />
      {onMark ? <ChecklistMarkButtons item={item} mark={mark} onMark={onMark} describedBy={titleId} /> : null}
    </li>
  );
}
