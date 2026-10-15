"""Learned critics: one interface, one registry, abstain by default (ADR-06).

    from researchly import critics
    result = critics.score(critics.SENTENCE_ROLE, sentence, context=paragraph)
    if result.abstain:
        ...   # behave exactly as if there were no critic

Today no critic model has passed the promotion gate, so every question is
answered by ``NullCritic`` and abstains: nothing in the engine changes.
A promoted model arrives as (1) a pinned folder in ``~/.researchly/models/
critic`` (``critic.json`` + the ONNX file whose SHA-256 it names; see
ml/critics/laya/export_onnx.py) and (2) a ``Critic`` runtime registered with
``register_backend``. ``status()`` (shown by ``health.critic_status``)
reports which of those exist.

The questions below are authored here, once, so the training scripts in
ml/critics/ ask a model exactly what the engine will ask it.
"""

from __future__ import annotations

from typing import Dict, Optional

from .base import (DESCRIPTOR, MODEL_DIR_ENV, NULL_MODEL_VERSION,  # noqa: F401
                   QUESTION_TYPES, Critic, CriticModelError, CriticScore,
                   InstalledModel, NullCritic, Question, abstention,
                   file_sha256, model_dir, read_descriptor, safe_score,
                   verify)

# --- the authored questions of S5 (Task A and Task B) ---------------------------

FLAG_USEFUL = Question(
    id="flag-useful",
    type="yes_no",
    text="Is this flag right, or worth acting on, in this paragraph?",
    options={
        "yes": "the flagged words have the problem the card describes",
        "no": "a false flag: the flagged words do not have that problem",
    },
)

SENTENCE_ROLE = Question(
    id="sentence-role",
    type="choice",
    text="What job does this sentence do in the abstract?",
    options={
        "background": "gives the context or the problem that motivates the study",
        "objective": "states the aim, question or hypothesis of the study",
        "methods": "says how the study was done: design, data, participants or analysis",
        "results": "reports what the study found, often with numbers",
        "conclusions": "says what the findings mean, or what should follow from them",
    },
)

QUESTIONS: Dict[str, Question] = {q.id: q for q in (FLAG_USEFUL, SENTENCE_ROLE)}

# --- registry --------------------------------------------------------------------

_NULL = NullCritic()
_BACKENDS: Dict[str, Critic] = {}


def register_backend(critic: Critic, questions=None) -> None:
    """Install a critic runtime for the given question ids (default: every
    question its thresholds name). Only a model that passed the promotion
    gate is registered; tests register fakes."""
    ids = list(questions) if questions is not None else list(critic.thresholds)
    for qid in ids:
        if qid not in QUESTIONS:
            raise ValueError(f"unknown question {qid!r}")
        _BACKENDS[qid] = critic


def reset() -> None:
    """Back to the null critic for every question (tests)."""
    _BACKENDS.clear()


def get(question_id: str) -> Critic:
    """The critic answering this question: the null critic unless a
    promoted model was registered for it."""
    return _BACKENDS.get(question_id, _NULL)


def score(question: Question, span: str, context: str = "") -> CriticScore:
    """Ask the registered critic; never raises (a failure abstains)."""
    return safe_score(get(question.id), question, span, context)


def active() -> bool:
    """Is any question answered by a real model right now?"""
    return bool(_BACKENDS)


def status(directory=None) -> dict:
    """What is installed and running, for health.critic_status():

    state  missing   nothing installed; every question abstains
           error     an installed critic is malformed or fails its SHA-256
           disabled  verified on disk, but no runtime is registered
           ready     verified on disk and answering questions
    """
    try:
        model: Optional[InstalledModel] = read_descriptor(directory)
    except CriticModelError as e:
        return {"state": "error", "detail": str(e), "model_version": "",
                "sha256": ""}
    if model is None:
        return {"state": "missing", "detail": "", "model_version":
                NULL_MODEL_VERSION, "sha256": ""}
    ok, why = verify(model)
    base = {"model_version": model.model_version, "sha256": model.sha256}
    if not ok:
        return dict(base, state="error", detail=why)
    running = {c.model_version for c in _BACKENDS.values()}
    if model.model_version not in running:
        return dict(base, state="disabled",
                    detail="installed and verified, but no critic runtime "
                           "is loaded in this build")
    return dict(base, state="ready", detail="")
