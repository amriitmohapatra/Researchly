/**
 * The only things this app remembers in the browser: the chosen input format,
 * the article type to check as (S4; shared by the website and the Word add-in,
 * which are one origin) and, in the Word add-in, the engine choice and
 * Draft/Revise. The document itself is never persisted (no localStorage,
 * sessionStorage or IndexedDB for text in S1) — scripts/check-boundary.mjs
 * enforces that storage APIs are used in this file only.
 */
import type { DocumentType, Format } from "@researchly/contract";
import { isDocumentType } from "./profiles";
import { isFormat } from "./validate";

const FORMAT_KEY = "researchly.format";
const DOCUMENT_TYPE_KEY = "researchly.document-type";

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

/* ---------- the article type (S4): one choice for both surfaces, never text ---------- */

/** The article type chosen on this computer, or null when never chosen (signed in, the account's choice wins). */
export function loadDocumentTypeChoice(): DocumentType | null {
  const v = read(DOCUMENT_TYPE_KEY);
  return isDocumentType(v) ? v : null;
}

export function saveDocumentTypeChoice(v: DocumentType): void {
  write(DOCUMENT_TYPE_KEY, v);
}

/** For useSyncExternalStore: the website and the taskpane share this choice, so one changing it updates the other. */
export function subscribeDocumentType(onChange: () => void): () => void {
  const handler = (e: StorageEvent) => {
    if (e.key === DOCUMENT_TYPE_KEY) onChange();
  };
  window.addEventListener("storage", handler);
  return () => window.removeEventListener("storage", handler);
}

/* ---------- the Word add-in (S3): per-viewer choices, never text ---------- */

/** Which engine the add-in checks with: the hosted one, or server.py on this computer (ADR-02 local mode). */
export type EngineChoice = "cloud" | "local";
/** Draft / Revise, remembered here when signed out (signed in, the account holds it). */
export type ModeChoice = "draft" | "revise";

const ENGINE_KEY = "researchly.word.engine";
const MODE_KEY = "researchly.word.mode";

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null; // private mode, blocked storage, SSR
  }
}

function write(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* storage unavailable: the choice just isn't remembered */
  }
}

export function loadEngineChoice(): EngineChoice | null {
  const v = read(ENGINE_KEY);
  return v === "cloud" || v === "local" ? v : null;
}

export function saveEngineChoice(v: EngineChoice): void {
  write(ENGINE_KEY, v);
}

export function loadModeChoice(): ModeChoice | null {
  const v = read(MODE_KEY);
  return v === "draft" || v === "revise" ? v : null;
}

export function saveModeChoice(v: ModeChoice): void {
  write(MODE_KEY, v);
}

/** For useSyncExternalStore: another taskpane or tab changing a Word preference updates this one. */
export function subscribeWordPrefs(onChange: () => void): () => void {
  const handler = (e: StorageEvent) => {
    if (e.key === ENGINE_KEY || e.key === MODE_KEY) onChange();
  };
  window.addEventListener("storage", handler);
  return () => window.removeEventListener("storage", handler);
}
