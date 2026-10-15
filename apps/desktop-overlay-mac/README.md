# Researchly Overlay for macOS

Researchly's suggestions, underlined where you write: in TextEdit, Word,
Pages, Mail, Notes and text areas in your browser. Pause typing for a
moment and the paragraph you are working on is checked. Hover over an
underline to see what was noticed. Click it for the full explanation, then
**Accept** or **Not an issue**.

It is a small background app with a menu-bar item and no Dock icon. It
uses macOS Accessibility to read the field you are typing in and never
takes the keyboard away from the app you are writing in. Design:
`docs/inline-review-design.md` (sections 3 to 6); plan: PLAN.md S4d R7.

> Open source and free to share (MIT). The app is **ad-hoc signed** on
> your Mac, not signed with a developer certificate, so macOS asks for
> Accessibility again after every rebuild (see below).

---

## 1. What you need

- A Mac with **macOS 14 (Sonoma) or newer** (Apple Silicon or Intel).
- **Swift 5.9 or newer**. The Xcode Command Line Tools are enough; the
  full Xcode app is not needed:

  ```sh
  xcode-select --install     # once; skip if already installed
  swift --version            # should say 5.9 or later
  ```

- This repository, downloaded from GitHub (Code → Download ZIP, or
  `git clone`). The build reads the rules in `packages/desktop-rules/`, so
  build from the full checkout, not from this folder alone.
- An engine to check with: the hosted Researchly engine (its address), or
  the engine running on this computer (see section 4).

## 2. Build and run

```sh
cd apps/desktop-overlay-mac
./build.sh                 # builds "build/Researchly Overlay.app"
open "build/Researchly Overlay.app"
```

Options:

- `./build.sh --test` runs the core's unit tests first.
- `./build.sh --dmg` also makes `build/Researchly-Overlay.dmg`, a disk
  image to copy the app to another Mac.

You can drag the app to `/Applications`. To start it at login, add it in
System Settings → General → Login Items.

The first build takes a minute or two. Later builds are quicker.

## 3. Allow Accessibility (and again after each rebuild)

On first launch, a window explains why Researchly needs Accessibility.
Click **Continue**. macOS shows its own prompt and opens System Settings →
Privacy & Security → Accessibility. Turn on **Researchly Overlay**.
Underlines start as soon as the switch is on. You do not need to restart
the app.

**After every rebuild**, macOS sees a new app, because ad-hoc signatures
change with each build. The old entry stays in the list but no longer
works. To fix it:

1. Open System Settings → Privacy & Security → Accessibility.
2. Select **Researchly Overlay** and remove it with **−**.
3. Start the new build and allow it again.

The menu-bar item shows the permission state ("Accessibility: allowed").
If permission is missing, it shows a button that opens the right settings
page.

## 4. Choose the engine

Click the menu-bar item, then **Check with**:

- **This computer (127.0.0.1:3517)**: text never leaves the Mac. Needs a
  local Researchly engine that offers `POST /v1/check-paragraphs` on port
  3517. The live-check endpoint is new (PLAN S4d R3). Until your local
  engine has it, the overlay shows "Can't check right now: this engine
  doesn't offer live checks yet".
- **Hosted engine…**: enter the engine's address, starting with
  `https://`. Plain `http://` is accepted only for this computer.

**Show Preference suggestions** adds the Preference type, which is hidden
by default as on every Researchly surface.

## 5. Using it

- **Underlines** appear after about 1.5 seconds without typing. Each type
  has its own colour and line, so colour is never the only cue:
  Correction is a solid line, Improvement dashed, Convention dotted and
  Preference wavy-dotted.
- **Hover** over an underline to see a teaser: the type, what was
  noticed, and the revision if there is one.
- **Click** an underline, or the teaser's "Why and how…", to open the
  card: the explanation in plain words, why it matters, and where the
  advice comes from. **Accept** changes the text in the app; Cmd-Z in that
  app undoes it. **Not an issue** hides the suggestion until you leave the
  field. Nothing is remembered.
- **The widget** is the small mark at the corner of the field. It shows
  the state: a spinning ring while checking, a number for suggestions, a
  tick when clear, a warning sign when only part of the check could run,
  and a crossed-out mark when the engine can't be reached. Hover over it
  for details. Click it for the list and the pause options. Drag it to
  move it. The new place is kept for that app.
- **Pause** from the menu bar: for 1 hour, until tomorrow, or always in the
  current app.

Researchly never attaches to password fields, to fields whose label or
identifier asks for private details (a password, PIN, card number,
one-time code, login, date of birth, phone, search, in eight languages:
`packages/desktop-rules/fields.json`), or to Terminal, iTerm, VS Code,
Xcode, 1Password, Keychain Access or Passwords.

## 6. Manual test checklist (PLAN R7 "done when")

Run these on your Mac after building. Tick each one, and note any app
where a check fails, with the details from **About this field…** in the
menu bar. That window shows the kind of field, never its text.

Set up: build, allow Accessibility, choose an engine that has
`/v1/check-paragraphs`, and keep a short test paragraph with a known
mistake handy (for example "Their are three results in the the table.").

**Underlines appear after a pause**

- [ ] TextEdit (a new rich-text document): type the paragraph, stop
      typing, and see underlines within about 2 s. The widget shows a
      spinning ring and then a number.
- [ ] Microsoft Word (document body): same.
- [ ] Pages (document body): same.
- [ ] Mail (a new message body): same. The To and Subject fields get
      nothing.
- [ ] A browser text area (Safari, then Chrome or Firefox; for example a
      comment box on any site or `data:text/html,<textarea cols=80 rows=10>`):
      same.
- [ ] While you type, no underline appears under the word being typed.
      Underlines in other paragraphs stay in place.

**Underlines stay aligned**

- [ ] Scroll the document: the underlines move with the words, and ones
      scrolled out of view disappear.
- [ ] Resize the window: the underlines follow the reflowed text.
- [ ] Move the window to another display, or change the display
      arrangement or resolution (System Settings → Displays): the
      underlines realign.
- [ ] Switch to another app: the underlines and widget disappear. Switch
      back: they return.
- [ ] Put another app's window over part of the document: the overlay
      hides and does not draw on top of the other window.
- [ ] Dark mode (System Settings → Appearance): the colours change, and
      the underlines and cards stay readable.

**Accept and undo**

- [ ] Hover over an underline: the teaser appears. Click it: the card
      appears.
- [ ] Click **Accept** on a suggestion with a revision: the text changes,
      and the caret and focus stay in the document (you can keep
      typing).
- [ ] Press **Cmd-Z** in the app: the change is undone in one step.
- [ ] Do the same in Word, Pages, Mail and a browser text area. Note
      which method worked if one fails (About this field… lists the
      write-back order).
- [ ] **Not an issue** removes the underline. It comes back only after
      you leave the field and return.
- [ ] Open a card, then type in the document: the card closes (a card
      never acts on text that has changed since it opened).

**Restraint**

- [ ] A password field (for example System Settings → Users & Groups, or
      a website's login): no widget, no underline.
- [ ] A field labelled "Search", "Card number" or "Email or phone" on a
      website: nothing.
- [ ] Terminal and VS Code: nothing.
- [ ] Pause for 1 hour: everything disappears. Resume: it returns.
- [ ] **Pause in TextEdit**: TextEdit is ignored and Pages still works.

**Offline and recovery**

- [ ] Turn Wi-Fi off (with a hosted engine), or stop the local engine:
      after the next pause, the widget shows the crossed-out mark. Hover
      over it: "Can't check right now" and what to do. Old underlines are
      not shown as current.
- [ ] Turn Wi-Fi back on: within 30 s, or at once after your next pause in
      typing, the check runs and the underlines return.

**Never steals focus**

- [ ] Throughout: the app you write in stays active (its name stays in
      the menu bar). Typing always goes to the document, including right
      after clicking the widget, a teaser or a card.

## 7. Troubleshooting

| What you see | What to do |
|---|---|
| Nothing at all, and the menu says "Accessibility: not allowed" | Allow it (section 3). After a rebuild, remove the old entry first |
| Nothing in one app, other apps fine | Menu bar → **About this field…**. If it says "This kind of field (AXSomething) isn't supported here", add that role to the app's `roles` in `packages/desktop-rules/apps-mac.json` and rebuild. If it says "Checked: yes", see the next rows |
| Crossed-out widget, "Can't reach the engine" | Check the address in **Check with**, your connection, or that the local engine is running on port 3517 |
| The ring spins for several seconds on the first check of the day | A hosted engine can take a few seconds to wake up. Later checks are quicker. A check that takes over 15 s counts as "can't check" and is retried |
| "This engine doesn't offer live checks yet" | The engine is older than the live-check endpoint. Update it, or choose another engine |
| Underlines in the wrong place in a browser | Reload the page once. Chrome, Arc and Firefox build their accessibility tree when Researchly first asks for it |
| Underlines in Slack or another Electron app don't appear | Quit and reopen that app with Researchly already running |
| Accept does nothing in an app | About this field… shows the write-back order. Reorder `write_back` for that app in `apps-mac.json` (for example `["paste", "typing"]`) and rebuild |
| Accept pasted, and your clipboard changed | The clipboard is restored 0.8 s after a paste, unless you copied something else in that time |
| The widget covers a button of the app | Drag it somewhere else. The place is kept per app |
| The build fails with a Swift error | Run `swift --version`: 5.9 or newer is required. Then `xcode-select --install` or update Xcode |

To see crash output while testing, run the app from a terminal:
`"build/Researchly Overlay.app/Contents/MacOS/ResearchlyOverlay"`. The app
logs nothing itself, and never any document text.

## 8. Privacy

- The text of the focused field goes **only to the engine you chose**:
  this computer, or the hosted engine whose address you entered. It is
  sent over HTTPS, or over loopback for this computer, without cookies,
  caches or credentials.
- **Nothing is stored.** The app keeps the field's text in memory only
  while the field has focus. Settings are stored in `UserDefaults`
  (`org.researchly.overlay`): the engine choice, the pause, the widget's
  position per app, and whether the drag tip was shown. Text,
  suggestions and history are never stored. "Not an issue" lasts until you
  leave the field.
- Password fields are never read: the gate refuses them before their
  contents are touched. Fields whose labels ask for private details are
  refused the same way.
- A paste puts the replacement on the clipboard for under a second and
  marks it as transient and concealed, so clipboard managers skip it.

## 9. For developers

```
Sources/ResearchlyOverlayCore/   Foundation only; builds and tests on Linux too
  UTF16Text.swift        UTF-16 ranges, grapheme-safe substrings, paragraph splitting
  Snapshot.swift         text snapshot, paragraph diff (which paragraphs changed)
  ParagraphLedger.swift  paragraph ids, status, placed suggestions, heading detection
  Eligibility.swift      fields.json + apps-mac.json, the gate, per-app rules
  States.swift           the six states, backoff 2/4/8/16/30 s, revisions, debounce, pause
  EngineModels.swift     the live-check request and a tolerant response decoder
  EngineClient.swift     POST {engine}/v1/check-paragraphs, engine choice, errors
  LiveCheckSession.swift the loop: pause → send → drop stale → retry → state
  Geometry.swift         AX↔AppKit flip, line splitting, clipping, widget placement
  Tokens.swift           category colours and patterns (temporary, see below)
Sources/ResearchlyOverlay/       the AppKit shell (macOS only)
  FocusTracker / FieldReading    AXObserver, polling, reading fields and line rectangles
  UnderlineOverlay               click-through panel drawing underlines (CAShapeLayer)
  FieldWidget / SuggestionPanels widget, teaser, card (non-activating panels)
  WriteBack                      Accessibility → typing → paste, verified, undo kept
  OverlayController              ties the loop together; StatusMenu, Onboarding, AppDelegate
Tests/ResearchlyOverlayCoreTests/  XCTest for the core (fixtures in Fixtures/)
```

- `swift test` runs the core's tests (on a Mac or on Linux).
- `swift run ResearchlyOverlay` runs the app without bundling. It finds
  the rules in the checkout, but macOS grants Accessibility to the
  terminal app you started it from.
- `Tokens.swift` holds the category colours until
  `packages/design-tokens/` (PLAN S4d R2) generates them. Replace it with
  the generated file then.
- Per-app behaviour lives in `packages/desktop-rules/apps-mac.json`
  (schema: `packages/desktop-rules/README.md`). Adding or tuning an app is
  a data change.
- GitHub Actions: **Desktop overlay (macOS)** in the Actions tab builds the
  app and runs the core tests on a macOS runner. It runs only when started
  by hand, because macOS minutes are costly on a private repository.
