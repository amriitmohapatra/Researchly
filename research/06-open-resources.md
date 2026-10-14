# Open-source resources for a licence-clean autocorrect engine and an academic writing checker

Research report for Researchly. Date: 2026-10-14. Nothing was written to the repository.

## 0. Method, and how far to trust each licence

- **Verified** means I opened the LICENSE file, licence page or package metadata myself on 2026-10-14. The evidence URL is given in each row.
- **Unverified** means I could not see the licence, or saw it only in a secondary source. The secondary source is named where there is one.
- **Last activity** is the date of the newest commit on the default branch. I got it from a shallow `git clone` (github.com HTML and api.github.com were blocked; git and raw.githubusercontent.com worked). PyPI JSON, Hugging Face's API and sources.debian.org also worked.
- **Blocked** during this audit: wortschatz.uni-leipzig.de and llds.phon.ox.ac.uk (both behind Anubis bot walls), presage.sourceforge.io and sourceforge.net (403). Hugging Face worked, which it did not during the S0 audit.
- **Fit codes**, following Researchly's rules (CLAUDE.md non-negotiable 1 and `ml/datasets.yaml`):
  - **SHIP**: a permissive licence (MIT/BSD/Apache/ISC-like, CC0, CC BY, ODC-BY with attribution). It may go inside the engine.
  - **SIDECAR**: GPL/LGPL/MPL. Run it as a separate process on the server, or use it only as a build-time tool.
  - **EVAL**: CC BY-SA, non-commercial, no licence, or unknown. Allowed for `private_eval`/`ci_eval`, and at most `train_experimental`.
  - **EXCLUDED**: generative models, which non-negotiable 1 forbids in the engine.

## 1. Findings that change existing assumptions

1. **The SymSpell bigram dictionary has no documented provenance, and it already ships.** The symspellpy 6.10.0 wheel bundles both `frequency_dictionary_en_82_765.txt` (1.33 MB) and `frequency_bigramdictionary_en_243_342.txt` (5.14 MB, 242,342 lines). I checked by listing the wheel.
   - SymSpell's README documents only the unigram file: Google Books Ngram (CC BY 3.0) intersected with SCOWL (README lines 269–273).
   - For the bigram file the README says only "English bigram frequency dictionary included" (v6.5 changelog).
   - Its counts are on the Google Books scale ("of the" = 177,045,273,024), so Google Books 2-grams are the likely source. That is my inference; nothing documents it.
   - The registry entry `symspell-frequency-dictionary` covers only the unigram file. Researchly's `spelling.py` loads only the unigram file today.
2. **SCOWL has been renamed ESDB** (English Speller Database, previously SCOWLv2), at `en-wl/wordlist`.
   - Licence: MIT-like. It now also absorbs the VarCon variant data.
   - Its variant levels include `x`, meaning "outright misspellings that are only included for completeness". That gives a typo→correction source under a permissive licence (§4.5).
   - Three extra notices apply in some cases: Australian data (Titze), any list larger than size 80 (UKACD), and full-database redistribution (WordNet).
3. **Every widely used typo→correction list has Wikipedia (CC BY-SA) ancestry:**
   - **codespell**: its dictionaries are CC BY-SA 3.0 (README line 449).
   - **client9/misspell**: its README says its list "started with a word list from Wikipedia".
   - **crate-ci/typos `words.csv`**: the 2019 initial commit (`0cdd64c03`) generated it from misspell's `words.go` (`DictMain` + `DictAmerican`). Even though the crate is MIT OR Apache-2.0, its data has CC BY-SA ancestry.
   - **Conclusion**: for a replace dictionary Researchly can ship, build its own (§4.5). Use these lists only for evaluation.
4. **The GitHub Typo Corpus has no licence.** Its terms say each commit follows its source repository's licence, and the authors collected it under GitHub's Acceptable Use Policy. The official S3 download returned **404** on 2026-10-14.
5. **The scispaCy models are CC BY-SA 3.0**, even though the scispaCy code is Apache-2.0. Source: `meta.json` of `en_core_sci_sm-0.5.4` (sources: OntoNotes 5, Common Crawl, GENIA 1.0). Their vocabulary (about 100k words in the sm model) cannot ship.
6. **wordfreq is frozen and its data is CC BY-SA 4.0.** The code is Apache-2.0. The README points to SUNSET.md, and its data sources include Wikipedia, OpenSubtitles and SUBTLEX. Use it for evaluation only.
7. **Harper (Automattic, Apache-2.0) already has the five dialects in the brief.** Its `Dialect` enum is American, Canadian, Australian, British and Indian, and it has `try_guess_from_document` (`harper-core/src/dict_word_metadata.rs` line 1129). It is the closest open peer to "consistent spelling within a document". Its 54,900-entry `dictionary.dict` does not document where its "original dictionary import" came from. One inline comment mentions a word "probably imported from Wiktionary".
8. **spylls has a licence mismatch.** The repository LICENSE is MPL-2.0, while the PyPI classifier says MIT.
9. **The FUTO keyboard is not open source.** Its licence is the "FUTO Source First License 1.1-kb", which allows modification only for non-commercial purposes. Do not reuse its code.
10. **The Aalto 136M Keystrokes dataset**, the best real typing-slip data, is "free to use for research and non-commercial use with attribution". That allows `train_experimental` and evaluation only, never `ship_model`.
11. **Google Books Ngram v3 (20200217) is CC BY 3.0** and has separate `eng-gb` and `eng-us` subcorpora for 1- to 5-grams. That gives frequency data for each dialect.

## 2. Spelling-correction engines and libraries

| Candidate | URL | What it provides | Size | Language | Last activity | Licence (evidence) | Fit |
|---|---|---|---|---|---|---|---|
| SymSpell | github.com/wolfgarbe/SymSpell | Symmetric-delete candidate generation, compound and word segmentation, unigram + bigram dictionaries | 82,765 unigrams; 242,342 bigrams | C# | 2026-07-04 | MIT (raw.githubusercontent.com/wolfgarbe/SymSpell/master/LICENSE). Unigram data: Google Books Ngram CC BY 3.0 ∩ SCOWL (README l.269–273). **Bigram data: provenance not documented** | SHIP for code and unigram data. Register the bigram file as "provenance unverified" or replace it (§4.1) |
| symspellpy | github.com/mammothb/symspellpy | Python port, already the S001 base | wheel ships both dictionaries (5.1 + 1.3 MB) | Python ≥3.10 | 2026-08-22 | MIT (repo LICENSE; PyPI JSON 6.10.0 "MIT License") | SHIP. Already in use |
| JamSpell | github.com/bakwc/JamSpell | Trigram-LM context spell checker | en model 35 MB | C++ with Python bindings via SWIG | 2024-08-29 | Code MIT (repo LICENSE). Models in `bakwc/JamSpell-models`: no licence file found; trained on Leipzig corpora (licence unverified, site blocked). PyPI 0.0.12 is old | Code: SHIP. Models: EVAL. The "Pro" ranker is commercial |
| Hunspell | github.com/hunspell/hunspell | Affix-based spell checker; LibreOffice/Firefox standard | — | C++ | 2026-10-11 | LGPL/GPL/MPL tri-licence (README line 4) | SIDECAR, or reach it through the MPL route. Wrappers: cyhunspell (MIT + tri-licence, PyPI), pyenchant (LGPL) |
| nuspell | github.com/nuspell/nuspell | Modern Hunspell-compatible engine | — | C++ | 2026-09-11 | LGPL-3.0-or-later (README) | SIDECAR |
| spylls | github.com/zverok/spylls | Pure-Python Hunspell port (readable algorithm) | — | Python | 2024-01-27 | **Repo LICENSE MPL-2.0; PyPI classifier says MIT**. Conflict unresolved | SIDECAR/EVAL until resolved |
| LibreOffice en dictionaries | github.com/LibreOffice/dictionaries/tree/master/en | en_US/CA/AU (SCOWL size 60), en_GB (Marco Pinto), en_ZA | en_GB.dic 1.23 MB; en_US.dic 552 KB | Hunspell | 2026-10-12 | en_US/CA/AU from SCOWL, so ESDB/SCOWL MIT-like (README_en_US.txt). **en_GB is LGPL** ("covered by his original LGPL licence"; README_en_GB.txt l.1–4) | en_US/CA/AU: SHIP (prefer generating them from ESDB). en_GB: SIDECAR |
| wooorm/dictionaries | github.com/wooorm/dictionaries | npm-packaged Hunspell dictionaries | — | JS | 2024-09-09 | MIT for the packaging (repo license). Each dictionary keeps its own licence (not checked one by one) | Reference only |
| Norvig spell corrector | norvig.com/spell-correct.html; code at github.com/norvig/pytudes | Didactic noisy-channel corrector; `big.txt` | big.txt 6.5 MB (about 1M words) | Python | 2026-10-05 | Code MIT (pytudes LICENSE). big.txt mixes Gutenberg with Wiktionary and BNC frequency lists; no data licence stated | Code: SHIP (ideas). big.txt: EVAL |
| NeuSpell | github.com/neuspell/neuspell | Neural spelling toolkit (SC-LSTM, BERT); synthetic-noise generators; BEA-60K test set | models hundreds of MB | Python/PyTorch | 2021-04-27 (stale) | Code MIT (LICENSE; PyPI MIT). Models and data licences unverified; BEA-60K derives from BEA-2019 (NC) | EVAL. Non-generative but heavy; useful for its noising functions and benchmarks |
| contextualSpellCheck | github.com/R1j1t/contextualSpellCheck | spaCy pipe: BERT masked-LM picks among out-of-vocabulary candidates | — | Python | 2024-12-05 (repo says "not actively maintained") | MIT (LICENSE) | EVAL. Masked-LM candidate choice is non-generative in principle, but BERT is heavy and its OOV handling of technical terms is poor |
| pyspellchecker | github.com/barrust/pyspellchecker | Norvig-style corrector with frequency lists | — | Python ≥3.10 | 2026-10-10 | Code MIT (LICENSE; PyPI). Frequency data built from OpenSubtitles 2018 (README "Dictionary Creation"); data licence unverified | Code: SHIP. Data: EVAL |
| Harper | github.com/Automattic/harper | Rust grammar and spell checker: 5 dialects, dialect guessing, 379 `.weir` phrase rules, LSP, WASM | dictionary 54,900 entries | Rust | 2026-10-13 | Apache-2.0 (LICENSE). Dictionary provenance undocumented | SHIP as code/peer; can run as a sidecar (harper-ls/CLI). `harper-py` (PyPI, Apache-2.0) is a third-party binding first released 2026-10-11: too new to rely on |
| textblob `correct()` | PyPI textblob | Norvig-style corrector | — | Python | — | MIT (PyPI) | Not better than symspellpy |
| autocorrect | PyPI autocorrect | Word-frequency corrector | — | Python | — | LGPL-3 (PyPI) | SIDECAR; no reason to use |
| nspell | github.com/wooorm/nspell | JS Hunspell-like | — | JS | — | MIT | n/a (JS) |

## 3. Misspelling and typo corpora (error-model training and evaluation)

| Corpus | URL / download | Contents and format | Size | Licence (evidence) | Fit |
|---|---|---|---|---|---|
| Birkbeck (Mitton) | dcs.bbk.ac.uk/~ROGER/corpora.html → `missp.dat` | `$correct` followed by its misspellings, one per line. Mostly handwritten errors by schoolchildren, students and adult-literacy learners | 36,133 misspellings of 6,136 words; 369 KB | **No licence on Mitton's page** (no rights text). The original is at the Oxford Text Archive (ota:0643); its record was behind a bot wall, so unverified | EVAL. Poor match for PhD typing slips (these are cognitive misspellings) |
| Holbrook | same page → `holbrook-missp.dat`, `holbrook-tagged.dat` | Tagged school passages (`<ERR targ=…>`); pairs with frequencies | 1,791 misspellings of 1,200 words; 24.6 KB | No licence; text from a CUP 1964 book used with permission granted to Mitton | EVAL |
| Aspell test set | same page → `aspell.dat` (from aspell.net/test/batch0.tab) | Atkinson's Aspell benchmark | 531 misspellings of 450 words; 9.3 KB | No licence stated | EVAL (standard benchmark) |
| Wikipedia (Mitton's version) | same page → `wikipedia.dat` | Editors' misspellings | 2,455 misspellings of 1,922 words; 43.8 KB | Derived from Wikipedia, so CC BY-SA | EVAL |
| Wikipedia "Lists of common misspellings/For machines" | en.wikipedia.org/wiki/Wikipedia:Lists_of_common_misspellings/For_machines | `typo->correction` | 4,310 entries (raw wikitext counted) | **CC BY-SA 4.0** (page footer, verified). The page itself says it is out of date | EVAL |
| GitHub Typo Corpus (Hagiwara & Mita 2020) | github.com/mhagiwara/github-typo-corpus | JSONL of commits with src/tgt edits, `prob_typo`, `is_typo`; more than 15 languages | 350k+ edits, 65M characters | **No licence**. README "Terms": per-repository licences, collected under GitHub's AUP. **Download URL returns 404 (2026-10-14)**. Last commit 2019-12-11 | EVAL only (if a copy can be found). Closest real-world match for typing slips in technical prose |
| crate-ci/typos `words.csv` | github.com/crate-ci/typos/tree/master/crates/typos-dict/assets | typo,correction CSV, curated against false positives | 95,948 rows; 2.07 MB | Crate MIT OR Apache-2.0 (LICENSE-MIT, Cargo.toml). **Seeded from client9/misspell** (initial commit 0cdd64c03, 2019-01-22, `assets/main.go` prints `DictMain`/`DictAmerican`), which itself began from the Wikipedia list. The repo also vendors `codespell-dict` (CC BY-SA 3.0), `wikipedia-dict` (CC BY-SA), `misspell-dict` and `varcon` | EVAL, or ship only after an owner decision on ancestry. Very good false-positive discipline, but code-oriented |
| codespell dictionaries | github.com/codespell-project/codespell | `typo->fix[, fix]` lists, including `dictionary_en-GB_to_en-US.txt` and others | dictionary.txt 1.49 MB | Code GPL-2.0-only (COPYING; PyPI). **Dictionaries CC BY-SA 3.0** (README l.449). Active (2026-10-13) | EVAL |
| client9/misspell | github.com/client9/misspell | Go list plus a US/UK locale mode | about 600 KB CSV | Code MIT (LICENSE). Word list from Wikipedia (heavily edited), tysto.com and oxforddictionaries.com, plus a SCOWL diff (README "Where do the word lists come from?"). **Archived**; last commit 2018-03-08 | EVAL |
| Norvig spell-testset1/2 | norvig.com/spell-testset1.txt, spell-testset2.txt | `right: wrong1 wrong2` | 270 / 400 cases | No licence; extracted from Birkbeck (spell-correct.html) | EVAL (classic baseline) |
| Aalto 136M Keystrokes (Dhakal et al., CHI 2018) | userinterfaces.aalto.fi/136Mkeystrokes/ → `data/Keystrokes.zip` | Keystroke-level transcription logs from 168,000 participants: real typing slips with timing | 1.57 GB zip (16 GB unzipped) | "**free to use for research and non-commercial use with attribution**" (project page, verified) | `train_experimental` / EVAL. Best data for the typing-slip channel model, but no `ship_model` |
| NeuSpell BEA-60K, JFLEG-spell and others | via neuspell README | Sentence pairs | — | Inherit BEA-2019/JFLEG NC terms (JFLEG is already registered as CC BY-NC-SA) | EVAL |
| HF `sarp3d0n/wiki-typos` | huggingface.co | Wiki typos | — | Tagged Apache-2.0 but derived from Wikipedia: **licence laundering risk** | Avoid |

## 4. Dialect variant lists

| Resource | URL | What | Size | Licence (evidence) | Fit |
|---|---|---|---|---|---|
| **ESDB (formerly SCOWL/SCOWLv2)** | github.com/en-wl/wordlist | One `scowl.txt` plus an SQLite database. Size levels 35–95; spelling codes A (US), B (GB -ise), Z (GB -ize/Oxford), C (CA), D (AU); variant levels from 0 (`.`) to `x` (misspelling); POS and inflections; `words_w_variant_info` view for US↔GB translation that keeps POS | built locally with `make` | **MIT-like** permission notice by Kevin Atkinson (raw.githubusercontent.com/en-wl/wordlist/HEAD/Copyright). Extra notices: AU data (Titze 2016, MIT-like), lists larger than size 80 (UKACD: keep notice verbatim), WordNet for full-DB redistribution. COCA 3-gram data was used under NDA, but the grant covers derived lists. Last commit 2026-06-24 | **SHIP** (keep notices). The backbone for vocabulary and dialect |
| VarCon 2020.12.07 | wordlist.aspell.net; copy in crate-ci/typos `crates/varcon/assets/` | `A: color / B: colour` lines grouped by sense | varcon.txt 846 KB (16,909 `A:` lines) | MIT-like (Atkinson; Titze) plus Ispell BSD-style notice (Kuenning); copyright section of the vendored README, verified | **SHIP** (now inside ESDB) |
| typos-vars / varcon crate | crates `typos-vars`, `varcon` | Rust encoding of VarCon | — | MIT OR Apache-2.0 (code); data VarCon | Reference |
| breame | github.com/cdpierse/breame | Python US↔GB spelling, meanings, terminology | at least 1,730 GB and 1,706 US spellings | Apache-2.0 (LICENSE; PyPI). **Data sources not stated in README.** Last commit 2021-10-04 | EVAL (provenance unknown; ESDB is larger and documented) |
| Harper dialect data | Automattic/harper `dictionary.dict` + `DialectFlags` | US/CA/AU/GB/**IN** flags for each word; document dialect guess | 54,900 entries | Apache-2.0; upstream import undocumented | Peer/benchmark; the only open source found with an Indian English flag |
| LanguageTool en-GB/US/CA/AU/NZ/ZA spellers | languagetool-org/languagetool | Morfologik dictionaries + `spelling_en-GB.txt` etc. | — | LGPL-2.1+ | SIDECAR (already used) |
| SPECIALIST Lexicon (NLM) | lhncbc.nlm.nih.gov/LSG/Projects/lexicon/current/web/release/ | Biomedical lexicon (2026 release), with lexical records incl. spelling variants such as ae/e and oe/e families | about 1M records (approx.; not counted) | "open source and freely available, subject to … terms": redistribution allowed with conditions included, attribution with release number, modifications stated, no endorsement (termsAndConditions.html, verified) | **SHIP** with notice. Fills VarCon's biomedical gaps (anaemia/anemia, oesophagus/esophagus, paediatric/pediatric). I did not check whether it labels dialect; it may only mark the pairs as variants |

**Indian English**: no open dialect list was found except Harper's flag. Indian academic English follows British spelling in most style guides, so an "en-IN" profile can be en-GB plus an allow-list. That is a policy choice for the owner, not data.

## 5. N-gram and word-frequency resources

| Resource | URL | What | Size | Licence (evidence) | Fit |
|---|---|---|---|---|---|
| **Google Books Ngram v3 (20200217)** | storage.googleapis.com/books/ngrams/books/datasetsv3.html | 1–5-grams with yearly counts; subcorpora `eng`, `eng-us`, `eng-gb`, `eng-fiction` | English 5-grams in 19,435 shards (TB scale) | "**This compilation is licensed under a Creative Commons Attribution 3.0 Unported License**" (page, verified) | **SHIP** derived counts with attribution. Domain: books, not papers |
| LanguageTool n-gram data | languagetool.org/download/ngram-data/ | Lucene index of Google n-grams (1–3) used by LT's confusion rules | `ngrams-en-20150817.zip` 8.96 GB | No licence statement in the directory; LT's dev page says it uses the Google Books data, so presumably CC BY 3.0 (unverified as a derivative) | SIDECAR use with LT; do not redistribute |
| wordfreq | github.com/rspeer/wordfreq | Zipf frequencies, multi-source | small/large lists | Code Apache-2.0 (LICENSE.txt). **Data CC BY-SA 4.0** (README §License; SUBTLEX terms). **Sunset**: frozen. Last commit 2025-01-04 | EVAL |
| hermitdave/FrequencyWords | github.com/hermitdave/FrequencyWords | OpenSubtitles 2016/2018 frequency lists | en_50k etc. | Code MIT; **content CC-BY-SA-4.0** (README) | EVAL |
| SUBTLEX-US/UK | Brysbaert et al. | Subtitle frequencies | — | Terms "similar to CC BY-SA" as quoted in wordfreq's README. Original site not checked, so unverified first-hand | EVAL |
| COCA / Google Web 1T 5-gram | english-corpora.org; LDC | Large frequency and 5-gram data | — | Not open (purchased or LDC licence; ESDB Copyright confirms COCA is "not freely available") | Not usable |
| **PMC OA commercial-use subset / Europe PMC OA** | registry id `pmc-oa-commercial-subset` | Full-text biomedical papers, section-tagged | millions of articles | Per article; restrict to CC0/CC BY (already in the registry) | **SHIP** derived counts, n-grams and section statistics with attribution. The best source for a scientific LM |
| peS2o v2 | huggingface.co/datasets/allenai/peS2o | Cleaned S2ORC full text plus S2AG abstracts | 38.97M documents, 42.01B tokens | **ODC-BY** (HF card, verified); code repo Apache-2.0 | `train_experimental`. ODC-BY covers the compilation; the papers inside keep their own copyright (S2AG abstracts include publisher abstracts), so prefer PMC OA CC BY for anything shipped |
| CORD-19 | github.com/allenai/cord19 | COVID papers | — | Custom "COVID DATASET LICENSE AGREEMENT" (LICENSE) | EVAL |
| scispaCy vocab and models | github.com/allenai/scispacy | Biomedical spaCy models (sm vocab about 100k) | sm 14.8 MB | Code Apache-2.0; **models CC BY-SA 3.0** (meta.json of en_core_sci_sm 0.5.4) | EVAL (or SIDECAR for parsing only) |
| hunspell-en-med-glut | github.com/glutanimate/hunspell-en-med-glut | Medical Hunspell word list (OpenMedSpel + MTH-Med-Spel-Chek) | — | **GPL-3.0** (LICENSE; README). Last commit 2017-01-04 | SIDECAR/EVAL. Use SPECIALIST instead |
| MeSH | nlm.nih.gov | Controlled vocabulary of headings and entry terms | about 30k descriptors | NLM terms: free; acknowledge NLM, no endorsement, state the version (terms_and_conditions_mesh.html, verified) | **SHIP** as an allow-list with attribution |
| KenLM | github.com/kpu/kenlm | Build and query ARPA/binary n-gram LMs | — | **LGPL-2.1-or-later** for most code (LICENSE). Last commit 2025-03-30. PyPI `kenlm` 0.3.0 | Build-time tool (models you build are not LGPL-encumbered; they carry the corpus licence). Query in the engine with own code, or run kenlm in a sidecar |
| NLTK `lm` | nltk/nltk | Pure-Python MLE/KN n-gram models | — | Apache-2.0 (LICENSE.txt; PyPI) | SHIP (slow; fine for experiments) |

## 6. Grammar, style and academic checkers

| Tool | URL | Approach | Language | Last activity | Licence (evidence) | Fit |
|---|---|---|---|---|---|---|
| LanguageTool | languagetool-org/languagetool | Rules + n-gram confusion (`confusion_sets.txt` 871 lines; `confusion_sets_extended.txt` 11,848 lines) | Java | 2026-10-13 | LGPL-2.1+ (already registered). Python client GPL-3.0-only | SIDECAR (current LT001 tier) |
| Harper | Automattic/harper | Fast rules (379 Weir phrase rules) + spelling + dialects | Rust/WASM | 2026-10-13 | Apache-2.0 | Peer; possible second sidecar. Weir rules are a good source of minimal, precise phrase fixes |
| Vale | github.com/vale-cli/vale (errata-ai/vale) | YAML rule framework (existence, substitution, consistency, conditional…) | Go | 2026-10-03 | MIT (LICENSE; PyPI `vale` 3.22.0.0 MIT) | SHIP-able binary; the rule *format* suits Researchly's lexicons |
| Vale styles: write-good, proselint, Microsoft, Google, Readability | github.com/errata-ai/* | Style packages | YAML | write-good 2025-05-23 | write-good MIT; proselint style BSD-3; Microsoft/Google/Readability MIT (LICENSE files) | Reference. **write-good's weasel list flags hedges that science needs** |
| testthedocs/vale-styles | github.com/testthedocs/vale-styles | Community styles | YAML | 2020-02-02 (stale) | MIT | Reference |
| **Academic Vale style** | — | — | — | — | **None found** (GitHub and web search) | A gap Researchly can fill |
| proselint | github.com/amperser/proselint | Curated usage rules | Python | 2026-06-22 | BSD-3-style (LICENSE.md; PyPI "BSD License") | SHIP-able; mine for ideas (each rule cites a usage authority) |
| write-good | github.com/btford/write-good | Passive, weasel, adverbs, clichés | JS | 2025-03-10 | MIT | Reference (low precision in Methods sections) |
| alex | github.com/get-alex/alex | Insensitive-language checker | JS | 2024-11-27 | MIT | Low relevance |
| textlint | github.com/textlint/textlint | Pluggable linter (mostly Japanese technical-writing presets) | JS | 2026-10-13 | MIT | Reference. No English academic preset found |
| retext | github.com/retextjs/retext | NLP plugin ecosystem (spell, passive, readability) | JS | 2025-02-04 | MIT | Reference |
| GECToR (Grammarly) | github.com/grammarly/gector | Token-level edit tagging (BERT/RoBERTa/XLNet) | Python | 2022-10-13 | Code Apache-2.0 (LICENSE). **Weights on Grammarly S3: no licence stated**; trained on BEA-2019 data (NC) | Permitted by non-negotiable 1 as `tier="gec"`. Weights: EVAL only; retrain on licence-clean data to ship |
| gector (gotutiyan re-implementation) | github.com/gotutiyan/gector; PyPI `gector` 1.2.0 | Modern HF-based GECToR | Python ≥3.11 (**incompatible with the 3.10 rule**) | — | Code MIT (LICENSE). HF model cards carry no licence tag | EVAL |
| ERRANT | github.com/chrisjbryant/errant | Edit extraction and classification for GEC evaluation | Python | 2026-05-28 | MIT (LICENSE.md; PyPI) | **SHIP/CI**: the evaluation scorer for the gec tier |
| After the Deadline | github.com/Automattic/atd-server(-next) | Old statistical grammar/style server | Java/Sleep | 2017-08-26 | GPL-2.0 (LICENSE.txt) | Historical; skip |
| Gramformer | github.com/PrithivirajDamodaran/Gramformer | Seq2seq GEC | Python | 2022-12-27 | Code MIT; HF model `prithivida/grammar_error_correcter_v1` has no licence tag | **EXCLUDED** (generative) |
| CoEdIT | huggingface.co/grammarly/coedit-large | Instruction-tuned T5 editor | — | 2024-04-28 | **CC BY-NC 4.0** (HF card) | **EXCLUDED** (generative and NC); offline experiment only |
| vennify/t5-base-grammar-correction | HF | T5 GEC | — | — | CC BY-NC-SA 4.0 (HF API) | EXCLUDED |
| TeXtidote | github.com/sylvainhalle/textidote | LaTeX-aware LT wrapper with source-position mapping | Java | 2026-09-09 | GPL-3.0 (LICENSE) | SIDECAR/reference for LaTeX masking |
| LTeX+ (ltex-ls-plus) | github.com/ltex-plus/ltex-ls-plus | LT language server for LaTeX/Markdown/Quarto | Kotlin | 2026-10-09 | MPL-2.0 (LICENSE.md) | Reference; the closest competitor in the owner's editors |
| ChkTeX | savannah.nongnu.org/projects/chktex | LaTeX typography lint (spacing, dashes, `\ldots`) | C | 1.7.10 (Debian 1.7.10-1) | GPL-2.0-or-later (Debian `debian/copyright`) | SIDECAR/reference for LaTeX typography rules |
| arxiv-latex-cleaner | github.com/google-research/arxiv-latex-cleaner | Strips comments and unused files | Python | — | Apache-2.0 | Utility only |
| devd/Academic-Writing-Check | github.com/devd/Academic-Writing-Check | Perl scripts: weasel words, passive, duplicates, "i.e."/"et al." | Perl | — | **No licence file found** | Ideas only |
| Academic Word List (Coxhead 2000) | wgtn.ac.nz/lals/resources/academicwordlist | 570 word families in 10 sublists | — | **No licence**; page shows only "Copyright © Victoria University of Wellington" | `knowledge_derivation`/EVAL |
| New Academic Word List (Browne et al.) | newgeneralservicelist.com/new-academic-word-list | Academic list sized to complement the NGSL | — | **CC BY-SA 4.0** (page, verified) | EVAL / `knowledge_derivation` |
| Academic Vocabulary List (Gardner & Davies) | academicvocabulary.info | 3,000 lemmas from COCA-academic | — | "completely free" but no licence; COCA-derived | EVAL |
| Manchester Academic Phrasebank | phrasebank.manchester.ac.uk | Phrase templates by rhetorical function | — | "**Intellectual Property of the University of Manchester. Copyright © 2023**" | Do not copy. At most cite it as further reading |
| BioScope (hedge/negation cues) | huggingface.co/datasets/bigbio/bioscope | Biomedical hedge-cue annotations (CoNLL-2010 base) | — | CC BY 2.0 per the BigBio card (secondary; the Szeged original was not checked) | Candidate for a learned hedge detector after the licence is verified first-hand |
| pint units registry | github.com/hgrecco/pint `default_en.txt` | Unit names, symbols and prefixes | 946 lines | BSD-3-style (LICENSE; PyPI "BSD") | **SHIP**: authoritative unit-symbol list for unit-formatting rules |

## 7. Next-word prediction and phrase completion (for the experiment)

| Candidate | URL | Approach | Last activity | Licence (evidence) | Fit |
|---|---|---|---|---|---|
| **pressagio** | github.com/cidles/pressagio | Pure-Python port of Presage: n-gram predictor + SQLite n-gram DB + recency predictor | 2019-11-18 (stale) | **Apache-2.0** (LICENSE; README; PyPI 0.1.6) | **SHIP-able harness** for the experiment; feed it Researchly-built n-grams |
| Presage | presage.sourceforge.io | C++ predictive-text framework (ARPA/n-gram, smoothing, user-adaptive) | 0.9.1 (Debian 0.9.1-3) | **GPL-2.0-or-later** (sources.debian.org presage 0.9.1-3 `debian/copyright`) | SIDECAR/comparison only |
| KenLM | kpu/kenlm | Fast n-gram query; build 5-gram ARPA | 2025-03-30 | LGPL-2.1+ | Build tool / sidecar (see §5) |
| AnySoftKeyboard | github.com/AnySoftKeyboard/AnySoftKeyboard (+ LanguagePack) | Android keyboard: dictionaries, next-word | 2026-10-09 | Apache-2.0 (LICENSE files) | Reference implementation (permissive) |
| FlorisBoard | github.com/florisboard/florisboard | Android keyboard | 2026-09-30 | Apache-2.0 | Reference (state of its prediction feature not checked) |
| HeliBoard + AOSP dictionaries | github.com/Helium314/HeliBoard; codeberg.org/Helium314/aosp-dictionaries | AOSP LatinIME engine; `.combined` word lists with bigram data | 2026-10-12 | HeliBoard GPL-3.0. Legacy en_US/en_GB lists come from openboard (licence not stated in the `.source` file). "Experimental" en lists are built from Leipzig, "source lists under CC BY 4.0" (secondary; Leipzig blocked) | Reference / EVAL |
| FUTO Keyboard | github.com/futo-org/android-keyboard | Transformer + dictionary autocorrect | 2026-09-23 | **FUTO Source First 1.1-kb** (non-commercial modification only) | Do not use |

**Experiment design (non-generative, local):** predict at most three completions of 1–3 words from n-gram counts (stupid backoff over a 5-gram SQLite table). Rank them by count × section prior, never auto-insert, and show them as optional chips. Build the n-grams from the CC BY/CC0 PMC-OA subset, split by IMRaD section, so "In this study, we" completions differ between Methods and Discussion. Whether a frequency-ranked phrase completion counts as "drafting sentences for the author" (non-negotiable 1) is a line the **owner must draw**. I suggest keeping it as an off-by-default experiment, limited to multi-word *terms and collocations* ("confidence interval", "basic reproduction number"), not clause templates.

## 8. Rebuilding the keyboard engine's capabilities from licence-clean data

| Capability | Licence-clean build | Evaluation-only aids |
|---|---|---|
| Vocabulary with frequencies | ESDB size ≤ 70 (MIT-like), optionally size 80 with the UKACD notice. Weight with Google Ngram v3 1-gram counts (CC BY 3.0, 2000–2019 slice) **from `eng-gb` and `eng-us` separately**. Add a scientific layer: counts from PMC-OA CC BY/CC0, SPECIALIST Lexicon (NLM terms), MeSH entry terms, and the project's `scientific_terms.txt` | wordfreq, SUBTLEX, scispaCy vocab |
| 5-gram LM | Google Ngram v3 2–5-grams pruned to the ESDB vocabulary (CC BY 3.0), interpolated with a 5-gram LM built with KenLM `lmplz` from PMC-OA CC BY text (build time only). Query with Researchly's own code (SQLite stupid backoff, or a small MIT reader for ARPA) | LT n-gram index |
| Noisy-channel error model | (1) **Synthetic, self-authored generator**: keyboard adjacency for QWERTY and the macOS layout, transposition, omission, doubling, phonetic confusions (ESDB/SymSpell candidates). It is fully clean and can be tuned. (2) Fit its parameters with the owner's own accept/dismiss logs (`owner-annotations`, which permits `ship_model`) | Aalto keystrokes (fits slip rates, `train_experimental`); Birkbeck/Holbrook/aspell/Wikipedia/Norvig and GitHub Typo Corpus for held-out recall |
| Small MLP ranker | scikit-learn MLP (BSD) over features: Damerau distance, error-model log-p, unigram/bigram/5-gram LM log-p, dialect agreement with the document's detected variety, scientific-lexicon membership, case/acronym shape, inside-masked-span flag, section. Train on synthetic pairs plus owner logs; report ERRANT-style P/R | — |
| typo→correction replace dictionary | Generate from (a) ESDB variant level `x` ("outright misspellings"), (b) the synthetic generator filtered by frequency, and (c) owner logs. Keep only pairs whose typo is not a valid ESDB/SPECIALIST word (precision first) | Wikipedia For_machines, codespell, typos, misspell: as **recall checks only** |
| UK/US/CA/AU/IN dialect maps | ESDB `words_w_variant_info` (POS-aware, so program/programme stays ambiguous). It can replace the 37 hand-curated `CONSISTENCY_PAIRS` in `lexicons.py` while keeping their don't-fire guards. Add SPECIALIST spelling variants for biomedical ae/oe/ph families. IN = GB profile plus allow-list (owner decision) | Harper's dialect flags to cross-check; breame |
| Phrase completion / next word | §7 | Presage |

## 9. Where open tools fall short for academic writing (gaps Researchly can exploit)

1. **Technical vocabulary precision.**
   - Generic dictionaries (SCOWL size 60, en_GB Hunspell, SymSpell's 82k list) flag estimands, gene and protein names, Stan/R identifiers and Latin binomials.
   - SymSpell's `lookup_compound` splits or "corrects" them.
   - scispaCy's vocabulary would help but cannot ship (CC BY-SA). SPECIALIST + MeSH + PMC-OA counts are the clean route.
   - No open tool sets its correction threshold by *section* or by an in-document frequency signal (a term used five times in the same thesis is probably right).
2. **Dialect consistency rather than dialect enforcement.**
   - Hunspell and LT check against one locale, and misspell is "neutral"; Harper guesses the dominant dialect.
   - None distinguishes Oxford -ize British (ESDB code Z) from -ise British. None treats biomedical exceptions properly: "fetus" is standard in UK medical journals, and "programme"/"program" depends on sense.
   - None reports "you used *modelling* 14× and *modeling* 2×" with a one-click fix towards the majority. ESDB has the data for this.
3. **LaTeX/Quarto.** Only LTeX+ (MPL) and TeXtidote (GPL) map LaTeX back to source positions, and both wrap LT. ChkTeX checks typography but not prose. Researchly's offset-preserving masking plus ChkTeX-style typography rules (unbreakable spaces before `\cite`, `\ldots`, en-dashes in ranges) is a differentiated, licence-clean surface.
4. **Academic conventions that generic linters get wrong or miss:**
   - **Hedging**: write-good/proselint flag "may", "suggests", "likely" as weasel words, which is wrong for science. Researchly's hedge/booster meter is the right shape. BioScope (if its CC BY licence is confirmed) could train a small cue classifier.
   - **Contractions**: no open tool turns them off by register.
   - **Latin abbreviations**: "e.g."/"i.e." punctuation and comma, "et al." with a full stop and its italics varying by journal, "etc." after "e.g." No open rules found.
   - **Units and numbers**: space between number and unit, SI symbols vs names, "%" spacing by style guide, a dimensionless "fold" change. pint's registry (BSD) gives the symbol list. No open checker found.
   - **Section-aware rules**: passive in Methods. Nothing open is IMRaD-aware.
   - **Real-word confusions frequent in science**: affect/effect, principal/principle, complementary/complimentary, dependant/dependent, discreet/discrete, prostate/prostrate. LT has generic confusion sets; a science-weighted n-gram model would rank them better.
5. **No academic Vale style or textlint preset exists** (searched GitHub and the web). An open "Researchly-academic" Vale style generated from `lexicons.py` could also serve as a public showcase through `tools/public-export/`.
6. **Learned GEC is trained on learner English** (Lang-8, NUCLE, FCE, W&I: all NC). Nothing open is trained on edited scientific prose; AESW is CC BY-NC-SA. A GECToR-style tagger retrained on licence-clean synthetic errors in PMC-OA CC BY sentences would be novel and shippable.

## 10. Ranked recommendation (what to use, for what, how)

1. **ESDB/SCOWL + VarCon (en-wl/wordlist). SHIP.**
   - For what: vocabulary backbone, dialect maps (A/B/Z/C/D, POS-aware), and `x`-level misspellings for the replace dictionary.
   - How: build `scowl.db` at release time and export only the tables needed into `packages/core/researchly/data/`. Carry its Copyright notice. Register it as `esdb` (licence verified).
2. **Google Books Ngram v3 (CC BY 3.0). SHIP derived counts.**
   - For what: re-derive the unigram and bigram dictionaries with documented provenance, per dialect (`eng-gb`/`eng-us`), and pruned 3–5-grams for context ranking.
   - How: this replaces the undocumented SymSpell bigram file. Add attribution in `sources.py`/NOTICE.
3. **PMC-OA commercial subset, CC BY/CC0 only (already registered). SHIP derived statistics.**
   - For what: scientific unigram frequencies, a section-split 5-gram LM, collocations for the prediction experiment, and a whitelist signal for technical terms.
   - How: store per-article licence filtering in the build manifest.
4. **symspellpy (MIT). Keep** as the fast candidate generator. Load the rebuilt dictionaries from item 2. Meanwhile, register the bundled bigram file as `licence_verified: false (provenance undocumented)`.
5. **SPECIALIST Lexicon + MeSH (NLM terms). SHIP** as biomedical allow-lists and the source of ae/oe variants, with the NLM notices. This replaces the GPL medical Hunspell list and CC BY-SA scispaCy vocabularies.
6. **KenLM (LGPL) as a build-time tool only, plus a small MIT query layer in the engine.** This gives a 5-gram LM without shipping LGPL code. Optionally run kenlm in the LT sidecar container.
7. **Evaluation bundle (EVAL only, kept out of `packages/`).**
   - Contents: Mitton's four files; Norvig testsets 1/2; the Wikipedia For_machines list; codespell, typos and misspell dictionaries (recall checks); the GitHub Typo Corpus if a copy surfaces; Aalto keystrokes (`train_experimental`).
   - Use: a spelling P/R harness next to `ml/eval/`, alongside the noise-floor gate.
8. **ERRANT (MIT). CI** scorer for the S001 and gec tiers (fire/don't-fire at token level).
9. **Harper (Apache-2.0). Benchmark and idea source.**
   - Run harper-cli on the noise-floor corpus to compare flags/1000 words.
   - Adopt its dialect-guess idea and the IN profile.
   - Mine its Weir rules for precise phrase fixes. Do not import its dictionary until its provenance is known.
10. **pressagio (Apache-2.0). Harness for the prediction experiment**, fed by item 3's section-split n-grams, behind an owner decision on non-negotiable 1. Use Presage (GPL) only as an offline comparison.

Do **not** use in shipped artefacts:
- FUTO keyboard (source-first)
- CoEdIT, Gramformer, T5-GEC (generative, and NC)
- scispaCy model vocab (CC BY-SA 3.0)
- wordfreq, FrequencyWords and SUBTLEX data (CC BY-SA or similar)
- codespell, Wikipedia, misspell and typos typo lists (CC BY-SA ancestry)
- hunspell-en-med-glut (GPL-3)
- LibreOffice en_GB (LGPL)
- AWL and AVL (no licence)
- Manchester Phrasebank (UoM IP)
- JamSpell models (no licence)
- GECToR S3 weights (no licence; NC training data)

## 11. Suggested `ml/datasets.yaml` additions (for the lead to write)

Each entry needs the evidence URL above:

- `esdb-scowl`: MIT-like; verified; permitted up to `ship_text`.
- `varcon`: MIT-like + Ispell BSD notice; verified.
- `google-books-ngram-v3`: CC-BY-3.0; verified; `ship_model`, `ship_text` with attribution.
- `symspell-bigram-dictionary`: unverified provenance; keep `private_eval` until replaced.
- `specialist-lexicon`: NLM SPECIALIST terms; verified.
- `mesh`: NLM MeSH terms; verified.
- `mitton-misspelling-corpora`, `norvig-spell-testsets`, `wikipedia-misspellings-for-machines` (CC-BY-SA-4.0, verified), `codespell-dictionary` (CC-BY-SA-3.0, verified), `typos-dict` (MIT/Apache, but with Wikipedia ancestry), `github-typo-corpus` (no licence), `aalto-136m-keystrokes` (research/NC, verified): all `private_eval`/`ci_eval`, with `train_experimental` where NC permits it.
- `pes2o` (ODC-BY, verified): `train_experimental`.
- `bioscope` (CC-BY-2.0, secondary): unverified.
- `nawl` (CC-BY-SA-4.0, verified): `knowledge_derivation`.
- `awl-coxhead`, `phrasebank-manchester`: no licence; `knowledge_derivation` only, if the owner agrees.

## 12. Still unverified

- Leipzig Corpora Collection licence (site behind Anubis; the AOSP-dictionaries README says CC BY 4.0).
- Birkbeck original at the OTA (record behind a bot wall).
- GECToR S3 weights.
- Licence fields of gotutiyan's GECToR HF models (none tagged).
- JamSpell models.
- Source of the SymSpell bigram file.
- Upstream source of Harper's dictionary.
- Data sources of breame.
- spylls MPL vs MIT conflict.
- OpenSubtitles/OPUS terms behind pyspellchecker.
- BioScope at its source.
- Licences of individual wooorm dictionaries.
- Academic-Writing-Check (no licence file found).
- Whether the SPECIALIST Lexicon labels dialect on its spelling variants.
