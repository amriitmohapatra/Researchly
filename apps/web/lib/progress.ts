/**
 * The personal progress view's data (S4): opt-in, counts only.
 *
 * When a signed-in writer has switched "Keep my progress" on, each check
 * records how many times each rule fired, the number of words and the
 * article type. Never text, never a file name. The database refuses a row
 * from a writer who has not opted in (supabase/migrations/
 * 20261008140000_s4_progress.sql), so a bug here cannot start recording.
 */
import "client-only";
import type { SupabaseClient } from "@supabase/supabase-js";
import type { AnalyzeResponse, DocumentType } from "@researchly/contract";
import { accountErrorMessage, type AccountResult } from "./account";
import { getSupabase } from "./supabase";

/** One recorded check, as the progress page reads it. */
export interface ProgressEvent {
  created_at: string;
  words: number;
  document_type: DocumentType;
  counts: Record<string, number>;
  /**
   * The rules the check could show (Codex review N2): a rule outside it was
   * not assessed, which is not zero. null on rows recorded before
   * 2026-10-14, or when the database has not had the migration.
   */
  assessed?: string[] | null;
  mode?: "draft" | "revise" | null;
  /** Engine version + rule-set fingerprint; checks compare only within one. */
  ruleset?: string | null;
}

type RowSource = Pick<AnalyzeResponse, "suggestions" | "metrics" | "profile"> &
  Partial<Pick<AnalyzeResponse, "assessed_rules" | "mode" | "ruleset">>;

const MAX_ASSESSED = 400;
const RULESET = /^[0-9A-Za-z.+_-]{1,40}$/;

const RULE_ID = /^[A-Z]{1,4}[0-9]{2,4}$/;

/** The row a check would record: rule counts, words, article type. Pure, unit-tested. */
export function progressRow(data: RowSource): {
  words: number;
  document_type: DocumentType;
  counts: Record<string, number>;
  assessed: string[] | null;
  mode: "draft" | "revise" | null;
  ruleset: string | null;
} {
  const counts: Record<string, number> = {};
  for (const s of data.suggestions) {
    if (RULE_ID.test(s.rule_id)) counts[s.rule_id] = (counts[s.rule_id] ?? 0) + 1;
  }
  return {
    words: Math.max(0, Math.min(2_000_000, Math.round(data.metrics?.words ?? 0))),
    document_type: data.profile?.id ?? "auto",
    counts,
    // Metadata only (rule ids, a word, a version): never text.
    assessed: data.assessed_rules?.length
      ? [...new Set(data.assessed_rules.filter((id) => RULE_ID.test(id)))].sort().slice(0, MAX_ASSESSED)
      : null,
    mode: data.mode === "draft" || data.mode === "revise" ? data.mode : null,
    ruleset: data.ruleset && RULESET.test(data.ruleset) ? data.ruleset : null,
  };
}

/** Postgres "undefined column": the database has not had the 2026-10-14 migration. */
function missingColumn(error: { code?: string } | null): boolean {
  return error?.code === "42703" || error?.code === "PGRST204";
}

async function run<T>(fn: (sb: SupabaseClient) => Promise<AccountResult<T>>): Promise<AccountResult<T>> {
  try {
    const sb = await getSupabase();
    if (!sb) return { ok: false, message: "Accounts are not available on this site." };
    return await fn(sb);
  } catch {
    return { ok: false, message: "Could not reach your account. Check your connection and try again." };
  }
}

/** Whether the writer has opted in; false when there is no settings row or the column is missing (migration not run). */
export function loadKeepProgress(): Promise<AccountResult<boolean>> {
  return run(async (sb) => {
    const { data, error } = await sb.from("user_settings").select("keep_progress").maybeSingle();
    if (error) return { ok: false, message: accountErrorMessage(error) };
    return { ok: true, data: (data as { keep_progress?: unknown } | null)?.keep_progress === true };
  });
}

export function saveKeepProgress(on: boolean): Promise<AccountResult<null>> {
  return run(async (sb) => {
    const { error } = await sb.from("user_settings").upsert({ keep_progress: on }, { onConflict: "user_id" });
    return error ? { ok: false, message: accountErrorMessage(error) } : { ok: true, data: null };
  });
}

/**
 * Record one check, only when `keep` is true (the caller's loaded opt-in).
 * Fire-and-forget from the surfaces: a failure never affects the check.
 */
export async function recordProgress(data: RowSource, keep: boolean): Promise<AccountResult<null>> {
  if (!keep) return { ok: true, data: null };
  return run(async (sb) => {
    const row = progressRow(data);
    let { error } = await sb.from("progress_events").insert(row);
    if (missingColumn(error)) {
      // A database without the comparability columns: record the counts as before.
      const legacy: Partial<typeof row> = { ...row };
      delete legacy.assessed;
      delete legacy.mode;
      delete legacy.ruleset;
      ({ error } = await sb.from("progress_events").insert(legacy));
    }
    return error ? { ok: false, message: accountErrorMessage(error) } : { ok: true, data: null };
  });
}

/** The newest checks first, at most `limit` (the table keeps 1,000). */
export function loadProgress(limit = 200): Promise<AccountResult<ProgressEvent[]>> {
  return run(async (sb) => {
    const query = (cols: string) =>
      sb.from("progress_events").select(cols).order("created_at", { ascending: false }).limit(limit);
    let { data, error } = await query("created_at, words, document_type, counts, assessed, mode, ruleset");
    if (missingColumn(error)) ({ data, error } = await query("created_at, words, document_type, counts"));
    if (error) return { ok: false, message: accountErrorMessage(error) };
    return { ok: true, data: (data ?? []) as unknown as ProgressEvent[] };
  });
}

/** Delete every recorded check of this writer (RLS scopes it; filtered by their id too). */
export function deleteProgress(): Promise<AccountResult<null>> {
  return run(async (sb) => {
    const { data } = await sb.auth.getSession();
    const uid = data.session?.user.id;
    if (!uid) return { ok: false, message: "Sign in again to delete your progress; nothing was changed." };
    const { error } = await sb.from("progress_events").delete().eq("user_id", uid);
    return error ? { ok: false, message: accountErrorMessage(error) } : { ok: true, data: null };
  });
}
