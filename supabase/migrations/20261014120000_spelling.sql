-- Researchly: the English spelling a user keeps to, saved with the account
-- so the web app and the Word add-in share it (PLAN task #15).
--
-- Apply AFTER 20261008140000_s4_progress.sql: Supabase dashboard -> SQL
-- Editor -> paste this whole file -> Run. Re-running is safe.
--
-- Adds one column holding one of seven short codes (researchly/config.py
-- SPELLINGS). "auto" follows the document's own majority and flags only
-- mixtures (W210); any other value also flags every spelling of another
-- dialect (W213). "in" is Indian English, spelled as British. No document
-- text, as before.

begin;

alter table public.user_settings
  add column if not exists spelling text not null default 'auto';

do $$
begin
  if not exists (
    select 1 from pg_catalog.pg_constraint
    where conname = 'user_settings_spelling_known'
      and conrelid = 'public.user_settings'::regclass
  ) then
    alter table public.user_settings
      add constraint user_settings_spelling_known
      check (spelling in ('auto', 'us', 'uk', 'uk-oxford', 'ca', 'au', 'in'));
  end if;
end
$$;

comment on column public.user_settings.spelling is
  'English spelling to keep to (researchly/config.py SPELLINGS); auto follows the document.';

-- my_config() gains "spelling"; otherwise as in the S4 document-type migration.
create or replace function public.my_config()
returns jsonb
language sql
stable
security invoker
set search_path = ''
as $$
  select pg_catalog.jsonb_build_object(
    'disabled_rules',   coalesce(pg_catalog.to_jsonb(s.disabled_rules), '[]'::jsonb),
    'show_preferences', coalesce(s.show_preferences, false),
    'locale',           coalesce(s.locale, 'en-US'),
    'mode',             coalesce(s.mode, 'revise'),
    'document_type',    coalesce(s.document_type, 'auto'),
    'spelling',         coalesce(s.spelling, 'auto'),
    'dictionary',       coalesce(
      (select pg_catalog.jsonb_agg(w.word order by w.word)
       from (select d.word
             from public.dictionary_words d
             where d.user_id = (select auth.uid())
             order by d.word
             limit 5000) as w),
      '[]'::jsonb)
  )
  from (select 1) as one
  left join public.user_settings s
    on s.user_id = (select auth.uid())
$$;

revoke all on function public.my_config() from public, anon, authenticated;
grant execute on function public.my_config() to authenticated;

commit;
