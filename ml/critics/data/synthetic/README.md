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
