# How a keyboard autocorrect engine is built — and what it means for Researchly

*2026-10-14. Written from the structure of an engine bundle the owner received
from a friend: 22 files, decoded tables plus the app's own data files. Its
licence is unknown, and its form shows it was extracted from a commercial
mobile keyboard / writing app (see §4). **None of its data is in this
repository, and none may be added** (`ml/datasets.yaml`: nothing is used
without a licence that permits it). This note keeps only what any reader of
the published literature could know: the architecture, its sizes, and the
techniques it rests on. Researchly's own engine is rebuilt from open data
(`research/06-open-resources.md`, `packages/core/researchly/spellmodel/`).*

---

## 1. The components

The bundle is a complete autocorrect + text-prediction pipeline of the
classic **noisy-channel** design. For a typed word *w* and candidate *c* it
ranks by P(c | context) · P(w | c), then a classifier decides whether the
best candidate is safe to apply.

| # | Component | Size and form | What it does | Technique it rests on |
|---|---|---|---|---|
| 1 | **Vocabulary** | 165,832 words; rank, two 32-bit flag fields, unigram count; the app file groups words by length | The set of valid words, with frequencies for the prior P(c). The flag fields are per-word feature bits (word classes the ranker's "previous word" features use). Grouping by length speeds up candidate search | Frequency dictionaries (Norvig 2007; SymSpell) |
| 2 | **Completion vocabulary** | 88,125 words with counts | Prefix completion of the word being typed | Frequency-ranked prefix lookup |
| 3 | **N-gram language model** | Orders 1–5; about 491 billion training tokens; counts below 5,000 dropped; counts quantised to 63,912 levels; stored as a minimal perfect hash with 16-bit fingerprints (5.98 M slots, 1.2 M displacement slots) | P(c \| previous words): the context term. The hash can be queried but not listed, so the bundle's "probed" n-gram files are what someone recovered by querying it with candidate n-grams | Web-scale n-grams with stupid backoff (Brants et al. 2007); randomised / fingerprinted LMs (Talbot & Brants 2008; Guthrie & Hepple 2010; Pauls & Klein 2011); hash-and-displace perfect hashing (Belazzougui et al. 2009); count quantisation |
| 4 | **Noisy-channel error model** | 23,051 context-dependent edits, keyed `<ctx><deleted>\|<ctx><inserted>` over words wrapped as `^word$`; log-probabilities quantised to 10,636 levels | P(typed \| intended): how likely each slip is ("ie"→"ei", a dropped letter after a vowel, a doubled consonant). Context-dependent edits are what make "recieve" cheap and "rexeive" expensive | Generic string-to-string edits with context (Brill & Moore 2000), after Kernighan, Church & Gale (1990) |
| 5 | **Ranker / autocorrect gate** | A 38 → 64 → 64 → 1 MLP with sigmoid output, exported from PyTorch to ONNX (opset 9) | Takes features of one (typed, candidate) pair and outputs the probability that replacing is right. Features: LM scores at three orders; length and length ratio; capital changes; the previous word's class (greeting, modal, pronoun, number, temporal word, "to be" form, -ing/-ed …); edit counts (deletions, insertions, substitutions, transpositions, case); **keyboard geometry** (key-shape distances, Hausdorff distance of the touch path); the noisy-channel probability | Learned confidence models for autocorrect (cf. Whitelaw et al. 2009, "Using the Web for language independent spellchecking and autocorrection") |
| 6 | **Replace dictionary** | 4,698 typed → replacement pairs | Hard rules applied without ranking: common typos, run-together words, brand casing, and about 85 entries that *add* an apostrophe (contractions such as "dont" → "don't") | Curated autocorrect lists |
| 7 | **Dialect map** | 4,820 rows for five locales (American, British, Canadian, Australian, Indian) | Converts a word to the user's locale spelling | Spelling-variant lists of the VarCon / SCOWL kind (Atkinson) |
| 8 | **Blocklists** | 9,247 + 1,465 MurmurHash3-32 hashes (words not shipped) | Never suggest or complete offensive words; a "contextual" list for words that are fine typed but not to be offered | Hashed denylists |
| 9 | **Phrase completions** | 102,469 prefixes forming a tree, 35,174 marked complete | Suggests the rest of a sentence as you type ("smart compose") | Count-ranked phrase tries mined from user text |

## 2. How it was built (reconstructed)

1. **Corpus.** Hundreds of billions of tokens of everyday typed text: the
   unigram total is 4.9 × 10¹¹ and the vocabulary's tail is social-media and
   messaging words.
2. **Counting.** n-grams up to order 5 counted, pruned at a count of 5,000,
   quantised and packed into a fingerprinted perfect hash so the model fits
   on a phone.
3. **Error model.** Trained on (typed, intended) pairs, most likely logged
   corrections, as context-dependent edit probabilities, then quantised.
4. **Ranker.** A small MLP trained on candidate pairs labelled
   accepted/rejected, combining LM, error-model, edit and touch-geometry
   features; exported to ONNX for the device.
5. **Hand-curated layers** on top: the replace dictionary, the dialect maps,
   the blocklists, and the phrase list.

## 3. Who it was built for

Everything points to **email and messaging on a phone**:

- the phrase completions are workplace email ("thanks for the note",
  scheduling, invoices, prices); a search of all 102,469 for research
  language found 0 with "hypothesis", "In this study", "statistically
  significant" or "confidence interval";
- the replace dictionary corrects business and student email typing
  (invoice, customer, semester, assignment) and supplies contractions;
- the vocabulary knows "venmo" and "Insta" but not "seroprevalence",
  "SEIR", "compartmental", "estimand", "transmissibility" or
  "nonpharmaceutical";
- the ranker's strongest signals are touch geometry and the previous word's
  social class (greetings, pronouns), which mean nothing in a manuscript.

## 4. Why it is not used directly

- **Provenance.** No licence came with it; its form (decoded tables,
  "probed" n-grams, an ONNX graph rewritten as JSON) shows it was taken out
  of an app. Shipping it, training on it, or copying its tables would
  reproduce someone else's product.
- **Fit.** Its defaults contradict academic conventions (§5).
- **Principle.** Phrase completion drafts text for the author (CLAUDE.md #1).
  The owner has asked to *test* prediction as an experiment (2026-10-14); it
  is built from open data, off by default and outside the shipped surfaces.

One private diagnostic was run on 2026-10-14, in a scratch folder: its typo
list against Researchly's S001. S001 flagged 93% of 4,460 single-word typos
and its first suggestion was right for 90% of those; the 301 it accepted
("occured", "begining", "commited") exposed a real bug in S001's suffix
fallback. That bug is fixed using Researchly's own tests, not the list.

## 5. Where an email keyboard is wrong for a manuscript

| Keyboard behaviour | Academic convention | Researchly |
|---|---|---|
| Applies corrections silently | The author decides; publishers' AI policies | Suggests; never applies unread (`fix_safety`) |
| Adds contractions ("dont" → "don't") | Contractions are avoided in formal prose | "dont" → "do not"; contractions flagged as a Convention |
| One locale for the whole user | One spelling *per document*, chosen by venue | Follows the document's own majority; mixing flagged (W210) |
| General vocabulary | Field terms, gene and drug names, Latin abbreviations, units | Scientific lexicon, document-learned terms, masking |
| Treats every token as prose | LaTeX, maths, citations, code are not words | Masked before checking |
| Same advice everywhere | Methods ≠ Discussion | Section-aware rules |
| Ranks by typing geometry | Typing slips matter less than spelling knowledge (doubling, -ence/-ance, ie/ei) | Error model of spelling-knowledge edits |

## References

- Belazzougui, Botelho & Dietzfelbinger (2009). Hash, displace, and compress. *ESA*.
- Brants, Popat, Xu, Och & Dean (2007). Large language models in machine translation. *EMNLP-CoNLL*.
- Brill & Moore (2000). An improved error model for noisy channel spelling correction. *ACL*.
- Guthrie & Hepple (2010). Storing the web in memory: space efficient language models with constant time retrieval. *EMNLP*.
- Kernighan, Church & Gale (1990). A spelling correction program based on a noisy channel model. *COLING*.
- Norvig (2007). How to write a spelling corrector. norvig.com/spell-correct.html.
- Pauls & Klein (2011). Faster and smaller n-gram language models. *ACL*.
- Talbot & Brants (2008). Randomized language models via perfect hash functions. *ACL*.
- Whitelaw, Hutchinson, Chung & Ellis (2009). Using the Web for language independent spellchecking and autocorrection. *EMNLP*.
