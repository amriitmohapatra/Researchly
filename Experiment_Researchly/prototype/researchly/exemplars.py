"""Exemplar retrieval over accepted manuscripts — EXPERIMENT (idea 2).

"Show me how accepted papers did it": when the guide finds a missing
move (no gap statement in your introduction, no significance in your
discussion), it retrieves REAL sentences that execute that move from a
local corpus of accepted documents, ranked by topical similarity to the
user's draft. Retrieval, not generation — every suggestion is a citable
sentence from a named source document, so nothing can be hallucinated
and the user still does all the writing.

The shipped index is built from the eight accepted PhD theses already in
the repo's dogfooding corpus (infectious-disease modelling — exactly the
user's field). Rebuild with your own folder of .txt documents:

    python experiments/build_exemplars.py path/to/txt-folder

Index format: JSONL, one exemplar per line —
    {"text", "move", "confidence", "how", "source"}
built by the same hybrid labeller the guide uses (lexicons for gap/aim/
limitation where they are high-precision; the move classifier for the
rest). TF-IDF vectors are computed at load time (the index is a few
thousand sentences; fitting takes milliseconds) so the only artifact on
disk is inspectable text.

Local-first: the corpus never leaves the machine; queries are a local
cosine similarity.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

INDEX_FILE = (Path(__file__).resolve().parent / "data" / "exemplars"
              / "exemplars.jsonl")

# Sentence quality gates for PDF-extracted text: length band, must look
# like prose (letters dominate), no extraction garbage.
MIN_LEN, MAX_LEN = 60, 420
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WS = re.compile(r"\s+")


def looks_like_prose(sentence: str) -> bool:
    s = sentence.strip()
    if not (MIN_LEN <= len(s) <= MAX_LEN):
        return False
    letters = sum(ch.isalpha() for ch in s)
    if letters / max(len(s), 1) < 0.72:
        return False
    if s.count("(") != s.count(")"):
        return False
    words = s.split()
    if len(words) < 8:
        return False
    # PDF artifacts: broken hyphenation runs, figure/table lines
    if re.search(r"\b(cid:|Figure \d|Table \d|\.{3,})", s):
        return False
    return True


def split_sentences(text: str) -> list:
    return [_WS.sub(" ", s).strip()
            for s in _SENT_SPLIT.split(text or "") if s.strip()]


class ExemplarIndex:
    """Loads exemplars.jsonl; query(move, context) → ranked exemplars."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else INDEX_FILE
        self._rows: Optional[list] = None
        self._vectorizer = None
        self._matrix = None
        self._failed: str = ""

    # -- loading ------------------------------------------------------------

    def available(self) -> bool:
        return bool(self._load())

    def why_unavailable(self) -> str:
        self._load()
        return self._failed

    def rows(self) -> list:
        return self._load() or []

    def _load(self):
        if self._rows is not None:
            return self._rows
        if not self.path.exists():
            self._rows = []
            self._failed = (f"no exemplar index at {self.path.name} — run "
                            "experiments/build_exemplars.py")
            return self._rows
        rows = []
        try:
            for line in self.path.read_text(
                    encoding="utf-8").splitlines():
                if line.strip():
                    rows.append(json.loads(line))
        except Exception as e:
            self._failed = f"{type(e).__name__}: {e}"
            self._rows = []
            return self._rows
        self._rows = rows
        return self._rows

    def _vectors(self):
        if self._vectorizer is None:
            rows = self._load()
            if not rows:
                return None, None
            try:
                from sklearn.feature_extraction.text import (
                    TfidfVectorizer)
                self._vectorizer = TfidfVectorizer(
                    ngram_range=(1, 2), min_df=1, sublinear_tf=True)
                self._matrix = self._vectorizer.fit_transform(
                    [r["text"] for r in rows])
            except Exception as e:
                self._failed = f"{type(e).__name__}: {e}"
                return None, None
        return self._vectorizer, self._matrix

    # -- querying -----------------------------------------------------------

    def query(self, move: str, context: str = "", k: int = 3) -> list:
        """Top-k exemplars of `move`, ranked by similarity to `context`.

        With no context (empty section), falls back to the labeller's
        confidence so the strongest examples of the move surface.
        Returns [] on any failure — the guide then shows frames only.
        """
        rows = self._load()
        if not rows:
            return []
        idxs = [i for i, r in enumerate(rows) if r.get("move") == move]
        if not idxs:
            return []
        try:
            if context.strip():
                vec, matrix = self._vectors()
                if vec is None:
                    raise RuntimeError(self._failed or "no vectors")
                sims = (matrix[idxs] @ vec.transform([context]).T
                        ).toarray().ravel()
                order = sims.argsort()[::-1]
                ranked = [(idxs[int(j)], float(sims[int(j)]))
                          for j in order]
            else:
                ranked = sorted(
                    ((i, float(rows[i].get("confidence", 0.0)))
                     for i in idxs), key=lambda t: -t[1])
        except Exception:
            ranked = [(i, 0.0) for i in idxs]
        out = []
        seen_sources: dict = {}
        for i, score in ranked:
            r = rows[i]
            # diversity: at most 2 exemplars from one source document
            if seen_sources.get(r.get("source", ""), 0) >= 2:
                continue
            seen_sources[r.get("source", "")] = \
                seen_sources.get(r.get("source", ""), 0) + 1
            out.append({"text": r["text"], "source": r.get("source", ""),
                        "move": move, "score": round(score, 4),
                        "how": r.get("how", "")})
            if len(out) >= k:
                break
        return out

    def stats(self) -> dict:
        rows = self._load()
        by_move: dict = {}
        sources = set()
        for r in rows:
            by_move[r.get("move", "?")] = by_move.get(
                r.get("move", "?"), 0) + 1
            sources.add(r.get("source", ""))
        return {"exemplars": len(rows), "by_move": by_move,
                "sources": sorted(s for s in sources if s),
                "detail": self._failed}


_DEFAULT: Optional[ExemplarIndex] = None


def get_index() -> ExemplarIndex:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = ExemplarIndex()
    return _DEFAULT
