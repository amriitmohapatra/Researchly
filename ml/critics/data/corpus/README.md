# Corpus flag labels for Laya Task A (published prose)

1,001 judged flags on 374 body paragraphs of 164 open-access research
articles (CC BY / CC0 only) from the S5a corpus (`ml/corpus/`). They give
the "is this flag useful?" critic (PLAN S5b, Task A; ARCHITECTURE.md ADR-06)
examples of **polished, published writing**, where many of the engine's
flags are wrong. They sit beside the synthetic-draft labels, which show
rough writing where most flags are right.

**No article text is in this folder.** It holds verdicts and pointers; the
paragraphs are rebuilt from the corpus cache, outside the repository, by
`rebuild.py`, which checks a SHA-256 of every paragraph.

| File | What it is |
|---|---|
| `train-labels.json` | 800 labels, 284 paragraphs, 120 articles from the corpus **train** split. The harness's `researchly-labels.json` format (version 1): `paragraph, rule_id, category, section, verdict, attempt, flag`. Attempt ids `corptNNNN` (one per paragraph). |
| `test-labels.json` | 201 labels, 90 paragraphs, 44 articles from the corpus **test** split: held out for evaluation only. Attempt ids `corpeNNNN`. No article appears on both sides. |
| `paragraph-index.json` | For each paragraph number: split, PMCID, discipline, licence, `body_index` (its index in the list `ml/corpus/weak_labels.labels_for(row, xml)[1]` returns), section, position within the section, SHA-256 of the text, word count. |
| `notes.jsonl` | One line per label: paragraph, flag, rule, verdict, a one-line reason, and at most the first six flagged words. |
| `rebuild.py` | Rebuilds `train-paragraphs.json` / `test-paragraphs.json` outside the repo (fetching any missing article from Europe PMC), verifying every hash. |
| `test_corpus_flag_labels.py` | `rebuild.py` on a tiny synthetic fake corpus, plus checks that the committed files are text-free pointers to trainable articles. |

## Run it (the owner's Mac)

```bash
# 1. paragraphs, outside the repo (~1 min; reuses ~/.researchly/corpus)
python3.10 ml/critics/data/corpus/rebuild.py --out ~/laya-corpus
# 2. Laya training files (engine's Python; re-checks each paragraph as the Label page does)
python ml/critics/laya/finetune.py data flags \
  --labels ml/critics/data/corpus/train-labels.json \
  --paragraphs ~/laya-corpus/train-paragraphs.json --out ~/laya-data-corpus
# 3. held-out evaluation of a trained checkpoint
python ml/critics/laya/zero_shot.py flags --model <checkpoint> \
  --labels ml/critics/data/corpus/test-labels.json \
  --paragraphs ~/laya-corpus/test-paragraphs.json --out ~/laya-corpus-heldout.json
```

To pool with other label sets, keep paragraph numbers distinct (these use
1–374). Step 2 gives 544 train / 130 dev rows from the train labels (the
126 `unsure` verdicts are left out, as the harness does).

## How the labels were made (2026-10-16)

- **Articles.** A seeded, stratified sample from `ml/corpus/manifest.jsonl`:
  `use: "train"` (CC BY / CC0) only, never the NC/ND `eval` articles; at
  least two IMRaD sections; 14 train-split and up to 5 test-split articles
  per discipline. Licences of the labelled paragraphs: CC BY 4.0 360,
  CC BY (unversioned statement) 13, CC0 1.
- **Paragraphs.** From `weak_labels.labels_for` (the corpus's own splitter),
  40–220 words, under Introduction, Methods, Results or Discussion (all
  four are `harness.SECTION_LABELS`, so no paragraph falls back to an
  Introduction heading). Paragraphs showing citation-removal artefacts
  (",,", "..", a preposition before punctuation) were skipped; the
  extractor drops citation markers, so these would carry false grammar
  flags no real draft has. Some paragraphs are figure legends (the
  splitter keeps `<p>` inside captions); they are labelled like any text.
- **Engine.** Each paragraph was checked exactly as
  `harness.label_page_flags` does (section heading line above it,
  preferences hidden, `mode="revise"`, all tiers on: parser, spelling,
  LanguageTool grammar), and flags are numbered in its order, so `flag`
  indexes the harness's list.
- **Balance.** Paragraphs carrying rarer rules were taken first, then a
  round-robin over discipline × section. Any rule was capped at 15% of a
  split's labels (F601: 150 of 1,001), D902 at 7.5%, and at most two F601
  and three of any other rule per paragraph; flags over a cap are simply
  not labelled.
- **Judging.** Every flag was judged by Claude per
  [`docs/labelling-guide.md`](../../../../docs/labelling-guide.md): would a
  careful supervisor want this published author to act on it here?
  Article-level facts were checked against the full article: F601
  (acronym first use) is *wrong* when the acronym is defined in the
  abstract or earlier in the body, *useful* when it is never or only
  later spelled out, *unsure* for standard ones (IFN, API); D902 (no gap
  statement) is *wrong* when the article's Introduction states one.
  *Unsure* also covers taste calls and flags caused by extraction (a
  stripped citation or table reference). One labeller, no adjudication:
  read the verdicts as a careful first pass, not a gold standard.

## Counts

| | Train | Test | All |
|---|---|---|---|
| Articles | 120 | 44 | 164 |
| Paragraphs | 284 | 90 | 374 |
| Labels | 800 | 201 | 1,001 |
| useful | 222 | 54 | 276 |
| wrong | 452 | 115 | 567 |
| unsure | 126 | 32 | 158 |

Paragraphs by discipline (train / test): clinical-medicine 24/10,
computational-statistics 29/12, ecology-evolution 27/9, engineering 28/12,
epidemiology 33/13, humanities 26/7, molecular-biology 29/4,
physical-earth-sciences 31/11, public-health 26/6, social-sciences 31/6.
By section (paragraphs / labels): Introduction 96/277, Methods 73/164,
Results 100/238, Discussion 105/322.

By category: correction 32 useful / 100 wrong / 5 unsure; improvement
183 / 203 / 90; convention 61 / 264 / 63.

| Rule | Labels (train/test) | Useful | Wrong | Unsure | Precision |
|---|---|---|---|---|---|
| F601 | 150 (120/30) | 11 | 127 | 12 | 0.08 |
| S001 | 87 (69/18) | 4 | 82 | 1 | 0.05 |
| G101 | 86 (64/22) | 23 | 44 | 19 | 0.34 |
| C303 | 70 (59/11) | 2 | 63 | 5 | 0.03 |
| G103 | 70 (51/19) | 6 | 55 | 9 | 0.10 |
| D902 | 68 (53/15) | 0 | 55 | 13 | 0.00 |
| G106 | 64 (51/13) | 50 | 2 | 12 | 0.96 |
| C304 | 55 (47/8) | 15 | 16 | 24 | 0.48 |
| LT001 | 48 (35/13) | 28 | 16 | 4 | 0.64 |
| W202 | 43 (32/11) | 43 | 0 | 0 | 1.00 |
| G107 | 40 (33/7) | 5 | 28 | 7 | 0.15 |
| W203 | 31 (27/4) | 14 | 13 | 4 | 0.52 |
| G104 | 25 (20/5) | 0 | 22 | 3 | 0.00 |
| G105 | 24 (20/4) | 14 | 3 | 7 | 0.82 |
| W201 | 24 (20/4) | 18 | 2 | 4 | 0.90 |
| E703 | 24 (22/2) | 7 | 12 | 5 | 0.37 |
| G102 | 13 (9/4) | 4 | 0 | 9 | 1.00 |
| E706 | 13 (12/1) | 2 | 2 | 9 | 0.50 |
| C305 | 10 (8/2) | 2 | 7 | 1 | 0.22 |
| E704 | 7 (5/2) | 0 | 2 | 5 | 0.00 |
| C302 | 6 (5/1) | 1 | 5 | 0 | 0.17 |
| S003 | 6 (5/1) | 0 | 6 | 0 | 0.00 |
| 17 rules with 1–4 labels | 37 | 27 | 5 | 5 | — |

Precision is useful / (useful + wrong), on published prose, so it is a
floor for the engine on drafts, not the S4 number. Read the small rows as
anecdotes.

What the wrong labels say (tuning targets; CLAUDE.md #5: each becomes a
don't-fire test before a rule changes):

- **F601** fires on every acronym in an isolated paragraph; 127 of 138
  decided were defined earlier in the article. On whole documents it
  would mostly stay silent; on the Label page it is noise.
- **S001**: species epithets (*thaliana*, *funestus*), R packages
  (limma), field terms (microplastics, ferroptotic) and accented names
  split by the tokenizer ("Fernández" -> "ndez", "Martínez" -> "nez").
  The 4 useful hits were real typos (avaliable, institutiuon, hearafter).
- **C303** flags nouns ("results in Table"), experiments that do support
  causation, definitions and stated goals; only 2 of 65 were useful.
- **D902** fires on every Introduction paragraph checked alone; no
  published Introduction here lacked a gap.
- **G104** "agent is stated": every decided case was a passive that keeps
  the topic in subject position or a method as agent (0 of 22).
- **G103** counts technical terms and variable names as nominalizations;
  **G107** flags terms of art and misparses across verbs; **G101** often
  misidentifies subject or verb (figure legends, lists, appositives).
- **C304** splits: right when "significant" means large or important in
  Discussion, wrong when a test or p-value sits in the same sentence.
- Reliable even on published prose: G106 (long sentences), W202, W201,
  G105, C301, W205, and LT001's real grammar slips.

## Licence and attribution

Only articles whose manifest `use` is `train` (CC BY 4.0, CC BY
unversioned, CC0) are used; `rebuild.py` refuses anything else and the
test checks every indexed article. CC BY requires attribution when text is
reused: the PMCIDs are in `paragraph-index.json`, and the DOI, journal,
year and licence evidence of each are in `ml/corpus/manifest.jsonl`. The
rebuilt paragraphs files stay outside the repository and are not shipped;
a model trained on them is governed by the registry entry the lead adds
in `ml/datasets.yaml` (`s5a-oa-corpus-cc-by`, plus a use note for these
labels).
