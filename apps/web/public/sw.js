/*
 * Researchly's service worker (PLAN S6, "Installable PWA"; P5).
 *
 * Confidential by design (CLAUDE.md #2, ADR-02): this worker NEVER stores
 * document text or anything the engine or Supabase returns. It keeps only
 * the app's own code and pictures:
 *
 *   - "static": same-origin GETs of /_next/static/* (content-hashed code and
 *     styles), /icons/*, /icon.svg and the offline page with its stylesheet.
 *     Cache first; stored only when the reply is a plain 200 from this site.
 *   - "page": navigations to this site's pages (not /word). Network only,
 *     never stored; when the network fails, the offline page is shown.
 *   - "network": everything else, untouched (the worker does not answer, so
 *     the browser fetches as if there were no worker): every POST, every
 *     other origin (the engine, Supabase), the Word taskpane, the demo
 *     manuscript, Next.js's data requests, the manifest.
 *
 * Cache names carry VERSION; activate deletes every other Researchly cache.
 * Registered only by production builds, never on /word (lib/pwa.ts).
 * tests/unit/pwa.test.ts loads this file and drives its handlers.
 */
"use strict";

const VERSION = "v1";
const CACHE_PREFIX = "researchly-";
const SHELL_CACHE = `${CACHE_PREFIX}shell-${VERSION}`;
const STATIC_CACHE = `${CACHE_PREFIX}static-${VERSION}`;
const OFFLINE_URL = "/offline.html";
/** Fetched on install, so the offline page works the first time the network is gone. */
const PRECACHE = [OFFLINE_URL, "/offline.css", "/icon.svg", "/icons/icon-192.png", "/icons/icon-512.png"];
/** Old builds' code is never needed again: keep the static cache to this many entries. */
const STATIC_LIMIT = 200;

/** Which of the three ways a request is handled. Pure: decided from the method, URL and mode alone. */
function route(request, origin) {
  if (request.method !== "GET") return "network";
  let url;
  try {
    url = new URL(request.url);
  } catch {
    return "network";
  }
  if (url.origin !== origin) return "network";
  const p = url.pathname;
  if (p === "/word" || p.startsWith("/word/")) return "network";
  if (request.mode === "navigate") return "page";
  if (url.search) return "network";
  if (p.startsWith("/_next/static/") || p.startsWith("/icons/") || PRECACHE.includes(p)) return "static";
  return "network";
}

/** Whether a reply may be stored: a static route's plain, complete 200 from this site, never marked no-store. */
function isCacheable(request, response, origin) {
  if (route(request, origin) !== "static") return false;
  if (!response || response.status !== 200 || response.type !== "basic") return false;
  const cc = (response.headers && response.headers.get("cache-control")) || "";
  return !/no-store|private/i.test(cc);
}

async function trim(cache) {
  const keys = await cache.keys();
  for (let i = 0; i < keys.length - STATIC_LIMIT; i += 1) await cache.delete(keys[i]);
}

async function fromStatic(request, origin) {
  const hit = await caches.match(request);
  if (hit) return hit;
  const response = await fetch(request);
  if (isCacheable(request, response, origin)) {
    const copy = response.clone();
    const cache = await caches.open(STATIC_CACHE);
    await cache.put(request, copy);
    await trim(cache);
  }
  return response;
}

async function page(request) {
  try {
    return await fetch(request);
  } catch (err) {
    const offline = await caches.match(OFFLINE_URL);
    if (offline) return offline;
    throw err;
  }
}

function install(event, scope) {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => scope.skipWaiting()),
  );
}

function activate(event, scope) {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names
            .filter((n) => n.startsWith(CACHE_PREFIX) && n !== SHELL_CACHE && n !== STATIC_CACHE)
            .map((n) => caches.delete(n)),
        ),
      )
      .then(() => scope.clients.claim()),
  );
}

function onFetch(event, origin) {
  const how = route(event.request, origin);
  // "network": no answer from the worker; the browser fetches as usual and nothing is kept.
  if (how === "static") event.respondWith(fromStatic(event.request, origin));
  else if (how === "page") event.respondWith(page(event.request));
}

if (typeof module === "object" && module.exports) {
  // Unit tests (tests/unit/pwa.test.ts) only; a browser has no `module`.
  module.exports = { VERSION, SHELL_CACHE, STATIC_CACHE, OFFLINE_URL, PRECACHE, route, isCacheable, install, activate, onFetch };
} else {
  const origin = self.location.origin;
  self.addEventListener("install", (event) => install(event, self));
  self.addEventListener("activate", (event) => activate(event, self));
  self.addEventListener("fetch", (event) => onFetch(event, origin));
}
