"""Regression tests for check_third_party.py.

The thesis sentence used below is read from the private corpus at run time,
never written into this file: a test of the third-party scan must not itself
carry third-party text.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_third_party as ctp  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
THESIS_DIR = REPO / "ml" / "dogfood" / "text"


@pytest.fixture(scope="module")
def index():
    idx, loaded = ctp.build_index(REPO, lambda msg: None)
    if not idx:
        pytest.skip("private sources not available")
    return idx


def _a_thesis_sentence() -> str:
    for path in sorted(THESIS_DIR.glob("*.txt")):
        for line in path.read_text(encoding="utf-8").splitlines():
            words = line.split()
            if len(words) >= 14 and sum(w.isalpha() for w in words) >= 12:
                return " ".join(words[:14])
    pytest.skip("no thesis text available")


def _scan(root: Path, index) -> list:
    return list(ctp.scan(root, index, set()))


def test_real_copied_prose_is_still_caught(tmp_path, index):
    target = tmp_path / "packages" / "core" / "rules.py"
    target.parent.mkdir(parents=True)
    target.write_text('WHY = "%s"\n' % _a_thesis_sentence())
    hits = _scan(tmp_path, index)
    assert len(hits) == 1 and hits[0][0] == Path("packages/core/rules.py")


def test_number_runs_are_not_prose(tmp_path, index):
    # Page/line numbering in a thesis once matched version lists in a
    # lockfile and failed CI. Numbers alone are never "copied text".
    target = tmp_path / "apps" / "web" / "data.ts"
    target.parent.mkdir(parents=True)
    target.write_text("export const xs = [%s];\n" % ", ".join(str(i) for i in range(40)))
    assert _scan(tmp_path, index) == []


def test_generated_files_are_skipped(tmp_path, index):
    web = tmp_path / "apps" / "web"
    web.mkdir(parents=True)
    sentence = _a_thesis_sentence()
    for name in ("package-lock.json", "tsconfig.tsbuildinfo", "chunk.js.map"):
        (web / name).write_text('"%s"\n' % sentence)
    assert _scan(tmp_path, index) == []


def test_is_prose_threshold():
    assert ctp.is_prose("we fitted a renewal model to daily counts".split())
    assert not ctp.is_prose("6 7 8 9 10 11 12 13".split())
    assert not ctp.is_prose("table 2 3 4 5 6 7 8".split())


def test_the_prediction_attribution_list_is_not_scanned():
    # authors and titles that theses also cite: bibliographic records
    import check_third_party as ctp
    assert ctp.SKIP_NAME_RX.match("predict_sources.tsv")
    assert not ctp.SKIP_NAME_RX.match("predict.py")
