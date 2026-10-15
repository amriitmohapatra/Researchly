# Inline review: underlines where the writer writes

Owner decision, 2026-10-15. Word prediction is removed: "it does not make
sense to include it in the app when any person can simply use Copilot or
other word-based tools". In its place, Researchly learns from how a
commercial field assistant presents its advice, and reaches parity with
it before making it our own. The owner's private study of that product's
shipped builds (15 October 2026) is the reference. It is kept outside the
repository because it describes vendor material that is "not for
redistribution". These notes are written in our own words. They hold no
vendor colour value, class name, string, rule table, placement offset or
protocol detail, and none may be added. Code, data and user-visible text
never name the vendor or its widgets.

Slices R1–R8 in `PLAN.md` implement this note, and ADR-09 to ADR-11 in
`ARCHITECTURE.md` record the decisions behind it.

## 1. What the study teaches (our reading)

1. **Integrate with the platform, not with each app.** On a desktop, one
   accessibility client reads every well-behaved text field. A small data
   table handles the exceptions. Adding an app means adding a row, not
   shipping a release.
2. **Restraint is a feature.** The assistant checks eligibility before
   appearing anywhere. It never attaches to password fields. It stays away
   from fields whose labels name secrets, and it honours per-app rules and
   the user's pause. Being trusted to read text depends on visibly
   declining to read some of it.
3. **Anchor to the content, not to the screen.** The entry widget is pinned
   to a corner of the focused field and moves with it. It keeps off the
   host's own controls, and the user can drag it. The drag is taught once,
   at the moment it becomes relevant.
4. **Never steal focus.** Every surface is a separate, non-activating
   window. The caret, undo history and shortcuts stay with the host.
   Changes are written back only when the user accepts one.
5. **Escalate commitment gradually.** First an underline, then a teaser on
   hover, then the full card, then the full list. Each step costs a little
   more attention and offers a little more help. None of them is forced.
6. **The server judges, the client presents.** The service sends
   categories, ranges and text. The client owns colour, shape, timing and
   placement through design tokens. Restyling needs no change to the
   service.
7. **Colour carries meaning, and few meanings.** A handful of categories
   map to colours. Colour is never the only cue: each category also has an
   icon and a name.
8. **Wait for the pause.** Underlines are held back while a word is still
   being typed. An interruption at the wrong moment costs more than a
   correction delivered a second later.
9. **Keep the grammar of the interface stable.** Placement rules and colour
   meanings stayed fixed for years while new surfaces came and went. Users
   carry their habits from one app, and one release, to the next.
10. **Degrade honestly.** When the service cannot be reached, the product
    says so, changes state and offers help. It never shows old findings as
    if they were current.

The study's gaps are worth avoiding too:
- its colours had no dark-mode values;
- a premium colour turns advice into an upsell;
- an "ask AI" launcher is a generative chatbot, which rule #1 excludes.

## 2. What Researchly keeps, and what it adds

Researchly already does several of these things:
- categories travel from the engine and every surface paints them;
- each category has an icon and a name;
- masking keeps advice out of maths, code, citations and headings;
- the Word add-in applies a revision only on the writer's click, as a
  tracked change where Word can.

What is new in this round:

| Pattern | Researchly's form |
|---|---|
| Underlines in place | Word: the annotations API (ADR-09). Website: the editor underlines as you write. Desktop: overlay clients (ADR-10). |
| Teaser, card, list | Hover gives a teaser (category, what was noticed, the revision if there is one). A click opens the full card (why, source, lesson). The revision queue is the list. |
| Wait for the pause | Live check of the current paragraph after about 1.5 s without typing. The whole document is still checked on request (it runs document-wide checks and the brief). |
| Few, stable states | Six states, one look each (§3). |
| Tokens, not colours | Three tiers in one file, light and dark (§4), generated for CSS, Swift and C#. |
| Degrade honestly | Revision numbers drop stale replies. Retry with backoff. A "cannot check" state with a next step. |
| Restraint | Desktop eligibility gate kept as a data file (§6). The existing masking stays. |

Where Researchly is deliberately different:
- **Four types, not tones.** Correction, Improvement, Convention and
  Preference. A Convention is never painted as an error. Preferences stay
  hidden unless switched on.
- **Section-aware underlines.** The same sentence can be underlined in the
  Discussion and left alone in the Methods.
- **Document-wide findings are not underlines.** Figure order, abbreviations
  defined once and the narrative map belong to a margin or list layer.
  Underlining one word for a whole-document problem misleads.
- **Every card explains itself.** The card gives the why and names its
  source. The card is the lesson.
- **No paywall colour and no chatbot.** The entry point for whole-document
  help is the reviewer's brief.
- **Confidential by design.** Annotations in Word are not saved in the
  file. Overlay clients keep nothing on disk but settings.

## 3. The six states

Every surface uses the same six states:
- the website's status line;
- the header of the Word pane;
- the desktop field widget and its menu-bar item.

| State | Meaning | Look |
|---|---|---|
| `hidden` | Not eligible here, or paused by the writer | Nothing shown (the menu bar says "Paused") |
| `checking` | A check is in flight for the current revision | Ring animation (static under reduced motion) |
| `issues` | Visible suggestions exist | Count badge |
| `clear` | Checked, nothing to show | Plain mark with a tick |
| `partial` | Checked, but a tier was down (e.g. grammar) | Mark with a small warning sign; the reason on hover |
| `offline` | The engine cannot be reached or refused | Mark crossed out; "Can’t check right now" and a next step |

Transitions:
- an edit goes to `checking`;
- a reply goes to `issues`, `clear` or `partial`;
- a failure goes to `offline`, with retries at 2, 4, 8, 16 and 30 s (then
  every 30 s), and any success leaves `offline`;
- leaving the field or pausing goes to `hidden`.

## 4. Design tokens

`packages/design-tokens/tokens.json` is the single source. A script
generates:
- CSS custom properties for the website and the Word pane;
- a Swift file for the Mac client;
- a C# resource dictionary for the Windows client.

The three tiers:
1. **Primitive hues.** Our own ramps, taken from the current website
   palette.
2. **Semantic roles.** `correction`, `improvement`, `convention`,
   `preference`, `focus`, `warning` and `offline`, each with `strong`,
   `subtle` and `text` variants.
3. **Component tokens.** `underline.<category>`, `highlight.<category>`,
   `badge`, `card.rail.<category>`, `widget.ring`, `widget.badge`.

Every token has a light and a dark value, checked for contrast against its
surface. Each category also names an icon and a pattern for underlines
when colour is unavailable: solid for Correction, dashed for Improvement,
dotted for Convention, wavy-dotted for Preference.

Word's annotation colour schemes are fixed. The mapping is Correction →
red, Improvement → blue, Convention → green, Preference → lavender.

## 5. The live-check contract

`POST /v1/check-paragraphs` (R3) is the fast path that every underline
surface calls after a typing pause.

- **Request:**
  ```
  { revision: int,
    paragraphs: [{ id: str, text: str, style?: str,
                   heading?: str }],
    options }
  ```
  - `heading` is the text of the nearest heading above the paragraph, so
    advice stays section-aware without the whole document.
  - `options` are the usual check options (profile, spelling, preferences).
- **Response:** `{ revision, paragraphs: [{ id, suggestions: [...] }], health,
  state }`. `revision` is echoed so the client can drop stale replies.
- **Each suggestion carries:**
  - `id`: stable for the same rule, paragraph, range and flagged text;
  - `begin` and `end`: **UTF-16** offsets within the paragraph;
  - `category` and `critical` (true for Correction);
  - `message`, `plain`, `why`, `source`, `replacements[]`, `section`,
    `fix_safety`.
- **Scope:** rules whose scope is the sentence or paragraph only. Document
  rules, the brief, the narrative map and the read-outs stay in the full
  check.
- **Budget:** p50 under 300 ms and p95 under 800 ms for a 200-word
  paragraph on a warm engine, grammar tier included. A test pins the
  budget.
- **Native clients:** a request with no `Origin` header is allowed. CORS
  protects browsers; rate limits protect the engine. Same privacy rules as
  `/v1/analyze`: in memory only, and canary-tested.

Offsets are UTF-16 because Word, browsers, macOS Accessibility and Windows
UI Automation all count in UTF-16. The engine converts once, at the edge.

## 6. Desktop overlay clients (R7 Mac, R8 Windows)

Source lives in `apps/desktop-overlay-mac/` (Swift, AppKit) and
`apps/desktop-overlay-win/` (C#, .NET 8, WPF). Each has a README with build
steps for the owner's machine. Both are open source and unsigned, or
ad-hoc signed on the Mac (D9). Each splits into:
- **Core:** platform-neutral logic with unit tests:
  - the text snapshot and its diff;
  - UTF-16 range arithmetic;
  - the eligibility gate;
  - the state machine and its retry timing;
  - the engine client.
- **Shell:** thin platform code that reads the focused field, asks for
  range rectangles, draws, and writes back.

The loop:
1. **Capture.** Read the focused text element, its value, selection and
   visible range. Mac: Accessibility. Windows: UI Automation TextPattern.
2. **Gate.** Check eligibility.
3. **Wait.** Pause until typing stops.
4. **Check.** Send the changed paragraphs with a revision.
5. **Measure.** Ask the host for each range's rectangle, one per line,
   clipped to the visible area.
6. **Draw.** Underlines go in a click-through, non-activating, transparent
   window.
7. **Hover.** A hover opens the teaser; a click opens the full card window.
8. **Write back.** On Accept, replace through the accessibility layer
   first, then fall back to select-and-type, then select-and-paste. Each
   app's method is set in the data file, and the host's undo history is
   kept.

The eligibility gate, `rules/eligibility.json`, is our own file, written
from scratch. It holds:
- secure and password fields: never;
- a label and identifier keyword blocklist in English, French, German,
  Spanish, Portuguese, Chinese, Hindi and Malay: password, passcode, PIN,
  card number, security code, one-time code, sign in, log in, user name,
  date of birth, phone, search;
- per-app rules by bundle ID or executable: off for terminals, password
  managers and code editors (VS Code has the language server);
- the widget corner and offset per app, with forbidden corners;
- the write-back method per app.

The writer can pause for 1 hour, until tomorrow, or always for this app or
site. Nothing is stored beyond settings. Text goes only to the engine the
writer chose: hosted, or "This computer".

## 7. Researchly grammar notes (R6)

Grammar rules written for Researchly at build time, in our own words, from
general knowledge of English grammar and its regional conventions (owner,
2026-10-15). They are not copied from any product or book. They live in
`docs/grammar-notes.md` (the source document that cards cite as
"Researchly grammar notes", source code `rgn`). That file:
- gives each rule's statement and reasoning;
- says how the rule differs between US, UK, Canadian, Australian and
  Indian English;
- ends with a list of further reading.

Each rule:
- is deterministic;
- has fire and don't-fire tests;
- has a `plain=` explanation;
- must not raise the noise floor;
- cannot be shown above Improvement unless its precision on the
  real-document bench is at least 0.9.
