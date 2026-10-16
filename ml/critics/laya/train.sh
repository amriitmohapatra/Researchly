#!/usr/bin/env bash
# Train Laya, Researchly's S5 critic, end to end in one command (PLAN S5b).
#
#   bash ml/critics/laya/train.sh                 # both tasks, on this Mac
#   bash ml/critics/laya/train.sh --quick         # a few-minute smoke run first
#   bash ml/critics/laya/train.sh --dry-run       # print the plan, run nothing
#   bash ml/critics/laya/train.sh --import ~/Downloads/laya-outputs.zip   # a Kaggle run
#
# What it does (each step is skipped when its output already exists, so
# running the same command again resumes):
#   1. a Python venv for the ML libraries (~/.venvs/laya, requirements.txt);
#   2. the open-access corpus into ~/.researchly/corpus (the committed
#      manifest's articles; harvest.py mirror), its weak labels, and the
#      published-article paragraphs behind the corpus flag labels (rebuild.py);
#   3. the training files (assemble.py, run with the engine's python3.10);
#   4. training, evaluation, temperature and threshold, INT8 ONNX export
#      (pipeline.py, in the venv), Task B first, then Task A;
#   5. the noise floor (ml/dogfood, if the private corpus is here), the
#      promotion gate (gate.py), and installation into the engine's critic
#      folder only if the gate says PROMOTE;
#   6. a plain-language summary (also saved as SUMMARY.txt in the run folder).
#
# Your own labels, the independent test (never trained on):
#   RESEARCHLY_LABELS=~/Downloads/researchly-labels.json \
#   RESEARCHLY_PARAGRAPHS=~/researchly-paragraphs.json bash ml/critics/laya/train.sh
#
# Written for macOS's bash 3.2 as well as Linux.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"

TASK="both"
QUICK=0
DEVICE=""
DRY=0
IMPORT=""
RUN_DIR=""
EPOCHS=""
NO_EXPORT=0
PY="${PYTHON:-python3.10}"
VENV="${LAYA_VENV:-$HOME/.venvs/laya}"
CACHE="${RESEARCHLY_CORPUS_CACHE:-$HOME/.researchly/corpus}"
CORPUS_PARAS="${LAYA_CORPUS_PARAGRAPHS:-$HOME/laya-corpus}"
CRITIC_HOME="${RESEARCHLY_CRITIC_DIR:-$HOME/.researchly/models/critic}"
OWNER_LABELS="${RESEARCHLY_LABELS:-}"
OWNER_PARAS="${RESEARCHLY_PARAGRAPHS:-}"

usage() {
  cat <<'EOF'
Usage: bash ml/critics/laya/train.sh [options]

  --task a|b|both     a = "is this flag useful?", b = sentence roles (default both)
  --quick             tiny smoke run (a few hundred examples, 1 epoch) to check
                      everything works; prints the measured speed
  --device cpu|mps|cuda
                      default: mps on Apple Silicon, cuda with an NVIDIA GPU, else cpu
  --dry-run           print the plan and the steps, change nothing
  --import ZIP        evaluate, gate and install a run trained on Kaggle
                      (laya-outputs.zip from kaggle_notebook.ipynb)
  --run-dir DIR       where this run lives (default ~/laya-runs/<date>[-quick])
  --epochs N          override the epochs chosen from the data size
  --no-export         stop after evaluating the checkpoint (no ONNX, no gate)
  -h, --help          this help

Environment: PYTHON (engine's Python, default python3.10), LAYA_VENV,
RESEARCHLY_CORPUS_CACHE, RESEARCHLY_LABELS + RESEARCHLY_PARAGRAPHS (your own
labels: the independent test, never trained on).
EOF
}

die() { echo "train.sh: $*" >&2; exit 2; }
need_value() { [ $# -ge 2 ] && [ -n "$2" ] || die "$1 needs a value"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --task) need_value "$@"; TASK="$2"; shift 2 ;;
    --task=*) TASK="${1#*=}"; shift ;;
    --quick) QUICK=1; shift ;;
    --device) need_value "$@"; DEVICE="$2"; shift 2 ;;
    --device=*) DEVICE="${1#*=}"; shift ;;
    --dry-run) DRY=1; shift ;;
    --import) need_value "$@"; IMPORT="$2"; shift 2 ;;
    --import=*) IMPORT="${1#*=}"; shift ;;
    --run-dir) need_value "$@"; RUN_DIR="$2"; shift 2 ;;
    --epochs) need_value "$@"; EPOCHS="$2"; shift 2 ;;
    --no-export) NO_EXPORT=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; die "unknown option: $1" ;;
  esac
done

case "$TASK" in a|b|both) ;; *) die "--task must be a, b or both (got '$TASK')" ;; esac
if [ -z "$DEVICE" ]; then
  if [ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ]; then DEVICE=mps
  elif command -v nvidia-smi >/dev/null 2>&1; then DEVICE=cuda
  else DEVICE=cpu; fi
fi
case "$DEVICE" in cpu|mps|cuda) ;; *) die "--device must be cpu, mps or cuda (got '$DEVICE')" ;; esac
if [ -n "$EPOCHS" ]; then
  case "$EPOCHS" in ''|*[!0-9]*) die "--epochs must be a whole number" ;; esac
fi
if [ -n "$IMPORT" ] && [ ! -f "$IMPORT" ]; then die "--import: no such file: $IMPORT"; fi
if [ -n "$OWNER_LABELS" ] || [ -n "$OWNER_PARAS" ]; then
  [ -n "$OWNER_LABELS" ] && [ -n "$OWNER_PARAS" ] || \
    die "set both RESEARCHLY_LABELS and RESEARCHLY_PARAGRAPHS (or neither)"
  [ -f "$OWNER_LABELS" ] || die "RESEARCHLY_LABELS: no such file: $OWNER_LABELS"
  [ -f "$OWNER_PARAS" ] || die "RESEARCHLY_PARAGRAPHS: no such file: $OWNER_PARAS"
fi
command -v "$PY" >/dev/null 2>&1 || die "$PY not found. Install Python 3.10 (brew install python@3.10) or set PYTHON=/path/to/python3.10"

STAMP="$(date +%Y-%m-%d)"
if [ -z "$RUN_DIR" ]; then
  SUFFIX=""
  [ "$QUICK" = 1 ] && SUFFIX="-quick"
  [ -n "$IMPORT" ] && SUFFIX="-kaggle"
  RUN_DIR="$HOME/laya-runs/$STAMP$SUFFIX"
fi
case "$RUN_DIR" in "$REPO"|"$REPO"/*) die "--run-dir must be outside the repository (it holds text and weights)" ;; esac
DATA="$RUN_DIR/data"
TASKS="b a"
[ "$TASK" = a ] && TASKS="a"
[ "$TASK" = b ] && TASKS="b"
TASK_TEXT="Task B, then Task A"
[ "$TASK" = a ] && TASK_TEXT="Task A"
[ "$TASK" = b ] && TASK_TEXT="Task B"

# --- helpers ------------------------------------------------------------------------
step_n=0
say() { printf '\n[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
step() {           # step "what" command args...
  step_n=$((step_n + 1))
  local what="$1"; shift
  if [ "$DRY" = 1 ]; then
    if [ "$(type -t "$1")" = function ]; then printf '  %2d. %s\n' "$step_n" "$what"
    else printf '  %2d. %s\n      would run: %s\n' "$step_n" "$what" "$*"; fi
  else
    say "$step_n. $what"
    "$@"
  fi
}
skip() {
  step_n=$((step_n + 1))
  if [ "$DRY" = 1 ]; then printf '  %2d. %s\n' "$step_n" "skip: $*"
  else say "$step_n. skip: $*"; fi
}
in_engine() { (cd "$REPO" && PYTHONPATH="$REPO/packages/core${PYTHONPATH:+:$PYTHONPATH}" "$@"); }
xml_count() { if [ -d "$CACHE/xml" ]; then ls "$CACHE/xml" | grep -c '\.xml$' || true; else echo 0; fi; }

setup_venv() {
  local stamp="$VENV/.researchly-requirements"
  local want
  want="$("$PY" -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$HERE/requirements.txt")"
  if [ ! -x "$VENV/bin/python" ]; then
    "$PY" -m venv "$VENV"
  fi
  if [ ! -f "$stamp" ] || [ "$(cat "$stamp")" != "$want" ]; then
    "$VENV/bin/python" -m pip install --quiet --upgrade pip
    "$VENV/bin/python" -m pip install --quiet -r "$HERE/requirements.txt"
    echo "$want" > "$stamp"
  fi
  "$VENV/bin/python" -c 'import torch, laya, onnxruntime; print("venv ready: torch", torch.__version__, "laya", laya.__version__)'
}

check_engine() {
  in_engine "$PY" - <<'PYEOF' || die "the engine's Python cannot run Researchly. Run: $PY -m pip install -r packages/core/requirements.txt && $PY -m spacy download en_core_web_sm"
import spacy, symspellpy  # noqa: F401
spacy.load("en_core_web_sm")
from researchly import health
print("engine:", health.summary_line(health.engine_status(probe=True)))
PYEOF
}

harvest_corpus() {
  in_engine "$PY" ml/corpus/harvest.py mirror --cache "$CACHE"
  in_engine "$PY" ml/corpus/weak_labels.py --cache "$CACHE"
}

assemble() {
  local sig="$TASK $QUICK $OWNER_LABELS $OWNER_PARAS"
  if [ -f "$DATA/.assembled" ] && [ "$(cat "$DATA/.assembled")" = "$sig" ]; then
    echo "  data already assembled in $DATA"
    return 0
  fi
  set -- --out "$DATA" --task "$TASK"
  [ "$QUICK" = 1 ] && set -- "$@" --quick
  [ -f "$CACHE/labels/sentences.jsonl" ] && set -- "$@" --sentences "$CACHE/labels/sentences.jsonl"
  [ -f "$CORPUS_PARAS/train-paragraphs.json" ] && set -- "$@" --corpus-paragraphs "$CORPUS_PARAS"
  [ -n "$OWNER_LABELS" ] && set -- "$@" --owner-labels "$OWNER_LABELS" --owner-paragraphs "$OWNER_PARAS"
  in_engine "$PY" ml/critics/laya/assemble.py "$@"
  echo "$sig" > "$DATA/.assembled"
}

train_eval_export() {
  mkdir -p "$RUN_DIR/logs"
  set -- run --task "$TASK" --data "$DATA" --run "$RUN_DIR" --device "$DEVICE"
  [ "$QUICK" = 1 ] && set -- "$@" --quick
  [ -n "$EPOCHS" ] && set -- "$@" --epochs "$EPOCHS"
  [ "$NO_EXPORT" = 1 ] && set -- "$@" --no-export
  (cd "$REPO" && "$VENV/bin/python" ml/critics/laya/pipeline.py "$@") 2>&1 | tee -a "$RUN_DIR/logs/pipeline.log"
  return "${PIPESTATUS[0]}"
}

import_zip() {
  local tmp="$RUN_DIR/.import"
  rm -rf "$tmp"; mkdir -p "$tmp"
  unzip -q "$IMPORT" -d "$tmp"
  local root="$tmp"
  [ -d "$tmp/laya-outputs" ] && root="$tmp/laya-outputs"
  [ -d "$root/data" ] || die "$IMPORT has no data/ folder: is it laya-outputs.zip from the Kaggle notebook?"
  cp -R "$root"/. "$RUN_DIR"/
  rm -rf "$tmp"
  echo "  imported into $RUN_DIR"
}

owner_test() {
  in_engine "$PY" ml/critics/laya/assemble.py --task owner --out "$DATA" \
    --owner-labels "$OWNER_LABELS" --owner-paragraphs "$OWNER_PARAS"
}

evaluate_imported() {
  local t
  for t in $TASKS; do
    if [ -f "$RUN_DIR/$t/critic/critic.json" ]; then
      (cd "$REPO" && "$VENV/bin/python" ml/critics/laya/pipeline.py evaluate --task "$t" --data "$DATA" --run "$RUN_DIR") 2>&1 | tee -a "$RUN_DIR/logs/import.log"
    else
      echo "  no exported critic for task $t in the import"
    fi
  done
}

noise_floor() {
  mkdir -p "$RUN_DIR/noise"
  (cd "$REPO/ml/dogfood" && RESEARCHLY_CORPUS_OUT="$RUN_DIR/noise" \
     PYTHONPATH="$REPO/packages/core" "$PY" run_dogfood.py) > "$RUN_DIR/noise/run.log" 2>&1
  tail -n 3 "$RUN_DIR/noise/run.log" | head -n 1
}

run_gate() {
  local t name rc
  for t in $TASKS; do
    [ -f "$RUN_DIR/$t/critic/critic.json" ] || { echo "  task $t: nothing exported, no gate"; continue; }
    name=roles; [ "$t" = a ] && name=flags
    set -- --critic-dir "$RUN_DIR/$t/critic" --report "$RUN_DIR/$t/eval-int8-test.json" \
      --noise "$RUN_DIR/noise/corpus_stats.json" --task "$name" --json-out "$RUN_DIR/$t/gate.json"
    [ -f "$RUN_DIR/$t/eval-int8-test-owner.json" ] && set -- "$@" --owner-report "$RUN_DIR/$t/eval-int8-test-owner.json"
    rc=0
    in_engine "$PY" ml/critics/laya/gate.py "$@" > "$RUN_DIR/$t/gate.txt" || rc=$?
    echo "  task $t: $(tail -n 1 "$RUN_DIR/$t/gate.txt")"
  done
}

install_promoted() {
  local t installed=""
  for t in $TASKS; do
    [ -f "$RUN_DIR/$t/gate.json" ] || continue
    grep -q '"verdict": "PROMOTE"' "$RUN_DIR/$t/gate.json" || continue
    if [ "$QUICK" = 1 ]; then echo "  task $t: a quick run is never installed"; continue; fi
    if [ -n "$installed" ]; then
      echo "Not installed: the engine holds one critic folder and task $installed is already in it" > "$RUN_DIR/$t/installed.txt"
      continue
    fi
    if [ -d "$CRITIC_HOME" ]; then mv "$CRITIC_HOME" "$CRITIC_HOME.prev-$(date +%Y%m%d%H%M%S)"; fi
    mkdir -p "$(dirname "$CRITIC_HOME")"
    cp -R "$RUN_DIR/$t/critic" "$CRITIC_HOME"
    echo "Installed into $CRITIC_HOME (the engine still answers nothing until an ONNX runtime backend is registered; health shows it as 'disabled')" > "$RUN_DIR/$t/installed.txt"
    installed="$t"
  done
  [ -n "$installed" ] || echo "  nothing promoted, nothing installed"
}

summary() {
  in_engine "$PY" ml/critics/laya/pipeline.py summary --run "$RUN_DIR" | tee "$RUN_DIR/SUMMARY.txt"
}

# --- the plan ----------------------------------------------------------------------------
echo "Laya training: task $TASK, device $DEVICE$([ "$QUICK" = 1 ] && echo ', quick smoke run')"
echo "Run folder: $RUN_DIR"
set -- plan --task "$TASK" --device "$DEVICE"
[ -f "$DATA/data-report.json" ] && set -- "$@" --data "$DATA"
[ "$QUICK" = 1 ] && set -- "$@" --quick
[ "$NO_EXPORT" = 1 ] && set -- "$@" --no-export
if [ -z "$IMPORT" ]; then
  (cd "$REPO" && "$PY" ml/critics/laya/pipeline.py "$@")
  echo "Disk: ~1 GB for the corpus cache and base model, ~2.5 GB per trained task (checkpoint + INT8 ONNX); about 3 GB more while exporting."
  echo "Memory: training holds ~8-10 GB on MPS/CPU; close other large apps on a 16 GB Mac."
fi
[ -n "$OWNER_LABELS" ] && echo "Your labels: $OWNER_LABELS (independent test only, never trained on)"
[ "$DRY" = 1 ] && printf '\nSteps:\n'

# --- the steps -----------------------------------------------------------------------------
[ "$DRY" = 1 ] || mkdir -p "$RUN_DIR/logs"

if [ -n "$IMPORT" ]; then
  step "set up the ML venv ($VENV)" setup_venv
  step "unpack the Kaggle outputs ($IMPORT)" import_zip
  if [ -n "$OWNER_LABELS" ]; then
    step "check the engine" check_engine
    step "build the test file from your own labels" owner_test
  fi
  step "evaluate the INT8 critics on this machine (dev threshold, test, your labels)" evaluate_imported
else
  step "set up the ML venv ($VENV)" setup_venv
  step "check the engine (spaCy, spelling, grammar) with $PY" check_engine
  if [ "$TASK" != a ] || [ -d "$REPO/ml/critics/data/corpus" ]; then
    if [ -f "$CACHE/labels/sentences.jsonl" ]; then
      skip "corpus already in $CACHE ($(xml_count) articles)"
    else
      step "download the open-access corpus into $CACHE (~10 min, ~250 MB) and build its weak labels" harvest_corpus
    fi
  fi
  if [ "$TASK" != b ] && [ -f "$REPO/ml/critics/data/corpus/rebuild.py" ]; then
    if [ -f "$CORPUS_PARAS/train-paragraphs.json" ]; then
      skip "published-article paragraphs already rebuilt in $CORPUS_PARAS"
    else
      step "rebuild the published-article paragraphs behind the corpus labels (SHA-256 checked)" \
        in_engine "$PY" ml/critics/data/corpus/rebuild.py --out "$CORPUS_PARAS" --cache "$CACHE"
    fi
  fi
  step "assemble the training, dev and test files into $DATA" assemble
  step "train, evaluate, calibrate and export ($TASK_TEXT)" train_eval_export
fi

if [ "$NO_EXPORT" = 1 ]; then
  skip "noise floor and gate (--no-export)"
else
  if [ "$QUICK" = 1 ]; then
    skip "noise floor (a quick run is never promoted; the gate will report it missing)"
  elif ls "$REPO"/ml/dogfood/text/*.txt >/dev/null 2>&1; then
    if [ -f "$RUN_DIR/noise/corpus_stats.json" ]; then skip "noise floor already measured"
    else step "noise floor on the private thesis corpus (ml/dogfood, ~10 min)" noise_floor; fi
  else
    skip "noise floor: the private corpus (ml/dogfood/text) is not on this machine; the gate needs it"
  fi
  step "promotion gate (gate.py)" run_gate
  step "install a promoted critic into $CRITIC_HOME" install_promoted
fi
step "summary" summary

if [ "$DRY" = 1 ]; then
  printf '\nDry run: nothing was changed.\n'
fi
