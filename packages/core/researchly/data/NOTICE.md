# Third-party data in this folder

Researchly's code is MIT-licensed (`LICENSE` at the repository root). Three
files here are derived from other people's data and keep their own terms.
Each file also carries its notice in its own header, so it travels with the
file. The registry entry for every source is in `ml/datasets.yaml`.

| File | Derived from | Licence | Built by |
|---|---|---|---|
| `variants.tsv` | VarCon, Kevin Atkinson (wordlist.aspell.net; now the English Speller Database) | VarCon's permissive notice, reproduced in the file header | `ml/tools/build_variants.py` |
| `specialist_words.txt` | SPECIALIST Lexicon, release 2026, U.S. National Library of Medicine | SPECIALIST NLP Tools terms; section 4 and the list of modifications are in the file header | `ml/tools/build_specialist_words.py` |
| `spell_errors.json` | "Wikipedia:Lists of common misspellings/For machines", Wikipedia contributors | **CC BY-SA 4.0**: the attribution and licence are in the file's `licence`, `licence_url` and `attribution` fields | `ml/tools/build_spell_errors.py` |

`spell_errors.json` is an adaptation of a CC BY-SA 4.0 work, so it is
licensed under CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/).
The modification: the list's training split was reduced to log-probabilities
of single character edits with one letter of context. The rest of Researchly
is not under CC BY-SA. The table is read as data at run time and stays a
separate file. Anyone who changes the table must share the changed table
under the same licence.

`scientific_terms.txt` is Researchly's own word list (MIT).

The two SymSpell dictionaries (single words and word pairs) are not copied
here. They are read from the installed `symspellpy` package (MIT).
