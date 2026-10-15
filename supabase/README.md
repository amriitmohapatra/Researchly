# supabase/

The database side of Researchly accounts (slice S2, `docs/s2-design.md` §2).
Two tables, both private to their owner by Row-Level Security, plus the test
that proves it.

| Path | What it is |
|---|---|
| `migrations/20261003120000_s2_settings.sql` | The schema: `user_settings`, `dictionary_words`, their RLS policies and grants, and `my_config()` (what the engine reads, with the user's own token). |
| `migrations/20261004120000_s3_mode.sql` | `user_settings.mode` (Draft / Revise); `my_config()` gains it. |
| `migrations/20261008120000_s4_document_type.sql` | `user_settings.document_type` (the article type); `my_config()` gains it. |
| `migrations/20261008140000_s4_progress.sql` | The opt-in `keep_progress` switch and the `progress_events` table (rule counts only). |
| `migrations/20261014120000_spelling_prediction.sql` | `user_settings.spelling`, the English spelling a writer keeps to (`auto`, `us`, `uk`, `uk-oxford`, `ca`, `au`, `in`; PLAN task #15), and `user_settings.prediction`, word prediction on (default) or off; `my_config()` gains both, so the hosted engine applies them. |
| `migrations/20261014130000_progress_comparable.sql` | `progress_events.assessed` (the rule ids a check could show), `.mode` and `.ruleset`, so the progress view compares like with like (Codex review N2); rule ids, a word and a version string, never text. Older rows keep NULLs. |
| `migrations/20261015120000_account_controls.sql` | Account controls (PLAN #12): `reset_my_preferences()` puts the caller's choices back to the column defaults and keeps their dictionary, progress and "Keep my progress" switch (SECURITY INVOKER, RLS decides); `delete_my_account()` deletes the caller's sign-in from `auth.users`, and every row they own goes with it by `ON DELETE CASCADE` (SECURITY DEFINER, one row, `where id = (select auth.uid())`). Neither takes an argument; both are for `authenticated` only. |
| `tests/shim.sql` | A stand-in for the parts of Supabase the migration needs (`auth.users`, `auth.uid()`, roles `anon` / `authenticated`, Supabase's default privileges), so the test runs on plain PostgreSQL 16. **Test only: never run it in Supabase.** |
| `tests/test_two_user.py` | The Q7 two-user test (ARCHITECTURE.md §3): user A can never read, create as, update or delete user B's settings or dictionary, and `anon` can do nothing. Also the limits (200 muted rules, valid rule ids, locales and spellings, 1–64-character words, 5,000 words per user) and account-deletion cascade. Also the account controls: a reset touches only the caller's preferences, deletion removes the caller's sign-in and every row in every table (and nothing of user B's), `anon` and a token without a user id can do neither, and every per-user table cascades from `auth.users`. |
| `tests/run_local.sh` | Runs the test against a throwaway local PostgreSQL 16; no Docker. |

## What is stored, and what is not

| Table | Holds | Limits |
|---|---|---|
| `user_settings` | muted rule ids, show-preferences switch, locale, mode, article type, spelling, prediction switch (unused since 2026-10-15), keep-progress switch, `updated_at` | ≤ 200 rule ids, each like `S001` / `LT001`; locale `en-US` or `en-GB`; spelling one of `auto` (default), `us`, `uk`, `uk-oxford`, `ca`, `au`, `in` |
| `dictionary_words` | one word per row, `added_at` | 1–64 characters, no spaces; ≤ 5,000 per user |

No document text, ever. No `profiles`, usage or feedback tables yet: a table
that exists invites data into it, so each arrives with the feature that needs
it. No row is created at sign-up; a missing settings row means defaults.
Deleting a user deletes their rows, whether the user does it ("Delete my
account" on the website's Settings, `delete_my_account()`) or the owner does
(Authentication → Users). A new per-user table must reference `auth.users`
with `on delete cascade`; without it account deletion fails (loudly), and
the two-user test names the table.

## Applying the migration (owner, once per project)

1. Open the Supabase project → **SQL Editor** → **New query**.
2. Paste the whole of `migrations/20261003120000_s2_settings.sql`.
3. Click **Run**. It should finish with "Success. No rows returned".
4. Check: **Table Editor** shows `user_settings` and `dictionary_words`, each
   marked with RLS enabled; **Database → Policies** shows four policies
   on each, all for the `authenticated` role.

Running it again is safe (it recreates its policies, triggers and functions
and re-states its grants; rows are untouched). It does not change an existing
table's columns or limits: that needs a new, later-dated migration file.

Each later migration is applied the same way, once, in date order (the
file names sort by date): paste the whole file, Run, expect "Success. No
rows returned". All of them are safe to re-run.

**Account controls (2026-10-15, PLAN #12):** after the comparable-progress
migration, paste `migrations/20261015120000_account_controls.sql`. Check:
**Database → Functions** lists `reset_my_preferences` and
`delete_my_account`; and in the SQL Editor
`select has_table_privilege('postgres', 'auth.users', 'DELETE');` returns
`true` (`delete_my_account` runs as `postgres`, the file's owner, and needs
it; Supabase grants it today). Until the migration is applied the website's
"Reset preferences" and "Delete my account" say they are not available yet,
and nothing changes. An access token issued before a deletion stays valid
until it expires (at most an hour) but reaches no rows; the website signs
the browser out at once.

**Comparable progress (2026-10-14):** after the spelling migration, paste
`migrations/20261014130000_progress_comparable.sql`. Check: **Table Editor →
progress_events** shows `assessed`, `mode` and `ruleset` columns. Until it is
applied the website still records progress, without them (older behaviour).

**Spelling and prediction (2026-10-14):** paste
`migrations/20261014120000_spelling_prediction.sql` after the earlier four.
Check: **Table Editor → user_settings** shows a `spelling` column (default
`auto`) and a `prediction` column (default `true`), and
`select public.my_config();` in the SQL Editor (no signed-in user there, so it
returns the defaults) now includes `"spelling": "auto"` and
`"prediction": true`. Until it is applied, the website and the Word add-in
still work: the spelling choice is then kept in the browser only and says it
could not be saved to the account, and prediction stays on.
Word prediction was removed on 2026-10-15: the `prediction` column and its
key in `my_config()` stay, so the deployed database needs no change, but
nothing writes them any more and the engine ignores the key.

## Running the tests

They need a PostgreSQL 16 server and a **superuser** connection string (the
test creates and drops its own throwaway database and the roles `anon`,
`authenticated`, `supabase_auth_admin`, `migration_owner`). Never point it at
Supabase or anything that matters.

```bash
# Easiest: a temporary local cluster, deleted afterwards (macOS: brew install postgresql@16)
python3.10 -m pip install pytest 'psycopg[binary]>=3.2,<4'
PG_BIN=$(brew --prefix postgresql@16)/bin supabase/tests/run_local.sh

# Or against a server you already run
RESEARCHLY_TEST_PG_DSN=postgresql://postgres:postgres@localhost:5432/postgres \
  python3.10 -m pytest supabase/tests -q
```

Without `RESEARCHLY_TEST_PG_DSN` the tests are skipped with a reason. CI sets
`RESEARCHLY_REQUIRE_PG_TESTS=1`, which turns that skip into a failure, so a
misconfigured job cannot report Q7 green by running nothing.

## How the test acts like Supabase

Each step is one transaction that does what PostgREST does for an API call:
`set local role authenticated` (or `anon`) and puts the token's claims in
`request.jwt.claims`, which `auth.uid()` reads. The migration is applied as a
non-superuser owner (as Supabase's SQL Editor runs as `postgres`), twice, on
top of Supabase's default privileges (which grant everything to `anon` and
`authenticated`), so the test proves the migration's own revokes work rather
than relying on a bare Postgres being strict by default.
