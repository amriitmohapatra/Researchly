# apps/web design contract

The contract every change to this surface is checked against. If a change
breaks a line here, change the line first, on purpose.

## Design read

A revision studio for research students (master's and PhD) reviewing their
own drafts. Calm, scholarly, a tool rather than a landing page. Native CSS,
system type stacks, no UI kit. Dials: variance 3, motion 2, density 5.

## What the page must communicate, in order

1. **What to do here**: paste a draft, press Check. One primary action.
2. **How to read the feedback**: four kinds of suggestion, and that a
   Convention is never an error. Taught before the first check by a key
   with live specimens, then by the filter chips.
3. **Why each suggestion exists**: the message, the flagged words, an
   explanation in everyday words and a visible source on every card. The
   technical reasoning is one click away; the rule's code and the tier that
   produced it are never shown (they are data attributes for actions and
   tests).
4. **That nothing is rewritten and nothing is kept**: revisions are labelled
   "your call"; the privacy line sits next to the Check button.

## Hierarchy (results)

`N suggestions` heading, then one row of filter chips, a Section chooser
(a select: "All sections" plus each section detected, with counts) and the
hidden preference note, then two columns: your text on the left (the thing
being revised), suggestions on the right in document order. Read-outs come
last; they describe the text and are never a score.

A card reads top to bottom as: category and section, what was noticed
(bold), the flagged words (serif), the suggested revision (your call), the
explanation in everyday words (always open), "The full reasoning" (a
disclosure holding the technical account), then "Source: …" set as a
reference. A student scanning the list reads only the first two lines of
each card.

**Sections.** The whole text is always checked and never truncated:
document-wide checks need all of it. Choosing a section only narrows what is
listed to that section's suggestions, with the document-wide ones (figure
references, abbreviations defined once; rule scope "document") kept in their
own "Whole document" group so they are never lost. The chooser starts at
"All sections" on every check and is not stored.

## Article type and the reviewer's brief (S4)

- **"Check as"** is one more control in the composer's row (Format, Check
  as, Show preferences), a select whose labels come from the engine's
  registry, default Auto. The chosen type's one-line summary reads under
  it. A change checks again whatever is on screen, like a stage change in
  Word. The choice is remembered (this browser, or the account when signed
  in); it is the only thing remembered.
- **One line under the results heading** says what the check ran as:
  "Checked as Research article (from the headings)." for a guess, "Checked
  as Grant proposal." for a choice, or the engine's own note when it
  switched checks off. A guessed General says nothing.
- **The brief is a second view of the same check**, chosen from a quiet
  tab strip (Suggestions | Reviewer's brief) above the results; it reads
  as a document at the reading measure, with hairline dividers and no
  boxes: for each of the five questions, the letter and question as a
  heading, the verdict in bold, the points as a list, and the writer's own
  sentences quoted in the serif as evidence. Then "Most frequent checks"
  in words ("3 times", "once") and the source set like a card's. Nothing
  in it is a score: no meters, no numbers but a rule's tally, no colour by
  verdict. Question A is the writer's and is shown as the engine gives it.
  In Draft the tab says the brief needs Revise, with a switch where the
  surface has one (Word). Nothing of the brief is stored.

## Type: who is speaking

- **Serif** (Iowan Old Style / Charter / Georgia stack) is for writing: the
  student's draft, quoted words, revisions, and the cited sources.
- **Sans** (system UI stack) is the coach: headings, messages, controls.
- Body 16px minimum on every viewport; explanations at 16px with 1.6 line
  height and a 62ch measure. No font files, no font CDNs.

## Colour

- Neutral paper (`#f4f5f3`), white surfaces, one navy accent (`#26344d`)
  for the primary action. Links are an underlined blue (`--link`). Not
  cream.
- The four categories use the Okabe-Ito colour-blind-safe palette and are
  always encoded four ways: colour, label, icon shape, underline style
  (Correction solid, Improvement double, Convention dotted, Preference
  dashed). Conventions are green-teal, never red. Health notices are blue,
  never red.
- AA contrast in light and dark, checked by axe in the e2e suite.

## Shape and density

- One radius, 8px, for panels, cards, inputs, buttons and notices. Pills
  only for filter chips, category badges and the switch.
- Cards are hairline plus a 3px category rule; no drop shadows on cards.
  The account panel is the one overlay with a small lift, so it reads as
  above the page; dialogs use the native backdrop instead.
- Spacing steps: 4, 8, 12, 16, 24, 32, 48.

## Accounts and files (S2, only in a build with Supabase configured)

Without the two Supabase variables the page is exactly the S1 page: no
sign-in, no upload, no settings route.

- **Sign-in is offered, never demanded.** A quiet "Sign in" in the header.
  It is asked for only where it is needed: checking a file, or pasting more
  than the anonymous limit. The prompt replaces the results; the text stays.
- **Account control**: the email in a bordered button, a disclosure (not an
  ARIA menu) with "Signed in as", Settings and dictionary, Sign out.
- **Upload is the second way in.** One quiet row under the editor ("Check a
  file instead") plus drop onto the editor. Check stays the only primary
  button. Signed out, the row says it needs an account.
- **A checked file replaces the composer** with a file panel: name, how it
  was read, what was skipped, and that the text is read-only (fixes are made
  in Word or Overleaf). "Back to the text editor" restores the pasted text.
  The results below are the same results view; for a multi-file project each
  card adds a mono "file, line N" line under its head.
- **Card actions (signed in)** sit after the source, as quiet links: "Mute
  this rule", and on spelling cards "Add “word” to dictionary". Each confirms in
  a quiet notice with a link to Settings, then re-checks.
- **Settings** is one column of panels: Muted rules (name, code, one-line
  why, Unmute), How suggestions are shown (switch, spelling locale),
  Your dictionary (add with inline limits, tiles with Remove), Delete. Every
  change saves at once and is announced; a failed save moves the control
  back and says why. Delete asks first, with focus on "Keep them".
- **Dialogs** are native `<dialog>` (focus contained, Escape closes, focus
  returns to the opener).

## Word taskpane (`/word`, S3)

The same coach inside Word's sidebar, which is 320 to 400px wide. One
column, the site's tokens, cards and notices; nothing new to learn.

- **Order**: header (brand, Sign in or the email), then one panel with the
  Draft / Revise choice (a two-part segmented control, 8px radius, under it
  exactly "Draft: check what you've written so far. Revise: check the
  finished manuscript."), **Check document** (the only primary button) beside
  the secondary **Check this section**, its one-line help, and the privacy
  line for the chosen engine. "Check this section" sends the whole document
  and then lists only the section the cursor is in (from its heading to the
  next), with document-wide suggestions under "Whole document" and a note
  saying how many are elsewhere, with "Show the whole document". Then health, errors, results,
  and a closed **Settings** disclosure (engine, show preferences, account).
  The footer holds "Report a problem" (mailto, never with document text).
- **Results**: "N suggestions", then quiet grey notes: what Draft held back
  (with "Switch to Revise"), hidden preferences (with "Show them"), and what
  was not checked (footnotes, headers and the rest). Cards in document order.
- **Cards** read as on the site; clicking one selects its words in Word.
  Under the source: "Show in document", and "Apply in document" only when
  the engine proposed a revision; account actions last. Applying is one span at a time, as a
  tracked change where Word supports it; the card then says how it was
  applied. A refusal (the document changed) is said on the card, in words.
- **Sign-in** replaces the main column: email, then the emailed code. No
  dialog (Office's dialog API is not used).
- **States**: connecting to Word, outside Word, office.js missing, idle,
  reading, checking (cancellable), results, empty result ("not a score"),
  empty document, engine errors with retry, sign-in required, local engine
  not running, degraded tier (before and after a check), card selected,
  approximate match, applied (tracked or direct), apply refused, mode not
  saved to the account, section view (with and without suggestions in the
  section), cursor not readable.

## States (all reachable, all covered by e2e)

Idle (key + example), invalid input, loading (skeleton, cancellable),
results, empty result ("not a score"), stale results after an edit,
degraded engine tier (calm banner), every error kind with retry where it
helps.

S2 adds: session loading (space held in the header), signed out, sign-in
sent, sign-in error, expired or foreign link, sign-in required (prompt in
place of results), signed out after a failed renewal, sign-in unavailable
(retry), file reading, file refused in the browser (type, size, empty),
file refused by the engine (unsupported, unreadable, too large), file
warnings, card action saved or failed; settings signed out, loading, load
failed, nothing muted, empty dictionary, saved, save failed, delete
confirm.

## Responsive

- 960px and up: composer beside the key; results in two columns with the
  text column sticky.
- Below 960px: one column. The key shows only before the first check, so
  results come straight after the composer. Phones are for reading reports:
  no horizontal scroll at 360px, 16px text, 32px minimum targets.

## Reject

Score, grade or progress bars of any kind; red for anything that is not a
likely error; apply-all or auto-fix buttons (the taskpane's Apply is per
card, read first, tracked where Word can); em dashes in UI copy;
uppercase tracked eyebrows; decorative gradients, glows or shadows;
third-party scripts, fonts or analytics; any control without a real outcome.
