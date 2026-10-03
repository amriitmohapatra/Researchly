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
- Spacing steps: 4, 8, 12, 16, 24, 32, 48.

## States (all reachable, all covered by e2e)

Idle (key + example), invalid input, loading (skeleton, cancellable),
results, empty result ("not a score"), stale results after an edit,
degraded engine tier (calm banner), every error kind with retry where it
helps.

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
