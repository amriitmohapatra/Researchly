# Researchly for Windows (overlay client)

Underlines, a hover teaser and a full card over the text field you are
writing in: Notepad, Word, Outlook, a browser text area, Teams, Slack and
any other app whose text fields Windows' UI Automation can read. It is the
Windows half of PLAN.md **R8**; the design is `docs/inline-review-design.md`
(sections 3 to 6) and ADR-10 in `ARCHITECTURE.md`.

The client does no language analysis itself. It reads the focused field,
waits for you to pause, sends the paragraphs that changed to the Researchly
engine you chose, and draws what comes back. Open source, not sold (D9);
the build is unsigned.

## What you need

- Windows 10 (1809 or later) or Windows 11, 64-bit.
- The **.NET 8 SDK**: <https://dotnet.microsoft.com/download/dotnet/8.0>
  (choose "SDK", x64). A later SDK (9, 10) also works. The SDK includes the
  .NET 8 Desktop Runtime the app needs to run.
- The whole repository (the build reads `packages/desktop-rules/`), from
  GitHub's "Code, Download ZIP" or `git clone`.
- An engine to check text (see [Choosing the engine](#choosing-the-engine)).

## Build and run

Open PowerShell in this folder (`apps\desktop-overlay-win`) and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1 -Run
```

The script checks the SDK, runs the core tests, and publishes the app to
`publish\win-x64\Researchly.Overlay.exe` (with its `rules` folder next to
it). `-SingleFile` makes one `.exe` instead of a folder of DLLs; `-Run`
starts it. `-ExecutionPolicy Bypass` is needed because Windows blocks
downloaded scripts by default; alternatively run `Unblock-File .\build.ps1`
once.

Without the script:

```powershell
dotnet test tests\Researchly.Overlay.Core.Tests
dotnet publish src\Researchly.Overlay\Researchly.Overlay.csproj -c Release -r win-x64 --self-contained false -o publish\win-x64
.\publish\win-x64\Researchly.Overlay.exe
```

Or open `Researchly.Overlay.sln` in Visual Studio 2022 and press F5 with
`Researchly.Overlay` as the start-up project.

Researchly has no main window. Look for its round icon in the notification
area (click the `^` arrow by the clock; drag it out to keep it visible).
Right-click it for the menu. Running a second copy does nothing; quit from
the menu.

A GitHub Actions workflow, **Desktop overlay (Windows)**, builds the same
thing on a Windows runner when started by hand (Actions tab, "Run
workflow") and offers the unsigned build as a download for seven days.

### "Windows protected your PC" (SmartScreen)

The build is not code-signed, so the first time you start it Windows
SmartScreen may show "Windows protected your PC". Click **More info**, then
**Run anyway**. That happens once per new build. A program you built
yourself from this source is what you ran; nothing else is downloaded.
Antivirus tools sometimes look twice at programs that read other windows'
text and send keystrokes; that is what this one does, for the reasons
below, and only in the ways described.

### Start with Windows (optional)

Press Win+R, type `shell:startup`, and put a shortcut to
`Researchly.Overlay.exe` in the folder that opens.

## Choosing the engine

Right-click the icon, then **Engine**:

- **This computer** (default): `http://127.0.0.1:3517`. Nothing leaves
  the machine. Run Researchly's engine locally on that port, from the
  repository root (needs Python 3.10 and, for the grammar tier, Java 17+):

  ```powershell
  cd services\engine
  pip install -r requirements-dev.txt
  $env:RESEARCHLY_ENV = "development"; $env:PORT = "3517"
  python -m researchly_service
  ```

  The live check uses `POST /v1/check-paragraphs` (design note section 5).
  An engine without that endpoint answers 404, and the client says "this
  engine does not offer live checks" rather than pretending.
- **Hosted**: choose **Set hosted address...** and enter the hosted
  engine's `https://` address. Plain `http://` is refused for anything but
  this computer.

If no engine answers, the widget shows the crossed-out mark and the menu
says "Can't check right now", with **Try again now**. Retries happen by
themselves after 2, 4, 8, 16 and 30 seconds, then every 30 seconds.

## How it looks and behaves

- **Underlines** appear about 1.5 seconds after you stop typing, under
  the words the engine flagged. Each type has its own colour *and* line, so
  colour is never the only cue: Correction solid, Improvement dashed,
  Convention dotted, Preference wavy dots (Preferences are hidden unless you
  tick **Show Preferences** in the menu). Colours follow the Windows app
  theme (light or dark) and high contrast.
- **Hover** over an underline for a moment: a teaser shows the type, what
  was noticed and the revision. **Click the teaser** for the full card:
  the explanation in plain words, the why, and its source.
- On the card, **Accept** writes the revision into your text (undo it in
  your app with Ctrl+Z as usual); **Not an issue** hides it for this
  session; **Previous / Next** step through every suggestion in the field.
- The **field widget**, a small round mark at a corner of the field, shows
  the state: a turning ring (checking; still if Windows animations are off),
  a count (suggestions), a tick (nothing to show), a warning sign (some
  checks unavailable, the reason on hover), a crossed-out mark (cannot
  check). Click it to open the first card. Drag it if it covers your text;
  it remembers the spot for that app.
- **Pause**: from the menu, for 1 hour, until tomorrow, or always in the
  current app. Paused means hidden and not reading.
- No Researchly window ever takes the keyboard: the caret, your app's undo
  history and its shortcuts stay where they were. (The one exception is the
  hosted-address box, which you open yourself to type in.)

Where it does not appear, on purpose:

- password fields, ever;
- fields whose label, placeholder, identifier or form name mentions a
  password, PIN, card number, security or one-time code, signing in, user
  name, date of birth, phone or search, in English, French, German,
  Spanish, Portuguese, Chinese, Hindi and Malay
  (`packages/desktop-rules/fields.json`, shared with the Mac client);
- terminals, code editors (VS Code has Researchly's language server) and
  password managers, and any app you pause
  (`packages/desktop-rules/apps-windows.json`);
- read-only text, and Researchly's own windows.

Adding or adjusting an app is a row in `apps-windows.json` (widget corner
and inset, corners to avoid, write-back methods in order, whether to poll, whether its document element is always the writing surface,
whether to read only the visible paragraphs), then rebuild.

## Privacy

- The client reads a field's text only after the eligibility checks pass,
  only while that field has focus, and keeps it in memory. Leaving the field
  or pausing drops it.
- It sends the paragraphs that changed, each with the nearest heading above
  it, to the engine you chose, and nothing to anyone else. The engine checks
  them in memory and does not store them (CLAUDE.md rule 2; the engine's
  canary test).
- The only file it writes is its settings,
  `%APPDATA%\Researchly\overlay-settings.json`: engine choice, hosted
  address, pauses, the Preferences switch, widget drags, whether the drag
  tip was shown. No text, no suggestion, no field name. A core test fails if
  a field is added there without review.
- It keeps no log. Errors are reported only to an attached debugger, by type
  name, never with a message (messages can quote input).
- When Accept falls back to pasting, the revision goes on the clipboard for
  a moment, marked so that Windows keeps it out of clipboard history and
  cloud clipboard sync, and your previous clipboard is put back.

## Manual test checklist (PLAN R8 "done when")

Tick these on a Windows machine with a working engine. Use your own
sentences; for example type "We measured teh rate in teh field." in each
app. Note the Windows version, the display scale(s) and the app versions.

**Notepad**
- [ ] Type, pause: underlines appear after about 1.5 s, not while typing.
- [ ] Underlines sit under the right words; they follow the text when you
      scroll, resize the window, and drag it to a monitor with a different
      display scale (or change the scale in Settings, Display).
- [ ] Hover shows the teaser; clicking it opens the card with plain words,
      why and source.
- [ ] Accept changes the text; **Ctrl+Z** in Notepad undoes it.
- [ ] Not an issue hides it; the widget count drops.

**Word** (desktop app)
- [ ] Same as Notepad on a page of text, including scrolling through a long
      document (only the paragraphs on screen are read).
- [ ] Accept, then Ctrl+Z in Word; the change is undone and Word's own
      formatting is untouched.
- [ ] With Track Changes on, Accept shows up as a tracked change.

**Outlook** (compose a new mail)
- [ ] Underlines in the body; Accept and Ctrl+Z work.
- [ ] Note whether the widget appears in the To, Cc or Subject boxes (the
      field blocklist does not name them; report whether it should).

**Edge and Chrome** (a plain `<textarea>` page, and a site's comment box)
- [ ] Underlines, teaser, card, Accept and Ctrl+Z work in the text area.
- [ ] Nothing attaches to a password box, a sign-in or search box, or a
      card-number field (try a shop's checkout page without paying).
- [ ] Nothing attaches to the address bar.

**Never attaches** (the widget must not appear)
- [ ] Windows Terminal, Command Prompt, PowerShell, VS Code, a password
      manager.
- [ ] A field labelled in another language: "Mot de passe", "Kennwort",
      "Contraseña", "Senha", "密码", "पासवर्ड", "Kata laluan".

**States and recovery**
- [ ] Stop the engine (or switch Wi-Fi off with the hosted engine): within a
      check the widget shows the crossed-out mark and the menu says "Can't
      check right now". Old underlines for text you have since changed are
      not shown.
- [ ] Start the engine again: within 30 s (or at once with **Try again
      now**) the widget returns to a count or a tick.
- [ ] Partial: stop the engine's grammar tier (no Java) and check that the
      warning sign and its reason appear.
- [ ] Pause for 1 hour hides everything; Resume brings it back. Pause in
      this app affects only that app.

**Never steals focus**
- [ ] While the widget, teaser or card is showing, keep typing: every key
      lands in your app; the caret never jumps; Alt+Tab never lists
      Researchly; the app's title bar stays active.
- [ ] Clicking Accept or Not an issue leaves the caret in your app.

**Display**
- [ ] Light and dark app mode (Settings, Personalisation, Colours) both
      read well; switching while running repaints.
- [ ] High contrast: underlines use the system highlight colour.

## Troubleshooting

- **No icon.** It may be in the overflow area (`^`). If the program
  closed at once, check that `rules\fields.json` is next to the `.exe` and
  that the .NET 8 Desktop Runtime is installed (`dotnet --list-runtimes`
  shows `Microsoft.WindowsDesktop.App 8.x`).
- **No underlines, widget shows a tick or a count.** The app exposes the
  text but not its position. The widget and card still work (click the
  widget). Note the app and version.
- **No widget at all in an app.** The app may not expose its text to UI
  Automation, may be paused or disabled in `apps-windows.json`, or the
  field's label matched the blocklist. Programs running as administrator
  cannot be read by a normal program (Windows' rule); that is expected.
- **Electron apps (Teams, Slack) show nothing.** Some only turn on their
  accessibility tree when asked by a screen reader. Try Narrator once
  (Ctrl+Win+Enter), then turn it off, and report the result.
- **Firefox.** Firefox's support for UI Automation's text interfaces is
  partial; the widget may appear without underlines.
- **Underlines slightly off at a non-100 % scale.** Report the scale of
  each monitor and whether the window spans two monitors.
- **Accept did nothing.** The card says why: the text changed since the
  check, the app was no longer in front, a key was held, or the app refused
  both typing and pasting. Nothing is changed in those cases.
- **"Can't check right now" with "This computer".** Start the engine (see
  above) and check `http://127.0.0.1:3517/v1/health` in a browser.

## How it is built

```
apps/desktop-overlay-win/
├── Researchly.Overlay.sln
├── build.ps1                         test + publish (win-x64, unsigned)
├── src/Researchly.Overlay.Core/      platform-neutral; builds and tests on any OS
│   ├── Text/                         snapshot, paragraph diff, UTF-16 ranges, headings
│   ├── Eligibility/                  fields.json + apps-windows.json, the gate
│   ├── State/                        the six states, retry backoff
│   ├── Timing/                       scheduler interface, 1.5 s debounce
│   ├── Engine/                       live-check contract, HTTP client, tolerant decoding
│   ├── Session/                      the loop: diff, wait, send, drop stale, place
│   ├── Placement/                    widget corner, inset, drag, work area
│   ├── WriteBack/                    pre-checks and outcome of Accept
│   ├── Settings/                     settings file, pauses, engine address rules
│   └── Tokens/                       category colours, patterns and icons (light, dark)
├── src/Researchly.Overlay/           the Windows shell (WPF, .NET 8)
│   ├── Capture/                      UI Automation on its own thread: focus, text,
│   │                                 rectangles, write-back, input, clipboard
│   ├── Ui/                           overlay, widget, teaser, card, tips, address box
│   ├── Tray/                         notification-area icon and menu
│   ├── Platform/                     dispatcher timers, theme, engine switch
│   ├── Native/                       Win32 declarations
│   └── OverlayController.cs          wires the loop together
└── tests/Researchly.Overlay.Core.Tests/   xUnit; synthetic fixtures only
```

The core holds everything that can be tested without Windows: the text
snapshot and its paragraph diff (stable ids, so only changed paragraphs are
sent), UTF-16 range arithmetic (surrogate pairs and combining marks), the
eligibility gate, the six-state machine with its 2/4/8/16/30 s backoff, the
1.5 s debounce, revision tracking that drops stale replies, and the engine
client. The shell is thin: it reads the focused field through UI
Automation (TextPattern, TextPattern2 for the caret, ValuePattern; text
events plus polling), asks for one rectangle per line of each range
(`GetBoundingRectangles`, physical pixels under per-monitor DPI awareness
v2), draws in a click-through, non-activating, topmost window, and writes
back by selecting the range through UI Automation and typing the revision
as Unicode input, then by pasting, in the order the app's row lists. Each
attempt is checked by reading the text again; a method that changed
nothing lets the next one try, anything unexpected stops.

The colours in `Core/Tokens/DesignTokens.cs` are copied from the website's
category colours until `packages/design-tokens/` (PLAN R2) generates a C#
file; replace that class with the generated one then.

The core's tests run anywhere with the .NET 8 SDK:
`dotnet test tests/Researchly.Overlay.Core.Tests`. The WPF project can be
compiled (not run) on Linux or macOS too, because it sets
`EnableWindowsTargeting`.
