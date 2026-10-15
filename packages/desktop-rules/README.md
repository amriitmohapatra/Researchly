# packages/desktop-rules

Researchly's data files for the desktop overlay clients
(`docs/inline-review-design.md` §6). They are written from scratch for
Researchly. Adding or tuning an app is a change here, not a release: the
build scripts copy these files into each app.

| File | Read by | What it holds |
|---|---|---|
| `fields.json` | macOS and Windows clients | Fields to refuse: secure fields always, plus label and identifier keywords in eight languages, and the field length limits |
| `apps-mac.json` | macOS client (`apps/desktop-overlay-mac`) | Per-app rules by bundle id |

## fields.json (shared; schema version 1)

The schema is shared by both clients. **Do not rename or remove keys.**
New keys must be optional, documented here, and ignored by clients that
don't know them.

| Key | Type | Meaning |
|---|---|---|
| `version` | int | Schema version (1) |
| `never_secure_fields` | bool | Secure (password) fields are refused. The clients refuse them whatever this says. The key documents the rule |
| `keywords` | object: language code → list of terms | A field is refused if its label, placeholder, help text, identifier, or an enclosing form's name contains a term |
| `scripts_matched_as_substrings` | list of language codes | Languages whose terms match anywhere in the text (no spaces between words, e.g. `zh`) or as plain substrings (`hi`) |
| `min_field_characters`, `max_field_characters` | int | Fields shorter or longer than this are not checked |

How the macOS client matches (Windows should match the same way):

- Latin-script terms match on **word boundaries**, ignoring case and
  accents. Any non-letter, non-digit character separates words, so "Sign-in",
  "sign_in" and "sign in" all match "sign in". camelCase splits words, so
  `userNameField` contains "user name".
- In **identifiers** only, terms of 8 letters or more also match inside
  compound words (`newpasswordfield` contains "password"). Shorter terms
  don't, so "search" never matches "research".
- Terms of the `scripts_matched_as_substrings` languages match as
  case-folded substrings.
- Window titles are never matched: a document called "Login notes" is still
  a document.

## apps-mac.json (macOS only; schema version 1)

```json
{
  "version": 1,
  "defaults": { ...an app entry without bundle_ids... },
  "apps": [ { "name": "...", "bundle_ids": ["..."], ...any keys to override... } ]
}
```

Every key except `bundle_ids` is optional. A missing key falls back to
`defaults`, and a key missing from `defaults` falls back to the client's
built-in value (in brackets below).

| Key | Type | Meaning |
|---|---|---|
| `name` | string | Shown in "About this field…" and in "Researchly is off in …" |
| `bundle_ids` | list of strings | Exact bundle ids, or a prefix ending in `.*` (e.g. `com.1password.*`). Matching ignores case. An exact match beats a prefix, and a longer prefix beats a shorter one |
| `enabled` | bool [true] | `false`: never attach in this app (terminals, password managers, code editors) |
| `priority` | `"normal"` or `"low"` [normal] | `low`: checked with a longer pause (2.5 s) and smaller requests |
| `roles` | list of AX roles [`["AXTextArea"]`] | Which Accessibility roles to attach to. Single-line `AXTextField`s are not included by default |
| `widget.corner` | `top-left`, `top-right`, `bottom-left`, `bottom-right` [bottom-right] | Where the field widget sits |
| `widget.offset` | `[x, y]` points [`[6, 6]`] | Inward from that corner |
| `widget.forbidden_corners` | list of corners [none] | Corners where the app draws its own controls. If the preferred corner is forbidden, the first allowed one in the order bottom-right, bottom-left, top-right, top-left is used |
| `write_back` | list of `accessibility`, `typing`, `paste` [all three, in that order] | How Accept changes the text, tried in order. Each attempt is verified by reading the field again; a partial change stops the sequence |
| `needs_polling` | bool [false] | Also poll the field (twice a second) because the app's change notifications are unreliable |
| `enhanced_accessibility` | `"AXEnhancedUserInterface"`, `"AXManualAccessibility"` or null [null] | An attribute set on the app so it builds its full accessibility tree (Chromium browsers and Firefox; Electron apps) |
| `note` | string | For people reading the file |

`apps-mac.json` holds macOS bundle ids only. Per-app rules for the Windows
client (`apps/desktop-overlay-win`) belong in a file of their own, for
example `apps-win.json` keyed by executable name, documented in this README
when it is added.
