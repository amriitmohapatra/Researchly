"""Word prediction: the end of the word being typed, or the next word.

A core feature since 2026-10-14 (owner decision). CLAUDE.md #1 sets its
limits, and this module keeps to them:

* **Words, not sentences.** It completes the word being typed or offers the
  next word. It offers at most a short fixed term ("confidence interval",
  "reproduction number"), never a clause.
* **Never inserted by itself.** It returns candidates. A surface shows them
  and inserts one only when the writer accepts it (Tab, a click).
* **Local and non-generative.** Counts of word sequences in open-access
  scientific articles (``data/predict.sqlite``, built by
  ``ml/tools/build_prediction_model.py``; attribution in
  ``data/predict_sources.tsv``). A sequence is kept only if it occurs in
  several different articles, so the model holds the shared phrasing of a
  field, never one author's sentence. No network, no learned weights.
* **Stays out of masked text.** Nothing is offered inside maths, code,
  citations, cross-references or URLs (api.complete checks the cursor).
* **Can be turned off** (``[features] prediction = false``; config.py).

The ranking is stupid backoff (Brants et al. 2007) over contexts of up to
three words, as in the experiment it grew from (ml/experiments/prediction).
"""

from __future__ import annotations

import bisect
import heapq
import json
import re
import sqlite3
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from . import spelling

MODEL_FILE = Path(__file__).parent / "data" / "predict.sqlite"
ORDER = 4
BACKOFF = 0.4
MAX_TERM_WORDS = 3          # a fixed term is at most three words
TERM_SHARE = 0.45           # how sure the next word must be to extend a term
TERM_MIN_COUNT = 8
MIN_SAVED = 2               # a completion must save at least two letters

_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9'\-]*[A-Za-z0-9]|[A-Za-z]|\d+(?:\.\d+)?|,")
_SENT_END = re.compile(r"[.!?][\"')\]]*\s+$|[.!?][\"')\]]*\s+(?=\S)")
# Words a fixed term never ends on or is extended with: "confidence
# interval" is a term, "confidence in the" is the start of a sentence.
_FUNCTION = frozenset("""
a an the of in on at to for from by with and or but nor as than that this
these those which who whom whose what when where while is are was were be
been being has have had do does did not no it its their there they we our
he she his her i you your can could may might must shall should will would
""".split())


@dataclass(frozen=True)
class Candidate:
    """One completion: replace ``[start, end)`` of the text with ``text``.
    ``end`` is the cursor; ``start`` is where the typed part of the word
    begins (the cursor itself when no word is being typed). ``kind`` is
    "word" or "term" (several words)."""
    text: str
    start: int
    end: int
    kind: str
    score: float

    def to_dict(self) -> dict:
        return {"text": self.text, "start": self.start, "end": self.end,
                "kind": self.kind, "score": round(self.score, 4)}


class Model:
    """The n-gram tables, read from the SQLite file on demand."""

    def __init__(self, path: Path = MODEL_FILE):
        self.path = Path(path)
        self._local = threading.local()
        self._unigrams: list[tuple[str, int]] | None = None
        self._uni_total = 1
        self._uni_sorted: list[tuple[str, int]] | None = None
        self._forms: dict[str, str] | None = None
        self._lock = threading.Lock()

    def _db(self) -> sqlite3.Connection:
        db = getattr(self._local, "db", None)
        if db is None:
            db = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True,
                                 check_same_thread=False)
            self._local.db = db
        return db

    def meta(self) -> dict:
        return {k: json.loads(v) for k, v in
                self._db().execute("select key, value from meta")}

    @lru_cache(maxsize=4096)
    def _row(self, ctx: str) -> tuple[int, tuple[tuple[str, int], ...]]:
        row = self._db().execute(
            "select total, words from next where ctx = ?", (ctx,)).fetchone()
        if not row:
            return 0, ()
        words = tuple((w, int(n)) for w, _, n in
                      (item.rpartition(":") for item in row[1].split()))
        return int(row[0]), words

    def _unigram_list(self) -> list[tuple[str, int]]:
        if self._unigrams is None:
            with self._lock:
                if self._unigrams is None:
                    total, words = self._row("")
                    self._uni_total = total or 1
                    self._unigrams = [(w, n) for w, n in words
                                      if w not in ("<num>", ",")]
        return self._unigrams

    def _unigram_candidates(self, prefix: str, k: int
                            ) -> list[tuple[str, int]]:
        """The k commonest words starting with `prefix`, from a sorted
        index (a prefix keystroke must not scan 40,000 words)."""
        ranked = self._unigram_list()
        if not prefix:
            return ranked[:k]
        if self._uni_sorted is None:
            with self._lock:
                if self._uni_sorted is None:
                    self._uni_sorted = sorted(ranked)
        table = self._uni_sorted
        lo = bisect.bisect_left(table, (prefix,))
        hi = bisect.bisect_left(table, (prefix + "\uffff",))
        return heapq.nlargest(k, table[lo:hi], key=lambda t: t[1])

    def display(self, word: str) -> str:
        """The word's usual case: "bayesian" → "Bayesian"."""
        if self._forms is None:
            with self._lock:
                if self._forms is None:
                    self._forms = dict(self._db().execute(
                        "select word, display from form"))
        return self._forms.get(word, word)

    def next_words(self, context: list[str], prefix: str = "",
                   k: int = 3) -> list[tuple[str, float]]:
        """The k likeliest next words after `context` (lower-case tokens)
        that start with `prefix`, with stupid-backoff scores."""
        seq = (["<s>"] + context)[-(ORDER - 1):]
        scores: dict[str, float] = {}
        weight = 1.0
        for order in range(len(seq), -1, -1):
            if order == 0:
                words = self._unigram_candidates(prefix, k + 2)
                total = self._uni_total
                if not words:
                    break
            else:
                total, words = self._row(" ".join(seq[-order:]))
            if total:
                for w, n in words:
                    if w in ("<num>", ",", "<s>") or \
                            (context and w == context[-1]):
                        continue        # never "the the"
                    if prefix and (not w.startswith(prefix)
                                   or len(w) - len(prefix) < MIN_SAVED):
                        continue
                    s = weight * n / total
                    if s > scores.get(w, 0.0):
                        scores[w] = s
                if len(scores) >= k and order > 0:
                    # a longer context already filled the list; lower
                    # orders could only add weaker candidates
                    break
            weight *= BACKOFF
        return sorted(scores.items(), key=lambda t: -t[1])[:k]

    def extend(self, context: list[str], word: str) -> list[str]:
        """The rest of a fixed term after `word`, when the model is sure:
        "confidence" → ["interval"]. Empty when it is not."""
        out: list[str] = []
        ctx = context + [word]
        while len(out) + 1 < MAX_TERM_WORDS:
            seq = (["<s>"] + ctx)[-(ORDER - 1):]
            total, words = self._row(" ".join(seq))
            if not total or not words:
                break
            nxt, n = words[0]
            if nxt in ("<num>", ",") or nxt in _FUNCTION or \
                    n < TERM_MIN_COUNT or n / total < TERM_SHARE:
                break
            out.append(nxt)
            ctx.append(nxt)
        return out


def write_model(path: Path, tables: dict, forms: dict[str, str],
                meta: dict) -> None:
    """Write a model file. `tables[order][context tuple] = (total count,
    [(next word, count), ...])`; order 0 has the empty context. Used by
    ml/tools/build_prediction_model.py and by the tests."""
    path = Path(path)
    if path.exists():
        path.unlink()
    db = sqlite3.connect(path)
    db.execute("create table meta (key text primary key, value text)")
    db.execute("create table next (ctx text primary key, total integer, "
               "words text)")
    db.execute("create table form (word text primary key, display text)")
    db.executemany("insert into meta values (?, ?)",
                   [(k, json.dumps(v)) for k, v in meta.items()])
    rows = []
    for order, table in tables.items():
        for ctx, (total, words) in table.items():
            rows.append((" ".join(ctx) if order else "", total,
                         " ".join(f"{w}:{n}" for w, n in words)))
    db.executemany("insert into next values (?, ?, ?)", rows)
    db.executemany("insert into form values (?, ?)", sorted(forms.items()))
    db.commit()
    db.execute("vacuum")
    db.close()


_MODEL: Model | None = None
_MODEL_LOCK = threading.Lock()


def get_model() -> Model | None:
    """The shipped model, or None when its file is missing (health.py
    reports that)."""
    global _MODEL
    if _MODEL is None:
        with _MODEL_LOCK:
            if _MODEL is None and MODEL_FILE.exists():
                _MODEL = Model(MODEL_FILE)
    return _MODEL


def available() -> bool:
    return MODEL_FILE.exists()


# --- turning text into context ------------------------------------------------

def _tokens(text: str) -> list[str]:
    return ["<num>" if t[0].isdigit() else t.lower()
            for t in _TOKEN.findall(text)]


def split_prefix(before: str) -> tuple[list[str], str, bool]:
    """(context tokens of the current sentence, the part of a word being
    typed, whether the sentence has just begun) from the text before the
    cursor."""
    m = re.search(r"[A-Za-z][A-Za-z'\-]*$", before)
    partial = m.group(0) if m else ""
    head = before[:len(before) - len(partial)]
    # the current sentence only: after the last sentence end
    cut = 0
    for e in _SENT_END.finditer(head):
        cut = e.end()
    for brk in ("\n\n",):
        i = head.rfind(brk)
        if i >= 0:
            cut = max(cut, i + len(brk))
    sentence = head[cut:]
    ctx = _tokens(sentence)
    return ctx, partial, not ctx


def _case_like(word: str, partial: str, model: Model,
               sentence_start: bool) -> str:
    shown = model.display(word)
    if partial[:1].isupper() and len(partial) > 1 and partial.isupper() \
            and len(word) <= 6:
        return shown.upper()
    if (sentence_start or partial[:1].isupper()) and shown[:1].islower():
        return shown[:1].upper() + shown[1:]
    return shown


def _dialect(choice: str, before: str) -> str | None:
    if choice and choice != "auto":
        return choice
    words = [w.lower() for w in re.findall(r"[A-Za-z]+", before[-20000:])]
    found, _agree, telling = spelling.detect_dialect(words)
    return found if telling else None


def _respell(word: str, dialect: str | None) -> str:
    if not dialect:
        return word
    return spelling.dialect_spelling(word, dialect) or word


def complete(before: str, cursor: int, *, spelling_choice: str = "auto",
             limit: int = 3, model: Model | None = None) -> list[Candidate]:
    """Candidates for the cursor at offset `cursor`, given the text before
    it. The caller has already checked that the cursor is in prose (not
    maths, code or a citation)."""
    model = model or get_model()
    if model is None or limit <= 0:
        return []
    ctx, partial, sentence_start = split_prefix(before)
    if not partial and (not before or not before[-1].isspace()):
        return []               # right after punctuation or a number
    if not partial and sentence_start:
        return []               # nothing to go on yet
    if partial and not partial.isalpha() and "-" not in partial:
        return []
    low = partial.lower()
    dialect = _dialect(spelling_choice, before)
    start = cursor - len(partial)

    merged: dict[str, tuple[float, str, str]] = {}
    for word, score in model.next_words(ctx, low, limit * 3):
        spelt = _respell(word, dialect)
        if low and not spelt.lower().startswith(low):
            continue
        tail = model.extend(ctx, word)
        text = " ".join([spelt] + [_respell(t, dialect) for t in tail])
        kind = "term" if tail else "word"
        text = _case_like(text.split(" ")[0], partial, model,
                          sentence_start) + text[len(text.split(" ")[0]):]
        key = text.lower()
        if key == low:
            continue
        old = merged.get(key)
        merged[key] = ((old[0] if old else 0.0) + score, text, kind)
    ranked = sorted(merged.values(), key=lambda t: -t[0])[:limit]
    return [Candidate(text, start, cursor, kind, score)
            for score, text, kind in ranked]
