/**
 * What an engine checks and what it contacts (Codex review #11), as the
 * plain sentence the Word pane's Settings shows under "This computer". Built
 * from the engine's own description (`capabilities` in GET /v1/health), so
 * it is true for the server actually running: turn grammar off there and
 * the sentence says so. Pure and unit-tested (tests/unit/capabilities.test.ts).
 */
import type { Capabilities } from "@researchly/contract";

function joined(words: string[]): string {
  if (words.length <= 1) return words.join("");
  return `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}`;
}

function capitalised(s: string): string {
  return s ? s[0]!.toUpperCase() + s.slice(1) : s;
}

/** Null for an engine that does not describe itself (an older local server). */
export function capabilityLine(caps: Capabilities | null | undefined): string | null {
  if (!caps || !Array.isArray(caps.checks)) return null;
  const who = caps.where === "service" ? "Researchly cloud" : "This computer";
  const on = caps.checks.filter((c) => c.on && c.id !== "brief").map((c) => c.label);
  const brief = caps.checks.some((c) => c.on && c.id === "brief");
  let line = on.length > 0 ? `${who} checks ${joined(on)}` : `${who} checks nothing right now`;
  if (brief) line += ", and builds the reviewer’s brief and the map";
  line += ".";
  for (const c of caps.checks) {
    if (!c.on && (c.id === "rules" || c.id === "spelling" || c.id === "grammar")) {
      const verb = c.label.endsWith("s") ? "are" : "is";
      line += ` ${capitalised(c.label)} ${verb} off${c.note ? ` (${c.note})` : ""}.`;
    }
  }
  const contacts = caps.network?.contacts ?? [];
  const sent = contacts.filter((c) => c.sends_text);
  if (caps.where === "service") {
    line += " Your text is analysed in memory and never stored, logged or used for training.";
  } else if (sent.some((c) => c.leaves_computer)) {
    line += ` It sends your text to ${joined(sent.map((c) => c.what))}.`;
  } else if (sent.length > 0) {
    line += ` It sends your text only to ${joined(sent.map((c) => c.what))}, nothing over the network.`;
  } else {
    line += " It sends nothing over the network.";
  }
  if (contacts.some((c) => !c.sends_text)) line += " The first grammar check downloads LanguageTool once; no text is sent.";
  return line;
}
