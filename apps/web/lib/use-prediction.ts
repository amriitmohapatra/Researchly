/**
 * React glue for word prediction (2026-10-14): the writer's switch, and the
 * editor's candidates. The logic lives in lib/prediction.ts (pure, tested);
 * the request in lib/engine.ts (the only module that sends text).
 */
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type ChangeEvent,
  type KeyboardEvent,
  type RefObject,
  type SyntheticEvent,
} from "react";
import type { Format } from "@researchly/contract";
import { loadPrediction, savePrediction } from "./account";
import { getEngineAuth } from "./auth";
import { complete, type EngineAuth } from "./engine";
import { loadPredictionChoice, savePredictionChoice, subscribePrediction } from "./prefs";
import {
  acceptCandidate,
  MAX_SHOWN,
  PredictionScheduler,
  predictionKey,
  resolvePrediction,
  snapshotAt,
  type PredictionReply,
  type PredictionShown,
  type PredictionSnapshot,
} from "./prediction";

/* ---------- the switch ---------- */

export interface PredictionSetting {
  on: boolean;
  /** Turn it on or off: remembered in this browser, and in the account when signed in. */
  set: (on: boolean) => void;
  /** Said when the account could not keep the choice (it then applies in this browser only). */
  note: string | null;
}

/**
 * Whether word prediction is on: this session's choice, else the account's
 * (signed in), else this browser's, else on. The engine applies the
 * account's switch too, so a signed-in writer who turned it off elsewhere
 * gets nothing even before this has loaded.
 */
export function usePredictionSetting(signedIn: boolean): PredictionSetting {
  const stored = useSyncExternalStore(subscribePrediction, loadPredictionChoice, () => null);
  const [account, setAccount] = useState<boolean | null>(null);
  const [chosen, setChosen] = useState<boolean | null>(null);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!signedIn) return;
    let live = true;
    void loadPrediction().then((r) => {
      // A failed load (no column yet, offline) leaves this browser's switch in charge.
      if (live && r.ok) setAccount(r.data);
    });
    return () => {
      live = false;
    };
  }, [signedIn]);

  const set = useCallback(
    (on: boolean) => {
      setChosen(on);
      savePredictionChoice(on);
      setNote(null);
      if (signedIn) {
        void savePrediction(on).then((r) => {
          if (r.ok) setAccount(on);
          else setNote(`This choice could not be saved to your account, so it applies here only. ${r.message}`);
        });
      }
    },
    [signedIn],
  );

  return { on: resolvePrediction({ chosen, account, stored, signedIn }), set, note };
}

/* ---------- asking the engine ---------- */

/** One prediction request, reduced to what the scheduler needs. Never throws on an engine error. */
export async function requestCandidates(
  snap: PredictionSnapshot,
  signal: AbortSignal,
  engineUrl: string | undefined,
  auth: EngineAuth | null,
): Promise<PredictionReply> {
  const r = await complete(
    { text: snap.window.text, cursor: snap.window.cursor, format: snap.format, limit: MAX_SHOWN, signal },
    engineUrl,
    auth,
  );
  if (r.ok) return { ok: true, status: r.data.status, candidates: r.data.candidates ?? [] };
  return { ok: false, rateLimited: r.error.kind === "rate_limited" };
}

/* ---------- the editor ---------- */

export interface TextPrediction {
  shown: PredictionShown | null;
  /** Call from the textarea's onChange, after its own handling. */
  onInput: (e: ChangeEvent<HTMLTextAreaElement>) => void;
  /** Call from the textarea's onKeyDown: Tab accepts the first candidate, Esc dismisses. */
  onKeyDown: (e: KeyboardEvent<HTMLTextAreaElement>) => void;
  /** Call from the textarea's onSelect: a caret that moved away drops what is shown. */
  onSelect: (e: SyntheticEvent<HTMLTextAreaElement>) => void;
  /** Esc, or the editor lost focus: what is shown no longer applies. */
  dismiss: () => void;
  /** Accept candidate `i` (a click). */
  accept: (i: number) => void;
}

/**
 * Candidates for a textarea: asked for after a pause in typing, shown
 * beside it, inserted only when the writer accepts one, and only if the
 * text and caret are still exactly as they were when they were asked for.
 */
export function useTextPrediction(opts: {
  ref: RefObject<HTMLTextAreaElement | null>;
  text: string;
  setText: (text: string) => void;
  format: Format;
  enabled: boolean;
  engineUrl?: string;
}): TextPrediction {
  const { ref, text, setText, format, enabled, engineUrl } = opts;
  const [shown, setShown] = useState<PredictionShown | null>(null);
  const sched = useRef<PredictionScheduler | null>(null);
  const caretAfter = useRef<number | null>(null);

  useEffect(() => {
    const s = new PredictionScheduler({
      request: (snap, signal) => requestCandidates(snap, signal, engineUrl, getEngineAuth()),
      onShow: setShown,
    });
    sched.current = s;
    return () => {
      s.cancel();
      sched.current = null;
    };
  }, [engineUrl]);

  useEffect(() => {
    if (!enabled) sched.current?.cancel();
  }, [enabled]);

  // After an accepted candidate, the caret goes to the end of what was inserted.
  useLayoutEffect(() => {
    const at = caretAfter.current;
    const el = ref.current;
    if (at === null || !el) return;
    caretAfter.current = null;
    el.setSelectionRange(at, at);
  }, [text, ref]);

  const dismiss = useCallback(() => sched.current?.cancel(), []);

  const onSelect = useCallback((e: SyntheticEvent<HTMLTextAreaElement>) => {
    const el = e.currentTarget;
    sched.current?.moved(el.value, el.selectionStart, el.selectionEnd);
  }, []);

  const onInput = useCallback(
    (e: ChangeEvent<HTMLTextAreaElement>) => {
      const el = e.target;
      const native = e.nativeEvent as Partial<InputEvent>;
      const pasted = /^insertFrom(Paste|Drop)/.test(native.inputType ?? "");
      if (!enabled || pasted || native.isComposing || el.selectionStart !== el.selectionEnd) {
        sched.current?.cancel();
        return;
      }
      sched.current?.schedule(snapshotAt(el.value, el.selectionStart, format));
    },
    [enabled, format],
  );

  const accept = useCallback(
    (i: number) => {
      const el = ref.current;
      const cand = shown?.candidates[i];
      sched.current?.cancel();
      if (!shown || !cand || !el) return;
      const { snapshot } = shown;
      // Only into the very text and caret it was asked for.
      if (el.value !== snapshot.full || el.selectionStart !== snapshot.caret || el.selectionEnd !== snapshot.caret) return;
      const done = acceptCandidate(snapshot.full, snapshot.window, cand);
      if (!done) return;
      caretAfter.current = done.caret;
      setText(done.text);
      el.focus();
    },
    [ref, setText, shown],
  );

  const onKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      const action = predictionKey(
        {
          key: e.key,
          shiftKey: e.shiftKey,
          altKey: e.altKey,
          ctrlKey: e.ctrlKey,
          metaKey: e.metaKey,
          isComposing: e.nativeEvent.isComposing,
        },
        shown !== null,
      );
      if (action === "accept") {
        e.preventDefault();
        accept(0);
      } else if (action === "dismiss") {
        e.preventDefault();
        e.stopPropagation();
        sched.current?.cancel();
      }
    },
    [accept, shown],
  );

  return { shown: enabled ? shown : null, onInput, onKeyDown, onSelect, dismiss, accept };
}
