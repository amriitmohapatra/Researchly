"use client";

import { useEffect } from "react";
import { SERVICE_WORKER_URL, shouldRegisterServiceWorker } from "@/lib/pwa";

/**
 * Registers the service worker (public/sw.js) once the page has loaded, in a
 * production build and outside the Word taskpane (lib/pwa.ts). It renders
 * nothing. A failure is ignored: the site works the same without it, only
 * without the offline page.
 */
export function ServiceWorker() {
  useEffect(() => {
    let framed = true;
    try {
      framed = window.self !== window.top;
    } catch {
      framed = true; // a cross-origin parent: framed
    }
    const ok = shouldRegisterServiceWorker({
      production: process.env.NODE_ENV === "production",
      pathname: window.location.pathname,
      supported: "serviceWorker" in navigator,
      framed,
    });
    if (!ok) return;
    navigator.serviceWorker.register(SERVICE_WORKER_URL, { scope: "/", updateViaCache: "none" }).catch(() => undefined);
  }, []);
  return null;
}
