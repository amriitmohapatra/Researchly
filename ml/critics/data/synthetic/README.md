# Synthetic Task A data for Laya (flag useful?)

Paragraphs written for Researchly so the owner can train Laya's Task A
("is this flag useful?") without labelling their own writing first. Every
paragraph is original text with invented data and no real people's names;
nothing was copied or closely paraphrased from any article, thesis, book or
course (licence: ours). Each part has three files:

| File | What it holds |
|---|---|
| `part-X-paragraphs.json` | `{"version": 1, "paragraphs": [{"paragraph", "section", "text"}]}`: the format `harness.label_paragraphs` reads |
| `part-X-labels.json` | the Label page's `researchly-labels.json` format (version 1; `paragraph, rule_id, category, section, verdict, attempt, flag`) |
| `part-X-notes.jsonl` | one line per label: `paragraph, flag, rule_id, verdict, reason, words` (the flagged words and why the verdict) |

Flags were found exactly as the harness finds them
(`harness.label_page_flags`: the paragraph under its section heading, all
tiers on, mode revise, preferences hidden, sorted by start then category),
so `zero_shot.py flags` and `finetune.py data flags` re-find every label.
If the engine changes, labels whose rule is no longer at its position are
skipped and counted, as designed.

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

## Part C: social sciences, humanities, health policy, other genres

150 paragraphs (61 to 199 words, 14,255 words in all), written 2026-10-16.

- **Fields**: sociology (gig work, refugees, housing first, professions),
  education (teacher beliefs, school counselling, undermatching, STEM
  attrition, parental involvement), economics (unemployment insurance, minimum
  wage, cash transfers, digital payments), psychology (mindfulness trial,
  mindset, loneliness, school start times), history (a nineteenth-century
  strike and its archives, colonial sanitary reports), ethics (consent,
  moral distress), and health policy (alcohol minimum pricing, catastrophic
  spending, insurance documents, antibiotic prescribing, dental reminders).
  The methods include interviews, thematic analysis, focus groups, archival
  and oral history work, mixed methods, RD, DiD, RCTs and surveys.
- **Sections** (as the harness heads them): Introduction 30, Methods 30,
  Results 25, Discussion 35, Abstract 10. Limitations and conclusions come
  to 10: the 5 limitations paragraphs (131–135) are filed under
  `discussion` because the harness has no Limitations heading (an unknown
  section would be checked as Introduction), and the 5 conclusions
  (136–140) under `conclusion`. The other genres come to 10: thesis chapter
  openings that state a gap (141–143) and grant aims (149–150) under
  `introduction`; policy-brief recommendations (144–145) under
  `conclusion`; responses to reviewers (146–148) under `discussion`.
- **Quality**: about two thirds carry realistic draft slips, among them
  wordiness, nominal chains, a vague "this", run-on sentences, stacked hedges
  and boosters, overclaiming from interviews, weak gaps, tense shifts,
  agreement errors, typos (some repeated), undefined abbreviations,
  inconsistent spelling or terms, and mixed "I"/"we". About a third are
  clean. Some carry correct conventions that a naive checker might flag:
  first person in qualitative methods, verbatim participant quotations, and
  long but clear humanities sentences. The English varies between UK, US and
  Indian usage ("till date", "discussed about", "upto", "the same", "OBC",
  "gram sabha").

### Labels

216 flags in 112 paragraphs (38 paragraphs drew no flag): **114 useful, 78
wrong, 24 unsure**. Engine precision without a critic is 114 / 192 = 0.59.
All 216 labels load through `label_precision.load` and are re-found by
`zero_shot.flag_items`: the 192 decided labels match and are kept, the 24
unsure are set aside, and none are skipped as "flag not found".
`finetune.py data flags` writes 151 training rows and 41 dev rows.

Attempt ids are `sync0001`…`sync0150`, one per paragraph. They are lower
case because `label_precision.load` accepts only `[a-z0-9]{6,16}`, so
`synC0001` would be rejected.

| Rule | n | useful | wrong | unsure | precision |
|---|---|---|---|---|---|
| LT001 | 27 | 24 | 3 | 0 | 0.89 |
| D902 | 23 | 4 | 18 | 1 | 0.18 |
| F601 | 22 | 8 | 5 | 9 | 0.62 |
| C303 | 20 | 4 | 16 | 0 | 0.20 |
| E703 | 12 | 7 | 5 | 0 | 0.58 |
| S001 | 10 | 7 | 3 | 0 | 0.70 |
| G101 | 10 | 2 | 5 | 3 | 0.29 |
| G105 | 10 | 9 | 1 | 0 | 0.90 |
| AB802 | 10 | 0 | 7 | 3 | 0.00 |
| G103 | 8 | 5 | 3 | 0 | 0.62 |
| C305 | 8 | 7 | 1 | 0 | 0.88 |
| C302 | 8 | 7 | 1 | 0 | 0.88 |
| W202 | 5 | 5 | 0 | 0 | 1.00 |
| C301 | 5 | 3 | 1 | 1 | 0.75 |
| C304 | 5 | 3 | 0 | 2 | 1.00 |
| G106 | 5 | 2 | 1 | 2 | 0.67 |
| W208 | 4 | 1 | 3 | 0 | 0.25 |
| G107 | 4 | 0 | 4 | 0 | 0.00 |
| W201, W205 | 3 each | 3 each | 0 | 0 | 1.00 |
| D903, G102, E707 | 2 each | 1, 0, 2 | 0, 1, 0 | 1, 1, 0 | — |
| G104, L901, GN201, GN207, W210, D905, E705, E704 | 1 each | 1 each (E704 unsure) | 0 | — | — |

**How the labels were made.** The author of the paragraphs labelled them,
so a planted slip nearby did not make a flag useful: the card itself had to
be right about the flagged words. The labels follow
`docs/labelling-guide.md`:

- An abbreviation in Methods, Results or Discussion that the paper would
  have defined in its Introduction is **unsure**: the paragraph alone cannot
  say.
- A proper name (UCLA, SPSS, ATLAS.ti) flagged as an undefined
  abbreviation is **wrong**.
- Causal verbs are **useful** under C303 only when the design does not
  support them. A randomised trial or a difference-in-differences design
  does.
- A long sentence is **unsure** when it is carefully built and **useful**
  when it is padded.

### What the labels say about the rules (Part C only; small counts)

- **D902 (no gap statement)**: wrong on 18 of 22 decided. Its gap lexicon
  misses common phrasings: "less is known", "it is not known whether",
  "much less clear", "remains contested", "rarely tested", "far fewer
  estimates", "neither account explains", "few empirical studies" (the
  regex wants "few studies"), and counter-claim niches ("Yet …"). It also
  requires a contrastive word even when "limited" states the gap.
- **AB802 (abstract moves)**: no useful flag (7 wrong, 3 unsure). It lists
  as missing moves that are present: methods written in plain prose, and
  even a section headed "Methods:"; findings after "It shows that" or "The
  study found that".
- **C303 (causal verb)**: wrong on 16 of 20. It fires on randomised and
  difference-in-differences results, on recommendations ("should be
  reduced"), on definitions ("prevented from acting"), on others'
  assumptions, and on a sentence that itself says causation cannot be
  established.
- **G107 (noun stack)**: 0 of 4. Each time it read a verb as a noun
  ("ledger records remittances", "platforms experience").
- **G101 (subject–verb distance)**: 2 of 7. It measures to a verb in a
  subordinate or second coordinated clause, and it names the wrong subject.
- **W208 (contractions)**: wrong 3 of 4, all inside verbatim participant
  quotations, which are not masked.
- **F601 (first use of an abbreviation)**: it flags proper names, and a
  single paragraph cannot see definitions made earlier.
- **E703 (naked "this")**: 7 of 12. It fires when the previous sentence
  holds a single finding.
- **S001**: "SHGs" (defined in the sentence before) became "Shags",
  "socio" was flagged in "socio-economic", and "gram sabha" was flagged.
- **LT001**: three false flags: "who attends", ALL_TIME_HYPHEN on "at all
  time points", and "nor were help" with "where/we" offered as the fix.

Recall (not labelled, for interest): many planted agreement errors with a
plural noun subject went unflagged ("Codes was then collated", "Minor
differences in wording was found", "Transaction charges was mentioned",
"Enrolment records … was obtained", "The decrease … were concentrated").
So did "affect" for "effect", "wether", "comprised of", "respondents were
explained about", and a tense shift ("is conducted … is reached").

To train on all parts together, concatenate the `labels` lists and the
`paragraphs` lists after renumbering each part's paragraphs into one
sequence (attempt ids are already distinct per part).
