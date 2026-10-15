# Researchly grammar notes

*Source document for the `GN` rules (source code `rgn`; cards show it as
"Researchly grammar notes"). Written for Researchly on 2026-10-15, at build
time, from general knowledge of English grammar and of how the major
Englishes differ (owner decision, ARCHITECTURE.md ADR-11). The wording and
the examples are Researchly's own: nothing here is copied or closely
paraphrased from a book, a style guide or another product, and every
example sentence is invented. The engine never consults a model: each note
below is carried out by a deterministic rule in
`packages/core/researchly/rules_grammar_notes.py`, with fire and don't-fire
tests in `packages/core/tests/test_grammar_notes.py`.*

## How to read these notes

Each note gives:

- **Rule**: what is flagged, in one sentence.
- **Why it matters**: what goes wrong for a reader of research writing.
- **Examples**: invented sentences, the flagged form first.
- **Across Englishes**: how American (US), British (UK), Canadian (CA),
  Australian (AU) and Indian (IN) English differ, where they do.
- **Not flagged**: what the rule leaves alone on purpose. Precision comes
  first (CLAUDE.md #5): a note that cannot be checked without false alarms
  is narrowed until it can, or dropped.

### Which English

The writer's choice of English is the `spelling` setting (`auto`, `us`,
`uk`, `uk-oxford`, `ca`, `au`, `in`), the same one that drives the spelling
checks. Indian English follows British usage in grammar as it does in
spelling, and Oxford spelling (`uk-oxford`) changes only spelling, so the
grammar notes treat `uk`, `uk-oxford`, `au` and `in` alike ("British-pattern
English"). Canadian English sits between: American in some habits,
British in others, and it is noted rule by rule.

With the setting on `auto`, the regional notes say nothing about a single
use, because either English could be right. They speak only when the
document mixes two styles of its own (dates, and full stops with quotation
marks).

### Categories

Regional notes (GN1xx) are **Conventions**: a usage that belongs to one
English is not an error in another, and Researchly never presents it as
one (CLAUDE.md #3). Grammar notes for research prose (GN2xx) are
**Improvements**, or a Convention or Preference where both forms are
accepted. None is a **Correction** yet: a rule is shown above Improvement
only once its precision on the real-document bench is measured at 0.9 or
more (`docs/inline-review-design.md` §7).

## Regional conventions (GN1xx)

### GN101 — Group nouns take a singular verb in American English

**Rule.** With American English chosen, a singular noun for a group of
people (team, committee, government, panel, board, council, jury, cohort,
consortium, family, company, audience, ministry, department, public, group,
population) followed by "are", "were", "have" or "do" is flagged.

**Why it matters.** American readers hear "the committee were" as British.
In a paper written to an American journal's style, it is one of the few
grammatical tells that the text was not edited to that style.

**Examples.**
- Flagged (US): *The committee were divided on the second dose.* → *was*
- Flagged (US): *The cohort have a median age of 40 years.* → *has*
- Fine everywhere: *The committee was divided on the second dose.*

**Across Englishes.** US: singular, almost always. UK, AU, IN: either, by
meaning; the plural when the members act separately ("the panel were
divided"), the singular when the group acts as one ("the panel was
appointed"). CA: mostly singular, but the plural is heard; not flagged.

**Not flagged.** A group noun followed by "of" and a plural ("a group of
patients were admitted"): there the verb follows the people in every
English. A noun with no determiner (often a table label run into the
text), coordinated subjects ("the team and the board were"), and any
English other than American.

### GN102 — Different from, than and to

**Rule.** "different than" is flagged in British-pattern English;
"different to" is flagged in American and Canadian English. The suggestion
is always "different from".

**Why it matters.** "Different from" is standard in every English, so it is
the one form no reader questions. The other two each read as foreign, and
"different than" is a common target of British copy-editors.

**Examples.**
- Flagged (UK, AU, IN): *The second estimate is different than the first.*
- Flagged (US, CA): *The second estimate is different to the first.*
- Fine everywhere: *The second estimate is different from the first.*

**Across Englishes.** US: "from" and "than" (the latter especially before
a clause: "different than we expected"). UK, AU, IN: "from" and "to"; "than"
is disliked. CA: "from" and "than", like American English.

**Not flagged.** A real comparison ("more different than we expected"),
"different to" about how something seems to someone ("different to the
reader"), "different to" before a verb ("something different to do"), a
range ("from different to similar"), and the `auto` setting.

### GN103 — "gotten" outside North America

**Rule.** With British-pattern English chosen, "gotten" is flagged, with
"got" as the fix.

**Why it matters.** British, Australian and Indian readers hear "have
gotten" as American. In research prose a more exact verb usually reads
better in any English ("obtained", "become", "received"), and the card
says so.

**Examples.**
- Flagged (UK, AU, IN): *The estimates have gotten worse over time.*
- Better everywhere: *The estimates have become less precise over time.*

**Across Englishes.** US and CA: "gotten" is the usual participle of "get"
in the sense of obtaining or becoming. UK, AU, IN: "got", with "gotten"
kept in set phrases.

**Not flagged.** "ill-gotten", "forgotten", and American, Canadian or
`auto`.

### GN104 — "whilst" in American English

**Rule.** With American English chosen, "whilst" is flagged, with "while"
as the fix.

**Why it matters.** In American English "whilst" reads as British or
old-fashioned. "While" means the same in every English.

**Examples.**
- Flagged (US): *Whilst the model fits well, the tails are heavy.*
- Fine everywhere: *While the model fits well, the tails are heavy.*

**Across Englishes.** UK, AU, IN: both, "whilst" a little more formal.
US: "while". CA: mostly "while"; "whilst" is rare but not flagged.

**Not flagged.** Any English other than American.

### GN105 — "was fit" and "was fitted"

**Rule.** With British-pattern English chosen, "fit" as the passive past
participle of fitting a model ("was fit to", "were fit using") is flagged,
with "fitted" as the fix.

**Why it matters.** Modelling papers say this sentence constantly.
American English often uses "fit" as the past form of the verb; British,
Australian and Indian English use "fitted", and an editor working to those
styles will change it.

**Examples.**
- Flagged (UK, AU, IN): *The model was fit to weekly counts.*
- Fine everywhere: *The model was fitted to weekly counts.*

**Across Englishes.** US: "fit" and "fitted" both, "fit" common in
statistics. CA: both. UK, AU, IN: "fitted".

**Not flagged.** The adjective: "fit for purpose", "fit to travel" (the
word after "to" is a verb). The active past ("we fit the model"), because
it cannot be told from the present without guessing. American, Canadian
and `auto`.

### GN106 — Full stops and commas with closing quotation marks

**Rule.** American and Canadian English: a full stop or comma after a
closing quotation mark is flagged (it goes inside). British-pattern
English: a full stop or comma inside the closing quotation mark of a short
lower-case term is flagged (it goes outside). `auto`: only a document that
uses both placements is flagged, towards the one it uses more (on a tie,
the one it used first).

**Why it matters.** Readers do not notice the convention when it is kept;
they notice when it changes from one paragraph to the next.

**Examples.**
- Flagged (US, CA): *We call this "herd protection". It lasts.*
- Flagged (UK, AU, IN): *We call this "herd protection." It lasts.*

**Across Englishes.** US and CA put full stops and commas inside the
closing mark, always. UK, AU and IN put them where the sense puts them:
outside after a quoted word or phrase, inside when a whole quoted sentence
ends with it. (British-pattern English also prefers single quotation
marks; that is not checked.)

**Not flagged.** In British-pattern English, a quoted full sentence ("The
leaflet said "Stay at home today.""), because its own full stop may stay
inside. Question marks, colons and semicolons. Reference entries, where
the cited work's style decides.

### GN107 — Dates in prose

**Rule.** With British-pattern English chosen, a month-first date
("October 15, 2026") is flagged, with the day-first form as the fix. In any
English, a document that writes dates both ways is flagged, towards the
form it uses more; with American English chosen, towards the month-first
form.

**Why it matters.** "15 October 2026" and "October 15, 2026" are both
clear, but a document that switches between them looks assembled from
pieces.

**Examples.**
- Flagged (UK, AU, IN): *The trial began on October 15, 2026.*
- Flagged (any, when mixed): *Enrolment ran from 3 March 2026 to April 9,
  2026.*

**Across Englishes.** US: month first with a comma before the year; the
day-first form is also normal in American scientific and military writing,
so it is flagged there only in a mixture. UK, AU, IN: day first, no comma.
CA: both are in use; only mixtures are flagged.

**Not flagged.** Dates written only in numbers (03/04/2026): they are
ambiguous across Englishes, but a reader cannot be told which was meant
without guessing. Either end of a range ("June 3–July 9, 2020"), reference
entries, table cells.

## Grammar of research prose (GN2xx)

LanguageTool (LT001) already checks general grammar. These notes target
what it misses in research writing, found by running it on invented
sentences of each kind (2026-10-15).

### GN201 — Agreement across an "of" phrase

**Rule.** A plural verb ("are", "were", "have", "do") whose subject is a
singular head noun followed by "of" and a plural noun is flagged, when the
head is one that names a single quantity or thing: proportion, percentage,
fraction, share, number, rate, risk, incidence, prevalence, probability,
likelihood, mean, median, average, sum, distribution, frequency, ratio,
level, concentration, duration, size, magnitude, variance, accuracy,
sensitivity, specificity, performance, quality, effect, impact, estimate,
aim, purpose, goal, objective, timing, severity, burden, cost, age; and the
pronouns "each" and "one".

**Why it matters.** Research sentences put long "of" phrases between a
subject and its verb ("the proportion of laboratory-confirmed cases in
children under five"), so the nearest noun is plural and pulls the verb
with it. The subject is still the proportion.

**Examples.**
- Flagged: *The proportion of cases were higher in the north.* → *was*
- Flagged: *Each of the models have converged.* → *has*
- Fine: *The proportion of cases was higher in the north.*

**Across Englishes.** The same in all five.

**Not flagged.** Heads that agree with what they quantify in careful
writing: "a proportion of patients were", "a number of studies have", "an
average of 40 samples were taken", "the majority of patients were", "the
rest", "a range of", "a group of". Coordinated or interrupted subjects ("the
mean and the median were", "the date and the number of articles were").
Main verbs other than "are/were/have/do", because the tagger sometimes
reads an adjective as a plural verb ("the percentage of patients reactive
to"). "None", "neither" and "either", after which a plural verb is
accepted.

### GN202 — "A number of" takes a plural verb

**Rule.** "A number of" + plural noun followed by a singular verb ("is",
"was", "has", "does", or another singular form) is flagged.

**Why it matters.** "A number of studies" means "several studies"; "the
number of studies" is one number. Mixing the two is common in literature
reviews.

**Examples.**
- Flagged: *A number of studies has shown this effect.* → *have*
- Fine: *The number of studies has grown.*

**Across Englishes.** The same in all five.

**Not flagged.** "The number of …" with a singular verb, which is right.

### GN203 — "Neither … nor" with two singular nouns

**Rule.** A sentence that opens "Neither A nor B", where A and B are both
singular nouns, followed by "are", "were", "have" or "do", is flagged.

**Why it matters.** "Neither … nor" speaks of each in turn, so two
singular nouns take a singular verb. A reviewer reading closely will notice
the plural.

**Examples.**
- Flagged: *Neither the model nor the method are suitable here.* → *is*
- Fine: *Neither the model nor the data are suitable here.* (the verb
  follows the nearer noun, here plural)

**Across Englishes.** The same in all five; a plural is common in speech
everywhere.

**Not flagged.** A plural nearer noun, pronouns ("neither he nor I"), and
"neither of the …", after which a plural verb is accepted.

### GN204 — "The reason is because"

**Rule.** "reason … is/was because" within one sentence is flagged; the fix
is "is that" (none is offered for "because of").

**Why it matters.** "The reason" already says "why", so "is because" says
it twice. Readers of discussions and limitations sections meet it often.

**Examples.**
- Flagged: *The reason is because the counts were delayed.* → *is that*
- Fine: *The counts fell because testing stopped.*

**Across Englishes.** Common in speech everywhere, edited out of formal
writing everywhere.

**Not flagged.** "for this reason, …" and "by reason of", where "reason" is
not the subject.

### GN205 — A dangling opener before a passive

**Rule.** A sentence that opens with an "-ing" phrase ("Using …", "After
fitting …", "By comparing …") followed by a comma and a passive main clause
whose subject is not the one doing the "-ing", with no "we" in the
sentence, is flagged.

**Why it matters.** An opening "-ing" phrase takes its doer from the
subject of the main clause. In "Using a Bayesian model, the parameters were
estimated", the parameters use the model. Methods sections produce this
sentence because the passive hides the people who did the work. The fix is
to name them ("we estimated") or to put the method after the verb ("The
parameters were estimated with a Bayesian model"). The passive itself is
fine in Methods and is never flagged there (CLAUDE.md #4).

**Examples.**
- Flagged: *Using a Bayesian model, the parameters were estimated from
  weekly counts.*
- Flagged: *After fitting the model, the residuals were inspected.*
- Fine: *Using a Bayesian model, we estimated the parameters.*

**Across Englishes.** The same in all five.

**Not flagged.** Openers that act as prepositions or set phrases:
assuming, considering, given, including, excluding, regarding, concerning,
following, according (to), depending (on), notwithstanding, provided,
owing (to), barring, speaking, judging, granted, starting, beginning, and
the mathematician's taking, letting, denoting, writing ("Taking X to denote
…"). "Being" and "having been" openers. Past-participle openers ("Based on
…", "Compared with …"), which are debated rather than wrong. A main clause
in the active voice, which may well have the right doer. Openers in Title
Case (a heading run into the text).

### GN206 — "A" or "an" before an abbreviation

**Rule.** "a" or "an" that does not match how a listed abbreviation is
said is flagged, with the right article and the pronunciation.

**Why it matters.** The article follows the first sound, not the first
letter. Abbreviations read letter by letter that start with F, H, L, M, N,
R, S or X begin with a vowel sound ("an MCMC sampler", "an RCT", "an HIV
test"); abbreviations said as words, or starting with a "you" sound, take
"a" ("a NATO grant", "a SNP", "a UK cohort"). LanguageTool guesses from
the letter and misses many of these, so for the listed abbreviations
Researchly's note replaces its card.

**Examples.**
- Flagged: *We used a MCMC sampler.* → *an*
- Flagged: *This was an UK cohort.* → *a*
- Flagged: *An SNP array was used.* → *A* (SNP is said "snip")

**Across Englishes.** The same in all five, with one caveat: the letter H
is "aitch" in most Englishes and "haitch" for some speakers in Australia,
Ireland and India. Printed usage everywhere is "an HIV", which the note
follows.

**Not flagged.** Abbreviations said two ways in published work: SIR and
SEIR ("ess-eye-ar" or "sir"; "seer"), SIS, MAP, LOO, WAIC, SQL, and SE
("ess-ee" as a standard error, "south-east" in "SE Asia"). Any abbreviation
not on the list (`lexicons.ABBREVIATION_ARTICLE`). A capital "A" in the
middle of a sentence ("Group A HIV cases"), which is a label.

### GN207 — "Data": singular and plural in one document

**Rule.** When a document treats "data" as plural in some places ("the data
are", "these data") and singular in others ("the data is", "this data"),
the rarer form is flagged once, with a count.

**Why it matters.** Both are accepted: the plural is the older scientific
habit and many journals ask for it; the singular, data as one body of
information, is now common in every field. A mixture reads as careless,
especially in a co-authored paper.

**Examples.**
- Flagged: *The data are sparse. These data were collected weekly. The
  data is noisy in winter.* (at "is")
- Fine: any document that keeps to one form.

**Across Englishes.** The same in all five. The plural is a little more
common in British and Indian scientific writing, but the note does not
take sides.

**Not flagged.** "data and code are" (a plural subject either way), a
"data" whose own phrase disagrees with itself, and a document that uses
only one form.

### GN208 — "Which" and "that" in American English (Preference)

**Rule.** With American English chosen, "which" that starts a clause
defining its noun (no comma before it: "the model which we fitted") is
flagged, with "that" as the fix. This is a **Preference**: hidden unless
the writer shows preferences.

**Why it matters.** Most American style manuals teach "that" for a clause
that says which one is meant and "which" after a comma for a clause that
adds a comment. Editors of American journals apply it.

**Examples.**
- Flagged (US, Preference): *We report the model which we fitted to the
  counts.*
- Fine: *We report the model that we fitted to the counts.*
- Fine: *We report the model, which we fitted to the counts.*

**Across Englishes.** UK, AU, IN: "which" for both kinds of clause is
standard. CA: either. US: the distinction above.

**Not flagged.** "in which", "of which", "to which" and other prepositions,
"which" after a comma, and every English other than American. A clause
that should have had a comma (a comment, not a definition) is flagged too,
and the card's "why" says what to do then; that is why the rule is a
Preference.

## Considered and dropped

| Candidate | Why it is not a Researchly rule |
|---|---|
| "less" with countable plurals ("less cases") | LanguageTool's `FEWER_LESS` catches it reliably (checked on invented sentences, 2026-10-15). |
| "between 5 to 10" | LanguageTool's `BETWEEN_TO_AND` catches it. |
| "comprised of" | LanguageTool's `COMPRISED_OF` catches it. |
| Double comparatives ("more better", "more higher") | LanguageTool's `MOST_COMPARATIVE` catches them. |
| "compared to" and "compared with" | Both are accepted in research prose in every English; the traditional difference (likening against contrasting) is a house-style matter, and the phrase is so frequent that a card would fire many times per paper. |
| "in hospital", "at university" against "in the hospital" | Medical journals in every English write "in hospital" and "admitted to hospital", whatever their spelling; "in hospital" is also often a compound adjective missing its hyphen ("in hospital deaths"). Too noisy to be a convention check. |
| "at the weekend" and "on the weekend" | Rare in research prose. |
| "fill in" and "fill out" (a form) | Both are used in every English. |
| Ambiguous numeric dates (03/04/2026) | A real ambiguity, but nothing tells the checker which date was meant, so the card could only ask; left for a later note if writers want it. |
| "toward" and "towards" | Both are accepted in American English; British English prefers "towards", but "toward" is not wrong there. |

## Further reading

These are standard references a reader can consult for more on the topics
above. They are listed as further reading only: the notes above are
Researchly's own wording and are not taken from them.

- The Chicago Manual of Style, 17th or 18th edition, University of Chicago
  Press: American usage, punctuation with quotation marks, dates.
- AMA Manual of Style, 11th edition, Oxford University Press: American
  medical and scientific usage.
- New Hart's Rules, 2nd edition, Oxford University Press: British usage and
  Oxford spelling.
- R. Huddleston and G. K. Pullum (2002), The Cambridge Grammar of the
  English Language, Cambridge University Press: agreement, relative
  clauses, comparatives.
- R. Quirk, S. Greenbaum, G. Leech and J. Svartvik (1985), A Comprehensive
  Grammar of the English Language, Longman: collective nouns and notional
  agreement.
- M. Swan, Practical English Usage, 4th edition, Oxford University Press:
  differences between British and American usage.
- P. Peters (2004), The Cambridge Guide to English Usage, Cambridge
  University Press: usage across British, American, Canadian and Australian
  English.
- The Australian Government Style Manual (stylemanual.gov.au): Australian
  usage and dates.
- The Canadian Press Stylebook and the Government of Canada's writing
  tools (Language Portal of Canada): Canadian usage.
- Merriam-Webster's Dictionary of English Usage: usage notes on "different
  than", "data", "gotten" and "whilst".
