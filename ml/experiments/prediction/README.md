# Text prediction: an experiment, not a feature

**Owner decision, 2026-10-14:** test next-word prediction as an experiment.
CLAUDE.md non-negotiable #1 keeps generative drafting out of the product, and
prediction suggests the author's next words, so this folder stays outside
`packages/` and `apps/`. No surface imports it, its model is written to a
cache outside the repository, and nothing here ships. Whether prediction may
ever reach a surface (off by default, multi-word terms only, or not at all)
is the owner's call, recorded in CLAUDE.md if it changes.

## The question

The engine the owner was given (research/05) predicts the next words of
everyday email. Does a model trained on **published scientific prose** predict
a scientist's next word better, and does knowing the **section** help?

## Data

The 115 CC BY / CC0 PMC articles of the real-document bench
(`ml/realdocs/manifest.yaml`; registry `realdocs-europepmc-oa`, which permits
`train_experimental`). Fetched at run time into a cache outside the
repository; a fixed 20% of articles (by a hash of the id) is held out.

```sh
python3.10 ml/realdocs/fetch.py --cache ~/.cache/rd --only $(grep -o 'id: pmc-PMC[0-9]*' ml/realdocs/manifest.yaml | cut -d' ' -f2)
python3.10 ml/experiments/prediction/predict.py evaluate --cache ~/.cache/rd
python3.10 ml/experiments/prediction/predict.py try --cache ~/.cache/rd --section methods "the model was"
```

## Models

| Model | What it knows |
|---|---|
| general | SymSpell's English unigram and bigram counts (symspellpy, MIT): a stand-in for an everyday-English keyboard model |
| academic | 1–4-grams of the training articles, stupid backoff (Brants et al. 2007) |
| academic+section | the same, interpolated 50/50 with a model of the current section (Abstract, Introduction, Methods, Results, Discussion) |

## Result (2026-10-14)

20,014 held-out words in 7,521 sentences from the held-out articles:

| Model | Next word, top 1 | Top 3 | Keystrokes saved |
|---|---|---|---|
| general | 11.4% | 19.1% | 29.6% |
| academic | **14.3%** | **22.9%** | **44.6%** |
| academic+section | 14.1% | 22.5% | 44.3% |

*Keystrokes saved*: the share of letters a writer would not type if they
accepted the right word as soon as it appeared among the top three.

- Training on scientific prose helps a great deal: half as many keystrokes
  again are saved (44.6% vs 29.6%), with only ~92 training articles.
- Knowing the section did **not** help at this size: the per-section models
  are too sparse, and interpolating them dilutes the whole-corpus model. Worth
  retrying with a much larger licence-clean corpus (S5a), not before.

## If it ever moves towards the product

- Train on a large CC BY / CC0 corpus (S5a), never on theses (D6).
- Offer only completions of the word being typed, or fixed multi-word terms
  ("confidence interval", "basic reproduction number"), never sentences.
- Off by default, local, and labelled as prediction, not advice.
