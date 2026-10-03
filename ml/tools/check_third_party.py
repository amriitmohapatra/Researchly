#!/usr/bin/env python3
"""check_third_party.py — no third-party text inside shipped code (PLAN.md S0).

Builds 8-word shingles from the project's *private* sources — the eight
sample theses (ml/dogfood/text), the legacy paper corpus, and the course
material in Notes_On_Writing/ (D6, D7) — and scans every text file under
packages/, apps/ and services/ for any run of 8+ consecutive words that
also occurs in one of those sources.

    python3 ml/tools/check_third_party.py            # exit 0 clean, 1 hits
    python3 ml/tools/check_third_party.py --sources  # list what was loaded

Normalisation (both sides): lowercase; every non-alphanumeric character is a
word break (punctuation, quotes, hyphens, slashes); PDF ligature damage is
folded (pdftotext often drops the "i" of "fi", so "findings" and "fndings"
must compare equal); and in scanned files the escape sequences \\n \\t \\r
inside string literals are treated as spaces. Python string literals split
over several lines therefore still match as one passage.

Allow-list: ml/tools/third_party_allowlist.txt, one phrase per line,
`phrase  # why it is fine`. A shingle is ignored only if it lies wholly
inside an allow-listed phrase. Keep the file empty or near-empty; it is for
generic academic phrasing that happens to be 8+ words, never for a passage.

Exit codes: 0 clean · 1 third-party text found · 2 no private sources
could be read (the check would be meaningless, so it refuses to pass).

Stdlib only; Python 3.10 compatible.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

N = 8                                   # shingle width (words)
REPO = Path(__file__).resolve().parents[2]
ALLOWLIST = Path(__file__).resolve().parent / "third_party_allowlist.txt"

SCAN_ROOTS = ("packages", "apps", "services")
SKIP_DIRS = {"dist", "node_modules", "__pycache__", ".git", ".venv", "venv",
             "build", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
SKIP_SUFFIXES = {".joblib", ".pkl", ".pickle", ".pyc", ".pyo", ".so",
                 ".dylib", ".dll", ".exe", ".png", ".jpg", ".jpeg", ".gif",
                 ".ico", ".icns", ".pdf", ".zip", ".gz", ".tar", ".dmg",
                 ".whl", ".jar", ".onnx", ".bin", ".pt", ".npz", ".npy",
                 ".woff", ".woff2", ".ttf", ".otf", ".vsix", ".docx"}
# The SymSpell frequency dictionary is a third-party *word list*, not prose;
# it is licensed separately (ml/datasets.yaml) and would only add noise.
SKIP_NAME_RX = re.compile(r"^frequency_(dictionary|bigramdictionary)", re.I)
# Machine-generated files: dependency lockfiles and compiler/bundler state.
# They hold version lists and number runs, never prose anyone wrote.
SKIP_GENERATED_RX = re.compile(
    r"(^package-lock\.json$|^pnpm-lock\.yaml$|^yarn\.lock$|\.tsbuildinfo$|\.map$)")

# A shingle must carry prose to count as a match. Without this, runs of page
# or line numbers ("6 7 8 9 10 11 12 13") in a thesis matched number lists in
# package-lock.json and source maps — a false positive that failed CI.
MIN_WORDS_WITH_LETTERS = 5
_HAS_LETTER = re.compile(r"[a-z]")

_LIGATURES = (("ffi", "f"), ("ffl", "f"), ("ff", "f"), ("fi", "f"),
              ("fl", "f"))
_WORD_RX = re.compile(r"[a-z0-9]+")
_ESCAPE_RX = re.compile(r"\\[ntr]")


def _fold(word: str) -> str:
    for a, b in _LIGATURES:
        if a in word:
            word = word.replace(a, b)
    return word


def _prep(text: str) -> str:
    text = text.lower()
    # Unicode ligature code points, then any non-ASCII letter → break.
    text = (text.replace("ﬁ", "fi").replace("ﬂ", "fl")
            .replace("ﬀ", "ff").replace("ﬃ", "ffi")
            .replace("ﬄ", "ffl"))
    return text


def tokens(text: str) -> list[str]:
    """Normalised word tokens of `text` (used for sources and allow-list)."""
    return [_fold(w) for w in _WORD_RX.findall(_prep(text))]


def tokens_with_lines(text: str) -> tuple[list[str], list[str], list[int]]:
    """(folded tokens, original-case words, 1-based line numbers)."""
    folded: list[str] = []
    orig: list[str] = []
    lines: list[int] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        line = _ESCAPE_RX.sub(" ", line)
        low = _prep(line)
        for m in _WORD_RX.finditer(low):
            folded.append(_fold(m.group()))
            orig.append(line[m.start():m.end()] if len(line) == len(low)
                        else m.group())
            lines.append(lineno)
    return folded, orig, lines


def is_prose(window) -> bool:
    return sum(1 for t in window if _HAS_LETTER.search(t)) >= MIN_WORDS_WITH_LETTERS


def shingles(toks: list[str]):
    for i in range(len(toks) - N + 1):
        window = toks[i:i + N]
        if is_prose(window):
            yield " ".join(window)


# ─────────────────────────────── sources ────────────────────────────────

def _pdf_text(path: Path, warn) -> str | None:
    exe = shutil.which("pdftotext")
    if exe is None:
        warn("pdftotext not found — skipping PDF sources "
             "(install poppler-utils / `brew install poppler`)")
        return None
    try:
        out = subprocess.run([exe, "-q", str(path), "-"],
                             capture_output=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        warn("could not run pdftotext on %s: %s" % (path.name, exc))
        return None
    text = out.stdout.decode("utf-8", "replace")
    if len(text.split()) < 50:
        warn("%s has no usable text layer (scan?) — not checked against; "
             "check its content by hand" % path.name)
        return None
    return text


def _docx_text(path: Path, warn) -> str | None:
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
    except (KeyError, zipfile.BadZipFile, OSError) as exc:
        warn("could not read %s: %s" % (path.name, exc))
        return None
    xml = re.sub(r"</w:p>|<w:tab/>|<w:br/>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml)


def _dehyphenate(text: str) -> str:
    # PDF line-break hyphenation: "trans-\nition" → "transition".
    return re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)


def iter_sources(root: Path, warn):
    """Yield (label, text) for every private source that can be read."""
    for p in sorted((root / "ml" / "dogfood" / "text").glob("*.txt")):
        yield "thesis:" + p.stem, p.read_text("utf-8", "replace")
    corpus = root / "legacy" / "experiment-p21" / "prototype" / \
        "experiments" / "corpus"
    if corpus.is_dir():
        for p in sorted(corpus.rglob("*")):
            if p.is_file() and p.suffix.lower() in {".txt", ".md", ".text"}:
                yield "corpus:" + p.stem, p.read_text("utf-8", "replace")
    notes = root / "Notes_On_Writing"
    if notes.is_dir():
        for p in sorted(notes.iterdir()):
            text = None
            if p.suffix.lower() == ".pdf":
                text = _pdf_text(p, warn)
            elif p.suffix.lower() == ".docx":
                text = _docx_text(p, warn)
            if text:
                yield "notes:" + p.name, text


def build_index(root: Path, warn) -> tuple[dict, list[str]]:
    index: dict = {}
    loaded: list[str] = []
    for label, text in iter_sources(root, warn):
        n_before = len(index)
        variants = [text]
        if "-\n" in text:
            variants.append(_dehyphenate(text))
        for variant in variants:
            for sh in shingles(tokens(variant)):
                index.setdefault(sh, label)
        loaded.append("%s (%d new shingles)" % (label, len(index) - n_before))
    return index, loaded


# ─────────────────────────────── allow-list ─────────────────────────────

def load_allowlist(path: Path, warn) -> set:
    allowed: set = set()
    if not path.exists():
        return allowed
    for n, raw in enumerate(path.read_text("utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        phrase, _, why = line.partition("#")
        if not why.strip():
            warn("%s:%d allow-list entry has no '# reason' comment"
                 % (path.name, n))
        toks = tokens(phrase)
        if len(toks) < N:
            warn("%s:%d allow-list phrase is shorter than %d words and can "
                 "never match" % (path.name, n, N))
        allowed.update(shingles(toks))
    return allowed


# ─────────────────────────────── targets ────────────────────────────────

def _candidate_files(root: Path):
    """Files that are, or would be, in the repository under SCAN_ROOTS.

    Shippable means "in git": build output (.next/, dist/) and anything
    .gitignore excludes never reach a release, so scanning them only adds
    noise. Falls back to walking the tree when git is unavailable.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others",
             "--exclude-standard", "--", *SCAN_ROOTS],
            capture_output=True, check=True, timeout=60).stdout
        rels = [Path(r) for r in out.decode("utf-8", "replace").split("\0") if r]
        return sorted(root / r for r in rels)
    except (OSError, subprocess.SubprocessError):
        files = []
        for top in SCAN_ROOTS:
            base = root / top
            if base.is_dir():
                files.extend(base.rglob("*"))
        return sorted(files)


def iter_targets(root: Path):
    for p in _candidate_files(root):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts[:-1]):
            continue
        if (p.suffix.lower() in SKIP_SUFFIXES or SKIP_NAME_RX.match(p.name)
                or SKIP_GENERATED_RX.search(p.name)):
            continue
        try:
            raw = p.read_bytes()
        except OSError:
            continue
        if b"\x00" in raw[:8192]:
            continue                                    # binary
        yield rel, raw.decode("utf-8", "replace")


def scan(root: Path, index: dict, allowed: set):
    """Yield (relpath, line, phrase, sources, n_words) per matching run."""
    for rel, text in iter_targets(root):
        folded, orig, lines = tokens_with_lines(text)
        hit = [False] * len(folded)
        srcs: dict = {}
        for i in range(len(folded) - N + 1):
            window = folded[i:i + N]
            if not is_prose(window):
                continue
            sh = " ".join(window)
            label = index.get(sh)
            if label is None or sh in allowed:
                continue
            for j in range(i, i + N):
                hit[j] = True
            srcs[i] = label
        i = 0
        while i < len(folded):
            if not hit[i]:
                i += 1
                continue
            j = i
            while j < len(folded) and hit[j]:
                j += 1
            labels = sorted({lab for k, lab in srcs.items() if i <= k < j})
            yield (rel, lines[i], " ".join(orig[i:j]), labels, j - i)
            i = j


def main(argv=None) -> int:
    global N
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path, default=REPO,
                    help="repository root (default: inferred)")
    ap.add_argument("--sources", action="store_true",
                    help="list the private sources loaded")
    ap.add_argument("--width", type=int, default=N, metavar="N",
                    help="shingle width in words (default %d; lower it for a "
                         "targeted audit, expect generic-phrase noise)" % N)
    args = ap.parse_args(argv)
    N = max(3, args.width)
    root = args.root.resolve()

    warned: set = set()

    def warn(msg: str) -> None:
        if msg not in warned:
            warned.add(msg)
            print("warning: " + msg, file=sys.stderr)

    index, loaded = build_index(root, warn)
    if args.sources:
        for line in loaded:
            print("source: " + line)
    if not index:
        print("error: no private sources could be read under %s — the check "
              "cannot pass vacuously" % root, file=sys.stderr)
        return 2
    allowed = load_allowlist(ALLOWLIST, warn)

    hits = list(scan(root, index, allowed))
    for rel, line, phrase, labels, n in hits:
        print("%s:%d: %d-word match with %s\n    \"%s\""
              % (rel, line, n, ", ".join(labels), phrase))
    print("checked against %d sources (%d shingles); %d hit%s"
          % (len(loaded), len(index), len(hits), "" if len(hits) == 1
             else "s"))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
