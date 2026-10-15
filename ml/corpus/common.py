"""Shared plumbing for the S5a open-access corpus (PLAN.md S5a, ml/corpus/SPEC.md).

Stdlib only (defusedxml when installed), Python 3.10. Nothing here writes
article text into the repository: the cache directory must be outside it
(`outside_repo`), and the manifest holds identifiers, licences, disciplines,
splits, counts and hashes only (`MANIFEST_FIELDS`; `check_manifest_row`
refuses anything else).

Licence at intake, read from the article's OWN JATS ``<permissions>`` block
(the search engine's licence field is only a hint):

    CC BY (any version) / CC0       -> use "train"  (trainable; may ship a model)
    CC BY-NC*, CC BY-ND, CC BY-SA   -> use "eval"   (evaluation only)
    none, unclear, or conflicting   -> dropped      (never enters the manifest)
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / "manifest.jsonl"
REGISTRY_TRAIN = "s5a-oa-corpus-cc-by"
REGISTRY_EVAL = "s5a-oa-corpus-nc-eval"

# Discipline vocabulary: the same one ml/realdocs/manifest.yaml uses.
DISCIPLINES = (
    "epidemiology", "public-health", "clinical-medicine", "molecular-biology",
    "ecology-evolution", "physical-earth-sciences", "engineering",
    "computational-statistics", "social-sciences", "humanities",
)

USES = {
    "train": ["private_eval", "ci_eval", "train_experimental", "ship_model"],
    "eval": ["private_eval", "ci_eval"],
}

# Every key a manifest row may carry. No titles, abstracts, author names or
# any other prose: a DOI or PMCID is enough to find (and attribute) an article.
MANIFEST_FIELDS = (
    "id", "pmcid", "pmid", "doi", "journal", "year", "discipline", "licence",
    "licence_evidence", "licence_checked", "use", "permitted_use",
    "registry", "split", "xml_sha256", "body_sha256", "words", "paragraphs",
    "sections", "structured_abstract", "abstract_sections",
)


def default_cache() -> Path:
    """Where full texts live: $RESEARCHLY_CORPUS_CACHE, else
    ~/.researchly/corpus (the owner's machine), else the system temp dir."""
    env = os.environ.get("RESEARCHLY_CORPUS_CACHE")
    if env:
        return Path(env)
    home = Path.home()
    if home.exists():
        return home / ".researchly" / "corpus"
    return Path(tempfile.gettempdir()) / "researchly-corpus"


def outside_repo(path: Path) -> Path:
    """Refuse a cache inside the repository, so no full text is committed."""
    p = Path(path).resolve()
    if p == REPO or REPO in p.parents:
        raise ValueError(f"{p} is inside the repository; full texts must "
                         "live outside it (pass --cache)")
    return p


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- licences -----------------------------------------------------------------

_CC_URL = re.compile(
    r"creativecommons\.org/licen[cs]es/(by(?:-nc)?(?:-nd|-sa)?)/(\d(?:\.\d)?)",
    re.I)
_CC0_URL = re.compile(r"creativecommons\.org/publicdomain/zero/", re.I)
_STATEMENT = re.compile(
    r"Creative\s+Commons\s+(?:CC[\s-]*)?(Attribution(?:[\s-]+(?:Non-?Commercial|"
    r"No-?Deriv(?:atives|s|ative)?|Share-?Alike))*)(?:[\s-]+(\d\.\d))?",
    re.I)
# Short form, e.g. Elsevier's "This is an open access article under the CC BY
# license" or "under the CC BY-NC-ND 4.0 license".
_SHORT = re.compile(r"\bCC[\s-]?BY((?:-NC)?(?:-ND|-SA)?)(?:\s+(\d\.\d))?\s+licen[cs]e",
                    re.I)
# PLOS's standard wording, unversioned; PLOS's content-licence policy makes
# it CC BY 4.0 (https://journals.plos.org/plosone/s/content-license).
_PLOS = re.compile(r"distributed\s+under\s+the\s+terms\s+of\s+the\s+Creative"
                   r"\s+Commons\s+Attribution\s+License", re.I)
_CC0_STATEMENT = re.compile(r"Creative\s+Commons\s+(?:CC0|Zero|public\s+domain"
                            r"\s+dedication)", re.I)
_DATA_WAIVER = re.compile(
    r"(?:The\s+)?Creative\s+Commons\s+Public\s+Domain\s+Dedication\s+waiver"
    r".{0,300}?applies\s+to\s+the\s+data[^<]{0,200}?(?:\.\s|\.<|$)",
    re.I | re.S)


def _code_from_statement(words: str) -> str:
    w = words.lower().replace(" ", "-")
    code = "by"
    if "commercial" in w:
        code += "-nc"
    if "deriv" in w:
        code += "-nd"
    if "share" in w:
        code += "-sa"
    return code


def licence_of(xml: bytes) -> tuple:
    """(SPDX id or None, use "train" | "eval" | None, evidence) from the
    article's own <permissions>. None: dropped (absent, unclear, or two
    different licences named)."""
    text = xml.decode("utf-8", "replace")
    start = text.find("<permissions")
    end = text.find("</permissions>", start)
    block = text[start:end] if start >= 0 and end > start else ""
    if not block:
        return None, None, "no <permissions> element"
    # Springer Nature / BMC blocks license the article CC BY and add "The
    # Creative Commons Public Domain Dedication waiver (…/zero/1.0/) applies
    # to the data made available in this article": that CC0 is about the
    # data, not the text, so that clause is removed before reading.
    block = _DATA_WAIVER.sub(" ", block)
    found = {}
    for m in _CC_URL.finditer(block):
        code, ver = m.group(1).lower(), m.group(2)
        ver = ver if "." in ver else ver + ".0"
        found[code] = (ver, f"licence URL creativecommons.org/licenses/"
                            f"{code}/{m.group(2)}")
    if _CC0_URL.search(block) or _CC0_STATEMENT.search(block):
        found["cc0"] = ("1.0", "CC0 (publicdomain/zero)")
    if not found:
        for m in _STATEMENT.finditer(block):
            code = _code_from_statement(m.group(1))
            found[code] = (m.group(2) or "", "statement: Creative Commons "
                           + re.sub(r"\s+", " ", m.group(1)) + " License")
        for m in _SHORT.finditer(block):
            code = "by" + (m.group(1) or "").lower()
            if code in found and found[code][0]:
                continue                     # a versioned statement wins
            found[code] = (m.group(2) or "", "statement: CC BY"
                           + (m.group(1) or "").upper() + " license")
    if not found:
        return None, None, "no Creative Commons licence named"
    if len(found) > 1:
        return None, None, "conflicting licences: " + ", ".join(sorted(found))
    code, (ver, evidence) = next(iter(found.items()))
    if code == "cc0":
        return "CC0-1.0", "train", evidence
    if not ver:
        if code == "by" and _PLOS.search(block):
            ver = "4.0"
            evidence += " (PLOS wording, unversioned; 4.0 per PLOS's policy)"
        else:
            # Every CC BY version allows reuse with attribution, and every NC
            # one forbids commercial use, so the use class is clear even
            # though the version is not; the id says so.
            ver = "unversioned"
    spdx = "CC-" + code.upper() + "-" + ver
    return spdx, ("train" if code == "by" else "eval"), evidence


# --- JATS -----------------------------------------------------------------------

def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _text(el) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def parse_xml(xml: bytes):
    """The <article> root, parsed without entities or external references."""
    try:
        import defusedxml.ElementTree as ET
    except ImportError:              # stdlib expat: no external entities,
        import xml.etree.ElementTree as ET   # billion-laughs guarded (3.7.1+)
    root = ET.fromstring(xml)
    if _local(root.tag) != "article":
        raise ValueError(f"root is <{_local(root.tag)}>, not <article>")
    return root


_SKIP_IN_P = {"xref", "fn", "table-wrap", "fig", "disp-formula",
              "inline-formula", "graphic", "media", "supplementary-material"}


def para_text(p) -> str:
    """A paragraph's prose: citations, footnotes, figures and maths dropped
    (they break the sentence for a classifier and add no rhetorical cue)."""
    out = []

    def walk(el):
        if el.text and _local(el.tag) not in _SKIP_IN_P:
            out.append(el.text)
        for c in el:
            if _local(c.tag) not in _SKIP_IN_P:
                walk(c)
            if c.tail:
                out.append(c.tail)

    walk(p)
    s = re.sub(r"\s+", " ", "".join(out)).strip()
    s = re.sub(r"\s*[\[(]\s*[,;–\-\s]*[\])]", "", s)     # emptied "[ , ]"
    s = re.sub(r"\s+([,.;:])", r"\1", s)
    return s


def article_meta(root) -> dict:
    meta = {"pmcid": "", "pmid": "", "doi": "", "journal": "", "year": ""}
    title = ""
    for el in root.iter():
        t = _local(el.tag)
        if t == "article-id":
            kind = el.attrib.get("pub-id-type", "")
            val = (el.text or "").strip()
            if kind in ("pmc", "pmcid") and val and not meta["pmcid"]:
                meta["pmcid"] = val if val.startswith("PMC") else "PMC" + val
            elif kind == "pmid" and not meta["pmid"]:
                meta["pmid"] = val
            elif kind == "doi" and not meta["doi"]:
                meta["doi"] = val.lower()
        elif t == "journal-id" and el.attrib.get("journal-id-type") in (
                "nlm-ta", "iso-abbrev") and (el.text or "").strip():
            # nlm-ta preferred; Springer titles often carry only iso-abbrev
            if not meta["journal"] or \
                    el.attrib.get("journal-id-type") == "nlm-ta":
                meta["journal"] = el.text.strip()
        elif t == "journal-title" and not title:
            title = _text(el)
        elif t == "pub-date" and not meta["year"]:
            for c in el:
                if _local(c.tag) == "year" and (c.text or "").strip():
                    meta["year"] = c.text.strip()
    # some publishers' records carry neither id, only the full title
    meta["journal"] = meta["journal"] or title
    return meta


def abstract_sections(root) -> list:
    """[(heading, [paragraph text, ...]), ...] for the main abstract's
    <sec> children; [] if the abstract is unstructured."""
    meta = None
    for el in root.iter():
        if _local(el.tag) == "article-meta":
            meta = el
            break
    if meta is None:
        return []
    abstracts = [a for a in meta if _local(a.tag) == "abstract"]
    plain = [a for a in abstracts if not a.attrib.get("abstract-type")]
    chosen = (plain or abstracts)[:1]
    out = []
    for a in chosen:
        for sec in a:
            if _local(sec.tag) != "sec":
                continue
            title = ""
            paras = []
            for c in sec:
                if _local(c.tag) == "title":
                    title = _text(c)
                elif _local(c.tag) == "p":
                    t = para_text(c)
                    if t:
                        paras.append(t)
            if title and paras:
                out.append((title, paras))
    return out


def body_sections(root) -> list:
    """[(top-level heading, [paragraph text, ...]), ...] for the body.
    Nested <sec> paragraphs belong to their top-level section."""
    body = None
    for c in root:
        if _local(c.tag) == "body":
            body = c
            break
    if body is None:
        return []
    out = []
    for sec in body:
        if _local(sec.tag) == "p":
            t = para_text(sec)
            if t:
                out.append(("", [t]))
            continue
        if _local(sec.tag) != "sec":
            continue
        title = ""
        for c in sec:
            if _local(c.tag) == "title":
                title = _text(c)
                break
        paras = []
        for p in sec.iter():
            if _local(p.tag) == "p":
                t = para_text(p)
                if t:
                    paras.append(t)
        if paras:
            out.append((title, paras))
    return out


def normalised_body_hash(sections: list) -> str:
    """De-duplication key: the body's words, lowercased, whitespace-folded."""
    words = " ".join(" ".join(ps) for _, ps in sections).lower()
    words = re.sub(r"[^a-z0-9]+", " ", words).strip()
    return sha256(words.encode("utf-8"))


# --- roles (weak labels) --------------------------------------------------------

# Structured-abstract heading -> sentence role. The five PubMed-RCT labels, so
# Task B stays comparable with the 82.6% TF-IDF baseline. Mixed headings
# ("Methods and findings") and non-rhetorical ones ("Funding", "Trial
# registration") are None: those sentences are left unlabelled.
_ABSTRACT_ROLES = (
    (r"^(methods? and (principal )?findings|methods? and results)$", None),
    (r"^(funding|trial registration|registration|keywords?|"
     r"clinical trial registration|ethics|abbreviations?)\b", None),
    (r"^(background|introduction|context|rationale|importance|"
     r"background and aims?)\b", "background"),
    (r"^(objectives?|aims?|purpose|goals?|study objectives?|"
     r"research questions?|hypothes[ie]s)\b", "objective"),
    (r"^(methods?|methodology|materials and methods|design|setting|"
     r"participants|patients|interventions?|exposures?|"
     r"main outcomes? (and|&) measures?|measurements|study design|"
     r"design,? setting,? and participants|data sources?|approach|"
     r"experimental design)\b", "methods"),
    (r"^(results?|findings|main results|principal findings|outcomes?)\b",
     "results"),
    (r"^(conclusions?|interpretation|implications?|discussion|"
     r"significance|conclusions? and relevance|relevance)\b", "conclusions"),
)

# Body heading -> section role (IMRaD and its common variants).
_SECTION_ROLES = (
    (r"^(\d+\.?\s*)?(introduction|background)\b", "introduction"),
    (r"^(\d+\.?\s*)?(materials? and methods|methods?|methodology|"
     r"experimental( procedures| section)?|study design|data and methods)\b",
     "methods"),
    (r"^(\d+\.?\s*)?results and discussion\b", "results-discussion"),
    (r"^(\d+\.?\s*)?(results?|findings)\b", "results"),
    (r"^(\d+\.?\s*)?discussion\b", "discussion"),
    (r"^(\d+\.?\s*)?(conclusions?|concluding remarks)\b", "conclusion"),
    (r"^(\d+\.?\s*)?limitations?\b", "limitations"),
)


def abstract_role(heading: str) -> Optional[str]:
    h = re.sub(r"[:.\s]+$", "", heading.strip().lower())
    for rx, role in _ABSTRACT_ROLES:
        if re.search(rx, h):
            return role
    return None


def section_role(heading: str) -> Optional[str]:
    h = re.sub(r"[:.\s]+$", "", heading.strip().lower())
    for rx, role in _SECTION_ROLES:
        if re.search(rx, h):
            return role
    return None


_ABBREV = re.compile(
    r"\b(e\.g|i\.e|et al|vs|Fig|Figs|Eq|Eqs|Ref|Refs|approx|ca|cf|No|Nos|"
    r"Dr|Mr|Mrs|Ms|Prof|St|resp|incl|min|max|Suppl|Tab|Vol|al)\.$", re.I)


def sentences(paragraph: str) -> list:
    """A plain splitter: good enough for weak labels, no model needed."""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(\[\"'])", paragraph)
    out = []
    for p in parts:
        if out and (_ABBREV.search(out[-1]) or re.search(r"\b[A-Z]\.$",
                                                          out[-1])):
            out[-1] = out[-1] + " " + p
        else:
            out.append(p)
    return [s.strip() for s in out if len(s.split()) >= 3]


# --- splits -----------------------------------------------------------------------

def split_of(pmcid: str) -> str:
    """Stable per-article split: ~10% test, ~10% dev, ~80% train. Hash-based,
    so it holds as the corpus grows, and per discipline in expectation (the
    report counts each discipline's test articles)."""
    h = int(sha256(("researchly-s5a:" + pmcid).encode())[:8], 16) / 0xFFFFFFFF
    if h < 0.10:
        return "test"
    if h < 0.20:
        return "dev"
    return "train"


def check_manifest_row(row: dict) -> None:
    """Raise if a manifest row could carry text or an unknown field."""
    extra = set(row) - set(MANIFEST_FIELDS)
    if extra:
        raise ValueError(f"manifest row carries unexpected fields: {extra}")
    for k, v in row.items():
        if isinstance(v, str) and len(v) > 200:
            raise ValueError(f"manifest field {k!r} is too long to be an id")
    if row.get("use") not in USES:
        raise ValueError(f"bad use {row.get('use')!r}")
    if row.get("discipline") not in DISCIPLINES:
        raise ValueError(f"bad discipline {row.get('discipline')!r}")
