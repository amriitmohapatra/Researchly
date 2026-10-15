"""The Critic interface (ADR-06, PLAN S5b): abstain by default, never raise,
never answer below a calibrated threshold, and report honestly in health.

No ML dependency: a fake critic stands in for a promoted model, and a fake
"ONNX" file (bytes) stands in for its pinned artifact.
"""

import hashlib
import json

import pytest

from researchly import api, critics, health
from researchly.critics import (FLAG_USEFUL, SENTENCE_ROLE, Critic,
                                CriticScore, NullCritic, Question)

NLP = api.get_nlp()


@pytest.fixture(autouse=True)
def clean(tmp_path, monkeypatch):
    """Every test starts with no critic registered and an empty model dir."""
    monkeypatch.setenv(critics.MODEL_DIR_ENV, str(tmp_path / "critic"))
    critics.reset()
    yield
    critics.reset()


class FakeCritic(Critic):
    model_version = "fake-critic-1"
    thresholds = {"sentence-role": 0.7, "flag-useful": 0.8}

    def __init__(self, probs=None, boom=False):
        self.probs = probs
        self.boom = boom

    def _score(self, question, span, context):
        if self.boom:
            raise RuntimeError("model exploded")
        return self.probs


def _install(tmp_path, payload=b"fake onnx bytes", version="fake-critic-1",
             sha=None, questions=None):
    d = tmp_path / "critic"
    d.mkdir(exist_ok=True)
    (d / "critic.onnx").write_bytes(payload)
    (d / critics.DESCRIPTOR).write_text(json.dumps({
        "model_version": version, "onnx_file": "critic.onnx",
        "sha256": sha or hashlib.sha256(payload).hexdigest(),
        "questions": questions or {"sentence-role": 0.7}}))
    return d


# --- the default: nothing installed, everything abstains ----------------------

def test_every_question_abstains_by_default():
    for q in critics.QUESTIONS.values():
        r = critics.score(q, "We recruited 412 adults.", "context")
        assert r.abstain and r.p is None and r.answer is None
        assert r.model_version == critics.NULL_MODEL_VERSION
        assert r.reason
    assert not critics.active()
    assert isinstance(critics.get("sentence-role"), NullCritic)


def test_analyze_is_unchanged_without_a_critic():
    """Health of a build with no critic lists no critic tier, so every
    surface's status line and the service's partial-state logic are as
    before."""
    a = api.analyze("The results was significant.", nlp=NLP)
    assert all(t.tier != "critic" for t in a.health)


def test_health_reports_not_installed_with_reason_and_remedy():
    s = health.critic_status()
    assert s.tier == "critic" and s.state == "missing" and not s.ok
    assert "not installed" in s.detail and "abstain" in s.detail
    assert "promot" in s.remedy


# --- the interface --------------------------------------------------------------

ROLE_PROBS = {"background": 0.02, "objective": 0.03, "methods": 0.85,
              "results": 0.07, "conclusions": 0.03}


def test_a_confident_answer_carries_p_answer_and_version():
    critics.register_backend(FakeCritic(ROLE_PROBS))
    r = critics.score(SENTENCE_ROLE, "We recruited 412 adults.")
    assert not r.abstain and r.answer == "methods" and r.p == 0.85
    assert r.model_version == "fake-critic-1"
    assert set(r.to_dict()) == {"p", "abstain", "model_version", "answer",
                                "probabilities", "reason"}


def test_below_threshold_is_an_abstention():
    flat = {"background": 0.2, "objective": 0.2, "methods": 0.24,
            "results": 0.18, "conclusions": 0.18}
    critics.register_backend(FakeCritic(flat))
    r = critics.score(SENTENCE_ROLE, "Something.")
    assert r.abstain and r.p is None and "threshold" in r.reason


def test_a_question_without_a_calibrated_threshold_is_never_answered():
    class OneQuestion(FakeCritic):
        thresholds = {"sentence-role": 0.7}
    critic = OneQuestion({"yes": 0.99, "no": 0.01})
    critics.register_backend(critic, questions=["flag-useful"])
    assert critics.score(FLAG_USEFUL, "x").abstain


def test_a_failing_critic_abstains_instead_of_raising():
    critics.register_backend(FakeCritic(boom=True))
    r = critics.score(SENTENCE_ROLE, "x")
    assert r.abstain and "RuntimeError" in r.reason


@pytest.mark.parametrize("probs", [
    {"methods": 1.0},                                        # options missing
    dict(ROLE_PROBS, extra=0.0),                             # options added
    {k: 0.5 for k in ROLE_PROBS},                            # not a distribution
    dict(ROLE_PROBS, methods=1.2, results=-0.28),            # out of [0, 1]
])
def test_malformed_model_output_abstains(probs):
    critics.register_backend(FakeCritic(probs))
    assert critics.score(SENTENCE_ROLE, "x").abstain


def test_critics_only_choose_among_authored_options():
    """Non-generative by construction: an answer is always an option key the
    question named, never text from the model."""
    critics.register_backend(FakeCritic(ROLE_PROBS))
    r = critics.score(SENTENCE_ROLE, "x")
    assert r.answer in SENTENCE_ROLE.options


def test_questions_are_typed_and_validated():
    with pytest.raises(ValueError):
        Question("flag-useful", "free_text", "Rewrite this?")
    with pytest.raises(ValueError):
        Question("q-yn", "yes_no", "?", {"true": "a", "false": "b"})
    with pytest.raises(ValueError):
        Question("q-choice", "choice", "?", {"only": "one"})
    with pytest.raises(ValueError):
        Question("Bad Id", "choice", "?", {"a": "1", "b": "2"})
    with pytest.raises(ValueError):
        critics.register_backend(FakeCritic(ROLE_PROBS), ["no-such-question"])


def test_null_critic_score_type():
    r = NullCritic().score(SENTENCE_ROLE, "x")
    assert isinstance(r, CriticScore) and r.abstain


# --- the pinned artifact and health -----------------------------------------------

def test_installed_and_verified_but_no_runtime_is_disabled(tmp_path):
    _install(tmp_path)
    s = health.critic_status()
    assert s.state == "disabled" and not s.ok
    assert "fake-critic-1" in s.detail and "sha256" in s.detail
    # reported in engine health once something is installed
    assert any(t.tier == "critic" for t in health.engine_status())


def test_installed_verified_and_running_is_ready(tmp_path):
    payload = b"pinned weights"
    _install(tmp_path, payload)
    critics.register_backend(FakeCritic(ROLE_PROBS))
    s = health.critic_status()
    assert s.ok and s.state == "ready"
    assert "fake-critic-1" in s.detail
    assert hashlib.sha256(payload).hexdigest()[:12] in s.detail


def test_sha_mismatch_is_an_error_with_a_remedy(tmp_path):
    _install(tmp_path, sha="0" * 64)
    s = health.critic_status()
    assert s.state == "error" and not s.ok
    assert "SHA-256" in s.detail and s.remedy


@pytest.mark.parametrize("descriptor", [
    "not json",
    json.dumps({"model_version": "x"}),
    json.dumps({"model_version": "x", "onnx_file": "../evil.onnx",
                "sha256": "a" * 64, "questions": {}}),
    json.dumps({"model_version": "x", "onnx_file": "c.onnx",
                "sha256": "abc", "questions": {}}),
    json.dumps({"model_version": "x", "onnx_file": "c.onnx",
                "sha256": "a" * 64, "questions": {"sentence-role": 0.2}}),
])
def test_malformed_descriptor_is_an_error(tmp_path, descriptor):
    d = tmp_path / "critic"
    d.mkdir()
    (d / critics.DESCRIPTOR).write_text(descriptor)
    s = health.critic_status()
    assert s.state == "error" and s.remedy


def test_health_never_raises_on_a_broken_critic(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("disk on fire")
    monkeypatch.setattr(critics, "status", boom)
    tiers = health.engine_status()
    assert any(t.state == "error" for t in tiers)
