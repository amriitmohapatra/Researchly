/**
 * Turning a failed check into something a writer can act on.
 *
 * Contract: every non-2xx body is an ErrorResponse whose `message` never
 * contains document text, so it is safe to show. `request_id` is shown for
 * server faults so a user can quote it when reporting a problem.
 * Whatever happens, the user's text stays in the editor.
 */
import { MAX_CONTENT_CHARS, type ErrorResponse } from "@researchly/contract";

export type CheckErrorKind =
  | "unreachable"
  | "timeout"
  | "too_large"
  | "rate_limited"
  | "invalid"
  | "server"
  | "bad_response";

export interface CheckError {
  kind: CheckErrorKind;
  title: string;
  message: string;
  /** Present when the engine returned one; shown so the user can report it. */
  requestId?: string;
  /** Whether a plain Retry is a sensible next step. */
  retryable: boolean;
}

export function isErrorResponse(body: unknown): body is ErrorResponse {
  if (typeof body !== "object" || body === null) return false;
  const err = (body as { error?: unknown }).error;
  if (typeof err !== "object" || err === null) return false;
  const e = err as Record<string, unknown>;
  return typeof e.code === "string" && typeof e.message === "string" && typeof e.request_id === "string";
}

const fmt = new Intl.NumberFormat("en-GB");

/** Map an HTTP failure from /v1/analyze to a user-facing error. */
export function errorFromResponse(
  status: number,
  body: unknown,
  headers?: { get(name: string): string | null },
): CheckError {
  const parsed = isErrorResponse(body) ? body.error : undefined;
  const requestId = parsed?.request_id || headers?.get("x-request-id") || undefined;

  if (status === 413) {
    return {
      kind: "too_large",
      title: "This text is too long for one check",
      message: `The engine accepts up to ${fmt.format(MAX_CONTENT_CHARS)} characters at a time. Try checking one chapter or section at a time.`,
      requestId,
      retryable: false,
    };
  }
  if (status === 429) {
    const wait = retryAfterSeconds(headers?.get("retry-after") ?? null);
    return {
      kind: "rate_limited",
      title: "Too many checks in a short time",
      message:
        wait !== null
          ? `Please wait about ${wait} second${wait === 1 ? "" : "s"}, then try again. Your text is still here.`
          : "Please wait a moment, then try again. Your text is still here.",
      requestId,
      retryable: true,
    };
  }
  if (status === 400 || status === 422) {
    return {
      kind: "invalid",
      title: "The engine could not read this request",
      message: parsed?.message
        ? `${parsed.message}`
        : "Something about the request was not accepted. Check the format setting and try again.",
      requestId,
      retryable: false,
    };
  }
  if (status >= 500) {
    return {
      kind: "server",
      title: "Something went wrong on our side",
      message:
        "The check did not complete. Your text was not stored. If this keeps happening, please report it and quote the reference below.",
      requestId,
      retryable: true,
    };
  }
  return {
    kind: "bad_response",
    title: "Unexpected response from the engine",
    message: `The engine answered with status ${status}. Your text is still here; try again shortly.`,
    requestId,
    retryable: true,
  };
}

/** The engine's host for the "unreachable" message, or "" if the URL won't parse. */
function engineHost(engineUrl: string): string {
  try {
    return new URL(engineUrl).host;
  } catch {
    return "";
  }
}

/**
 * `engineUrl` is named in the "unreachable" message: when a deployment is
 * built against the wrong engine address, the fetch fails identically to a
 * dropped connection, and the host is the one clue that tells them apart.
 * It is public (the page's security policy already lists it).
 */
export function networkError(timedOut: boolean, engineUrl = ""): CheckError {
  const host = engineHost(engineUrl);
  return timedOut
    ? {
        kind: "timeout",
        title: "The check took too long",
        message: "The engine did not answer in time. Your text is still here. Try again, or check a shorter part.",
        retryable: true,
      }
    : {
        kind: "unreachable",
        title: "Could not reach the checking engine",
        message:
          "Your text is still here and nothing was sent anywhere else. Check your connection and try again." +
          (host ? ` If it keeps failing, the site may be set up with the wrong engine address (tried ${host}).` : ""),
        retryable: true,
      };
}

export function badPayloadError(detail: string): CheckError {
  return {
    kind: "bad_response",
    title: "Unexpected response from the engine",
    message: `${detail} Reloading the page usually fixes this; your text is still here.`,
    retryable: true,
  };
}

/** Parses a Retry-After header (seconds or HTTP date). Returns whole seconds, or null. */
export function retryAfterSeconds(value: string | null, now: number = Date.now()): number | null {
  if (!value) return null;
  const v = value.trim();
  if (/^\d+$/.test(v)) return Math.max(0, Math.min(3600, Number(v)));
  const t = Date.parse(v);
  if (Number.isNaN(t)) return null;
  return Math.max(0, Math.min(3600, Math.ceil((t - now) / 1000)));
}
