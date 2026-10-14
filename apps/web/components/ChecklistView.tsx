"use client";

import { useId, useState } from "react";
import type { ChecklistItem, ChecklistReport } from "@researchly/contract";
import {
  CHECKLIST_SCOPE_LINE,
  checklistTally,
  editionLine,
  itemRefsLine,
  itemStatus,
  markAnnouncement,
  statusWords,
  type ChecklistMark,
  type ChecklistMarks,
} from "@/lib/checklists";
import { sectionLabel } from "@/lib/categories";
import { ChecklistDetail, ChecklistMarkButtons } from "./ChecklistParts";

interface Props {
  report: ChecklistReport;
  /** The writer's calls in this session: confirmed or not applicable (never stored, never sent). */
  marks: ChecklistMarks;
  /** Screen only: presses or releases one of an item's calls. Absent on paper. */
  onMark?: (id: string, mark: ChecklistMark) => void;
  /** "screen" (default) or "print": on paper there are no controls, and the calls are said as the writer's. */
  variant?: "screen" | "print";
}

/**
 * The reporting checklist (S4; cautious statuses since Codex review N1):
 * the fourth view of a check, shown only when a checklist ran. Read top to
 * bottom as a document: the guideline and design, "Selected themes of
 * <edition>, not a full compliance check", the tally in words, the
 * engine's note, then every item in the guideline's order with its topic,
 * the guideline's own item numbers, its question and its status in words:
 * "Found: please confirm" (a matching sentence is possible evidence, not
 * proof), "Partly there" (each part of a compound question with its
 * state) or "Needs your check" (a prompt, never a verdict). The writer
 * can say "Confirmed by me" or "Not applicable" for this session; the
 * print keeps both calls apart from what the engine found. Then the
 * source and the line that bounds it: reporting only, never the science.
 * No colour by status, no meters, no score.
 */
export function ChecklistView({ report: r, marks, onMark, variant = "screen" }: Props) {
  const idBase = useId();
  const print = variant === "print";
  const voice = print ? "print" : "screen";
  const [said, setSaid] = useState("");
  const mark = onMark && !print
    ? (id: string, m: ChecklistMark) => {
        const it = r.items.find((x) => x.id === id);
        if (it) setSaid(markAnnouncement(it.topic, m, marks.get(id) !== m));
        onMark(id, m);
      }
    : undefined;
  return (
    <div className={`checklist${print ? " checklist-print" : ""}`} data-testid="checklist" data-checklist={r.id}>
      <p className="checklist-title">
        <span className="checklist-label">{r.label}</span>
        {r.design ? <span className="checklist-design muted"> for {r.design}</span> : null}
      </p>
      <p className="checklist-edition muted" data-testid="checklist-edition">
        {editionLine(r)}
      </p>
      <p className="checklist-tally" data-testid="checklist-tally">
        {checklistTally(r, marks, voice)}
      </p>
      {r.note.trim() ? (
        <p className="help checklist-note" data-testid="checklist-note">
          {r.note}
        </p>
      ) : null}
      <ol className="checklist-items">
        {r.items.map((it) => (
          <li
            key={it.id}
            className="checklist-item"
            data-testid="checklist-item"
            data-item={it.id}
            data-status={itemStatus(it)}
            data-mark={marks.get(it.id) ?? "none"}
          >
            <Item item={it} report={r} mark={marks.get(it.id)} onMark={mark} titleId={`${idBase}-${it.id}`} voice={voice} />
          </li>
        ))}
      </ol>
      <p className="card-source checklist-source">
        <span className="card-source-label">Source:</span> <cite>{r.source}</cite>
      </p>
      <p className="checklist-scope" data-testid="checklist-scope">
        {CHECKLIST_SCOPE_LINE}
      </p>
      {print ? null : (
        <p className="sr-only" role="status" aria-live="polite" aria-atomic="true" data-testid="checklist-live">
          {said}
        </p>
      )}
    </div>
  );
}

function Item({
  item: it,
  report,
  mark,
  onMark,
  titleId,
  voice,
}: {
  item: ChecklistItem;
  report: ChecklistReport;
  mark: ChecklistMark | undefined;
  onMark?: (id: string, mark: ChecklistMark) => void;
  titleId: string;
  voice: "screen" | "print";
}) {
  const where = (it.sections ?? []).map((s) => sectionLabel(s)).filter((s): s is string => s !== null);
  const showWhere = where.length > 0 && itemStatus(it) === "needs_check" && !mark && !it.section_absent;
  return (
    <>
      <h3 className="checklist-topic" id={titleId}>
        {it.topic}
      </h3>
      <p className="checklist-refs" data-testid="checklist-refs">
        {itemRefsLine(it, report)}
      </p>
      <p className="checklist-question">{it.question}</p>
      <p className="checklist-status" data-testid="checklist-status">
        <span className="checklist-status-word">{statusWords(it, mark, voice)}</span>
        {showWhere ? <span className="checklist-where muted"> · readers look in {where.join(", ")}</span> : null}
      </p>
      <ChecklistDetail item={it} mark={mark} />
      {onMark ? <ChecklistMarkButtons item={it} mark={mark} onMark={onMark} describedBy={titleId} /> : null}
    </>
  );
}
