/**
 * The installable app (PLAN S6, "Installable PWA"; P5): its icons and when
 * the service worker (public/sw.js) is registered.
 *
 * The service worker keeps only the app's own code, icons and the offline
 * page. It never stores document text or anything the engine or Supabase
 * returns (confidential by design, CLAUDE.md #2); tests/unit/pwa.test.ts
 * runs public/sw.js itself to prove it.
 */
import { isWordPath } from "./security";

export const SERVICE_WORKER_URL = "/sw.js";

export interface PwaIcon {
  src: string;
  sizes: string;
  type: "image/png";
  purpose: "any" | "maskable";
}

/** Drawn from app/icon.svg by scripts/make-pwa-icons.mjs; the PNGs are committed. */
export const PWA_ICONS: readonly PwaIcon[] = [
  { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
  { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
  { src: "/icons/maskable-192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
  { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
];

export interface RegisterContext {
  /** A production build (`next build`); `next dev` never registers, so a stale worker never hides a code change. */
  production: boolean;
  pathname: string;
  /** The browser has `navigator.serviceWorker` (Office's webviews and private windows may not). */
  supported: boolean;
  /** The page is inside a frame (Word on the web frames /word). */
  framed: boolean;
}

/**
 * Whether this page registers the service worker. Never in development,
 * never where the browser lacks support, never in a frame, and never on the
 * Word add-in's taskpane (/word): Office's webviews may not support service
 * workers, and the pane has nothing to install.
 */
export function shouldRegisterServiceWorker(ctx: RegisterContext): boolean {
  return ctx.production && ctx.supported && !ctx.framed && !isWordPath(ctx.pathname);
}
