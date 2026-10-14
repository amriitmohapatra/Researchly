/**
 * The English spelling a writer keeps to (PLAN task #15), as the surfaces
 * present it. Pure and unit-tested. The engine decides what each choice
 * flags (researchly/config.py SPELLINGS, rules W210 and W213); this file
 * only words the choices and decides which one a check sends.
 */
import { SPELLINGS, type Spelling } from "@researchly/contract";

export function isSpelling(v: unknown): v is Spelling {
  return typeof v === "string" && (SPELLINGS as readonly string[]).includes(v);
}

/** The selector's labels. A Record, so a spelling added to the contract fails the typecheck until it has one. */
export const SPELLING_LABELS: Readonly<Record<Spelling, string>> = {
  auto: "Auto (follow the document)",
  us: "American",
  uk: "British (-ise)",
  "uk-oxford": "British (Oxford -ize)",
  ca: "Canadian",
  au: "Australian",
  in: "Indian (British spelling)",
};

/** The one line under the selector: what the choice asks for, with a few words as examples. */
export const SPELLING_HELP: Readonly<Record<Spelling, string>> = {
  auto: "Follows the spelling most of your text uses and points out only the words that break from it.",
  us: "Points out every spelling from another kind of English: color, analyze, organize, center.",
  uk: "Points out every spelling from another kind of English: colour, analyse, organise, centre.",
  "uk-oxford": "Points out every spelling from another kind of English: colour, analyse, organize, centre.",
  ca: "Points out every spelling from another kind of English: colour, analyze, organize, centre.",
  au: "Points out every spelling from another kind of English: colour, analyse, organise, centre.",
  in: "Indian English is spelled as British English: colour, analyse, organise, centre.",
};

export interface SpellingChoice {
  id: Spelling;
  label: string;
}

/** Every choice, in the engine's order (Auto first). */
export const SPELLING_CHOICES: readonly SpellingChoice[] = SPELLINGS.map((id) => ({ id, label: SPELLING_LABELS[id] }));

/**
 * The spelling a check sends, resolved like the article type: this
 * session's choice, else the account's (signed in), else this browser's.
 * Null when none of them has one: the request then leaves `spelling` out
 * and the engine applies the account's saved choice, or Auto.
 */
export function resolveSpelling(p: {
  chosen: Spelling | null;
  account: Spelling | null;
  stored: Spelling | null;
  signedIn: boolean;
}): Spelling | null {
  return p.chosen ?? (p.signedIn ? p.account : null) ?? p.stored ?? null;
}
