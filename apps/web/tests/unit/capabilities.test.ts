/**
 * "This computer: checks X, Y; sends nothing over the network" (Codex
 * review #11): the Word pane's Settings line, from the local server's own
 * description in GET /v1/health.
 */
import { describe, expect, it } from "vitest";
import type { Capabilities, CapabilityCheck } from "@researchly/contract";
import { capabilityLine } from "@/lib/capabilities";

const check = (id: CapabilityCheck["id"], label: string, on = true, note = ""): CapabilityCheck => ({ id, label, on, note });

const LOCAL: Capabilities = {
  route: "local_server",
  label: "This computer (Word and the desktop overlays)",
  where: "this_computer",
  checks: [
    check("rules", "writing rules"),
    check("spelling", "spelling"),
    check("grammar", "grammar"),
    check("document", "whole-document checks"),
    check("brief", "the reviewer’s brief and the map"),
  ],
  network: { sends_text: false, contacts: [] },
  summary: "(the engine’s own line, for the command line)",
};

describe("capabilityLine", () => {
  it("says what this computer checks and that nothing goes over the network", () => {
    expect(capabilityLine(LOCAL)).toBe(
      "This computer checks writing rules, spelling, grammar and whole-document checks, and builds the reviewer’s brief and the map. It sends nothing over the network.",
    );
  });

  it("says grammar is off, and why, when the server runs without it", () => {
    const caps = { ...LOCAL, checks: LOCAL.checks.map((c) => (c.id === "grammar" ? { ...c, on: false, note: "turned off in settings" } : c)) };
    expect(capabilityLine(caps)).toBe(
      "This computer checks writing rules, spelling and whole-document checks, and builds the reviewer’s brief and the map. Grammar is off (turned off in settings). It sends nothing over the network.",
    );
  });

  it("says where the text goes when grammar uses a server", () => {
    const away = {
      ...LOCAL,
      network: { sends_text: true, contacts: [{ what: "the grammar server at lt.example.org:8010", when: "every check", sends_text: true, leaves_computer: true }] },
    };
    expect(capabilityLine(away)).toContain("It sends your text to the grammar server at lt.example.org:8010.");
    const here = {
      ...LOCAL,
      network: { sends_text: false, contacts: [{ what: "a grammar server on this computer (localhost:8010)", when: "every check", sends_text: true, leaves_computer: false }] },
    };
    expect(capabilityLine(here)).toContain("only to a grammar server on this computer (localhost:8010), nothing over the network.");
  });

  it("mentions LanguageTool’s one-time download, which sends no text", () => {
    const first = {
      ...LOCAL,
      network: { sends_text: false, contacts: [{ what: "LanguageTool’s download site", when: "once", sends_text: false, leaves_computer: true }] },
    };
    expect(capabilityLine(first)).toMatch(/It sends nothing over the network\. The first grammar check downloads LanguageTool once; no text is sent\.$/);
  });

  it("is plural-aware and says nothing for an older server", () => {
    const noRules = { ...LOCAL, checks: [check("rules", "writing rules", false, "not installed")] };
    expect(capabilityLine(noRules)).toContain("Writing rules are off (not installed).");
    expect(capabilityLine(null)).toBeNull();
    expect(capabilityLine(undefined)).toBeNull();
  });
});
