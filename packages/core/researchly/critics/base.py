"""The Critic interface (ARCHITECTURE.md ADR-06, PLAN.md S5b).

A critic is a learned, NON-GENERATIVE scorer. It answers one authored,
typed question about a span of the writer's text, in context, with a
calibrated probability, or it abstains:

    critic.score(question, span, context) -> CriticScore(p, abstain, model_version)

What a critic may never do (CLAUDE.md #1, #2, #5, #6):

- produce text. Its output is a probability over options the question
  already names; the explanation a writer sees always comes from the
  authored question and its source, never from the model;
- leave the machine or the engine container: weights are local ONNX run on
  CPU, pinned by SHA-256 (``InstalledModel``); no API is ever wired here;
- fail loudly into a check. ``safe_score`` turns every error into an
  abstention with a reason, because a critic that can crash a check takes
  every other tier down with it;
- be trusted below its threshold. A score under the question's calibrated
  threshold is an abstention, and an abstaining critic changes nothing:
  the flag is not shown (precision over recall, ADR-06 "Two components").

Nothing here imports an ML library. A model runtime plugs in as a
``Critic`` subclass registered through ``critics.register_backend`` once a
model has passed the promotion gate; until then every question is answered
by ``NullCritic``, which always abstains.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional

QUESTION_TYPES = ("yes_no", "choice", "score")

NULL_MODEL_VERSION = "null-critic-0 (no model installed)"

# Where a promoted critic is installed: a folder holding critic.json (the
# pinned descriptor, written by ml/critics/laya/export_onnx.py) and the ONNX
# file it names. Outside the engine package, like the GEC tier's weights.
MODEL_DIR_ENV = "RESEARCHLY_CRITIC_DIR"
DESCRIPTOR = "critic.json"


def model_dir() -> Path:
    env = os.environ.get(MODEL_DIR_ENV)
    if env:
        return Path(env)
    return Path.home() / ".researchly" / "models" / "critic"


@dataclass(frozen=True)
class Question:
    """One authored, typed question.

    ``id`` names it in model cards and thresholds; ``text`` is the
    question as the critic reads it; ``options`` maps each option key to a
    short description (``yes_no`` questions have exactly the keys "yes" and
    "no"; ``score`` options are ordered, lowest first). ``source`` is the
    short source code of the advice the question checks (researchly.sources),
    so the explanation stays traceable even when a model scores it.
    """

    id: str
    type: str
    text: str
    options: Mapping[str, str] = field(default_factory=dict)
    source: str = ""

    def __post_init__(self):
        if self.type not in QUESTION_TYPES:
            raise ValueError(f"question {self.id!r}: type must be one of "
                             f"{QUESTION_TYPES}, not {self.type!r}")
        if not re.fullmatch(r"[a-z][a-z0-9-]{1,63}", self.id):
            raise ValueError(f"question id {self.id!r} is not kebab-case")
        keys = list(self.options)
        if self.type == "yes_no" and sorted(keys) != ["no", "yes"]:
            raise ValueError(f"yes_no question {self.id!r} needs exactly "
                             "the options 'yes' and 'no'")
        if self.type in ("choice", "score") and len(keys) < 2:
            raise ValueError(f"{self.type} question {self.id!r} needs at "
                             "least two options")


@dataclass(frozen=True)
class CriticScore:
    """A critic's answer. ``p`` is the calibrated probability of
    ``answer`` (for a yes_no question, the probability of "yes" is
    ``probabilities["yes"]``). When ``abstain`` is true, ``p`` and
    ``answer`` are None and ``reason`` says why; callers treat an
    abstention exactly as if no critic existed."""

    p: Optional[float]
    abstain: bool
    model_version: str
    answer: Optional[str] = None
    probabilities: Mapping[str, float] = field(default_factory=dict)
    reason: str = ""

    def to_dict(self) -> dict:
        return {"p": self.p, "abstain": self.abstain,
                "model_version": self.model_version, "answer": self.answer,
                "probabilities": dict(self.probabilities),
                "reason": self.reason}


def abstention(model_version: str, reason: str) -> CriticScore:
    return CriticScore(p=None, abstain=True, model_version=model_version,
                       reason=reason)


class Critic:
    """Interface every learned scorer implements.

    Subclasses implement ``_score`` and return the full distribution over
    the question's options; ``score`` applies the per-question threshold
    (from the model card) and turns low confidence into an abstention.
    """

    #: names the exact artifact (model card + SHA) in every score
    model_version: str = NULL_MODEL_VERSION
    #: question id -> minimum calibrated probability to answer (from the
    #: model card; a question missing here is never answered)
    thresholds: Mapping[str, float] = {}

    def _score(self, question: Question, span: str,
               context: str) -> Mapping[str, float]:  # pragma: no cover
        raise NotImplementedError

    def score(self, question: Question, span: str,
              context: str = "") -> CriticScore:
        threshold = self.thresholds.get(question.id)
        if threshold is None:
            return abstention(self.model_version,
                              f"no calibrated threshold for {question.id!r}")
        probs = dict(self._score(question, span, context))
        if set(probs) != set(question.options):
            return abstention(self.model_version,
                              "the model answered other options than asked")
        total = sum(probs.values())
        if not probs or not (0.98 <= total <= 1.02) or \
                any(not (0.0 <= v <= 1.0) for v in probs.values()):
            return abstention(self.model_version,
                              "the model's probabilities are not a "
                              "distribution")
        answer = max(probs, key=probs.get)
        p = probs[answer]
        if p < threshold:
            return abstention(self.model_version,
                              f"confidence {p:.2f} below the calibrated "
                              f"threshold {threshold:.2f}")
        return CriticScore(p=p, abstain=False,
                           model_version=self.model_version, answer=answer,
                           probabilities=probs)


class NullCritic(Critic):
    """The critic every question gets until a model is promoted: it always
    abstains, so the engine behaves exactly as if critics did not exist."""

    model_version = NULL_MODEL_VERSION

    def score(self, question: Question, span: str,
              context: str = "") -> CriticScore:
        return abstention(self.model_version, "no critic model installed")


def safe_score(critic: Critic, question: Question, span: str,
               context: str = "") -> CriticScore:
    """``critic.score`` that never raises (a failure is an abstention)."""
    version = getattr(critic, "model_version", NULL_MODEL_VERSION)
    try:
        result = critic.score(question, span, context)
    except Exception as e:                       # a critic must never break a check
        return abstention(version, f"critic failed: {type(e).__name__}")
    if not isinstance(result, CriticScore):
        return abstention(version, "critic returned no score")
    return result


# --- the installed, pinned artifact ---------------------------------------------

@dataclass(frozen=True)
class InstalledModel:
    """What ``critic.json`` pins: the ONNX file, its SHA-256, the model
    version, the questions it was promoted for and their thresholds."""

    model_version: str
    onnx_file: str
    sha256: str
    questions: Mapping[str, float]
    directory: Path

    @property
    def onnx_path(self) -> Path:
        return self.directory / self.onnx_file


class CriticModelError(ValueError):
    pass


def read_descriptor(directory: Optional[Path] = None) -> Optional[InstalledModel]:
    """The installed critic's descriptor, None when nothing is installed.
    Raises CriticModelError when one is present but malformed."""
    d = Path(directory) if directory is not None else model_dir()
    path = d / DESCRIPTOR
    try:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise CriticModelError(f"{DESCRIPTOR} unreadable ({type(e).__name__})")
    try:
        model = InstalledModel(
            model_version=str(data["model_version"]),
            onnx_file=str(data["onnx_file"]),
            sha256=str(data["sha256"]).lower(),
            questions={str(k): float(v) for k, v in
                       dict(data["questions"]).items()},
            directory=d)
    except (KeyError, TypeError, ValueError) as e:
        raise CriticModelError(f"{DESCRIPTOR} is missing or has a bad "
                               f"field ({e})")
    if not re.fullmatch(r"[0-9a-f]{64}", model.sha256):
        raise CriticModelError(f"{DESCRIPTOR}: sha256 is not a SHA-256 digest")
    if Path(model.onnx_file).name != model.onnx_file:
        raise CriticModelError(f"{DESCRIPTOR}: onnx_file must be a bare "
                               "file name in the same folder")
    if any(not (0.5 <= t <= 1.0) for t in model.questions.values()):
        raise CriticModelError(f"{DESCRIPTOR}: thresholds must lie in "
                               "[0.5, 1.0]")
    return model


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# (path, mtime_ns, size) -> digest: a ~0.45 GB file is hashed once, not on
# every health check (engine_status runs on every analyze()).
_DIGESTS: dict = {}


def verify(model: InstalledModel) -> tuple:
    """(ok, reason): the ONNX file exists and matches its pinned SHA-256."""
    try:
        if not model.onnx_path.is_file():
            return False, f"{model.onnx_file} is missing"
        st = model.onnx_path.stat()
        key = (str(model.onnx_path), st.st_mtime_ns, st.st_size)
        actual = _DIGESTS.get(key)
        if actual is None:
            actual = _DIGESTS[key] = file_sha256(model.onnx_path)
    except OSError as e:
        return False, f"{model.onnx_file} unreadable ({type(e).__name__})"
    if actual != model.sha256:
        return False, (f"{model.onnx_file} does not match its pinned "
                       f"SHA-256 (expected {model.sha256[:12]}…, found "
                       f"{actual[:12]}…)")
    return True, ""
