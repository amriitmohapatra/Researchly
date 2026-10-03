/**
 * The signed-in user's settings and dictionary, read and written by the
 * browser directly in Supabase (docs/s2-design.md §5). These are not
 * document text; the engine only reads them, with the user's own token.
 *
 * Ownership is enforced server-side by Row-Level Security. This client also
 * never sends a user id it did not get from its own session: inserts rely on
 * the column default `auth.uid()`, and the only filter by id is the caller's own.
 */
import "client-only";
import type { SupabaseClient } from "@supabase/supabase-js";
import { normaliseSettings, withRule, withoutRule, type UserSettings } from "./settings";
import { getSupabase } from "./supabase";

export type AccountResult<T> = { ok: true; data: T } | { ok: false; message: string };

interface DbError {
  code?: string;
  message?: string;
  status?: number;
}

const OFFLINE = "Could not reach your account. Check your connection and try again; nothing was changed.";

/** A database or network failure as a sentence. Postgres's own text is for developers, not shown. */
export function accountErrorMessage(err: DbError | null | undefined): string {
  switch (err?.code) {
    case "23514": // check_violation: the 5,000-word cap trigger, or the word-shape check
      return /full/i.test(err.message ?? "")
        ? "Your dictionary is full (5,000 words). Remove a word to add another."
        : "That word can't be added: words are 1 to 64 characters with no spaces.";
    case "42501":
    case "PGRST301":
    case "PGRST303":
      return "Your sign-in has expired. Sign in again; nothing was changed.";
    default:
      return err?.message?.toLowerCase().includes("fetch") ? OFFLINE : "Your account could not be updated just now. Try again; nothing was changed.";
  }
}

async function client(): Promise<SupabaseClient | null> {
  const pending = getSupabase();
  return pending ? pending : null;
}

/** Never rejects: a failed load of supabase-js or a thrown fetch becomes a message. */
async function run<T>(fn: (sb: SupabaseClient) => Promise<AccountResult<T>>): Promise<AccountResult<T>> {
  try {
    const sb = await client();
    if (!sb) return { ok: false, message: "Accounts are not available on this site." };
    return await fn(sb);
  } catch {
    return { ok: false, message: OFFLINE };
  }
}

/** The caller's settings; defaults when they have never saved any (no row). */
export function loadSettings(): Promise<AccountResult<UserSettings>> {
  return run(async (sb) => {
    const { data, error } = await sb
      .from("user_settings")
      .select("disabled_rules, show_preferences, locale")
      .maybeSingle();
    return error ? { ok: false, message: accountErrorMessage(error) } : { ok: true, data: normaliseSettings(data) };
  });
}

/** Upsert the caller's row with these fields (the row's user_id defaults to auth.uid()). */
export function saveSettings(patch: Partial<UserSettings>): Promise<AccountResult<UserSettings>> {
  return run(async (sb) => {
    const { data, error } = await sb
      .from("user_settings")
      // user_id defaults to auth.uid(); updated_at is set by a trigger.
      .upsert(patch, { onConflict: "user_id" })
      .select("disabled_rules, show_preferences, locale")
      .maybeSingle();
    return error ? { ok: false, message: accountErrorMessage(error) } : { ok: true, data: normaliseSettings(data) };
  });
}

async function updateRules(change: (rules: readonly string[]) => string[]): Promise<AccountResult<UserSettings>> {
  const current = await loadSettings();
  if (!current.ok) return current;
  return saveSettings({ disabled_rules: change(current.data.disabled_rules) });
}

export function muteRule(id: string) {
  return updateRules((rules) => withRule(rules, id));
}

export function unmuteRule(id: string) {
  return updateRules((rules) => withoutRule(rules, id));
}

export function listWords(): Promise<AccountResult<string[]>> {
  return run(async (sb) => {
    const { data, error } = await sb.from("dictionary_words").select("word").order("word", { ascending: true });
    if (error) return { ok: false, message: accountErrorMessage(error) };
    const words = (data ?? []).map((r: { word?: unknown }) => r.word).filter((w): w is string => typeof w === "string");
    return { ok: true, data: words };
  });
}

/** Add one word (its user_id defaults to auth.uid()). Adding a word that is already there is not an error. */
export function addWord(word: string): Promise<AccountResult<null>> {
  return run(async (sb) => {
    const { error } = await sb.from("dictionary_words").insert({ word });
    if (error && error.code !== "23505") return { ok: false, message: accountErrorMessage(error) };
    return { ok: true, data: null };
  });
}

export function removeWord(word: string): Promise<AccountResult<null>> {
  return run(async (sb) => {
    const { error } = await sb.from("dictionary_words").delete().eq("word", word);
    return error ? { ok: false, message: accountErrorMessage(error) } : { ok: true, data: null };
  });
}

/** "Delete my settings and dictionary": every row this user owns, in both tables. */
export function deleteMyData(): Promise<AccountResult<null>> {
  return run(async (sb) => {
    const { data } = await sb.auth.getSession();
    const uid = data.session?.user.id;
    if (!uid) return { ok: false, message: "Sign in again to delete your data; nothing was changed." };
    // Filtered by the caller's own id (from its own session): PostgREST refuses
    // an unfiltered delete, and RLS would scope it to this user anyway.
    const words = await sb.from("dictionary_words").delete().eq("user_id", uid);
    if (words.error) return { ok: false, message: accountErrorMessage(words.error) };
    const settings = await sb.from("user_settings").delete().eq("user_id", uid);
    if (settings.error) return { ok: false, message: accountErrorMessage(settings.error) };
    return { ok: true, data: null };
  });
}
