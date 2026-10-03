"""Run researchly v0.1 over the extracted thesis corpus; dump stats + samples.

Front-matter fairness: suggestions under non-content headings
(acknowledgements, declaration, contents, publication lists) are excluded —
those aren't scientific prose and a real user would never check them.
"""

import json
import os
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Resolved from this file, not a cloud-sandbox absolute path, so the
# noise-floor guard runs on any machine.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "packages" / "core"))

import spacy  # noqa: E402
from researchly.document import Document  # noqa: E402
from researchly.engine import check  # noqa: E402
from researchly import metrics as metrics_mod  # noqa: E402

TEXTDIR = Path(os.environ.get("RESEARCHLY_CORPUS_TEXT", HERE / "text"))
OUTDIR = Path(os.environ.get("RESEARCHLY_CORPUS_OUT", HERE / "results"))
OUTDIR.mkdir(parents=True, exist_ok=True)

# Lets a run isolate one tier's contribution, e.g. RESEARCHLY_DISABLE=S001 to
# compare against a baseline measured before the spelling tier existed.
DISABLED = {r.strip() for r in
            os.environ.get("RESEARCHLY_DISABLE", "").split(",") if r.strip()}

NONCONTENT = re.compile(
    r"acknowledg|declaration|contents|list of|publication|dedicat|"
    r"curriculum|symbols|abbreviation", re.I)

nlp = spacy.load("en_core_web_sm")
nlp.max_length = 1_200_000

corpus_stats = {}
all_samples = defaultdict(list)

for txt in sorted(TEXTDIR.glob("*.txt")):
    doc = Document.from_path(txt)
    # governing heading text for each offset
    headings = doc.headings

    def gov_heading(off: int) -> str:
        cur = ""
        for h in headings:
            if h.start > off:
                break
            cur = h.text
        return cur

    suggestions = check(doc, nlp, show_preferences=True, disabled=DISABLED)
    kept = [s for s in suggestions if not NONCONTENT.search(gov_heading(s.start))]
    skipped = len(suggestions) - len(kept)

    mets = metrics_mod.compute(nlp(doc.masked), doc)
    words = mets.words or 1

    by_rule = Counter(s.rule_id for s in kept)
    by_section = Counter(s.section for s in kept)

    corpus_stats[txt.stem] = {
        "words": mets.words,
        "sentences": mets.sentences,
        "suggestions": len(kept),
        "skipped_frontmatter": skipped,
        "per_1000_words": round(1000 * len(kept) / words, 1),
        "by_rule": dict(by_rule.most_common()),
        "by_section": dict(by_section.most_common()),
        "metrics": mets.to_dict(),
    }

    rng = random.Random(42)
    per_rule = defaultdict(list)
    for s in kept:
        per_rule[s.rule_id].append(s)
    for rid, items in per_rule.items():
        for s in rng.sample(items, min(6, len(items))):
            ctx_a = max(0, s.start - 90)
            ctx_b = min(len(doc.original), s.end + 90)
            all_samples[rid].append({
                "thesis": txt.stem,
                "section": s.section,
                "flagged": " ".join(s.text.split())[:120],
                "message": s.message,
                "context": " ".join(
                    doc.original[ctx_a:ctx_b].split()),
            })
    print(f"{txt.stem:42s} {mets.words:>7,}w  {len(kept):>5} flags "
          f"({round(1000*len(kept)/words,1):>5}/1000w)  top: "
          f"{', '.join(f'{r}:{n}' for r, n in by_rule.most_common(5))}")

(OUTDIR / "corpus_stats.json").write_text(json.dumps(corpus_stats, indent=2))
(OUTDIR / "samples.json").write_text(json.dumps(all_samples, indent=2))

total = sum(v["suggestions"] for v in corpus_stats.values())
words = sum(v["words"] for v in corpus_stats.values())
agg = Counter()
for v in corpus_stats.values():
    agg.update(v["by_rule"])
print(f"\nTOTAL: {total:,} suggestions over {words:,} words "
      f"({round(1000*total/words,1)}/1000w)")
for rid, n in agg.most_common():
    print(f"  {rid}: {n}")
