"use client";

import { useId } from "react";
import type { ScopeInfo } from "@researchly/contract";
import { SCOPE_OPTIONS, scopeNote, type ScopeChoice } from "@/lib/evidence";

interface Props {
  scope: ScopeInfo | null | undefined;
  /** The writer's choice for this session; "auto" lets the engine infer it. */
  value?: ScopeChoice;
  /** Check again read as another scope. Absent (print, an engine without scopes): the line only. */
  onChange?: ((next: ScopeChoice) => void) | null;
  disabled?: boolean;
}

/**
 * How much of the document the check took the text to be (Codex review
 * #4): the engine's one line saying what was assumed and what it changes,
 * with a small "Read as" select to override it. Kept beside the brief and
 * the map, the views it changes, rather than in the composer's row. Never
 * stored: it is a choice about this check.
 */
export function ScopeLine({ scope, value = "auto", onChange = null, disabled = false }: Props) {
  const id = useId();
  const note = scopeNote(scope);
  if (!note) return null;
  return (
    <div className="scope-line" data-testid="scope-line" data-scope={scope?.id}>
      <p className="scope-note muted" data-testid="scope-note">
        {note}
      </p>
      {onChange ? (
        <div className="control scope-control">
          <label htmlFor={id} className="control-label">
            Read as
          </label>
          <select
            id={id}
            className="select select-compact"
            value={value}
            disabled={disabled}
            onChange={(e) => onChange(e.target.value as ScopeChoice)}
            data-testid="scope-select"
          >
            {SCOPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.value === "auto" && scope?.guessed ? `Auto (${scope.label.toLowerCase()})` : o.label}
              </option>
            ))}
          </select>
        </div>
      ) : null}
    </div>
  );
}
