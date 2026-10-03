"use client";

import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type ChangeEvent,
  type DragEvent,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import Link from "next/link";
import {
  MAX_CONTENT_CHARS,
  type AnalyzeFileResponse,
  type AnalyzeResponse,
  type Format,
  type Suggestion,
} from "@researchly/contract";
import { addWord, loadSettings, muteRule } from "@/lib/account";
import { getEngineAuth, openSignIn, useAuth } from "@/lib/auth";
import { analyze, analyzeFile } from "@/lib/engine";
import { clientError, UPLOAD_TYPES_SENTENCE, type CheckError } from "@/lib/errors";
import { loadFormat, saveFormat, subscribeFormat } from "@/lib/prefs";
import { codePointLength } from "@/lib/segments";
import { ACCEPT_ATTR, checkFile } from "@/lib/source";
import { FORMATS, isFormat, validateContent, type InputProblem } from "@/lib/validate";
import { revealNeedsRecheck, shownSuggestions, summarySentence } from "@/lib/view";
import { FilePanel, type DropHandlers } from "./FilePanel";
import { ReadingKey } from "./ReadingKey";
import { Results } from "./Results";
import type { CardActions } from "./SuggestionCard";

type Phase = "idle" | "loading" | "done" | "error";
/** Pasting into the editor (S1), or reading an uploaded file (S2, signed in). */
type Mode = "paste" | "file";
type Target = { kind: "paste" } | { kind: "file"; file: File };

interface Checked {
  /** Increments per completed check; remounts the results view (fresh selection). */
  seq: number;
  data: AnalyzeResponse;
  text: string;
  format: Format;
}

interface FileChecked {
  seq: number;
  data: AnalyzeFileResponse;
  /** Kept in memory only, so a re-check (after muting a rule) can send it again. */
  file: File;
}

type AccountNote = { ok: boolean; text: string; settingsLink?: boolean };

const fmt = new Intl.NumberFormat("en-GB");

/** Written for this page (no third-party text). Inserted only into an empty editor; nothing is sent until Check. */
const EXAMPLE_DRAFT =
  "Methods\nCase counts were analysed using a renewal model with a seven day generation interval. Data was collected from 2019 to 2023.\n\nDiscussion\nIn order to understand the the dynamics of transmission, further studies are needed. It is clearly proven that vector control works.\n";

const FILE_NEEDS_ACCOUNT = `Checking a file needs an account. Sign in, then choose the file again. Researchly reads ${UPLOAD_TYPES_SENTENCE}`;

function isFileDrag(e: DragEvent<HTMLElement>): boolean {
  return Array.from(e.dataTransfer?.types ?? []).includes("Files");
}

export function Checker() {
  const { auth } = useAuth();
  // "off": a build without accounts. Everything account-related below is then absent (S1).
  const accounts = auth.status !== "off";
  const signedIn = auth.status === "signed_in";

  const [text, setText] = useState("");
  // The only remembered setting. Server render and first client render agree on null.
  const storedFormat = useSyncExternalStore(subscribeFormat, loadFormat, () => null);
  const [chosenFormat, setFormat] = useState<Format | null>(null);
  const format: Format = chosenFormat ?? storedFormat ?? "plain";
  const [showPreferences, setShowPreferences] = useState(false);
  const [problem, setProblem] = useState<InputProblem | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [mode, setMode] = useState<Mode>("paste");
  const [checked, setChecked] = useState<Checked | null>(null);
  const [fileChecked, setFileChecked] = useState<FileChecked | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [fileProblem, setFileProblem] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [accountNote, setAccountNote] = useState<AccountNote | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [error, setError] = useState<CheckError | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const loadingRef = useRef(false);
  const prefsTouched = useRef(false);
  /** The file whose results are on screen, read synchronously (state may lag inside a running check). */
  const shownFileRef = useRef<File | null>(null);
  const dragDepth = useRef(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  const ids = {
    text: useId(),
    hint: useId(),
    problem: useId(),
    format: useId(),
    prefs: useId(),
    privacy: useId(),
    upload: useId(),
  };

  useEffect(() => () => abortRef.current?.abort(), []);

  // Move focus to a new error (or sign-in prompt) once it is on screen, so
  // keyboard and screen-reader users land on it.
  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  // Nothing is saved anywhere, so leaving the page loses the draft: ask first.
  const hasText = text.trim().length > 0;
  useEffect(() => {
    if (!hasText) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [hasText]);

  // Signed in: start from the account's "show preferences" choice (the engine applies it either way).
  useEffect(() => {
    if (!signedIn) return;
    let live = true;
    void loadSettings().then((r) => {
      if (live && r.ok && r.data.show_preferences && !prefsTouched.current) setShowPreferences(true);
    });
    return () => {
      live = false;
    };
  }, [signedIn]);

  const onExample = () => {
    setText(EXAMPLE_DRAFT);
    setProblem(null);
    textareaRef.current?.focus();
  };

  const runCheck = useCallback(
    async (target: Target = { kind: "paste" }, opts?: { showPreferences?: boolean }) => {
      if (loadingRef.current) return;
      const prefs = opts?.showPreferences ?? showPreferences;
      const submitted = text;
      if (target.kind === "paste") {
        const invalid = validateContent(text);
        setProblem(invalid);
        if (invalid) {
          textareaRef.current?.focus();
          return;
        }
      }
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      loadingRef.current = true;
      setPhase("loading");
      setError(null);
      setAnnouncement(target.kind === "file" ? `Checking ${target.file.name}…` : "Checking your text…");
      // The bearer token (signed in) is fetched at call time; null signed out or without accounts.
      const auth = getEngineAuth();
      const fail = (e: CheckError) => {
        setError(e);
        setPhase("error");
        setAnnouncement("");
      };
      try {
        if (target.kind === "paste") {
          const r = await analyze({ content: submitted, format, showPreferences: prefs, signal: ctrl.signal }, undefined, auth);
          if (r.ok) {
            setChecked((prev) => ({ seq: (prev?.seq ?? 0) + 1, data: r.data, text: submitted, format }));
            setPhase("done");
            setAnnouncement(summarySentence(shownSuggestions(r.data, prefs)));
          } else fail(r.error);
        } else {
          const r = await analyzeFile({ file: target.file, showPreferences: prefs, signal: ctrl.signal }, undefined, auth);
          if (r.ok) {
            shownFileRef.current = target.file;
            setFileChecked((prev) => ({ seq: (prev?.seq ?? 0) + 1, data: r.data, file: target.file }));
            setPhase("done");
            setAnnouncement(summarySentence(shownSuggestions(r.data, prefs)));
          } else fail(r.error);
        }
      } catch {
        if (!ctrl.signal.aborted) {
          // Not a cancel: something failed before the request went out.
          fail(clientError());
          return;
        }
        // Cancelled by the user. Nothing to report beyond that.
        if (target.kind === "file" && shownFileRef.current !== target.file) {
          // A new file was cancelled before any result: back to the editor.
          setMode("paste");
          setPendingFile(null);
          setPhase(checked ? "done" : "idle");
        } else {
          setPhase((target.kind === "file" ? shownFileRef.current : checked) ? "done" : "idle");
        }
        setAnnouncement(target.kind === "file" ? "Check cancelled." : "Check cancelled. Your text is unchanged.");
      } finally {
        loadingRef.current = false;
        abortRef.current = null;
      }
    },
    [text, format, showPreferences, checked],
  );

  /** Check again whatever is on screen: the file, or the editor's text. */
  const recheck = useCallback(
    (opts?: { showPreferences?: boolean }) => {
      // In file mode, the file on screen, or the one whose first check failed.
      const file = fileChecked?.file ?? pendingFile;
      if (mode === "file") return file ? runCheck({ kind: "file", file }, opts) : undefined;
      return runCheck({ kind: "paste" }, opts);
    },
    [mode, fileChecked, pendingFile, runCheck],
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
    prefsTouched.current = true;
    setShowPreferences(true);
    const data = mode === "file" ? fileChecked?.data : checked?.data;
    if (data && revealNeedsRecheck(data)) void recheck({ showPreferences: true });
  };

  const onPrefsChange = (v: boolean) => {
    prefsTouched.current = true;
    setShowPreferences(v);
  };

  /* ---------- files (S2) ---------- */

  const startFile = (file: File | undefined) => {
    if (!file || loadingRef.current) return;
    setFileProblem(null);
    if (!signedIn) {
      openSignIn(FILE_NEEDS_ACCOUNT);
      return;
    }
    const bad = checkFile(file);
    if (bad) {
      setFileProblem(bad.message);
      return;
    }
    setMode("file");
    setFileChecked(null);
    shownFileRef.current = null;
    setPendingFile(file);
    setAccountNote(null);
    void runCheck({ kind: "file", file });
  };

  const chooseFile = () => {
    if (!signedIn) {
      openSignIn(FILE_NEEDS_ACCOUNT);
      return;
    }
    fileInputRef.current?.click();
  };

  const onFileInput = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // choosing the same file again still fires
    startFile(file);
  };

  const backToEditor = () => {
    abortRef.current?.abort();
    setMode("paste");
    setFileChecked(null);
    shownFileRef.current = null;
    setPendingFile(null);
    setFileProblem(null);
    setError(null);
    setAccountNote(null);
    setPhase(checked ? "done" : "idle");
    requestAnimationFrame(() => textareaRef.current?.focus());
  };

  const dropHandlers: DropHandlers = {
    onDragEnter: (e) => {
      if (!isFileDrag(e)) return;
      e.preventDefault();
      dragDepth.current += 1;
      setDragging(true);
    },
    onDragOver: (e) => {
      if (!isFileDrag(e)) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
    },
    onDragLeave: (e) => {
      if (!isFileDrag(e)) return;
      dragDepth.current = Math.max(0, dragDepth.current - 1);
      if (dragDepth.current === 0) setDragging(false);
    },
    onDrop: (e) => {
      if (!isFileDrag(e)) return;
      e.preventDefault();
      dragDepth.current = 0;
      setDragging(false);
      const files = e.dataTransfer.files;
      if (files.length > 1) {
        setFileProblem("Drop one file at a time. For a LaTeX project, drop the Overleaf .zip.");
        return;
      }
      startFile(files[0]);
    },
  };

  const dropOverlay = dragging ? (
    <div className="drop-overlay" aria-hidden="true">
      <p className="drop-title">{signedIn ? "Drop to check this file" : "Sign in to check files"}</p>
      <p className="drop-sub">Your pasted text stays in the editor.</p>
    </div>
  ) : null;

  /* ---------- account actions on cards (S2, signed in) ---------- */

  const onMute = useCallback(
    async (s: Suggestion) => {
      setActionBusy(true);
      setAccountNote(null);
      const r = await muteRule(s.rule_id);
      setActionBusy(false);
      if (!r.ok) {
        setAccountNote({ ok: false, text: r.message });
        return;
      }
      setAccountNote({
        ok: true,
        text: `Muted “${s.rule_name}”. It stays muted wherever you sign in.`,
        settingsLink: true,
      });
      void recheck();
    },
    [recheck],
  );

  const onAddWord = useCallback(
    async (_s: Suggestion, word: string) => {
      setActionBusy(true);
      setAccountNote(null);
      const r = await addWord(word);
      setActionBusy(false);
      if (!r.ok) {
        setAccountNote({ ok: false, text: r.message });
        return;
      }
      setAccountNote({ ok: true, text: `Added “${word}” to your dictionary.`, settingsLink: true });
      void recheck();
    },
    [recheck],
  );

  const loading = phase === "loading";
  const cardActions = useMemo<CardActions | null>(
    () => (signedIn ? { onMute, onAddWord, busy: actionBusy || loading } : null),
    [signedIn, onMute, onAddWord, actionBusy, loading],
  );

  const chars = codePointLength(text);
  const overLimit = chars > MAX_CONTENT_CHARS;
  const describedBy = [ids.hint, problem ? ids.problem : null].filter(Boolean).join(" ");
  const current = mode === "file" ? fileChecked : checked;
  const signInPrompt = accounts && error?.kind === "sign_in_required";

  return (
    <>
      <div className="studio">
        {mode === "file" ? (
          <FilePanel
            name={(pendingFile ?? fileChecked?.file)?.name ?? "Your file"}
            source={fileChecked?.data.document ?? null}
            extraWarnings={fileChecked?.data.warnings}
            words={fileChecked?.data.metrics?.words ?? null}
            loading={loading}
            problem={fileProblem}
            showPreferences={showPreferences}
            onShowPreferences={onPrefsChange}
            onChooseFile={chooseFile}
            onCancel={() => abortRef.current?.abort()}
            onBack={backToEditor}
            dropHandlers={dropHandlers}
            dropOverlay={dropOverlay}
          />
        ) : (
          <form className="panel composer" onSubmit={onSubmit} onKeyDown={onKeyDown} aria-labelledby="composer-title" noValidate>
            <h2 id="composer-title" className="sr-only">
              Check your writing
            </h2>
            <div className={`field${accounts ? " drop-zone" : ""}`} {...(accounts ? dropHandlers : {})}>
              {accounts ? dropOverlay : null}
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

            {accounts ? (
              <div className="upload-row" data-testid="upload-row">
                <button
                  type="button"
                  className="btn btn-quiet btn-upload"
                  onClick={chooseFile}
                  aria-describedby={ids.upload}
                  data-testid="choose-file"
                >
                  <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
                    <path d="M8 10.5V2.5M4.75 5.5 8 2.25l3.25 3.25" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    <path d="M2.5 10v3.25h11V10" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  Check a file instead
                </button>
                <p id={ids.upload} className="help upload-help">
                  {signedIn
                    ? "A .docx, .tex, Overleaf .zip, .md, .qmd, .Rmd or .txt file up to 25 MB. You can also drop it on the box above."
                    : "Needs an account: sign in to check a .docx, .tex, Overleaf .zip, .md, .qmd, .Rmd or .txt file."}
                </p>
                {fileProblem ? (
                  <p className="field-problem upload-problem" role="alert" data-testid="file-problem">
                    {fileProblem}
                  </p>
                ) : null}
              </div>
            ) : null}

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
                  onChange={(e) => onPrefsChange(e.target.checked)}
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
        )}
        <ReadingKey
          className={current ? "key-has-results" : undefined}
          onExample={mode === "paste" && !hasText ? onExample : undefined}
        />
      </div>

      {accounts ? (
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPT_ATTR}
          hidden
          tabIndex={-1}
          onChange={onFileInput}
          data-testid="file-input"
        />
      ) : null}

      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true" data-testid="announcer">
        {announcement}
      </div>

      {accountNote ? (
        <div
          className={`notice ${accountNote.ok ? "notice-quiet" : "notice-error"} account-note`}
          role={accountNote.ok ? "status" : "alert"}
          data-testid="account-note"
        >
          <p className="notice-text">
            {accountNote.text}
            {accountNote.settingsLink ? (
              <>
                {" "}
                <Link href="/settings" className="inline-link">
                  Change this in Settings
                </Link>
              </>
            ) : null}
          </p>
        </div>
      ) : null}

      {signInPrompt && error ? (
        <section
          ref={errorRef}
          className="panel sign-in-prompt"
          tabIndex={-1}
          aria-labelledby="sign-in-prompt-title"
          data-testid="sign-in-prompt"
        >
          <h2 id="sign-in-prompt-title" className="panel-title">
            {error.title}
          </h2>
          <p className="notice-text">{error.message}</p>
          <p className="muted">
            {mode === "paste" ? "Your text is still in the editor. " : ""}Nothing was checked or stored.
          </p>
          <button type="button" className="btn btn-secondary" onClick={() => openSignIn()} data-testid="prompt-sign-in">
            Sign in
          </button>
        </section>
      ) : error ? (
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
            <button type="button" className="btn btn-secondary" onClick={() => void recheck()} data-testid="retry">
              Try again
            </button>
          ) : null}
          {error.signIn && accounts ? (
            <button type="button" className="btn btn-secondary" onClick={() => openSignIn()} data-testid="error-sign-in">
              Sign in
            </button>
          ) : null}
        </div>
      ) : null}

      {loading && !current ? (
        <div className="loading-card" aria-hidden="true">
          <div className="skeleton" />
          <div className="skeleton short" />
          <div className="skeleton" />
        </div>
      ) : null}

      {signInPrompt ? null : mode === "file" && fileChecked ? (
        <Results
          key={`f${fileChecked.seq}`}
          data={fileChecked.data}
          submittedText={fileChecked.data.document.text}
          showPreferences={showPreferences}
          stale={false}
          busy={loading}
          onRevealPreferences={onRevealPreferences}
          source={fileChecked.data.document}
          actions={cardActions}
        />
      ) : mode === "paste" && checked ? (
        <Results
          key={checked.seq}
          data={checked.data}
          submittedText={checked.text}
          showPreferences={showPreferences}
          stale={checked.text !== text || checked.format !== format}
          busy={loading}
          onRevealPreferences={onRevealPreferences}
          actions={cardActions}
        />
      ) : null}
    </>
  );
}
