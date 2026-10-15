"""The Laya harness without Laya: metrics, question mapping, data plumbing,
the export's card filling and the promotion gate, all on synthetic inputs.
No torch, no weights, nothing fetched."""

import hashlib
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import export_onnx  # noqa: E402
import finetune  # noqa: E402
import gate  # noqa: E402
import harness  # noqa: E402
import zero_shot  # noqa: E402
from harness import critics  # noqa: E402

ROLES = list(critics.SENTENCE_ROLE.options)


class FakeAgent:
    """Answers like Laya: a probability per option key."""

    def __init__(self, pick):
        self.pick = pick              # state -> option key it favours

    def predict(self, state, questions):
        out = {}
        for qid, q in questions.items():
            keys = list(q["criteria"])
            fav = self.pick(state, keys)
            probs = {k: (0.7 if k == fav else 0.3 / (len(keys) - 1))
                     for k in keys}
            out[qid] = {"choice": fav, "probabilities": probs,
                        "answer_confidence": 0.7}
        return {"answers": out}

    def predict_batch(self, states, questions, batch_size=8):
        return [self.predict(s, questions) for s in states]


def role_rows(n=40, split="test"):
    rows = []
    for i in range(n):
        role = ROLES[i % 5]
        rows.append({"pmcid": f"PMC{i // 5}", "discipline": ["epidemiology",
                     "humanities"][i % 2], "split": split, "use": "train",
                     "role": role, "position": i % 5, "n": 5,
                     "text": f"synthetic {role} sentence number {i}"})
    return rows


# --- questions ---------------------------------------------------------------------

def test_yes_no_is_asked_as_a_neutral_two_option_choice():
    q = harness.laya_question(critics.FLAG_USEFUL)
    assert q["type"] == "choice" and list(q["criteria"]) == ["A", "B"]
    back = harness.from_laya(critics.FLAG_USEFUL, {"A": 0.8, "B": 0.2})
    assert back == {"yes": 0.8, "no": 0.2}


def test_role_question_uses_the_engine_options_verbatim():
    q = harness.laya_question(critics.SENTENCE_ROLE)
    assert q["criteria"] == dict(critics.SENTENCE_ROLE.options)
    assert q["instructions"] == critics.SENTENCE_ROLE.text


def test_rotations_cover_every_slot():
    q = harness.laya_question(critics.SENTENCE_ROLE)
    rots = harness.rotations(q)
    assert len(rots) == 5
    firsts = {r["option_order"][0] for r in rots.values()}
    assert firsts == set(range(5))


# --- metrics -----------------------------------------------------------------------

def test_ece_is_zero_when_confidence_matches_accuracy():
    conf = [0.8] * 10
    correct = [1] * 8 + [0] * 2
    assert harness.ece(conf, correct) == pytest.approx(0.0)
    assert harness.ece([1.0] * 4, [0] * 4) == pytest.approx(1.0)


def test_risk_coverage_and_gate_coverage():
    conf = [0.9 - i * 0.01 for i in range(40)]
    correct = [1] * 30 + [0] * 10
    rc = harness.risk_coverage(conf, correct)
    assert rc["1.0"]["precision"] == pytest.approx(0.75)
    assert rc["0.6"]["precision"] == 1.0
    assert rc["coverage_at_gate"]["coverage"] == pytest.approx(35 / 40)


def test_temperature_fit_softens_an_overconfident_model():
    dists = [{"a": 0.99, "b": 0.01}] * 6 + [{"a": 0.01, "b": 0.99}] * 4
    gold = ["a"] * 4 + ["b"] * 2 + ["b"] * 2 + ["a"] * 2
    t = harness.fit_temperature(dists, gold)
    assert t > 1.0
    soft = harness.temper({"a": 0.99, "b": 0.01}, t)
    assert 0.5 < soft["a"] < 0.99 and sum(soft.values()) == pytest.approx(1)


def test_summarise_reports_groups_and_majority():
    dists = [{"x": 0.9, "y": 0.1}, {"x": 0.2, "y": 0.8}, {"x": 0.6, "y": 0.4}]
    s = harness.summarise(dists, ["x", "y", "y"], ["g1", "g2", "g2"])
    assert s["accuracy"] == pytest.approx(2 / 3)
    assert s["by_group"]["g2"] == {"accuracy": 0.5, "n": 2}


# --- Task B plumbing ---------------------------------------------------------------------

def test_roles_zero_shot_end_to_end_with_a_fake_agent():
    def pick(state, keys):     # reads the role out of the synthetic text
        return next((k for k in keys if k in state), keys[0])
    test, dev = role_rows(40), role_rows(20, "dev")
    rep = zero_shot.run_roles(FakeAgent(pick), test, dev, context="position",
                              rotate=False)
    assert rep["zero_shot"]["accuracy"] == 1.0
    assert rep["zero_shot"]["ece"] == pytest.approx(0.3)
    assert rep["temperature_fitted_on_dev"]["t"] < 1.0   # under-confident
    assert len(rep["items"]) == 40
    assert all(set(i) == {"answer", "confidence", "correct", "gold", "group"}
               for i in rep["items"])                    # no text
    assert rep["latency_cpu"]["n"] == 40
    assert set(rep["zero_shot"]["by_group"]) == {"epidemiology", "humanities"}


def test_a_cached_run_resumes_without_asking_again(tmp_path):
    calls = []

    class Counting(FakeAgent):
        def predict(self, state, questions):
            calls.append(state)
            return super().predict(state, questions)
    agent = Counting(lambda s, k: k[0])
    q = harness.laya_question(critics.SENTENCE_ROLE)
    cache = tmp_path / "answers.jsonl"
    first, _, _ = zero_shot.ask(agent, ["a", "b"], q, cache=cache)
    again, _, _ = zero_shot.ask(agent, ["a", "b", "c"], q, cache=cache)
    assert calls == ["a", "b", "c"]
    assert again[:2] == first
    rows = [json.loads(x) for x in cache.read_text().splitlines()]
    assert all(set(r) == {"key", "probs", "seconds"} for r in rows)  # no text


def test_sample_roles_takes_whole_abstracts_from_one_split():
    rows = role_rows(40) + role_rows(40, "train")
    s = harness.sample_roles(rows, 12)
    assert all(r["split"] == "test" for r in s)
    assert len(s) == 12


def test_training_rows_use_only_trainable_articles():
    rows = role_rows(20, "train")
    rows[0]["use"] = "eval"
    out = finetune.role_rows(rows, "train")
    assert len(out) == 19
    assert all(set(r) == {"state", "questions", "expected", "meta"}
               for r in out)
    capped = finetune.role_rows(role_rows(50, "train"), "train",
                                max_per_role=3)
    assert len(capped) == 15


# --- Task A plumbing (labels without text + local paragraphs) ----------------------------------

def test_flag_items_match_labels_to_flags(monkeypatch):
    import label_precision
    flags = {
        "results": [("W202", "improvement", 9, 20, "Tighter: 'to'."),
                    ("S001", "correction", 30, 36, "Did you mean?"),
                    ("E707", "improvement", 40, 54, "Open with the result"),
                    ("W207", "correction", 60, 67, "Doubled word")],
    }

    def fake_flags(section, text, nlp=None):
        content = "Results\n\n" + text
        return content, flags.get(section, [])
    monkeypatch.setattr(harness, "label_page_flags", fake_flags)
    labels = label_precision.load(HERE / "fixtures" / "synthetic-labels.json")
    paras = harness.label_paragraphs(HERE / "fixtures" /
                                     "synthetic-paragraphs.json")
    items, skipped = zero_shot.flag_items(labels, paras)
    assert skipped["replaced"] == 1          # the first W202 verdict
    assert skipped["unsure"] == 1
    assert len(items) == 4                   # paragraph 3's four flags
    assert [g for _, g, *_ in items] == ["yes", "yes", "no", "yes"]
    assert skipped["flag not found"] == 7    # other sections: no fake flags
    state = items[0][0]
    assert state.startswith("Section: results") and "Flagged words:" in state


def test_flags_run_with_a_fake_agent(monkeypatch):
    def fake_flags(section, text, nlp=None):
        return "x" * 300, [("W202", "improvement", 0, 5, "card")] * 3
    monkeypatch.setattr(harness, "label_page_flags", fake_flags)
    labels = [{"paragraph": 1, "rule_id": "W202", "category": "improvement",
               "section": "results", "verdict": v, "attempt": "aaaaaa",
               "flag": i} for i, v in enumerate(["useful", "wrong", "useful"])]
    paras = {1: {"section": "results", "text": "synthetic"}}
    rep = zero_shot.run_flags(FakeAgent(lambda s, k: "A"), labels, paras,
                              rotate=False)
    assert rep["zero_shot"]["n"] == 3
    assert rep["engine_precision_without_critic"] == pytest.approx(2 / 3)


def test_flags_two_stage_export_then_score(tmp_path, monkeypatch):
    """Stage 1 (engine) writes the matched flags; stage 2 (Laya) scores
    them without the engine in the same process."""
    def fake_flags(section, text, nlp=None):
        return "Results\n\n" + text, [
            ("W202", "improvement", 9, 20, "Tighter."),
            ("S001", "correction", 30, 36, "Did you mean?"),
            ("E707", "improvement", 40, 54, "Open with the result"),
            ("W207", "correction", 60, 67, "Doubled word")]
    monkeypatch.setattr(harness, "label_page_flags", fake_flags)
    items = tmp_path / "items.jsonl"
    rc = zero_shot.main(["flags", "--synthetic", "--export-items", str(items)])
    assert rc == 0
    rows = harness.read_jsonl(items)
    assert "skipped" in rows[0] and rows[1:]
    monkeypatch.setattr(harness, "load_agent",
                        lambda *a, **k: FakeAgent(lambda s, k: "A"))
    out = tmp_path / "report.json"
    zero_shot.main(["flags", "--synthetic", "--items", str(items),
                    "--out", str(out)])
    rep = json.loads(out.read_text())
    assert rep["zero_shot"]["n"] == len(rows) - 1
    assert "state" not in json.dumps(rep["items"])


def test_telemetry_priors_are_text_free(tmp_path):
    log = tmp_path / "t.jsonl"
    log.write_text("\n".join(json.dumps(e) for e in [
        {"event": "applied", "rule": "W202", "section": "results", "n": 3},
        {"event": "dismissed", "rule": "W202", "section": "results", "n": 1},
        {"event": "shown", "rule": "W202", "section": "results", "n": 9}]))
    pri = harness.telemetry_priors(log)
    assert pri[("W202", "results")] == (3, 1)
    assert "applied 3 and dismissed 1" in harness.prior_text(pri, "W202",
                                                             "results")


# --- export card and the gate -----------------------------------------------------------------

def _critic_dir(tmp_path, version="laya-roles-test"):
    d = tmp_path / "critic"
    d.mkdir()
    (d / "laya.int8.onnx").write_bytes(b"synthetic graph")
    (d / "tokenizer").mkdir()
    (d / "tokenizer" / "tokenizer.json").write_text("{}")
    digest = hashlib.sha256(b"synthetic graph").hexdigest()
    (d / "critic.json").write_text(json.dumps({
        "model_version": version, "onnx_file": "laya.int8.onnx",
        "sha256": digest, "questions": {"sentence-role": 0.9},
        "files": {"tokenizer/tokenizer.json":
                  hashlib.sha256(b"{}").hexdigest()}}))
    export_onnx.fill_card({
        "model_version": version, "sha256": digest, "onnx_bytes": 15,
        "base_model": "convaiinnovations/laya@pinned",
        "questions": "sentence-role (threshold 0.90)",
        "training_data": "s5a-oa-corpus-cc-by", "heldout_accuracy": "0.9",
        "heldout_ece": "0.05", "heldout_n": 400, "coverage_at_gate": "{}",
        "int8_check": "not run", "exported": "2026-10-15"}, d / "MODEL_CARD.md")
    return d, digest


def _report(tmp_path, n_ok=60, n_bad=5, acc=0.9):
    items = ([{"confidence": 0.95, "correct": 1}] * n_ok +
             [{"confidence": 0.95, "correct": 0}] * n_bad +
             [{"confidence": 0.5, "correct": 0}] * 20)
    p = tmp_path / "report.json"
    p.write_text(json.dumps({"zero_shot": {"accuracy": acc, "ece": 0.04},
                             "items": items}))
    return p


def _noise(tmp_path, rate):
    p = tmp_path / "corpus_stats.json"
    p.write_text(json.dumps({"per_1000_words": rate}))
    return p


def test_template_card_has_only_known_placeholders():
    import re
    fields = set(re.findall(r"\{\{(\w+)\}\}", export_onnx.TEMPLATE.read_text()))
    assert fields == {"model_version", "sha256", "onnx_bytes", "base_model",
                      "questions", "training_data", "heldout_accuracy",
                      "heldout_ece", "heldout_n", "coverage_at_gate",
                      "int8_check", "exported"}


def test_gate_blocks_today_because_laya_may_not_ship(tmp_path):
    """Today the registry withholds ship_model from Laya (D8), there are no
    fire/don't-fire tests for this model, and the noise floor is above
    target: the gate must say NOT PROMOTED, naming each reason."""
    d, _ = _critic_dir(tmp_path)
    res = gate.check(d, d / "MODEL_CARD.md", _report(tmp_path),
                     _noise(tmp_path, 11.89))
    by = {r["check"]: r for r in res}
    assert by["model card"]["ok"]
    assert by["SHA-256 pin"]["ok"]
    assert by["held-out precision (sentence-role)"]["ok"]
    assert by["beats the Task B baseline"]["ok"]
    assert not by["dataset registry"]["ok"]
    assert "laya" in by["dataset registry"]["detail"]
    assert not by["fire and don't-fire tests"]["ok"]
    assert not by["noise floor"]["ok"]
    assert by["health.py entry"]["ok"]
    assert "NOT PROMOTED" in gate.render(res)


def test_gate_passes_when_everything_holds(tmp_path):
    d, _ = _critic_dir(tmp_path, "laya-roles-pass")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_laya_roles.py").write_text(
        "V = 'laya-roles-pass'\n"
        "def test_methods_sentence_fires(): pass\n"
        "def test_background_sentence_does_not_fire(): pass\n")
    reg = tmp_path / "datasets.yaml"
    reg.write_text("datasets:\n"
                   "  - id: laya\n    permitted_use: [ship_model]\n"
                   "  - id: s5a-oa-corpus-cc-by\n"
                   "    permitted_use: [train_experimental, ship_model]\n")
    res = gate.check(d, d / "MODEL_CARD.md", _report(tmp_path),
                     _noise(tmp_path, 10.9), tests_dir=tests, registry=reg)
    assert all(r["ok"] for r in res), gate.render(res)


@pytest.mark.parametrize("change", ["sha", "precision", "card", "pickle"])
def test_gate_fails_on_each_broken_requirement(tmp_path, change):
    d, digest = _critic_dir(tmp_path)
    report = _report(tmp_path)
    if change == "sha":
        (d / "laya.int8.onnx").write_bytes(b"tampered")
    elif change == "precision":
        report = _report(tmp_path, n_ok=40, n_bad=20)
    elif change == "card":
        (d / "MODEL_CARD.md").write_text("# Model card: {{model_version}}\n")
    elif change == "pickle":
        (d / "move_clf.joblib").write_bytes(b"x")
    res = {r["check"]: r["ok"] for r in
           gate.check(d, d / "MODEL_CARD.md", report, _noise(tmp_path, 10))}
    key = {"sha": "SHA-256 pin", "precision":
           "held-out precision (sentence-role)", "card": "model card",
           "pickle": "no pickles"}[change]
    assert res[key] is False


def test_registry_reader_sees_laya_without_ship_model():
    uses = gate.registry_uses()
    assert "laya" in uses and "ship_model" not in uses["laya"]
    assert "ship_model" in uses["s5a-oa-corpus-cc-by"]
    assert "ship_model" not in uses["s5a-oa-corpus-nc-eval"]
