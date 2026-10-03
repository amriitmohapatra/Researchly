# apps/web — Researchly web surface (PLAN.md S1)

Paste text at a private URL and get explained, section-aware suggestions.
Next.js (App Router, TypeScript strict), no UI kit, no analytics, no
third-party scripts or fonts, no cookies.

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
| `npm run test:e2e` | Playwright against `next build && next start` on :3100, engine mocked |
| `npm run screenshots` | Design screenshots (`SHOTS_DIR=…` to choose where) |

Playwright is pinned to 1.56.1 to match the pre-installed Chromium; set
`PLAYWRIGHT_BROWSERS_PATH` if your browsers live elsewhere.

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `NEXT_PUBLIC_ENGINE_URL` | `http://localhost:8080` | Engine base URL. Inlined at **build** time; also the only non-self origin in the CSP `connect-src`. A malformed value fails the build. |

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
- **CORS**: the engine must allow this site's origin, and should expose
  `Retry-After` and `X-Request-ID` (`Access-Control-Expose-Headers`).

## Privacy boundary (ADR-02, ARCHITECTURE.md §5.3)

Document text goes from the browser straight to the engine. **The Next.js
server never receives it.** This is enforced, not just intended:

- No route handlers, API routes or server actions exist. `npm run lint` runs
  `scripts/check-boundary.mjs`, which fails on any of them, on network calls
  outside `lib/engine.ts`, on a proxy that reads request bodies, on
  `sessionStorage`/IndexedDB/cookies, and on any `localStorage` use outside
  `lib/prefs.ts`. `tests/unit/boundary.test.ts` proves the checker catches
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
app/            layout (dynamic, for CSP nonces), page (static chrome), globals.css
components/     Checker (form + state), ReadingKey (idle "how to read the
                feedback" key), Results, DocumentView, SuggestionCard,
                HealthBanner, MetricsPanel, CategoryIcon
lib/            engine (fetch), segments (offsets + highlight segmentation),
                categories, health, errors, validate, view, prefs, config, security
proxy.ts        CSP nonce
scripts/        check-boundary.mjs (confidentiality lint)
tests/unit/     Vitest
e2e/            Playwright specs, typed fixtures (`satisfies AnalyzeResponse`)
```
