"""The one-command Laya pipeline without Laya: the data assembler, the
evaluator, resumable training, the export pin, the gate's new checks and the
shell scripts' argument handling. No torch, no weights, nothing fetched; the
engine's flags are faked where a test needs them."""

import json
import os
import subprocess
import sys
import types
from collections import Counter
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import assemble  # noqa: E402
import evaluate  # noqa: E402
import export_onnx  # noqa: E402
import finetune  # noqa: E402
import gate  # noqa: E402
import harness  # noqa: E402
import pipeline  # noqa: E402
from harness import critics  # noqa: E402

RULES = ["W202", "C303", "F601", "S001"]


# --- fixtures ------------------------------------------------------------------------

def fake_engine(monkeypatch):
    """Every paragraph shows the same four flags, one per rule."""
    def flags(section, text, nlp=None):
        content = "Results\n\n" + text
        return content, [(r, "improvement", 9 + 3 * i, 11 + 3 * i, f"card {r}")
                         for i, r in enumerate(RULES)]
    monkeypatch.setattr(harness, "label_page_flags", flags)


def write_part(folder: Path, part: str, n: int):
    paras, labels = [], []
    for p in range(1, n + 1):
        paras.append({"paragraph": p, "section": "results",
                      "text": f"Synthetic paragraph {part}{p} written for a "
                              "test of the assembler, with no real content."})
        for i, r in enumerate(RULES):
            verdict = ["useful", "wrong", "useful", "unsure"][(p + i) % 4]
            labels.append({"paragraph": p, "rule_id": r,
                           "category": "improvement", "section": "results",
                           "verdict": verdict, "attempt": f"syn{part}{p:04d}",
                           "flag": i})
    (folder / f"part-{part}-paragraphs.json").write_text(json.dumps(
        {"version": 1, "paragraphs": paras}))
    (folder / f"part-{part}-labels.json").write_text(json.dumps(
        {"version": 1, "labels": labels}))


def synthetic_dir(tmp_path, n=20):
    d = tmp_path / "synthetic"
    d.mkdir()
    for part in "abc":
        write_part(d, part, n)
    return d


def corpus_dir(tmp_path, n_train=24, n_test=8):
    """Labels + paragraph index (as committed) and rebuilt paragraphs
    (as rebuild.py writes them, outside the repo)."""
    d = tmp_path / "corpus"
    d.mkdir()
    rebuilt = tmp_path / "rebuilt"
    rebuilt.mkdir()
    index, paras = [], {"train": [], "test": []}
    labels = {"train": [], "test": []}
    for p in range(1, n_train + n_test + 1):
        split = "train" if p <= n_train else "test"
        index.append({"paragraph": p, "split": split,
                      "pmcid": f"PMC{900 + (p - 1) // 3}",
                      "discipline": "ecology-evolution", "section": "results"})
        paras[split].append({"paragraph": p, "section": "results",
                             "text": f"Corpus stand-in paragraph {p}."})
        for i, r in enumerate(RULES[:3]):
            labels[split].append({
                "paragraph": p, "rule_id": r, "category": "improvement",
                "section": "results",
                "verdict": "wrong" if (p + i) % 3 else "useful",
                "attempt": f"corp{split[1]}{p:04d}", "flag": i})
    (d / "paragraph-index.json").write_text(json.dumps(
        {"version": 1, "paragraphs": index}))
    for split in ("train", "test"):
        (d / f"{split}-labels.json").write_text(json.dumps(
            {"version": 1, "labels": labels[split]}))
        (rebuilt / f"{split}-paragraphs.json").write_text(json.dumps(
            {"version": 1, "paragraphs": paras[split]}))
    return d, rebuilt


# --- merging the synthetic parts -----------------------------------------------------

def test_real_synthetic_parts_merge_into_one_sequence():
    labels, paras, part_of = assemble.merge_synthetic()
    assert sorted(paras) == list(range(1, len(paras) + 1))
    assert len(paras) == 450
    assert Counter(part_of.values()) == {"a": 150, "b": 150, "c": 150}
    assert part_of[1] == "a" and part_of[151] == "b" and part_of[450] == "c"
    assert all(x["paragraph"] in paras for x in labels)
    # a label keeps its own part's paragraph: attempt ids name the part
    for x in labels:
        assert x["attempt"][:4] == "syn" + part_of[x["paragraph"]]


def test_merged_files_load_like_label_page_exports(tmp_path):
    import label_precision
    labels, paras, part_of = assemble.merge_synthetic(synthetic_dir(tmp_path))
    assemble.write_merged(tmp_path, labels, paras, part_of)
    back = label_precision.load(tmp_path / "synthetic-labels.json")
    assert len(back) == len(labels) == 3 * 20 * 4
    assert set(harness.label_paragraphs(tmp_path / "synthetic-paragraphs.json")
               ) == set(range(1, 61))


# --- splitting and balancing ---------------------------------------------------------

def test_grouped_split_is_disjoint_stratified_and_deterministic():
    groups = {f"p{i}": [f"{RULES[i % 4]}:{'yes' if i % 3 else 'no'}"] * (1 + i % 5)
              for i in range(200)}
    fr = {"train": 0.7, "dev": 0.15, "test": 0.15}
    where = assemble.grouped_split(groups, fr)
    assert set(where) == set(groups)
    assert where == assemble.grouped_split(groups, fr)
    rows = Counter()
    for g, s in groups.items():
        rows[where[g]] += len(s)
    total = sum(rows.values())
    for sp, f in fr.items():
        assert abs(rows[sp] / total - f) < 0.05
    # every stratum reaches every split
    for stratum in {s for v in groups.values() for s in v}:
        seen = {where[g] for g, v in groups.items() if stratum in v}
        assert seen == set(fr)


def test_balance_repeats_the_minority_up_to_the_ratio():
    rows = [{"state": f"s{i}", "meta": {"verdict": "useful"}} for i in range(30)]
    rows += [{"state": f"w{i}", "meta": {"verdict": "wrong"}} for i in range(10)]
    out, rep = assemble.balance(rows, 1.5)
    c = Counter(r["meta"]["verdict"] for r in out)
    assert c["useful"] == 30 and c["wrong"] == 20
    assert rep["added"] == 10 and rep["ratio_before"] == 3.0
    same, rep2 = assemble.balance(rows, 0)
    assert len(same) == 40 and rep2["added"] == 0


# --- Task A end to end ---------------------------------------------------------------

def test_task_a_pools_sources_without_leaks(tmp_path, monkeypatch):
    fake_engine(monkeypatch)
    syn = synthetic_dir(tmp_path)
    cdir, rebuilt = corpus_dir(tmp_path)
    owner_labels = tmp_path / "owner-labels.json"
    owner_paras = tmp_path / "owner-paras.json"
    (owner_paras).write_text(json.dumps({"version": 1, "paragraphs": [
        {"paragraph": 1, "section": "results", "text": "Owner stand-in."}]}))
    owner_labels.write_text(json.dumps({"version": 1, "labels": [
        {"paragraph": 1, "rule_id": "W202", "category": "improvement",
         "section": "results", "verdict": "useful", "attempt": "owner00001",
         "flag": 0}]}))
    out = tmp_path / "data"
    out.mkdir()
    rep = assemble.task_a(out, corpus_paragraphs=rebuilt,
                          owner_labels=owner_labels,
                          owner_paragraphs=owner_paras, max_ratio=1.5,
                          quick=False, synthetic_dir=syn, corpus_dir=cdir)
    assert rep["overlap"] == {}
    rows = {k: harness.read_jsonl(out / f"flags-{k}.jsonl")
            for k in ("train", "dev", "test", "test-owner")}
    # the corpus's own test split stays the test; its dev comes from train
    corpus_test = {f"PMC{900 + (p - 1) // 3}" for p in range(25, 33)}
    for k in ("train", "dev"):
        assert not {r["meta"].get("pmcid") for r in rows[k]} & corpus_test
    assert {r["meta"]["source"] for r in rows["test"]} == {"synthetic",
                                                           "corpus"}
    # the owner's labels are only ever a test
    assert [r["meta"]["source"] for r in rows["test-owner"]] == ["owner"]
    for k in ("train", "dev", "test"):
        assert all(r["meta"]["source"] != "owner" for r in rows[k])
    # synthetic paragraphs: one split each, roughly 70/15/15 by row
    syn_rows = Counter(k for k in ("train", "dev", "test") for r in rows[k]
                       if r["meta"]["source"] == "synthetic")
    assert syn_rows["train"] > syn_rows["dev"] > 0 and syn_rows["test"] > 0
    # Laya's format, the question the engine will ask
    r = rows["train"][0]
    assert set(r) == {"state", "questions", "expected", "meta"}
    assert r["expected"]["flag-useful"] in ("A", "B")
    assert r["questions"]["flag-useful"] == harness.laya_question(
        critics.FLAG_USEFUL)
    # unsure verdicts never train
    assert rep["sources"]["synthetic"]["skipped"]["unsure"] == 60
    assert "corpus" in rep["sources"]


def test_task_a_without_rebuilt_corpus_says_so(tmp_path, monkeypatch):
    fake_engine(monkeypatch)
    syn = synthetic_dir(tmp_path, n=8)
    cdir, _ = corpus_dir(tmp_path)
    out = tmp_path / "data"
    out.mkdir()
    rep = assemble.task_a(out, corpus_paragraphs=None, owner_labels=None,
                          owner_paragraphs=None, max_ratio=1.5, quick=True,
                          synthetic_dir=syn, corpus_dir=cdir)
    assert "corpus" not in rep["sources"]
    assert any("synthetic data only" in n for n in rep["notes"])
    assert not (out / "flags-test-owner.jsonl").exists()


def test_task_b_uses_only_trainable_articles_and_their_split(tmp_path):
    rows = []
    for i in range(60):
        rows.append({"pmcid": f"PMC{i // 5}", "discipline": "epidemiology",
                     "split": ["train", "dev", "test"][(i // 5) % 3],
                     "use": "eval" if i % 10 == 0 else "train",
                     "role": ["background", "methods", "results"][i % 3],
                     "position": i % 5, "n": 5, "text": f"sentence {i}"})
    src = tmp_path / "sentences.jsonl"
    src.write_text("\n".join(json.dumps(r) for r in rows))
    rep = assemble.task_b(tmp_path, src, max_per_role=0, quick=False)
    assert rep["articles_in_two_splits"] == 0
    assert sum(v["rows"] for v in rep["counts"].values()) == 54
    test = harness.read_jsonl(tmp_path / "roles-test.jsonl")
    assert all(r["meta"]["role"] == r["expected"]["sentence-role"]
               for r in test)


def test_assembler_refuses_an_output_inside_the_repo():
    with pytest.raises(SystemExit):
        assemble.main(["--out", str(HERE / "data-here"), "--task", "b"])


# --- evaluation ----------------------------------------------------------------------

class FakeAgent:
    """Right with confidence 0.9 on even states, wrong with 0.6 on odd."""

    def predict_batch(self, states, questions, batch_size=None):
        out = []
        for s in states:
            qid, q = next(iter(questions.items()))
            keys = list(q["criteria"])
            gold = s.split("|")[1]
            right = int(s.split("|")[0]) % 2 == 0
            pick = gold if right else next(k for k in keys if k != gold)
            p = 0.9 if right else 0.6
            out.append({"answers": {qid: {"probabilities": {
                k: (p if k == pick else (1 - p) / (len(keys) - 1))
                for k in keys}}}})
        return out


def flag_rows_for_eval(n, source="synthetic"):
    q = critics.FLAG_USEFUL
    rows = []
    for i in range(n):
        g = "A" if i % 3 else "B"
        rows.append({"state": f"{i}|{g}", "questions": {
            q.id: harness.laya_question(q)}, "expected": {q.id: g},
            "meta": {"source": source, "rule": RULES[i % 4],
                     "verdict": "useful" if g == "A" else "wrong"}})
    return rows


def test_evaluate_calibrates_on_dev_and_reports_each_test(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    for name, n, src in (("dev", 80, "synthetic"), ("test", 100, "corpus"),
                         ("test-owner", 40, "owner")):
        assemble.write_jsonl(flag_rows_for_eval(n, src),
                             data / f"flags-{name}.jsonl")
    s = evaluate.evaluate(FakeAgent(), data, "a", tmp_path / "ev")
    assert s["threshold"]["reached"]
    assert 0.5 < s["threshold"]["threshold"] <= 1.0
    assert set(s["tests"]) == {"test", "test-owner"}
    rep = json.loads((tmp_path / "ev-test.json").read_text())
    # the gate reads this report the same way
    prec, kept = gate.precision_at_threshold(rep, s["threshold"]["threshold"])
    assert prec == 1.0 and kept == 50
    assert rep["at_dev_threshold"]["precision"] == 1.0
    assert "state" not in json.dumps(rep)
    assert rep["with_critic"]["flags_hidden"] >= 1
    assert (tmp_path / "ev-test-owner.json").exists()


def test_threshold_is_none_when_precision_never_reaches_the_bar():
    dists = [{"yes": 0.7, "no": 0.3}] * 40
    gold = ["yes", "no"] * 20
    t = evaluate.pick_threshold(dists, gold)
    assert t["threshold"] is None and not t["reached"]
    assert export_onnx.clamp_threshold(None) == 1.0
    assert export_onnx.clamp_threshold(0.31) == 0.5


# --- resumable training (Laya's trainer faked) -------------------------------------

def fake_laya_train(monkeypatch, crash_after=None):
    calls = []
    mod = types.ModuleType("laya.train")

    class TrainConfig:
        def __init__(self, **k):
            self.__dict__.update(k)

    def save_checkpoint(model, tok, cfg, path):
        Path(path).mkdir(parents=True, exist_ok=True)
        (Path(path) / "model.safetensors").write_text("w")

    def finetune(data, base, out, cfg, device="auto"):
        calls.append({"base": base, "epochs": cfg.epochs, "seed": cfg.seed})
        for e in range(cfg.epochs):
            mod.save_checkpoint(None, None, {}, os.path.join(out,
                                                             "checkpoint_latest"))
            if crash_after is not None and len(calls) == 1 and e + 1 == crash_after:
                raise KeyboardInterrupt
        mod.save_checkpoint(None, None, {}, out)
        return {"train_items": 10, "epoch_loss": [1.0] * cfg.epochs}

    mod.TrainConfig, mod.save_checkpoint, mod.finetune = (
        TrainConfig, save_checkpoint, finetune)
    pkg = types.ModuleType("laya")
    pkg.train = mod
    monkeypatch.setitem(sys.modules, "laya", pkg)
    monkeypatch.setitem(sys.modules, "laya.train", mod)
    return calls


def test_training_resumes_from_the_last_finished_epoch(tmp_path, monkeypatch):
    calls = fake_laya_train(monkeypatch, crash_after=2)
    base = tmp_path / "base"
    base.mkdir()
    out = tmp_path / "ckpt"
    with pytest.raises(KeyboardInterrupt):
        finetune.train(tmp_path / "d.jsonl", out, base=str(base), epochs=5)
    assert finetune.read_progress(out)["epochs_done"] == 2
    rep = finetune.train(tmp_path / "d.jsonl", out, base=str(base), epochs=5)
    assert calls[1]["epochs"] == 3 and calls[1]["base"].endswith("resume-base")
    assert rep["resumed_after_epoch"] == 2
    assert finetune.read_progress(out) == {"epochs_done": 5, "epochs": 5,
                                           "finished": True}
    assert not (out / "checkpoint_latest").exists()
    assert not (out / "resume-base").exists()
    # a finished run is not redone
    finetune.train(tmp_path / "d.jsonl", out, base=str(base), epochs=5)
    assert len(calls) == 2


# --- export pin and model card -------------------------------------------------------

def test_finalise_pins_the_graph_and_fills_the_card(tmp_path):
    d = tmp_path / "critic"
    (d / "tokenizer").mkdir(parents=True)
    (d / "laya.int8.onnx").write_bytes(b"graph")
    (d / "tokenizer" / "tokenizer.json").write_text("{}")
    (d / "export-meta.json").write_text(json.dumps(
        {"files": ["tokenizer/tokenizer.json"], "int8_check": None,
         "exported": "2026-10-16"}))
    report = {"after_temperature": {"accuracy": 0.8, "ece": 0.05, "n": 246,
                                    "risk_coverage": {"coverage_at_gate": {}}}}
    desc = export_onnx.finalise(d, version="laya-flags-test",
                                questions={"flag-useful": 0.42},
                                report=report,
                                training_data="s5-synthetic-drafts")
    assert desc["questions"] == {"flag-useful": 0.5}
    card = (d / "MODEL_CARD.md").read_text()
    assert "{{" not in card and desc["sha256"] in card
    assert critics.read_descriptor(d).model_version == "laya-flags-test"


def test_check_states_reads_both_formats(tmp_path):
    flags = tmp_path / "flags.jsonl"
    assemble.write_jsonl(flag_rows_for_eval(5), flags)
    states, q = export_onnx.check_states(flags, 3)
    assert len(states) == 3 and list(q["criteria"]) == ["A", "B"]


# --- the gate's additions --------------------------------------------------------------

def test_gate_reads_run_dogfoods_per_document_file(tmp_path):
    from noise_gate import summarise
    stats = {"thesis1": {"words": 1000, "suggestions": 10, "by_rule": {}},
             "thesis2": {"words": 1000, "suggestions": 12, "by_rule": {}}}
    p = tmp_path / "corpus_stats.json"
    p.write_text(json.dumps(stats))
    assert summarise(stats)["per_1000_words"] == 11.0
    d = tmp_path / "critic"
    d.mkdir()
    (d / "critic.json").write_text(json.dumps({"model_version": "v",
                                               "questions": {}}))
    res = {r["check"]: r for r in gate.check(d, d / "card.md", p, p)}
    assert res["noise floor"]["ok"] and "11.0/1000w" in res[
        "noise floor"]["detail"]


def test_gate_task_a_needs_the_owners_labels(tmp_path):
    d = tmp_path / "critic"
    d.mkdir()
    (d / "critic.json").write_text(json.dumps(
        {"model_version": "v", "questions": {"flag-useful": 0.8}}))
    report = tmp_path / "r.json"
    report.write_text(json.dumps({"after_temperature": {"ece": 0.05},
                                  "items": [{"confidence": 0.9,
                                             "correct": 1}] * 30}))
    noise = tmp_path / "n.json"
    noise.write_text(json.dumps({"per_1000_words": 10}))
    res = {r["check"]: r for r in gate.check(d, d / "c.md", report, noise,
                                             task="flags")}
    assert not res["independent test (owner's labels)"]["ok"]
    assert "RESEARCHLY_LABELS" in res["independent test (owner's labels)"][
        "detail"]
    res = {r["check"]: r for r in gate.check(
        d, d / "c.md", report, noise, task="flags", owner_report_path=report)}
    assert res["independent test (owner's labels)"]["ok"]


# --- the plan --------------------------------------------------------------------------

def test_hyperparameters_are_apple_silicon_safe():
    h = pipeline.hyper(5184, "mps", False)
    assert h["micro_batch"] == 1 and h["effective_batch"] == 64
    assert h["epochs"] == 3
    a = pipeline.hyper(1033, "mps", False)
    assert a["micro_batch"] == 1 and a["grad_accum"] == 32 and a["epochs"] == 5
    c = pipeline.hyper(5184, "cuda", False)
    assert c["micro_batch"] * c["grad_accum"] == 64
    assert pipeline.hyper(96, "cpu", True)["epochs"] == 1


def test_plan_without_data_uses_the_known_sizes():
    p = pipeline.plan(None, ["b", "a"], "mps", False)
    assert p["tasks"]["b"]["sizes"]["train"] == 5184
    assert p["total_minutes"] > 60


def test_summary_reads_a_finished_run(tmp_path):
    run = tmp_path / "run"
    (run / "a").mkdir(parents=True)
    (run / "a" / "run.json").write_text(json.dumps(
        {"sizes": {"train": 10, "dev": 4, "test": 4}, "hyper": {"epochs": 1},
         "device": "cpu"}))
    (run / "a" / ".done-eval-int8").write_text(json.dumps(
        {"threshold": {"reached": False, "threshold": None},
         "tests": {"test": {"n": 4, "accuracy": 0.5, "raw_accuracy": 0.5,
                            "ece": 0.1, "at_dev_threshold": {
                                "coverage": 0.0, "precision": None},
                            "engine_precision_without_critic": 0.5,
                            "with_critic": {"flags_hidden": 0,
                                            "useful_flags_hidden": 0,
                                            "engine_precision_with_critic":
                                                0.5}}}}))
    (run / "a" / "gate.json").write_text(json.dumps(
        {"verdict": "NOT PROMOTED", "checks": [
            {"check": "dataset registry", "ok": False,
             "detail": "no ship_model for: laya"}]}))
    text = pipeline.summary_text(run)
    assert "agreement with Claude" in text
    assert "NOT PROMOTED" in text and "no ship_model for: laya" in text
    assert "RESEARCHLY_LABELS" in text


# --- the shell scripts ---------------------------------------------------------------------

def run_sh(script, *args, env_extra=None, home=None):
    env = dict(os.environ, PYTHON=sys.executable)
    if home is not None:
        env["HOME"] = str(home)
        env["RESEARCHLY_CORPUS_CACHE"] = str(Path(home) / "corpus")
        env["LAYA_CORPUS_PARAGRAPHS"] = str(Path(home) / "laya-corpus")
    env.pop("RESEARCHLY_LABELS", None)
    env.pop("RESEARCHLY_PARAGRAPHS", None)
    env.update(env_extra or {})
    return subprocess.run(["bash", str(HERE / script), *args], env=env,
                          capture_output=True, text=True, timeout=120)


def test_train_sh_dry_run_prints_the_plan_and_changes_nothing(tmp_path):
    r = run_sh("train.sh", "--dry-run", "--task", "both", "--device", "mps",
               home=tmp_path)
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "Plan (device mps)" in out and "Task B" in out and "Task A" in out
    assert "micro-batch 1" in out
    for words in ("set up the ML venv", "download the open-access corpus",
                  "assemble", "train, evaluate, calibrate and export",
                  "promotion gate", "summary", "Dry run: nothing was changed"):
        assert words in out
    assert list(tmp_path.iterdir()) == []


def test_train_sh_quick_task_b_dry_run(tmp_path):
    r = run_sh("train.sh", "--dry-run", "--quick", "--task", "b",
               "--device", "cpu", home=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "quick smoke run" in r.stdout and "Task A" not in r.stdout
    assert "1 epoch(s)" in r.stdout


@pytest.mark.parametrize("args,needle", [
    (["--task", "x"], "--task must be a, b or both"),
    (["--device", "tpu"], "--device must be cpu, mps or cuda"),
    (["--import", "/nonexistent/laya-outputs.zip"], "no such file"),
    (["--epochs", "many"], "whole number"),
    (["--bogus"], "unknown option"),
    (["--task"], "needs a value"),
])
def test_train_sh_rejects_bad_arguments(tmp_path, args, needle):
    r = run_sh("train.sh", "--dry-run", *args, home=tmp_path)
    assert r.returncode == 2 and needle in r.stderr


def test_train_sh_needs_both_owner_variables(tmp_path):
    labels = tmp_path / "labels.json"
    labels.write_text("{}")
    r = run_sh("train.sh", "--dry-run", home=tmp_path,
               env_extra={"RESEARCHLY_LABELS": str(labels)})
    assert r.returncode == 2 and "RESEARCHLY_PARAGRAPHS" in r.stderr
    paras = tmp_path / "paras.json"
    paras.write_text("{}")
    r = run_sh("train.sh", "--dry-run", "--task", "a", home=tmp_path,
               env_extra={"RESEARCHLY_LABELS": str(labels),
                          "RESEARCHLY_PARAGRAPHS": str(paras)})
    assert r.returncode == 0 and "independent test only" in r.stdout


def test_train_sh_import_dry_run(tmp_path):
    z = tmp_path / "laya-outputs.zip"
    z.write_bytes(b"PK")
    r = run_sh("train.sh", "--dry-run", "--import", str(z), home=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "unpack the Kaggle outputs" in r.stdout
    assert "evaluate the INT8 critics on this machine" in r.stdout


def test_train_sh_help():
    r = run_sh("train.sh", "--help")
    assert r.returncode == 0 and "--import ZIP" in r.stdout


def test_kit_script_dry_run_and_arguments(tmp_path):
    r = run_sh("make_kaggle_kit.sh", "--dry-run", home=tmp_path)
    assert r.returncode == 0 and "no owner labels" in r.stdout
    r = run_sh("make_kaggle_kit.sh", "--nope", home=tmp_path)
    assert r.returncode == 2


def test_notebook_runs_the_same_pipeline():
    nb = json.loads((HERE / "kaggle_notebook.ipynb").read_text())
    code = "".join("".join(c["source"]) for c in nb["cells"]
                   if c["cell_type"] == "code")
    assert "pipeline.py run" in code and "--device cuda" in code
    assert "laya-outputs" in code
    assert all(c.get("outputs", []) == [] for c in nb["cells"]
               if c["cell_type"] == "code")
