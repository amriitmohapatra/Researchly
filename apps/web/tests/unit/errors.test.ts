import { describe, expect, it } from "vitest";
import { errorFromResponse, isErrorResponse, networkError, retryAfterSeconds } from "@/lib/errors";

const body = (code: string, message = "msg", request_id = "req-123") => ({ error: { code, message, request_id } });
const headers = (h: Record<string, string>) => ({ get: (k: string) => h[k.toLowerCase()] ?? null });

describe("error mapping", () => {
  it("recognises the contract's ErrorResponse shape", () => {
    expect(isErrorResponse(body("internal"))).toBe(true);
    expect(isErrorResponse({ error: { code: "x", message: "y" } })).toBe(false);
    expect(isErrorResponse({ detail: [] })).toBe(false);
    expect(isErrorResponse(null)).toBe(false);
  });

  it("413 explains the limit and is not retryable", () => {
    const e = errorFromResponse(413, body("payload_too_large"));
    expect(e.kind).toBe("too_large");
    expect(e.message).toContain("1,000,000");
    expect(e.retryable).toBe(false);
  });

  it("429 asks the user to slow down, using Retry-After when present", () => {
    const e = errorFromResponse(429, body("rate_limited"), headers({ "retry-after": "12" }));
    expect(e.kind).toBe("rate_limited");
    expect(e.message).toContain("12 seconds");
    expect(e.retryable).toBe(true);
    expect(errorFromResponse(429, null).message).toMatch(/wait a moment/);
  });

  it("400 and 422 show the engine's (text-free) message", () => {
    expect(errorFromResponse(422, body("invalid_request", "format must be one of plain, markdown, latex")).message).toBe(
      "format must be one of plain, markdown, latex",
    );
    expect(errorFromResponse(400, null).kind).toBe("invalid");
  });

  it("500 carries the request id so the user can report it", () => {
    const e = errorFromResponse(500, body("internal", "boom", "req-abc"));
    expect(e.kind).toBe("server");
    expect(e.requestId).toBe("req-abc");
    expect(e.retryable).toBe(true);
  });

  it("takes the request id from a header when the body has none", () => {
    expect(errorFromResponse(503, "<html>", headers({ "x-request-id": "hdr-1" })).requestId).toBe("hdr-1");
  });

  it("maps other statuses to an unexpected-response error", () => {
    expect(errorFromResponse(404, null).kind).toBe("bad_response");
  });

  it("network failures keep the user's text and offer retry", () => {
    const e = networkError(false);
    expect(e.kind).toBe("unreachable");
    expect(e.message).toMatch(/still here/);
    expect(e.retryable).toBe(true);
    expect(networkError(true).kind).toBe("timeout");
  });

  it("an unreachable engine is named by host, so a wrong deploy-time address is diagnosable", () => {
    // Regression: the first live deploy was built against a stale engine URL
    // and the page gave no clue which address it had tried.
    const e = networkError(false, "https://researchly-engine-1.asia-southeast1.run.app");
    expect(e.message).toContain("tried researchly-engine-1.asia-southeast1.run.app");
    expect(networkError(false, "not a url").message).not.toMatch(/tried/);
    expect(networkError(false).message).not.toMatch(/tried/);
  });

  it("never echoes document text: messages come only from the engine's message field or fixed copy", () => {
    const secret = "CANARY-7f3a my unpublished finding";
    const e = errorFromResponse(500, { error: { code: "internal", message: "Engine error", request_id: "r" }, content: secret });
    expect(JSON.stringify(e)).not.toContain("CANARY");
  });
});

describe("retryAfterSeconds", () => {
  it("parses delta-seconds", () => {
    expect(retryAfterSeconds("30")).toBe(30);
    expect(retryAfterSeconds(" 5 ")).toBe(5);
  });
  it("parses an HTTP date", () => {
    const now = Date.parse("2026-10-03T10:00:00Z");
    expect(retryAfterSeconds("Sat, 03 Oct 2026 10:00:20 GMT", now)).toBe(20);
  });
  it("caps absurd values and rejects garbage", () => {
    expect(retryAfterSeconds("999999")).toBe(3600);
    expect(retryAfterSeconds("soon")).toBeNull();
    expect(retryAfterSeconds(null)).toBeNull();
  });
});
