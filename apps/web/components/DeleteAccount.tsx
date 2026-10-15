"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";

/** The word a writer types to confirm (any case; spaces around it are ignored). */
export const CONFIRM_WORD = "delete";

export function confirmWordMatches(typed: string): boolean {
  return typed.trim().toLowerCase() === CONFIRM_WORD;
}

/** What is deleted, said once in the panel and again in the dialog (pinned by tests). */
export const DELETE_ACCOUNT_BODY =
  "This deletes your sign-in and everything kept with it: muted rules, display choices, your dictionary and any recorded progress, on every device. It can’t be undone, and this browser will be signed out. Researchly never kept any of your text, so there is none to delete.";

interface Props {
  busy: boolean;
  /** Deletes the account; resolves to null when it is gone, else a sentence saying why not. */
  onDelete: () => Promise<string | null>;
}

/**
 * "Delete my account" (PLAN #12). Two steps, because it cannot be undone:
 * open the dialog (the safe choice is focused), then type a word and
 * confirm. A failure keeps the dialog open and says why; nothing is deleted.
 * Native <dialog> as everywhere else (DESIGN.md): focus contained, Escape
 * closes, focus returns to the opener.
 */
export function DeleteAccount({ busy, onDelete }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const openerRef = useRef<HTMLButtonElement>(null);
  const keepRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const ids = { title: useId(), body: useId(), word: useId(), help: useId(), problem: useId() };
  const [typed, setTyped] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const [working, setWorking] = useState(false);
  const ready = confirmWordMatches(typed);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (working) return;
    if (!ready) {
      setProblem(`Type the word “${CONFIRM_WORD}” to confirm.`);
      inputRef.current?.focus();
      return;
    }
    setProblem(null);
    setWorking(true);
    const failed = await onDelete();
    // On success this component is replaced by the "deleted" message.
    if (failed) {
      setWorking(false);
      setProblem(failed);
    }
  };

  return (
    <>
      <button
        ref={openerRef}
        type="button"
        className="btn btn-secondary"
        aria-disabled={busy || undefined}
        onClick={() => {
          if (busy) return;
          setTyped("");
          setProblem(null);
          ref.current?.showModal();
          keepRef.current?.focus();
        }}
        data-testid="delete-account-open"
      >
        Delete my account…
      </button>
      <dialog
        ref={ref}
        className="dialog"
        aria-labelledby={ids.title}
        aria-describedby={ids.body}
        onCancel={(e) => {
          if (working) e.preventDefault();
        }}
        onClose={() => openerRef.current?.focus()}
        data-testid="delete-account-dialog"
      >
        <form className="dialog-body" onSubmit={onSubmit} noValidate>
          <h2 id={ids.title} className="dialog-title">
            Delete your account?
          </h2>
          <p id={ids.body}>{DELETE_ACCOUNT_BODY}</p>
          <div className="field">
            <label htmlFor={ids.word} className="field-label">
              To confirm, type {CONFIRM_WORD}
            </label>
            <input
              id={ids.word}
              ref={inputRef}
              className="input"
              type="text"
              name="confirm"
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
              value={typed}
              onChange={(e) => {
                setTyped(e.target.value);
                if (problem) setProblem(null);
              }}
              aria-invalid={problem ? true : undefined}
              aria-describedby={problem ? ids.problem : undefined}
              data-testid="delete-account-word"
            />
            {problem ? (
              <p id={ids.problem} className="field-problem" role="alert" data-testid="delete-account-problem">
                {problem}
              </p>
            ) : null}
          </div>
          <div className="dialog-actions">
            <button
              ref={keepRef}
              type="button"
              className="btn btn-secondary"
              aria-disabled={working || undefined}
              onClick={() => {
                if (!working) ref.current?.close();
              }}
            >
              Keep my account
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              aria-disabled={working || undefined}
              data-testid="delete-account-confirm"
            >
              {working ? (
                <>
                  <span className="spinner" aria-hidden="true" />
                  Deleting…
                </>
              ) : (
                "Delete my account"
              )}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}

/**
 * Shown in place of the settings once the account is gone. The heading takes
 * focus, so a screen reader says it at once.
 */
export function AccountDeleted() {
  const ref = useRef<HTMLHeadingElement>(null);
  useEffect(() => ref.current?.focus(), []);
  return (
    <section className="panel settings-gate" aria-labelledby="deleted-title" data-testid="account-deleted">
      <h2 id="deleted-title" className="panel-title" tabIndex={-1} ref={ref}>
        Your account was deleted
      </h2>
      <p className="muted">
        Your sign-in, settings, dictionary and any recorded progress are gone, and this browser is signed out. You can
        still check text without an account, and you can make a new account at any time.
      </p>
      <p>
        <Link className="inline-link" href="/">
          Back to the checker
        </Link>
      </p>
    </section>
  );
}
