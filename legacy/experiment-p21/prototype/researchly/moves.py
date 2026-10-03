"""Learned rhetorical-move classifier — EXPERIMENT (idea 1, 2026-08-14).

A sentence-level classifier for the moves scientific prose makes:
background / aim / methods / findings / significance. This is the
non-generative "understand what the writer is doing" layer the Codex
review asked for, done the cheap honest way first:

- v0 model: TF-IDF + multinomial logistic regression trained on the
  PubMed RCT corpus (Dernoncourt & Lee 2017 — 180k sentences from
  randomized-controlled-trial abstracts, labelled BACKGROUND / OBJECTIVE /
  METHODS / RESULTS / CONCLUSIONS). Linear baselines are strong on this
  task, train on a laptop CPU in minutes, and the artifact is a few MB —
  no torch, no GPU, no gigabytes in the installers.
- The corpus labels map onto the Belcher move schema `abstract_lens`
  already uses:  BACKGROUND→background, OBJECTIVE→aim, METHODS→methods,
  RESULTS→findings, CONCLUSIONS→significance.
- **"gap" has no public labelled corpus**, so gap detection remains the
  lexicon layer's job. Consumers get a HYBRID view: model moves where the
  model is confident, lexicon signals (gap, limitation…) on top. This is
  deliberate and documented, not a fallback.
- Abstention: predictions under CONFIDENCE_THRESHOLD are returned as
  "other" with the probability attached — precision over recall, same as
  every tier.
- Provenance: the artifact ships with a .meta.json (corpus, date, seed,
  held-out metrics, sklearn version); `describe()` surfaces it so a
  suggestion can always say which model spoke.

The class is the swap point: a future encoder model (SciBERT-class)
replaces `_predict_proba` and nothing downstream changes — the same
promise `argument.label_sentence()` makes for roles.

Local-first: the model was trained on PUBLIC corpora before shipping;
at runtime everything is a local matrix multiply. No text leaves the
machine, nothing downloads.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

MODEL_DIR = Path(__file__).resolve().parent / "data" / "models"
MODEL_FILE = MODEL_DIR / "move_clf.joblib"
META_FILE = MODEL_DIR / "move_clf.meta.json"

# Below this probability the classifier abstains ("other"). Chosen from
# the MEASURED held-out abstention curve (move_clf.metrics.md, 2026-08-14
# run): 0.6 → 84.5% coverage at 88.3% accuracy (vs 82.6% at full
# coverage; 0.7 → 76%/90.9%). Precision-over-recall says abstain rather
# than mislabel; out-of-domain prose abstains more, which is correct.
CONFIDENCE_THRESHOLD = 0.6

# Corpus label → Researchly move (the abstract_lens/Belcher schema).
LABEL_TO_MOVE = {
    "BACKGROUND": "background",
    "OBJECTIVE": "aim",
    "METHODS": "methods",
    "RESULTS": "findings",
    "CONCLUSIONS": "significance",
}
MOVES = tuple(LABEL_TO_MOVE.values())

_WS = re.compile(r"\s+")


def _normalize(sentence: str) -> str:
    """Mirror of the training-time normalisation (train_moves.py):
    collapse whitespace; mask digits so '63 patients' and '125 patients'
    share features. Keep in sync with the training script."""
    s = _WS.sub(" ", (sentence or "").strip())
    return re.sub(r"\d", "0", s)


class MoveClassifier:
    """Loads the pinned artifact lazily; abstains when absent or unsure."""

    def __init__(self, model_path: Optional[Path] = None,
                 threshold: float = CONFIDENCE_THRESHOLD):
        self.model_path = Path(model_path) if model_path else MODEL_FILE
        self.threshold = threshold
        self._pipeline = None
        self._failed: Optional[str] = None
        self._meta: Optional[dict] = None

    # -- availability -------------------------------------------------------

    def available(self) -> bool:
        return self._load() is not None

    def why_unavailable(self) -> str:
        if self._load() is not None:
            return ""
        return self._failed or "model artifact not present"

    def describe(self) -> dict:
        """Provenance for health/UI: model version, corpus, metrics."""
        meta = self.meta()
        return {
            "available": self.available(),
            "threshold": self.threshold,
            "version": meta.get("version", "none"),
            "trained_on": meta.get("corpus", ""),
            "accuracy": meta.get("test_accuracy"),
            "detail": self._failed or "",
        }

    def meta(self) -> dict:
        if self._meta is None:
            candidates = [Path(str(self.model_path).replace(
                ".joblib", ".meta.json")), META_FILE]
            self._meta = {}
            for p in candidates:
                try:
                    if p.exists():
                        self._meta = json.loads(
                            p.read_text(encoding="utf-8"))
                        break
                except Exception:
                    continue
        return self._meta

    def _load(self):
        if self._pipeline is not None or self._failed is not None:
            return self._pipeline
        if not self.model_path.exists():
            self._failed = (f"no model at {self.model_path.name} — run "
                            "experiments/train_moves.py to build it")
            return None
        try:
            import joblib
            self._pipeline = joblib.load(self.model_path)
        except Exception as e:
            self._failed = f"{type(e).__name__}: {e}"
            self._pipeline = None
        return self._pipeline

    # -- prediction ---------------------------------------------------------

    def predict(self, sentences: list) -> list:
        """[(move, probability)] per sentence; ("other", p) on abstention.

        Never raises: a broken model abstains on everything, and
        health/describe() says why.
        """
        n = len(sentences)
        pipeline = self._load()
        if pipeline is None or n == 0:
            return [("other", 0.0)] * n
        try:
            probs = pipeline.predict_proba(
                [_normalize(s) for s in sentences])
            classes = list(pipeline.classes_)
        except Exception as e:
            self._failed = f"{type(e).__name__}: {e}"
            return [("other", 0.0)] * n
        out = []
        for row in probs:
            best = int(row.argmax())
            p = float(row[best])
            move = LABEL_TO_MOVE.get(classes[best], "other")
            if p < self.threshold:
                out.append(("other", p))
            else:
                out.append((move, p))
        return out

    def predict_one(self, sentence: str) -> tuple:
        return self.predict([sentence])[0]


_DEFAULT: Optional[MoveClassifier] = None


def get_classifier() -> MoveClassifier:
    """Process-wide default instance (model loads once)."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = MoveClassifier()
    return _DEFAULT
