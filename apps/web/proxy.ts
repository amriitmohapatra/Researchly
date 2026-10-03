/**
 * Sets a per-request Content-Security-Policy with a fresh nonce.
 *
 * This proxy only reads the URL and headers. It never reads a request body,
 * and document text never comes here anyway: the browser sends it straight
 * to the engine (ADR-02). scripts/check-boundary.mjs enforces both.
 */
import { NextResponse, type NextRequest } from "next/server";
import { cspHeader, makeNonce } from "./lib/security";

export function proxy(request: NextRequest) {
  const nonce = makeNonce();
  const csp = cspHeader({
    nonce,
    engineUrl: process.env.NEXT_PUBLIC_ENGINE_URL,
    dev: process.env.NODE_ENV === "development",
  });
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);
  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  matcher: [
    {
      source: "/((?!_next/static|_next/image|favicon.ico|icon.svg).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
