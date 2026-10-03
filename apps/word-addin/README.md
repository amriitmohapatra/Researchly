# Researchly for Word (local add-in)

The Researchly checker inside Microsoft Word: a sidebar that reads your
document, sends it to a **local** server on your own computer (nothing is
ever uploaded), and shows typed, explainable, section-aware suggestions.

```
Word (taskpane sidebar)  ←Office JS→  your document
        │  paragraphs + styles
        ▼
http://localhost:3517  (server.py — Python, stdlib only)
        │
        ▼
researchly engine (spaCy rules, same as the CLI)
```

## Requirements

- Microsoft Word 2016 or later / Microsoft 365 (Mac or Windows)
- The prototype's Python environment already set up (spaCy + model)
- Internet is only needed to load Microsoft's `office.js` script; your
  document text never leaves the machine.

## Setup (Mac)

```bash
cd prototype/word-addin
bash install-mac.sh          # installs the manifest into Word's wef folder
python3 server.py            # keep running while you write
```

Then quit and reopen Word, open any document, and go to
**Insert → Add-ins dropdown → Developer Add-ins → Researchly**
(on some versions: **Insert → My Add-ins → Researchly**). The sidebar opens.

(Windows note: sideloading uses a shared-folder catalog instead of the wef
folder — see Microsoft's "sideload Office Add-ins" docs; everything else
here works the same.)

## Using it

- **Check document** — one full pass; suggestions appear as cards.
- **Re-check as I type** — polls for changes every few seconds and
  re-checks. Off by default: the tool follows the draft-quiet /
  revise-thorough philosophy, and a check-on-demand keeps your drafting
  flow yours.
- Each card: category color (correction / improvement / convention /
  preference), rule, section it fired in, the flagged text (click to jump
  there in the document), the one-line reason, and **Why?** for the full
  rationale from the writing guide.
- **Apply fix** (only on suggestions with a concrete replacement) applies
  it **as a tracked change** by default, so Word's own review workflow
  keeps you in control. Toggle off if you want direct edits.
- **Dismiss** hides one suggestion for the session. **Mute rule** turns a
  rule off persistently (stored in the add-in; "unmute all" link to reset).
- **Add to dictionary** (on spelling cards): teaches Researchly the word
  permanently — saved locally to `~/.researchly/dictionary.txt`, shared by
  every surface (Word, desktop hotkeys, VS Code, CLI).
- Suggestions with a deletion fix (e.g. filler phrases) show a **Delete
  phrase** button.
- **Show preferences** reveals the subjective tier (off by default).
- Sections come from your **Word heading styles** (Heading 1/2/…, Title) —
  use them and the section-aware rules (passive quiet in Methods,
  causal-verb checks in Results/Discussion) work exactly as in the CLI.
  Typed-but-unstyled headings like a lone "Methods" line are also caught.

## Troubleshooting

- **"local server not running"** in the sidebar → start `python3 server.py`
  and wait for "ready." (the first check loads the spaCy model).
- **Add-in not listed in Word** → re-run `install-mac.sh`, fully quit Word
  (Cmd-Q), reopen. Check the manifest landed in
  `~/Library/Containers/com.microsoft.Word/Data/Documents/wef/`.
- **Blank sidebar** → your Word version may refuse plain-HTTP localhost
  panes. Switch to HTTPS:
  1. `openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"`
  2. Trust it once: `sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain cert.pem`
  3. Edit `manifest.xml`: replace every `http://localhost:3517` with
     `https://localhost:3517`, re-run `install-mac.sh`, restart Word.
  4. Run `python3 server.py --https`.
- **"Could not apply"** on Apply fix → the text changed since the last
  check (e.g. auto-recheck raced your typing). Re-check and apply again —
  the add-in now also searches the whole document as a fallback if the
  paragraph moved.
- **Apply fix / tracked changes** → tracked-change application needs
  WordApi 1.4+ (Word 2021 / Microsoft 365). On older Word the toggle shows
  "(unavailable in this Word version)" and fixes apply as direct edits.
  (Historical note: before v0.5 an unsupported tracking call silently
  broke *every* apply — if Apply seemed dead, update to the current files
  and fully quit Word (Cmd-Q) to clear the cached taskpane.)
- **After updating the add-in's files** → restart `server.py` AND fully
  quit Word (Cmd-Q) before reopening; Word caches the taskpane.

## Design notes (why it works this way)

- **Local-first is the point.** Publisher AI policies (Elsevier, Wiley)
  restrict uploading unpublished manuscripts to external tools; a local
  server makes the privacy answer structural, not contractual.
- **On-demand by default, tracked changes for edits, no silent
  modifications, mute as a first-class action** — all direct applications
  of the interaction-design findings in `../../research/04` and the
  dogfooding report.
- The server is Python stdlib only; the pane is plain HTML/JS with
  Microsoft's office.js. No node toolchain, no build step.
