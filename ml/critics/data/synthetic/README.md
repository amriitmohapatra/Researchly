# Synthetic labelled paragraphs for Laya Task A

Synthetic paragraphs written for Researchly (licence: ours; nobody's real
writing), checked with the engine exactly as the Label page checks them
(`harness.label_page_flags`: the paragraph under its section heading, every
tier on, preferences hidden, mode revise) and labelled flag by flag per
[`docs/labelling-guide.md`](../../../../docs/labelling-guide.md).

## Part B

Life sciences, ecology and evolution, climate and earth science, materials
and engineering, statistics and machine learning, computational modelling.
Written and labelled 2026-10-16.

| File | What it holds |
|---|---|
| `part-b-paragraphs.json` | 150 paragraphs, `{"paragraph": n, "section", "text"}`, n = 1..150 |
| `part-b-labels.json` | 306 labels in the Label page's export format (`attempt` = `synb0001`…, `flag` = position in the Label page's order) |
| `part-b-notes.jsonl` | one line per label: paragraph, flag, rule_id, verdict, a one-line reason, the flagged words |

About 70% of paragraphs (105) carry realistic draft slips (wordiness, vague
"this", run-on sentences, stacked hedges, boosters and overclaiming, tense
shifts, agreement and article errors, repeated typos, undefined
abbreviations, inconsistent terms and unit spacing, figures cited out of
order); 45 are clean, including correct conventions a naive checker might
flag (passive Methods, species and gene names, equations in words). US and
UK spelling both appear. Limitations paragraphs are filed as `discussion`
(the Label page has no "limitations" section).

Check that the labels still match the engine (no weights needed):

```bash
python ml/critics/laya/zero_shot.py flags \
  --labels ml/critics/data/synthetic/part-b-labels.json \
  --paragraphs ml/critics/data/synthetic/part-b-paragraphs.json \
  --export-items /tmp/part-b-items.jsonl
# 2026-10-16: {"items": 284, "skipped": {"replaced": 0, "unsure": 22,
#              "no paragraph text": 0, "flag not found": 0}}
```

### By section

| Section | Paragraphs | With flags | Flags | Useful | Wrong | Unsure |
|---|---|---|---|---|---|---|
| introduction | 30 | 30 | 86 | 50 | 29 | 7 |
| methods | 35 | 25 | 56 | 40 | 13 | 3 |
| results | 30 | 25 | 51 | 30 | 15 | 6 |
| discussion | 38 | 30 | 71 | 50 | 18 | 3 |
| abstract | 10 | 10 | 31 | 14 | 14 | 3 |
| conclusion | 7 | 5 | 11 | 9 | 2 | 0 |
| **all** | **150** | **125** | **306** | **193** | **91** | **22** |

Precision (useful / (useful + wrong)): 68% (Wilson 95%: 62% to 73%).
On the 45 clean paragraphs: 2 useful, 36 wrong, 7 unsure.

### By rule

| Rule | Flags | Useful | Wrong | Unsure | Precision |
|---|---|---|---|---|---|
| S001 | 45 | 23 | 22 | 0 | 51% |
| F601 | 44 | 35 | 6 | 3 | 85% |
| W202 | 27 | 26 | 0 | 1 | 100% |
| C303 | 18 | 0 | 17 | 1 | 0% |
| C301 | 16 | 14 | 2 | 0 | 88% |
| D902 | 15 | 0 | 14 | 1 | 0% |
| G106 | 15 | 14 | 0 | 1 | 100% |
| E703 | 14 | 10 | 0 | 4 | 100% |
| C305 | 12 | 12 | 0 | 0 | 100% |
| G101 | 12 | 6 | 6 | 0 | 50% |
| C302 | 10 | 9 | 1 | 0 | 90% |
| C304 | 10 | 3 | 3 | 4 | 50% |
| AB802 | 10 | 0 | 7 | 3 | 0% |
| LT001 | 8 | 7 | 1 | 0 | 88% |
| G103 | 7 | 0 | 7 | 0 | 0% |
| G107 | 5 | 0 | 4 | 1 | 0% |
| G105 | 5 | 5 | 0 | 0 | 100% |
| W205 | 4 | 4 | 0 | 0 | 100% |
| W207 | 4 | 4 | 0 | 0 | 100% |
| E706 | 4 | 3 | 0 | 1 | 100% |
| G102, E704, W201, N101 | 3 each | 3 each | 0 | 0 | 100% |
| E705, GN201, W206, W211, E701, W203 | 1 each | 1 each | 0 | 0 | 100% |
| G104 | 1 | 0 | 1 | 0 | 0% |
| D903, G108 | 1 each | 0 | 0 | 1 each | – |

### What the wrong labels say about the engine

- **S001** (22 wrong): species and gene names (*terrestris*, *thaliana*,
  *magna*, *reinhardtii*, *glandulifera*, *dlt*) and field terms
  (*mitophagy*, *peatlands*, *landfalling*, *poroelastic*, *roguing*,
  *tokenised*, *whitespace*, *agri-*) are read as typos.
- **C303** (17 wrong): causal verbs are flagged in manipulative experiments
  and model comparisons, where the design supports them, and in non-claims
  ("raised under identical conditions", "injection rates were reduced").
- **D902** (14 wrong): on a single Introduction paragraph it fires whenever
  its cue words are absent, even when the gap is stated ("What remains
  unknown is whether…", "it is not known whether…").
- **AB802** (7 wrong, 3 unsure): its move lexicon misses ordinary
  life/physical-science phrasing ("is not well understood", "poorly known",
  "We measured/sampled/pre-trained", "These results support"), so clean
  abstracts are told five of six moves are missing.
- **G103** (7 wrong): counts technical nouns (*selection*, *gene
  expression*, *calibration*, *In addition*) as hidden verbs.
- **G101 / G107** (6 + 4 wrong): parse errors: a compound-subject list, a
  verb read as a noun ("diversity predicts", "study tracking"), and one
  span that runs across a sentence boundary after the unit "m.".
- **F601** (6 wrong): universally known acronyms (CRISPR, GPU, NE) and
  SDS-PAGE split into two "undefined" abbreviations.
