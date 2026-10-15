# apps/web — Researchly web surface (PLAN.md S1, S2, S3)

Paste text at a private URL and get explained, section-aware suggestions.
With accounts configured (S2), sign in by email link to check whole files
(.docx, .tex, Overleaf .zip, .md/.qmd/.Rmd, .txt) and keep muted rules and a
dictionary across devices. Next.js (App Router, TypeScript strict), no UI
kit, no analytics, no third-party scripts or fonts, no cookies.

## Run locally

```bash
cd apps/web
npm install
cp .env.example .env.local        # optional; the default is http://localhost:8080
npm run dev                        # http://localhost:3000
```

You need an engine to check against: `services/engine` on port 8080 (see its
README). Without one the page still works and shows the "could not reach the
checking engine" state.

| Script | What it does |
|---|---|
| `npm run dev` | Dev server on :3000 |
| `npm run build` / `npm start` | Production build / serve on :3000 |
| `npm run lint` | ESLint (Next + a11y rules, no-innerHTML) **and** `scripts/check-boundary.mjs` |
| `npm run typecheck` | `tsc --noEmit` (strict, includes the contract package) |
| `npm test` | Vitest unit tests (`tests/unit`) |
| `npm run test:e2e` | Playwright against two production builds, engine and Supabase mocked: project `chromium` (S1 build, no Supabase, :3100) and project `accounts` (with Supabase, :3101, `e2e/accounts*.spec.ts`) |
| `npm run screenshots` | Design screenshots of every page, light and dark, phone and desktop, Word pane at 320px, with axe logged (`SHOTS_DIR=…` to choose where, `SHOT_PREFIX=…` to name a set) |

Playwright is pinned to 1.56.1 to match the pre-installed Chromium; set
`PLAYWRIGHT_BROWSERS_PATH` if your browsers live elsewhere.

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `NEXT_PUBLIC_ENGINE_URL` | `http://localhost:8080` | Engine base URL. Inlined at **build** time; also in the CSP `connect-src`. A malformed value fails the build. |
| `NEXT_PUBLIC_SUPABASE_URL` | unset | S2 accounts. `https://<ref>.supabase.co` (or `http(s)://localhost:<port>` for a local Supabase). Added to `connect-src` only when both Supabase values are set. Anything else fails the build. |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | unset | `sb_publishable_…`. Public by design (RLS protects the data). A secret key (`sb_secret_…`) fails the build. |

With either Supabase value unset the site is the S1 site: no sign-in UI, no
upload, no `/settings` (404), and supabase-js is never loaded.

### Uploading files in local development, without Supabase

| Variable | Default | Meaning |
|---|---|---|
| `NEXT_PUBLIC_RESEARCHLY_DEV_UPLOAD` | unset | `1`: `npm run dev` offers "Check a file instead" and drop-to-check without accounts. **Ignored by `npm run build`** (the production build inlines `NODE_ENV=production`) and whenever Supabase is configured (`lib/config.ts`, `devUploadEnabled`; tests/unit/config.test.ts, and the e2e S1 build sets it to prove it has no effect). |

Files then go to `POST {engine}/v1/analyze-file` **with no token**. The
engine accepts an anonymous upload only when it runs without accounts
(`services/engine` with `RESEARCHLY_SUPABASE_URL` unset), which is how the
local engine runs; a hosted engine with accounts answers "Sign in to check
files". So:

```bash
# services/engine, no Supabase variables: anonymous uploads allowed
# apps/web:
echo 'NEXT_PUBLIC_RESEARCHLY_DEV_UPLOAD=1' >> .env.local
npm run dev
```

The help line under the upload button says it is a development upload. No
card actions appear (they need an account).

Telemetry is disabled in the npm scripts (`NEXT_TELEMETRY_DISABLED=1`).

## How it talks to the engine

The browser calls `POST ${NEXT_PUBLIC_ENGINE_URL}/v1/analyze` directly, from
`lib/engine.ts` (the only module that sends text). Request and response
types come from the committed contract, `@researchly/contract` →
`../../packages/contract/src` (generated from the engine's OpenAPI; never
hand-copied). `next.config.ts` sets `turbopack.root` to the monorepo root so
the contract compiles as first-party source.

- **Offsets**: the engine's spans are Python string indices (Unicode code
  points); JavaScript strings are UTF-16. `lib/segments.ts` converts them,
  so highlights stay correct after emoji or characters like 𝑅.
- **Errors**: 413/429/400/422/500 and network failures map to plain-language
  messages (`lib/errors.ts`). 500s show the `request_id` to quote. The text
  in the editor is never cleared on failure.
- **Health**: a degraded grammar tier (or any tier in `error`/`unstarted`)
  gets a calm banner with the engine's detail and remedy. The learned `gec`
  tier being absent is normal and not shown.
- **One check at a time** (`lib/check-session.ts`, review proposal 8): every
  check has a sequence number and an AbortController. Cancel aborts it and
  puts the previous results back as current; a newer check supersedes an
  older one; a reply that arrives for a cancelled or superseded check is
  dropped, even when the network ignored the abort. Retry reruns the same
  check (the website resends the same snapshot; Word reads the document
  afresh). `tests/unit/check-session.test.ts` proves it with a mocked fetch
  and a ~120,000-word synthetic document.
- **Rule scopes**: after the first results the page asks `GET /v1/rules`
  once (no text) so the section view knows which rules read the whole
  document (`lib/scope.ts`); without a registry the engine's known
  document-wide ids stand in.
- **Reading summary**: `AnalyzeResponse.reading` is one line under the
  results heading (`lib/reading.ts`).
- **CORS**: the engine must allow this site's origin, and should expose
  `Retry-After` and `X-Request-ID` (`Access-Control-Expose-Headers`).

## The Word add-in's taskpane (`/word`, S3)

Word loads `https://<site>/word` in its sidebar (manifests in
`apps/word-addin/`; owner steps in its README, "Hosted add-in (S3)").

- **Office.js** comes from Microsoft's CDN with a plain script tag
  (`app/word/layout.tsx`), between two tiny same-origin scripts
  (`public/word/office-guard.js`, `office-restore.js`) that keep
  `history.pushState/replaceState` alive, because office.js removes them in
  some hosts and Next.js's router needs them.
- **All Office.js calls** are in `lib/word/office.ts` (read paragraphs with
  style and table flag, find the paragraph the cursor is in for "Check this
  section", find a suggestion by `snippet` + `occurrence`, select, apply). Tests swap in `e2e/fake-office.ts`, which e2e serves at office.js's
  own URL. Before selecting or replacing, the paragraph is re-read and must
  still hold the flagged words at the recorded offsets, Word's search must
  count the snippet as the engine did, and (to apply) the found range's text
  must equal the snippet; otherwise nothing changes and the card says why.
  Tracked changes only with WordApi 1.4: setting `changeTrackingMode` on
  older Word silently fails the whole batch.
- **Engine**: `POST /v1/analyze-word` and `GET /v1/health` from
  `lib/engine.ts`, either to `NEXT_PUBLIC_ENGINE_URL` ("Researchly cloud",
  with the Bearer token when signed in) or to `http://localhost:3517`
  ("This computer": `apps/word-addin/server.py`, no token, but the account's
  muted rules are sent as `disabled_rules`).
- **Sign-in** by an emailed code (`signInWithOtp` then `verifyOtp`, 6 to 10
  digits), inside the pane. Draft/Revise is saved in `user_settings.mode`
  when signed in (migration `20261004120000_s3_mode.sql`), else in
  localStorage with the engine choice (`lib/prefs.ts`).
- **Headers**: `/word` has its own CSP (proxy.ts, `surface: "word"`):
  `script-src` adds `https://appsforoffice.microsoft.com` (and drops
  `'strict-dynamic'`, which would block office.js's parser-inserted
  scripts), `frame-ancestors` lists the Office web origins, `connect-src`
  adds `http://localhost:3517`, and there is no `upgrade-insecure-requests`
  (it would break the local engine). No `X-Frame-Options` on `/word`.
  Every other route's headers are unchanged (tests/unit/security.test.ts,
  e2e/word.spec.ts).

## Install Researchly as an app (S6, P5)

The website is an installable web app (PWA). Nothing changes about how it
checks: text still goes from the page straight to the engine.

- **Chrome or Edge on a computer**: open the site, then the install icon at
  the right of the address bar, or the browser menu, then **Install
  Researchly** (Edge: Apps, then Install this site as an app). It opens in
  its own window and appears with your other apps.
- **Android (Chrome)**: the menu (⋮), then **Add to Home screen** or
  **Install app**.
- **iPhone and iPad (Safari)**: the Share button, then **Add to Home
  Screen**.

How it is built:

- `app/manifest.ts` → `/manifest.webmanifest` (name, `standalone`, start
  URL and scope `/`, colours from the design tokens). Icons in
  `public/icons/` (192 and 512, plain and maskable) and `app/apple-icon.png`
  (180), drawn from `app/icon.svg` by `node scripts/make-pwa-icons.mjs`
  (uses sharp, which Next.js installs); the PNGs are committed.
- **The service worker, `public/sw.js`, never stores document text or any
  reply from the engine or Supabase** (confidential by design). Its rules:
  - same-origin GETs of `/_next/static/*`, `/icons/*`, `/icon.svg`,
    `/offline.html` and `/offline.css`: cache first, stored only when the
    reply is a plain 200 from this site without `no-store`/`private`;
  - navigations to this site's pages: network only, never stored; when the
    network fails, the offline page ("Researchly needs a connection to check
    your writing", with local mode as the way to check offline);
  - everything else is not touched (the worker does not answer, so the
    browser fetches as usual): every POST, the engine, Supabase, any other
    origin, `/word`, the demo manuscript, Next.js data requests, URLs with
    a query.
  - Cache names carry a version (`researchly-shell-v1`,
    `researchly-static-v1`); activate deletes every other Researchly cache.
    Bump `VERSION` in `sw.js` when its rules change.
- **Registered** by `components/ServiceWorker.tsx` only in a production
  build, in a top-level window, never on `/word` (Office's webviews may not
  support service workers; `lib/pwa.ts`). `check-boundary.mjs` allows
  `fetch` only in `lib/engine.ts` and `sw.js`, the Cache Storage API only
  in `sw.js` (and there one `put`, behind `isCacheable()`), and
  registration only in that component.
- **Tests**: `tests/unit/pwa.test.ts` loads `sw.js` as shipped and drives
  its handlers with fake caches and network (no POST, engine, Supabase or
  page reply is ever stored; offline fallback; old caches deleted), and
  checks the manifest, the icon sizes and the offline page's colours.
  `e2e/pwa.spec.ts` registers it in the production build, runs a check, and
  reads every cache entry (same-origin static files only, none holding the
  checked text), shows the offline page with the network off, and proves
  `/word` registers nothing. The other specs block service workers
  (`serviceWorkers: "block"`) so page.route mocks stay in charge.
- The CSP already has `manifest-src 'self'` and `worker-src 'self'`.

## Accounts (S2, docs/s2-design.md §5)

- **Browser only.** supabase-js is loaded by `lib/supabase.ts` alone (a
  dynamic import, `client-only`), with PKCE and `detectSessionInUrl`: the
  email link's code is exchanged in the browser. No route handler, server
  action or cookie is involved; `check-boundary.mjs` refuses supabase-js
  anywhere else and `@supabase/ssr` everywhere.
- **Engine calls** (`lib/engine.ts`) carry `Authorization: Bearer <access
  token>` when signed in. On 401 `unauthorized` the session is refreshed once
  and the call retried once; if it still fails the browser is signed out
  locally and the page says so (never a silent anonymous retry). 401
  `sign_in_required` shows a sign-in prompt in place of results; 503
  `auth_unavailable` is a retryable error.
- **Uploads** go to `POST {engine}/v1/analyze-file` as the raw file
  (`application/octet-stream`), name in `X-Researchly-Filename`
  (`encodeURIComponent`), options in `X-Researchly-Options`. Type and the
  25 MB cap are checked first, for usability only.
- **Muting a rule on an uploaded file** never sends the file again: the
  rule's cards are filtered out in the page at once, the mute is saved
  (`mute_rule`), and Undo (`unmute_rule`) brings them back at once. The
  next check of the file applies the account's mutes in the engine. On
  pasted text the page still checks again after a mute or an undo.
- **Settings** (`/settings`, `lib/account.ts`) read and write
  `user_settings` and `dictionary_words` straight from the browser. Inserts
  rely on the `user_id` default (`auth.uid()`); the only id the client ever
  sends is its own, as a filter on "delete my settings and dictionary".
- **Storage**: besides the format preference (and, in the Word taskpane,
  the engine choice and Draft/Revise), the only stored item is
  supabase-js's session (`sb-<ref>-auth-token`, plus its PKCE verifier while
  a link is pending). Never document text.

## Privacy boundary (ADR-02, ARCHITECTURE.md §5.3)

Document text goes from the browser straight to the engine. **The Next.js
server never receives it.** This is enforced, not just intended:

- No route handlers, API routes or server actions exist. `npm run lint` runs
  `scripts/check-boundary.mjs`, which fails on any of them, on network calls
  outside `lib/engine.ts`, on a proxy that reads request bodies, on
  `sessionStorage`/IndexedDB/cookies, and on any `localStorage` use outside
  `lib/prefs.ts`. The Word taskpane obeys the same rules: document text
  goes from Office.js straight to the chosen engine. `tests/unit/boundary.test.ts` proves the checker catches
  each case.
- `lib/engine.ts` imports `client-only`, so importing it from server code is a
  build error.
- The e2e suite asserts that the only non-GET traffic is to the engine, that
  no cookies are set, and that the only stored item is the format preference.
- Nothing about the document is persisted: no localStorage, sessionStorage
  or IndexedDB in S1. Only the chosen format is remembered (`lib/prefs.ts`).
- Text is rendered as text nodes only. `dangerouslySetInnerHTML`/`innerHTML`
  are lint errors.

## Security headers

- `next.config.ts`: `Referrer-Policy: no-referrer`,
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Cross-Origin-Opener-Policy: same-origin`, a restrictive `Permissions-Policy`.
- `proxy.ts`: a per-request **Content-Security-Policy** with a fresh nonce —
  `script-src 'self' 'nonce-…' 'strict-dynamic'`, `style-src 'self' 'nonce-…'`,
  `connect-src 'self' <engine origin>`, `frame-ancestors 'none'`,
  `object-src 'none'`, `base-uri 'none'`. A nonce is needed because Next.js
  inlines its bootstrap scripts; without one the only alternative is
  `'unsafe-inline'`. As a result every route renders per request
  (`await connection()` in the root layout). Both files take their values
  from `lib/security.ts`.

## Deploy (Vercel)

`vercel.json` pins the function region to `sin1` (D3, Singapore). In the
Vercel project set **Root Directory** to `apps/web`, keep "Include files
outside the root directory" enabled (the contract lives in
`packages/contract`), and set `NEXT_PUBLIC_ENGINE_URL` to the engine's
HTTPS URL for each environment.

## Design

`DESIGN.md` is the design contract (hierarchy, type roles, colour, shape,
required states, what to reject). Check UI changes against it.

## Layout

```
app/            layout (dynamic, for CSP nonces), page (static chrome), globals.css,
                word/ (the Word add-in's taskpane, S3)
components/     Checker (form + state), ReadingKey (idle "how to read the
                feedback" key), Results, DocumentView, SuggestionCard,
                HealthBanner, MetricsPanel, CategoryIcon, RevisionQueue
                (pass chooser + queue, shared with Word), CheckProgress
                (running-check line, shared with Word), ReadingSummary
components/word/ Taskpane, WordCard, CodeSignIn
lib/word/       office (every Office.js call), view (taskpane helpers)
lib/            engine (fetch), segments (offsets + highlight segmentation),
                categories, health, errors, validate, view, prefs, config, security,
                queue (the revision queue's passes and positions),
                check-session (one check at a time; late replies dropped), reading
proxy.ts        CSP nonce
public/         sw.js (service worker), offline.html/.css, icons/ (PWA icons)
scripts/        check-boundary.mjs (confidentiality lint), make-pwa-icons.mjs
tests/unit/     Vitest
e2e/            Playwright specs, typed fixtures (`satisfies AnalyzeResponse`),
                fake-office.ts (Office.js stand-in), word*.spec.ts
```
