"""HTML rendering for the desktop floating panel.

Pure Python, no AppKit — fully unit-testable off-Mac. The panel is a
WKWebView showing this HTML (display only; actions are native buttons, so
no JS bridge is needed — expandable "why" sections use <details>, which
needs no JavaScript).
"""

from __future__ import annotations

import html as _html

CATEGORY_COLORS = {
    "correction": "#c0392b",
    "improvement": "#2563ab",
    "convention": "#a06a00",
    "preference": "#7d3f98",
}

_BASE_CSS = """
body { font-family: -apple-system, 'Helvetica Neue', sans-serif;
  font-size: 13px; color: #1d2733; margin: 0; padding: 12px 14px;
  background: #fafbfd; }
h2 { font-size: 14px; margin: 0 0 2px; }
.sub { color: #6b7686; font-size: 11px; margin-bottom: 10px; }
.chips { margin: 6px 0 12px; }
.chip { display: inline-block; padding: 2px 9px; border-radius: 999px;
  font-size: 11px; color: #fff; font-weight: 600; margin-right: 4px; }
.card { background: #fff; border: 1px solid #e3e7ee; border-left: 3px solid
  #6b7686; border-radius: 8px; padding: 8px 11px; margin-bottom: 8px; }
.tag { font-size: 10px; font-weight: 700; letter-spacing: .4px;
  text-transform: uppercase; }
.section-tag { float: right; font-size: 10px; color: #6b7686;
  font-weight: 400; text-transform: none; }
.flagged { font-family: Georgia, serif; background: #f4f6fa;
  border-radius: 4px; padding: 4px 7px; margin: 6px 0; font-size: 12.5px; }
.msg { margin: 4px 0 2px; }
.fix { font-size: 12px; color: #1c7c3c; margin: 2px 0; }
details { margin-top: 5px; }
summary { font-size: 11px; color: #6b7686; cursor: pointer; }
.why { color: #6b7686; font-size: 11.5px; line-height: 1.45;
  padding: 6px 0 2px; }
.metrics { border-top: 1px solid #e3e7ee; margin-top: 12px; padding-top: 8px;
  font-size: 11px; color: #6b7686; }
.empty { text-align: center; color: #6b7686; padding: 30px 12px; }
.polish-diff { font-family: Georgia, serif; font-size: 13px;
  line-height: 1.6; background: #f4f6fa; border-radius: 6px;
  padding: 10px 12px; margin-bottom: 10px; white-space: pre-wrap; }
del { color: #b3392b; background: #fbe9e7; }
ins { color: #1c7c3c; background: #e8f4ec; text-decoration: none; }
.edit-line { font-size: 11.5px; color: #6b7686; margin: 3px 0; }
.edit-line b { color: #1d2733; }
.note { font-size: 11px; color: #6b7686; margin-top: 8px; }
.tiers { background: #fff8e6; border: 1px solid #f0dca8; border-radius: 6px;
  padding: 7px 10px; margin-bottom: 10px; font-size: 11.5px;
  color: #6b4e00; }
.tier-row { margin: 2px 0; }
.tiers code { font-family: 'SF Mono', Menlo, monospace; font-size: 11px;
  background: #fff; border: 1px solid #f0dca8; border-radius: 3px;
  padding: 1px 4px; }
"""


def esc(t: str) -> str:
    return _html.escape(t or "", quote=True)


def _page(body: str) -> str:
    return (f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<style>{_BASE_CSS}</style></head><body>{body}</body></html>")


def _truncate(t: str, n: int = 180) -> str:
    t = " ".join((t or "").split())
    return t if len(t) <= n else t[: n - 1] + "…"


def render_tiers(health) -> str:
    """One line naming any checking tier that is NOT running.

    Silence used to mean either "your prose is clean" or "the grammar engine
    never started" with no way to tell them apart. Say which.
    """
    if not health:
        return ""
    items = [t.to_dict() if hasattr(t, "to_dict") else t for t in health]
    down = [t for t in items
            if not t.get("ok") and (t.get("remedy")
                                    or t.get("state") in ("disabled", "error"))]
    if not down:
        return ""
    rows = "".join(
        f"<div class='tier-row'><b>{esc(t['label'])} is off</b> — "
        f"{esc(t.get('detail', ''))}"
        + (f"<br><code>{esc(t['remedy'])}</code>" if t.get("remedy") else "")
        + "</div>" for t in down)
    return f"<div class='tiers'>{rows}</div>"


def render_check(suggestions, metrics=None, hidden_prefs: int = 0,
                 source_app: str = "", health=None) -> str:
    """suggestions: list of engine Suggestion objects (or dicts)."""
    items = [s.to_dict() if hasattr(s, "to_dict") else s for s in suggestions]
    tiers = render_tiers(health)

    counts: dict[str, int] = {}
    for s in items:
        counts[s["category"]] = counts.get(s["category"], 0) + 1
    chips = "".join(
        f"<span class='chip' style='background:{CATEGORY_COLORS[c]}'>"
        f"{n} {c}{'s' if n != 1 else ''}</span>"
        for c, n in counts.items())

    src = f" — from {esc(source_app)}" if source_app else ""
    head = (f"<h2>Researchly</h2><div class='sub'>checked selection{src}"
            + (f" · {hidden_prefs} preference notes hidden" if hidden_prefs
               else "") + "</div>")

    if not items:
        body = head + tiers + ("<div class='empty'>Nothing to flag in this "
                               "selection.<br><span style='font-size:11px'>"
                               "(section-aware rules need headings; a bare "
                               "snippet is checked as section-unknown)"
                               "</span></div>")
        return _page(body)

    cards = []
    for s in items:
        color = CATEGORY_COLORS.get(s["category"], "#6b7686")
        sec = (f"<span class='section-tag'>§{esc(s['section'])}</span>"
               if s.get("section") and s["section"] != "unknown" else "")
        fix = (f"<div class='fix'>fix: ‘{esc(s['replacement'])}’</div>"
               if s.get("replacement") else "")
        why = s.get("why", "")
        why_html = (f"<details><summary>Why?</summary>"
                    f"<div class='why'>{esc(why)}</div></details>"
                    if why else "")
        cards.append(
            f"<div class='card' style='border-left-color:{color}'>"
            f"<span class='tag' style='color:{color}'>{esc(s['category'])}"
            f" · {esc(s['rule_id'])} {esc(s['rule_name'])}</span>{sec}"
            f"<div class='flagged'>{esc(_truncate(s.get('text', '')))}</div>"
            f"<div class='msg'>{esc(s['message'])}</div>{fix}{why_html}"
            f"</div>")

    mets = ""
    if metrics:
        d = metrics.to_dict() if hasattr(metrics, "to_dict") else metrics
        balance = d.get("hedge_booster_balance", "")
        mets = (f"<div class='metrics'>{d['sentences']} sentences · mean "
                f"{d['mean_sentence_len']} words · nominalizations "
                f"{d['nominalizations_per_100w']}/100w · hedges "
                f"{d['hedges_per_100w']}/100w · boosters "
                f"{d.get('boosters_per_100w', '?')}/100w"
                + (f"<br>calibration: {esc(balance)}" if balance else "")
                + "<br><i>a read-out, not a score</i></div>")

    return _page(head + tiers + f"<div class='chips'>{chips}</div>"
                 + "".join(cards) + mets)


def render_polish(result, source_app: str = "") -> str:
    """result: transform.PolishResult (or its to_dict())."""
    d = result.to_dict() if hasattr(result, "to_dict") else result
    src = f" — from {esc(source_app)}" if source_app else ""
    head = (f"<h2>Researchly Polish</h2><div class='sub'>rule-composed "
            f"rewrite{src} · every change traceable, no AI generation</div>")

    if not d["changed"]:
        notes = d.get("notes") or []
        extra = ""
        if notes:
            lis = "".join(f"<div class='edit-line'>{esc(n)}</div>"
                          for n in notes[:5])
            extra = (f"<div class='note'>Left for your judgement:</div>{lis}")
        return _page(head + "<div class='empty'>Nothing to safely rewrite "
                     "here — the composable edits all check out.</div>"
                     + extra)

    segs = []
    for seg in d["segments"]:
        t = esc(seg["text"])
        if seg["op"] == "del":
            segs.append(f"<del>{t}</del>")
        elif seg["op"] == "ins":
            segs.append(f"<ins>{t}</ins>")
        else:
            segs.append(t)
    diff = f"<div class='polish-diff'>{''.join(segs)}</div>"

    edits = "".join(
        f"<div class='edit-line'><b>{esc(e['rule_id'])}</b> "
        f"{esc(e['rule_name'])}: “{esc(e['before'])}” → "
        f"“{esc(e['after'])}”</div>"
        for e in d["edits"])

    note = ""
    if d.get("notes"):
        note = (f"<div class='note'>+ {len(d['notes'])} judgement-call "
                f"flag{'s' if len(d['notes']) != 1 else ''} left alone "
                f"(run Check to see them)</div>")

    return _page(head + diff + edits + note
                 + "<div class='note'>Use the buttons below to replace the "
                   "selection or copy the rewrite.</div>")


def render_message(title: str, message: str) -> str:
    return _page(f"<h2>{esc(title)}</h2>"
                 f"<div class='empty'>{esc(message)}</div>")
