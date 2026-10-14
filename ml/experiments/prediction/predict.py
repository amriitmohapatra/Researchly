"""Text-prediction experiment: next-word and word completion from n-grams.

EXPERIMENT ONLY (owner decision, 2026-10-14). Prediction drafts words for
the author, which CLAUDE.md non-negotiable #1 keeps out of the product; the
owner asked to *test* it. So it lives here, outside packages/ and apps/, is
never imported by the engine or any surface, and its model is written to a
cache outside the repository.

The question it answers: does a model trained on published scientific prose
predict a scientist's next word better than a general-English model of the
kind an everyday keyboard uses, and does knowing the section help?

Training text: the 115 CC BY / CC0 PMC articles of the real-document bench
(``ml/realdocs/manifest.yaml``; registry ``realdocs-europepmc-oa``, whose
permitted uses include ``train_experimental``). They are fetched with
``ml/realdocs/fetch.py`` into a cache outside the repository.

    python3.10 ml/realdocs/fetch.py --cache CACHE --only <pmc ids>
    python3.10 ml/experiments/prediction/predict.py evaluate --cache CACHE
    python3.10 ml/experiments/prediction/predict.py try --cache CACHE \
        --section methods "the model was"

Three models are compared on held-out articles (a fixed 20% split by id):

* ``general``: SymSpell's English unigram and bigram counts (symspellpy,
  MIT; Google Books n-grams), standing in for an everyday-English model;
* ``academic``: 1–4-grams from the training articles, stupid backoff;
* ``academic+section``: the same, interpolated with a model of the current
  section only (Methods, Results, Discussion, Introduction, Abstract).

Metrics: next-word top-1 and top-3 accuracy, and the keystroke saving rate
(KSR): the share of letters a writer would not type if they accepted a
correct completion from the top three as soon as it appeared.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "packages" / "core"))
sys.path.insert(0, str(ROOT / "ml" / "realdocs"))

ORDER = 4
BACKOFF = 0.4
SECTION_WEIGHT = 0.5
SECTIONS = ("abstract", "introduction", "methods", "results", "discussion")
TOKEN = re.compile(r"[A-Za-z][A-Za-z'-]*[A-Za-z]|[A-Za-z]|\d+(?:\.\d+)?")
SENT_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")


def tokens(sentence: str) -> list[str]:
    out = []
    for t in TOKEN.findall(sentence):
        out.append("<num>" if t[0].isdigit() else t.lower())
    return out


# --- corpus -----------------------------------------------------------------

def articles(cache: Path) -> list[tuple[str, str]]:
    """(id, plain text) for every cached PMC article the manifest allows
    to be used for experimental training."""
    from common import default_manifest, load_manifest, safe_name
    from convert import parse_jats, render_plain

    out = []
    for item in load_manifest(default_manifest()):
        if not item["id"].startswith("pmc-") or \
                "train_experimental" not in item["permitted_use"]:
            continue
        path = cache / safe_name(item["id"])
        files = sorted(path.glob("*.xml")) if path.is_dir() else []
        if not files:
            continue
        try:
            text = render_plain(parse_jats(files[0].read_bytes())).expect_text
        except Exception:
            continue
        out.append((item["id"], text))
    return out


def held_out(article_id: str) -> bool:
    return int(hashlib.sha256(article_id.encode()).hexdigest()[:8], 16) % 5 == 0


def sentences_by_section(text: str) -> list[tuple[str, list[str]]]:
    """(section kind, tokens) per sentence, sections from Researchly's own
    heading detection."""
    from researchly.document import Document

    doc = Document.from_text(text, "plain")
    out = []
    pos = 0
    for para in text.split("\n\n"):
        start = text.find(para, pos)
        pos = start + len(para)
        if len(para.split()) < 6:          # headings, captions' labels
            continue
        section = doc.section_at(start)
        section = section if section in SECTIONS else "other"
        for sent in SENT_END.split(para):
            toks = tokens(sent)
            if len(toks) >= 4:
                out.append((section, toks))
    return out


# --- models -----------------------------------------------------------------

class NGram:
    """Counts of the next word after each context of 0..ORDER-1 words."""

    def __init__(self):
        self.next: dict[int, dict[tuple, Counter]] = {
            k: defaultdict(Counter) for k in range(ORDER)}

    def add(self, toks: list[str]) -> None:
        seq = ["<s>"] + toks
        for i in range(1, len(seq)):
            for k in range(ORDER):
                if i - k < 0:
                    break
                self.next[k][tuple(seq[i - k:i])][seq[i]] += 1

    def prune(self, min_count: int = 2) -> None:
        for k in range(2, ORDER):
            for ctx in list(self.next[k]):
                c = Counter({w: n for w, n in self.next[k][ctx].items()
                             if n >= min_count})
                if c:
                    self.next[k][ctx] = c
                else:
                    del self.next[k][ctx]

    def scores(self, context: list[str], prefix: str = "",
               limit: int = 60) -> dict[str, float]:
        """Stupid-backoff scores of possible next words (not normalised)."""
        seq = ["<s>"] + context
        out: dict[str, float] = {}
        weight = 1.0
        for k in range(ORDER - 1, -1, -1):
            if k > len(seq):
                continue
            ctx = tuple(seq[len(seq) - k:]) if k else ()
            nxt = self.next[k].get(ctx)
            if nxt:
                total = sum(nxt.values())
                for w, n in nxt.most_common(limit if not prefix else None):
                    if prefix and not w.startswith(prefix):
                        continue
                    s = weight * n / total
                    if s > out.get(w, 0.0):
                        out[w] = s
                if len(out) >= limit:
                    break
            weight *= BACKOFF
        return out

    def to_json(self) -> dict:
        return {str(k): {"\x1f".join(ctx): dict(c) for ctx, c in d.items()}
                for k, d in self.next.items()}

    @classmethod
    def from_json(cls, data: dict) -> "NGram":
        m = cls()
        for k, d in data.items():
            for ctx, c in d.items():
                m.next[int(k)][tuple(ctx.split("\x1f")) if ctx else ()] = \
                    Counter(c)
        return m


class General:
    """Everyday-English baseline: SymSpell's unigram and bigram counts."""

    def __init__(self):
        from researchly import spellrank, spelling
        self.uni = spelling.get_sym().words
        self.total = sum(self.uni.values())
        self.after: dict[str, Counter] = defaultdict(Counter)
        for (a, b), n in spellrank.bigrams().items():
            self.after[a][b] = n
        self.top_uni = Counter(self.uni).most_common(5000)

    def scores(self, context: list[str], prefix: str = "",
               limit: int = 60) -> dict[str, float]:
        out: dict[str, float] = {}
        prev = context[-1] if context else None
        if prev and prev in self.after:
            nxt = self.after[prev]
            total = self.uni.get(prev) or sum(nxt.values())
            for w, n in nxt.most_common(None if prefix else limit):
                if not prefix or w.startswith(prefix):
                    out[w] = n / total
        for w, n in self.top_uni:
            if len(out) >= limit:
                break
            if (not prefix or w.startswith(prefix)) and w not in out:
                out[w] = BACKOFF * n / self.total
        return out


class Sectioned:
    """Interpolates a section's own model with the whole-corpus model."""

    def __init__(self, whole: NGram, by_section: dict[str, NGram]):
        self.whole, self.by_section = whole, by_section
        self.section = "other"

    def scores(self, context, prefix="", limit=60):
        base = self.whole.scores(context, prefix, limit)
        sec = self.by_section.get(self.section)
        if sec is None:
            return base
        own = sec.scores(context, prefix, limit)
        return {w: (1 - SECTION_WEIGHT) * base.get(w, 0.0)
                + SECTION_WEIGHT * own.get(w, 0.0)
                for w in set(base) | set(own)}


def top(model, context, prefix="", k=3) -> list[str]:
    s = model.scores(context, prefix)
    return [w for w, _ in sorted(s.items(), key=lambda t: -t[1])[:k]]


# --- training and evaluation -------------------------------------------------

def train(cache: Path):
    whole, by_section = NGram(), {s: NGram() for s in SECTIONS}
    test = []
    for aid, text in articles(cache):
        sents = sentences_by_section(text)
        if held_out(aid):
            test += sents
            continue
        for section, toks in sents:
            whole.add(toks)
            if section in by_section:
                by_section[section].add(toks)
    whole.prune()
    for m in by_section.values():
        m.prune()
    return whole, by_section, test


def evaluate(models: dict, test: list, max_words: int) -> dict:
    res = {}
    for name, model in models.items():
        n = hit1 = hit3 = 0
        typed = letters = 0
        for section, toks in test:
            if n >= max_words:
                break
            if isinstance(model, Sectioned):
                model.section = section
            for i, w in enumerate(toks):
                if w == "<num>":
                    continue
                ctx = toks[:i]
                preds = top(model, ctx)
                n += 1
                hit1 += bool(preds) and preds[0] == w
                hit3 += w in preds
                # keystrokes: type letters until w is offered, then accept
                cost = len(w)
                for j in range(len(w)):
                    if w in (preds if j == 0 else top(model, ctx, w[:j])):
                        cost = j + 1
                        break
                typed += cost
                letters += len(w)
        res[name] = {"words": n, "top1": hit1 / n if n else 0,
                     "top3": hit3 / n if n else 0,
                     "ksr": 1 - typed / letters if letters else 0}
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    ev = sub.add_parser("evaluate")
    ev.add_argument("--cache", type=Path, required=True)
    ev.add_argument("--max-words", type=int, default=20000)
    ev.add_argument("--json", type=Path)
    tr = sub.add_parser("try")
    tr.add_argument("--cache", type=Path, required=True)
    tr.add_argument("--section", default="other")
    tr.add_argument("text")
    args = ap.parse_args(argv)

    whole, by_section, test = train(args.cache)
    if args.cmd == "try":
        model = Sectioned(whole, by_section)
        model.section = args.section
        ctx = tokens(args.text)
        print("next:", ", ".join(top(model, ctx, k=5)))
        return 0
    models = {"general": General(), "academic": whole,
              "academic+section": Sectioned(whole, by_section)}
    res = evaluate(models, test, args.max_words)
    print(f"held-out sentences: {len(test)}\n")
    print("| model | words | next-word top-1 | top-3 | keystrokes saved |")
    print("|---|---|---|---|---|")
    for name, r in res.items():
        print(f"| {name} | {r['words']} | {100 * r['top1']:.1f}% | "
              f"{100 * r['top3']:.1f}% | {100 * r['ksr']:.1f}% |")
    if args.json:
        args.json.write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
