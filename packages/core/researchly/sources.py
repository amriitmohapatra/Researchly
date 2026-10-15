"""Short source codes -> full citations a student can look up (CLAUDE.md #6).

Rules declare compact codes (`source="§4"`, `"lecture"`, `"§6+lecture"`) because
they are easy to audit next to the rule. Users must never see the code
alone: "§4" means nothing outside this repository. The rule registry expands
every code through `cite()` at registration, so every surface (CLI, Word,
LSP, web) shows the same full citation.

An unknown code raises KeyError at import time: a rule with an unexplained
source should fail loudly, not ship. Add the citation here, and its
provenance entry in docs/knowledge-base.md, in the same change.

Citations name works; they never quote them (PLAN.md S0: no third-party
text in shippable code).
"""

from __future__ import annotations

GUIDE = "The Craft of Scientific Writing (Researchly's founding guide)"

# Section numbers and titles of the guide, as headed in
# The-Craft-of-Scientific-Writing.md (the owner's own text).
GUIDE_SECTIONS = {
    "2": "Structure from the top down: the paper is a story",
    "3": "The Introduction, move by move",
    "4": "Warranting your arguments",
    "5.1": "The paragraph",
    "5.2": "The sentence: Gopen & Swan's reader-expectation principles",
    "5.2.1": "Keep subject and verb close together (after Gopen & Swan)",
    "5.2.2": "Put the emphasis at the end, the stress position (after Gopen & Swan)",
    "5.2.3": "Put whose story it is in the topic position (after Gopen & Swan)",
    "5.2.4": "Put the action in the verb (after Gopen & Swan)",
    "6": "Language and tone",
    "8": "A practical workflow to beat the blank page",
    "9.1": "Write for a reader who lacks one of your fields",
    "9.3": "Uncertainty is not a caveat, it is the finding",
    "9.2": "Equations are sentences — make them grammatical",
    "9.4": "A model is an argument, not an oracle",
    "9.5": "Reproducibility is part of the writing",
    "7.3": "Tag the three funnel moves and the argument spine",
    "9.7": "Figures are arguments too",
    "9.8": "Translate for the decision-maker",
}

# What a user sees for advice the owner learned in training (a lecture and
# a university course). The course and lecturer are credited only in the
# internal provenance map (docs/knowledge-base.md): naming them to the
# public could read as their endorsement, which is theirs to give (owner
# decision, 2026-10-08). The codes stay so provenance is traceable.
LEARNINGS = "Amriit's learnings from scientific-writing training (Researchly notes)"

WORKS = {
    # The lecture and the course's units 1 and 2; docs/knowledge-base.md
    # §1-§3 names them (private provenance, never shipped by name).
    "lecture": LEARNINGS,
    "course-U1": LEARNINGS,
    "course-U2": LEARNINGS,
    # A thesis-writing workshop on the research gap (2026-10-14);
    # docs/knowledge-base.md §13 names it (private provenance).
    "workshop-S2": LEARNINGS,
    "Alvesson2011": ('M. Alvesson and J. Sandberg (2011), "Generating '
                     'research questions through problematization", '
                     "Academy of Management Review 36(2)"),
    "Sandberg2011": ('J. Sandberg and M. Alvesson (2011), "Ways of '
                     'constructing research questions: gap-spotting or '
                     'problematization?", Organization 18(1)'),
    "Bunton2005": ('D. Bunton (2005), "The structure of PhD conclusion '
                   'chapters", Journal of English for Academic Purposes '
                   "4(3)"),
    "Kwan2006": ('B. S. C. Kwan (2006), "The schematic structure of '
                 'literature reviews in doctoral theses of applied '
                 'linguistics", English for Specific Purposes 25(1)'),
    "Lim2006": ('J. M. H. Lim (2006), "Method sections of management '
                'research articles: a pedagogically motivated qualitative '
                'study", English for Specific Purposes 25(3)'),
    "Shehzad": 'W. Shehzad (2008), "Move two: establishing a niche"',
    # Genre-native units (Codex review #4, 2026-10-15): the parts of a
    # policy brief, and the comment-and-reply unit of a response letter.
    "YoungQuinn2002": ("E. Young and L. Quinn (2002), Writing Effective "
                       "Public Policy Papers: A Guide for Policy Advisers "
                       "in Central and Eastern Europe, Open Society "
                       "Institute (the parts of a policy brief)"),
    "Noble2017": ('W. S. Noble (2017), "Ten simple rules for writing a '
                  'response to reviewers", PLOS Computational Biology '
                  "13(10)"),
    "Swales": ("J. M. Swales (1990), Genre Analysis, on the three moves "
               "of a research introduction"),
    "Toulmin": ("S. E. Toulmin (1958), The Uses of Argument, Cambridge "
                "University Press (claim, grounds, warrant)"),
    "STROBE": ("E. von Elm et al. (2007), the STROBE statement for "
               "reporting observational studies in epidemiology"),
    "CONSORT": ("K. F. Schulz, D. G. Altman and D. Moher (2010), the "
                "CONSORT 2010 statement for reporting randomised trials"),
    "PRISMA": ("M. J. Page et al. (2021), the PRISMA 2020 statement for "
               "reporting systematic reviews"),
    "EPIFORGE": ("S. Pollett et al. (2021), the EPIFORGE 2020 guidelines "
                 "for reporting epidemic forecasting and prediction "
                 "research"),
    "WW": ("M. Wallace & A. Wray (2016), Critical Reading and Writing for "
           "Postgraduates, 3rd ed., SAGE"),
    "LanguageTool": "LanguageTool, open-source grammar checker",
    "symspellpy": ("SymSpell spelling engine with Researchly's scientific "
                   "lexicon"),
    "local GEC": "Researchly learned-correction tier (local model)",
    "SI": ("BIPM, The International System of Units (SI Brochure), "
           "9th ed., on writing a number with its unit"),
    "AMA": ("AMA Manual of Style, 11th ed., on numbers at the start of a "
            "sentence"),
    "Word": ("Microsoft Word documentation on heading styles, which build "
             "the navigation pane and the table of contents"),
    "ICMJE": ("International Committee of Medical Journal Editors, "
              "Recommendations for the Conduct, Reporting, Editing, and "
              "Publication of Scholarly Work in Medical Journals "
              "(tables and figures)"),
    "VarCon": ("K. Atkinson, VarCon: variant spellings of American, British, "
               "Canadian and Australian English (wordlist.aspell.net)"),
    "Mays1991": ("E. Mays, F. J. Damerau and R. L. Mercer (1991), Context "
                 "based spelling correction, Information Processing & "
                 "Management 27(5)"),
    "Swan": ("M. Swan (2016), Practical English Usage, 4th ed., Oxford "
             "University Press, on uncountable nouns"),
    # Rules written for Researchly at build time from general knowledge of
    # English grammar (ADR-11, owner 2026-10-15); docs/grammar-notes.md is
    # the source document, with further reading at its end.
    "rgn": ("Researchly grammar notes: grammar and regional usage written "
            "for Researchly in its own words, with further reading "
            "(docs/grammar-notes.md in the Researchly repository)"),
}


def _one(code: str) -> str:
    code = code.strip()
    if code.startswith("§"):
        # The section is named, never numbered: a reader outside this
        # project cannot look up "§6" (CLAUDE.md #6; the owner's P35
        # feedback). The code keeps the number for provenance.
        number = code[1:]
        title = GUIDE_SECTIONS[number]
        return f"{GUIDE}: {title}"
    return WORKS[code]


def cite(code: str) -> str:
    """Full citation for a rule's source code. Raises KeyError if unknown.

    Several sections of the guide are cited once, by the guide's name and
    then each section's title in quotes, where the first of them stood:
    repeating the guide's long name read as clutter on a source line.
    """
    seen: list[str] = []
    titles: list[str] = []
    for part in code.split("+"):
        part = part.strip()
        if part.startswith("§"):
            title = GUIDE_SECTIONS[part[1:]]
            if title not in titles:
                titles.append(title)
            if GUIDE not in seen:
                seen.append(GUIDE)
            continue
        c = _one(part)
        if c not in seen:
            seen.append(c)
    if titles:
        if len(titles) == 1:
            guide = f"{GUIDE}: {titles[0]}"
        else:
            quoted = [f"\u201c{t}\u201d" for t in titles]
            guide = f"{GUIDE}: {', '.join(quoted[:-1])} and {quoted[-1]}"
        seen[seen.index(GUIDE)] = guide
    return "; ".join(seen)
