"""Assemble Laya's training, development and test files for both S5 tasks
(PLAN S5b; ARCHITECTURE.md ADR-06). Run with the engine's Python: Task A
re-checks every labelled paragraph exactly as the Label page does.

    python3.10 ml/critics/laya/assemble.py --out ~/laya-runs/2026-10-16/data \\
        [--sentences ~/.researchly/corpus/labels/sentences.jsonl] \\
        [--corpus-paragraphs ~/laya-corpus] \\
        [--owner-labels researchly-labels.json --owner-paragraphs paras.json] \\
        [--task a|b|both] [--quick]

Task A ("is this flag useful?") pools two label sets, each judged by Claude:

- synthetic drafts (``ml/critics/data/synthetic/part-{a,b,c}``; registry
  ``s5-synthetic-drafts``). Each part numbers its paragraphs 1..150, so they
  are renumbered into one sequence (part a 1-150, b 151-300, c 301-450) and
  the part is kept as a field. Split 70/15/15 by paragraph.
- published-article flags (``ml/critics/data/corpus``; registry
  ``s5-corpus-flag-judgments``), when ``rebuild.py`` has written their
  paragraphs outside the repository. Its own test split stays the test;
  15% of its train split, by article, becomes dev.

Both splits are stratified by rule and verdict, and no paragraph (no
article, for the corpus) sits on two sides. The training split's
useful/wrong ratio is evened out by repeating minority rows up to
``--max-ratio`` (train only; dev and test keep their natural ratio).

The owner's own labels (``researchly-labels.json`` from the Label page plus
the paragraphs) are the independent test: they become
``flags-test-owner.jsonl`` and are never trained on.

Task B (sentence roles) comes from the S5a weak labels: train/dev/test by
the corpus's per-article split, CC BY / CC0 articles only (so every file
can go into a private Kaggle dataset; NC articles never leave the Mac).

Writes, into ``--out`` (outside the repository):

    flags-train.jsonl  flags-dev.jsonl  flags-test.jsonl  [flags-test-owner.jsonl]
    roles-train.jsonl  roles-dev.jsonl  roles-test.jsonl
    synthetic-labels.json  synthetic-paragraphs.json   (the merged parts)
    data-report.json   counts by task, source, split, rule and verdict

Every row is Laya's training format ``{state, questions, expected}`` plus a
``meta`` object (source, rule, verdict, group; no text) that Laya ignores
and ``evaluate.py`` reads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402
from harness import critics  # noqa: E402

DATA = harness.REPO / "ml" / "critics" / "data"
SYNTHETIC = DATA / "synthetic"
CORPUS = DATA / "corpus"
PARTS = ("a", "b", "c")
SEED = 20261016
SYNTH_FRACS = {"train": 0.70, "dev": 0.15, "test": 0.15}
CORPUS_DEV_FRAC = 0.15
QUICK = {"a": {"train": 96, "dev": 48, "test": 48},
         "b": {"train": 240, "dev": 60, "test": 60}}


# --- merging the synthetic parts ----------------------------------------------------

def merge_synthetic(folder: Path = SYNTHETIC, parts=PARTS) -> tuple:
    """(labels, {paragraph: {section, text}}, {paragraph: part}) with the
    parts' paragraphs renumbered into one sequence, in part order."""
    import label_precision
    labels, paragraphs, part_of = [], {}, {}
    offset = 0
    for part in parts:
        p_rows = json.loads((folder / f"part-{part}-paragraphs.json")
                            .read_text(encoding="utf-8"))["paragraphs"]
        numbers = sorted(p["paragraph"] for p in p_rows)
        new = {old: offset + i + 1 for i, old in enumerate(numbers)}
        for p in p_rows:
            n = new[p["paragraph"]]
            paragraphs[n] = {"section": p.get("section", "introduction"),
                             "text": p["text"]}
            part_of[n] = part
        for x in label_precision.load(folder / f"part-{part}-labels.json"):
            if x.get("paragraph") not in new:
                raise ValueError(f"part {part}: label for paragraph "
                                 f"{x.get('paragraph')} has no paragraph")
            labels.append(dict(x, paragraph=new[x["paragraph"]]))
        offset += len(numbers)
    return labels, paragraphs, part_of


def write_merged(out: Path, labels: list, paragraphs: dict,
                 part_of: dict) -> None:
    (out / "synthetic-labels.json").write_text(json.dumps(
        {"version": 1, "labels": labels}, indent=1), encoding="utf-8")
    (out / "synthetic-paragraphs.json").write_text(json.dumps(
        {"version": 1, "note": "parts a, b, c of ml/critics/data/synthetic, "
         "renumbered into one sequence",
         "paragraphs": [{"paragraph": n, "part": part_of[n], **paragraphs[n]}
                        for n in sorted(paragraphs)]},
        ensure_ascii=False, indent=1), encoding="utf-8")


# --- flags -> rows ---------------------------------------------------------------

def flag_items(labels: list, paragraphs: dict, nlp=None) -> tuple:
    """Matched flags with their paragraph: ([{paragraph, state, gold, rule,
    category}], skipped counts). One paragraph at a time, so every item
    keeps the paragraph it came from."""
    import zero_shot
    by_para: dict = defaultdict(list)
    for x in labels:
        by_para[x.get("paragraph")].append(x)
    out, skipped = [], Counter()
    for p in sorted(by_para, key=lambda k: (str(type(k)), k)):
        items, sk = zero_shot.flag_items(by_para[p], paragraphs, nlp)
        skipped.update(sk)
        for state, gold, rule, cat in items:
            out.append({"paragraph": p, "state": state, "gold": gold,
                        "rule": rule, "category": cat})
    return out, dict(skipped)


def flag_row(item: dict, source: str, group: str, **meta) -> dict:
    q = critics.FLAG_USEFUL
    return {"state": item["state"],
            "questions": {q.id: harness.laya_question(q)},
            "expected": {q.id: "A" if item["gold"] == "yes" else "B"},
            "meta": dict({"source": source, "group": group,
                          "rule": item["rule"], "category": item["category"],
                          "verdict": "useful" if item["gold"] == "yes"
                          else "wrong"}, **meta)}


# --- splitting ------------------------------------------------------------------

def _tiebreak(seed: int, key) -> str:
    return hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()


def grouped_split(groups: dict, fracs: dict, seed: int = SEED) -> dict:
    """Assign whole groups to splits so every stratum (here rule:verdict)
    lands in each split close to its fraction: iterative stratification
    (rarest strata first; each group goes where its strata are most
    short). ``groups``: {group key: [stratum, ...]} -> {group key: split}.
    Deterministic for a seed."""
    totals = Counter(s for strata in groups.values() for s in strata)
    n_all = sum(len(v) for v in groups.values())
    want = {sp: {s: f * c for s, c in totals.items()} for sp, f in fracs.items()}
    want_n = {sp: f * n_all for sp, f in fracs.items()}
    have = {sp: Counter() for sp in fracs}
    have_n = Counter()
    order = sorted(groups, key=lambda k: (min((totals[s] for s in groups[k]),
                                              default=0), _tiebreak(seed, k)))
    out = {}
    for k in order:
        strata = groups[k]

        def score(sp):
            # relative shortfall (share of each target still unfilled), so a
            # large split does not soak up the big groups; then overall size
            need = sum((want[sp][s] - have[sp][s]) / want[sp][s]
                       for s in strata if want[sp][s] > 0)
            size = (want_n[sp] - have_n[sp] - len(strata)) / want_n[sp] \
                if want_n[sp] else -1.0
            return (round(need / max(1, len(strata)) + size, 9),
                    _tiebreak(seed, f"{k}:{sp}"))
        sp = max(fracs, key=score)
        out[k] = sp
        have[sp].update(strata)
        have_n[sp] += len(strata)
    return out


def balance(rows: list, max_ratio: float, seed: int = SEED) -> tuple:
    """Repeat minority-verdict rows (seeded, without replacement until the
    pool is used up) so majority / minority <= max_ratio. Returns
    (rows, report)."""
    by = defaultdict(list)
    for r in rows:
        by[r["meta"]["verdict"]].append(r)
    before = {k: len(v) for k, v in sorted(by.items())}
    rep = {"before": before, "max_ratio": max_ratio, "added": 0}
    if len(by) < 2 or not max_ratio or max_ratio <= 0:
        rep["after"] = before
        return rows, rep
    (maj, maj_rows), (mino, min_rows) = sorted(by.items(),
                                               key=lambda kv: -len(kv[1]))
    target = math.ceil(len(maj_rows) / max_ratio)
    add = max(0, target - len(min_rows))
    rng = random.Random(seed)
    extra = []
    while len(extra) < add:
        pool = list(min_rows)
        rng.shuffle(pool)
        extra.extend(pool[:add - len(extra)])
    extra = [dict(r, meta=dict(r["meta"], repeated=True)) for r in extra]
    out = rows + extra
    random.Random(seed + 1).shuffle(out)
    rep["added"] = len(extra)
    rep["after"] = dict(Counter(r["meta"]["verdict"] for r in out))
    rep["ratio_before"] = round(len(maj_rows) / max(1, len(min_rows)), 3)
    rep["ratio_after"] = round(len(maj_rows) / max(1, len(min_rows) + add), 3)
    return out, rep


def _cap(rows: list, n: Optional[int], seed: int = SEED) -> list:
    """A deterministic sample of at most n rows, keeping the verdict mix."""
    if not n or len(rows) <= n:
        return rows
    rows = sorted(rows, key=lambda r: _tiebreak(seed, json.dumps(
        r["meta"], sort_keys=True) + r["state"][:80]))
    by = defaultdict(list)
    for r in rows:
        by[r["meta"].get("verdict") or r["meta"].get("role")].append(r)
    out = []
    while len(out) < n and any(by.values()):
        for k in sorted(by):
            if by[k] and len(out) < n:
                out.append(by[k].pop())
    return out


# --- Task A ---------------------------------------------------------------------

def task_a(out: Path, *, corpus_paragraphs: Optional[Path],
           owner_labels: Optional[Path], owner_paragraphs: Optional[Path],
           max_ratio: float, quick: bool, nlp=None,
           synthetic_dir: Path = SYNTHETIC, corpus_dir: Path = CORPUS) -> dict:
    import label_precision
    report: dict = {"sources": {}, "notes": []}
    splits: dict = {"train": [], "dev": [], "test": []}

    # synthetic drafts
    labels, paragraphs, part_of = merge_synthetic(synthetic_dir)
    write_merged(out, labels, paragraphs, part_of)
    items, skipped = flag_items(labels, paragraphs, nlp)
    groups = defaultdict(list)
    for it in items:
        groups[it["paragraph"]].append(f"{it['rule']}:{it['gold']}")
    where = grouped_split(groups, SYNTH_FRACS)
    for it in items:
        p = it["paragraph"]
        splits[where[p]].append(flag_row(it, "synthetic", f"syn-{p}",
                                         part=part_of[p], paragraph=p))
    report["sources"]["synthetic"] = {
        "registry": "s5-synthetic-drafts", "labels": len(labels),
        "paragraphs": len(paragraphs), "matched": len(items),
        "skipped": skipped}

    # published-article flags (labels committed, paragraphs rebuilt locally)
    tr_p = corpus_paragraphs / "train-paragraphs.json" if corpus_paragraphs \
        else None
    te_p = corpus_paragraphs / "test-paragraphs.json" if corpus_paragraphs \
        else None
    if not (corpus_dir / "train-labels.json").exists():
        report["notes"].append("corpus flag labels not in this checkout; "
                               "synthetic data only")
    elif not (tr_p and tr_p.exists()):
        report["notes"].append(
            "corpus paragraphs not rebuilt (run ml/critics/data/corpus/"
            "rebuild.py --out <dir> and pass --corpus-paragraphs <dir>); "
            "synthetic data only")
    else:
        index = {p["paragraph"]: p for p in json.loads(
            (corpus_dir / "paragraph-index.json").read_text())["paragraphs"]}
        src = {"registry": "s5-corpus-flag-judgments"}
        tr_items, tr_sk = flag_items(
            label_precision.load(corpus_dir / "train-labels.json"),
            harness.label_paragraphs(tr_p), nlp)
        art = defaultdict(list)
        for it in tr_items:
            art[index[it["paragraph"]]["pmcid"]].append(
                f"{it['rule']}:{it['gold']}")
        where = grouped_split(art, {"train": 1 - CORPUS_DEV_FRAC,
                                    "dev": CORPUS_DEV_FRAC})
        for it in tr_items:
            meta = index[it["paragraph"]]
            splits[where[meta["pmcid"]]].append(flag_row(
                it, "corpus", f"corpus-{meta['pmcid']}", paragraph=it[
                    "paragraph"], pmcid=meta["pmcid"],
                discipline=meta.get("discipline")))
        src["train_labels"] = {"matched": len(tr_items), "skipped": tr_sk}
        if te_p and te_p.exists():
            te_items, te_sk = flag_items(
                label_precision.load(corpus_dir / "test-labels.json"),
                harness.label_paragraphs(te_p), nlp)
            for it in te_items:
                meta = index[it["paragraph"]]
                splits["test"].append(flag_row(
                    it, "corpus", f"corpus-{meta['pmcid']}",
                    paragraph=it["paragraph"], pmcid=meta["pmcid"],
                    discipline=meta.get("discipline")))
            src["test_labels"] = {"matched": len(te_items), "skipped": te_sk}
        report["sources"]["corpus"] = src

    if quick:
        splits = {k: _cap(v, QUICK["a"][k]) for k, v in splits.items()}
        report["notes"].append("--quick: a small sample of each split")
    splits["train"], report["balance"] = balance(splits["train"], max_ratio)

    files = {k: f"flags-{k}.jsonl" for k in splits}
    for k, rows in splits.items():
        write_jsonl(rows, out / files[k])

    # the owner's own labels: the independent test, never trained on
    if owner_labels and owner_paragraphs:
        rows, report["sources"]["owner"] = owner_test(
            out, owner_labels, owner_paragraphs, nlp)
        files["test-owner"] = "flags-test-owner.jsonl"
        splits["test-owner"] = rows
    report["files"] = files
    report["counts"] = _counts(splits)
    report["overlap"] = _overlap(splits)
    return report


def owner_test(out: Path, labels: Path, paragraphs: Path, nlp=None) -> tuple:
    """flags-test-owner.jsonl from the owner's Label-page export and the
    paragraphs' text (local only). Never a training file."""
    import label_precision
    items, skipped = flag_items(label_precision.load(labels),
                                harness.label_paragraphs(paragraphs), nlp)
    rows = [flag_row(it, "owner", f"owner-{it['paragraph']}",
                     paragraph=it["paragraph"]) for it in items]
    write_jsonl(rows, out / "flags-test-owner.jsonl")
    return rows, {"matched": len(items), "skipped": skipped,
                  "use": "independent test only",
                  "by_verdict": dict(Counter(r["meta"]["verdict"]
                                             for r in rows))}


def _counts(splits: dict) -> dict:
    out = {}
    for k, rows in splits.items():
        m = [r["meta"] for r in rows]
        out[k] = {"rows": len(rows),
                  "by_source": dict(Counter(x["source"] for x in m)),
                  "by_verdict": dict(Counter(x["verdict"] for x in m)),
                  "by_source_verdict": dict(Counter(
                      f"{x['source']}:{x['verdict']}" for x in m)),
                  "by_rule": dict(sorted(Counter(
                      f"{x['rule']}:{x['verdict']}" for x in m).items())),
                  "groups": len({x["group"] for x in m})}
    return out


def _overlap(splits: dict) -> dict:
    """Groups (paragraphs / articles) seen in more than one split; must be
    empty."""
    seen = defaultdict(set)
    for k, rows in splits.items():
        for r in rows:
            seen[r["meta"]["group"]].add(k)
    return {g: sorted(s) for g, s in seen.items() if len(s) > 1}


# --- Task B ---------------------------------------------------------------------

def task_b(out: Path, sentences: Path, *, max_per_role: int,
           quick: bool) -> dict:
    import finetune
    rows = harness.read_jsonl(sentences)
    splits = {"train": finetune.role_rows(rows, "train",
                                          max_per_role=max_per_role),
              "dev": finetune.role_rows(rows, "dev"),
              "test": finetune.role_rows(rows, "test")}
    for k, rs in splits.items():
        for r in rs:
            r["meta"] = dict(r["meta"], source="s5a-corpus",
                             role=r["expected"]["sentence-role"],
                             group=f"corpus-{r['meta']['pmcid']}")
    if quick:
        splits = {k: _cap(v, QUICK["b"][k]) for k, v in splits.items()}
    for k, rs in splits.items():
        write_jsonl(rs, out / f"roles-{k}.jsonl")
    arts = {k: {r["meta"]["pmcid"] for r in rs} for k, rs in splits.items()}
    return {"registry": "s5a-oa-corpus-cc-by",
            "source": str(sentences),
            "files": {k: f"roles-{k}.jsonl" for k in splits},
            "counts": {k: {"rows": len(rs), "articles": len(arts[k]),
                           "by_role": dict(sorted(Counter(
                               r["meta"]["role"] for r in rs).items())),
                           "by_discipline": dict(sorted(Counter(
                               r["meta"]["discipline"] for r in rs).items()))}
                       for k, rs in splits.items()},
            "articles_in_two_splits": len((arts["train"] & arts["dev"]) |
                                          (arts["train"] & arts["test"]) |
                                          (arts["dev"] & arts["test"])),
            "max_per_role": max_per_role,
            "note": "CC BY / CC0 articles only (use: train); split by "
                    "article (common.split_of)"}


def write_jsonl(rows: list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def engine_health(nlp=None) -> list:
    try:
        from researchly import health
        return [s.to_dict() for s in health.engine_status(nlp=nlp)]
    except Exception as e:                        # report, never fail here
        return [{"tier": "unknown", "ok": False, "detail": repr(e)}]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--task", choices=["a", "b", "both", "owner"],
                    default="both",
                    help="owner: only the owner's test file (e.g. after "
                         "importing a Kaggle run)")
    ap.add_argument("--sentences", type=Path,
                    help="Task B weak labels (sentences.jsonl)")
    ap.add_argument("--corpus-paragraphs", type=Path,
                    help="folder rebuild.py wrote {train,test}-paragraphs.json to")
    ap.add_argument("--owner-labels", type=Path)
    ap.add_argument("--owner-paragraphs", type=Path)
    ap.add_argument("--max-ratio", type=float, default=1.5,
                    help="Task A train: majority/minority verdict ratio "
                         "above which minority rows are repeated (0: off)")
    ap.add_argument("--max-per-role", type=int, default=4000)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--max-not-found", type=float, default=0.10,
                    help="fail if more than this share of decided labels "
                         "no longer matches its flag (engine drift, or a "
                         "tier such as grammar is off)")
    a = ap.parse_args(argv)
    out = a.out.resolve()
    if out == harness.REPO or harness.REPO in out.parents:
        ap.error("--out must be outside the repository (it holds text)")
    if bool(a.owner_labels) != bool(a.owner_paragraphs):
        ap.error("--owner-labels and --owner-paragraphs go together")
    out.mkdir(parents=True, exist_ok=True)
    report = {"version": 1, "seed": SEED, "quick": a.quick}
    rc = 0
    if a.task == "owner":
        if not a.owner_labels:
            ap.error("--task owner needs --owner-labels and --owner-paragraphs")
        from researchly import api
        rows, rep = owner_test(out, a.owner_labels, a.owner_paragraphs,
                               api.get_nlp())
        report["owner"] = rep
        (out / "owner-report.json").write_text(json.dumps(report, indent=1))
        print(json.dumps(rep, indent=1))
        return 0 if rows else 3
    if a.task in ("a", "both"):
        from researchly import api
        nlp = api.get_nlp()
        report["engine_health"] = engine_health(nlp)
        report["task_a"] = task_a(
            out, corpus_paragraphs=a.corpus_paragraphs,
            owner_labels=a.owner_labels, owner_paragraphs=a.owner_paragraphs,
            max_ratio=a.max_ratio, quick=a.quick, nlp=nlp)
        for name, src in report["task_a"]["sources"].items():
            parts = [src] + [src[k] for k in ("train_labels", "test_labels")
                             if k in src]
            for part in parts:
                if "skipped" not in part:
                    continue
                nf = part["skipped"].get("flag not found", 0)
                share = nf / max(1, nf + part.get("matched", 0))
                if share > a.max_not_found:
                    report["task_a"]["notes"].append(
                        f"{name}: {nf} labels no longer match their flag "
                        f"({share:.0%}); check the engine's health "
                        "(the grammar tier needs Java) before training")
                    rc = 3
        if report["task_a"]["overlap"]:
            rc = 4
    if a.task in ("b", "both"):
        if not a.sentences or not a.sentences.exists():
            report["task_b"] = {"error": "no weak labels: run ml/corpus/"
                                         "weak_labels.py first"}
            rc = rc or 2
        else:
            report["task_b"] = task_b(out, a.sentences,
                                      max_per_role=a.max_per_role,
                                      quick=a.quick)
    (out / "data-report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(summary(report), indent=1))
    return rc


def summary(report: dict) -> dict:
    """The short version train.sh prints."""
    s = {}
    if "task_a" in report:
        a = report["task_a"]
        s["task_a"] = {k: {"rows": v["rows"], "by_source_verdict":
                           v["by_source_verdict"]}
                       for k, v in a["counts"].items()}
        s["task_a_balance"] = a["balance"]
        s["task_a_notes"] = a["notes"]
    if "task_b" in report:
        b = report["task_b"]
        s["task_b"] = b.get("error") or {k: v["rows"] for k, v in
                                         b["counts"].items()}
    return s


if __name__ == "__main__":
    sys.exit(main())
