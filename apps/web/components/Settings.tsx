"use client";

import Link from "next/link";
import { useEffect, useId, useMemo, useRef, useState, type FormEvent } from "react";
import type { RuleInfo, Spelling } from "@researchly/contract";
import {
  addWord,
  clearDictionary,
  deleteMyAccount,
  listWords,
  loadSettings,
  loadSpelling,
  removeWord,
  resetPreferences,
  saveSettings,
  saveSpelling,
  unmuteRule,
} from "@/lib/account";
import { openSignIn, signOut, useAuth } from "@/lib/auth";
import { deleteProgress, loadKeepProgress, saveKeepProgress } from "@/lib/progress";
import { CATEGORIES, categoryMeta } from "@/lib/categories";
import { listRules } from "@/lib/engine";
import { saveDocumentTypeChoice, saveSpellingChoice } from "@/lib/prefs";
import {
  LOCALES,
  MAX_DICTIONARY_WORDS,
  validateWord,
  type Locale,
  type UserSettings,
} from "@/lib/settings";
import { SPELLING_LABELS } from "@/lib/spelling";
import { CategoryIcon } from "./CategoryIcon";
import { AccountDeleted, DeleteAccount } from "./DeleteAccount";
import { ConfirmDelete } from "./pages/ConfirmDelete";
import { SpellingSelect } from "./SpellingSelect";

const nf = new Intl.NumberFormat("en-GB");
/** Above this many words the list gets a filter box. */
const FILTER_FROM = 24;

type Status = { ok: boolean; text: string } | null;

/**
 * The signed-in user's muted rules, display choices and dictionary, read and
 * written straight from the browser to Supabase (RLS scopes every row to the
 * caller). Each change saves at once and says so.
 */
export function Settings() {
  const { auth } = useAuth();
  /** The account was deleted on this page: say so, then sign this browser out. */
  const [deleted, setDeleted] = useState(false);

  useEffect(() => {
    if (deleted) void signOut();
  }, [deleted]);

  if (deleted) return <AccountDeleted />;
  if (auth.status === "loading" || auth.status === "off") {
    return (
      <div className="loading-card" aria-hidden="true">
        <div className="skeleton" />
        <div className="skeleton short" />
      </div>
    );
  }
  if (auth.status === "signed_out") {
    return (
      <section className="panel settings-gate" aria-labelledby="gate-title" data-testid="settings-signed-out">
        <h2 id="gate-title" className="panel-title">
          Sign in to see your settings
        </h2>
        <p className="muted">
          Your muted rules and dictionary are kept with your account, so they apply on every device you sign in on.
        </p>
        <button type="button" className="btn btn-primary" onClick={() => openSignIn()}>
          Sign in
        </button>
      </section>
    );
  }
  return <SignedInSettings key={auth.email} onAccountDeleted={() => setDeleted(true)} />;
}

function SignedInSettings({ onAccountDeleted }: { onAccountDeleted: () => void }) {
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [words, setWords] = useState<string[] | null>(null);
  const [rules, setRules] = useState<Map<string, RuleInfo> | null>(null);
  const [rulesFailed, setRulesFailed] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>(null);
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  /** "Keep my progress" (S4c): null while loading; loaded on its own, so a database without the column fails only this. */
  const [keep, setKeep] = useState<boolean | null>(null);
  const [keepError, setKeepError] = useState<string | null>(null);
  /**
   * The English spelling to keep to (task #15): Auto until loaded; loaded on
   * its own, so a database without the spelling migration fails only this.
   */
  const [spelling, setSpelling] = useState<Spelling>("auto");
  const [spellingError, setSpellingError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    void loadSpelling().then((r) => {
      if (!live) return;
      if (r.ok) {
        setSpelling(r.data ?? "auto");
        setSpellingError(null);
      } else setSpellingError(r.message);
    });
    return () => {
      live = false;
    };
  }, [reload]);

  useEffect(() => {
    let live = true;
    void loadKeepProgress().then((r) => {
      if (!live) return;
      if (r.ok) {
        setKeep(r.data);
        setKeepError(null);
      } else setKeepError(r.message);
    });
    return () => {
      live = false;
    };
  }, [reload]);

  useEffect(() => {
    let live = true;
    const ctrl = new AbortController();
    void Promise.all([loadSettings(), listWords()]).then(([s, w]) => {
      if (!live) return;
      if (!s.ok || !w.ok) {
        setLoadError(!s.ok ? s.message : !w.ok ? w.message : null);
        return;
      }
      setLoadError(null);
      setSettings(s.data);
      setWords(w.data);
    });
    // Rule names and descriptions come from the engine (no text is sent).
    void listRules(undefined, ctrl.signal)
      .then((r) => {
        if (!live) return;
        if (r.ok) setRules(new Map(r.data.map((x) => [x.id, x])));
        else setRulesFailed(true);
      })
      .catch(() => undefined);
    return () => {
      live = false;
      ctrl.abort();
    };
  }, [reload]);

  /** Run one change; every outcome is announced. */
  const act = async <T,>(
    fn: () => Promise<{ ok: true; data: T } | { ok: false; message: string }>,
    done: (data: T) => string,
  ): Promise<boolean> => {
    if (busy) return false;
    setBusy(true);
    const r = await fn();
    setBusy(false);
    setStatus(r.ok ? { ok: true, text: done(r.data) } : { ok: false, text: r.message });
    return r.ok;
  };

  if (loadError) {
    return (
      <div className="notice notice-error" role="alert" data-testid="settings-load-error">
        <p className="notice-title">Your settings could not be loaded</p>
        <p className="notice-text">{loadError}</p>
        <button type="button" className="btn btn-secondary" onClick={() => setReload((n) => n + 1)}>
          Try again
        </button>
      </div>
    );
  }
  if (!settings || !words) {
    return (
      <div className="loading-card" aria-hidden="true" data-testid="settings-loading">
        <div className="skeleton" />
        <div className="skeleton short" />
        <div className="skeleton" />
      </div>
    );
  }

  return (
    <div className="settings" data-testid="settings">
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true" data-testid="settings-status">
        {status?.ok ? status.text : ""}
      </div>
      {status && !status.ok ? (
        <div className="notice notice-error" role="alert" data-testid="settings-error">
          <p className="notice-text">{status.text}</p>
        </div>
      ) : null}

      <MutedRules
        ids={settings.disabled_rules}
        rules={rules}
        rulesFailed={rulesFailed}
        busy={busy}
        onUnmute={(id) =>
          void act(
            () => unmuteRule(id),
            (s) => {
              setSettings(s);
              return `Unmuted ${rules?.get(id)?.name ?? id}.`;
            },
          )
        }
      />

      <Display
        settings={settings}
        busy={busy}
        spelling={spelling}
        spellingError={spellingError}
        onSpelling={(next) => {
          // The control moves at once; if the save fails it moves back and says why.
          const before = spelling;
          setSpelling(next);
          void act(
            () => saveSpelling(next),
            () => {
              // This browser follows too, so the checker and the taskpane agree before their next sign-in load.
              saveSpellingChoice(next);
              setSpellingError(null);
              return `Spelling set to ${SPELLING_LABELS[next]}.`;
            },
          ).then((saved) => {
            if (!saved) setSpelling(before);
          });
        }}
        onChange={(patch, message) => {
          // The control moves at once; if the save fails it moves back and says why.
          const before = settings;
          setSettings({ ...settings, ...patch });
          void act(
            () => saveSettings(patch),
            (s) => {
              setSettings(s);
              return message;
            },
          ).then((saved) => {
            if (!saved) setSettings(before);
          });
        }}
      />

      <Dictionary
        words={words}
        busy={busy}
        onAdd={(word) =>
          act(
            () => addWord(word),
            () => {
              setWords((w) => [...(w ?? []), word].sort((a, b) => a.localeCompare(b)));
              return `Added “${word}” to your dictionary.`;
            },
          )
        }
        onRemove={(word) =>
          void act(
            () => removeWord(word),
            () => {
              setWords((w) => (w ?? []).filter((x) => x !== word));
              return `Removed “${word}” from your dictionary.`;
            },
          )
        }
        onClear={() =>
          act(clearDictionary, () => {
            setWords([]);
            return "Your dictionary was cleared.";
          })
        }
      />

      <KeepProgress
        keep={keep}
        loadError={keepError}
        busy={busy}
        onChange={(on) => {
          // The switch moves at once; if the save fails it moves back and says why.
          const before = keep;
          setKeep(on);
          void act(
            () => saveKeepProgress(on),
            () =>
              on
                ? "Your progress will be recorded after each check."
                : "Progress is no longer recorded. What was recorded stays until you delete it.",
          ).then((saved) => {
            if (!saved) setKeep(before);
          });
        }}
        onDelete={() => act(deleteProgress, () => "Your recorded progress was deleted.")}
      />

      <AccountControls
        busy={busy}
        onReset={() =>
          act(resetPreferences, (s) => {
            setSettings(s);
            setSpelling("auto");
            // This browser follows too, so the checker and the taskpane agree before their next sign-in load.
            saveSpellingChoice("auto");
            saveDocumentTypeChoice("auto");
            return "Your preferences were reset. Your dictionary and progress are as they were.";
          })
        }
        onDeleteAccount={async () => {
          if (busy) return "Wait for the last change to finish, then try again.";
          setBusy(true);
          const r = await deleteMyAccount();
          setBusy(false);
          if (!r.ok) return r.message;
          onAccountDeleted();
          return null;
        }}
      />
    </div>
  );
}

function MutedRules({
  ids,
  rules,
  rulesFailed,
  busy,
  onUnmute,
}: {
  ids: readonly string[];
  rules: Map<string, RuleInfo> | null;
  rulesFailed: boolean;
  busy: boolean;
  onUnmute: (id: string) => void;
}) {
  return (
    <section className="panel settings-section" aria-labelledby="muted-title" data-testid="muted-rules">
      <h2 id="muted-title" className="panel-title">
        Muted rules
      </h2>
      <p className="muted section-intro">
        Suggestions from these rules are not shown to you, on any device you sign in on.
      </p>
      {ids.length === 0 ? (
        <p className="empty-line" data-testid="muted-empty">
          No rules are muted. To mute one, choose &ldquo;Mute this rule&rdquo; on a suggestion.
        </p>
      ) : (
        <ul className="rule-list">
          {ids.map((id) => {
            const r = rules?.get(id);
            const meta = r ? categoryMeta(r.category) : null;
            return (
              <li key={id} className="rule-row" data-testid="muted-rule">
                <div className="rule-text">
                  <p className="rule-name">
                    {meta ? <CategoryIcon category={meta.id} /> : null}
                    <span>{r?.name ?? "Rule"}</span>
                    <span className="rule-id" translate="no">
                      {id}
                    </span>
                  </p>
                  {r ? (
                    <p className="rule-short">
                      {meta ? <span className="sr-only">{CATEGORIES[meta.id].label}: </span> : null}
                      {r.short}
                    </p>
                  ) : null}
                </div>
                <button
                  type="button"
                  className="btn btn-secondary btn-compact"
                  aria-disabled={busy || undefined}
                  aria-label={`Unmute ${r?.name ?? id}`}
                  onClick={() => {
                    if (!busy) onUnmute(id);
                  }}
                >
                  Unmute
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {rulesFailed && ids.length > 0 ? (
        <p className="help">Rule names could not be loaded from the checking engine, so only their codes are shown.</p>
      ) : null}
    </section>
  );
}

function Display({
  settings,
  busy,
  spelling,
  spellingError,
  onSpelling,
  onChange,
}: {
  settings: UserSettings;
  busy: boolean;
  spelling: Spelling;
  spellingError: string | null;
  onSpelling: (next: Spelling) => void;
  onChange: (patch: Partial<UserSettings>, message: string) => void;
}) {
  const ids = { prefs: useId(), prefsHelp: useId(), spelling: useId(), localeHelp: useId() };
  return (
    <section className="panel settings-section" aria-labelledby="display-title">
      <h2 id="display-title" className="panel-title">
        How suggestions are shown
      </h2>
      <div className="setting-row">
        <label className="control-toggle setting-toggle" htmlFor={ids.prefs}>
          <input
            id={ids.prefs}
            type="checkbox"
            role="switch"
            className="switch"
            checked={settings.show_preferences}
            aria-describedby={ids.prefsHelp}
            aria-disabled={busy || undefined}
            onChange={(e) => {
              if (busy) return;
              const on = e.target.checked;
              onChange({ show_preferences: on }, on ? "Preferences will be shown." : "Preferences will be hidden.");
            }}
            data-testid="settings-show-preferences"
          />
          <span>Show preferences</span>
        </label>
        <p id={ids.prefsHelp} className="help">
          Preferences are matters of taste, so they are hidden unless you switch this on.
        </p>
      </div>
      <div className="setting-row" data-testid="settings-spelling">
        <SpellingSelect
          id={ids.spelling}
          value={spelling}
          busy={busy}
          onChange={(next) => {
            if (next !== spelling) onSpelling(next);
          }}
          note={spellingError ? `Your spelling choice could not be loaded, so Auto applies. ${spellingError}` : null}
        />
      </div>
      <fieldset className="setting-row locale-set" aria-describedby={ids.localeHelp}>
        <legend className="field-label">Grammar checks</legend>
        <p id={ids.localeHelp} className="help">
          Which English the grammar checker reads your text as. Spelling is chosen above.
        </p>
        {LOCALES.map((l) => (
          <label key={l.value} className="radio">
            <input
              type="radio"
              name="locale"
              value={l.value}
              checked={settings.locale === l.value}
              onChange={() => {
                if (busy) return;
                onChange({ locale: l.value as Locale }, `Grammar checks set to ${l.label}.`);
              }}
              data-testid={`locale-${l.value}`}
            />
            <span>
              {l.label} <span className="muted">({l.example})</span>
            </span>
          </label>
        ))}
      </fieldset>
    </section>
  );
}

function Dictionary({
  words,
  busy,
  onAdd,
  onRemove,
  onClear,
}: {
  words: readonly string[];
  busy: boolean;
  onAdd: (word: string) => Promise<boolean>;
  onRemove: (word: string) => void;
  onClear: () => Promise<boolean>;
}) {
  const [draft, setDraft] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const ids = { word: useId(), help: useId(), problem: useId(), filter: useId(), count: useId() };
  const shown = useMemo(() => {
    const f = filter.trim().toLowerCase();
    return f ? words.filter((w) => w.toLowerCase().includes(f)) : words;
  }, [words, filter]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    const p = validateWord(draft, words);
    if (p) {
      setProblem(p.message);
      inputRef.current?.focus();
      return;
    }
    const word = draft.trim();
    if (await onAdd(word)) setDraft("");
    inputRef.current?.focus();
  };

  return (
    <section className="panel settings-section" aria-labelledby="dict-title" data-testid="dictionary">
      <h2 id="dict-title" className="panel-title">
        Your dictionary
      </h2>
      <p className="muted section-intro">
        Words here are never flagged as spelling mistakes: names, models, places, terms from your field.
      </p>
      <form className="word-form" onSubmit={onSubmit} noValidate>
        <div className="field">
          <label htmlFor={ids.word} className="field-label">
            Add a word
          </label>
          <p id={ids.help} className="help">
            One word at a time, up to 64 characters, no spaces.
          </p>
          <div className="word-form-row">
            <input
              id={ids.word}
              ref={inputRef}
              className="input word-input"
              type="text"
              name="word"
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
              value={draft}
              onChange={(e) => {
                setDraft(e.target.value);
                if (problem) setProblem(null);
              }}
              aria-invalid={problem ? true : undefined}
              aria-describedby={[ids.help, problem ? ids.problem : null].filter(Boolean).join(" ")}
              data-testid="word-input"
            />
            <button type="submit" className="btn btn-secondary" aria-disabled={busy || undefined} data-testid="word-add">
              Add
            </button>
          </div>
          {problem ? (
            <p id={ids.problem} className="field-problem" role="alert" data-testid="word-problem">
              {problem}
            </p>
          ) : null}
        </div>
      </form>

      <p className="word-count muted" id={ids.count} data-testid="word-count">
        {words.length === 0
          ? "Your dictionary is empty."
          : `${nf.format(words.length)} of ${nf.format(MAX_DICTIONARY_WORDS)} words`}
      </p>
      {words.length >= FILTER_FROM ? (
        <div className="field word-filter">
          <label htmlFor={ids.filter} className="control-label">
            Find a word
          </label>
          <input
            id={ids.filter}
            className="input"
            type="search"
            name="filter"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            autoComplete="off"
          />
        </div>
      ) : null}
      {words.length > 0 ? (
        <ul className="word-list" aria-describedby={ids.count} data-testid="word-list">
          {shown.map((w) => (
            <li key={w} className="word-item">
              <span className="word" translate="no">
                {w}
              </span>
              <button
                type="button"
                className="btn-link btn-link-quiet"
                aria-label={`Remove ${w}`}
                aria-disabled={busy || undefined}
                onClick={() => {
                  if (!busy) onRemove(w);
                }}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {words.length > 0 && shown.length === 0 ? <p className="muted">No word matches &ldquo;{filter}&rdquo;.</p> : null}
      {words.length > 0 ? (
        <div className="setting-row">
          <ConfirmDelete
            label="Clear my dictionary…"
            title="Clear your dictionary?"
            body={`All ${nf.format(words.length)} ${words.length === 1 ? "word" : "words"} will be removed from your dictionary on every device, so they can be flagged as spelling mistakes again. Your other settings and your progress stay. This can’t be undone.`}
            keepLabel="Keep them"
            confirmLabel="Clear it"
            workingLabel="Clearing…"
            busy={busy}
            onConfirm={onClear}
            testId="clear-dictionary"
          />
        </div>
      ) : null}
    </section>
  );
}

/** The exact help text under the switch (pinned by tests). */
export const KEEP_PROGRESS_HELP =
  "Records how many times each check fired, how many words were checked, which checks ran, Draft or Revise and the checker’s version, after each check. Never your text. Off by default; switching it off stops recording.";

function KeepProgress({
  keep,
  loadError,
  busy,
  onChange,
  onDelete,
}: {
  keep: boolean | null;
  loadError: string | null;
  busy: boolean;
  onChange: (on: boolean) => void;
  onDelete: () => Promise<boolean>;
}) {
  const ids = { keep: useId(), help: useId() };
  return (
    <section className="panel settings-section" aria-labelledby="progress-title" data-testid="keep-progress">
      <h2 id="progress-title" className="panel-title">
        Your progress
      </h2>
      <div className="setting-row">
        <label className="control-toggle setting-toggle" htmlFor={ids.keep}>
          <input
            id={ids.keep}
            type="checkbox"
            role="switch"
            className="switch"
            checked={keep === true}
            aria-describedby={ids.help}
            aria-disabled={busy || keep === null || undefined}
            onChange={(e) => {
              if (busy || keep === null) return;
              onChange(e.target.checked);
            }}
            data-testid="keep-progress-switch"
          />
          <span>Keep my progress</span>
        </label>
        <p id={ids.help} className="help" data-testid="keep-progress-help">
          {KEEP_PROGRESS_HELP}
        </p>
        {loadError ? (
          <p className="field-problem" role="alert" data-testid="keep-progress-error">
            This switch could not be loaded, so it is off. {loadError}
          </p>
        ) : null}
      </div>
      <p className="help settings-progress-links">
        <Link className="inline-link" href="/progress">
          See your progress
        </Link>
      </p>
      <div className="setting-row">
        <ConfirmDelete
          label="Delete my progress…"
          title="Delete your recorded progress?"
          body="Every recorded check (rule counts, word counts and which checks ran) will be removed from your account. Your settings and dictionary stay. This can’t be undone."
          keepLabel="Keep it"
          confirmLabel="Delete it"
          busy={busy}
          onConfirm={onDelete}
          testId="delete-progress"
        />
      </div>
    </section>
  );
}

/** What "Reset preferences" changes and what it keeps (pinned by tests). */
export const RESET_PREFERENCES_BODY =
  "Every muted rule is unmuted, preferences are hidden again, and grammar checks, spelling, Draft or Revise and the article type go back to their defaults, on every device. Your dictionary, your recorded progress and the Keep my progress switch stay as they are.";

/**
 * The account as a whole (PLAN #12): two separate actions, worded apart.
 * Resetting keeps the account and its words; deleting removes everything,
 * and asks for a typed word as well as a second click.
 */
function AccountControls({
  busy,
  onReset,
  onDeleteAccount,
}: {
  busy: boolean;
  onReset: () => Promise<boolean>;
  onDeleteAccount: () => Promise<string | null>;
}) {
  return (
    <section className="panel settings-section" aria-labelledby="account-title" data-testid="account-controls">
      <h2 id="account-title" className="panel-title">
        Your account
      </h2>
      <div className="setting-row" data-testid="reset-preferences">
        <h3 className="field-label">Reset preferences</h3>
        <p className="help section-intro">{RESET_PREFERENCES_BODY}</p>
        <ConfirmDelete
          label="Reset preferences…"
          title="Reset your preferences?"
          body={RESET_PREFERENCES_BODY}
          keepLabel="Keep them"
          confirmLabel="Reset them"
          workingLabel="Resetting…"
          busy={busy}
          onConfirm={onReset}
          testId="reset-preferences"
        />
      </div>
      <div className="setting-row" data-testid="delete-account">
        <h3 className="field-label">Delete my account</h3>
        <p className="help section-intro">
          Deletes your sign-in, settings, dictionary and any recorded progress. It can&rsquo;t be undone. To keep the
          account and start again, reset your preferences instead.
        </p>
        <DeleteAccount busy={busy} onDelete={onDeleteAccount} />
      </div>
    </section>
  );
}

