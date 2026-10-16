"""Shared pieces of the Laya harness (PLAN S5b; ARCHITECTURE.md ADR-06).

No torch here, so the metrics, data readers and question mapping are
tested in CI without weights. The Laya runtime is imported only by
``load_agent``.

- Questions come from the engine (``researchly.critics``), so a model is
  trained and evaluated on exactly the wording the engine will ask.
- Laya reads a question as ``{"type": "choice", "instructions", "criteria"}``.
  Yes/no questions are asked as a two-option ``choice`` with neutral keys
  A/B, not as Laya's ``noul``: Laya's own README reports that ``noul`` on
  the English checkpoint can follow its option labels instead of the state
  (issue #156) and recommends this form.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "packages" / "core"))
sys.path.insert(0, str(REPO / "ml" / "corpus"))
sys.path.insert(0, str(REPO / "ml" / "eval"))

from researchly import critics  # noqa: E402

BASELINE_TASK_B = 0.826          # TF-IDF + LR on PubMed 20k RCT (move-clf-v0)
PRECISION_GATE = 0.85            # ADR-06 / Q4
LAYA_REPO = "convaiinnovations/laya"
LAYA_REVISION = "7b928d828b7b0e022f929d9bd2e44165aa270148"   # pinned 2026-10-15

YES_NO_KEYS = ("A", "B")         # A = yes, B = no


def laya_question(q: "critics.Question") -> dict:
    """An engine Question as Laya's typed-question dict."""
    if q.type == "yes_no":
        return {"type": "choice", "instructions": q.text,
                "criteria": {"A": "yes: " + q.options["yes"],
                             "B": "no: " + q.options["no"]}}
    return {"type": "choice" if q.type == "choice" else "score",
            "instructions": q.text,
            "criteria": dict(q.options) if q.type == "choice"
            else list(q.options.values())}


def from_laya(q: "critics.Question", probabilities: dict) -> dict:
    """Laya's probabilities keyed back to the engine question's options."""
    if q.type == "yes_no":
        return {"yes": float(probabilities.get("A", 0.0)),
                "no": float(probabilities.get("B", 0.0))}
    return {k: float(probabilities.get(k, 0.0)) for k in q.options}


def rotations(question: dict) -> dict:
    """The question under every cyclic option order (Laya's README: average
    them to cancel the position bias of the sequential checkpoints)."""
    k = len(question["criteria"])
    return {f"r{r}": dict(question, option_order=[(i + r) % k for i in range(k)])
            for r in range(k)}


def average(answers: dict) -> dict:
    tot: dict = defaultdict(float)
    for a in answers.values():
        for label, p in a["probabilities"].items():
            tot[label] += p / len(answers)
    return dict(tot)


# --- states -------------------------------------------------------------------------

def role_state(row: dict, context: str = "position") -> str:
    """Task B input. ``position`` adds where the sentence sits in its
    abstract, a cue any reader has; ``none`` is the sentence alone."""
    if context == "none":
        return row["text"]
    return (f"Sentence {row['position'] + 1} of {row['n']} in a research "
            f"abstract: {row['text']}")


def flag_state(section: str, paragraph: str, span: str, message: str,
               prior: Optional[str] = None) -> str:
    """Task A input: the paragraph, the flagged words and the card."""
    s = (f"Section: {section}\nParagraph: {paragraph}\n"
         f"Flagged words: \"{span}\"\nThe card says: {message}")
    if prior:
        s += f"\n{prior}"
    return s


# --- data ---------------------------------------------------------------------------

def read_jsonl(path: Path) -> list:
    return [json.loads(line) for line in
            Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def sample_roles(rows: list, n: int, seed: int = 20261015,
                 split: str = "test", use: Optional[str] = None) -> list:
    """A deterministic sample of up to ``n`` sentences from one split,
    whole abstracts at a time (so position context stays meaningful)."""
    import random
    pick = [r for r in rows if r["split"] == split
            and (use is None or r["use"] == use)]
    by_article: dict = defaultdict(list)
    for r in pick:
        by_article[r["pmcid"]].append(r)
    ids = sorted(by_article)
    random.Random(seed).shuffle(ids)
    out: list = []
    for pid in ids:
        if len(out) >= n:
            break
        out.extend(by_article[pid])
    return out[:n]


def label_paragraphs(path: Path) -> dict:
    """The owner's paragraphs file (local only, never committed):
    {"version": 1, "paragraphs": [{"paragraph": 1, "section": "methods",
    "text": "..."}]} -> {paragraph number: {section, text}}."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {}
    for p in data.get("paragraphs", []):
        if not isinstance(p.get("paragraph"), int) or \
                not isinstance(p.get("text"), str):
            raise ValueError("paragraph rows need an int 'paragraph' and "
                             "a 'text'")
        out[p["paragraph"]] = {"section": p.get("section", "introduction"),
                               "text": p["text"]}
    return out


SECTION_LABELS = {"introduction": "Introduction", "methods": "Methods",
                  "results": "Results", "discussion": "Discussion",
                  "abstract": "Abstract", "conclusion": "Conclusion"}
CATEGORY_ORDER = ("correction", "improvement", "convention", "preference")


def label_page_flags(section: str, paragraph: str, nlp=None) -> tuple:
    """The flags the website's Label page shows for this paragraph, in its
    order (apps/web LabelStudio: the paragraph under its section heading,
    preferences hidden, sorted by start then category). Returns
    (content, flags) where each flag is (rule_id, category, start, end,
    message) in content offsets."""
    from researchly import api
    content = f"{SECTION_LABELS.get(section, 'Introduction')}\n\n{paragraph.strip()}\n"
    a = api.analyze(content, kind="plain", nlp=nlp or api.get_nlp(),
                    with_metrics=False, mode="revise")
    shown = [s for s in a.suggestions
             if getattr(s.category, "value", s.category) != "preference"]
    shown.sort(key=lambda s: (s.start, CATEGORY_ORDER.index(
        getattr(s.category, "value", s.category))))
    return content, [(s.rule_id, getattr(s.category, "value", s.category),
                      s.start, s.end, s.message) for s in shown]


def telemetry_priors(path: Path) -> dict:
    """Per (rule, section) acceptance from the local, text-free telemetry
    log (~/.researchly/telemetry.jsonl): applied vs dismissed. These logs
    hold no text, so on their own they cannot train Task A; they become a
    one-line prior in the state."""
    acc: dict = defaultdict(lambda: [0, 0])
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        key = (e.get("rule"), e.get("section", "unknown"))
        if e.get("event") == "applied":
            acc[key][0] += int(e.get("n", 1))
        elif e.get("event") == "dismissed":
            acc[key][1] += int(e.get("n", 1))
    return {k: (a, d) for k, (a, d) in acc.items() if a + d}


def prior_text(priors: dict, rule: str, section: str) -> Optional[str]:
    a_d = priors.get((rule, section)) or priors.get((rule, "unknown"))
    if not a_d:
        return None
    a, d = a_d
    return f"Writers applied {a} and dismissed {d} of this rule's flags."


# --- metrics --------------------------------------------------------------------------

def ece(conf: list, correct: list, bins: int = 15) -> float:
    """Expected calibration error, equal-width bins on the top-1 confidence."""
    n = len(conf)
    if n == 0:
        return float("nan")
    tot = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, c in enumerate(conf)
               if (lo < c <= hi) or (b == 0 and c == 0.0)]
        if idx:
            acc = sum(correct[i] for i in idx) / len(idx)
            avg = sum(conf[i] for i in idx) / len(idx)
            tot += len(idx) / n * abs(acc - avg)
    return tot


def risk_coverage(conf: list, correct: list,
                  coverages=(1.0, 0.8, 0.6, 0.4, 0.2)) -> dict:
    """Precision (accuracy of the answers kept) when only the most confident
    fraction is answered; plus the largest coverage reaching the gate."""
    order = sorted(range(len(conf)), key=lambda i: -conf[i])
    out = {}
    for c in coverages:
        k = max(1, int(round(c * len(order))))
        kept = order[:k]
        out[f"{c:.1f}"] = {
            "precision": sum(correct[i] for i in kept) / k,
            "threshold": conf[kept[-1]], "n": k}
    best = None
    hits = 0
    for j, i in enumerate(order, 1):
        hits += correct[i]
        if j < len(order) and conf[order[j]] == conf[i]:
            continue        # a threshold keeps every tied answer, not some
        if hits / j >= PRECISION_GATE and j >= 20:
            best = {"coverage": j / len(order), "threshold": conf[i], "n": j}
    out["coverage_at_gate"] = best or {"coverage": 0.0, "threshold": None,
                                       "n": 0}
    return out


def temper(probs: dict, t: float) -> dict:
    """Temperature-scale a distribution given only its probabilities:
    p_i^(1/t), renormalised (equivalent to dividing the logits by t)."""
    logs = {k: math.log(max(v, 1e-12)) / t for k, v in probs.items()}
    m = max(logs.values())
    ex = {k: math.exp(v - m) for k, v in logs.items()}
    s = sum(ex.values())
    return {k: v / s for k, v in ex.items()}


def fit_temperature(dists: list, gold: list) -> float:
    """The temperature minimising NLL on held-out (dev) answers."""
    best_t, best = 1.0, float("inf")
    for i in range(1, 101):
        t = 0.25 + i * 0.05
        nll = -sum(math.log(max(temper(d, t)[g], 1e-12))
                   for d, g in zip(dists, gold)) / max(1, len(gold))
        if nll < best:
            best_t, best = t, nll
    return best_t


def summarise(dists: list, gold: list, groups: Optional[list] = None) -> dict:
    """Accuracy, macro-F1, ECE, risk-coverage and per-group accuracy."""
    pred = [max(d, key=d.get) for d in dists]
    conf = [d[p] for d, p in zip(dists, pred)]
    correct = [int(p == g) for p, g in zip(pred, gold)]
    labels = sorted(set(gold) | set(pred))
    f1s = []
    for lab in labels:
        tp = sum(p == lab and g == lab for p, g in zip(pred, gold))
        fp = sum(p == lab and g != lab for p, g in zip(pred, gold))
        fn = sum(p != lab and g == lab for p, g in zip(pred, gold))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    out = {"n": len(gold),
           "accuracy": sum(correct) / len(gold) if gold else float("nan"),
           "macro_f1": sum(f1s) / len(f1s) if f1s else float("nan"),
           "ece": ece(conf, correct),
           "mean_confidence": sum(conf) / len(conf) if conf else float("nan"),
           "risk_coverage": risk_coverage(conf, correct),
           "predicted": dict(Counter(pred)), "gold": dict(Counter(gold))}
    if groups:
        g_acc: dict = defaultdict(lambda: [0, 0])
        for g, c in zip(groups, correct):
            g_acc[g][0] += c
            g_acc[g][1] += 1
        out["by_group"] = {g: {"accuracy": a / n, "n": n}
                           for g, (a, n) in sorted(g_acc.items())}
    return out


def items(dists: list, gold: list, groups: list) -> list:
    """Per-item results without text (gate.py reads them): the answer, its
    confidence, whether it was right, the gold label and a group."""
    out = []
    for d, g, grp in zip(dists, gold, groups):
        ans = max(d, key=d.get)
        out.append({"answer": ans, "confidence": round(d[ans], 6),
                    "correct": int(ans == g), "gold": g, "group": grp})
    return out


def latency_summary(seconds: list) -> dict:
    s = sorted(seconds)
    if not s:
        return {}

    def q(p):
        return s[min(len(s) - 1, int(p * len(s)))]
    return {"n": len(s), "mean_s": sum(s) / len(s), "p50_s": q(0.5),
            "p95_s": q(0.95)}


# --- the runtime ------------------------------------------------------------------------

def load_agent(model: str = LAYA_REPO, revision: str = LAYA_REVISION,
               device: str = "cpu", threads: Optional[int] = None):
    """A Laya Agent pinned to a revision (or a local checkpoint folder).
    Imports torch and laya; only the scripts call this."""
    os.environ.setdefault("USE_TF", "0")
    import torch
    if threads:
        torch.set_num_threads(threads)
    import laya
    if Path(model).exists():
        return laya.load(str(model), device=device)
    return laya.load(model, revision=revision, device=device)


def timed(fn, *a, **k):
    t = time.perf_counter()
    r = fn(*a, **k)
    return r, time.perf_counter() - t
