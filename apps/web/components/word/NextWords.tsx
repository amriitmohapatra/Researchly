"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { getEngineAuth } from "@/lib/auth";
import {
  PredictionScheduler,
  predictionAnnouncement,
  snapshotAt,
  wordInsertion,
  type PredictionReply,
  type PredictionShown,
} from "@/lib/prediction";
import { requestCandidates, type PredictionSetting } from "@/lib/use-prediction";
import {
  canListen,
  canPredict,
  insertAtCursor,
  officeApi,
  onSelectionChange,
  readCursorContext,
  type CursorContext,
} from "@/lib/word/office";

type Reason = Exclude<CursorContext, { ok: true }>["reason"] | null;

/** What the panel says when it has no words to offer (pinned by tests). */
export function nextWordsIdle(reason: Reason): string {
  switch (reason) {
    case "unsupported":
      return "This version of Word can’t share where the cursor is, so Next words is not available here. Checking is not affected.";
    case "selection":
      return "Words are offered at the cursor, not for selected text.";
    case "heading":
      return "Nothing is offered in headings.";
    default:
      return "Words that fit at the cursor appear here as you type. Click one to add it; nothing is added otherwise.";
  }
}

/**
 * Word prediction in the Word pane (2026-10-14). Office JS cannot show
 * words inline, so this panel offers them: after the cursor moves (typing
 * moves it), the paragraph up to the cursor goes to the chosen engine and
 * up to three words come back as buttons. A click inserts the rest of the
 * word at the cursor, and only if the text there is still what it was.
 * Nothing is ever inserted by itself.
 */
export function NextWords({ engineUrl, local, setting }: { engineUrl: string; local: boolean; setting: PredictionSetting }) {
  const [shown, setShown] = useState<PredictionShown | null>(null);
  const [reason, setReason] = useState<Reason>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const sched = useRef<PredictionScheduler | null>(null);
  const titleId = useId();
  // Rendered only inside Word (the pane checks first), so Office is there to ask.
  const [{ supported, listening }] = useState(() => {
    const api = officeApi();
    return { supported: api !== null && canPredict(api), listening: api !== null && canListen(api) };
  });

  useEffect(() => {
    const api = officeApi();
    if (!api || !setting.on || !supported) return;
    const s = new PredictionScheduler({
      request: async (_snap, signal): Promise<PredictionReply> => {
        const ctx = await readCursorContext(api);
        if (signal.aborted) return { ok: false };
        setReason(ctx.ok ? null : ctx.reason);
        if (!ctx.ok) return { ok: true, status: "masked", candidates: [] };
        const snap = snapshotAt(ctx.before, ctx.before.length, "plain");
        const r = await requestCandidates(snap, signal, engineUrl, local ? null : getEngineAuth());
        return r.ok ? { ...r, snapshot: snap } : r;
      },
      onShow: setShown,
    });
    sched.current = s;
    const ask = () => s.schedule(snapshotAt("", 0, "plain"));
    const stop = onSelectionChange(api, ask);
    ask();
    return () => {
      stop?.();
      s.cancel();
      sched.current = null;
    };
  }, [engineUrl, local, setting.on, supported]);

  const accept = useCallback(
    async (i: number) => {
      const api = officeApi();
      const cand = shown?.candidates[i];
      if (!api || !shown || !cand || busy) return;
      const offer = wordInsertion(shown.snapshot.window, cand);
      sched.current?.cancel();
      if (!offer) return;
      setBusy(true);
      const r = await insertAtCursor(api, offer.insertion, shown.snapshot.full);
      setBusy(false);
      setNote(r.ok ? null : r.message);
      // The selection moved: the event asks again. Where there is no event, ask here.
      if (r.ok && !listening) sched.current?.schedule(snapshotAt("", 0, "plain"));
    },
    [busy, listening, shown],
  );

  if (!setting.on) return null;

  const offers = shown
    ? shown.candidates
        .map((c) => wordInsertion(shown.snapshot.window, c))
        .filter((o): o is { label: string; insertion: string } => o !== null)
    : [];

  return (
    <section className="panel tp-next" aria-labelledby={titleId} data-testid="next-words">
      <div className="tp-next-head">
        <h2 id={titleId} className="tp-next-title">
          Next words
        </h2>
        <button type="button" className="btn-link" onClick={() => setting.set(false)} data-testid="next-words-hide">
          Hide
        </button>
      </div>
      <span className="sr-only" aria-live="polite" aria-atomic="true">
        {predictionAnnouncement(
          offers.map((o) => ({ text: o.label })),
          "Choose a word to add it at the cursor.",
        )}
      </span>
      {offers.length > 0 ? (
        <span className="prediction-options" role="group" aria-labelledby={titleId}>
          {offers.map((o, i) => (
            <button
              key={`${i}-${o.label}`}
              type="button"
              className={`prediction-option${i === 0 ? " is-first" : ""}`}
              onClick={() => void accept(i)}
              aria-disabled={busy || undefined}
              data-testid="next-word"
            >
              {o.label}
            </button>
          ))}
        </span>
      ) : (
        <p className="tp-next-note" data-testid="next-words-idle">
          {nextWordsIdle(supported ? reason : "unsupported")}
        </p>
      )}
      {note ? (
        <p className="tp-next-note" role="status" data-testid="next-words-note">
          {note}
        </p>
      ) : null}
      {!listening && supported ? (
        <button
          type="button"
          className="btn btn-quiet btn-compact"
          onClick={() => sched.current?.schedule(snapshotAt("", 0, "plain"))}
          data-testid="next-words-ask"
        >
          Suggest words at the cursor
        </button>
      ) : null}
    </section>
  );
}
