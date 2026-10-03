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
3. **Why each suggestion exists**: the message, the flagged words, and a
   visible source on every card. The full explanation is one click away.
4. **That nothing is rewritten and nothing is kept**: revisions are labelled
   "your call"; the privacy line sits next to the Check button.

## Hierarchy (results)

`N suggestions` heading, then one row of filter chips (with the hidden
preference note at its end), then two columns: your text on the left (the
thing being revised), suggestions on the right in document order. Read-outs
come last; they describe the text and are never a score.

A card reads top to bottom as: category and section, what was noticed
(bold), the flagged words (serif), the suggested revision (your call), the
source, then "Why?". A student scanning the list reads only the first two
lines of each card.

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
- **Card actions (signed in)** sit after "Why?", as quiet links: "Mute this
  rule", and on spelling cards "Add “word” to dictionary". Each confirms in
  a quiet notice with a link to Settings, then re-checks.
- **Settings** is one column of panels: Muted rules (name, code, one-line
  why, Unmute), How suggestions are shown (switch, spelling locale),
  Your dictionary (add with inline limits, tiles with Remove), Delete. Every
  change saves at once and is announced; a failed save moves the control
  back and says why. Delete asks first, with focus on "Keep them".
- **Dialogs** are native `<dialog>` (focus contained, Escape closes, focus
  returns to the opener).

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
likely error; apply-all or auto-fix buttons; em dashes in UI copy;
uppercase tracked eyebrows; decorative gradients, glows or shadows;
third-party scripts, fonts or analytics; any control without a real outcome.
