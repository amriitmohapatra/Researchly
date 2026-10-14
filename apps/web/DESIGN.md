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

`N suggestions` heading, then the "Work through" row (All suggestions and
the three passes of the revision queue), one row of filter chips, a
Section chooser (a select: "All sections" plus each section detected, with
counts) and the hidden preference note, then two columns: your text on the
left (the thing being revised), suggestions on the right in document order.
Read-outs come last; they describe the text and are never a score.

A card reads top to bottom as: category and section, what was noticed
(bold), the flagged words (serif), the suggested revision (your call), the
explanation in everyday words (always open), "The full reasoning" (a
disclosure holding the technical account), "The lesson" (a second
disclosure, below), then "Source: …" set as a reference, and last the
quiet actions as links: "Not an issue here", then the signed-in ones. A
student scanning the list reads only the first two lines of each card.

**Sections.** The whole text is always checked and never truncated:
document-wide checks need all of it. Choosing a section only narrows what is
listed to that section's suggestions, with the document-wide ones (figure
references, abbreviations defined once; rule scope "document") kept in their
own "Whole document" group so they are never lost. The chooser starts at
"All sections" on every check and is not stored.

## Article type and the reviewer's brief (S4)

- **"Check as"** is one more control in the composer's row (Format, Check
  as, Reporting checklist, Show preferences), a select whose labels come
  from the engine's registry, default Auto. The chosen type's one-line
  summary reads under it. A change checks again whatever is on screen,
  like a stage change in Word. The choice is remembered (this browser, or
  the account when signed in). The format, the type and the checklist are
  the only things remembered.
- **One line under the results heading** says what the check ran as:
  "Checked as Research article (from the headings: Methods, Results)."
  for a guess, naming the headings it rested on so a wrong guess is easy
  to see and override; "Checked as Grant proposal." for a choice; or the
  engine's own note alone when it switched checks off. A guessed General
  says nothing.
- **The website always checks in Revise** (it is the revision studio), so
  a Draft choice saved from Word never hides document-wide checks here. If
  an engine still answers in Draft, one quiet line under the heading says
  what it held back ("Draft mode held back 3 whole-document
  suggestions.") with "Check again in Revise"; the brief and the map
  offer the same switch.
- **The brief is a second view of the same check**, chosen from a quiet
  tab strip (Suggestions | Reviewer's brief) above the results; it reads
  as a document at the reading measure, with hairline dividers and no
  boxes: for each of the five questions, the letter and question as a
  heading, the verdict in bold, the points as a list, and the writer's own
  sentences quoted in the serif as evidence. After each question a small
  italic word says what its answer rests on: detected, not detected, not
  assessed (the check was off) or not applicable (that part is not
  there); nothing for question A. The same ink for every status. Then
  "Most frequent checks" in words ("3 times", "once"), the engine's
  disclaimer (the brief does not establish whether the science is sound)
  as the closing line, and the source set like a card's. Nothing in it is
  a score: no meters, no numbers but a rule's tally, no colour by verdict
  or status. Question A is the writer's and is shown as the engine gives it.
  In Draft the tab says the brief needs Revise, with a switch where the
  surface has one (Word). Nothing of the brief is stored.

## Narrative map (S4)

- **The map is the third view of the same check** (Suggestions |
  Reviewer's brief | Narrative map), asked for with the brief and shown at
  the reading measure with the brief's dividers. It opens with the engine's
  one-line note, then one strip per section: the section's name, how many
  of its expected moves are present ("2 of 5 moves present"), and the moves
  in order as small hairline cells. A move's status is shown by shape and
  word, never by colour: a filled dot for present, a hollow dot in a dashed
  cell with the word "missing", a half dot with the words "out of order".
  The row wraps on a phone and is a vertical list in the Word pane.
- **Under each strip** the missing and out-of-order moves open to their
  question (bold), the lesson in everyday words, a frame to fill in (serif,
  in a dashed box, captioned "A frame to fill in; the words are yours": a
  template, never a sentence written for the author) and the source set
  like a card's. A present move keeps the writer's own sentence, quoted in
  the serif, behind "Show the sentence" (a native disclosure, closed).
- **Then** "Argument: missing links" (section, message, source) and
  "Hedging across the document": a table with one row per section, hedges
  and boosters per 100 words and the reading word, every value in text; a
  trajectory to notice, not a score. No meters, no bars, no colour by
  verdict. Headings with no expected moves are named in one line. In Draft
  the tab says the map needs Revise, with a switch in Word; an engine
  without a map is said in one line. On paper the map follows the brief on
  its own page, the strip as text rows and every sentence open.

## Lessons (S4)

- **"The lesson"** is a native disclosure on every card whose suggestion
  names a Learn card, closed, under "The full reasoning" and set like it:
  the card's title (bold), the lesson in everyday words, an invented
  before-and-after pair quoted in the serif and labelled "Before" and
  "After", "A habit to keep:" and the card's source. "All lessons" opens
  the Learn page in a new tab; nothing navigates away from the results.
  The cards ship with the page, so opening one sends nothing. The narrative
  map's missing and out-of-order moves and its missing links carry the same
  disclosure when they name a lesson; on paper lessons are left out.
- A missing link's sentences sit behind "Show the sentence" (closed),
  quoted in the serif like a move's; on paper they are open.

- **The lessons pages** (`/learn`, `/learn/[id]`, server-rendered, no
  client script) are a reading-measure document: group headings with
  hairline rows of title link and summary. On a lesson page, Before is
  quoted in the serif with a dashed rule and After with a solid accent
  rule (told apart by label and line style, never colour), then "Check
  your own draft", the source set like a card's, "All lessons" and
  previous/next. "Lessons" is a quiet text link in the header.

## Progress (S4, opt-in)

- Off by default: "Keep my progress" in Settings, with "Delete my
  progress" behind a confirmation; "Delete my data" removes progress too.
  Only rule ids and counts are kept, never text.
- `/progress`: one row per rule, a 132×36 sparkline in the accent with a
  hairline zero baseline and a ringed end dot, each line on its own scale
  from zero. The first and latest values are written out with a bold
  direction word (fewer, about the same, more), a link to the rule's
  lesson, native tooltips, and a closed "Every value, as a table". The
  number of recorded checks is shown as context. Never a score, a grade
  or a flag total. Off and empty states link to Settings. In the account
  menu.

## Labelling flags (S4, `/label`)

- A closed "How to label" disclosure, the section select, a serif
  textarea, Check (primary) and Next paragraph, then compact cards with
  Useful / Wrong / Unsure toggle buttons (`aria-pressed`; the chosen one is
  the accent for every verdict, never coloured by verdict), the running
  count, Export (`researchly-labels.json`: rule ids and verdicts, no text)
  and "Start over…" behind a confirmation. Labels stay in this browser. In
  the account menu.

## Reporting checklists (S4)

- **"Reporting checklist"** sits beside "Check as": None (the default),
  Auto, then each guideline by its registry label (STROBE, CONSORT,
  PRISMA, EPIFORGE), its design read under the control. A change checks
  again whatever is on screen. Remembered in this browser only.
- With None chosen and the text's words pointing to a guideline, one quiet
  line under the heading offers it ("This reads like an epidemic forecast.
  Check it against EPIFORGE?") with a link-style button that chooses it,
  checks again and opens the Checklist tab.
- **The Checklist tab** (a fourth tab, only when a checklist ran) reads as
  a document at the reading measure with the brief's dividers: the label
  and design; "Selected themes of PRISMA 2020 — not a full compliance
  check." (the engine's edition); the tally in words, semibold with
  tabular figures ("4 of 16 with possible evidence · 2 partly there ·
  confirmed by you: 1", then "not applicable (your call): N" when there
  are any); the engine's note; then every item in the guideline's order:
  its topic (a heading), the guideline's own item numbers in small grey
  type ("PRISMA 2020 item 6", "items 13a and 13b", or "Good practice, not
  a numbered item"), its question, and the status in italic words.
- **Cautious statuses (Codex review N1).** A matching sentence is possible
  evidence, never proof, so nothing is ever "reported" and nothing is a
  score. "Found — please confirm": the writer's sentence quoted in the
  serif, with "Possible evidence:" for screen readers. "Partly there": a
  compound question part by part, each "Found:" (semibold, its sentence
  quoted under it) or "Needs your check:" (italic), then the reason in
  everyday words. "Needs your check": the reason and where readers look; a
  prompt, never a verdict. Under any of them, quietly in small grey type:
  a sentence the engine did not count, in its own words ("A sentence
  mentions this but says this is not reported: “…”", the sentence in the
  serif), and a section the document lacks ("No Methods section was found
  to look in.", replacing "readers look in").
- **The writer's calls.** Two link-style toggle buttons under each item,
  wrapping, never a scrollbar: "Confirmed by me" (only where there is
  possible evidence) and "Not applicable" (every item). `aria-pressed`,
  described by the topic; the label never changes, a pressed one gains a
  tick and weight (never colour alone). Pressing one releases the other.
  The status then reads "Confirmed by you" (the evidence stays, so a
  confirmation is inspectable) or "Not applicable (your call)" (evidence
  and reason hidden). A polite live region says what changed ("Setting:
  confirmed by you.", "… confirmation undone."). The calls last for this
  check, are never stored or sent, and are gone with the next check. Then
  the source and "This checks reporting only, never the science." No
  colour by status, no meters. Four tabs wrap to two lines on a phone,
  never a scrollbar.
- **Words in one place.** Every status, tally, item-number, part,
  set-aside and absent-section line comes from `lib/checklists.ts`, and the
  item detail and the two toggles from `components/ChecklistParts.tsx`, so
  the website, Word and the printed report say the same thing.

## Dismissal (review proposal 2)

- **"Not an issue here"** on each card hides that one suggestion and its
  highlight for this check only. It is held in the results' memory: never
  stored, never sent, gone with the next check. A polite live region
  pinned to the bottom of the window says "Dismissed. Undo" and takes
  keyboard focus to Undo, which brings the card back and focuses it.
- The results header then says "N dismissed · Show"; Show brings every
  dismissed suggestion back. Counts and chips leave dismissed ones out.
- Muting a rule (signed in) removes its cards at once, then re-checks as
  before; dismissal is the light action, muting the deliberate one.

## Revision queue (review proposal 1)

- **"Work through"** sits above the filter chips: four toggle buttons
  (`aria-pressed`, 8px radius, the chosen one in the accent) reading "All
  suggestions" (the default, the list exactly as before), "Correctness
  first", "Clarity next" and "Whole-document review", each with its number
  of findings as a tally. A chosen pass has one help line under the row.
- **The passes follow the taxonomy.** Correctness: every Correction.
  Clarity: Improvements that judge one sentence, and Preferences when the
  writer shows them. Whole document: checks that read the whole text (rule
  scope "document") and every Convention, whose help line says conventions
  are not errors. Every suggestion is in exactly one pass; the passes walk
  what the Section chooser shows (the section and its whole-document
  checks), whatever the category chip says, so the chips step aside while a
  pass is chosen.
- **A pass is a queue** in the suggestions column: the pass's title, a
  bordered row with "Issue 3 of 9 in this pass" (a polite live region that
  also reads the message to a screen reader) and Previous issue / Next
  issue, then for a finding repeated in the text (the same check with the
  same message) a dashed row "Found 14 times in your text." with Previous
  / "Occurrence 2 of 14" / Next, then the current suggestion's ordinary
  card, then "Every issue in this pass" (a closed disclosure listing each
  issue with its tally in words: once, twice, 14 times). At an end the
  button stays focusable (`aria-disabled`), so the keyboard never loses its
  place; nothing wraps. The last issue says so and offers "Go on to" the
  next pass with findings; the whole-document pass then points to the
  reviewer's brief and the narrative map.
- **The text column highlights only the pass's findings**, the current one
  marked as active and scrolled into view inside the column (never the
  page, so Next stays under the pointer). Clicking a highlight moves the
  queue to it.
- **The place is anchored to the suggestion**, so dismissing a card shows
  the next occurrence (or the next issue) and Undo returns to it; a muted
  rule's issue gives way to the one after it; a re-check keeps the pass and
  the place. Held in memory only, like the view tabs; never stored.
- No score, no progress bar, no "done" percentage: the position line is the
  only count.

## Long checks (review proposal 8)

- **While a check runs** a quiet info-blue line under the composer shows a
  spinner, "Checking your text…" and "Time so far: 12 s" (outside any live
  region, so it is never read out every second). After 8 seconds it says
  "Still checking your text. A long document can take a minute or two;
  your previous results stay below until it finishes.", and that sentence
  alone goes to a polite live region, once.
- **The previous results stay** on screen (dimmed, as before) with a line
  under the heading, set in bold with a dashed rule beside it: "These are
  the results of your previous check. A new check is running; …". The same
  line, with its reason, stays after a cancel ("The new check was
  cancelled.") or a failure ("The new check did not finish."), so an older
  answer is never taken for the new one.
- **Cancel** (beside Check, the only Cancel) aborts the request and returns
  the screen to exactly what it showed, with a quiet note "Check
  cancelled." and "Check again", which runs the same check again. "Try
  again" after a failure does the same. A new file cancelled before any
  result returns to the editor, as before.
- **Sequenced requests**: every check carries a number; the reply of a
  cancelled or superseded check is dropped even if the network delivers
  it. A changed type or checklist during a check supersedes it; pressing
  Check again while one runs does nothing (the button says "Checking…").
- In the Word pane the same line and notes appear under the Check panel;
  "Check again" there reads the document afresh.

## Demo manuscript

- While the editor is empty, a quiet row under it offers "Try the demo
  manuscript": a short invented paper with planted slips, served by this
  site, loaded into the editor as Markdown (the remembered format is left
  alone). Nothing is checked until Check. The same row links the Word and
  Overleaf versions for download. The example-draft button in the key stays.

## Word prediction (2026-10-14, CLAUDE.md #1)

- **A quiet strip under the editor**, its height held so the text never
  jumps: after a pause in typing (250 ms), up to three candidates as small
  bordered buttons in the serif (they are the writer's words to be), the
  first with a slightly stronger border, then "Tab to accept · Esc to
  dismiss" in the muted ink. A word, the end of the word being typed, or a
  fixed term of at most three words; never more.
- **Never inserted by itself.** Tab takes the first candidate, a click takes
  any; only into the very text and caret they were offered for. Esc, a
  moved caret, leaving the editor or more typing drop the offer. With
  nothing shown, Tab moves focus as it always did. The buttons are out of
  the tab order; a polite live region (always mounted) says each offer.
- **"Word prediction"** is a switch in the composer's row after "Show
  preferences" (on by default) and a panel in Settings when signed in.
  Remembered in this browser (`researchly.prediction`, on/off only) and in
  the account when signed in. Off means nothing is asked for.
- Only a window around the cursor is sent (up to 4,000 characters before it
  and the rest of its paragraph); it is never stored. A reply that answers
  older text is dropped. Nothing shows unless the engine says "ok"; after
  "too many requests" the strip stays quiet for a minute. Not on paper.

## The table cell on an X401 card (2026-10-14)

When a sentence names a row and a column of a table and quotes a number
that is not in that cell, the card carries a small quiet box under the
quoted words: where the cell is ("Table 1, row “Mortality”, column
“Treatment”"), **The table holds** and **This sentence says** side by side,
and the rounding the comparison allowed. Numbers in the serif, tabular
figures; the box itself is the page background, not a category colour. On
the website **Show the cell** outlines the cell in the text with a dashed
line (outlined, not tinted: it is evidence, not a second finding) and moves
focus there; choosing the outlined cell returns to the card; **Show in
text** drops the outline. The Word card shows the same box without the
jump.

## What was read (2026-10-14)

- One quiet line under the results heading, after the profile line:
  "Checked 4,210 words. Set aside: 2 lines of code · 1 paragraph not in
  English." in the engine's own words (singular for one). Only the word
  count when nothing was set aside; nothing from an engine without it. The
  same line in the Word pane's results. Warnings stay where they were.

## The printable report (S4)

- **"Print or save as PDF"** sits beside the results heading as a link-style
  button. It opens the browser's own print dialog; Save as PDF there is the
  PDF. Nothing is generated anywhere else and no text leaves the page.
- On paper the page is the report and nothing else: a header (title, when
  the text was checked and when it was printed, counts, sections, the mode,
  the profile line with its headings, a one-line key), then the text with
  every highlight numbered on the left and the suggestions under the same
  numbers on the right (for a multi-file upload each with its file and
  line), whole-document checks after them, then the reviewer's brief on a
  new page, the narrative map on the page after it, the reporting checklist
  on its own page when one ran, and a footer saying nothing was stored.
  The checklist on paper uses the screen's cautious statuses, with the
  edition line and the tally, and no controls; it keeps four states apart
  in words for whoever the page is handed to: "Found — please confirm"
  (not confirmed), "Confirmed by the writer", "Not applicable (the
  writer's call)" and "Needs your check" (the tally says "confirmed by the
  writer: N").
- **The context block** under the header lines, one plain line each and
  only when it applies: "This report describes the version that was
  checked, not the text now in the editor." (bold) when the editor changed
  after the check; every tier that did not contribute, by label ("Not
  available for this check: Grammar."), the expected ones included, since
  a PDF outlives the screen's banner; what Draft held back; how many
  suggestions were dismissed on screen and left out; and what was skipped
  or approximated while reading. A reader of the PDF can tell what version
  and which parts were assessed without the app.
- Light ink only: a grey tint on highlights, an underline whose style says
  the category (solid, double, dotted, dashed), bold numbers, no colour by
  verdict, no meters. A4 and Letter both fit; the two columns are a grid,
  so they flow across pages together.
- The report is mounted only while printing (the button, or the browser's
  own print command) and removed afterwards, so a long document is never
  laid out twice on screen.

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
- **Apply outcomes (S4c, review R3)**: a refusal says nothing changed.
  "Applied, but Track Changes was not restored" and "Word reported an
  error after the edit" are said plainly on the card and remove its Apply,
  so an edit is never repeated blindly. Any edit marks the paragraph's
  other cards out of date: no Apply, and the note "check the document
  again". If Word cannot load a range's fields, nothing is inserted and
  the card offers a manual edit.
- **Reporting checklist (S4c)**: a full-width select under "Check as"
  (None, Auto, STROBE, CONSORT, PRISMA, EPIFORGE), sent in Revise only,
  with its help line. A fourth tab, "Checklist", appears only when one
  was asked for, in the website's words (Codex review N1): the edition
  line and the tally, then per item its topic with the status beside it
  ("Found — please confirm", "Partly there", or "Needs your check" in
  italic; the writer's call upright), the guideline's item numbers, the
  question, and the same detail as the site (parts, the quoted sentence or
  the plain reason, a sentence not counted, an absent section). "Confirmed
  by me" and "Not applicable" (added for parity with the site) are the
  same toggles, kept in the pane's memory for this check (across tab
  switches), never stored or sent, announced politely. Everything wraps at
  320px. No colour by status, no meters. In Draft the tab offers "Switch
  to Revise", like the brief.
- **Revision queue (review proposal 1)**: the "Work through" choices sit
  under the quiet notes as a two-by-two grid; a pass replaces the cards
  with the same queue as on the site (one column), and each step selects
  the finding's words in Word, as clicking its card does.
- **Next words (2026-10-14)**: Office JS cannot show words inline, so a
  small panel under the check panel, titled "Next words" with a quiet
  "Hide" link, offers up to three words as buttons when the cursor moves
  (typing moves it). A click inserts the rest of the word at the cursor
  (the typed letters stay as typed), only if the paragraph up to the cursor
  still reads as it did; otherwise it says nothing was inserted. Track
  Changes is never touched, so with it on the insertion is tracked like
  typing. Nothing for selected words or in headings, said in one line;
  Word older than WordApi 1.3 is told the panel is not available there.
  "Word prediction" in Settings brings a hidden panel back. States: idle,
  words offered, selection, heading, unsupported, text at the cursor
  changed.
- **Sign-in** replaces the main column: email, then the emailed code. No
  dialog (Office's dialog API is not used).
- **States**: connecting to Word, outside Word, office.js missing, idle,
  reading, checking (cancellable), results, empty result ("not a score"),
  empty document, engine errors with retry, sign-in required, local engine
  not running, degraded tier (before and after a check), card selected,
  approximate match, applied (tracked or direct), apply refused, mode not
  saved to the account, section view (with and without suggestions in the
  section), cursor not readable. S4c adds: checklist needs Revise, nothing
  in the text points to a checklist, the engine has none, card out of
  date, applied without restoring Track Changes, unknown outcome.

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

S4c adds: a lesson open on a card or a move, a checklist with found,
partly-there, needs-your-check, confirmed and not-applicable items (N1:
also a sentence not counted, an absent section, an unnumbered item; on
the website, in Word and on paper), the checklist offer, a card
dismissed (with Undo) and every card dismissed, what Draft held back (an
older engine), a muted rule's cards gone before the re-check, the demo
loaded or not loadable.

Review proposals 1 and 8 add: a pass chosen (first, middle and last issue; an issue
found once and one found many times; an empty pass, also in a section),
a card dismissed inside a pass, a long check (still checking), previous
results while checking, after a cancel and after a failure, the cancelled
note with and without earlier results.

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
