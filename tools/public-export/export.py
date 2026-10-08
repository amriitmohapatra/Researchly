#!/usr/bin/env python3
"""export.py: build the public copy of Researchly, and refuse a dirty one.

The private repository stays the source of truth. The public repository is
generated from it: committed files at a git ref, filtered through an
allow-list (include.txt) and a deny-list (exclude.txt), plus the public-only
files in overlay/. Then a gate reads every exported file and refuses the
export if any of these is found:

  - third-party text: an 8-word run shared with a private source (the theses,
    the course material), by the same scanner CI runs on packages/;
  - a private term (private-terms.txt): the lecturer, the course, thesis
    authors, student ids, in a path or in text;
  - a credential pattern (secret keys, private keys, tokens);
  - an email address that is not a placeholder or listed in
    public-emails.txt;
  - a forbidden file type (PDFs, pickles, archives other than the demo's) or
    a file over the size limit;
  - a symbolic link.

    python3 tools/public-export/export.py --check            # CI: gate only
    python3 tools/public-export/export.py --out /tmp/public  # write + gate
    python3 tools/public-export/export.py --out /tmp/public \\
        --sync-to ../researchly-public                        # + commit there

--sync-to points at a clone of the public repository: after a clean gate the
clone's tree is replaced by the export and committed (never pushed; pushing
is the owner's deliberate step). Exit codes: 0 clean, 1 findings, 2 usage or
setup error (for example, no private sources to scan against).

Stdlib only; Python 3.10 compatible. Nothing in this folder is exported.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OVERLAY = HERE / "overlay"

MAX_BYTES = 10 * 1024 * 1024
# Binary files the public tree may hold; anything else binary is refused.
BINARY_OK = {".png", ".ico", ".icns", ".svg", ".docx", ".zip", ".woff",
             ".woff2", ".ttf"}
# Archives are allowed only where they are the demo's own output.
ARCHIVE_DIRS = ("demo/dist/", "apps/web/public/demo/")
FORBIDDEN_SUFFIXES = {".pdf", ".joblib", ".pkl", ".pickle", ".gz", ".tgz",
                      ".dmg", ".exe", ".onnx", ".pt", ".bin", ".npz", ".npy",
                      ".pem", ".key", ".p12", ".pfx"}

SECRET_PATTERNS = [
    ("Supabase secret key", r"sb_secret_[A-Za-z0-9_\-]{10,}"),
    ("private key block", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("AWS access key", r"\bAKIA[0-9A-Z]{16}\b"),
    ("Google API key", r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    ("GitHub token", r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{60,}"),
    ("Slack token", r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"),
    ("Stripe secret key", r"\bsk_live_[A-Za-z0-9]{20,}"),
    ("OpenAI-style key", r"\bsk-[A-Za-z0-9]{32,}\b"),
    # A JWT whose payload says service_role ("c2VydmljZV9yb2xl" is its base64).
    ("Supabase service-role JWT", r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]*c2VydmljZV9yb2xl[A-Za-z0-9_\-]*\.[A-Za-z0-9_\-]+"),
    ("assigned secret", r"(?i)\b(?:secret|password|passwd|api[_-]?key|access[_-]?token)\b\s*[:=]\s*['\"][^'\"\s<>{}$]{16,}['\"]"),
]
EMAIL_RX = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PLACEHOLDER_EMAIL_RX = re.compile(
    r"@(?:[a-z0-9.\-]*\.)?(?:example\.(?:com|org|net|edu)|example\.ac\.uk|"
    r"exampl\.com|host\.org|b\.co|[a-z]+\.supabase\.co)$|^noreply@|"
    r"^name@university\.|"
    r"@users\.noreply\.github\.com$", re.I)


# ─────────────────────────────── selection ──────────────────────────────

def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    out = []
    for raw in path.read_text("utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def _glob_rx(pattern: str) -> re.Pattern:
    """A path pattern as a regex: "dir/" = the folder and below, "*" within a
    segment, "**" across segments. Matches the whole relative path."""
    if pattern.endswith("/"):
        pattern = pattern + "**"
    rx = ""
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            rx += "(?:.*/)?"
            i += 3
        elif pattern.startswith("**", i):
            rx += ".*"
            i += 2
        elif pattern[i] == "*":
            rx += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            rx += "[^/]"
            i += 1
        else:
            rx += re.escape(pattern[i])
            i += 1
    return re.compile(rx + r"\Z")


@dataclass
class Policy:
    include: list = field(default_factory=list)
    exclude: list = field(default_factory=list)
    terms: list = field(default_factory=list)
    emails: set = field(default_factory=set)

    @classmethod
    def load(cls, here: Path = HERE) -> "Policy":
        terms = []
        for t in _read_lines(here / "private-terms.txt"):
            terms.append((t, re.compile(t, re.I)))
        return cls(
            include=[_glob_rx(p) for p in _read_lines(here / "include.txt")],
            exclude=[_glob_rx(p) for p in _read_lines(here / "exclude.txt")],
            terms=terms,
            emails={e.lower() for e in _read_lines(here / "public-emails.txt")},
        )

    def admits(self, rel: str) -> bool:
        return (any(r.match(rel) for r in self.include)
                and not any(r.match(rel) for r in self.exclude))


def _git(*args: str, cwd: Path = REPO, input: bytes | None = None) -> bytes:
    return subprocess.run(["git", "-C", str(cwd), *args], input=input,
                          capture_output=True, check=True).stdout


def tracked(ref: str, repo: Path = REPO) -> list[tuple[str, str, str]]:
    """(mode, blob sha, path) for every file committed at `ref`."""
    out = _git("ls-tree", "-r", "-z", "--full-tree", ref, cwd=repo)
    rows = []
    for entry in out.decode("utf-8", "surrogateescape").split("\0"):
        if not entry:
            continue
        meta, path = entry.split("\t", 1)
        mode, kind, sha = meta.split()
        if kind == "blob":
            rows.append((mode, sha, path))
    return rows


def export(ref: str, out: Path, policy: Policy, repo: Path = REPO,
           overlay: Path = OVERLAY) -> tuple[list[str], list[str]]:
    """Write the admitted files at `ref`, then the overlay, into `out`.

    Returns (exported paths, refused symlinks). Reads blobs from git, so an
    uncommitted or ignored file can never be exported.
    """
    out.mkdir(parents=True, exist_ok=True)
    exported: list[str] = []
    symlinks: list[str] = []
    for mode, sha, rel in tracked(ref, repo):
        if not policy.admits(rel):
            continue
        if mode == "120000":
            symlinks.append(rel)
            continue
        data = _git("cat-file", "blob", sha, cwd=repo)
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        if mode == "100755":
            dest.chmod(0o755)
        exported.append(rel)
    if overlay.is_dir():
        for src in sorted(overlay.rglob("*")):
            if src.is_file():
                rel = src.relative_to(overlay).as_posix()
                dest = out / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                if rel not in exported:
                    exported.append(rel)
    return sorted(exported), symlinks


# ─────────────────────────────── the gate ───────────────────────────────

@dataclass
class Finding:
    kind: str
    path: str
    line: int
    detail: str

    def __str__(self) -> str:
        where = self.path + (":%d" % self.line if self.line else "")
        return "%s: [%s] %s" % (where, self.kind, self.detail)


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _is_binary(data: bytes) -> bool:
    return b"\x00" in data[:8192]


def gate(out: Path, policy: Policy, repo: Path = REPO, symlinks=(),
         third_party: bool = True) -> tuple[list[Finding], dict]:
    findings: list[Finding] = [Finding("symlink", s, 0, "symbolic links are not exported") for s in symlinks]
    files = sorted(p for p in out.rglob("*") if p.is_file() and ".git" not in p.relative_to(out).parts)
    stats = {"files": len(files), "bytes": 0, "binary": []}
    texts: list[tuple[Path, str]] = []

    for p in files:
        rel = p.relative_to(out).as_posix()
        data = p.read_bytes()
        stats["bytes"] += len(data)
        for term, rx in policy.terms:
            if rx.search(rel):
                findings.append(Finding("private term", rel, 0, "the path matches %r" % term))
        suffix = "".join(p.suffixes[-2:]).lower() if p.name.endswith(".tar.gz") else p.suffix.lower()
        if suffix in FORBIDDEN_SUFFIXES:
            findings.append(Finding("file type", rel, 0, "%s files are never published" % suffix))
            continue
        if len(data) > MAX_BYTES:
            findings.append(Finding("size", rel, 0, "%.1f MB is over the %d MB limit" % (len(data) / 1e6, MAX_BYTES // 2**20)))
        if _is_binary(data):
            stats["binary"].append(rel)
            if suffix not in BINARY_OK:
                findings.append(Finding("file type", rel, 0, "binary %s files are not on the list" % (suffix or "(no suffix)")))
            elif suffix == ".zip" and not rel.startswith(ARCHIVE_DIRS):
                findings.append(Finding("file type", rel, 0, "archives are published only as the demo's output"))
            continue
        text = data.decode("utf-8", "replace")
        texts.append((Path(rel), text))
        for term, rx in policy.terms:
            for m in rx.finditer(text):
                findings.append(Finding("private term", rel, _line_of(text, m.start()), "matches %r" % term))
        for name, pattern in SECRET_PATTERNS:
            for m in re.finditer(pattern, text):
                findings.append(Finding("secret", rel, _line_of(text, m.start()), name))
        for m in EMAIL_RX.finditer(text):
            email = m.group(0).rstrip(".").lower()
            if email in policy.emails or PLACEHOLDER_EMAIL_RX.search(email):
                continue
            findings.append(Finding("email", rel, _line_of(text, m.start()),
                                    "%s is not a placeholder or in public-emails.txt" % email))

    if third_party:
        findings.extend(_third_party(texts, repo))
    return findings, stats


def _third_party(texts, repo: Path) -> list[Finding]:
    sys.path.insert(0, str(repo / "ml" / "tools"))
    try:
        import check_third_party as ctp
    finally:
        sys.path.pop(0)
    warnings: list[str] = []
    index, loaded = ctp.build_index(repo, warnings.append)
    if not index:
        raise SystemExit("error: no private sources could be read; the third-party "
                         "check cannot pass vacuously (exit 2)")
    allowed = ctp.load_allowlist(ctp.ALLOWLIST, warnings.append)
    targets = [(rel, text) for rel, text in texts
               if rel.suffix.lower() not in ctp.SKIP_SUFFIXES
               and not ctp.SKIP_NAME_RX.match(rel.name)
               and not ctp.SKIP_GENERATED_RX.search(rel.name)]
    out = []
    for rel, line, phrase, labels, n in ctp.scan(repo, index, allowed, targets=targets):
        out.append(Finding("third-party text", rel.as_posix(), line,
                           "%d-word match with %s" % (n, ", ".join(labels))))
    return out


# ─────────────────────────────── sync ───────────────────────────────────

def sync(out: Path, clone: Path, message: str) -> bool:
    """Make `clone`'s tree equal to `out` and commit. Returns False if unchanged."""
    if not (clone / ".git").exists():
        raise SystemExit("error: %s is not a git clone of the public repository" % clone)
    for p in sorted(clone.rglob("*"), reverse=True):
        rel = p.relative_to(clone)
        if rel.parts[0] == ".git":
            continue
        if p.is_file() or p.is_symlink():
            p.unlink()
        elif p.is_dir() and not any(p.iterdir()):
            p.rmdir()
    for src in out.rglob("*"):
        if src.is_file():
            dest = clone / src.relative_to(out)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
    _git("add", "-A", cwd=clone)
    if not _git("status", "--porcelain", cwd=clone).strip():
        return False
    _git("commit", "-q", "-m", message, cwd=clone)
    return True


# ─────────────────────────────── main ───────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ref", default="HEAD", help="git ref to export (default HEAD)")
    ap.add_argument("--out", type=Path, help="write the export here (must be empty or new)")
    ap.add_argument("--check", action="store_true", help="export to a temporary folder and gate it only")
    ap.add_argument("--sync-to", type=Path, help="after a clean gate, replace this public clone's tree and commit")
    ap.add_argument("--report", type=Path, help="also write the findings and stats as JSON")
    ap.add_argument("--list", action="store_true", help="print every exported path")
    args = ap.parse_args(argv)
    if not args.check and not args.out:
        ap.error("give --out DIR, or --check")

    policy = Policy.load()
    if not policy.terms:
        print("error: private-terms.txt is missing or empty", file=sys.stderr)
        return 2
    tmp = None
    if args.check and not args.out:
        tmp = tempfile.TemporaryDirectory(prefix="researchly-public-")
        out = Path(tmp.name)
    else:
        out = args.out.resolve()
        if out.exists() and any(out.iterdir()):
            print("error: %s is not empty" % out, file=sys.stderr)
            return 2
    try:
        sha = _git("rev-parse", "--short", args.ref).decode().strip()
        paths, symlinks = export(args.ref, out, policy)
        findings, stats = gate(out, policy, symlinks=symlinks)
        tops: dict = {}
        for rel in paths:
            top = rel.split("/", 1)[0] if "/" in rel else "(root)"
            tops[top] = tops.get(top, 0) + 1
        if args.list:
            for rel in paths:
                print(rel)
        print("exported %d files (%.1f MB) from %s: %s" % (
            stats["files"], stats["bytes"] / 1e6, sha,
            ", ".join("%s %d" % kv for kv in sorted(tops.items()))))
        print("binary files: %d (%s)" % (len(stats["binary"]), ", ".join(sorted({Path(b).suffix for b in stats["binary"]}))))
        for f in findings:
            print(f)
        print("gate: %s (%d finding%s)" % ("CLEAN" if not findings else "REFUSED",
                                            len(findings), "" if len(findings) == 1 else "s"))
        if args.report:
            args.report.write_text(json.dumps({
                "ref": sha, "files": paths, "stats": stats,
                "findings": [f.__dict__ for f in findings]}, indent=2), "utf-8")
        if findings:
            return 1
        if args.sync_to:
            changed = sync(out, args.sync_to.resolve(),
                           "Sync from the private repository (%s)" % sha)
            print("public clone %s: %s" % (args.sync_to, "committed; review, then push" if changed else "already up to date"))
        return 0
    finally:
        if tmp is not None:
            tmp.cleanup()


if __name__ == "__main__":
    sys.exit(main())
