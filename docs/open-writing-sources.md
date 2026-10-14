# Open sources for academic-writing advice (survey, 2026-10-14)

The owner asked for more knowledge and features from online sources on
academic writing. This page lists candidate sources, what each could add,
and what its licence allows. Nothing here is used yet. Before any of it
enters the engine, its entry in `ml/datasets.yaml` must be verified
first-hand (`licence_verified: true`) and permit the intended use. The
licences below come from web searches on 2026-10-14; several are
second-hand and are marked so.

## What each source could add

| Source | What it offers | Licence (as found) | Possible use |
|---|---|---|---|
| Google Books Ngram (2012 release) | Word n-gram counts, orders 1 to 5 | CC BY 3.0 (second-hand: package pages, not Google's own) | Train a local n-gram model for context-aware spelling (real-word errors such as "form/from") and a/an and agreement checks. Ships as a derived model with attribution |
| PMC open-access articles, CC BY or CC0 (already partly in `ml/realdocs`) | Edited research prose across disciplines | Per article; CC BY and CC0 verified per item | Train the same n-gram model on academic text instead of books; the S5a corpus plan already covers the intake |
| Wikipedia, "Lists of common misspellings/For machines" | Typo → correction pairs | CC BY-SA (second-hand: a CRAN package's COPYRIGHTS file) | An error model for the spelling tier. Share-alike: a shipped derived list stays CC BY-SA, so keep it a separate data file with its own notice |
| proselint | Rules on redundancy, clichés, hedging, jargon, illogic, drawn from usage guides | BSD (from its 2016 SciPy paper; check the repository LICENSE) | Port selected checks as Researchly rules, each with fire and don't-fire tests and a noise-floor run |
| write-good | Passive voice, weasel words, wordy phrases, "there is/are" openers | MIT (README notice, 2014) | The same: compare with our existing rules, port only what adds precision |
| U.S. Federal Plain Language Guidelines (2011) and the plainlanguage.gov word list | Plainer substitutes for complex words; short-sentence guidance | Likely public domain as U.S. federal work (not confirmed on the site) | Extend the plain-words rules and their lexicon |
| Mensh & Kording (2017), "Ten simple rules for structuring papers", PLOS Comput Biol | Context–content–conclusion at every scale; one message per paper | CC BY (PLOS and PMC pages; second-hand via search) | Knowledge source for Learn cards and narrative-map questions, cited by name |
| UNC Writing Center handouts | Teaching guidance on scientific writing | CC BY-NC-ND (2.5 and 4.0 seen) | Cite only. No derivatives: no adapted text may ship |
| Manchester Academic Phrasebank | Phrases by rhetorical function | University of Manchester copyright; the PDF forbids redistribution | Cite only, as a pointer for writers. No phrases ship, and it is not used to generate sentences |

## Features this suggests, within the project's rules

1. **Context-aware spelling and word choice.** A local n-gram model trained
   on CC BY sources scores a word against its neighbours, so "the data form
   the survey" can be flagged. It proposes a single-word correction with a
   confidence, in a new tier labelled as learned, never auto-applied
   (CLAUDE.md #1). This is the open replacement for the capability the owner
   asked about.
2. **More plain-word and wordiness rules**, from the plain-language list,
   proselint and write-good. Each needs fire and don't-fire tests and a
   noise-floor run (precision over recall, CLAUDE.md #5).
3. **Structure lessons** from Mensh & Kording, as Learn cards and narrative-map
   questions.

Not proposed: phrase or sentence autocomplete. Suggesting the next words of
a sentence is drafting for the author, which CLAUDE.md #1 forbids whatever
the source.

## Rejected (2026-10-14)

The owner uploaded scripts and decoded data tables taken from a commercial
writing assistant's browser extension: its n-gram table, autocorrect
classifier, vocabulary, phrase lists, dialect map and blocklists. They are
another company's proprietary product data with no licence to reuse. They
were not opened beyond reading the scripts' descriptions, and nothing from
them is in this repository or the app. See `ml/datasets.yaml`,
`rejected-commercial-extension-tables`.

## Sources

- [Google Books Ngram downloader (licence statement)](https://pypi.org/project/google-ngram-downloader)
- [Wikipedia: Lists of common misspellings](https://wikipedia.com/wiki/Wikipedia:LCM)
- [CRAN fuzzystring COPYRIGHTS (licence of the misspellings list)](https://cran.nics.utk.edu/cran/web/packages/fuzzystring/COPYRIGHTS)
- [proselint (GitHub)](https://github.com/amperser/proselint) and [its SciPy 2016 paper](https://proceedings.scipy.org/articles/Majora-629e541a-00d.pdf)
- [write-good README](https://cdn.jsdelivr.net/npm/write-good@1.0.8/README.md)
- [Plain language word suggestions (archived plainlanguage.gov)](https://cybercemetery.unt.edu/oilspill/20121014022836mp_/http://www.plainlanguage.gov/howto/wordsuggestions/index.cfm)
- [Mensh & Kording 2017 (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC5619685/)
- [UNC Writing Center (licence footer)](https://writingcenter.unc.edu/outlines-demo/)
- [Academic Phrasebank](https://www.phrasebank.manchester.ac.uk/)
