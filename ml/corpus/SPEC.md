# S5a open-access training corpus: specification

PLAN.md S5a; ARCHITECTURE.md ADR-06 ("Open-access corpus"). Owner request
2026-10-03: a broad, licence-clean corpus so the critics learn research
writing across disciplines, not only epidemiology.

## What it is for

- **Task B (sentence roles):** structured-abstract sentences labelled by
  their heading (weak labels), to train and test a Laya sentence-role
  critic against the TF-IDF baseline (82.6%).
- **Section roles:** body paragraphs labelled by their IMRaD heading, for
  section-aware critics later.
- **Evaluation across disciplines:** held-out articles per discipline, so a
  critic's precision is reported per field, not only overall.

It is not a source of shipped text. `ship_text` is not granted: no sentence
from it appears in the engine, a Learn card or an exemplar list until an
attribution plan exists (CC BY needs attribution on every shipped sentence).

## Disciplines (10; at least 6 required)

The vocabulary of `ml/realdocs/manifest.yaml`: epidemiology,
public-health, clinical-medicine, molecular-biology, ecology-evolution,
physical-earth-sciences, engineering, computational-statistics,
social-sciences, humanities. A discipline is assigned by the query that
found the article (first match wins); `harvest.py QUERIES` lists them.

## Sources

Europe PMC's open REST API (no key): `search` for candidates,
`/{PMCID}/fullTextXML` for the JATS full text. Journals are open-access
titles of the Nature, Lancet, BMJ, PLOS, eLife, BMC, Frontiers, Royal
Society and Springer families, plus field journals for the humanities
(Synthese, History and Philosophy of the Life Sciences, Humanities & Social
Sciences Communications, BMC Medical Ethics…). Articles published
2016–2026, research articles only, most-cited first. Several queries share
a discipline's quota evenly, so one prolific journal cannot fill it.

The PubMed, bioRxiv, Scholar Gateway and Consensus connectors named in
ADR-06 are interactive tools of a Claude session, not something a script
can call, so the harvester uses Europe PMC directly (the same PMC Open
Access content, with the full text in one request).

## Licence filter at intake

Read from each article's **own** `<permissions>` block in its JATS XML (the
search engine's licence field is only a hint and is not used):

| Licence seen | `use` | `permitted_use` | Registry |
|---|---|---|---|
| CC BY (any version, or an unversioned CC BY statement) / CC0 | `train` | private_eval, ci_eval, train_experimental, ship_model | `s5a-oa-corpus-cc-by` |
| CC BY-NC, -NC-ND, -NC-SA, -ND, -SA | `eval` | private_eval, ci_eval | `s5a-oa-corpus-nc-eval` |
| no Creative Commons licence, unclear, or two different licences | dropped | — | — |

Details: PLOS's unversioned wording "distributed under the terms of the
Creative Commons Attribution License" is CC BY 4.0 by PLOS's published
policy; other unversioned statements are recorded as `CC-BY-unversioned`
(every CC BY version permits reuse with attribution). Springer Nature and
BMC add a CC0 waiver *for the data*; that clause is ignored, since the
article text is CC BY. A publisher's free-access grant (e.g. a COVID-19
resource centre) is not a reuse licence and is dropped. ShareAlike and
NoDerivatives are kept to evaluation: a model trained on them would raise
questions this project has not answered.

## Size target

**N = 1,200 licence-verified articles with `use: train`, at least 80 in each
of at least 6 disciplines, and at least 400 with a structured abstract.**
That gives several thousand labelled abstract sentences for Task B and tens
of thousands of labelled paragraphs. Growth path: `--per-discipline 500`
(about 5,000 articles) once the first fine-tune shows the data helps.

## De-duplication

By PMCID, then by DOI, then by a SHA-256 of the body's normalised words
(lower case, punctuation folded), so the same paper indexed twice, or
re-published, is counted once. Abstract-only records and bodies under
1,500 words or 5 paragraphs are dropped.

## Splits

Per article, by a stable hash of the PMCID (`common.split_of`): about 10%
`test`, 10% `dev`, 80% `train`. The split never changes as the corpus
grows, and an article's sentences all sit on one side. Results are
reported per discipline (`zero_shot.py` reports `by_group`). Training
scripts read only `train` (and `dev` for calibration); `test` is for the
held-out numbers the promotion gate reads.

## Storage

- `ml/corpus/manifest.jsonl` (committed): one row per article with ids
  (PMCID, PMID, DOI), journal, year, discipline, licence, the licence
  evidence seen and when, `use`, `permitted_use`, registry id, split,
  SHA-256 of the XML and of the normalised body, word and paragraph counts,
  the section roles present, and whether the abstract is structured. **No
  titles, abstracts, author names or any article text**
  (`common.check_manifest_row` refuses other fields).
- Full texts and weak labels: a cache **outside the repository**
  (`~/.researchly/corpus` by default, `--cache` or `$RESEARCHLY_CORPUS_CACHE`
  to move it; a path inside the repo is refused). `weak_labels.py` checks
  each cached file against the manifest's SHA-256 before using it.

## Commands

```bash
python3.10 ml/corpus/harvest.py all --per-discipline 150   # find, fetch, manifest
python3.10 ml/corpus/weak_labels.py                        # labels into the cache
python3.10 ml/corpus/harvest.py summary                    # counts from the manifest
python3.10 -m pytest ml/corpus -q                          # synthetic tests
```

## First build (2026-10-15)

See `docs/s5-laya.md` for the counts by discipline and licence.
