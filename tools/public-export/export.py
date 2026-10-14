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

ZIP and Word (.docx) files the policy admits are opened and every member
is held to the same checks (names, text, document metadata, comments),
within size and depth limits; an archive that cannot be inspected is
refused (Codex review N6, 2026-10-14). The overlay and the policy files
are read from the exported ref, never from the working tree, so an
uncommitted edit cannot change an export; the private terms are those of
the ref together with the current ones. gitleaks is required: without it
the gate reports INCOMPLETE (exit 3) and never syncs, unless
--allow-incomplete is given for a local look.

    python3 tools/public-export/export.py --check            # CI: gate only
    python3 tools/public-export/export.py --out /tmp/public  # write + gate
    python3 tools/public-export/export.py --out /tmp/public \\
        --sync-to ../researchly-public                        # + commit there

--sync-to points at a clone of the public repository: after a clean gate the
clone's tree is replaced by the export and committed (never pushed; pushing
is the owner's deliberate step). Exit codes: 0 clean, 1 findings, 2 usage or
setup error (for example, no private sources to scan against), 3 incomplete
(a required scanner is missing).

Stdlib only; Python 3.10 compatible. Nothing in this folder is exported.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import io
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OVERLAY = HERE / "overlay"
# Where the policy and the overlay live inside the repository's tree: read
# from the exported ref (git show), never from the working tree.
POLICY_TREE = "tools/public-export"
# Limits for looking inside ZIP and .docx files (Codex review N6).
ARCHIVE_SUFFIXES = {".zip", ".docx"}
ARCHIVE_MAX_MEMBERS = 5000
ARCHIVE_MAX_MEMBER = 20 * 1024 * 1024
ARCHIVE_MAX_TOTAL = 100 * 1024 * 1024
ARCHIVE_MAX_DEPTH = 2

MAX_BYTES = 10 * 1024 * 1024
# Binary files the public tree may hold; anything else binary is refused.
BINARY_OK = {".png", ".ico", ".icns", ".svg", ".docx", ".zip", ".woff",
             ".woff2", ".ttf", ".mp4"}
# Archives are allowed only where they are the demo's own output, and video
# only in media/ (the launch video, reviewed before it was added).
ARCHIVE_DIRS = ("demo/dist/", "apps/web/public/demo/")
VIDEO_DIRS = ("media/",)
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

    @classmethod
    def load_ref(cls, ref: str, repo: Path = None,
                 also: "Policy | None" = None) -> "Policy":
        """The policy committed at `ref` (include, exclude, terms, emails).
        `also` adds its private terms: exporting an old ref never uses a
        weaker list than today's."""
        repo = repo or REPO
        tmp = Path(tempfile.mkdtemp(prefix="researchly-policy-"))
        try:
            for name in ("include.txt", "exclude.txt", "private-terms.txt",
                         "public-emails.txt"):
                try:
                    data = _git("show", "%s:%s/%s" % (ref, POLICY_TREE, name),
                                cwd=repo)
                except subprocess.CalledProcessError:
                    data = b""
                (tmp / name).write_bytes(data)
            policy = cls.load(tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if also is not None:
            have = {t for t, _ in policy.terms}
            policy.terms += [(t, rx) for t, rx in also.terms if t not in have]
        return policy

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
           overlay: Path | None = None) -> tuple[list[str], list[str]]:
    """Write the admitted files at `ref`, then the overlay, into `out`.

    Returns (exported paths, refused symlinks). Reads blobs from git, so an
    uncommitted or ignored file can never be exported. The overlay is read
    from `ref` too (tools/public-export/overlay/ in its tree); `overlay` (a
    folder) is for tests only. A symbolic link is never exported, overlay
    included.
    """
    out.mkdir(parents=True, exist_ok=True)
    exported: list[str] = []
    symlinks: list[str] = []
    rows = tracked(ref, repo)
    for mode, sha, rel in rows:
        if not policy.admits(rel):
            continue
        if mode == "120000":
            symlinks.append(rel)
            continue
        _write_blob(out, rel, sha, mode, repo)
        exported.append(rel)
    prefix = POLICY_TREE + "/overlay/"
    if overlay is None:
        for mode, sha, path in rows:
            if not path.startswith(prefix):
                continue
            rel = path[len(prefix):]
            if mode == "120000":
                symlinks.append("overlay/" + rel)
                continue
            _write_blob(out, rel, sha, mode, repo)
            if rel not in exported:
                exported.append(rel)
    elif overlay.is_dir():
        for src in sorted(overlay.rglob("*")):
            rel = src.relative_to(overlay).as_posix()
            if src.is_symlink():
                symlinks.append("overlay/" + rel)
                continue
            if src.is_file():
                dest = out / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                if rel not in exported:
                    exported.append(rel)
    return sorted(exported), symlinks


def _write_blob(out: Path, rel: str, sha: str, mode: str, repo: Path) -> None:
    data = _git("cat-file", "blob", sha, cwd=repo)
    dest = out / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    if mode == "100755":
        dest.chmod(0o755)


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
            elif suffix == ".mp4" and not rel.startswith(VIDEO_DIRS):
                findings.append(Finding("file type", rel, 0, "video is published only from media/"))
            if suffix in ARCHIVE_SUFFIXES:
                for member, text in _archive_texts(rel, data, findings, policy):
                    texts.append((Path(member), text))
                    _scan_text(member, text, policy, findings)
            continue
        text = data.decode("utf-8", "replace")
        texts.append((Path(rel), text))
        _scan_text(rel, text, policy, findings)

    if third_party:
        findings.extend(_third_party(texts, repo))
    leaks = _gitleaks(out)
    stats["incomplete"] = [] if leaks is not None else [
        "gitleaks is not installed: the export was not scanned with the "
        "public CI's secret rules"]
    findings.extend(leaks or [])
    return _dedupe(findings), stats


def _dedupe(findings: list) -> list:
    seen, out = set(), []
    for f in findings:
        key = (f.kind, f.path, f.line, f.detail)
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


def _scan_text(rel: str, text: str, policy: Policy, findings: list) -> None:
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


_XML_BREAK = re.compile(r"</w:p>|<w:br\s*/>|<w:tab\s*/>|</a:p>|</text:p>")


def _xml_text(xml: str) -> str:
    """The text of an Office XML part with run boundaries removed, so a
    word Word split across runs ("Zanzi" + "barova") is one word again."""
    return re.sub(r"<[^>]+>", "", _XML_BREAK.sub("\n", xml))


def _archive_texts(rel: str, data: bytes, findings: list, policy: Policy,
                   depth: int = 0):
    """(member path, text) for every text member of a ZIP or .docx, and for
    archives inside it up to ARCHIVE_MAX_DEPTH. Member names are checked
    for private terms and forbidden types; an archive that cannot be fully
    inspected is a finding, never a pass."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        infos = zf.infolist()
    except (zipfile.BadZipFile, OSError, ValueError) as e:
        findings.append(Finding("archive", rel, 0, "cannot be inspected (%s)" % type(e).__name__))
        return
    if len(infos) > ARCHIVE_MAX_MEMBERS or sum(i.file_size for i in infos) > ARCHIVE_MAX_TOTAL:
        findings.append(Finding("archive", rel, 0, "too large to inspect (members or total size over the limit)"))
        return
    for info in infos:
        if info.is_dir():
            continue
        member = "%s!%s" % (rel, info.filename)
        for term, rx in policy.terms:
            if rx.search(info.filename):
                findings.append(Finding("private term", member, 0, "the member name matches %r" % term))
        msuffix = Path(info.filename).suffix.lower()
        if msuffix in FORBIDDEN_SUFFIXES and msuffix not in ARCHIVE_SUFFIXES:
            findings.append(Finding("file type", member, 0, "%s files are never published, inside an archive either" % msuffix))
            continue
        if info.file_size > ARCHIVE_MAX_MEMBER:
            findings.append(Finding("archive", member, 0, "member too large to inspect"))
            continue
        try:
            raw = zf.read(info)
        except Exception as e:      # encrypted, corrupt, unsupported method
            findings.append(Finding("archive", member, 0, "cannot be read (%s)" % type(e).__name__))
            continue
        if msuffix in ARCHIVE_SUFFIXES or raw[:2] == b"PK":
            if depth + 1 > ARCHIVE_MAX_DEPTH:
                findings.append(Finding("archive", member, 0, "archives nested too deeply to inspect"))
                continue
            yield from _archive_texts(member, raw, findings, policy, depth + 1)
            continue
        if _is_binary(raw):
            continue                # images, fonts: no text to scan
        text = raw.decode("utf-8", "replace")
        yield member, text
        if msuffix in (".xml", ".rels") or text.lstrip().startswith("<?xml"):
            plain = _xml_text(text)
            if plain.strip() and plain != text:
                yield member + " (text)", plain


def _gitleaks(out: Path) -> "list[Finding] | None":
    """gitleaks over the exported tree (CI installs it): the public CI runs
    it on every push, so the gate checks the same rules. None when it is
    not installed: the gate is then incomplete, never silently clean."""
    exe = shutil.which("gitleaks")
    if not exe:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "gitleaks.json"
        subprocess.run([exe, "dir", str(out), "--no-banner", "--exit-code", "0",
                        "--report-format", "json", "--report-path", str(report)],
                       capture_output=True, check=True)
        rows = json.loads(report.read_text("utf-8") or "[]")
    found = []
    for r in rows:
        path = Path(r.get("File", ""))
        try:
            rel = path.resolve().relative_to(out.resolve()).as_posix()
        except ValueError:
            rel = path.as_posix()
        found.append(Finding("secret", rel, int(r.get("StartLine") or 0), "gitleaks: %s" % r.get("RuleID", "?")))
    return found


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
    ap.add_argument("--allow-incomplete", action="store_true",
                    help="local look only: report a missing scanner instead of failing (never syncs)")
    args = ap.parse_args(argv)
    if not args.check and not args.out:
        ap.error("give --out DIR, or --check")

    try:
        policy = Policy.load_ref(args.ref, also=Policy.load())
    except subprocess.CalledProcessError:
        print("error: %s is not a ref of this repository" % args.ref, file=sys.stderr)
        return 2
    if not policy.include:
        print("error: the policy (include.txt) is not committed at %s" % args.ref, file=sys.stderr)
        return 2
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
        for why in stats.get("incomplete", []):
            print("incomplete: %s" % why)
        print("gate: %s (%d finding%s)%s" % ("CLEAN" if not findings else "REFUSED",
                                              len(findings), "" if len(findings) == 1 else "s",
                                              ", INCOMPLETE" if stats.get("incomplete") else ""))
        if args.report:
            args.report.write_text(json.dumps({
                "ref": sha, "files": paths, "stats": stats,
                "findings": [f.__dict__ for f in findings]}, indent=2), "utf-8")
        if findings:
            return 1
        if stats.get("incomplete"):
            if args.sync_to:
                print("not syncing: an incomplete gate never publishes", file=sys.stderr)
            return 0 if args.allow_incomplete and not args.sync_to else 3
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
