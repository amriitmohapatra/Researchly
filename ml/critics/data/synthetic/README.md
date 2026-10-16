# Synthetic labelled paragraphs for the S5 critic (Laya, Task A)

## Part A: epidemiology, public health, clinical research

Written 2026-10-16 for Researchly. These are original paragraphs in the
style of PhD and master's drafts, not anyone's real writing. They were
not copied or paraphrased from any article, thesis, book or course. All
numbers are invented. Licence: Researchly's own. Topics: infectious-disease
modelling (SEIR, renewal equations, R_t, Bayesian calibration in Stan),
surveillance, vaccine effectiveness, cohort, case-control and test-negative
studies, trials, public-health interventions and health equity. Spelling
is a mix of UK and US English.

About two thirds of the paragraphs contain planted slips: wordiness, a
vague "this", long sentences, hedge stacks and boosters, unsupported
causal claims, tense shifts, missing articles and agreement errors,
repeated typos, undefined abbreviations, inconsistent terms, numbers
without units and agentless passives in the Discussion. The other 50
paragraphs (33%) are clean. Methods paragraphs use the passive voice as a
correct convention.

| File | What it holds |
|---|---|
| `part-a-paragraphs.json` | 150 paragraphs `{paragraph, section, text}`, numbered 1–150 |
| `part-a-labels.json` | 227 labels in the Label page's export format (version 1; attempt ids `syna0001`…`syna0150`, one per paragraph) |
| `part-a-notes.jsonl` | One line per label: paragraph, flag, rule_id, verdict, a one-line reason, the flagged words (shortened) |

**How the flags were produced.** Each paragraph was checked exactly as
the Label page and `harness.label_page_flags` do. The text sits under its
section heading, with every tier on (spaCy, SymSpell and local
LanguageTool; the GEC tier has no model and abstains). Preferences are
hidden and the mode is revise. Flags are sorted by start, then category.
The four limitations paragraphs (141, 143, 147 and 149) are filed as
`discussion`, because the Label page has no Limitations heading.

**Verified.** `zero_shot.py flags --labels part-a-labels.json --paragraphs
part-a-paragraphs.json --export-items …` matched every label to its flag:
211 items, 16 unsure set aside, 0 "flag not found", 0 replaced.
`finetune.py data flags` wrote 173 train and 38 dev rows.
`label_precision.load` read all 227 labels and dropped none.

**Verdicts.** Each flag was judged by one question: would a careful
supervisor want the writer to act on it here? The rules are in
`docs/labelling-guide.md`. A flag was marked useful only when it pointed
at a real problem and its advice was sound, not merely because a slip
had been planted nearby. For AB802, a card was marked wrong when most of
the moves it called missing were present, and unsure when it was half
right.

| Section | Paragraphs | With flags | Flags | Useful | Wrong | Unsure |
|---|---|---|---|---|---|---|
| introduction | 30 | 23 | 42 | 32 | 7 | 3 |
| methods | 35 | 22 | 44 | 35 | 8 | 1 |
| results | 30 | 21 | 38 | 30 | 7 | 1 |
| discussion (incl. 4 limitations) | 39 | 25 | 61 | 43 | 13 | 5 |
| abstract | 10 | 10 | 29 | 18 | 8 | 3 |
| conclusion | 6 | 5 | 13 | 8 | 2 | 3 |
| **All** | **150** | **106** | **227** | **166** | **45** | **16** |

Precision (useful / (useful + wrong)) is 0.79 (Wilson 95% interval about
0.73–0.84). Planted slips make this sample richer in true problems than
real drafts, so do not read this figure as the engine's precision.

| Rule | Flags | Useful | Wrong | Unsure | Precision |
|---|---|---|---|---|---|
| F601 | 39 | 37 | 1 | 1 | 0.97 |
| S001 | 31 | 27 | 4 | 0 | 0.87 |
| C303 | 21 | 5 | 14 | 2 | 0.26 |
| C301 | 17 | 14 | 2 | 1 | 0.88 |
| W202 | 16 | 15 | 0 | 1 | 1.00 |
| G106 | 14 | 14 | 0 | 0 | 1.00 |
| E703 | 10 | 6 | 0 | 4 | 1.00 |
| AB802 | 10 | 4 | 5 | 1 | 0.44 |
| G101 | 9 | 3 | 5 | 1 | 0.38 |
| C302 | 9 | 9 | 0 | 0 | 1.00 |
| C305 | 8 | 8 | 0 | 0 | 1.00 |
| G105 | 8 | 8 | 0 | 0 | 1.00 |
| G103 | 8 | 0 | 7 | 1 | 0.00 |
| W205 | 7 | 7 | 0 | 0 | 1.00 |
| D902 | 5 | 0 | 4 | 1 | 0.00 |
| LT001 | 4 | 3 | 1 | 0 | 0.75 |
| E706 | 3 | 0 | 0 | 3 | – |
| W207 | 3 | 3 | 0 | 0 | 1.00 |
| GN201 | 2 | 2 | 0 | 0 | 1.00 |
| G107 | 2 | 0 | 2 | 0 | 0.00 |
| C304 | 1 | 1 | 0 | 0 | 1.00 |

**Precision findings** (the wrong flags are candidates for don't-fire tests):

- **C303 (causal verbs), 14 of 21 wrong.** It fires on any causal verb,
  but most were not inferential claims:
  - microbiology: "cases caused by serotypes";
  - descriptions of statistics: "heterogeneity was reduced";
  - model mechanisms and outputs: "infections ... are prevented",
    "a fifth cycle averted";
  - "affected" used as an adjective ("residents affected");
  - established background: "chemoprevention reduces malaria";
  - negated trial results and plans for future work.

  It was right on observational "causes", "caused", "prove" and
  "prevented".
- **G103 (nominalizations), 0 of 8 useful.** Its triggers were technical
  terms and variable names (education, registration, misclassification,
  concurrency, prescription), and its spans often run to 40–50 words.
- **D902 (missing gap in the Introduction), 0 of 5 useful.** It fired
  only on clean paragraphs whose gaps were stated with "however", "but
  most assume", "rarely tested" or "rarely applied". It may check for a
  narrower set of cue phrases.
- **AB802 (abstract moves), 5 of 10 wrong.** It reports findings,
  significance and methods as missing when they are present, even in a
  complete structured abstract (paragraph 131) and a well-formed
  unstructured one (paragraph 133, where all five listed moves are
  present).
- **G101 (subject–verb distance), 5 of 9 wrong.** Two were misparses,
  where the counted "subject" was not the verb's subject (paragraphs 8
  and 56). The other three were effect estimates in parentheses, a short
  "such as" example and a standard matched-control phrase.
- **G107 (noun stacks), 2 of 2 wrong.** One was a misparse ("household
  crowding affects tuberculosis transmission", where "affects" is a
  verb). The other was the fixed term "community health worker
  programmes".
- **C301 (hedge stacks), 2 wrong.** It treated "may ... less likely" and
  "may be more likely" as stacked hedges, but "likely" there states a
  behavioural probability, not a hedge.
- **S001 (spelling), 4 wrong.** It flagged correct domain words:
  "pseudonymised", "deregistration", "condomless", and "NPIs" (suggested
  as "Apis").
- **LT001, 1 wrong.** It suggested the hyphenated "all-time" in "at all
  time points".
- **F601** was right 37 of 38 times. The miss: it asked to expand "RT"
  inside "RT-PCR".

**Planted slips the engine did not flag** (recall notes, not labels):

- **Agreement errors:** "threaten", "depend", "reduces", "has", "girls
  ... was", "Coverage ... were", "follow-up ... were", "this gap have",
  "rainfall was".
- **Missing articles:** in paragraph 138 ("Cholera vaccination campaign
  was conducted in displacement camp").
- **Wordiness:** "At the present time", "In view of the fact that",
  "With regard to", "In terms of".
- **Boosters and filler:** "really", "very", "Remarkably", "definitely".
- **Agentless passives in the Discussion:** "Mistakes were made",
  "Errors were introduced", "Efforts were made".
- **Others:** tense shifts, numbers without units ("6", "-80",
  "4.2 per child"), inconsistent terms (VE/efficacy,
  serial interval/generation time, R0/basic reproductive ratio,
  participants/subjects/patients), and the undefined ESS and CIN2+.
