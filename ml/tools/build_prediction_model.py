"""Build the word-prediction model, ``researchly/data/predict.sqlite``.

Text prediction became a core feature on 2026-10-14 (owner decision; see
CLAUDE.md #1 for the safeguards). It suggests the end of the word being
typed, or the next word or short fixed term, from counts of word sequences in
published scientific articles. It never writes a sentence.

Three steps, each re-runnable:

    # 1. find open-access articles (Europe PMC search; ids only)
    python3.10 ml/tools/build_prediction_model.py find --cache DIR --max 3000
    # 2. fetch their full text (JATS XML) into the cache, outside the repo
    python3.10 ml/tools/build_prediction_model.py fetch --cache DIR
    # 3. count, prune, evaluate on held-out articles and write the model
    python3.10 ml/tools/build_prediction_model.py build --cache DIR
    # (re-measure a built model: ... evaluate --cache DIR)

**Licence, per article.** Europe PMC's licence filter is only a search
hint. Each article's own ``<license>`` element is read, and the article is
used only if it names CC BY (any version) or CC0, with no NonCommercial,
NoDerivatives or ShareAlike term. The licence seen is written next to the
article in the attribution file (``data/predict_sources.tsv``), which ships
with the model as CC BY requires: creator, title, where to find it, the
licence, and what was changed.

**What is kept.** Only paragraph prose: no titles, headings, captions,
tables, references, formulas or citations (each of those breaks the word
sequence, so no sequence runs across one). A sequence of two or more words
is kept only if it occurs in at least ``MIN_DOCS`` different articles, so
the model holds shared phrasing of the field ("the basic reproduction
number"), never a sentence that belongs to one article. Each context keeps
its ``TOP_K`` likeliest next words.

Registry: ``europepmc-oa-prediction-corpus`` in ml/datasets.yaml.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "core"))
sys.path.insert(0, str(ROOT / "ml" / "realdocs"))

DATA = ROOT / "packages" / "core" / "researchly" / "data"
DEFAULT_OUT = DATA / "predict.sqlite"
SOURCES_OUT = DATA / "predict_sources.tsv"
REGISTRY_ID = "europepmc-oa-prediction-corpus"

SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
FULLTEXT = "https://www.ebi.ac.uk/europepmc/webservices/rest/{}/fullTextXML"
USER_AGENT = ("ResearchlyPrediction/1.0 (+https://github.com/amriitmohapatra/"
              "Researchly; builds a word-prediction model from open-access "
              "articles; one-off, low volume)")
INTERVAL = 0.25          # seconds between requests (4 a second, all threads)

# The fields Researchly is for first, then the wider biomedical sciences.
# Each query is ANDed with the open-access, licence and research-article
# filters below; the per-article licence check is what decides.
TOPICS = [
    '"infectious disease" AND (model OR modelling OR modeling)',
    '"transmission model" OR "transmission dynamics"',
    'epidemiology AND (cohort OR "case-control" OR surveillance)',
    '"public health" AND (intervention OR policy OR equity)',
    '"global health" OR "health equity" OR "health inequalities"',
    'vaccination OR vaccine AND (coverage OR effectiveness)',
    '"Bayesian" AND (inference OR hierarchical OR stan)',
    'biostatistics OR "statistical methods" OR "regression model"',
    '"randomised controlled trial" OR "randomized controlled trial"',
    'ecology OR evolution AND population',
]
FILTER = ('(LICENSE:"cc by" OR LICENSE:"cc0") AND OPEN_ACCESS:y AND '
          'IN_EPMC:y AND PUB_TYPE:"research-article" AND PUB_YEAR:[2012 TO 2026]')

ORDER = 4                # contexts of up to three words
MIN_DOCS = 3             # a 2+ word sequence must occur in this many articles
MIN_UNIGRAM_DOCS = 3     # a word must occur in this many articles
TOP_K = {0: 40000, 1: 40, 2: 12, 3: 8}   # next words kept per context
HOLD_OUT = 10            # one article in HOLD_OUT is held out for evaluation

_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9'\-]*[A-Za-z0-9]|[A-Za-z]|\d+(?:\.\d+)?|,")
_SENT_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")


# --- licences ------------------------------------------------------------------

_CC_BY = re.compile(r"creativecommons\.org/licenses/by/(\d\.\d)", re.I)
_CC0 = re.compile(r"creativecommons\.org/publicdomain/zero/", re.I)
_RESTRICTED = re.compile(r"non-?commercial|no-?deriv|share-?alike|"
                         r"licenses/by-(nc|nd|sa)", re.I)


def licence_of(xml: bytes) -> tuple[str | None, str]:
    """("CC-BY-4.0" | "CC0-1.0" | None, the evidence seen) from an article's
    own <permissions>. None: not usable (restricted, absent or unclear)."""
    text = xml.decode("utf-8", "replace")
    start = text.find("<permissions")
    end = text.find("</permissions>", start)
    block = text[start:end] if start >= 0 and end > start else ""
    if not block:
        return None, "no <permissions> element"
    if _RESTRICTED.search(block):
        return None, "restricted terms (NC, ND or SA)"
    m = _CC_BY.search(block)
    if m:
        return f"CC-BY-{m.group(1)}", m.group(0)
    if _CC0.search(block):
        return "CC0-1.0", "creativecommons.org/publicdomain/zero"
    if re.search(r"Creative Commons Attribution License", block, re.I):
        # PLOS's statement carries no version; their policy is CC BY 4.0
        return "CC-BY-4.0", "statement: Creative Commons Attribution License"
    return None, "no CC BY or CC0 licence named"


# --- 1. find ---------------------------------------------------------------------

class Limiter:
    def __init__(self, interval: float):
        self.interval, self.next, self.lock = interval, 0.0, threading.Lock()

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            delay = max(0.0, self.next - now)
            self.next = max(now, self.next) + self.interval
        if delay:
            time.sleep(delay)


def http_get(url: str, limiter: Limiter, attempts: int = 4) -> bytes:
    for attempt in range(attempts):
        limiter.wait()
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read(40 * 1024 * 1024)
        except urllib.error.HTTPError as err:
            if err.code not in (429, 500, 502, 503, 504) or \
                    attempt == attempts - 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == attempts - 1:
                raise
        time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def find(cache: Path, max_items: int) -> int:
    limiter = Limiter(INTERVAL)
    index_path = cache / "index.jsonl"
    seen: dict[str, dict] = {}
    if index_path.exists():
        for line in index_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            seen[row["pmcid"]] = row
    per_topic = math.ceil(max_items / len(TOPICS))
    for topic in TOPICS:
        got, cursor = 0, "*"
        while got < per_topic and len(seen) < max_items:
            q = urllib.parse.urlencode({
                "query": f"({topic}) AND {FILTER}", "format": "json",
                "pageSize": 200, "cursorMark": cursor, "resultType": "lite",
                "sort": "CITED desc"})
            data = json.loads(http_get(f"{SEARCH}?{q}", limiter))
            results = data.get("resultList", {}).get("result", [])
            if not results:
                break
            for r in results:
                pmcid = r.get("pmcid")
                if not pmcid or pmcid in seen:
                    continue
                seen[pmcid] = {
                    "pmcid": pmcid, "doi": r.get("doi", ""),
                    "title": (r.get("title") or "").strip(),
                    "authors": (r.get("authorString") or "").strip(),
                    "journal": r.get("journalTitle", ""),
                    "year": r.get("pubYear", ""), "topic": topic}
                got += 1
                if got >= per_topic or len(seen) >= max_items:
                    break
            nxt = data.get("nextCursorMark")
            if not nxt or nxt == cursor:
                break
            cursor = nxt
        print(f"{topic[:50]:50} {got}", file=sys.stderr)
    cache.mkdir(parents=True, exist_ok=True)
    with index_path.open("w", encoding="utf-8") as f:
        for row in seen.values():
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"{len(seen)} articles in {index_path}", file=sys.stderr)
    return 0


# --- 2. fetch ----------------------------------------------------------------------

def read_index(cache: Path) -> list[dict]:
    path = cache / "index.jsonl"
    return [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fetch(cache: Path, workers: int = 4) -> int:
    limiter = Limiter(INTERVAL)
    rows = read_index(cache)
    xml_dir = cache / "xml"
    xml_dir.mkdir(parents=True, exist_ok=True)
    todo = [r for r in rows if not (xml_dir / f"{r['pmcid']}.xml").exists()
            and not (xml_dir / f"{r['pmcid']}.missing").exists()]
    done = Counter()

    def one(row):
        try:
            data = http_get(FULLTEXT.format(row["pmcid"]), limiter)
        except urllib.error.HTTPError as err:
            (xml_dir / f"{row['pmcid']}.missing").write_text(str(err.code))
            done["missing"] += 1
            return
        except Exception:
            done["failed"] += 1
            return
        (xml_dir / f"{row['pmcid']}.xml").write_bytes(data)
        done["fetched"] += 1
        if sum(done.values()) % 200 == 0:
            print(dict(done), file=sys.stderr)

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(one, todo))
    print(f"{len(todo)} to fetch: {dict(done)}", file=sys.stderr)
    return 0


# --- 3. build -----------------------------------------------------------------------

def tokens(text: str) -> list[str]:
    out = []
    for t in _TOKEN.findall(text):
        out.append("<num>" if t[0].isdigit() else t)
    return out


def article_runs(xml: bytes) -> list[list[str]]:
    """Runs of prose tokens, original case: one run per sentence, broken at
    every citation, formula or other non-text element."""
    from convert import parse_jats

    runs: list[list[str]] = []
    for block in parse_jats(xml).blocks:
        if block.kind != "para":
            continue
        pieces, cur = [], []
        for t in block.toks:
            if t.kind == "text":
                cur.append(t.text)
            else:
                pieces.append(" ".join(cur))
                cur = []
        pieces.append(" ".join(cur))
        for piece in pieces:
            for sent in _SENT_END.split(piece):
                toks = tokens(sent)
                if len(toks) >= 3:
                    runs.append(toks)
    return runs


def held_out(pmcid: str) -> bool:
    return int(hashlib.sha256(pmcid.encode()).hexdigest()[:8], 16) \
        % HOLD_OUT == 0


def count(articles: list[tuple[str, list[list[str]]]]):
    """n-gram counts, the number of articles each n-gram occurs in, and the
    surface forms (case) of each word away from a sentence start."""
    counts: dict[int, dict[tuple, Counter]] = {
        k: defaultdict(Counter) for k in range(ORDER)}
    docs: Counter = Counter()
    forms: dict[str, Counter] = defaultdict(Counter)
    for _, runs in articles:
        seen_here: set = set()
        for run in runs:
            low = [t.lower() for t in run]
            for i, t in enumerate(run[1:], 1):
                if t != ",":
                    forms[low[i]][t] += 1
            seq = ["<s>"] + low
            for i in range(1, len(seq)):
                for k in range(ORDER):
                    if i - k < 0:
                        break
                    ctx = tuple(seq[i - k:i])
                    counts[k][ctx][seq[i]] += 1
                    seen_here.add(ctx + (seq[i],))
        docs.update(seen_here)
    return counts, docs, forms


def _usable_word(w: str) -> bool:
    return w not in ("<s>", "<num>", ",") and len(w) > 1 or w in ("a", "i")


def prune(counts, docs) -> dict[int, dict[tuple, tuple[int, list]]]:
    from researchly import spelling

    known_cache: dict[str, bool] = {}

    def known(w: str) -> bool:
        if w not in known_cache:
            known_cache[w] = w in ("<num>", ",") or \
                spelling.known_with_fallbacks(w)
        return known_cache[w]

    out: dict[int, dict[tuple, list]] = {}
    for k in range(ORDER):
        out[k] = {}
        for ctx, nxt in counts[k].items():
            keep = []
            for w, n in nxt.most_common():
                need = MIN_UNIGRAM_DOCS if k == 0 else MIN_DOCS
                if docs[ctx + (w,)] < need:
                    continue
                # a word that is not a known English or scientific word
                # (a typo in an article, a gene symbol) is never offered,
                # but it may still be context
                if w not in ("<num>", ",") and not known(w):
                    continue
                keep.append((w, n))
                if len(keep) >= TOP_K[k]:
                    break
            if keep:
                out[k][ctx] = (sum(nxt.values()), keep)
    return out


def display_forms(forms: dict[str, Counter]) -> dict[str, str]:
    """The usual case of each word when its usual case is not lower case:
    "Bayesian", "COVID-19", "DNA"."""
    out = {}
    for low, c in forms.items():
        form, n = c.most_common(1)[0]
        if form != low and n >= 0.6 * sum(c.values()):
            out[low] = form
    return out


def write_model(path: Path, model, forms: dict[str, str], meta: dict) -> None:
    from researchly import predict
    predict.write_model(path, model, forms, meta)


def write_sources(path: Path, used: list[dict]) -> None:
    head = (
        "# Attribution for researchly/data/predict.sqlite (CC BY requires it).\n"
        "# The word-prediction model was built from the articles below by\n"
        "# ml/tools/build_prediction_model.py. Each is open access under the\n"
        "# licence named on its row, read from the article's own <license>.\n"
        "# Modifications: only paragraph prose was used; it was reduced to\n"
        "# counts of word sequences of up to four words, keeping only\n"
        f"# sequences found in at least {MIN_DOCS} different articles. No\n"
        "# article's text can be recovered from the model. The model does not\n"
        "# imply that any author endorses Researchly.\n"
        "# Columns: pmcid, doi, licence, year, journal, authors, title\n")
    with path.open("w", encoding="utf-8") as f:
        f.write(head)
        for r in sorted(used, key=lambda r: r["pmcid"]):
            cells = [r["pmcid"], r.get("doi", ""), r["licence"],
                     str(r.get("year", "")), r.get("journal", ""),
                     r.get("authors", ""), r.get("title", "")]
            f.write("\t".join(c.replace("\t", " ").replace("\n", " ")
                              for c in cells) + "\n")


def evaluate(model_path: Path, test: list[list[str]],
             max_words: int = 20000) -> dict:
    """Next-word top-1/top-3 and keystrokes saved on held-out articles, as
    the engine itself predicts (researchly.predict)."""
    from researchly import predict

    m = predict.Model(model_path)
    n = hit1 = hit3 = typed = letters = 0
    for run in test:
        if n >= max_words:
            break
        low = [t.lower() for t in run]
        for i, w in enumerate(low):
            if w in ("<num>", ",") or not w.isalpha():
                continue
            ctx = low[:i]
            preds = [c for c, _ in m.next_words(ctx, "", 3)]
            n += 1
            hit1 += bool(preds) and preds[0] == w
            hit3 += w in preds
            cost = len(w)
            for j in range(len(w)):
                cands = preds if j == 0 else \
                    [c for c, _ in m.next_words(ctx, w[:j], 3)]
                if w in cands:
                    cost = j + 1        # letters typed, plus one to accept
                    break
            typed += min(cost, len(w))
            letters += len(w)
    return {"words": n, "top1": round(hit1 / max(n, 1), 4),
            "top3": round(hit3 / max(n, 1), 4),
            "keystrokes_saved": round(1 - typed / max(letters, 1), 4)}


SHARDS = 16
_S, _NUM, _COMMA = 0, 1, 2          # reserved ids in the encoded corpus


def encode(train, vocab: dict[str, int], forms: dict[int, Counter],
           ) -> list[list]:
    """Each article as runs of word ids (lower case), so 18 million tokens
    fit in memory; `forms` collects the case each word is written in away
    from a sentence start."""
    from array import array

    out = []
    for _, runs in train:
        enc = []
        for run in runs:
            ids = array("i")
            for i, t in enumerate(run):
                low = "<num>" if t == "<num>" else t.lower()
                wid = vocab.setdefault(low, len(vocab))
                ids.append(wid)
                if i and t != low and t not in ("<num>", ","):
                    forms[wid][t] += 1
                elif i:
                    forms[wid][low] += 1
            enc.append(ids)
        out.append(enc)
    return out


def count_shard(articles: list[list], shard: int):
    """Counts and article frequencies of the n-grams whose context falls in
    this shard (a hash of the context), in word-id space."""
    counts: dict[tuple, Counter] = defaultdict(Counter)
    docs: Counter = Counter()
    for runs in articles:
        seen: set = set()
        for ids in runs:
            seq = (_S,) + tuple(ids)
            for i in range(1, len(seq)):
                w = seq[i]
                for k in range(ORDER):
                    if i - k < 0:
                        break
                    ctx = seq[i - k:i]
                    if hash(ctx) % SHARDS != shard:
                        continue
                    counts[ctx][w] += 1
                    seen.add(ctx + (w,))
        docs.update(seen)
    return counts, docs


def prune_shard(counts, docs, words: list[str], known) -> list[tuple]:
    """Rows (order, context words, total, [(word, count), ...]) to keep."""
    rows = []
    for ctx, nxt in counts.items():
        k = len(ctx)
        need = MIN_UNIGRAM_DOCS if k == 0 else MIN_DOCS
        keep = []
        for w, n in nxt.most_common():
            if n < need:
                break               # too rare to be in enough articles
            if docs[ctx + (w,)] < need:
                continue
            if w not in (_NUM, _COMMA) and not known(w):
                continue
            keep.append((words[w], n))
            if len(keep) >= TOP_K[k]:
                break
        if keep:
            rows.append((k, tuple(words[i] for i in ctx),
                         sum(nxt.values()), keep))
    return rows


def build(cache: Path, out: Path, sources_out: Path) -> int:
    from researchly import spelling

    rows = {r["pmcid"]: r for r in read_index(cache)}
    vocab: dict[str, int] = {"<s>": _S, "<num>": _NUM, ",": _COMMA}
    forms: dict[int, Counter] = defaultdict(Counter)
    train, test, used, refused = [], [], [], Counter()
    words_total = 0
    for path in sorted((cache / "xml").glob("*.xml")):
        pmcid = path.stem
        xml = path.read_bytes()
        lic, evidence = licence_of(xml)
        if lic is None:
            refused[evidence] += 1
            continue
        try:
            runs = article_runs(xml)
        except Exception:
            refused["unparseable"] += 1
            continue
        if not runs:
            refused["no prose"] += 1
            continue
        if held_out(pmcid):
            test += runs
            continue
        words_total += sum(len(r) for r in runs)
        train += encode([(pmcid, runs)], vocab, forms)
        row = dict(rows.get(pmcid, {"pmcid": pmcid}))
        row["licence"] = lic
        used.append(row)
    print(f"training articles {len(train)} ({words_total:,} tokens); held "
          f"out {len(test)} sentences; refused {dict(refused)}",
          file=sys.stderr)

    words = [""] * len(vocab)
    for w, i in vocab.items():
        words[i] = w
    known_cache: dict[int, bool] = {}

    def known(wid: int) -> bool:
        if wid not in known_cache:
            known_cache[wid] = spelling.known_with_fallbacks(words[wid])
        return known_cache[wid]

    model: dict[int, dict] = {k: {} for k in range(ORDER)}
    for shard in range(SHARDS):
        counts, docs = count_shard(train, shard)
        for k, ctx, total, keep in prune_shard(counts, docs, words, known):
            model[k][ctx] = (total, keep)
        del counts, docs
        print(f"shard {shard + 1}/{SHARDS}: "
              f"{sum(len(t) for t in model.values()):,} contexts kept",
              file=sys.stderr)
    shown = {}
    for wid, c in forms.items():
        form, n = c.most_common(1)[0]
        if form != words[wid] and n >= 0.6 * sum(c.values()):
            shown[words[wid]] = form
    meta = {"version": 1, "articles": len(train), "tokens": words_total,
            "order": ORDER, "min_docs": MIN_DOCS, "top_k": TOP_K,
            "registry": REGISTRY_ID, "built": time.strftime("%Y-%m-%d"),
            "attribution": "data/predict_sources.tsv"}
    write_model(out, model, shown, meta)
    write_sources(sources_out, used)
    result = evaluate(out, test)
    db = sqlite3.connect(out)
    db.execute("insert or replace into meta values ('heldout', ?)",
               (json.dumps(result),))
    db.commit()
    db.close()
    size = out.stat().st_size / 1e6
    print(f"{out} {size:.1f} MB; held out: {result}", file=sys.stderr)
    return 0


def evaluate_only(cache: Path, out: Path) -> int:
    """Re-measure a built model on the held-out articles and record the
    result in its meta table."""
    test = []
    for path in sorted((cache / "xml").glob("*.xml")):
        if not held_out(path.stem):
            continue
        xml = path.read_bytes()
        if licence_of(xml)[0] is None:
            continue
        try:
            test += article_runs(xml)
        except Exception:
            continue
    result = evaluate(out, test)
    db = sqlite3.connect(out)
    db.execute("insert or replace into meta values ('heldout', ?)",
               (json.dumps(result),))
    db.commit()
    db.execute("vacuum")
    db.close()
    print(f"held out: {result}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("find", "fetch", "build", "evaluate"):
        p = sub.add_parser(name)
        p.add_argument("--cache", type=Path, required=True)
        if name == "find":
            p.add_argument("--max", type=int, default=3000)
        if name in ("build", "evaluate"):
            p.add_argument("--out", type=Path, default=DEFAULT_OUT)
        if name == "build":
            p.add_argument("--sources", type=Path, default=SOURCES_OUT)
    args = ap.parse_args(argv)
    if ROOT in args.cache.resolve().parents or args.cache.resolve() == ROOT:
        print("refused: the article cache must be outside the repository",
              file=sys.stderr)
        return 2
    if args.cmd == "find":
        return find(args.cache, args.max)
    if args.cmd == "fetch":
        return fetch(args.cache)
    if args.cmd == "evaluate":
        return evaluate_only(args.cache, args.out)
    return build(args.cache, args.out, args.sources)


if __name__ == "__main__":
    sys.exit(main())
