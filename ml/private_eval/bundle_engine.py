"""PRIVATE: the shared keyboard engine, run through its own runtime.

Registry: ``keyboard-engine-bundle`` (ml/datasets.yaml) — ``private_eval``
only. The owner's plan (2026-10-14): test this engine and Researchly's side
by side, improve Researchly's where this one wins, then discard this one.

Rules for this folder:
* neither the bundle's files nor its runtime (``engine.py``,
  ``onnx_dump.py``, shared by the owner's friend, licence unknown) are
  copied into the repository: this adapter loads them from wherever they
  are on disk (``--bundle-code DIR`` and ``--bundle-assets DIR``);
* nothing here is imported by the engine, and ``tools/public-export``
  never exports ``ml/private_eval/`` (it is not on the allow-list);
* outputs are numbers; no bundle entry is written to the repository or
  copied into Researchly's word lists. Improvements to Researchly come from
  open data and its own methods.

What runs: the bundle's whole correction path — its replace list, its
vocabulary search (letter-bag signatures), its context-dependent error
table and 5-gram counts (read through the perfect hash), and its MLP, whose
"touch" inputs are QWERTY key positions of the typed letters. A keyboard
replaces a word only when the MLP scores a candidate >= 0.95; ``suggest``
returns the ranked candidates regardless, ``autocorrect`` applies the
threshold. Only the left context is used, as on a keyboard.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


class BundleEngine:
    def __init__(self, code_dir: Path, assets_dir: Path,
                 blocklist: Path | None = None):
        sys.path.insert(0, str(code_dir))
        self.g = importlib.import_module("engine")
        hashes = set()
        if blocklist and blocklist.exists():
            hashes = {int(x) for x in blocklist.read_text().split()
                      if x.isdigit()}
        self.ac = self.g.Autocorrect(str(assets_dir), blocklist=hashes)

    def known(self, word: str) -> bool:
        v = self.ac.vocab
        return v.contains(word) or v.contains(word.lower())

    def _check(self, word: str, prev: str | None):
        return self.ac.check_token(prev or "", word, verbose=True)

    def suggest(self, word: str, prev: str | None = None,
                nxt: str | None = None, top_n: int = 3) -> list[str]:
        best, scored = self._check(word, prev)
        if scored and scored[0][0] == "replace-dict":
            return [best]
        return [c for c, _p in scored[:top_n]]

    def autocorrect(self, word: str, prev: str | None = None) -> str | None:
        """What the keyboard would do: replace only at >= 0.95."""
        best, _scored = self._check(word, prev)
        return best
