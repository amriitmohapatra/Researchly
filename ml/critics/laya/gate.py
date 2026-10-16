"""The ADR-06 promotion gate for a critic model. Exit 0 only if every check
passes; the report says which failed and why.

    python ml/critics/laya/gate.py --critic-dir critic-roles \\
        --card critic-roles/MODEL_CARD.md --report heldout-eval.json \\
        --noise /tmp/nf/corpus_stats.json [--task roles]

Checks (ARCHITECTURE.md ADR-06 decision 4, PLAN S5b):

1. model card: present, every placeholder filled, the SHA-256 it quotes is
   the pinned one;
2. dataset registry: the base model and every training-data id the card
   names exist in ml/datasets.yaml and grant ``ship_model``;
3. held-out precision: for every question the model may answer, precision
   of the answers kept at its threshold is >= 0.85 on the test split, with
   at least 20 answers kept; Task B must also beat the TF-IDF baseline
   (82.6%) at full coverage; for Task A (flags) the same bar on the
   owner's own labels (``--owner-report``), because the training and test
   labels are Claude's judgments and only the owner's are independent;
4. calibration: ECE is reported (warns above 0.10);
5. fire and don't-fire tests: a test module under packages/core/tests names
   the model version and has at least one test whose name says it fires and
   one whose name says it does not;
6. noise floor: a run with the critic in place is at or below the Q3 target
   (ml/dogfood/noise_gate.py TARGET);
7. SHA-256 pin: critic.json's digest matches the ONNX file, and every other
   pinned file matches;
8. health.py entry: health.critic_status() reads the installed folder and
   reports its version, not an error;
9. no pickles in the folder (ADR-06: joblib is never loaded in production).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "packages" / "core"))
sys.path.insert(0, str(REPO / "ml" / "dogfood"))

PRECISION_GATE = 0.85
BASELINE_TASK_B = 0.826
MIN_KEPT = 20
BASE_MODEL_ID = "laya"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def registry_uses(path: Path = REPO / "ml" / "datasets.yaml") -> dict:
    """{id: [permitted_use, ...]} from ml/datasets.yaml, read line by line
    (the registry's layout is fixed; no YAML library needed)."""
    out, current = {}, None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^  - id:\s*(\S+)", line)
        if m:
            current = m.group(1)
            out[current] = []
            continue
        m = re.match(r"^    permitted_use:\s*\[(.*)\]", line)
        if m and current:
            out[current] = [u.strip() for u in m.group(1).split(",")
                            if u.strip()]
    return out


def card_training_ids(card: str) -> list:
    m = re.search(r"Registry ids:\s*([^\n(]+)", card)
    if not m:
        return []
    return [x.strip(" `.") for x in m.group(1).split(",") if x.strip(" `.")]


def precision_at_threshold(report: dict, threshold: float) -> tuple:
    """(precision, kept) of the answers at or above the threshold, from the
    per-item confidences the report carries (``items``), else from its
    risk-coverage table (the closest coverage at or above the threshold)."""
    body = report.get("after_temperature") or report.get("zero_shot") or {}
    items = report.get("items")
    if items:
        # item confidences are rounded to 6 places in reports
        kept = [i for i in items if i["confidence"] >= threshold - 1e-6]
        if not kept:
            return 0.0, 0
        return sum(i["correct"] for i in kept) / len(kept), len(kept)
    rc = body.get("risk_coverage", {})
    rows = [v for k, v in rc.items() if k != "coverage_at_gate"
            and v.get("threshold") is not None and v["threshold"] >= threshold]
    if not rows:
        return 0.0, 0
    best = max(rows, key=lambda v: v["n"])
    return best["precision"], best["n"]


def check(critic_dir: Path, card_path: Path, report_path: Path,
          noise_path: Path, task: str = "roles",
          tests_dir: Path = REPO / "packages" / "core" / "tests",
          registry: Path = REPO / "ml" / "datasets.yaml",
          owner_report_path: Optional[Path] = None) -> list:
    results = []

    def add(name, ok, detail):
        results.append({"check": name, "ok": bool(ok), "detail": detail})

    desc_path = critic_dir / "critic.json"
    try:
        desc = json.loads(desc_path.read_text())
    except (OSError, ValueError) as e:
        add("SHA-256 pin", False, f"critic.json unreadable: {e}")
        return results
    version = desc.get("model_version", "")

    # 1. model card
    try:
        card = card_path.read_text(encoding="utf-8")
        unfilled = re.findall(r"\{\{[^}]*\}\}", card)
        add("model card", not unfilled and desc.get("sha256", "") in card
            and version in card,
            "complete" if not unfilled else f"unfilled: {unfilled[:3]}")
    except OSError:
        card = ""
        add("model card", False, f"{card_path} missing")

    # 2. registry
    uses = registry_uses(registry)
    needed = [BASE_MODEL_ID] + card_training_ids(card)
    missing = [i for i in needed if "ship_model" not in uses.get(i, [])]
    add("dataset registry", not missing,
        "all grant ship_model" if not missing else
        "no ship_model for: " + ", ".join(missing))

    # 3 + 4. held-out precision and calibration
    try:
        report = json.loads(report_path.read_text())
    except (OSError, ValueError) as e:
        report = {}
        add("held-out precision", False, f"report unreadable: {e}")
    if report:
        for qid, thr in desc.get("questions", {}).items():
            prec, kept = precision_at_threshold(report, thr)
            add(f"held-out precision ({qid})",
                prec >= PRECISION_GATE and kept >= MIN_KEPT,
                f"{prec:.3f} on {kept} answers kept at threshold {thr:.2f} "
                f"(gate {PRECISION_GATE}, at least {MIN_KEPT})")
        body = report.get("after_temperature") or report.get("zero_shot") or {}
        if task == "roles":
            acc = body.get("accuracy", 0.0)
            add("beats the Task B baseline", acc > BASELINE_TASK_B,
                f"accuracy {acc:.3f} vs TF-IDF {BASELINE_TASK_B}")
        e = body.get("ece")
        add("calibration reported", e is not None,
            f"ECE {e:.3f}" + (" (warning: above 0.10)" if e and e > 0.10
                              else "") if e is not None else "no ECE")

    # 5. fire and don't-fire tests naming this model
    fire = dont = False
    for f in sorted(Path(tests_dir).glob("test_*.py")):
        text = f.read_text(encoding="utf-8")
        if version and version in text:
            names = re.findall(r"def (test_\w+)", text)
            neg = [n for n in names if re.search(r"(not|dont|never)_fire", n)]
            dont |= bool(neg)
            fire |= any("fire" in n and n not in neg for n in names)
    add("fire and don't-fire tests", fire and dont,
        f"fire={fire}, don't-fire={dont} (tests naming {version!r})")

    # 3b. Task A: the owner's own labels are the independent test (the
    # training and test labels are Claude's judgments; ADR-06, 2026-10-16)
    if task == "flags":
        owner = None
        if owner_report_path is not None:
            try:
                owner = json.loads(Path(owner_report_path).read_text())
            except (OSError, ValueError):
                owner = None
        if owner is None:
            add("independent test (owner's labels)", False,
                "not run: label paragraphs on the Label page and set "
                "RESEARCHLY_LABELS and RESEARCHLY_PARAGRAPHS (the test split "
                "only measures agreement with Claude's judgments)")
        else:
            for qid, thr in desc.get("questions", {}).items():
                prec, kept = precision_at_threshold(owner, thr)
                add("independent test (owner's labels)",
                    prec >= PRECISION_GATE and kept >= MIN_KEPT,
                    f"{prec:.3f} on {kept} of your flags kept at threshold "
                    f"{thr:.2f} (gate {PRECISION_GATE}, at least {MIN_KEPT})")

    # 6. noise floor
    try:
        from noise_gate import TARGET, summarise
        stats = json.loads(noise_path.read_text())
        if "per_1000_words" not in stats:     # run_dogfood's per-document file
            stats = summarise(stats)
        rate = stats["per_1000_words"]
        add("noise floor", rate <= TARGET, f"{rate}/1000w (target <= {TARGET})")
    except (OSError, ValueError, KeyError, TypeError, ImportError,
            AttributeError) as e:
        add("noise floor", False, f"no usable run: {e}")

    # 7. SHA pin
    onnx = critic_dir / desc.get("onnx_file", "")
    bad = []
    if not onnx.is_file() or sha256_file(onnx) != desc.get("sha256"):
        bad.append(desc.get("onnx_file", "?"))
    for rel, digest in desc.get("files", {}).items():
        p = critic_dir / rel
        if not p.is_file() or sha256_file(p) != digest:
            bad.append(rel)
    add("SHA-256 pin", not bad, "all files match" if not bad else
        "mismatch: " + ", ".join(bad))

    # 8. health.py
    from researchly import critics, health
    old = os.environ.get(critics.MODEL_DIR_ENV)
    os.environ[critics.MODEL_DIR_ENV] = str(critic_dir)
    try:
        st = health.critic_status()
    finally:
        if old is None:
            os.environ.pop(critics.MODEL_DIR_ENV, None)
        else:
            os.environ[critics.MODEL_DIR_ENV] = old
    add("health.py entry", st.state in ("disabled", "ready")
        and version in st.detail, f"{st.state}: {st.detail}")

    # 9. no pickles
    pickles = [p.name for p in critic_dir.rglob("*")
               if p.suffix in (".pkl", ".pickle", ".joblib")]
    add("no pickles", not pickles, ", ".join(pickles) or "none")
    return results


def render(results: list) -> str:
    lines = ["| Check | Result | Detail |", "|---|---|---|"]
    for r in results:
        lines.append(f"| {r['check']} | {'PASS' if r['ok'] else 'FAIL'} | "
                     f"{r['detail']} |")
    verdict = all(r["ok"] for r in results)
    lines += ["", "PROMOTE" if verdict else "NOT PROMOTED: fix the failed "
              "checks (PLAN S5 exit check records why if it ships nothing)"]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--critic-dir", type=Path, required=True)
    ap.add_argument("--card", type=Path)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--noise", type=Path, required=True)
    ap.add_argument("--task", choices=["roles", "flags"], default="roles")
    ap.add_argument("--owner-report", type=Path,
                    help="flags: evaluation on the owner's own labels")
    ap.add_argument("--json-out", type=Path,
                    help="also write the results as JSON")
    a = ap.parse_args(argv)
    results = check(a.critic_dir, a.card or a.critic_dir / "MODEL_CARD.md",
                    a.report, a.noise, a.task,
                    owner_report_path=a.owner_report)
    ok = all(r["ok"] for r in results)
    print(render(results))
    if a.json_out:
        a.json_out.write_text(json.dumps(
            {"verdict": "PROMOTE" if ok else "NOT PROMOTED",
             "checks": results}, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
