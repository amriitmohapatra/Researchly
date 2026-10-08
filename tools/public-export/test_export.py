"""Tests for the public export: what it admits, what it copies, what the gate refuses."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import export as ex  # noqa: E402

REPO = HERE.parents[1]


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture()
def toy(tmp_path: Path):
    """A small git repo, its policy folder and an overlay."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.org")
    _git(repo, "config", "user.name", "t")
    files = {
        "LICENSE": "MIT",
        "packages/core/a.py": "print('hello')\n",
        "packages/core/run.sh": "#!/bin/sh\necho hi\n",
        "packages/core/data/notes.pdf": "%PDF-1.4",
        "private/plan.md": "secret plans\n",
        "README.md": "private readme\n",
    }
    for rel, text in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    (repo / "packages/core/run.sh").chmod(0o755)
    (repo / "packages/core/link.py").symlink_to("a.py")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    (repo / "packages/core/uncommitted.py").write_text("x = 1\n")

    here = tmp_path / "policy"
    here.mkdir()
    (here / "include.txt").write_text("LICENSE\nREADME.md\npackages/\nprivate/\n")
    (here / "exclude.txt").write_text("private/\n**/*.pdf\n")
    (here / "private-terms.txt").write_text("# names\n\\bZanzibarova\\b\n")
    (here / "public-emails.txt").write_text("help@researchly.test\n")
    overlay = here / "overlay"
    (overlay / ".github").mkdir(parents=True)
    (overlay / "README.md").write_text("public readme\n")
    (overlay / ".github" / "ci.yml").write_text("name: CI\n")
    return repo, here, overlay


def test_patterns():
    rx = ex._glob_rx
    assert rx("packages/").match("packages/core/a.py")
    assert not rx("packages/").match("packagesX/a.py")
    assert rx("**/*.pdf").match("a/b/c.pdf") and rx("**/*.pdf").match("c.pdf")
    assert not rx("docs/*.md").match("docs/adr/x.md")
    assert rx("Codex_Review*.md").match("Codex_Review_8Oct2026.md")


def test_export_copies_only_committed_admitted_files_then_the_overlay(toy, tmp_path):
    repo, here, overlay = toy
    policy = ex.Policy.load(here)
    out = tmp_path / "out"
    paths, symlinks = ex.export("HEAD", out, policy, repo=repo, overlay=overlay)
    assert paths == sorted(["LICENSE", "README.md", "packages/core/a.py",
                            "packages/core/run.sh", ".github/ci.yml"])
    assert symlinks == ["packages/core/link.py"]
    assert not (out / "packages/core/uncommitted.py").exists()   # never from the working tree
    assert not (out / "private").exists()                        # excluded wins over included
    assert not (out / "packages/core/data/notes.pdf").exists()
    assert (out / "README.md").read_text() == "public readme\n"   # the overlay replaces
    assert (out / "packages/core/run.sh").stat().st_mode & 0o111   # executable bit kept


def _gate(tmp_path, here, files: dict, **kw):
    out = tmp_path / "gated"
    for rel, data in files.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else data.encode())
    findings, _ = ex.gate(out, ex.Policy.load(here), third_party=False, **kw)
    return sorted((f.kind, f.path) for f in findings)


def test_gate_refuses_terms_secrets_emails_and_file_types(toy, tmp_path):
    _, here, _ = toy
    fake_key = "sb_" + "secret_" + "A1b2C3d4E5f6G7h8"
    found = _gate(tmp_path, here, {
        "ok.py": "x = 'clean'  # contact: help@researchly.test, a@example.org\n",
        "names.md": "Thanks to Dr zanzibarova for the lecture.\n",
        "zanzibarova/readme.txt": "fine text\n",
        "keys.ts": "const k = '%s';\n" % fake_key,
        "mail.md": "write to someone.real@gmail.com\n",
        "paper.pdf": b"%PDF-1.4\x00",
        "blob.bin": b"\x00\x01\x02",
        "img.png": b"\x89PNG\x00\x00",
        "stray.zip": b"PK\x03\x04\x00",
        "demo/dist/demo.zip": b"PK\x03\x04\x00",
        "media/launch.mp4": b"\x00\x00\x00\x18ftypmp42",
        "apps/web/public/clip.mp4": b"\x00\x00\x00\x18ftypmp42",
    }, symlinks=["link.py"])
    assert found == sorted([
        ("private term", "names.md"),
        ("private term", "zanzibarova/readme.txt"),
        ("secret", "keys.ts"),
        ("email", "mail.md"),
        ("file type", "paper.pdf"),
        ("file type", "blob.bin"),
        ("file type", "stray.zip"),
        ("file type", "apps/web/public/clip.mp4"),
        ("symlink", "link.py"),
    ])


def test_gate_finds_third_party_text_in_any_exported_file(tmp_path):
    """The shingle scan reads every exported file, not only packages/."""
    fake = tmp_path / "private"
    (fake / "ml" / "tools").mkdir(parents=True)
    shutil.copy(REPO / "ml" / "tools" / "check_third_party.py", fake / "ml" / "tools")
    (fake / "ml" / "dogfood" / "text").mkdir(parents=True)
    passage = ("the seasonal pattern of transmission in the northern districts "
               "was driven mainly by rainfall and the timing of school terms")
    (fake / "ml" / "dogfood" / "text" / "someone.txt").write_text("Chapter one. " + passage + ". The end.")
    out = tmp_path / "out"
    (out / "docs").mkdir(parents=True)
    (out / "docs" / "notes.md").write_text("As shown, " + passage + ", which matters.\n")
    (out / "docs" / "clean.md").write_text("A synthetic sentence written for this test only.\n")
    policy = ex.Policy(terms=[("x", re.compile(r"\bnever-matches\b"))])
    findings, _ = ex.gate(out, policy, repo=fake)
    assert [(f.kind, f.path) for f in findings] == [("third-party text", "docs/notes.md")]


def test_the_real_policy_keeps_private_material_out():
    policy = ex.Policy.load()
    for rel in ("Sample_thesis_drafts/x.pdf", "Notes_On_Writing/unit.pdf", "ml/dogfood/text/a.txt",
                "ml/dogfood/baseline.json", "legacy/experiment-p21/a.py", "_to_delete/a.tar.gz",
                "CLAUDE.md", "PLAN.md", "ARCHITECTURE.md", "docs/PROJECT_LOG.md",
                "docs/knowledge-base.md", "ml/datasets.yaml", "ml/tools/check_third_party.py",
                "tools/public-export/private-terms.txt", "research/00-synthesis.md",
                ".github/workflows/deploy-engine.yml", "apps/web/.env.local", "Rough Drafts.docx",
                "packages/core/model.joblib"):
        assert not policy.admits(rel), rel
    for rel in ("LICENSE", "packages/core/researchly/api.py", "apps/web/app/page.tsx",
                "services/engine/Dockerfile", "supabase/migrations/x.sql", "demo/dist/researchly-demo.docx",
                "ml/realdocs/run.py", ".github/workflows/realdocs.yml", "apps/web/.env.example",
                "media/researchly-video.mp4"):
        assert policy.admits(rel), rel
    assert policy.terms, "private-terms.txt must not be empty"


def _jobs(path: Path) -> set:
    return set(re.findall(r"^  ([a-z][a-z0-9-]*):\s*$", path.read_text("utf-8"), re.M))


def test_public_ci_runs_every_private_job_that_needs_no_private_material():
    private = _jobs(REPO / ".github" / "workflows" / "ci.yml")
    public = _jobs(HERE / "overlay" / ".github" / "workflows" / "ci.yml")
    private_only = {"third-party-text", "public-export"}
    assert public == private - private_only


def test_sync_replaces_the_public_tree_and_commits(tmp_path):
    clone = tmp_path / "public"
    clone.mkdir()
    _git(clone, "init", "-q")
    _git(clone, "config", "user.email", "t@example.org")
    _git(clone, "config", "user.name", "t")
    (clone / "old.txt").write_text("gone soon\n")
    _git(clone, "add", "-A")
    _git(clone, "commit", "-q", "-m", "first")
    out = tmp_path / "out"
    (out / "pkg").mkdir(parents=True)
    (out / "pkg" / "new.py").write_text("x = 1\n")
    assert ex.sync(out, clone, "Sync") is True
    assert not (clone / "old.txt").exists() and (clone / "pkg" / "new.py").exists()
    assert ex.sync(out, clone, "Sync") is False      # nothing changed, no empty commit


def test_gitleaks_runs_on_the_export_when_installed(tmp_path, monkeypatch):
    gl = shutil.which("gitleaks")
    if not gl:
        pytest.skip("gitleaks is not installed here (CI installs it)")
    out = tmp_path / "out"
    out.mkdir()
    token = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
    (out / "leak.py").write_text("TOKEN = '%s'\n" % token)
    found = ex._gitleaks(out)
    assert found and all(f.kind == "secret" and f.path == "leak.py" for f in found)
