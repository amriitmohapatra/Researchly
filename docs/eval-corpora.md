# Evaluation corpora — what to test against, and what it costs

*2026-08-11. Researchly has measured flag **volume** since P4 but never
measured **recall**: `dogfooding-report.md` counts how loud the tool is, not
what it misses. `research/00-synthesis.md:75` called for an evaluation
harness "from day one" and it was never built. This is the sourced plan for
one, plus the first results.*

Two questions need different corpora, and conflating them is why the project
has had only half an answer:

| Question | Needs | Oracle |
|---|---|---|
| Does it shout at good writing? | **published, edited prose** | any flag is a candidate false positive |
| Does it catch bad writing? | **text with known errors** | annotated corrections |

---

## Tier 1 — get these first

### AESW 2016 · the one that matters most ✅ acquired

The closest public corpus to Researchly's actual job: ~1.2M sentences from
**9,919 published journal articles** (mostly physics and mathematics), each
shown before *and* after a professional language editor worked on it.
466,672 edited + 722,742 unedited sentences in train alone.

Every sentence carries a free label — an expert either changed it or left it
alone — which is precisely the ground truth this project has lacked.

- **Access**: direct download, no registration. The "registration" mentioned
  around the shared task was for the *competition*, not the data.
  `http://textmining.lt/aesw/aesw2016down.html`
- ⚠️ **The site's TLS certificate has expired.** It serves fine over plain
  HTTP (200). `curl -k` or `--insecure` is required; this is a dead cert on
  a live host, not a redirect or a mirror.
- **Licence**: CC BY-NC-SA 4.0, **plus** three extra clauses forbidding any
  attempt to re-identify authors of the text samples, sharing such an
  identification, or building derivative data that would help do so.
- **Cite**: Vidas Daudaravicius (2016), *Automated Evaluation of Scientific
  Writing Data Set* (Version 1.2) [Data file], VTeX.
- **Do not commit the corpus or any derived sentences to this repo.**
  NC + ShareAlike + the re-identification clauses make redistribution the
  one thing that is clearly disallowed. It lives in `prototype/eval/data/`,
  which exists for exactly this and should stay untracked.

```bash
mkdir -p prototype/eval/data && cd prototype/eval/data
BASE=http://textmining.lt/aesw
curl -k -o aesw_dev.xml.bz2   "$BASE/aesw2016%28v1.2%29_dev.xml.bz2"    #   5 MB
curl -k -o aesw_train.xml.bz2 "$BASE/aesw2016%28v1.2%29_train.xml.bz2"  #  44 MB
bunzip2 -k aesw_dev.xml.bz2
```

Parser: `prototype/eval/aesw.py`. Harness: `prototype/eval/stress_test.py`.

### BEA-2019 family · learner and native error corpora

The standard GEC training/eval sets, and the right ones for the academic-ESL
regression set W3 needs (articles, agreement, prepositions, tense).

| Corpus | Content | Access |
|---|---|---|
| **W&I+LOCNESS v2.1** | 3,600 Write&Improve submissions across CEFR A/B/C + 100 native essays; 45k sentences | direct download |
| **FCE v2.1** | 1,244 exam scripts, Cambridge Learner Corpus | direct download |
| **NUCLE** | 1,400 NUS student essays — *the local one* | Google Form, ~1 day |
| **Lang-8** | large, noisy, web-scraped learner corrections | Google Form, immediate |

- `https://www.cl.cam.ac.uk/research/nl/bea2019st/`
- **Licence**: the site states plainly that "All corpora are subject to
  similar licences and may only be used for **non-commercial purposes**."
  Compatible with foundational decision #3 (NC acceptable, personal use).

### ERRANT · the scorer

- `pip install errant` (**3.0.2, MIT**), requires `spacy>=3.2,<4` — already a
  project dependency, so it adds no new stack.
- Produces the span-level P / R / **F0.5** the plan specifies. Prefer it to
  the older M2 scorer (`nusnlp/m2scorer`, **GPL-2.0** — avoid bundling).

---

## Tier 2 — breadth, once Tier 1 is wired

| Corpus | Why | Licence |
|---|---|---|
| **JFLEG** (`jhu-clsp/jfleg` on HF, or `keisks/jfleg`) | 1,511 sentences × 4 fluency rewrites — tests whether we over-edit | **CC BY-NC-SA 4.0** (HF card and the GitHub README's License section; corrected 2026-10-14 from "no licence", per the 2026-10-03 registry audit) |
| **CoNLL-2014 test** | the classic 1,312-sentence benchmark; comparability with published GEC numbers | research use |
| **GMEG** (`grammarly/GMEG`) | Grammarly's *own* multi-domain benchmark — formal native, informal native, learner; 4 references each | **no licence declared** |
| **CWEB** (`SimonHFL/CWEB`) | 13,574 web sentences; low error density, so it is a false-positive test by design | **CC BY-NC-SA 4.0** (README's License section; corrected 2026-10-14) |
| **PMC Open Access** | vast published biomedical prose — the domain FP oracle. Split into commercial-use-allowed (CC0/BY/BY-SA/BY-ND) and NC groups; take the CC-BY bulk packages | per-article, machine-readable |
| **arXiv** | metadata **CC0**; full text is *not* generally redistributable — most submissions use arXiv's default licence | mixed — read carefully |

⚠️ **Three of the Tier-2 repos declare no licence at all.** Under default
copyright that means no granted rights, notwithstanding public hosting. Fine
to read and evaluate against locally; do not vendor, redistribute, or train
on them without checking the paper and repo LICENSE text first. This is the
licensing-hygiene risk `research/00-synthesis.md:74` already flagged for
CoEdIT and AESW.

---

## First results (AESW dev, 3,000 sentences, 63,773 words)

`python3.10 eval/stress_test.py --limit 3000`

### 1. False positives on editor-approved prose

Everything below was flagged in text a **professional language editor had
already signed off**.

| Configuration | flags/1000w | sentences with ≥1 flag |
|---|---|---|
| all rules | 25.1 | 35.2% |
| − F601 | 16.4 | 26.6% |
| − F601, − S001 (**craft layer alone**) | **9.5** | 17.6% |
| *thesis-corpus baseline for comparison* | *10.4* | — |

**The craft layer is well calibrated.** At 9.5/1000w on published prose it
lands where the accepted-thesis corpus put it, from a completely independent
source and without PDF-extraction damage. That is real corroboration of the
P4 dogfooding work.

The excess is two rules:

- **F601 (34.7% of all flags)** — abbreviation-at-first-use. This is largely
  a **measurement artifact**: the harness feeds isolated sentences, so F601
  cannot see the abbreviation list or an earlier definition. It is not
  evidence that F601 is broken; it *is* evidence that F601 is meaningless
  without document context, which matters for the macOS/Windows surfaces,
  where the input genuinely is a loose selection.
- **S001 (27.4%)** — domain vocabulary again (`exergy` in the sample). This
  independently confirms the thesis-corpus finding: the shipped scientific
  lexicon has real gaps.

### 2. Detection on text an expert did change

| Measure | grammar dead | grammar live | + tuning |
|---|---|---|---|
| edited sentences | 1,193 | 1,193 | 1,193 |
| flagged *something* | 38.1% | 43.0% | 41.2% |
| flagged **at the edit site** | 13.0% | **15.7%** | **15.3%** |

Two caveats remain:

1. **AESW edits are copy-editing**, not only grammar: commas before "where",
   hyphenation, maths punctuation. Much of it is publisher house style
   Researchly deliberately does not imitate, so a low number here is partly
   correct behaviour, not failure.
2. Edit-site offsets are approximate (detokenization rescales them), so read
   these as coverage indicators, not precise scores.

### 3. What happened when the grammar tier finally ran (P17)

LT001 had never once executed before P17. Switching it on is the first
chance the project has had to measure it, and it immediately failed the
project's own standard:

| Corpus | grammar dead | grammar live | after tuning |
|---|---|---|---|
| **accepted theses** (flags/1000w) | 10.4 | **16.4** ✗ | **12.5** |
| LT001 flags on that corpus | 0 | 1,713 | 592 (−65%) |
| **AESW published prose** (flags/1000w) | 25.1 | 27.9 | 26.9 |
| LT001 alone on AESW | 0 | 3.1/1000w | 2.2/1000w |
| recall at edit site | 13.0% | 15.7% | 15.3% |

16.4/1000w is past the ~11 threshold this project rejects at. The cause was
one rule: **`UPPERCASE_SENTENCE_START` was 39.7% of LT001's flags on theses
and 26.4% on published prose** — the noisiest in both. Scientific sentences
legitimately open with a symbol, a variable, a gene name or a unit
("$R_0$ exceeds one", "log-normal priors were used"), and PDF extraction
manufactures more by splitting sentences mid-clause.

Suppressing it plus four sibling typographical rules (unpaired quotes and
brackets, which fire on numeric-citation and interval notation; dash and
quote rules, which fire on en-dashed year ranges and reference lists) cut
LT001's thesis flags by 65% and the floor to 12.5/1000w **for 0.4pp of
recall** — the trade F0.5 exists to reward. See
`rules_grammar.SKIP_TYPO_RULES`, pinned by a test.

Note the corpora disagree usefully: LT001 costs 6.0 flags/1000w on
PDF-extracted theses but only 3.1 on clean published prose. Most of the
difference is extraction damage, not the rule. `dogfooding-report.md:133`
already said PDFs are hostile input; this quantifies it.

---

## What this establishes for W3

- The craft layer does **not** need tuning. Two independent corpora now
  agree it sits near 10 flags/1000w on good writing.
- **S001 is the precision problem**, on both corpora. Fix the lexicon before
  touching anything else: `estimand(s)`, `urbanicity`, `prespecified`,
  `lockdowns`, `serotypic`, `tradeoff`, `exergy` …
- **F601 needs document context** or a selection-aware downgrade.
- **The grammar tier is now live and tuned**, at 12.5/1000w. The remaining
  gap to the 10.4 pre-grammar baseline is LT001 doing its job.
- Recall is **15.3%**, honestly measured with every tier running. That is the
  number a local GEC tagger has to beat to justify itself.

### Wiring order

1. ~~`brew install openjdk@17`~~ — done, and Researchly now finds keg-only
   JDKs by itself. **Re-run the stress test → the real baseline.**
2. Fix the S001 lexicon; re-run both corpora.
3. `pip install errant`; build the academic-ESL regression set from
   W&I+LOCNESS filtered to academic register.
4. Only then consider the local GEC tagger — with a before/after number
   ready to justify it.
