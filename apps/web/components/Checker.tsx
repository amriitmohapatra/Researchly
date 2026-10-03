"use client";

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  useSyncExternalStore,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { MAX_CONTENT_CHARS, type AnalyzeResponse, type Format } from "@researchly/contract";
import { analyze } from "@/lib/engine";
import type { CheckError } from "@/lib/errors";
import { loadFormat, saveFormat, subscribeFormat } from "@/lib/prefs";
import { codePointLength } from "@/lib/segments";
import { FORMATS, isFormat, validateContent, type InputProblem } from "@/lib/validate";
import { revealNeedsRecheck, shownSuggestions, summarySentence } from "@/lib/view";
import { ReadingKey } from "./ReadingKey";
import { Results } from "./Results";

type Phase = "idle" | "loading" | "done" | "error";

interface Checked {
  /** Increments per completed check; remounts the results view (fresh selection). */
  seq: number;
  data: AnalyzeResponse;
  text: string;
  format: Format;
}

const fmt = new Intl.NumberFormat("en-GB");

/** Written for this page (no third-party text). Inserted only into an empty editor; nothing is sent until Check. */
const EXAMPLE_DRAFT =
  "Methods\nCase counts were analysed using a renewal model with a seven day generation interval. Data was collected from 2019 to 2023.\n\nDiscussion\nIn order to understand the the dynamics of transmission, further studies are needed. It is clearly proven that vector control works.\n";

export function Checker() {
  const [text, setText] = useState("");
  // The only remembered setting. Server render and first client render agree on null.
  const storedFormat = useSyncExternalStore(subscribeFormat, loadFormat, () => null);
  const [chosenFormat, setFormat] = useState<Format | null>(null);
  const format: Format = chosenFormat ?? storedFormat ?? "plain";
  const [showPreferences, setShowPreferences] = useState(false);
  const [problem, setProblem] = useState<InputProblem | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [checked, setChecked] = useState<Checked | null>(null);
  const [error, setError] = useState<CheckError | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const loadingRef = useRef(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  const ids = { text: useId(), hint: useId(), problem: useId(), format: useId(), prefs: useId(), privacy: useId() };

  useEffect(() => () => abortRef.current?.abort(), []);

  // Nothing is saved anywhere, so leaving the page loses the draft: ask first.
  const hasText = text.trim().length > 0;
  useEffect(() => {
    if (!hasText) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [hasText]);

  const onExample = () => {
    setText(EXAMPLE_DRAFT);
    setProblem(null);
    textareaRef.current?.focus();
  };

  const runCheck = useCallback(
    async (opts?: { showPreferences?: boolean }) => {
      if (loadingRef.current) return;
      const prefs = opts?.showPreferences ?? showPreferences;
      const invalid = validateContent(text);
      setProblem(invalid);
      if (invalid) {
        textareaRef.current?.focus();
        return;
      }
      const submitted = text;
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      loadingRef.current = true;
      setPhase("loading");
      setError(null);
      setAnnouncement("Checking your text…");
      try {
        const r = await analyze({ content: submitted, format, showPreferences: prefs, signal: ctrl.signal });
        if (r.ok) {
          setChecked((prev) => ({ seq: (prev?.seq ?? 0) + 1, data: r.data, text: submitted, format }));
          setPhase("done");
          setAnnouncement(summarySentence(shownSuggestions(r.data, prefs)));
        } else {
          setError(r.error);
          setPhase("error");
          setAnnouncement("");
          // Move focus to the error so keyboard and screen-reader users land on it.
          requestAnimationFrame(() => errorRef.current?.focus());
        }
      } catch {
        // Cancelled by the user. Nothing to report beyond that.
        setPhase(checked ? "done" : "idle");
        setAnnouncement("Check cancelled. Your text is unchanged.");
      } finally {
        loadingRef.current = false;
        abortRef.current = null;
      }
    },
    [text, format, showPreferences, checked],
  );

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void runCheck();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLFormElement>) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      void runCheck();
    }
  };

  const onRevealPreferences = () => {
    setShowPreferences(true);
    if (checked && revealNeedsRecheck(checked.data)) void runCheck({ showPreferences: true });
  };

  const loading = phase === "loading";
  const chars = codePointLength(text);
  const overLimit = chars > MAX_CONTENT_CHARS;
  const describedBy = [ids.hint, problem ? ids.problem : null].filter(Boolean).join(" ");

  return (
    <>
      <div className="studio">
        <form className="panel composer" onSubmit={onSubmit} onKeyDown={onKeyDown} aria-labelledby="composer-title" noValidate>
          <h2 id="composer-title" className="sr-only">
            Check your writing
          </h2>
          <div className="field">
            <label htmlFor={ids.text} className="field-label">
              Text to check
            </label>
            <p id={ids.hint} className="help">
              Paste a section, a chapter or a whole draft. Headings such as &ldquo;Methods&rdquo; or
              &ldquo;Discussion&rdquo; let the advice fit the section.
            </p>
            <textarea
              id={ids.text}
              ref={textareaRef}
              className="editor"
              name="content"
              value={text}
              onChange={(e) => {
                setText(e.target.value);
                if (problem) setProblem(null);
              }}
              aria-describedby={describedBy}
              aria-invalid={problem ? true : undefined}
              spellCheck={false}
              autoComplete="off"
              autoCorrect="off"
              autoCapitalize="off"
              rows={12}
              placeholder="In order to estimate the effective reproduction number, a renewal model was fitted…"
              data-testid="editor"
            />
            <div className="field-foot">
              {problem ? (
                <p id={ids.problem} className="field-problem" role="alert" data-testid="input-problem">
                  {problem.message}
                </p>
              ) : (
                <span />
              )}
              <p className={`counter${overLimit ? " counter-over" : ""}`} aria-live="off">
                {fmt.format(chars)} / {fmt.format(MAX_CONTENT_CHARS)} characters
              </p>
            </div>
          </div>

          <div className="controls">
            <div className="control">
              <label htmlFor={ids.format} className="control-label">
                Format
              </label>
              <select
                id={ids.format}
                className="select"
                value={format}
                onChange={(e) => {
                  const v = e.target.value;
                  if (isFormat(v)) {
                    setFormat(v);
                    saveFormat(v);
                  }
                }}
                data-testid="format"
              >
                {FORMATS.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Label wraps the switch: one hit target, no dead zone between them. */}
            <label className="control control-toggle" htmlFor={ids.prefs}>
              <input
                id={ids.prefs}
                type="checkbox"
                role="switch"
                className="switch"
                checked={showPreferences}
                onChange={(e) => setShowPreferences(e.target.checked)}
                data-testid="show-preferences"
              />
              <span>Show preferences</span>
            </label>

            <div className="control control-actions">
              <button
                type="submit"
                className="btn btn-primary"
                aria-disabled={loading || undefined}
                aria-describedby={ids.privacy}
                data-testid="check"
              >
                {loading ? (
                  <>
                    <span className="spinner" aria-hidden="true" />
                    Checking…
                  </>
                ) : (
                  "Check"
                )}
              </button>
              {loading ? (
                <button type="button" className="btn btn-quiet" onClick={() => abortRef.current?.abort()}>
                  Cancel
                </button>
              ) : (
                <span className="kbd-hint" aria-hidden="true">
                  <kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>Enter</kbd>
                </span>
              )}
            </div>
          </div>

          <div className="privacy">
            <p id={ids.privacy} className="privacy-line">
              <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
                <rect x="3" y="7" width="10" height="7" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.4" />
                <path d="M5.5 7V5a2.5 2.5 0 015 0v2" fill="none" stroke="currentColor" strokeWidth="1.4" />
              </svg>
              Your text is analysed in memory and never stored.
            </p>
            <details className="local-note">
              <summary>Prefer it never leaves your computer?</summary>
              <p>
                Local mode runs the same checks on your own machine, through the Researchly command-line tool or the
                VS&nbsp;Code extension, so no text is sent over the network at all. This page never saves your text,
                and it uses no cookies, analytics or third-party scripts.
              </p>
            </details>
          </div>
        </form>
        <ReadingKey className={checked ? "key-has-results" : undefined} onExample={hasText ? undefined : onExample} />
      </div>

      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true" data-testid="announcer">
        {announcement}
      </div>

      {error ? (
        <div
          ref={errorRef}
          className={`notice notice-error notice-${error.kind}`}
          role="alert"
          tabIndex={-1}
          data-testid="check-error"
          data-kind={error.kind}
        >
          <p className="notice-title">{error.title}</p>
          <p className="notice-text">{error.message}</p>
          {error.requestId ? (
            <p className="notice-text">
              <span className="notice-label">Reference:</span>{" "}
              <code className="request-id" data-testid="request-id">
                {error.requestId}
              </code>
            </p>
          ) : null}
          {error.retryable ? (
            <button type="button" className="btn btn-secondary" onClick={() => void runCheck()} data-testid="retry">
              Try again
            </button>
          ) : null}
        </div>
      ) : null}

      {loading && !checked ? (
        <div className="loading-card" aria-hidden="true">
          <div className="skeleton" />
          <div className="skeleton short" />
          <div className="skeleton" />
        </div>
      ) : null}

      {checked ? (
        <Results
          key={checked.seq}
          data={checked.data}
          submittedText={checked.text}
          showPreferences={showPreferences}
          stale={checked.text !== text || checked.format !== format}
          busy={loading}
          onRevealPreferences={onRevealPreferences}
        />
      ) : null}
    </>
  );
}
