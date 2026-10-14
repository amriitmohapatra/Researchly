-- Researchly: make recorded checks comparable (Codex review N2, 2026-10-14).
--
-- Apply AFTER 20261014120000_spelling_prediction.sql: Supabase dashboard ->
-- SQL Editor -> paste this whole file -> Run. Re-running is safe.
--
-- A progress row said how often each rule fired, but not whether the rule
-- ran: a rule the writer muted, a preference they hid, a check in Draft
-- or a grammar tier that was down all looked like "fewer" in the chart.
-- Each new row now also carries, as metadata only:
--   * assessed — the rule ids the check could show (the engine's
--     `assessed_rules`); a rule outside it was not assessed, not zero;
--   * mode     — draft or revise;
--   * ruleset  — the engine version and a fingerprint of its rules, so a
--     chart compares only checks made with the same rules.
-- Rule ids, a word and a version string: still no document text, no file
-- names, no fingerprints of text. Older rows keep NULLs and are read as
-- "eligibility unknown" (only their non-zero counts are shown).

begin;

alter table public.progress_events
  add column if not exists assessed text[];

alter table public.progress_events
  add column if not exists mode text;

alter table public.progress_events
  add column if not exists ruleset text;

do $$
begin
  if not exists (
    select 1 from pg_catalog.pg_constraint
    where conname = 'progress_events_assessed_shape'
      and conrelid = 'public.progress_events'::regclass
  ) then
    alter table public.progress_events
      add constraint progress_events_assessed_shape
      check (assessed is null
             or (pg_catalog.cardinality(assessed) <= 400
                 and public.researchly_rule_ids_valid(assessed)));
  end if;
  if not exists (
    select 1 from pg_catalog.pg_constraint
    where conname = 'progress_events_mode_known'
      and conrelid = 'public.progress_events'::regclass
  ) then
    alter table public.progress_events
      add constraint progress_events_mode_known
      check (mode is null or mode in ('draft', 'revise'));
  end if;
  if not exists (
    select 1 from pg_catalog.pg_constraint
    where conname = 'progress_events_ruleset_shape'
      and conrelid = 'public.progress_events'::regclass
  ) then
    alter table public.progress_events
      add constraint progress_events_ruleset_shape
      check (ruleset is null or ruleset ~ '^[0-9A-Za-z.+_-]{1,40}$');
  end if;
end
$$;

comment on column public.progress_events.assessed is
  'Rule ids the check could show (engine assessed_rules); NULL on rows recorded before 2026-10-14. Never text.';
comment on column public.progress_events.mode is
  'draft or revise; NULL on older rows.';
comment on column public.progress_events.ruleset is
  'Engine version + rule-set fingerprint; checks are compared only within one. NULL on older rows.';

commit;
