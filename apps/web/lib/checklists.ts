/**
 * Reporting checklists (S4, the discipline packs) as the website presents
 * them: the choices for the selector, the offer when the text's own words
 * point to one, and the words an item's status is said in, on the website,
 * in Word and on paper alike. The engine decides what a checklist finds;
 * this file only words it, and holds the writer's own calls (confirmed,
 * not applicable) as a value the surfaces keep in memory for one check.
 * Pure and unit-tested.
 */
import type { ChecklistChoice, ChecklistChoiceInfo, ChecklistItem, ChecklistPart, ChecklistReport, NotCounted } from "@researchly/contract";
import { sectionLabel } from "./categories";

/** What the selector holds: no checklist, Auto (the one the words point to), or a guideline's id. */
export type ChecklistSetting = ChecklistChoice | "none";

const IDS = ["auto", "strobe", "consort", "prisma", "epiforge"] as const satisfies readonly ChecklistChoice[];

export function isChecklistChoice(v: unknown): v is ChecklistChoice {
  return typeof v === "string" && (IDS as readonly string[]).includes(v);
}

export function isChecklistSetting(v: unknown): v is ChecklistSetting {
  return v === "none" || isChecklistChoice(v);
}

/** The setting as a request option: nothing for "none". */
export function checklistOption(setting: ChecklistSetting): ChecklistChoice | null {
  return setting === "none" ? null : setting;
}

/**
 * The choices when the engine's registry has not arrived or has none (the
 * local server, an older engine): the engine's own list (packs/
 * epidemiology.py), so the labels read the same either way.
 */
export const FALLBACK_CHECKLISTS: readonly ChecklistChoiceInfo[] = [
  { id: "strobe", label: "STROBE", design: "observational studies (cohort, case-control, cross-sectional)", pack: "Epidemiology" },
  { id: "consort", label: "CONSORT", design: "randomised controlled trials", pack: "Epidemiology" },
  { id: "prisma", label: "PRISMA", design: "systematic reviews and meta-analyses", pack: "Epidemiology" },
  { id: "epiforge", label: "EPIFORGE", design: "epidemic forecasts, projections and predictions", pack: "Epidemiology" },
];

/** The help line under the selector: what the chosen checklist is for. */
export function checklistHelp(choices: readonly ChecklistChoiceInfo[], setting: ChecklistSetting): string {
  if (setting === "none") return "";
  if (setting === "auto") return "The checklist your text's own words point to, if any.";
  const c = choices.find((x) => x.id === setting);
  return c?.design ? `For ${c.design}.` : "";
}

/** One study of each design, in the singular, for the offer's sentence. */
const ONE_OF: Record<string, string> = {
  strobe: "an observational study",
  consort: "a randomised controlled trial",
  prisma: "a systematic review or meta-analysis",
  epiforge: "an epidemic forecast",
};

export interface ChecklistOffer {
  id: ChecklistChoice;
  label: string;
  sentence: string;
}

/**
 * The quiet offer under the results when no checklist was chosen and the
 * engine says the text's words point to one: "This reads like an epidemic
 * forecast. Check it against EPIFORGE?" The label comes from the registry
 * (or the fallback list); a design this page has no singular for is named
 * from the registry's own words. Null when there is nothing to offer or
 * the id is not one this page can ask for.
 */
export function checklistOffer(suggested: string | null | undefined, choices: readonly ChecklistChoiceInfo[]): ChecklistOffer | null {
  if (!suggested || suggested === "auto" || !isChecklistChoice(suggested)) return null;
  const c = choices.find((x) => x.id === suggested) ?? FALLBACK_CHECKLISTS.find((x) => x.id === suggested);
  if (!c) return null;
  const like = ONE_OF[c.id] ?? `a study ${c.label} covers (${c.design})`;
  return { id: suggested, label: c.label, sentence: `This reads like ${like}. Check it against ${c.label}?` };
}

/**
 * The engine's three statuses (Codex review N1): "found" is possible
 * evidence for every part, for the writer to confirm (a matching sentence
 * is not proof); "partial" is some parts of a compound question; and
 * "needs_check" is a prompt, never a verdict. An older engine's
 * "reported" is read as "found", so it is never shown as settled.
 */
export type ItemStatus = "found" | "partial" | "needs_check";

export function itemStatus(item: Pick<ChecklistItem, "status">): ItemStatus {
  const s = item.status as string;
  if (s === "found" || s === "reported") return "found";
  return s === "partial" ? "partial" : "needs_check";
}

/** The status in words, on screen and on paper alike: never "reported", never a colour, never a score. */
export const CHECKLIST_STATUS_WORD: Record<ItemStatus, string> = {
  found: "Found — please confirm",
  partial: "Partly there",
  needs_check: "Needs your check",
};

/**
 * The writer's own call on an item, for this check only: held in memory,
 * never stored, never sent. "confirmed": the writer read the evidence and
 * says the item is there (offered for found and partial items only);
 * "not_applicable": the item does not apply to this study. One or the other.
 */
export type ChecklistMark = "confirmed" | "not_applicable";
export type ChecklistMarks = ReadonlyMap<string, ChecklistMark>;
export const NO_MARKS: ChecklistMarks = new Map();

/** Whether the writer can confirm the item: only where the engine found possible evidence. */
export function canConfirm(item: Pick<ChecklistItem, "status">): boolean {
  return itemStatus(item) !== "needs_check";
}

/** Press or release one of an item's two controls; pressing one releases the other. Pure. */
export function toggleMark(marks: ChecklistMarks, id: string, mark: ChecklistMark): ChecklistMarks {
  const next = new Map(marks);
  if (next.get(id) === mark) next.delete(id);
  else next.set(id, mark);
  return next;
}

/** Who reads it: the writer on screen ("you"), or anyone the printed page is handed to ("the writer"). */
export type ChecklistVoice = "screen" | "print";

/** An item's status line: the writer's call when there is one, else the engine's status. */
export function statusWords(item: Pick<ChecklistItem, "status">, mark: ChecklistMark | undefined, voice: ChecklistVoice = "screen"): string {
  if (mark === "not_applicable") return voice === "print" ? "Not applicable (the writer’s call)" : "Not applicable (your call)";
  if (mark === "confirmed" && canConfirm(item)) return voice === "print" ? "Confirmed by the writer" : "Confirmed by you";
  return CHECKLIST_STATUS_WORD[itemStatus(item)];
}

function editionOf(report: Pick<ChecklistReport, "edition" | "label">): string {
  return (report.edition ?? "").trim() || report.label;
}

/** The guideline and its version, and what the list is not: "Selected themes of PRISMA 2020 — not a full compliance check." */
export function editionLine(report: Pick<ChecklistReport, "edition" | "label">): string {
  return `Selected themes of ${editionOf(report)} — not a full compliance check.`;
}

function joinWith(xs: readonly string[], last: string): string {
  return xs.length <= 1 ? (xs[0] ?? "") : `${xs.slice(0, -1).join(", ")} ${last} ${xs[xs.length - 1]}`;
}

/** The guideline's own item numbers: "PRISMA 2020 item 6", "CONSORT 2010 items 13a and 13b", or good practice it does not number. */
export function itemRefsLine(item: Pick<ChecklistItem, "refs">, report: Pick<ChecklistReport, "edition" | "label">): string {
  const refs = (item.refs ?? []).map((r) => r.trim()).filter(Boolean);
  if (refs.length === 0) return "Good practice, not a numbered item";
  return `${editionOf(report)} ${refs.length === 1 ? "item" : "items"} ${joinWith(refs, "and")}`;
}

/**
 * The tally in words: "4 of 16 with possible evidence · 2 partly there ·
 * confirmed by you: 1", then the writer's not-applicable calls when there
 * are any. Counts of what was found and what the writer decided, never a
 * score: nothing here says the paper passes.
 */
export function checklistTally(report: Pick<ChecklistReport, "items">, marks: ChecklistMarks, voice: ChecklistVoice = "screen"): string {
  let found = 0;
  let partial = 0;
  let confirmed = 0;
  let na = 0;
  for (const it of report.items) {
    const st = itemStatus(it);
    const m = marks.get(it.id);
    if (st === "found") found += 1;
    if (st === "partial") partial += 1;
    if (m === "not_applicable") na += 1;
    else if (m === "confirmed" && st !== "needs_check") confirmed += 1;
  }
  const print = voice === "print";
  const bits = [`${found} of ${report.items.length} with possible evidence`];
  if (partial > 0) bits.push(`${partial} partly there`);
  bits.push(`${print ? "confirmed by the writer" : "confirmed by you"}: ${confirmed}`);
  if (na > 0) bits.push(`${print ? "not applicable (the writer’s call)" : "not applicable (your call)"}: ${na}`);
  return bits.join(" · ");
}

/** One part of a compound question in words: "Found" (possible evidence, with its sentence) or "Needs your check". */
export function partState(part: Pick<ChecklistPart, "found">): string {
  return part.found ? "Found" : "Needs your check";
}

/** The parts to list under a found or partial item (a needs-check item has none found, so its reason is shown instead). */
export function shownParts(item: Pick<ChecklistItem, "status" | "parts">): readonly ChecklistPart[] {
  return itemStatus(item) === "needs_check" ? [] : (item.parts ?? []);
}

/** A matching sentence the engine set aside, said quietly in the engine's words: "A sentence mentions this but says this is not reported:". */
export function notCountedLine(nc: Pick<NotCounted, "label">): string {
  return `A sentence mentions this but ${nc.label.trim() || "was not counted"}:`;
}

/** When the document has sections but none where readers look: "No Methods section was found to look in." */
export function sectionAbsentLine(item: Pick<ChecklistItem, "sections" | "section_absent">): string | null {
  if (!item.section_absent) return null;
  const names = (item.sections ?? []).map((s) => sectionLabel(s)).filter((s): s is string => s !== null);
  if (names.length === 0) return "None of the sections where readers look for this was found.";
  return `No ${joinWith(names, "or")} section was found to look in.`;
}

/** What the polite live region says after the writer presses or releases a control. */
export function markAnnouncement(topic: string, mark: ChecklistMark, pressed: boolean): string {
  if (mark === "confirmed") return pressed ? `${topic}: confirmed by you.` : `${topic}: confirmation undone.`;
  return pressed ? `${topic}: marked not applicable.` : `${topic}: not applicable undone.`;
}

/** The closing line of every checklist view, on screen and on paper. */
export const CHECKLIST_SCOPE_LINE = "This checks reporting only, never the science.";
