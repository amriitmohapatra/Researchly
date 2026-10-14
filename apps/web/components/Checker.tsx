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
  type ChecklistChoice,
  type DocumentType,
  type Format,
  type Spelling,
  type Suggestion,
} from "@researchly/contract";
import { addWord, loadDocumentType, loadSettings, loadSpelling, muteRule, saveDocumentType, saveSpelling } from "@/lib/account";
import { getEngineAuth, openSignIn, useAuth } from "@/lib/auth";
import { checklistOffer, checklistOption, type ChecklistSetting } from "@/lib/checklists";
import { createCheckSession, previousMark, type CheckTask } from "@/lib/check-session";
import { analyze, analyzeFile, fetchDemoManuscript } from "@/lib/engine";
import { QUEUE_START, type QueueState } from "@/lib/queue";
import { loadKeepProgress } from "@/lib/progress";
import { recordCheck, textKey } from "@/lib/record-progress";
import { loadChecklistSetting, saveChecklistSetting, subscribeChecklistSetting } from "@/lib/results-prefs";
import { UPLOAD_TYPES_SENTENCE } from "@/lib/errors";
import { ENGINE_URL } from "@/lib/config";
import {
  loadDocumentTypeChoice,
  loadFormat,
  loadSpellingChoice,
  saveDocumentTypeChoice,
  saveFormat,
  saveSpellingChoice,
  subscribeDocumentType,
  subscribeFormat,
  subscribeSpelling,
} from "@/lib/prefs";
import { useChecklistChoices, useProfileChoices } from "@/lib/registry";
import { useRuleScopes } from "@/lib/scope";
import { codePointLength } from "@/lib/segments";
import { resolveSpelling } from "@/lib/spelling";
import { ACCEPT_ATTR, checkFile } from "@/lib/source";
import { FORMATS, isFormat, validateContent, type InputProblem } from "@/lib/validate";
import { revealNeedsRecheck, shownSuggestions, summarySentence } from "@/lib/view";
import { usePredictionSetting, useTextPrediction } from "@/lib/use-prediction";
import { CheckProgress } from "./CheckProgress";
import { ChecklistSelect } from "./ChecklistSelect";
import { FilePanel, type DropHandlers } from "./FilePanel";
import { PredictionStrip, PredictionToggle } from "./PredictionStrip";
import { ProfileSelect } from "./ProfileSelect";
import { ReadingKey } from "./ReadingKey";
import { Results } from "./Results";
import { SpellingSelect } from "./SpellingSelect";
import type { CardActions } from "./SuggestionCard";
import type { ResultsView } from "./ViewTabs";

/** Pasting into the editor (S1), or reading an uploaded file (S2, signed in). */
type Mode = "paste" | "file";
type Target = { kind: "paste" } | { kind: "file"; file: File };

interface Checked {
  /** Increments per completed check; remounts the results view (fresh selection). */
  seq: number;
  data: AnalyzeResponse;
  text: string;
  format: Format;
  /** When the answer arrived (the printed report's "Checked" time). */
  at: Date;
}

interface FileChecked {
  seq: number;
  data: AnalyzeFileResponse;
  /** Kept in memory only, so a re-check (after muting a rule) can send it again. */
  file: File;
  at: Date;
}

type AccountNote = { ok: boolean; text: string; settingsLink?: boolean };

/** What a re-check may change: the toggle, the article type, the spelling, the checklist. */
type CheckOptions = { showPreferences?: boolean; documentType?: DocumentType; spelling?: Spelling; checklist?: ChecklistSetting };

/** Rules muted since the results on screen were checked, keyed to those results (they lapse with the next check). */
type Muted = { key: string; rules: ReadonlySet<string> };

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
  // The article type to check as (S4): this session's choice, else the
  // account's (signed in), else this browser's, else Auto.
  const storedType = useSyncExternalStore(subscribeDocumentType, loadDocumentTypeChoice, () => null);
  const [accountType, setAccountType] = useState<DocumentType | null>(null);
  const [chosenType, setChosenType] = useState<DocumentType | null>(null);
  const documentType: DocumentType = chosenType ?? (signedIn ? accountType : null) ?? storedType ?? "auto";
  const [typeNote, setTypeNote] = useState<string | null>(null);
  // The English spelling to keep to (task #15), resolved like the article
  // type. Null when nothing chose one: the check then leaves it to the engine
  // (the account's saved choice, else Auto).
  const storedSpelling = useSyncExternalStore(subscribeSpelling, loadSpellingChoice, () => null);
  const [accountSpelling, setAccountSpelling] = useState<Spelling | null>(null);
  const [chosenSpelling, setChosenSpelling] = useState<Spelling | null>(null);
  const spelling = resolveSpelling({ chosen: chosenSpelling, account: accountSpelling, stored: storedSpelling, signedIn });
  const [spellingNote, setSpellingNote] = useState<string | null>(null);
  const profiles = useProfileChoices(ENGINE_URL);
  // The reporting checklist (S4): this session's choice, else this browser's, else none.
  const storedChecklist = useSyncExternalStore(subscribeChecklistSetting, loadChecklistSetting, () => null);
  const [chosenChecklist, setChosenChecklist] = useState<ChecklistSetting | null>(null);
  const checklist: ChecklistSetting = chosenChecklist ?? storedChecklist ?? "none";
  const checklists = useChecklistChoices(ENGINE_URL);
  const [muted, setMuted] = useState<Muted | null>(null);
  const [demoProblem, setDemoProblem] = useState<string | null>(null);
  const [demoLoading, setDemoLoading] = useState(false);
  // "Keep my progress" (opt-in, counts only): loaded once per sign-in, read when a check succeeds.
  const keepProgressRef = useRef(false);
  const [view, setView] = useState<ResultsView>("suggestions");
  const [showPreferences, setShowPreferences] = useState(false);
  // The revision queue's pass and place (review proposal 1): held here so a re-check keeps it; never stored.
  const [queue, setQueue] = useState<QueueState>(QUEUE_START);
  const [problem, setProblem] = useState<InputProblem | null>(null);
  // One check at a time (review proposal 8): a cancelled or superseded check's late reply is dropped.
  const [session] = useState(() => createCheckSession<AnalyzeResponse>());
  const run = useSyncExternalStore(session.subscribe, session.getState, session.getState);
  const error = run.error;
  const [mode, setMode] = useState<Mode>("paste");
  const [checked, setChecked] = useState<Checked | null>(null);
  const [fileChecked, setFileChecked] = useState<FileChecked | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [fileProblem, setFileProblem] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [accountNote, setAccountNote] = useState<AccountNote | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const prefsTouched = useRef(false);
  /** The file whose results are on screen, read synchronously (state may lag inside a running check). */
  const shownFileRef = useRef<File | null>(null);
  /** Which results are on screen ("p3", "f1"), read by a mute that completes after a re-render. */
  const resultsKeyRef = useRef<string | null>(null);
  const dragDepth = useRef(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  const ids = {
    text: useId(),
    hint: useId(),
    problem: useId(),
    format: useId(),
    type: useId(),
    spelling: useId(),
    checklist: useId(),
    demo: useId(),
    prefs: useId(),
    privacy: useId(),
    upload: useId(),
  };

  // Word prediction (2026-10-14): candidates after a pause in typing, inserted only on Tab or a click.
  const predictionSetting = usePredictionSetting(signedIn);
  const prediction = useTextPrediction({ ref: textareaRef, text, setText, format, enabled: predictionSetting.on });

  useEffect(() => () => session.dispose(), [session]);

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

  // Signed in: whether the writer keeps their progress. Never blocks a check; a failed load means "no".
  useEffect(() => {
    keepProgressRef.current = false;
    if (!signedIn) return;
    let live = true;
    void loadKeepProgress()
      .then((r) => {
        if (live) keepProgressRef.current = r.ok && r.data;
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [signedIn]);

  // Signed in: the article type comes from the account (shared with the Word add-in).
  useEffect(() => {
    if (!signedIn) return;
    let live = true;
    void loadDocumentType().then((r) => {
      if (live && r.ok && r.data) setAccountType(r.data);
    });
    return () => {
      live = false;
    };
  }, [signedIn]);

  // Signed in: the spelling comes from the account too (shared with the Word add-in).
  useEffect(() => {
    if (!signedIn) return;
    let live = true;
    void loadSpelling().then((r) => {
      if (live && r.ok && r.data) setAccountSpelling(r.data);
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

  // The demo manuscript: a synthetic paper served by this site, loaded into an empty editor. Nothing is sent until Check.
  const onDemo = async () => {
    if (demoLoading) return;
    setDemoProblem(null);
    setDemoLoading(true);
    const r = await fetchDemoManuscript();
    setDemoLoading(false);
    if (!r.ok) {
      setDemoProblem("The demo manuscript could not be loaded. Check your connection and try again.");
      return;
    }
    setText(r.text);
    setFormat("markdown"); // the demo is Markdown; the remembered format is left as it was
    setProblem(null);
    textareaRef.current?.focus();
  };

  /**
   * Check the editor's text or a file. A check already running is
   * superseded (a changed type or checklist, a mute): it is aborted and its
   * reply, if it still comes, is dropped by the session, so an older answer
   * is never shown as the current one. The results on screen stay, marked as
   * previous, until the new answer arrives.
   */
  const runCheck = useCallback(
    async (target: Target = { kind: "paste" }, opts?: CheckOptions) => {
      const prefs = opts?.showPreferences ?? showPreferences;
      const type = opts?.documentType ?? documentType;
      const spell = opts?.spelling ?? spelling;
      const list = checklistOption(opts?.checklist ?? checklist);
      const submitted = text;
      const submittedFormat = format;
      if (target.kind === "paste") {
        const invalid = validateContent(text);
        setProblem(invalid);
        if (invalid) {
          textareaRef.current?.focus();
          return;
        }
      }
      // A signed-in writer who keeps their progress: counts only, fire and forget, never in the way.
      // `signed_in` is the engine's word that the account's token came with this check.
      // A recheck of the same words is not recorded twice (Codex review N2); the key stays in this page's memory.
      const key =
        target.kind === "file"
          ? textKey(`file:${target.file.name}:${target.file.size}:${target.file.lastModified}`)
          : textKey(submitted);
      const record = (data: AnalyzeResponse) =>
        recordCheck(data, { signedIn: data.signed_in === true, keep: keepProgressRef.current, textKey: key });
      // Retry runs this same task again: the same text or file, the same options.
      const task: CheckTask<AnalyzeResponse> = (signal) => {
        setAnnouncement(target.kind === "file" ? `Checking ${target.file.name}…` : "Checking your text…");
        // The bearer token (signed in) is fetched at call time; null signed out or without accounts.
        const auth = getEngineAuth();
        // The website is the revision studio: every check asks for Revise
        // (Codex review R6), so a Draft choice saved from Word never hides
        // the document-wide checks here, and the brief and the narrative map
        // are always asked for.
        const options = { showPreferences: prefs, documentType: type, spelling: spell, review: true, narrative: true, checklist: list, mode: "revise" as const, signal };
        return target.kind === "paste"
          ? analyze({ ...options, content: submitted, format: submittedFormat }, undefined, auth)
          : analyzeFile({ ...options, file: target.file }, undefined, auth);
      };
      await session.start(task, {
        onResult: (data) => {
          if (target.kind === "paste") {
            setChecked((prev) => ({ seq: (prev?.seq ?? 0) + 1, data, text: submitted, format: submittedFormat, at: new Date() }));
          } else {
            shownFileRef.current = target.file;
            const fileData = data as AnalyzeFileResponse;
            setFileChecked((prev) => ({ seq: (prev?.seq ?? 0) + 1, data: fileData, file: target.file, at: new Date() }));
          }
          setMuted(null);
          setAnnouncement(summarySentence(shownSuggestions(data, prefs)));
          record(data);
        },
        onError: () => setAnnouncement(""),
      });
    },
    [session, text, format, showPreferences, documentType, spelling, checklist],
  );

  /** Cancel the running check: the screen goes back to what it showed before, with a note. */
  const cancelCheck = () => {
    const newFile = mode === "file" && shownFileRef.current === null;
    if (!session.cancel()) return;
    if (newFile) {
      // A new file was cancelled before any result: back to the editor, as if it had not been chosen.
      setMode("paste");
      setPendingFile(null);
      session.settle();
      setAnnouncement("Check cancelled.");
      return;
    }
    setAnnouncement(mode === "file" ? "Check cancelled." : "Check cancelled. Your text is unchanged.");
  };

  /** Try again: the same check as the one that failed or was cancelled. */
  const retryCheck = () => {
    void session.retry();
  };

  /** Check again whatever is on screen: the file, or the editor's text. */
  const recheck = useCallback(
    (opts?: CheckOptions) => {
      // In file mode, the file on screen, or the one whose first check failed.
      const file = fileChecked?.file ?? pendingFile;
      if (mode === "file") return file ? runCheck({ kind: "file", file }, opts) : undefined;
      return runCheck({ kind: "paste" }, opts);
    },
    [mode, fileChecked, pendingFile, runCheck],
  );

  // Check (and Ctrl/Cmd+Enter) does nothing while a check runs: the button says so, and Cancel is beside it.
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (session.getState().phase === "running") return;
    void runCheck();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLFormElement>) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      if (session.getState().phase === "running") return;
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
    if (!file || session.getState().phase === "running") return;
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
    session.settle(); // aborts a running check (its reply is dropped) and clears its error
    setMode("paste");
    setFileChecked(null);
    shownFileRef.current = null;
    setPendingFile(null);
    setFileProblem(null);
    setAccountNote(null);
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
      // Its cards leave at once (review proposal 2); the re-check then confirms it from the engine.
      const key = resultsKeyRef.current;
      if (key) setMuted((prev) => ({ key, rules: new Set(prev?.key === key ? prev.rules : []).add(s.rule_id) }));
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

  const loading = run.phase === "running";
  const cardActions = useMemo<CardActions | null>(
    () => (signedIn ? { onMute, onAddWord, busy: actionBusy || loading } : null),
    [signedIn, onMute, onAddWord, actionBusy, loading],
  );

  const chars = codePointLength(text);
  const overLimit = chars > MAX_CONTENT_CHARS;
  const describedBy = [ids.hint, problem ? ids.problem : null].filter(Boolean).join(" ");
  const current = mode === "file" ? fileChecked : checked;
  const signInPrompt = accounts && error?.kind === "sign_in_required";
  // Results on screen while a newer check runs, failed or was cancelled are the previous check's (review proposal 8).
  const previous = previousMark(current !== null, run);

  // A changed type checks again whatever is on screen, exactly as a stage change does in Word.
  const onTypeChange = (next: DocumentType) => {
    if (next === documentType) return;
    setChosenType(next);
    saveDocumentTypeChoice(next);
    setTypeNote(null);
    if (signedIn) {
      void saveDocumentType(next).then((r) => {
        if (r.ok) setAccountType(next);
        else setTypeNote(`This choice could not be saved to your account, so it applies in this browser only. ${r.message}`);
      });
    }
    if (current) void recheck({ documentType: next });
  };
  const typeControl = (
    <ProfileSelect id={ids.type} value={documentType} choices={profiles} onChange={onTypeChange} note={typeNote} />
  );

  // A changed spelling checks again whatever is on screen, like a changed type, and is saved the same way.
  const onSpellingChange = (next: Spelling) => {
    if (next === (spelling ?? "auto")) return;
    setChosenSpelling(next);
    saveSpellingChoice(next);
    setSpellingNote(null);
    if (signedIn) {
      void saveSpelling(next).then((r) => {
        if (r.ok) setAccountSpelling(next);
        else setSpellingNote(`This choice could not be saved to your account, so it applies in this browser only. ${r.message}`);
      });
    }
    if (current) void recheck({ spelling: next });
  };
  const spellingControl = <SpellingSelect id={ids.spelling} value={spelling ?? "auto"} onChange={onSpellingChange} note={spellingNote} />;

  // A changed checklist checks again whatever is on screen, like a changed type. Remembered in this browser only.
  const onChecklistChange = (next: ChecklistSetting) => {
    if (next === checklist) return;
    setChosenChecklist(next);
    saveChecklistSetting(next);
    if (current) void recheck({ checklist: next });
  };
  const checklistControl = <ChecklistSelect id={ids.checklist} value={checklist} choices={checklists} onChange={onChecklistChange} />;
  // The offer under the results: only when no checklist was chosen and the text's words point to one.
  const offer = checklist === "none" ? checklistOffer(current?.data.suggested_checklist, checklists) : null;
  const onUseChecklist = (id: ChecklistChoice) => {
    onChecklistChange(id);
    setView("checklist");
  };
  // Check again in Revise: what an engine that ran Draft held back, or the brief and the map.
  const onRunRevise = () => void recheck();

  // Which rules read the whole document (for the section chooser). Asked once, after the first results; no text is sent.
  const scopes = useRuleScopes(ENGINE_URL, current !== null);
  // The results on screen, for a mute to filter only those (a new check starts clean).
  const resultsKey = mode === "file" ? (fileChecked ? `f${fileChecked.seq}` : null) : checked ? `p${checked.seq}` : null;
  useEffect(() => {
    resultsKeyRef.current = resultsKey;
  }, [resultsKey]);
  const mutedRules = muted && muted.key === resultsKey ? muted.rules : undefined;

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
            typeControl={
              <>
                {typeControl}
                {spellingControl}
              </>
            }
            checklistControl={checklistControl}
            onChooseFile={chooseFile}
            onCancel={cancelCheck}
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
                  prediction.onInput(e);
                }}
                onKeyDown={prediction.onKeyDown}
                onSelect={prediction.onSelect}
                onBlur={prediction.dismiss}
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
              <PredictionStrip candidates={prediction.shown?.candidates ?? null} onAccept={prediction.accept} />
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

            {!hasText ? (
              <div className="demo-row" data-testid="demo-row">
                <button
                  type="button"
                  className="btn btn-quiet"
                  onClick={() => void onDemo()}
                  aria-describedby={ids.demo}
                  aria-disabled={demoLoading || undefined}
                  data-testid="load-demo"
                >
                  Try the demo manuscript
                </button>
                <p id={ids.demo} className="help demo-help">
                  A short invented paper with planted slips, loaded into the editor; nothing is checked until you press Check.
                  Also as a{" "}
                  <a href="/demo/researchly-demo.docx" download className="inline-link" data-testid="demo-docx">
                    Word file (.docx)
                  </a>{" "}
                  or an{" "}
                  <a href="/demo/researchly-demo-overleaf.zip" download className="inline-link" data-testid="demo-zip">
                    Overleaf project (.zip)
                  </a>
                  .
                </p>
                {demoProblem ? (
                  <p className="field-problem" role="alert" data-testid="demo-problem">
                    {demoProblem}
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

              {typeControl}

              {spellingControl}

              {checklistControl}

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

              <PredictionToggle setting={predictionSetting} />

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
                  <button type="button" className="btn btn-quiet" onClick={cancelCheck} data-testid="cancel-check">
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
            <button type="button" className="btn btn-secondary" onClick={retryCheck} data-testid="retry">
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

      {loading && run.startedAt !== null ? (
        <CheckProgress
          key={run.requestId}
          startedAt={run.startedAt}
          what={mode === "file" ? "your file" : "your text"}
          hasPrevious={current !== null && !signInPrompt}
        />
      ) : null}

      {!loading && run.note === "cancelled" ? (
        <div className="notice notice-quiet cancel-note" data-testid="cancelled-note">
          <p className="notice-text">
            Check cancelled.{current ? "" : mode === "paste" ? " Nothing was checked; your text is unchanged." : " Nothing was checked."}{" "}
            <button type="button" className="btn-link" onClick={retryCheck} data-testid="retry-cancelled">
              Check again
            </button>
          </p>
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
          scopes={scopes}
          view={view}
          onView={setView}
          checkedAt={fileChecked.at}
          mutedRules={mutedRules}
          onRunRevise={onRunRevise}
          checklistOffer={offer}
          onUseChecklist={onUseChecklist}
          queue={queue}
          onQueue={setQueue}
          previous={previous}
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
          scopes={scopes}
          view={view}
          onView={setView}
          checkedAt={checked.at}
          mutedRules={mutedRules}
          onRunRevise={onRunRevise}
          checklistOffer={offer}
          onUseChecklist={onUseChecklist}
          queue={queue}
          onQueue={setQueue}
          previous={previous}
        />
      ) : null}
    </>
  );
}
