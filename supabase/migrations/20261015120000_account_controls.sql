-- Researchly: account controls a user runs on their own account (PLAN #12,
-- Codex review 8 Oct; before the public beta).
--
-- Apply AFTER 20261014130000_progress_comparable.sql: Supabase dashboard ->
-- SQL Editor -> paste this whole file -> Run. Re-running is safe (both
-- functions are CREATE OR REPLACE and their grants are re-stated).
--
-- Two functions, each called by the signed-in user through PostgREST
-- (POST /rest/v1/rpc/<name> with their own token). Neither takes an
-- argument: the account they act on is always auth.uid(), never one a
-- client names.
--
--   reset_my_preferences()  puts the caller's choices back to the table's
--     defaults: muted rules cleared, preferences hidden, grammar checks,
--     spelling, Draft/Revise and the article type back to their defaults.
--     It KEEPS the dictionary (words the user collected, not a choice),
--     recorded progress and the "Keep my progress" switch (a privacy
--     opt-in with its own control and its own delete, which a reset of
--     display choices must not quietly turn off or on). Each of those has
--     its own action on the Settings page. SECURITY INVOKER: Row-Level
--     Security decides, exactly as for the user's own edits.
--
--   delete_my_account()  deletes the caller's sign-in (auth.users) and,
--     through the foreign keys' ON DELETE CASCADE, every row they own:
--     user_settings, dictionary_words, progress_events. Supabase's own
--     auth tables (identities, sessions, refresh tokens) cascade too, so
--     the account cannot be renewed afterwards. SECURITY DEFINER, because
--     a user cannot delete from auth.users themselves; it runs as this
--     file's owner (`postgres` in Supabase), touches exactly one row,
--     `where id = (select auth.uid())`, and refuses a caller without one.
--
-- Why the cascade and not explicit deletes: the public tables use FORCE ROW
-- LEVEL SECURITY with policies for `authenticated` only, so a DELETE run
-- as the owner would see none of the caller's rows and remove nothing,
-- silently. Foreign-key actions are exempt from RLS, and a table added
-- later without ON DELETE CASCADE makes the delete FAIL (foreign-key
-- violation) rather than leave rows behind. The two-user test checks that
-- every public table referencing auth.users cascades.
--
-- An access token already issued stays valid until it expires (at most an
-- hour; the engine checks tokens locally). After deletion it reaches no
-- rows: my_config() returns the defaults and any write fails its foreign
-- key. The website signs out at once.
--
-- No document text, as before: nothing here reads or stores any.

begin;

-- ---------------------------------------------------------------------------
-- reset_my_preferences(): every preference column back to its DEFAULT, so a
-- later migration's new default is followed without editing this function.
-- No row = already the defaults; nothing to do.
-- ---------------------------------------------------------------------------
create or replace function public.reset_my_preferences()
returns void
language sql
volatile
security invoker
set search_path = ''
as $$
  update public.user_settings as s
     set disabled_rules   = default,
         show_preferences = default,
         locale           = default,
         mode             = default,
         document_type    = default,
         spelling         = default,
         prediction       = default
   where s.user_id = (select auth.uid())
$$;

comment on function public.reset_my_preferences() is
  'Caller''s preferences back to defaults; keeps dictionary, progress and keep_progress. RLS applies.';

-- ---------------------------------------------------------------------------
-- delete_my_account(): the caller's auth.users row, and by cascade every row
-- they own. Returns nothing; raises 42501 for a caller with no user id.
-- ---------------------------------------------------------------------------
create or replace function public.delete_my_account()
returns void
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  uid uuid := (select auth.uid());
begin
  if uid is null then
    raise exception 'not signed in'
      using errcode = 'insufficient_privilege';
  end if;
  delete from auth.users as u where u.id = uid;
end;
$$;

comment on function public.delete_my_account() is
  'Deletes the caller''s auth.users row; their rows cascade. SECURITY DEFINER, own row only.';

-- ---------------------------------------------------------------------------
-- Privileges: signed-in users only. Supabase's default privileges grant
-- EXECUTE on new public functions to anon and authenticated (and PostgreSQL
-- to PUBLIC); revoke all of that first.
-- ---------------------------------------------------------------------------
revoke all on function public.reset_my_preferences() from public, anon, authenticated;
grant execute on function public.reset_my_preferences() to authenticated;
revoke all on function public.delete_my_account() from public, anon, authenticated;
grant execute on function public.delete_my_account() to authenticated;

commit;
