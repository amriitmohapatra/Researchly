"""What in a plain text is not English prose: pasted code, inline maths,
other languages (2026-10-14; Codex review #5 and the English-only notice).

Plain text and Word documents carry no markup, so code pasted from R or
Stan, maths typed as ``$\\beta_1$`` and a paragraph in Portuguese all
reached the rules as prose: "rnorm" was a typo, "<-" a stray symbol, every
Portuguese word unknown. These finders return the spans to mask. Each is
conservative (precision over recall, CLAUDE.md #5): a line is code only if
it looks like nothing else, and a paragraph is another language only when
its function words say so clearly.
"""

from __future__ import annotations

import re

from . import lexicons as lx

# --- code ----------------------------------------------------------------------

# Lines only code looks like.
_CODE_LINES = [re.compile(p) for p in (
    # assignment in R: x <- ..., df$y <<- ...
    r"^\s*[A-Za-z_.][\w.$@\[\]\"']*\s*(?:<-|<<-)\s*\S",
    # statements that open code in R, Python, Stan or a shell
    r"^\s*(?:library|require|import|source|setwd|install\.packages)\s*\(",
    r"^\s*(?:from\s+[\w.]+\s+import|import\s+[\w.]+(?:\s+as\s+\w+)?\s*$)",
    r"^\s*(?:def|class)\s+\w+\s*[(:]",
    r"^\s*(?:for|if|while)\s*\(.*\)\s*\{?\s*$",
    r"^\s*\}?\s*else\s*\{\s*$",
    r"^\s*[}\])]+\s*[;,)]*\s*$",
    # Stan blocks and declarations
    r"^\s*(?:functions|data|transformed data|parameters|transformed "
    r"parameters|model|generated quantities)\s*\{\s*$",
    r"^\s*(?:real|int|vector|row_vector|matrix|array|simplex|ordered|"
    r"cov_matrix|corr_matrix)\b(?:<[^>]*>)?(?:\[[^\]]*\])?\s+\w+[^.]*;\s*$",
    # console output and prompts
    r"^\s*(?:#>|>>>|\$ )\s*\S",
)]
# Lines code usually looks like, but a terse line of prose might too
# ("We used three models (A, B and C);"): code only when few words.
_CODE_LIKE = [re.compile(p) for p in (
    # a whole line that is one call or an assignment of one: plot(x, y)
    r"^\s*(?:[A-Za-z_][\w.]*\s*=\s*)?[A-Za-z_][\w.]*\((?:[^()]|\([^()]*\))*\)"
    r"\s*;?\s*$",
    # pipes, and a statement ending in ; or {
    r"(?:%>%|\|>)\s*$",
    r"^[^.!?]*\)\s*[;{]\s*$",
)]
_FENCE = re.compile(r"^\s*```", re.M)


def _prose_like(line: str) -> bool:
    """A sentence, whatever the patterns say: many words, few symbols, a
    full stop at the end."""
    words = re.findall(r"[A-Za-z]{2,}", line)
    symbols = len(re.findall(r"[{}()\[\]<>=;$#%|]", line))
    return len(words) >= 8 and symbols <= 2 and line.rstrip().endswith(".")


def _wordy(line: str) -> int:
    """Words of three or more letters outside brackets: prose has many."""
    outside = re.sub(r"\([^()]*\)", "()", line)
    return len(re.findall(r"(?<![\w.$])[A-Za-z]{3,}(?![\w(.$])", outside))


def code_spans(text: str) -> list[tuple[int, int]]:
    """Lines of pasted code, and fenced blocks pasted from Markdown."""
    spans: list[tuple[int, int]] = []
    fences = [m.start() for m in _FENCE.finditer(text)]
    for a, b in zip(fences[::2], fences[1::2]):
        end = text.find("\n", b)
        spans.append((a, len(text) if end < 0 else end))
    for m in re.finditer(r"[^\n]+", text):
        line = m.group()
        if any(a <= m.start() < b for a, b in spans):
            continue
        if _prose_like(line):
            continue
        if any(p.search(line) for p in _CODE_LINES) or (
                _wordy(line) <= 1 and any(p.search(line) for p in _CODE_LIKE)):
            spans.append((m.start(), m.end()))
    return sorted(spans)


# --- inline maths and code ---------------------------------------------------------

_INLINE = [re.compile(p) for p in (
    # $...$ with something only maths has: a backslash, ^, _ or braces.
    # "$5 to $10" has none of them and stays prose.
    r"(?<![\\$\w])\$(?=[^\s$])[^$\n]{0,200}?[\\^_{}][^$\n]{0,200}?\$(?!\w)",
    r"\\\((?:[^\n]){1,300}?\\\)",
    r"\\\[(?:.|\n){1,2000}?\\\]",
    r"`[^`\n]{1,200}`",
)]


def inline_spans(text: str) -> list[tuple[int, int]]:
    """Inline maths ($\\beta_1$, \\(x\\)) and `code` typed into plain text."""
    spans = []
    for pat in _INLINE:
        spans += [(m.start(), m.end()) for m in pat.finditer(text)]
    return sorted(spans)


# --- other languages -----------------------------------------------------------------

MIN_WORDS = 12


def paragraph_language(text: str) -> str | None:
    """None for English (or too short to tell); otherwise the language the
    paragraph is in: "Spanish", ..., or "another script"."""
    letters = [c for c in text if c.isalpha()]
    if len(letters) >= 40:
        latin = sum(1 for c in letters if c < "ɐ")
        if latin < 0.5 * len(letters):
            return "another script"
    words = [w.lower() for w in re.findall(r"[^\W\d_]+", text)]
    if len(words) < MIN_WORDS:
        return None
    english = sum(w in lx.ENGLISH_FUNCTION_WORDS for w in words) / len(words)
    best, share = None, 0.0
    for lang, vocab in lx.OTHER_FUNCTION_WORDS.items():
        s = sum(w in vocab for w in words) / len(words)
        if s > share:
            best, share = lang, s
    if share >= 0.12 and share >= 3 * english:
        return best
    return None


def foreign_spans(text: str) -> list[tuple[int, int, str]]:
    """Paragraphs not in English: (start, end, language)."""
    out = []
    for m in re.finditer(r"[^\n]+(?:\n[^\n]+)*", text):
        lang = paragraph_language(m.group())
        if lang:
            out.append((m.start(), m.end(), lang))
    return out


def language_notice(text: str, foreign: list[tuple[int, int, str]]) -> str:
    """The English-only notice, when it applies: "" otherwise."""
    if not foreign:
        return ""
    # `text` is already masked: code and maths are blanks, not English
    other = sum(len(text[a:b].split()) for a, b, _ in foreign)
    total = len(text.split()) or 1
    langs = sorted({lang for _, _, lang in foreign})
    named = ", ".join(langs)
    if other >= 0.6 * total:
        return (f"This text does not look like English ({named}). Researchly "
                "checks English only, so it was not checked.")
    n = len(foreign)
    return (f"{n} paragraph{'s' if n != 1 else ''} not in English ({named}) "
            f"{'were' if n != 1 else 'was'} left unchecked: Researchly checks "
            "English only.")
