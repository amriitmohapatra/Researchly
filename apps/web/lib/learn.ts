/**
 * The Learn cards (S4) as the results present them: the lesson behind a
 * suggestion, a missing move or a missing link, looked up by the engine's
 * `learn_ref`. The cards ship with the contract (packages/contract/
 * learn.json, generated from the engine's learn.py), so opening one sends
 * nothing anywhere. Pure and unit-tested.
 */
import { LEARN_CARDS, type LearnCard } from "@researchly/contract";

const BY_ID: ReadonlyMap<string, LearnCard> = new Map(LEARN_CARDS.map((c) => [c.id, c]));

/** Where every lesson is listed. Opened in a new tab so the results stay where they are. */
export const LEARN_PATH = "/learn";

/** The card a `learn_ref` names, or null when there is none (or this build does not know it). */
export function learnCard(ref: string | null | undefined): LearnCard | null {
  if (typeof ref !== "string" || !ref.trim()) return null;
  return BY_ID.get(ref.trim()) ?? null;
}
