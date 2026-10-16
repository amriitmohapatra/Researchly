"""Curated word lists. Deliberately conservative: precision over recall.

Sources: the project's writing-craft guide (§4, §6, §9), the AJE 2022
causal-language word lists (Am J Epidemiol), and standard plain-language
style references. Every list is easy to audit and extend — auditable rules
are a trust feature (research/04).
"""

# --- W201: single grand words → plain alternatives -------------------------
# (employ/leverage/elucidate added from the lecture's avoid-list, which treats
#  them as needlessly grand where plain 'use' or 'clarify' would do)
GRAND_WORDS = {
    "utilize": "use", "utilizes": "uses", "utilized": "used",
    "utilizing": "using", "utilization": "use", "utilisation": "use",
    "utilise": "use", "utilises": "uses", "utilised": "used",
    "commence": "begin", "commences": "begins", "commenced": "began",
    "endeavor": "try", "endeavour": "try",
    "ascertain": "determine",
    "necessitates": "requires", "necessitate": "require",
    "leverage": "use", "leverages": "uses", "leveraged": "used",
    "elucidate": "clarify", "elucidates": "clarifies",
    "elucidated": "clarified",
}
# Grand only as verbs: "financial leverage" and "this endeavour" are nouns,
# and "use"/"try" would make nonsense of them (P33).
GRAND_ONLY_AS_VERB = frozenset({
    "leverage", "leverages", "leveraged", "endeavor", "endeavour"})

# --- S001: Latin phrases of academic and legal English -----------------------
# "ad valorem" was read as the lone word "valorem" and corrected to "galore"
# (owner's assignment, 2026-10-08). A word is skipped when it and a
# neighbour form one of these.
LATIN_PHRASES = frozenset({
    "ad valorem", "ad hoc", "ad libitum", "ad infinitum", "a priori",
    "a posteriori", "a fortiori", "per capita", "per se", "per annum",
    "per diem", "pro rata", "pro forma", "pro bono", "de facto", "de jure",
    "de novo", "ex ante", "ex post", "ex vivo", "ex officio", "in situ",
    "in vitro", "in vivo", "in silico", "in utero", "in toto", "in extremis",
    "inter alia", "intra vitam", "prima facie", "bona fide", "mutatis mutandis",
    "ceteris paribus", "status quo", "vice versa", "sine qua non", "sui generis",
    "post hoc", "post mortem", "ante mortem", "ipso facto", "modus operandi",
    "non sequitur", "quid pro quo", "et cetera", "et al", "sensu lato",
    "sensu stricto", "viva voce", "nota bene", "sic passim", "circa",
})
_LATIN_WORDS = frozenset(w for ph in LATIN_PHRASES for w in ph.split())

# --- W202: wordy phrases → tighter alternatives ----------------------------
WORDY_PHRASES = {
    "due to the fact that": "because",
    "owing to the fact that": "because",
    "despite the fact that": "although",
    "in spite of the fact that": "although",
    "in order to": "to",
    "prior to": "before",
    "subsequent to": "after",
    "at this point in time": "now",
    "in the event that": "if",
    "in close proximity to": "near",
    "by means of": "by",
    "has the ability to": "can",
    "have the ability to": "can",
    "whether or not": "whether",
    "in excess of": "more than",
    "a majority of": "most",
    "the majority of": "most",
    "a large number of": "many",
    "it is possible that": "possibly / may",
    "in the absence of": "without",
    "period of time": "period",
}

# --- W203: hype / buzzwords -------------------------------------------------
HYPE_WORDS = (
    "novel", "cutting-edge", "state-of-the-art", "groundbreaking",
    "ground-breaking", "paradigm-shifting", "revolutionary", "unprecedented",
    "game-changing",
)
# "novel coronavirus/pathogen/variant..." is technical usage, not hype.
HYPE_TECHNICAL_FOLLOWERS = (
    "coronavirus", "virus", "pathogen", "variant", "strain", "influenza",
    "serotype", "antigen", "compound", "species", "host",
)

# --- W204: intensifiers (Preference) ---------------------------------------
INTENSIFIERS = ("very", "extremely", "really", "incredibly", "hugely",
                "tremendously", "massively")

# --- W205: filler / throat-clearing ----------------------------------------
FILLER_PHRASES = (
    "it should be noted that",
    "it is important to note that",
    "it is worth noting that",
    "it is interesting to note that",
    "it must be mentioned that",
    "needless to say",
    "as a matter of fact",
    "it goes without saying that",
)

# --- W206: redundant pairs --------------------------------------------------
REDUNDANT_PAIRS = {
    "each and every": "every",
    "first and foremost": "first",
    "full and complete": "complete",
    "basic fundamentals": "fundamentals",
    "end result": "result",
    "final outcome": "outcome",
    "past history": "history",
    "advance planning": "planning",
    "completely eliminate": "eliminate",
    "close proximity": "proximity",
    "exactly identical": "identical",
    "general consensus": "consensus",
    "mutual cooperation": "cooperation",
    "small in size": "small",
    "brief in duration": "brief",
    "future prospects": "prospects",
}

# --- W208: contractions -----------------------------------------------------
CONTRACTIONS = (
    "don't", "doesn't", "didn't", "isn't", "aren't", "wasn't", "weren't",
    "can't", "couldn't", "won't", "wouldn't", "shouldn't", "hasn't",
    "haven't", "hadn't", "it's", "we're", "we've", "we'll", "they're",
    "there's", "that's", "let's", "i'm", "you're", "what's", "who's",
)

# The full form W208 offers. Only contractions with one reading: "it's" is
# "it is" or "it has" ("it's been"), so the 's forms are expanded only when
# the next word is not "been" or "got" (see w208_contractions).
CONTRACTION_EXPANSIONS = {
    "don't": "do not", "doesn't": "does not", "didn't": "did not",
    "isn't": "is not", "aren't": "are not", "wasn't": "was not",
    "weren't": "were not", "can't": "cannot", "couldn't": "could not",
    "won't": "will not", "wouldn't": "would not",
    "shouldn't": "should not", "hasn't": "has not", "haven't": "have not",
    "hadn't": "had not", "we're": "we are", "we've": "we have",
    "we'll": "we will", "they're": "they are", "let's": "let us",
    "i'm": "I am", "you're": "you are",
    "it's": "it is", "there's": "there is", "that's": "that is",
    "what's": "what is", "who's": "who is",
}

# Contractions typed without their apostrophe ("dont"). A keyboard restores
# the apostrophe; in formal prose the full form is the fix. Words that are
# also real words are left out: cant, wont, lets, its, were, well, shell,
# hell, id, ill, im (also "IM", intramuscular).
APOSTROPHELESS_CONTRACTIONS = {
    "dont": "do not", "doesnt": "does not", "didnt": "did not",
    "isnt": "is not", "arent": "are not", "wasnt": "was not",
    "werent": "were not", "couldnt": "could not", "wouldnt": "would not",
    "shouldnt": "should not", "hasnt": "has not", "havent": "have not",
    "hadnt": "had not", "mustnt": "must not", "neednt": "need not",
    "thats": "that is", "theres": "there is", "whats": "what is",
    "theyre": "they are", "youre": "you are",
    "couldve": "could have", "wouldve": "would have",
    "shouldve": "should have",
}

# --- S001 / S003: endings of coined biomedical names -------------------------
# A repeated unknown word with one of these endings is built like a term (a
# drug, an enzyme, a condition, a virus), so it is asked about once (S003)
# rather than corrected at every use, even when a common word is one letter
# away. Only endings that general English words seldom share: "-ase" and
# "-ome" were left out because "increase" and "outcome" end that way, and a
# typo of them would have been taken for a term.
TERM_ENDINGS = (
    "mab", "mabs", "vir", "virs", "cillin", "mycin", "azole", "azoles",
    "kinase", "kinases", "osis", "oses", "itis", "aemia", "emia", "omics",
    "virus", "viruses", "phage", "phages", "cyte", "cytes", "plasma",
    "plasmas", "bacter", "coccus", "cocci",
)

# --- W212: uncountable nouns given a plural ---------------------------------
# Mass nouns that standard English does not pluralise: a common slip for
# writers whose first language counts them ("softwares", "informations"),
# and Latin plurals given a second, English plural ("criterias").
# Left out on purpose, because a correct reading exists: verbs
# ("researches", "evidences", "progresses"), countable uses in a field
# ("climate feedbacks", "indigenous knowledges"), and plurals that are
# themselves correct ("data", "criteria", "phenomena", "bacteria").
UNCOUNTABLE_PLURALS = {
    "informations": "information", "softwares": "software",
    "hardwares": "hardware", "equipments": "equipment",
    "advices": "advice",
    "datas": "data", "criterias": "criteria", "phenomenas": "phenomena",
    "bacterias": "bacteria", "stimulis": "stimuli",
}
LATIN_PLURALS = frozenset({"data", "criteria", "phenomena", "bacteria",
                           "stimuli"})

# --- C301: hedges -----------------------------------------------------------
HEDGE_TOKENS = {
    "may", "might", "could", "possibly", "potentially", "perhaps",
    "presumably", "apparently", "seemingly", "arguably", "somewhat",
    "likely", "suggest", "suggests", "suggested", "appear", "appears",
    "appeared", "seem", "seems", "seemed", "tentatively", "conceivably",
}

# --- C302: overclaiming -----------------------------------------------------
OVERCLAIM_PATTERNS = (
    r"\bproves?\b", r"\bproved\b", r"\bproven\b",
    r"\bconclusively\b", r"\bdefinitively\b", r"\bunambiguously\b",
    r"\bbeyond (?:any )?doubt\b", r"\bundoubtedly\b",
    r"\bestablishes that\b",
)

# --- C303: causal verbs (AJE 2022-style list) ------------------------------
CAUSAL_VERB_LEMMAS = {
    "cause", "reduce", "increase", "decrease", "improve", "prevent",
    "protect", "drive", "affect", "impact", "lower", "raise", "worsen",
    "mitigate", "avert",
}
CAUSAL_PHRASES = (r"\bleads? to\b", r"\bled to\b", r"\bresults? in\b",
                  r"\bresulted in\b")
# Verbs describing the *authors'* actions are fine ("we increased the
# sample size"); only claims about the world are flagged.
AUTHOR_SUBJECTS = {"we", "i", "author", "authors", "study", "analysis",
                   "model", "simulation", "paper"}

# --- C305: assertive adverbs ------------------------------------------------
ASSERTIVE_PATTERNS = (
    r"\bclearly\b", r"\bobviously\b", r"\bof course\b", r"\bevidently\b",
    r"\bit is clear that\b", r"\bit is obvious that\b",
)

# --- G102: light verbs + nominalization → verb ------------------------------
LIGHT_VERBS = {"perform", "conduct", "make", "carry", "undertake", "execute",
               "do", "provide", "achieve", "accomplish"}
NOMINAL_TO_VERB = {
    "estimation": "estimate", "comparison": "compare", "analysis": "analyse",
    "analyses": "analyse", "investigation": "investigate",
    "assessment": "assess", "evaluation": "evaluate",
    "examination": "examine", "measurement": "measure",
    "calculation": "calculate", "computation": "compute",
    "implementation": "implement", "identification": "identify",
    "validation": "validate", "simulation": "simulate",
    "estimations": "estimate", "comparisons": "compare",
    "calibration": "calibrate", "optimization": "optimise",
    "optimisation": "optimise", "adjustment": "adjust",
    "determination": "determine", "prediction": "predict",
    "description": "describe", "collection": "collect",
    "selection": "select", "derivation": "derive",
}

# --- G103: nominalization suffixes -----------------------------------------
NOMINAL_SUFFIXES = ("tion", "sion", "ment", "ance", "ence", "ency", "ancy")
NOMINAL_MIN_LEN = 7
# Common words that end in these suffixes but read fine / aren't derived
NOMINAL_ALLOWLIST = {
    "attention", "information", "population", "distribution", "proportion",
    "question", "section", "equation", "function", "position", "condition",
    "government", "environment", "moment", "element", "document",
    "experiment", "department", "instrument", "treatment", "science",
    "evidence", "confidence", "difference", "prevalence", "incidence",
    "influence", "absence", "presence", "sentence", "reference",
    "transmission", "emission", "session", "profession", "dimension",
    "infection", "intervention", "vaccination", "surveillance", "variance",
    "importance", "significance", "frequency", "tendency", "emergency",
    "agency", "region", "religion", "version", "mention",
}

# --- G108: weak stress-position trailers ------------------------------------
TRAILING_QUALIFIERS = (
    r", according to [^,.;]+$",
    r", as (?:shown|seen|reported|illustrated|demonstrated) (?:in|by) [^,.;]+$",
    r", in (?:our|this) (?:study|analysis|simulations?|model)$",
)

# --- E7xx: rules mined from the owner's lecture notes on scientific writing -

# E701: low-information phrases that sound substantive but say nothing
# (the lecture, 'Information density')
EMPTY_PHRASES = (
    "holistic understanding",
    "comprehensive understanding of the complex",
    "sheds light on", "shed light on", "shedding light on",
    "paves the way for", "pave the way for",
    "provides valuable insights into", "provide valuable insights into",
    "provides important insights into",
    "helps to inform", "help to inform",
    "a wide range of applications",
)

# E703: verbs after a naked sentence-initial "This"
NAKED_THIS_VERBS = {
    "is", "was", "has", "can", "could", "may", "might", "will", "would",
    "suggests", "indicates", "means", "implies", "shows", "demonstrates",
    "allows", "highlights", "raises", "reflects", "leads", "led",
    "results", "resulted", "supports", "confirms", "underscores",
}

# E704: consensus claims that need an owner or a citation
CONSENSUS_RX = (r"\b(?:is|are)\s+(?:widely\s+|generally\s+|commonly\s+)?"
                r"(?:known|considered|believed|thought|recognized|"
                r"recognised|regarded|assumed)\s+to\b")

# E705: absolute novelty claims (risky without "to our knowledge")
NOVELTY_RX = (
    r"\b(?:has|have)\s+(?:never\s+|not\s+)(?:yet\s+)?been\s+"
    r"(?:studied|investigated|explored|examined|reported|done|addressed|"
    r"quantified|characteri[sz]ed|assessed)\b"
    r"|\bno\s+(?:prior\s+|previous\s+)?(?:study|studies|work|research)\s+"
    r"(?:has|have|exists?)\b",
)
KNOWLEDGE_SOFTENERS = ("to our knowledge", "to the best of our knowledge",
                       "as far as we are aware", "we are not aware")

# D903: a gap stated as a bare absence ("remains underexplored", "has been
# overlooked", "little is known about"). Question-raising wording ("it is
# unclear whether") and disagreement are not absences and are left alone.
ABSENCE_GAP_RX = (
    r"\b(?:under-?explored|under-?studied|under-?researched|"
    r"under-?investigated|under-?examined|unexplored|unstudied)\b",
    r"\b(?:has|have)\s+(?:largely\s+|mostly\s+|often\s+|generally\s+)?"
    r"(?:been\s+)?(?:largely\s+|mostly\s+|often\s+|generally\s+)?"
    r"(?:overlooked|neglected)\b",
    r"\b(?:has|have)\s+(?:not|never)\s+(?:yet\s+)?been\s+(?:\w+ly\s+)?"
    r"(?:studied|investigated|explored|examined|assessed|quantified|"
    r"evaluated|addressed|described|characteri[sz]ed|measured|estimated)\b",
    r"\bno\s+(?:published\s+|previous\s+|prior\s+|existing\s+)?"
    r"(?:study|studies|research|work)\s+(?:to\s+date\s+)?(?:has|have)\b",
    r"\blittle\s+(?:is|was)\s+known\b",
    r"\blittle\s+(?:research|attention|work)\s+(?:has|have)\b",
    r"\bfew\s+(?:studies|researchers|authors)\s+have\b",
    r"\bremains?\s+(?:largely\s+|relatively\s+|mostly\s+)?(?:unknown|"
    r"unexplored|under-?explored|unstudied|understudied)\b",
    r"\b(?:paucity|dearth|scarcity|lack)\s+of\s+(?:research|studies|"
    r"literature|work|evidence)\b",
)
# D903: a sentence that states the stake: what goes wrong, who pays, what
# is decided without the answer, or the untested assumption a decision
# rests on. Deliberately broad: the rule stays quiet when any of these is
# near the gap (precision first).
STAKE_RX = (
    r"\b(?:would|could|might|may|will|can)\s+(?:\w+\s+){0,2}(?:lead|result|"
    r"cause|bias|mislead|misdirect|undermine|underestimate|overestimate|"
    r"misallocate|miss|fail|delay|waste|cost|limit|hamper|hinder|prevent|"
    r"leave|mean|matter|affect|compromise|distort|invalidate|weaken|"
    r"jeopardi[sz]e)\w*\b",
    r"\b(?:cannot|can ?not|unable to|impossible to|difficult to|hard to)\b",
    r"\bwithout\s+(?:this|these|such|it|knowing|reliable|accurate|an?|the)\b",
    r"\b(?:limits?|limiting|hampers?|hinders?|impedes?|prevents?|"
    r"undermines?|constrains?|restricts?|compromises?|obscures?|biases|"
    r"leaves?|leaving)\b",
    r"\b(?:risks?|risking|consequences?|consequently|as a result|costly|"
    r"costs?|harms?|harmful|misinformed|misguided|blind|guesswork)\b",
    r"\b(?:depends?|depending|relies|rely|relying|rests?)\s+on\b",
    r"\bassum(?:e|es|ed|ing|ption|ptions)\b",
    r"\bif\b",
    r"\b(?:matters?|important|crucial|critical|essential|vital)\s+"
    r"(?:for|to|because|when|before)\b",
    r"\b(?:inform|informs|informing|guide|guides|guiding|decisions?|"
    r"decision-makers|policy|policies|policymakers|planners?|planning|"
    r"clinicians?|practitioners?|programmes?|programs?|interventions?|"
    r"allocation|resources?)\b",
)

# D904: "fills the gap" in a Discussion or Conclusion, a claim with no
# ruling. The gap must be a knowledge gap: a "gap in the literature", a
# "knowledge gap", or "this gap" pointing back at one. "Closes the gap" is
# a ruling and is left alone, and so is a partial or negated claim
# ("partly fills", "does not fill"), which is a ruling too.
FILL_GAP_RX = (
    r"\b(?:fill|fills|filled|filling|address|addresses|addressed|"
    r"addressing|bridge|bridges|bridged|bridging|plug|plugs|plugged)"
    r"(?:\s+in)?\s+(?:(?:this|that|these|those|such|an?|the|some\s+of\s+"
    r"the|several|current|existing|important|key|critical|significant|"
    r"major|identified)\s+){0,2}(?:(?:knowledge|research|evidence|"
    r"literature|empirical|methodological|theoretical)\s+)gaps?\b",
    r"\b(?:fill|fills|filled|filling|address|addresses|addressed|"
    r"addressing|bridge|bridges|bridged|bridging|plug|plugs|plugged)"
    r"(?:\s+in)?\s+(?:(?:this|that|these|those|such|an?|the|current|"
    r"existing|important|key|critical|significant|major)\s+){1,2}gaps?\s+"
    r"in\s+(?:the\s+|our\s+|current\s+|existing\s+)?(?:literature|"
    r"knowledge|evidence|research|understanding|field)\b",
    r"\b(?:fill|fills|filled|filling|address|addresses|addressed|"
    r"addressing|bridge|bridges|bridged|bridging|plug|plugs|plugged)"
    r"(?:\s+in)?\s+(?:this|that|these|those|such\s+a)\s+gaps?\b"
    r"(?!\s+(?:between|in\s+(?:coverage|vaccination|immunity|care|"
    r"treatment|access|services|provision|uptake|funding|supply)))",
)
# Words just before the verb that make the claim a ruling or an aim, not a
# claim that the gap is filled: "partly fills", "does not fill", "to fill".
FILL_GAP_RULING_RX = (r"\b(?:not|cannot|never|partly|partially|in part|"
                      r"only|begins? to|began to|starts? to|to|aims? to|"
                      r"aimed to|sought to|seeks? to|attempts? to|"
                      r"attempted to)\s+(?:\w+\s+)?$")

# D906: thread versus tape. A chapter of a thesis: a LaTeX \chapter, or a
# heading that says "Chapter N" (plain text, Word, Markdown). Front and back
# matter set as chapters are not chapters of the argument.
CHAPTER_HEADING_RX = (r"^\s*chapter\s+(\d+|[ivxlc]+|one|two|three|four|five|"
                      r"six|seven|eight|nine|ten)\b")
NON_CHAPTER_RX = (r"abstract|summary|acknowledg|declaration|dedicat|"
                  r"contents|list of|abbreviation|nomenclature|glossary|"
                  r"preface|foreword|publications?\b|references|"
                  r"bibliography|appendix|appendices|curriculum|vita\b|"
                  r"biograph|index\b")
# The aim of a whole thesis or one of its chapters, which the article-level
# aim signals (discourse/moves.py) do not name.
THESIS_AIM_RX = (
    r"\b(?:this|the present|my|our) (?:thesis|dissertation|chapter|"
    r"research|programme of work|body of work) (?:aims?|aimed|sets? out|"
    r"seeks?|sought|asks?|addresses|investigates?|examines?|explores?|"
    r"estimates?|tests?)\b",
    r"\b(?:the|my|our) (?:overall |overarching |primary |main )?(?:aims?|"
    r"objectives?|goals?|purpose|research questions?) of (?:this|the) "
    r"(?:thesis|dissertation|chapter|research)\b",
)
# Near-duplicate test: sets of adjacent word pairs (shingles) with a
# Jaccard overlap of at least TAPE_JACCARD, between sentences of at least
# TAPE_MIN_WORDS words. A short aim ("We estimate R.") can recur by
# coincidence; a 12-word sentence sharing 80% of its word pairs does not.
TAPE_MIN_WORDS = 12
TAPE_JACCARD = 0.8

# D905: a generic call for future research ("Further research is needed.",
# "Future work should explore this.") in a Discussion or Conclusion. The
# rule fires only when nothing in the sentence names what is still open:
# every word left after the call is generic.
FUTURE_RESEARCH_RX = (
    r"\b(?:further|future|more|additional)\s+(?:research|studies|study|"
    r"work|investigations?|analys[ie]s)\s+(?:(?:is|are|will\s+be|would\s+be|"
    r"may\s+be|might\s+be)\s+(?:\w+\s+)?(?:needed|required|warranted|"
    r"necessary|called\s+for)|(?:should|could|may|might|can|will|would|"
    r"must)\b)",
    r"\b(?:warrants?|merits?|deserves?|requires?|needs?|calls?\s+for)\s+"
    r"(?:further|more|additional)\s+(?:research|investigation|study|work|"
    r"exploration|attention)\b",
    r"\b(?:there\s+is\s+a\s+need\s+for|it\s+would\s+be\s+(?:interesting|"
    r"useful|valuable|worthwhile)\s+(?:for|to))\s+(?:further|future|more)\s+"
    r"(?:research|studies|work)\b",
)
GENERIC_FUTURE_WORDS = frozenset("""
    further future more additional research studies study work works
    investigation investigations analysis analyses exploration attention
    is are be been being will would may might could should can must need
    needs needed required warranted necessary called call calls for there it
    interesting useful valuable worthwhile also still perhaps possibly clearly
    definitely certainly therefore thus however hence finally lastly overall
    this these that those such its their our the a an them they which what
    in on of to and or with into across within from by at as about
    findings finding results result issue issues area areas topic topics
    question questions relationship relationships association associations
    observation observations aspect aspects matter matters phenomenon
    phenomena field subject direction directions avenue avenues line lines
    knowledge gap gaps understanding picture light
    other different various similar wider broader larger bigger longer new
    settings setting contexts context populations population countries
    regions places groups samples sample cohorts data datasets
    explore investigate examine address assess clarify elucidate determine
    confirm validate replicate extend fill understand study consider
    look build focus conduct conducted carry carried out implement
    implemented undertake undertaken pursue pursued shed done made
    better fully deeper improve studied investigated explored examined
    addressed assessed confirmed validated replicated extended
    we us one researchers authors recommend recommends recommended suggest
    suggests suggested propose proposes proposed encourage encouraged hope
    addition additionally moreover furthermore finally lastly conclusion
    summary nonetheless nevertheless importantly ultimately given
    limitation limitations
    """.split())

# E707: display-first openers in Results (lead with the finding instead)
FIGURE_OPENER_RX = (r"^\s*(?:Figure|Fig\.?|Table|Supplementary\s+"
                    r"(?:Figure|Table))\s+\S+\s+"
                    r"(?:shows?|presents?|displays?|illustrates?|depicts?|"
                    r"summari[sz]es?|provides?|gives?|lists?)\b")

# --- AB801: vague forward references in abstracts (Belcher/Schultz) ---------
ABSTRACT_VAGUE_RX = (r"\b(?:results?|findings?|implications?|data|outcomes?)"
                     r"\s+(?:will|shall)\s+be\s+"
                     r"(?:discussed|presented|explored|described|reported|"
                     r"examined)\b")

# --- L901: serial-summary literature-review openers (the course, unit 1) --------
LITREVIEW_FILLER = (
    r"\bthere\s+(?:are|have\s+been|is\s+a\s+growing\s+body\s+of)\s+"
    r"(?:many|several|numerous|various|a\s+number\s+of)?\s*"
    r"(?:studies|articles|papers|reports|researchers|works?)\b",
    r"\bmuch\s+research\s+has\s+been\s+(?:done|conducted|carried\s+out)\b",
    r"\bmany\s+(?:studies|researchers|authors|scholars)\s+have\s+"
    r"(?:studied|investigated|examined|explored|looked\s+at|reported)\b",
)

# --- F601: acronyms ---------------------------------------------------------
ACRONYM_ALLOWLIST = {
    # ubiquitous general/scientific
    "USA", "UK", "US", "EU", "UN", "PDF", "DOI", "URL", "ID", "AI", "IT",
    # ubiquitous biomedical/epi (assume audience knows)
    "DNA", "RNA", "HIV", "AIDS", "COVID", "SARS", "MERS", "PCR", "WHO",
    "CDC", "NHS", "NIH", "ICU", "BMI",
    # statistics reporting conventions
    "CI", "SD", "SE", "IQR", "OR", "RR", "HR", "AIC", "BIC", "MCMC",
    "ESS", "HMC", "NUTS", "GLM", "GAM", "ODE", "SIR", "SEIR", "SEIRD",
    # P31 (Q3): reporting conventions and names, not abbreviations to define
    "GDP", "UV", "ROC", "AUC",
    "BMJ", "BMC", "PLOS", "JAMA", "NEJM",          # journal names
    # currency codes (dogfooding: "SGD$10 (~USD8)")
    "SGD", "USD", "EUR", "GBP", "CNY", "JPY", "INR", "MYR", "IDR", "THB",
}

# --- Metadiscourse meter (Hyland's interactional resources; the course, unit 2) ------
# Boosters assert certainty; the hedge/booster balance is a calibration
# read-out ("confidence without cockiness" — Wellington et al.).
BOOSTER_TOKENS = {
    "clearly", "obviously", "certainly", "definitely", "undoubtedly",
    "always", "never", "must", "evidently", "indeed", "conclusively",
    "definitively", "unquestionably", "demonstrably", "surely",
    "established", "establishes", "proven", "proves",
}
SELF_MENTION_TOKENS = {"we", "our", "us", "i", "my"}

# --- -ise in every English -------------------------------------------------
# Words spelt -ise in American and British alike, so an -ize form is a
# misspelling, never a variant ("surprize", "advize"). Stems, as prefixes of
# every inflection. The standard list of Oxford and Merriam-Webster style.
ISE_ONLY = (
    "advertis", "advis", "appris", "chastis", "circumcis", "compris",
    "compromis", "despis", "devis", "disguis", "enterpris", "excis",
    "exercis", "franchis", "improvis", "incis", "merchandis", "premis",
    "revis", "supervis", "surmis", "surpris", "televis",
)

# --- W210: variant consistency ("one term, one meaning") --------------------
# Curated exact pairs only — algorithmic UK/US transforms create false pairs
# (four/for, filling/filing). Extend freely.
CONSISTENCY_PAIRS = (
    ("modelling", "modeling"), ("modelled", "modeled"),
    ("behaviour", "behavior"), ("behaviours", "behaviors"),
    ("analyse", "analyze"), ("analysed", "analyzed"),
    ("analysing", "analyzing"), ("analyses", "analyzes"),
    ("organisation", "organization"), ("organisations", "organizations"),
    ("optimisation", "optimization"), ("optimise", "optimize"),
    ("optimised", "optimized"),
    ("parameterisation", "parameterization"),
    ("hospitalisation", "hospitalization"),
    ("hospitalisations", "hospitalizations"),
    ("colour", "color"), ("colours", "colors"),
    ("labelled", "labeled"), ("labelling", "labeling"),
    ("centre", "center"), ("centres", "centers"),
    ("standardised", "standardized"), ("standardise", "standardize"),
    ("characterised", "characterized"), ("characterise", "characterize"),
    ("summarised", "summarized"), ("summarise", "summarize"),
    ("generalisability", "generalizability"),
    ("immunisation", "immunization"), ("randomised", "randomized"),
    ("categorised", "categorized"), ("visualisation", "visualization"),
    ("neighbourhood", "neighborhood"), ("neighbourhoods", "neighborhoods"),
    ("favourable", "favorable"), ("favour", "favor"),
)

# --- S002: real-word confusions ---------------------------------------------
# Real words a spell checker cannot catch, because both are spelt correctly.
# Each entry is (typed, probably meant), in the direction the slip is made:
# "principle component" is a slip, "the school principals" is not, so only
# principle → principal is listed. Chosen for scientific writing, where
# "casual" for "causal" or "trail" for "trial" changes the meaning. S002
# speaks only when the neighbouring words make the other word far more
# likely (rules_spelling.s002_confusion).
# Left to LanguageTool's grammar rules, because word pairs alone misjudge
# them on published prose (2026-10-14, eight theses + 115 PMC articles):
# than/then ("rather than consider") and from/form ("samples form the
# posterior").
CONFUSIONS = (
    ("affect", "effect"), ("effect", "affect"),
    ("affects", "effects"), ("effects", "affects"),
    ("effected", "affected"),
    ("principle", "principal"),
    ("complement", "compliment"), ("compliment", "complement"),
    ("complementary", "complimentary"), ("complimentary", "complementary"),
    ("discreet", "discrete"),
    ("dependant", "dependent"),
    ("weather", "whether"),
    ("cite", "site"), ("cites", "sites"),
    ("lead", "led"),
    ("insure", "ensure"),
    ("loose", "lose"),
    ("adverse", "averse"), ("averse", "adverse"),
    ("precede", "proceed"), ("proceed", "precede"),
    ("preceded", "proceeded"), ("proceeded", "preceded"),
    ("illicit", "elicit"), ("elicit", "illicit"),
    ("casual", "causal"),
    ("trail", "trial"), ("trails", "trials"),
    ("statue", "statute"),
    ("prostrate", "prostate"),
    ("martial", "marital"),
    ("rational", "rationale"),
    ("breathe", "breath"),
    ("quiet", "quite"),
)


# --- Researchly grammar notes (R6, 2026-10-15; docs/grammar-notes.md) -------
# Lists written for Researchly from general knowledge of English grammar.
# Each one is deliberately short: a word earns its place only if the rule is
# right for it in every context a research paper is likely to put it in.

# GN101: nouns for a group of people that American English treats as one
# thing ("the committee was"), where British, Australian and Indian English
# may also treat them as the people in it ("the committee were").
COLLECTIVE_NOUNS = frozenset("""
team committee government panel board council jury cohort consortium
family company audience ministry department public group population
""".split())

# GN201: head nouns that name one quantity or one thing even when an
# "of" phrase full of plurals follows ("the proportion of cases was").
# Left out on purpose, because they agree with what follows them in
# careful writing everywhere: majority, minority, half, rest, remainder,
# bulk, range, variety, series, set, group, total, lot, couple, kind, type.
AGREEMENT_HEADS = frozenset("""
proportion percentage fraction share number rate risk incidence prevalence
probability likelihood mean median average sum distribution frequency
ratio level concentration duration size magnitude variance accuracy
sensitivity specificity performance quality effect impact estimate aim
purpose goal objective timing severity burden cost age
""".split())
# ("length" is left out: "length of stay" is a term that is itself a
# modifier, as in "length of stay statistics were".)
# Of those, the ones that take a plural verb after "a" ("a proportion of
# patients were", "an average of 40 samples were taken"): the writer means
# the patients or the samples, not the proportion or the average.
AGREEMENT_HEADS_NEED_THE = frozenset({
    "proportion", "percentage", "fraction", "share", "number", "average",
    "mean", "median", "sum"})
# Pronoun heads that are singular however plural their "of" phrase is
# ("each of the models was"). "none", "neither" and "either" are left out:
# a plural verb after them is accepted in careful writing.
AGREEMENT_PRONOUN_HEADS = frozenset({"each", "one"})

# GN201, GN202, GN203, GN101: a plural verb form and its singular.
PLURAL_TO_SINGULAR_VERB = {"are": "is", "were": "was", "have": "has",
                           "do": "does"}
SINGULAR_TO_PLURAL_VERB = {v: k for k, v in PLURAL_TO_SINGULAR_VERB.items()}

# GN205: participles that open a sentence without needing a doer, because
# they work as prepositions ("Assuming a fixed interval, ...", "Given
# these counts, ...") or set phrases ("Starting from April, ..."), and the
# mathematician's "Taking X to denote ...", "Letting n be ...".
DANGLING_OK = frozenset("""
assuming considering given including excluding regarding concerning
following according depending notwithstanding provided providing owing
barring speaking judging granted being having starting beginning taking
letting denoting writing
""".split())
# Prepositions that can carry an -ing opener ("After fitting the model, ...").
DANGLING_PREPOSITIONS = frozenset({
    "after", "before", "by", "on", "upon", "when", "while", "whilst",
    "through"})

# GN206: abbreviations, how they are said, and so whether they take "a" or
# "an". The article follows the first SOUND, not the first letter: MCMC is
# said "em-see-em-see" (an), NATO "nay-toe" (a), UK "you-kay" (a).
# Abbreviations said two ways in published work are left out on purpose:
# SIR and SEIR ("ess-eye-ar" or "sir", "seer"), MAP, LOO, WAIC, SQL; and
# SE, which is "ess-ee" as a standard error but "south-east" in "SE Asia".
ABBREVIATION_ARTICLE = {
    # said letter by letter, first letter F, H, L, M, N, R, S or X
    "MCMC": ("an", "em-see-em-see"), "MRI": ("an", "em-ar-eye"),
    "HIV": ("an", "aitch-eye-vee"), "HPV": ("an", "aitch-pee-vee"),
    "RCT": ("an", "ar-see-tee"), "LMIC": ("an", "el-em-eye-see"),
    "NGO": ("an", "en-gee-oh"), "SD": ("an", "ess-dee"),
    "FDA": ("an", "ef-dee-ay"),
    "MSM": ("an", "em-ess-em"), "NHS": ("an", "en-aitch-ess"),
    "RNA": ("an", "ar-en-ay"), "mRNA": ("an", "em-ar-en-ay"),
    "LSTM": ("an", "el-ess-tee-em"), "MLE": ("an", "em-el-ee"),
    "NPI": ("an", "en-pee-eye"), "HR": ("an", "aitch-ar"),
    "RR": ("an", "ar-ar"), "SMR": ("an", "ess-em-ar"),
    "FOI": ("an", "ef-oh-eye"), "HMC": ("an", "aitch-em-see"),
    "SVM": ("an", "ess-vee-em"), "MSE": ("an", "em-ess-ee"),
    "RMSE": ("an", "ar-em-ess-ee"), "MAE": ("an", "em-ay-ee"),
    "R0": ("an", "ar-nought"), "Rt": ("an", "ar-tee"),
    "SDE": ("an", "ess-dee-ee"), "HDI": ("an", "aitch-dee-eye"),
    "SNR": ("an", "ess-en-ar"), "NIH": ("an", "en-eye-aitch"),
    "FMD": ("an", "ef-em-dee"), "STI": ("an", "ess-tee-eye"),
    "MDR": ("an", "em-dee-ar"), "LTBI": ("an", "el-tee-bee-eye"),
    "NTD": ("an", "en-tee-dee"),
    # said as a word, or starting with a "you" or "double-you" sound
    "UK": ("a", "you-kay"), "US": ("a", "you-ess"),
    "USA": ("a", "you-ess-ay"), "UN": ("a", "you-en"),
    "URL": ("a", "you-ar-el"), "UTI": ("a", "you-tee-eye"),
    "UV": ("a", "you-vee"), "WHO": ("a", "double-you-aitch-oh"),
    "SNP": ("a", "snip"), "NATO": ("a", "nay-toe"),
    "SARS": ("a", "sars"), "MERS": ("a", "murz"),
    "NICE": ("a", "nice"), "LASSO": ("a", "lasso"),
    "NASA": ("a", "nassa"), "UNICEF": ("a", "you-ni-sef"),
    "LOESS": ("a", "low-ess"), "HEPA": ("a", "heppa"),
}

# GN102: the word after "different to" that makes it about how something
# looks to someone ("different to the reader"), which every English allows.
PERCEIVERS = frozenset("""
me us you him her them reader readers observer observers clinicians
clinician patients patient participants respondents people users eye eyes
""".split())

# GN105: what follows "was fit"/"were fit" when it is the past participle
# of fitting a model ("were fit to the data", "was fit using a sampler").
FIT_FOLLOWERS = frozenset({
    "to", "using", "with", "by", "in", "on", "separately", "independently",
    "jointly", "simultaneously", "via", "within", "across", "against"})

# GN107: month names for dates in prose.
MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")


# --- Language detection (2026-10-14; reading.py) --------------------------
# Researchly checks English. A paragraph in another language (a thesis's
# second abstract, a quotation) is masked rather than flagged word by word.
# Each list holds a language's commonest function words, leaving out those
# that are also English words ("a", "in", "do", "die", "me", "son").
ENGLISH_FUNCTION_WORDS = frozenset("""
the of and to in is that for are was were with as on by this be from at
or an which have has been not their these it its we our also than can
between but more such into other both may each when where while there
""".split())
OTHER_FUNCTION_WORDS = {
    "Spanish": frozenset("""
        el los las del por para una con que se lo como pero su sus muy
        está están entre sobre también fue fueron según desde hasta este
        esta estos estas ser son""".split()),
    "French": frozenset("""
        le les des du est une et dans pour avec que qui sur pas plus par
        ont été sont cette ces aux leur leurs mais ou entre selon nous
        être""".split()),
    "German": frozenset("""
        der das und ist nicht mit sich den dem des ein eine einer auf für
        von zu wird werden wurde wurden auch bei aus oder nach über sind
        zwischen""".split()),
    "Portuguese": frozenset("""
        os das dos uma com não para pelo pela como mais foi foram são
        está estão entre sobre também seu sua seus suas pelos pelas
        ao aos""".split()),
    "Italian": frozenset("""
        il gli della delle degli dei che è una con non per sono stato
        stati nella nelle anche tra fra sul sulla questo questa
        essere""".split()),
    "Dutch": frozenset("""
        het een van en zijn niet met voor op dat ook bij werd worden
        wordt naar uit tussen deze dit onder""".split()),
}
