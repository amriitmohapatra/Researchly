"use client";

import { useId, useRef, useState, type ReactNode } from "react";

interface Props {
  /** The opener's label, e.g. "Delete my progress…". */
  label: string;
  title: string;
  body: ReactNode;
  keepLabel: string;
  confirmLabel: string;
  busy: boolean;
  onConfirm: () => Promise<unknown>;
  testId: string;
  /** Shown on the confirm button while it works (default "Deleting…"). */
  workingLabel?: string;
}

/**
 * A destructive action behind a native <dialog> (DESIGN.md: focus contained,
 * Escape closes, focus returns to the opener), the safe choice focused first.
 * Used wherever a second click should confirm: deleting progress, clearing
 * the dictionary, resetting preferences. Deleting the account asks for more
 * (components/DeleteAccount.tsx).
 */
export function ConfirmDelete({
  label,
  title,
  body,
  keepLabel,
  confirmLabel,
  busy,
  onConfirm,
  testId,
  workingLabel = "Deleting…",
}: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const openerRef = useRef<HTMLButtonElement>(null);
  const keepRef = useRef<HTMLButtonElement>(null);
  const ids = { title: useId(), body: useId() };
  const [working, setWorking] = useState(false);

  return (
    <>
      <button
        ref={openerRef}
        type="button"
        className="btn btn-secondary"
        aria-disabled={busy || undefined}
        onClick={() => {
          if (busy) return;
          ref.current?.showModal();
          keepRef.current?.focus();
        }}
        data-testid={`${testId}-open`}
      >
        {label}
      </button>
      <dialog
        ref={ref}
        className="dialog"
        aria-labelledby={ids.title}
        aria-describedby={ids.body}
        onClose={() => openerRef.current?.focus()}
        data-testid={`${testId}-dialog`}
      >
        <div className="dialog-body">
          <h2 id={ids.title} className="dialog-title">
            {title}
          </h2>
          <p id={ids.body}>{body}</p>
          <div className="dialog-actions">
            <button ref={keepRef} type="button" className="btn btn-secondary" onClick={() => ref.current?.close()}>
              {keepLabel}
            </button>
            <button
              type="button"
              className="btn btn-primary"
              aria-disabled={working || undefined}
              onClick={async () => {
                if (working) return;
                setWorking(true);
                await onConfirm();
                setWorking(false);
                ref.current?.close();
              }}
              data-testid={`${testId}-confirm`}
            >
              {working ? (
                <>
                  <span className="spinner" aria-hidden="true" />
                  {workingLabel}
                </>
              ) : (
                confirmLabel
              )}
            </button>
          </div>
        </div>
      </dialog>
    </>
  );
}
