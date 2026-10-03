/**
 * The only thing this app remembers in the browser: the chosen input format.
 * The document itself is never persisted (no localStorage, sessionStorage
 * or IndexedDB for text in S1) — scripts/check-boundary.mjs enforces that
 * storage APIs are used in this file only.
 */
import type { Format } from "@researchly/contract";
import { isFormat } from "./validate";

const FORMAT_KEY = "researchly.format";

export function loadFormat(): Format | null {
  try {
    const v = window.localStorage.getItem(FORMAT_KEY);
    return isFormat(v) ? v : null;
  } catch {
    return null; // private mode, blocked storage, SSR
  }
}

export function saveFormat(f: Format): void {
  try {
    window.localStorage.setItem(FORMAT_KEY, f);
  } catch {
    /* storage unavailable: the choice just isn't remembered */
  }
}

/** For useSyncExternalStore: another tab changing the preference updates this one. */
export function subscribeFormat(onChange: () => void): () => void {
  const handler = (e: StorageEvent) => {
    if (e.key === FORMAT_KEY) onChange();
  };
  window.addEventListener("storage", handler);
  return () => window.removeEventListener("storage", handler);
}
