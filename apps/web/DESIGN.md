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
  as, Reporting checklist, Show preferences, Underlines while writing), a select whose labels come
  from the engine's registry, default Auto. The chosen type's one-line
  summary reads under it. A change checks again whatever is on screen,
  like a stage change in Word. The choice is remembered (this browser, or
  the account when signed in). The format, the type, the checklist and the
  "Underlines while writing" switch are the only things remembered.
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
  cell with the words "not detected" (the map reads wording, so it never says
  "missing"; Codex review N5), a half dot with the words "out of order".
  The row wraps on a phone and is a vertical list in the Word pane.
- **Under each strip** the not-detected and out-of-order moves open to their
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

- **The document type decides what is expected** (Codex review N5,
  2026-10-14): a commentary or policy brief is not asked for a research gap
  and, where no limitations section is expected, not for a limitations
  move; a response to reviewers is described, not judged (what was found is
  listed, nothing is "not detected", and the note says so). A section that
  comes back after another (a second chapter's Introduction) gets its own
  strip, "Introduction (2)". A move taken from a section's first sentence
  only because it names no other move says so under its sentence, quietly:
  an assumption, never proof. Two moves in one sentence are in order, and
  every out-of-order move explains itself.

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
  progress" behind a confirmation; "Delete my account" removes progress too.
  Only rule ids and counts are kept, never text.
- `/progress`: one row per rule, a 132×36 sparkline in the accent with a
  hairline zero baseline and a ringed end dot, each line on its own scale
  from zero. The first and latest values are written out with a bold
  direction word (fewer, about the same, more), a link to the rule's
  lesson, native tooltips, and a closed "Every value, as a table". The
  number of recorded checks is shown as context. Never a score, a grade
  or a flag total. Off and empty states link to Settings. In the account
  menu.
- Like with like (Codex review N2, 2026-10-14): each check also records
  which checks ran (rule ids), Draft or Revise and the checker's version.
  A rule that did not run in a check (muted, a hidden preference, held back
  by Draft, off for the article type, its tier down) is a **gap**: the line
  breaks and a small hollow mark sits on the baseline, "not assessed" in
  the tooltip and the table; never a zero. Only checks of one article type
  and one checker version are compared: the latest type by default, a
  "Compare checks of" select when there are several; earlier versions are
  counted in a quiet note, not plotted. The help line says the dates
  compared and calls the view how often flags appeared, not a score. A
  recheck of unchanged text (a control changed) is not recorded again: an
  in-memory key of the text, never stored or sent.

## Labelling flags (S4, `/label`)

- A closed "How to label" disclosure, the section select, a serif
  textarea, Check (primary) and Next paragraph, then compact cards with
  Useful / Wrong / Unsure toggle buttons (`aria-pressed`; the chosen one is
  the accent for every verdict, never coloured by verdict), the running
  count, Export (`researchly-labels.json`: rule ids and verdicts, no text)
  and "Start over…" behind a confirmation. Labels stay in this browser. In
  the account menu.
- Attempts (Codex review N3, 2026-10-14): each successful check of a
  paragraph is an attempt (a random id, never derived from the text); a
  label names its attempt and its flag's position. A changed verdict
  replaces; a recheck of the paragraph replaces its earlier labels, which
  a quiet note under the buttons says beforehand ("This paragraph already
  has 2 labels from an earlier check…"); a failed or cancelled check
  changes nothing. After a reload the cards are gone with the text, so the
  page asks for a recheck rather than showing labels it cannot place.

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
  and design; "Selected themes of PRISMA 2020, not a full compliance
  check." (the engine's edition); the tally in words, semibold with
  tabular figures ("4 of 16 with possible evidence · 2 partly there ·
  confirmed by you: 1", then "not applicable (your call): N" when there
  are any); the engine's note; then every item in the guideline's order:
  its topic (a heading), the guideline's own item numbers in small grey
  type ("PRISMA 2020 item 6", "items 13a and 13b", or "Good practice, not
  a numbered item"), its question, and the status in italic words.
- **Cautious statuses (Codex review N1).** A matching sentence is possible
  evidence, never proof, so nothing is ever "reported" and nothing is a
  score. "Found: please confirm": the writer's sentence quoted in the
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
- Muting a rule (signed in) removes its cards at once, before the account
  answers (a failed save brings them back and says why); dismissal is the
  light action, muting the deliberate one. Pasted text is then checked
  again. An uploaded file is **not** sent again: its results are filtered in
  the page, and the next check of the file applies the account's mutes in
  the engine as always.
- The mute's quiet notice reads "Muted “Rule name”. It stays muted wherever
  you sign in. Undo · Change this in Settings", and keyboard focus moves to
  Undo, as after a dismissal. Undo unmutes in the account; on a file's
  results its cards come back at once with no request to the engine, and
  pasted text is checked again. The notice then reads "Unmuted “Rule
  name”." and keeps focus.

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
  in words for whoever the page is handed to: "Found: please confirm"
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
  the category (solid, dashed, dotted, wavy), bold numbers, no colour by
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
- Typography in every string a writer reads: a curly apostrophe (’) and the
  ellipsis character (…), never ' or ... (tests/unit/typography.test.ts).
- The card's "The lesson" and the lesson page share class names at two
  scales: the card's are scoped to the open disclosure, the page's to
  `.lesson-page`, so neither leaks into the other.

## Colour

- Neutral paper (`#f4f5f3`), white surfaces, one navy accent (`#26344d`)
  for the primary action. Links are an underlined blue (`--link`). Not
  cream.
- The four categories use the Okabe-Ito colour-blind-safe palette and are
  always encoded four ways: colour, label, icon shape, underline style
  (Correction solid, Improvement dashed, Convention dotted, Preference
  wavy; S4d R2 made these the patterns every surface draws). Conventions
  are green-teal, never red. Health notices are blue, never red.
- Category colours come **only** from the design tokens
  (`packages/design-tokens`, next section): `app/layout.tsx` loads the
  generated `tokens.css` before `globals.css`, and `globals.css` reads
  `--rl-*` variables. It writes no category colour of its own.
- AA contrast in light and dark, checked by axe in the e2e suite.

## Design tokens (S4d R2)

One file, `packages/design-tokens/tokens.json`, is the design language of
every surface: this site, the Word pane (`/word`) and the desktop clients.
`node packages/design-tokens/scripts/build.mjs` generates
`dist/tokens.css` (custom properties: light by default, dark under
`prefers-color-scheme` unless `data-theme="light"`, and always under
`data-theme="dark"`), `dist/tokens.ts` (typed map with icon names, Word
annotation colours and the six states), `dist/ResearchlyTokens.swift` and
`dist/ResearchlyTokens.cs`. Never edit `dist/` by hand: `--check` (in this
app's lint and in CI) fails when it is stale.

Three tiers:

1. **Primitive hues**: Researchly's own ramps, taken from this site's
   palette (paper, slate, night, navy, azure, vermillion, blue, green,
   orchid, amber). No mode; only the tiers below use them.
2. **Semantic roles**: `surface.page|raised|sunken`, `text.primary|
   secondary|on-accent`, `line.hairline|strong`, `accent`, and the roles
   `correction`, `improvement`, `convention`, `preference`, `focus`,
   `warning`, `offline`, each with `strong` (lines, rails, marks),
   `subtle` (tints) and `text`. CSS: `--rl-correction-strong`.
3. **Component tokens**: `underline.<category>` (colour, pattern,
   thickness), `highlight.<category>`, `card.rail.<category>`,
   `badge.<category>.text|background`, `widget.surface|border|mark|ring|
   warning|offline` and `widget.badge.background|text`. CSS:
   `--rl-underline-preference-style`, `--rl-card-rail-convention`.

Every semantic and component colour has a light **and** a dark value. The
generator refuses (and the package's tests fail) when one is missing, when
text falls below 4.5:1 against the page, a card, a sunken panel or its own
tint, or when an underline, rail or mark falls below 3:1 against the page
or a card, in either mode. That floor moved one colour: the Preference line
is `#c06c9b` (3.28:1 on the paper) where it was `#cc79a7` (2.80:1).

Each category names its icon (ours: circle-cross, arrow-up, open-book,
sliders, as `CategoryIcon` draws them; an SF Symbol and a Segoe glyph for the
native clients), its underline pattern (solid, dashed, dotted,
wavy-dotted; CSS draws the last as wavy) and its Word annotation colour
scheme (Correction Red, Improvement Blue, Convention Green, Preference
Lavender). The page's neutrals (`--bg`, `--ink`, …) keep their names here
and match the tokens' surface and text roles (a unit test holds them
equal).

## The six states (S4d R2)

Every surface that checks while the writer writes shows one of six states,
with one look each (`lib/check-state.ts`, `components/StatusMark.tsx`;
labels from the tokens, so the website, Word and the desktop clients say
the same words):

| State | Meaning | Look | Words |
|---|---|---|---|
| `hidden` | Not eligible here, or paused | Nothing drawn (a screen reader hears "Paused") | Paused |
| `checking` | A check is in flight for the latest revision | A ring in `widget.ring`; turning, static under reduced motion | Checking… |
| `issues` | Visible suggestions | A count badge (`widget.badge`) | 3 suggestions / 1 suggestion |
| `clear` | Checked, nothing to show | A plain mark with a tick (`widget.mark`) | Nothing to suggest |
| `partial` | Checked, but a tier was down | The mark with a small warning sign (`widget.warning`); the reason in the label | Checked in part |
| `offline` | The engine can’t be reached or refused | The mark crossed out (`widget.offline`); the next step in the label | Can’t check right now |

Transitions (a pure reducer, unit-tested): an edit goes to `checking`; a
reply for the latest revision goes to `issues`, `clear` or `partial` (a
reply for an older revision is dropped); a failure goes to `offline` and
retries after 2, 4, 8, 16 and 30 s, then every 30 s, staying `offline`
while a retry is in flight; any success leaves `offline`; leaving the
field or pausing goes to `hidden`. The Word pane shows them in its header
(R4, below); the website shows them beside the editor's privacy line (R5,
below).

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
  a quiet notice with a link to Settings, then re-checks; muting on an
  uploaded file filters in the page instead (Dismissal, above).
- **Upload in local development** (`NEXT_PUBLIC_RESEARCHLY_DEV_UPLOAD=1`,
  `next dev` without Supabase only): the same row and drop zone, with the
  help line saying it is a development upload with no account. A
  production build never shows it.
- **Settings** is one column of panels: Muted rules (name, code, one-line
  why, Unmute), How suggestions are shown (switch, spelling locale),
  Your dictionary (add with inline limits, tiles with Remove, "Clear my
  dictionary…"), Your progress, Your account. Every change saves at once
  and is announced; a failed save moves the control back and says why.
  Every destructive action asks first, with focus on the safe choice
  ("Keep them", "Keep my account").
- **Your account** (PLAN #12) holds two actions, each with a sentence saying
  exactly what it does, never one combined "Delete my data":
  - **Reset preferences…** unmutes every rule, hides preferences and puts
    grammar checks, spelling, Draft or Revise and the article type back to
    their defaults; the dictionary, recorded progress and the "Keep my
    progress" switch stay (the dialog says so). Words have their own "Clear
    my dictionary…", progress its own "Delete my progress…": three scoped
    actions instead of the old "Delete my data", so a writer never loses
    more than they meant to.
  - **Delete my account…** deletes the sign-in and everything kept with it,
    says it can't be undone and signs this browser out. Two steps: the
    dialog, then typing "delete" (any case). The confirm button is never
    disabled: pressed early it says what to type and focuses the field. A
    failure keeps the dialog open and says nothing was deleted. Done, the
    page shows "Your account was deleted" (heading focused) with "Back to
    the checker".
- **Dialogs** are native `<dialog>` (focus contained, Escape closes, focus
  returns to the opener).

## The installable app (S6, P5)

The website installs as an app window: "Install Researchly" in Chrome or
Edge's menu on a computer, "Add to Home Screen" on a phone. Nothing about
the page changes inside the window; there is no install banner or prompt
of our own (the browser offers it, quietly).

- **Icons** are the brand mark (`app/icon.svg`), drawn by
  `scripts/make-pwa-icons.mjs`: the rounded navy square at 192 and 512
  ("any"); a full-bleed navy square with the letter inside the 80% safe
  circle for maskable icons (192, 512); a full-bleed 180px Apple touch icon
  that iOS rounds itself. No other artwork.
- **Colours** from the tokens: the title bar and the splash screen are the
  paper page colour (`surface.page`); in dark mode the theme-color meta
  tags give the dark page colour, so the title bar always matches the page.
- **The offline page** (`public/offline.html`, shown by the service worker
  when a page cannot be reached): the header's brand line, one heading
  ("Researchly needs a connection to check your writing"), a sentence on
  why, "Try again" as the one primary button (a link to the checker, 44px
  high), then two quiet lines: nothing written is kept on this device, and
  local mode (the command-line tool, the VS Code extension) checks without a
  network. The reading measure, the page's neutrals and accent, light and
  dark; no script, no inline style.
- **The service worker keeps no text.** It stores only this site's code
  (`/_next/static`), icons and the offline page. Pages are network only;
  the engine, Supabase and every POST are never touched. Never registered by
  `next dev` or on `/word`.

## Word taskpane (`/word`, S3)

The same coach inside Word's sidebar, which is 320 to 400px wide. One
column, the site's tokens, cards and notices; nothing new to learn.

- **Order**: header in two rows (row 1: brand, then the status mark (S4d R4) at the right, with the
  right 40px kept clear because Word on the Mac draws its own "i" button over the pane's top-right
  corner; row 2: "Signed in as …" shortened with an ellipsis, or Sign in), then one panel with the
  Draft / Revise choice (a two-part segmented control, 8px radius, under it
  exactly "Draft: check what you’ve written so far. Revise: check the
  finished manuscript."), **Check document** (the only primary button) beside
  the secondary **Check this section**, its one-line help, and the privacy
  line for the chosen engine. "Check this section" sends the whole document
  and then lists only the section the cursor is in (from its heading to the
  next), with document-wide suggestions under "Whole document" and a note
  saying how many are elsewhere, with "Show the whole document". Then health, errors, results,
  and a closed **Settings** disclosure (engine, show preferences, live underlines, account).
  The account part links to the website's Settings ("To reset your preferences or delete
  your account, use Settings on the website", a new window) rather than repeating those
  actions: they are rare, destructive and need room for their confirmations, and one
  place to keep correct is safer than two (PLAN #12).
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
  ("Found: please confirm", "Partly there", or "Needs your check" in
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
  S4d R4 adds the six states in the header, live underlines (live-only
  results, a card in the text, dismissed cards, applied from the popup,
  applied by Word itself), live underlines paused, and underlines
  unavailable (older Word, no Microsoft 365).

## Underlines in Word (S4d R4)

Word draws the underlines itself (annotations, WordApi 1.7); the pane owns
when they appear and what they mean (docs/inline-review-design.md).

- **Colour by type, from the tokens**: Correction red, Improvement blue,
  Convention green, Preference lavender (Word's fixed schemes, mapped in
  `packages/design-tokens`). Red only for a likely error. Preferences are
  underlined only with "Show preferences" on. Underlines never overlap:
  where two findings cover the same words, the more serious type wins and
  the other stays a card without "In the text".
- **When**: about 1.5 s after typing stops, only the paragraphs that
  changed (each sent with the heading above it), at most one request in
  flight, at most 50 paragraphs and 20,000 characters per request. When
  the pane opens it underlines the document once. Headings, table cells
  and blank lines are never checked live. A reply is drawn only if its
  paragraph still reads exactly as sent; otherwise it is dropped and the
  new text is checked.
- **What is underlined**: sentence-level findings only. Check document's
  whole-document findings stay in the pane, never as underlines. After
  Check document its sentence-level findings are drawn and the live
  results give way; a paragraph edited later shows its live cards in
  place of the full check's.
- **Escalation**: hover or click an underline and its card is highlighted
  and scrolled into view in the pane (a click also leaves a section view
  or a pass so the card is shown); focus stays in the document. With
  WordApi 1.8, the underline's popup shows the type as its title, "Why and
  source: in the Researchly pane" and the brand; it offers the revision
  only when the rule's fix is `safe` (a revision to read first is applied
  from the card). Popup Accept applies the revision through the same
  tracked Apply as the card (or recognises that Word made it); Reject is
  "Not an issue here".
- **Cards**: an underlined finding's card carries "In the text" in its
  head, drawn as the type's underline (colour and pattern from the
  tokens). Every card gains a quiet "Not an issue here" (right-aligned, the
  last action), which removes the card and its underline while the pane
  is open; the notes then say "N suggestions dismissed while the pane is
  open. Show them". Nothing about a dismissal is stored or sent.
- **Before any Check document**, the live cards are listed under "N
  suggestions in the text" with one line saying Check document adds the
  whole-document checks, the brief and the map.
- **States in the header**: the status mark sits at the right of the
  brand's row, the account on the row below (never side by side: at 320px
  they overlapped): checking while a live or full check runs, the
  count, nothing to suggest, checked in part (with the tier that was off),
  can't check right now (retrying after 2, 4, 8, 16, 30 s, back by itself).
  Nothing is drawn before the first check; "Paused" (to a screen reader)
  when the writer turned underlines off. The count is always what the pane
  lists, so dismissing or applying updates it at once.
- **Settings**: a "Live underlines" switch under "Show preferences", on by
  default, remembered on this computer like the engine and stage, with one
  help line (with "This computer": underlines after Check document only).
  Where Word cannot draw underlines (no WordApi 1.7, or the first
  insertion refused: no Microsoft 365) the switch is replaced by one quiet
  line: "Underlines in the document need Word for Microsoft 365, version
  16.79 or later. Suggestions still appear here in the pane." Everything
  else works as before.
- **Privacy**: underlines live only in the open document (Word does not
  save them); the pane keeps the checked text in memory only.

## Underlines while writing (S4d R5)

The website's editor underlines as the writer writes; the textarea stays
native (typing, IME, paste, undo and screen readers are the browser's own).

- **How it is drawn**: behind the textarea, a mirror with the same box,
  type, wrapping, padding and scroll draws the text in transparent ink and
  the underlined words with their type's line, colour, pattern and
  thickness from the tokens (Correction solid, Improvement dashed,
  Convention dotted, Preference wavy, so colour is never the only cue). A
  missing word or comma is a small wedge at the insertion point. One block
  per paragraph, so a keystroke re-lays out only its own paragraph; the
  mirror follows in the frame after the key, never in it.
- **When**: about 1.5 s after typing stops, only the paragraphs the writer
  changed, each with the heading that decides its section (a Markdown
  `#` line or a plain-text section name such as "Methods"; a "Priors"
  subsection under "Methods" is sent as Methods, as the full check reads
  it), one request at a time. Never a sweep of the whole text: switching
  underlines on, changing the format or loading the demo sends nothing by
  itself, and a long paste is checked nearest the caret, one request's
  worth, with one quiet line: "Underlines follow the paragraphs you
  change; for a long paste, press Check to see the whole text." Answers
  are kept in memory by a hash of heading and text, so an undo brings its
  underlines back without a request. A reply for words that changed while
  it was out is never drawn; underlines on unchanged words in an edited
  paragraph move with the edit until the answer comes.
- **Markdown** is sent with its formatting blanked (emphasis marks, link
  brackets and targets, citations, tags), same length, so every offset
  still points at the writer's words. **LaTeX** is not underlined (the
  live check reads plain paragraphs, not markup): one quiet line under the
  editor says "Underlines while writing are available for plain text and
  Markdown; press Check for LaTeX." An uploaded file is never live-checked.
- **Escalation**: hover an underline (about 0.2 s) for the **teaser**, a
  small panel under the words: the type's badge (icon and name), what was
  noticed (bold), "Suggested revision (your call):" with the words in the
  serif, then "Use it" and "Why?" as links. A click on the teaser or "Why?"
  opens the **full card** (the results' card, unchanged) anchored under the
  words inside the editor, with "Use this revision" (or "Remove these
  words") and "Back to your text"; Escape or a click outside closes it and
  focus returns to the text with the words selected. The revision queue in
  the results remains the list layer.
- **Keyboard**: the caret resting in an underline (after arrow keys or a
  click, never while typing) shows the same teaser after 0.6 s, described
  to the textarea (`aria-describedby`) and said once in a polite region
  with the shortcut. **Ctrl + .** (⌘ + . on a Mac) opens the card for the
  underline at the caret, or the next one. "Underlines in your text (N)",
  a quiet disclosure under the editor, lists them (type: message (“words”));
  choosing one selects the words and opens the card.
- **Accepting** a revision replaces the words through the browser's own
  editing command, so Ctrl/Cmd + Z undoes it; the words are checked to be
  unchanged first ("These words have changed since they were checked, so
  nothing was replaced."), and the paragraph is checked again at once.
  "Not an issue here" on the card hides that underline for this page;
  nothing is stored or sent.
- **States**: the status mark (count badge, ring, tick, warning, crossed
  out) sits at the end of the privacy row: checking during a live check or
  Check, the count, nothing to suggest, checked in part (which part was
  off), can’t check right now with a quiet "Try now" (retrying by itself
  after 2, 4, 8, 16, 30 s; old underlines are not drawn as current).
  Nothing before the first check, nothing when switched off. It is not a
  live region here: one polite region says only a settled count, going
  offline, an applied revision or a caret teaser, at most every 8 s.
- **After Check**: the full check's sentence-level suggestions become the
  underlines of the paragraphs it read, so the two agree exactly;
  whole-document findings (figure order, abbreviations defined once) are
  never underlines. A paragraph edited afterwards shows its live answer.
- **The switch**: "Underlines while writing" beside "Show preferences" in
  the composer's switch row, on by default, remembered in this browser
  (`researchly.web.underlines`, a sibling of the Word pane's switch).
- **Privacy**: the text goes only to the engine, as with Check; answers
  are held in this page's memory and never stored.

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

PLAN #12 adds: clear the dictionary (confirm), reset preferences (confirm,
not yet available), delete the account (dialog, word missing or wrong,
deleting, failed with the dialog kept open, not yet available, deleted and
signed out), and the Word pane's link to the website's Settings.

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

S4d R5 adds: underlines while writing (each type, a Preference only with
"Show preferences"), the teaser (by hover and by caret), the card over the
editor, a revision applied and undone, the underline list, checking,
count, clear, partial, offline with "Try now", a long paste left to Check,
LaTeX's one line, switched off.

## Responsive

- 960px and up: composer beside the key; results in two columns with the
  text column sticky.
- Below 960px: one column. The key shows only before the first check, so
  results come straight after the composer. Phones are for reading reports:
  no horizontal scroll at 360px, 16px text, 32px minimum targets. On a
  phone the composer's selects stack at one full width, as in the Word pane.
- In the composer the selects come first, their labels lined up along the
  top; a help line under a select (Check as, Spelling) hangs below it. The
  switches (Show preferences, Underlines while writing) and Check take their own row
  under them, so a switch never floats beside a help line.
- Every disclosure shows its marker: where a summary is a flex row (the
  Word pane's Settings, the queue's "Every issue in this pass" list) it draws the cards'
  small triangle, turned when open.

## Reject

Score, grade or progress bars of any kind; red for anything that is not a
likely error; apply-all or auto-fix buttons (the taskpane's Apply is per
card, read first, tracked where Word can); em dashes in UI copy;
uppercase tracked eyebrows; decorative gradients, glows or shadows;
third-party scripts, fonts or analytics; any control without a real outcome.
