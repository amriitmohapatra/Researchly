"""The drafting guide — EXPERIMENT (ideas 1+2 combined, 2026-08-14).

"What should this section be doing that it isn't yet?" — answered
without generating a word of prose:

1. every sentence gets a rhetorical move via the HYBRID labeller
   (high-precision lexicons for gap / aim / limitation — the learned
   model's blind spots — and the trained move classifier for the rest);
2. each detected section's move profile is compared against what that
   section type is expected to do (SECTION_EXPECTED);
3. each missing move comes back with (a) a Pallas/Belcher fill-in frame
   and (b) up to three REAL exemplar sentences from accepted papers and
   theses in the local corpus, ranked by topical similarity to the
   user's own draft, each citing its source document.

The user does the writing; the guide shows the structure and how
published work executed it. No generation, nothing leaves the machine.
"""

from __future__ import annotations

import re
from typing import Optional

from . import abstract_lens
from .document import Document
from .exemplars import get_index, looks_like_prose
from .moves import get_classifier

# Gap detection for the guide uses only the STRONG signals — "however"
# alone (fine for the abstract lens's presence check) would mislabel far
# too many sentences when used as a per-sentence tag.
GAP_STRONG = [
    r"\bremains? (unclear|unknown|unexplored|unquantified|limited|"
    r"uncertain|to be)\b",
    r"\blittle is known\b", r"\bfew(er)? studies\b",
    r"\b(has|have) (not|never|yet to) been\b",
    r"\blimited (evidence|research|data|understanding|insight)\b",
    r"\bgap in (the |our )?(literature|knowledge|understanding)\b",
    r"\bpaucity\b", r"\bunderstudied\b", r"\boverlooked\b",
]

LIMITATION_STRONG = [
    r"\blimitations?\b", r"\bwe (could|can) ?not\b",
    r"\bwe were unable to\b", r"\bcaveats?\b",
    r"\bshould be interpreted with\b",
    r"\bmay not (generali[sz]e|apply|hold|capture)\b",
    r"\bresidual confounding\b", r"\bunmeasured\b",
]

# What each section type is expected to do (the Belcher moves the guide
# checks coverage of). Sections not listed are not nagged.
SECTION_EXPECTED = {
    "abstract": ("background", "gap", "aim", "methods", "findings",
                 "significance"),
    "introduction": ("background", "gap", "aim"),
    "methods": ("methods",),
    "results": ("findings",),
    "discussion": ("significance", "limitation"),
    "limitations": ("limitation",),
    "conclusion": ("significance",),
}

FRAMES = dict(abstract_lens.FRAMES)
FRAMES["limitation"] = ("“This study has several limitations. First, "
                        "[data/design constraint], which means "
                        "[bounded consequence for the conclusions]…”")

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def label_hybrid(sentence: str, classifier=None) -> tuple:
    """(move, confidence, how) — 'how' is "lexicon" or "model".

    Lexicons first, for exactly the moves the corpus cannot teach the
    model: gap has no labelled data at all, aim (OBJECTIVE) is the
    model's weakest class (0.55 recall on held-out), and limitation is
    not a corpus label. The classifier covers everything else.
    """
    for rx in GAP_STRONG:
        if re.search(rx, sentence, re.IGNORECASE):
            return "gap", 0.9, "lexicon"
    for rx in LIMITATION_STRONG:
        if re.search(rx, sentence, re.IGNORECASE):
            return "limitation", 0.9, "lexicon"
    for rx in abstract_lens.SIGNALS["aim"]:
        if re.search(rx, sentence, re.IGNORECASE):
            return "aim", 0.9, "lexicon"
    clf = classifier if classifier is not None else get_classifier()
    move, p = clf.predict_one(sentence)
    return move, p, "model"


def _sentences_by_section(document: Document) -> dict:
    """{section: [sentence, ...]} from the masked text (offsets =
    source; masked markup is spaces the labellers ignore)."""
    out: dict = {}
    text = document.masked
    pos = 0
    for chunk in _SENT_SPLIT.split(text):
        stripped = chunk.strip()
        if not stripped:
            pos += len(chunk) + 1
            continue
        start = text.find(chunk, pos)
        start = pos if start == -1 else start
        pos = start + len(chunk)
        section = document.section_at(start)
        out.setdefault(section, []).append(" ".join(stripped.split()))
    return out


def build_guide(document: Document, classifier=None,
                index=None, k: int = 3) -> dict:
    """The guide payload every surface can render.

    {"sections": [{section, sentences, moves_present, missing:
       [{move, frame, exemplars}]}], "model": …, "exemplars": …}
    """
    clf = classifier if classifier is not None else get_classifier()
    idx = index if index is not None else get_index()

    sections_out = []
    for section, sents in _sentences_by_section(document).items():
        expected = SECTION_EXPECTED.get(section)
        labels = [label_hybrid(s, clf) for s in sents]
        present: dict = {}
        for (move, conf, how) in labels:
            if move != "other":
                present[move] = present.get(move, 0) + 1
        entry = {
            "section": section,
            "sentences": len(sents),
            "moves_present": present,
            "checked": expected is not None,
            "missing": [],
        }
        if expected:
            context = " ".join(sents)[:4000]
            for move in expected:
                if present.get(move):
                    continue
                entry["missing"].append({
                    "move": move,
                    "frame": FRAMES.get(move, ""),
                    "exemplars": idx.query(move, context, k=k),
                })
        sections_out.append(entry)

    return {
        "sections": sections_out,
        "model": clf.describe(),
        "exemplars": idx.stats(),
        "note": ("Moves from a local classifier (+ precise lexicons for "
                 "gap/aim/limitation); exemplars are real sentences from "
                 "accepted papers and theses in your local corpus. "
                 "Nothing here is generated; the writing is yours."),
    }
