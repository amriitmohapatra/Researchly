import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { AccountDeleted, CONFIRM_WORD, DELETE_ACCOUNT_BODY, DeleteAccount, confirmWordMatches } from "@/components/DeleteAccount";
import { ConfirmDelete } from "@/components/pages/ConfirmDelete";
import { RESET_PREFERENCES_BODY } from "@/components/Settings";

/** PLAN #12: reset preferences, clear the dictionary, delete the account (lib/account.ts). */

const db = {
  rpcs: [] as { fn: string; args: unknown }[],
  rpcError: null as { code?: string; message?: string } | null,
  deletes: [] as { table: string; column: string; value: unknown }[],
  row: { disabled_rules: [], show_preferences: false, locale: "en-US" } as unknown,
  session: { user: { id: "11111111-1111-4111-8111-111111111111" } } as unknown,
};

vi.mock("@/lib/supabase", () => ({
  getSupabase: () =>
    Promise.resolve({
      rpc: async (fn: string, args?: unknown) => {
        db.rpcs.push({ fn, args });
        return { data: null, error: db.rpcError };
      },
      auth: { getSession: async () => ({ data: { session: db.session } }) },
      from: (table: string) => ({
        select: () => ({ maybeSingle: async () => ({ data: db.row, error: null }) }),
        delete: () => ({
          eq: async (column: string, value: unknown) => {
            db.deletes.push({ table, column, value });
            return { error: null };
          },
        }),
      }),
    }),
}));

const { clearDictionary, deleteErrorMessage, deleteMyAccount, resetPreferences } = await import("@/lib/account");

beforeEach(() => {
  db.rpcs = [];
  db.rpcError = null;
  db.deletes = [];
  db.session = { user: { id: "11111111-1111-4111-8111-111111111111" } };
});

describe("the account calls", () => {
  it("reset calls the database function with no arguments, then reads the settings back", async () => {
    const r = await resetPreferences();
    expect(r).toEqual({ ok: true, data: { disabled_rules: [], show_preferences: false, locale: "en-US" } });
    expect(db.rpcs).toEqual([{ fn: "reset_my_preferences", args: undefined }]);
  });

  it("delete calls the database function with no arguments: the account is the caller's, never one named here", async () => {
    expect(await deleteMyAccount()).toEqual({ ok: true, data: null });
    expect(db.rpcs).toEqual([{ fn: "delete_my_account", args: undefined }]);
    expect(db.deletes).toEqual([]);
  });

  it("says plainly when the database has not had the migration, and that nothing changed", async () => {
    db.rpcError = { code: "PGRST202", message: "Could not find the function" };
    const del = await deleteMyAccount();
    expect(del.ok).toBe(false);
    expect(!del.ok && del.message).toContain("nothing was deleted");
    expect(!del.ok && del.message).toContain("Report a problem");
    const reset = await resetPreferences();
    expect(!reset.ok && reset.message).toBe("Resetting isn’t available on this site yet. Nothing was changed.");
  });

  it("a refused or failed deletion says nothing was deleted", () => {
    expect(deleteErrorMessage({ code: "42501" })).toBe("Your sign-in has expired. Sign in again, then delete your account; nothing was deleted.");
    expect(deleteErrorMessage({ message: "Failed to fetch" })).toContain("Check your connection");
    expect(deleteErrorMessage({ code: "XX000", message: "relation does not exist" })).toBe(
      "Your account could not be deleted just now. Try again; nothing was deleted.",
    );
    // Postgres's own words are never shown.
    expect(deleteErrorMessage({ code: "XX000", message: "relation does not exist" })).not.toContain("relation");
  });

  it("clearing the dictionary removes the caller's words only, by their own id", async () => {
    expect(await clearDictionary()).toEqual({ ok: true, data: null });
    expect(db.deletes).toEqual([{ table: "dictionary_words", column: "user_id", value: "11111111-1111-4111-8111-111111111111" }]);
    db.session = null;
    const r = await clearDictionary();
    expect(r.ok).toBe(false);
    expect(db.deletes).toHaveLength(1);
  });
});

describe("the confirmation word", () => {
  it("is 'delete', in any case, with spaces around it ignored", () => {
    expect(CONFIRM_WORD).toBe("delete");
    for (const ok of ["delete", "DELETE", " Delete ", "delete\n"]) expect(confirmWordMatches(ok)).toBe(true);
    for (const no of ["", "del", "deleted", "delete it", "yes"]) expect(confirmWordMatches(no)).toBe(false);
  });
});

describe("what each action says", () => {
  it("reset says what resets and what stays", () => {
    for (const part of ["unmuted", "preferences are hidden", "grammar checks", "spelling", "Draft or Revise", "article type"]) {
      expect(RESET_PREFERENCES_BODY).toContain(part);
    }
    expect(RESET_PREFERENCES_BODY).toMatch(/Your dictionary, your recorded progress and the Keep my progress switch stay/);
  });

  it("delete says it removes everything, cannot be undone and signs out; there was never any text", () => {
    for (const part of ["sign-in", "muted rules", "dictionary", "recorded progress", "every device", "can’t be undone", "signed out", "never kept any of your text"]) {
      expect(DELETE_ACCOUNT_BODY).toContain(part);
    }
  });

  it("the delete dialog asks for the word and keeps the confirm button usable (it explains rather than being disabled)", () => {
    const html = renderToStaticMarkup(<DeleteAccount busy={false} onDelete={async () => null} />);
    expect(html).toContain("Delete my account…");
    expect(html).toContain('<dialog class="dialog"');
    expect(html).toContain(">To confirm, type delete</label>");
    expect(html).toMatch(/data-testid="delete-account-confirm"[^>]*>Delete my account</);
    expect(html).not.toMatch(/aria-disabled="true"[^>]*data-testid="delete-account-confirm"/); // never disabled: it explains instead
    expect(html).toContain("Keep my account");
  });

  it("the deleted message offers the way back", () => {
    const html = renderToStaticMarkup(<AccountDeleted />);
    expect(html).toContain("Your account was deleted");
    expect(html).toContain('href="/"');
  });

  it("ConfirmDelete says what it is doing while it works", () => {
    const html = renderToStaticMarkup(
      <ConfirmDelete
        label="Reset preferences…"
        title="Reset?"
        body="b"
        keepLabel="Keep them"
        confirmLabel="Reset them"
        workingLabel="Resetting…"
        busy={false}
        onConfirm={async () => undefined}
        testId="t"
      />,
    );
    expect(html).toContain("Reset them");
    expect(html).toContain('data-testid="t-open"');
  });
});
