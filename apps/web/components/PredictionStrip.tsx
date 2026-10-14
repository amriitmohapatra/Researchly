"use client";

import { useId } from "react";
import type { CompletionCandidate } from "@researchly/contract";
import { predictionAnnouncement } from "@/lib/prediction";
import type { PredictionSetting } from "@/lib/use-prediction";

/** The exact help under the switch (pinned by tests). */
export const PREDICTION_HELP =
  "Offers the end of the word you are typing, or the next word. Nothing is added unless you press Tab or click it.";

/** The same, in the Word pane, where there is no Tab to press. */
export const WORD_PREDICTION_HELP =
  "Shows the Next words panel: the end of the word you are typing, or the next word. Nothing is added unless you click it.";

/** The writer's switch for word prediction, as a switch like "Show preferences". */
export function PredictionToggle({
  setting,
  testId = "prediction-switch",
  help = PREDICTION_HELP,
  showHelp = false,
}: {
  setting: PredictionSetting;
  testId?: string;
  help?: string;
  /** Visible help under the switch (the Word pane's settings); otherwise it is read by screen readers only. */
  showHelp?: boolean;
}) {
  const ids = { input: useId(), help: useId() };
  const className = "control control-toggle";
  return (
    <div className="prediction-control">
      <label className={className} htmlFor={ids.input}>
        <input
          id={ids.input}
          type="checkbox"
          role="switch"
          className="switch"
          checked={setting.on}
          aria-describedby={ids.help}
          onChange={(e) => setting.set(e.target.checked)}
          data-testid={testId}
        />
        <span>Word prediction</span>
      </label>
      <p id={ids.help} className={showHelp ? "help" : "sr-only"} data-testid={`${testId}-help`}>
        {help}
      </p>
      {setting.note ? (
        <p className="field-problem" role="alert" data-testid="prediction-note">
          {setting.note}
        </p>
      ) : null}
    </div>
  );
}

/**
 * The candidates for the word at the cursor (2026-10-14): a quiet strip
 * under the editor. Nothing is inserted unless the writer presses Tab (the
 * first candidate) or clicks one. The buttons are out of the tab order on
 * purpose: Tab accepts while they are shown and moves focus as usual
 * otherwise, so a keyboard user is never trapped. A polite live region,
 * always mounted, says each new offer without interrupting.
 */
export function PredictionStrip({
  candidates,
  onAccept,
}: {
  candidates: readonly CompletionCandidate[] | null;
  onAccept: (index: number) => void;
}) {
  const list = candidates ?? [];
  return (
    <div className="prediction-strip" data-testid="prediction-strip">
      <span className="sr-only" aria-live="polite" aria-atomic="true" data-testid="prediction-live">
        {predictionAnnouncement(list)}
      </span>
      {list.length > 0 ? (
        <>
          <span className="prediction-options" role="group" aria-label="Word prediction">
            {list.map((c, i) => (
              <button
                key={`${i}-${c.text}`}
                type="button"
                tabIndex={-1}
                className={`prediction-option${i === 0 ? " is-first" : ""}`}
                // Keep the caret in the editor: a click must not blur it first.
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => onAccept(i)}
                data-testid="prediction-option"
                data-kind={c.kind}
              >
                {c.text}
              </button>
            ))}
          </span>
          <span className="prediction-hint" aria-hidden="true">
            <kbd>Tab</kbd> to accept · <kbd>Esc</kbd> to dismiss
          </span>
        </>
      ) : null}
    </div>
  );
}
