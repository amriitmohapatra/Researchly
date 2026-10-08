# The public repository (private notes; this folder is never exported)

The owner chose, on 2026-10-08, to share Researchly as a **separate public
repository with a fresh history**, generated from this private one. This
repository stays the source of truth and stays private: it holds the eight
theses, the text extracted from them, the course PDFs and the planning
documents, all of which remain in its git history.

## How it works

`export.py` builds the public tree:

1. it takes **committed** files at a git ref (never the working folder, so
   nothing uncommitted or ignored can leak);
2. it keeps only paths that match `include.txt` and match nothing in
   `exclude.txt` (a new top-level folder is private until it is listed);
3. it lays `overlay/` on top: the public README, CONTRIBUTING, SECURITY and
   the public CI (the private CI minus the job that needs private sources);
4. it **gates** the result and refuses it on any finding:
   - an 8-word run shared with a thesis, the course material or the legacy
     corpus, in any exported file (`ml/tools/check_third_party.py`);
   - a private term from `private-terms.txt` (the lecturer, the course,
     thesis authors, student ids), in a path or in text;
   - a credential pattern;
   - an email address that is neither a placeholder nor in
     `public-emails.txt`;
   - a PDF, pickle, model file or stray archive, a file over 10 MB, or a
     symbolic link.

CI runs the gate on every change (`public-export` job), so a problem is
caught when it is introduced, not when publishing.

## Publishing

First time (after the owner has created the empty repository on GitHub,
private until reviewed):

```bash
python3.10 tools/public-export/export.py --out /tmp/researchly-public
cd /tmp/researchly-public
git init -b main && git add -A
git commit -m "Researchly, published from the private repository"
git remote add origin https://github.com/amriitmohapatra/researchly-public.git
git push -u origin main
```

Every later release, from a clone of the public repository:

```bash
python3.10 tools/public-export/export.py --ref main --out /tmp/rp-export \
    --sync-to ../researchly-public
cd ../researchly-public && git log -1 --stat   # review
git push
```

`--sync-to` replaces the clone's tree with the export and commits; it
never pushes. Publishing is always a deliberate push.

## The launch video

`media/` holds the 50-second launch video (the music-only cut) and its
poster, shown at the top of the public README. The gate admits video only
from `media/`. The voiced cut stays out until someone has listened to it;
to swap it in, replace `media/researchly-in-50-seconds.mp4` and publish.

## Changing what is published

- To publish a new folder or document, add it to `include.txt`, run
  `python3.10 tools/public-export/export.py --check --list`, and read what
  would go out.
- If the gate flags a passage, rewrite the passage. Allow-list a phrase in
  `ml/tools/third_party_allowlist.txt` only when it is a licence statement,
  a published title or other stock wording, with the reason.
- A name that must never appear goes in `private-terms.txt`. The engine's
  explanation test reads the same list.

## What stays private, and why

| Kept private | Why |
|---|---|
| `Sample_thesis_drafts/`, `ml/dogfood/`, `legacy/`, `_to_delete/` | Other people's theses and text extracted from them |
| `Notes_On_Writing/` | Course material; the lecturer and course are credited only in `docs/knowledge-base.md` |
| `The-Craft-of-Scientific-Writing.md` | The owner's guide; publish it only when the owner decides to |
| `CLAUDE.md`, `AGENTS.md`, `PLAN.md`, `ARCHITECTURE.md`, `docs/PROJECT_LOG.md`, `docs/rule-inventory.md`, `docs/knowledge-base.md`, Codex reviews | Planning and provenance that name private sources and owner tasks |
| `docs/deploy.md`, the deploy and noise-floor workflows | Production deployment runs from this repository only |
| `ml/datasets.yaml` | The licence registry lists the private sources |
