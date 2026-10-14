"use client";

import { useId } from "react";
import type { Spelling } from "@researchly/contract";
import { isSpelling, SPELLING_CHOICES, SPELLING_HELP } from "@/lib/spelling";

interface Props {
  id: string;
  value: Spelling;
  onChange: (v: Spelling) => void;
  /** A failed save to the account, said under the control. */
  note?: string | null;
  /** Disabled while a settings change is being saved (the settings page). */
  busy?: boolean;
  className?: string;
}

/**
 * "Spelling": which English the writer keeps to (PLAN task #15). Default
 * Auto, which follows the document's own majority and points out only the
 * words that break from it; any other choice also points out every spelling
 * from another kind of English. One line under the control says which.
 */
export function SpellingSelect({ id, value, onChange, note, busy, className }: Props) {
  const helpId = useId();
  return (
    <div className={`control control-spelling${className ? ` ${className}` : ""}`}>
      <label htmlFor={id} className="control-label">
        Spelling
      </label>
      <select
        id={id}
        className="select"
        value={value}
        aria-describedby={helpId}
        aria-disabled={busy || undefined}
        onChange={(e) => {
          if (busy) return;
          const v = e.target.value;
          if (isSpelling(v)) onChange(v);
        }}
        data-testid="spelling"
      >
        {SPELLING_CHOICES.map((c) => (
          <option key={c.id} value={c.id}>
            {c.label}
          </option>
        ))}
      </select>
      <p id={helpId} className="help control-help" data-testid="spelling-help">
        {SPELLING_HELP[value]}
      </p>
      {note ? (
        <p className="field-problem" role="alert" data-testid="spelling-note">
          {note}
        </p>
      ) : null}
    </div>
  );
}
