#!/usr/bin/env bash
# Pack everything ml/critics/laya/kaggle_notebook.ipynb needs into one zip
# (PLAN S5b): the harness scripts, the requirements, and the assembled
# training/dev/test files for both tasks.
#
#   bash ml/critics/laya/make_kaggle_kit.sh            # -> ~/laya-kit.zip
#   bash ml/critics/laya/make_kaggle_kit.sh --quick    # a small kit for a smoke run
#
# Upload the zip to Kaggle as a PRIVATE dataset (README: "Train on Kaggle").
# What is in it: synthetic paragraphs written for Researchly (ours), and
# sentences and paragraphs of CC BY / CC0 open-access articles (allowed in a
# private dataset; attribution in ATTRIBUTION.md, with the manifest). Never
# your own labelled paragraphs: they stay on your Mac, and train.sh --import
# tests the Kaggle model on them there. Never NC/ND articles.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
PY="${PYTHON:-python3.10}"
CACHE="${RESEARCHLY_CORPUS_CACHE:-$HOME/.researchly/corpus}"
CORPUS_PARAS="${LAYA_CORPUS_PARAGRAPHS:-$HOME/laya-corpus}"
OUT="$HOME/laya-kit.zip"
QUICK=0
DATA=""
DRY=0

usage() {
  cat <<'EOF'
Usage: bash ml/critics/laya/make_kaggle_kit.sh [--quick] [--out ZIP] [--data DIR] [--dry-run]

  --quick      a small kit (a few hundred examples) to check the notebook end to end
  --out ZIP    where to write the kit (default ~/laya-kit.zip)
  --data DIR   use files assemble.py already wrote (default: assemble afresh)
  --dry-run    say what would be packed, change nothing
EOF
}
die() { echo "make_kaggle_kit.sh: $*" >&2; exit 2; }

while [ $# -gt 0 ]; do
  case "$1" in
    --quick) QUICK=1; shift ;;
    --out) [ $# -ge 2 ] || die "--out needs a value"; OUT="$2"; shift 2 ;;
    --data) [ $# -ge 2 ] || die "--data needs a value"; DATA="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; die "unknown option: $1" ;;
  esac
done
case "$OUT" in "$REPO"/*) die "--out must be outside the repository" ;; esac
command -v "$PY" >/dev/null 2>&1 || die "$PY not found (set PYTHON=/path/to/python3.10)"
command -v zip >/dev/null 2>&1 || die "zip not found"

in_engine() { (cd "$REPO" && PYTHONPATH="$REPO/packages/core" "$@"); }
WORK="$HOME/laya-runs/kaggle-kit"
[ "$QUICK" = 1 ] && WORK="$WORK-quick"
[ -n "$DATA" ] || DATA="$WORK/data"

if [ "$DRY" = 1 ]; then
  echo "Would: fetch the corpus into $CACHE if missing, rebuild the article paragraphs into $CORPUS_PARAS,"
  echo "       assemble into $DATA (no owner labels), and zip scripts + data into $OUT"
  exit 0
fi

if [ ! -f "$CACHE/labels/sentences.jsonl" ]; then
  echo "Fetching the open-access corpus into $CACHE (~10 min) ..."
  in_engine "$PY" ml/corpus/harvest.py mirror --cache "$CACHE"
  in_engine "$PY" ml/corpus/weak_labels.py --cache "$CACHE"
fi
if [ -f "$REPO/ml/critics/data/corpus/rebuild.py" ] && [ ! -f "$CORPUS_PARAS/train-paragraphs.json" ]; then
  in_engine "$PY" ml/critics/data/corpus/rebuild.py --out "$CORPUS_PARAS" --cache "$CACHE"
fi
if [ ! -f "$DATA/data-report.json" ]; then
  set -- --out "$DATA" --task both --sentences "$CACHE/labels/sentences.jsonl"
  [ -f "$CORPUS_PARAS/train-paragraphs.json" ] && set -- "$@" --corpus-paragraphs "$CORPUS_PARAS"
  [ "$QUICK" = 1 ] && set -- "$@" --quick
  in_engine "$PY" ml/critics/laya/assemble.py "$@"
fi

STAGE="$WORK/stage/laya-kit"
rm -rf "$WORK/stage"
mkdir -p "$STAGE/ml/critics/laya" "$STAGE/packages/core/researchly/critics" \
  "$STAGE/ml/corpus" "$STAGE/data"
for f in harness.py finetune.py evaluate.py export_onnx.py pipeline.py zero_shot.py \
         MODEL_CARD.md requirements.txt; do
  cp "$HERE/$f" "$STAGE/ml/critics/laya/"
done
# Kaggle's image already has a CUDA build of torch: keep it.
grep -v '^torch' "$HERE/requirements.txt" > "$STAGE/ml/critics/laya/requirements-kaggle.txt"
cp "$REPO/packages/core/researchly/__init__.py" "$STAGE/packages/core/researchly/"
cp "$REPO/packages/core/researchly/critics/"*.py "$STAGE/packages/core/researchly/critics/"
cp "$REPO/ml/corpus/manifest.jsonl" "$STAGE/ml/corpus/"
[ -f "$REPO/ml/critics/data/corpus/paragraph-index.json" ] && \
  cp "$REPO/ml/critics/data/corpus/paragraph-index.json" "$STAGE/ml/corpus/flag-paragraph-index.json"
for f in "$DATA"/flags-train.jsonl "$DATA"/flags-dev.jsonl "$DATA"/flags-test.jsonl \
         "$DATA"/roles-train.jsonl "$DATA"/roles-dev.jsonl "$DATA"/roles-test.jsonl \
         "$DATA"/data-report.json; do
  [ -f "$f" ] && cp "$f" "$STAGE/data/"
done
# never the owner's text, even if an earlier run assembled it here
rm -f "$STAGE/data/flags-test-owner.jsonl"

cat > "$STAGE/ATTRIBUTION.md" <<'EOF'
# What is in this kit

- `data/flags-*.jsonl` (Task A) hold two kinds of paragraph:
  - synthetic research-draft paragraphs written for Researchly (Researchly's
    own, MIT; registry id `s5-synthetic-drafts`);
  - paragraphs of open-access research articles licensed **CC BY 4.0,
    CC BY (unversioned) or CC0** (registry ids `s5-corpus-flag-judgments`,
    `s5a-oa-corpus-cc-by`). Each row's `meta.pmcid` names its article.
- `data/roles-*.jsonl` (Task B) hold sentences of the structured abstracts
  of CC BY / CC0 articles; `meta.pmcid` names each one.

Attribution: every article's PMCID, DOI, journal, year, licence and the
licence evidence read from its own JATS are in `ml/corpus/manifest.jsonl`
(`flag-paragraph-index.json` maps the Task A paragraphs to their articles).
No CC BY-NC/ND/SA article is included. Keep this dataset private: the text
is here for training only and is not redistributed (ship_text is not granted).
EOF

COMMIT="$(cd "$REPO" && git rev-parse --short HEAD 2>/dev/null || true)"
"$PY" - "$STAGE" "$QUICK" "$COMMIT" <<'PYEOF'
import json, sys, time
from pathlib import Path
stage, quick, commit = Path(sys.argv[1]), sys.argv[2] == "1", sys.argv[3]
counts = {p.stem: sum(1 for l in p.open() if l.strip()) for p in sorted((stage / "data").glob("*.jsonl"))}
(stage / "laya-kit.json").write_text(json.dumps(
    {"kit": 1, "created": time.strftime("%Y-%m-%d %H:%M"), "quick": quick,
     "commit": commit, "files": counts}, indent=1))
print(json.dumps(counts, indent=1))
PYEOF

rm -f "$OUT"
mkdir -p "$(dirname "$OUT")"
(cd "$WORK/stage" && zip -qr "$OUT" laya-kit)
echo "Kit: $OUT ($(du -h "$OUT" | cut -f1)). Upload it to Kaggle as a private dataset (README)."
