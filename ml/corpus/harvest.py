"""Harvest the S5a open-access corpus (PLAN.md S5a; spec: ml/corpus/SPEC.md).

Three re-runnable steps, all through Europe PMC's open REST API
(https://europepmc.org/RestfulWebService; no key, polite rate):

    # 1. find candidate articles per discipline (ids only)
    python3.10 ml/corpus/harvest.py find --per-discipline 80
    # 2. fetch their full text (JATS XML) into the cache, OUTSIDE the repo
    python3.10 ml/corpus/harvest.py fetch
    # 3. read each article's own licence, de-duplicate, split, and write the
    #    manifest (ml/corpus/manifest.jsonl): ids, licence, discipline,
    #    split, counts and hashes. No text.
    python3.10 ml/corpus/harvest.py manifest
    # or all three:
    python3.10 ml/corpus/harvest.py all --per-discipline 80

The cache defaults to ~/.researchly/corpus ($RESEARCHLY_CORPUS_CACHE or
--cache to move it); a cache inside the repository is refused. The search
is not filtered by licence: every article's own <permissions> block decides
(common.licence_of), so the manifest also shows what the filter turned away.

Registry: s5a-oa-corpus-cc-by (use "train") and s5a-oa-corpus-nc-eval
(use "eval") in ml/datasets.yaml.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
FULLTEXT = "https://www.ebi.ac.uk/europepmc/webservices/rest/{}/fullTextXML"
USER_AGENT = ("ResearchlyCorpus/1.0 (+https://github.com/amriitmohapatra/"
              "Researchly; builds a licence-checked open-access training "
              "manifest; low volume)")
INTERVAL = 0.25          # seconds between requests, all threads (4/s)
FILTER = ('OPEN_ACCESS:y AND IN_EPMC:y AND PUB_TYPE:"research-article" '
          'AND PUB_YEAR:[2016 TO 2026]')

# discipline -> Europe PMC queries. Journals are open-access titles with
# editorial standards (Nature/Lancet/BMJ/PLOS/eLife/BMC/Royal Society
# families); topics keep multidisciplinary journals on the discipline.
# The first discipline to find an article keeps it.
QUERIES = {
    "epidemiology": [
        '("infectious disease" OR epidemic OR outbreak OR pathogen) AND '
        '(transmission OR "mathematical model" OR surveillance) AND '
        '(JOURNAL:"PLoS Comput Biol" OR JOURNAL:"Lancet Infect Dis" OR '
        'JOURNAL:"BMC Infect Dis" OR JOURNAL:"Epidemics" OR '
        'JOURNAL:"PLoS Negl Trop Dis" OR JOURNAL:"Lancet Glob Health")',
    ],
    "public-health": [
        '("public health" OR "health policy" OR "health equity" OR '
        '"health inequalities" OR "global health") AND '
        '(JOURNAL:"BMC Public Health" OR JOURNAL:"BMJ Glob Health" OR '
        'JOURNAL:"Lancet Public Health" OR JOURNAL:"Lancet Glob Health" OR '
        'JOURNAL:"PLoS Med")',
    ],
    "clinical-medicine": [
        '("randomised controlled trial" OR "randomized controlled trial" OR '
        '"cohort study" OR "cross-sectional") AND (JOURNAL:"BMC Med" OR '
        'JOURNAL:"PLoS Med" OR JOURNAL:"BMJ Open" OR JOURNAL:"JAMA Netw Open" '
        'OR JOURNAL:"Lancet" OR JOURNAL:"EClinicalMedicine")',
    ],
    "molecular-biology": [
        '(protein OR gene OR genome OR "cell biology" OR transcription) AND '
        '(JOURNAL:"eLife" OR JOURNAL:"PLoS Biol" OR JOURNAL:"Nat Commun" OR '
        'JOURNAL:"Nucleic Acids Res" OR JOURNAL:"Cell Rep")',
    ],
    "ecology-evolution": [
        '(ecology OR evolution OR biodiversity OR "species distribution" OR '
        'phylogen*) AND (JOURNAL:"Ecol Evol" OR JOURNAL:"Proc Biol Sci" OR '
        'JOURNAL:"PLoS Biol" OR JOURNAL:"Nat Ecol Evol" OR '
        'JOURNAL:"Evol Lett" OR JOURNAL:"R Soc Open Sci")',
    ],
    "physical-earth-sciences": [
        '(physics OR chemistry OR climate OR geophysics OR ocean OR '
        '"materials science" OR atmospheric) AND (JOURNAL:"Sci Rep" OR '
        'JOURNAL:"Nat Commun" OR JOURNAL:"Sci Adv" OR '
        'JOURNAL:"R Soc Open Sci" OR JOURNAL:"Commun Earth Environ")',
    ],
    "engineering": [
        '(engineering OR robot* OR sensor OR "control system" OR '
        '"signal processing" OR manufacturing) AND (JOURNAL:"Sci Rep" OR '
        'JOURNAL:"PLoS One" OR JOURNAL:"Sci Adv" OR '
        'JOURNAL:"R Soc Open Sci" OR JOURNAL:"Sensors (Basel)")',
    ],
    "computational-statistics": [
        '("Bayesian" OR "statistical method" OR "simulation study" OR '
        '"machine learning" OR "causal inference") AND '
        '(JOURNAL:"BMC Med Res Methodol" OR JOURNAL:"PLoS Comput Biol" OR '
        'JOURNAL:"Stat Med" OR JOURNAL:"BMC Bioinformatics")',
    ],
    # Humanities and social sciences: discipline journals only. A topic word
    # in a general journal ("history" in PLOS ONE) mostly finds medicine.
    # Several queries share a discipline's quota evenly, so one prolific
    # journal cannot fill it.
    "social-sciences": [
        '(economics OR education OR sociology OR "political" OR policy OR '
        'migration OR inequality) AND (JOURNAL:"Humanit Soc Sci Commun" OR '
        'JOURNAL:"Palgrave Commun")',
        '(education OR sociology OR economics OR "social psychology") AND '
        'JOURNAL:"Front Psychol"',
    ],
    "humanities": [
        '(history OR philosophy OR literature OR linguistics OR archaeology '
        'OR heritage OR religion OR art OR language) AND '
        '(JOURNAL:"Humanit Soc Sci Commun" OR JOURNAL:"Palgrave Commun")',
        'JOURNAL:"Synthese" OR JOURNAL:"Philos Stud" OR '
        'JOURNAL:"Erkenntnis" OR JOURNAL:"Hum Stud"',
        'JOURNAL:"Hist Philos Life Sci" OR JOURNAL:"Herit Sci"',
        'JOURNAL:"BMC Med Ethics"',
    ],
}


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
            wait = err.headers.get("Retry-After") if err.headers else None
            time.sleep(float(wait) if wait and wait.isdigit() else 2 ** attempt)
            continue
        except (urllib.error.URLError, TimeoutError):
            if attempt == attempts - 1:
                raise
        time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


# --- 1. find ----------------------------------------------------------------------

def read_index(cache: Path) -> dict:
    path = cache / "index.jsonl"
    out: dict = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                out[row["pmcid"]] = row
    return out


def find(cache: Path, per_discipline: int, disciplines=None) -> dict:
    limiter = Limiter(INTERVAL)
    seen = read_index(cache)
    have = Counter(r["discipline"] for r in seen.values())
    for disc in disciplines or common.DISCIPLINES:
        queries = QUERIES[disc]
        for qi, query in enumerate(queries):
            # an even share of what is still missing; a query that runs dry
            # leaves its remainder to the next
            share = -(-(per_discipline - have[disc]) // (len(queries) - qi))
            stop = have[disc] + share
            cursor = "*"
            while have[disc] < stop:
                q = urllib.parse.urlencode({
                    "query": f"({query}) AND {FILTER}", "format": "json",
                    "pageSize": 100, "cursorMark": cursor,
                    "resultType": "lite", "sort": "CITED desc"})
                data = json.loads(http_get(f"{SEARCH}?{q}", limiter))
                results = data.get("resultList", {}).get("result", [])
                if not results:
                    break
                for r in results:
                    pmcid = r.get("pmcid")
                    if not pmcid or pmcid in seen:
                        continue
                    seen[pmcid] = {"pmcid": pmcid, "discipline": disc,
                                   "search_licence": r.get("license") or ""}
                    have[disc] += 1
                    if have[disc] >= stop:
                        break
                nxt = data.get("nextCursorMark")
                if not nxt or nxt == cursor:
                    break
                cursor = nxt
        print(f"  find {disc:26} {have[disc]}", file=sys.stderr)
    cache.mkdir(parents=True, exist_ok=True)
    with (cache / "index.jsonl").open("w", encoding="utf-8") as f:
        for row in seen.values():
            f.write(json.dumps(row) + "\n")
    print(f"{len(seen)} candidates in {cache / 'index.jsonl'}",
          file=sys.stderr)
    return seen


# --- 2. fetch ------------------------------------------------------------------------

def fetch(cache: Path, workers: int = 4) -> Counter:
    limiter = Limiter(INTERVAL)
    rows = list(read_index(cache).values())
    xml_dir = cache / "xml"
    xml_dir.mkdir(parents=True, exist_ok=True)
    todo = [r for r in rows if not (xml_dir / f"{r['pmcid']}.xml").exists()
            and not (xml_dir / f"{r['pmcid']}.missing").exists()]
    done: Counter = Counter()
    lock = threading.Lock()

    def one(row):
        try:
            data = http_get(FULLTEXT.format(row["pmcid"]), limiter)
        except urllib.error.HTTPError as err:
            (xml_dir / f"{row['pmcid']}.missing").write_text(str(err.code))
            key = "missing"
        except Exception:
            key = "failed"
        else:
            (xml_dir / f"{row['pmcid']}.xml").write_bytes(data)
            key = "fetched"
        with lock:
            done[key] += 1
            if sum(done.values()) % 100 == 0:
                print(f"  fetch {dict(done)}", file=sys.stderr)

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(one, todo))
    print(f"{len(todo)} to fetch: {dict(done)}", file=sys.stderr)
    return done


# --- 3. manifest -----------------------------------------------------------------------

def build_row(cand: dict, xml: bytes, checked: str) -> tuple:
    """(manifest row or None, reason dropped)."""
    spdx, use, evidence = common.licence_of(xml)
    if spdx is None:
        return None, "licence: " + evidence
    try:
        root = common.parse_xml(xml)
    except Exception as e:
        return None, f"unparseable XML ({type(e).__name__})"
    meta = common.article_meta(root)
    body = common.body_sections(root)
    paras = sum(len(ps) for _, ps in body)
    words = sum(len(p.split()) for _, ps in body for p in ps)
    if paras < 5 or words < 1500:
        return None, "no full body (abstract only or too short)"
    abstract = common.abstract_sections(root)
    pmcid = cand["pmcid"]
    row = {
        "id": "pmc-" + pmcid,
        "pmcid": pmcid,
        "pmid": meta["pmid"],
        "doi": meta["doi"],
        "journal": meta["journal"],
        "year": meta["year"],
        "discipline": cand["discipline"],
        "licence": spdx,
        "licence_evidence": evidence,
        "licence_checked": checked,
        "use": use,
        "permitted_use": common.USES[use],
        "registry": common.REGISTRY_TRAIN if use == "train"
        else common.REGISTRY_EVAL,
        "split": common.split_of(pmcid),
        "xml_sha256": common.sha256(xml),
        "body_sha256": common.normalised_body_hash(body),
        "words": words,
        "paragraphs": paras,
        "sections": sorted({r for r in (common.section_role(h)
                                        for h, _ in body) if r}),
        "structured_abstract": bool(abstract),
        "abstract_sections": sum(1 for h, _ in abstract
                                 if common.abstract_role(h)),
    }
    common.check_manifest_row(row)
    return row, ""


def manifest(cache: Path, out: Path, checked: str = "") -> dict:
    checked = checked or ("<permissions> of the Europe PMC fullTextXML, "
                          + date.today().isoformat())
    cands = read_index(cache)
    xml_dir = cache / "xml"
    rows, dropped = [], Counter()
    seen_doi, seen_body = {}, {}
    for pmcid in sorted(cands):
        path = xml_dir / f"{pmcid}.xml"
        if not path.exists():
            dropped["not fetched / no full text"] += 1
            continue
        row, why = build_row(cands[pmcid], path.read_bytes(), checked)
        if row is None:
            dropped[why] += 1
            continue
        if row["doi"] and row["doi"] in seen_doi:
            dropped["duplicate (DOI)"] += 1
            continue
        if row["body_sha256"] in seen_body:
            dropped["duplicate (same body text)"] += 1
            continue
        seen_doi[row["doi"]] = pmcid
        seen_body[row["body_sha256"]] = pmcid
        rows.append(row)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    summary = summarise(rows)
    summary["dropped"] = dict(dropped)
    summary["candidates"] = len(cands)
    print(json.dumps(summary, indent=1), file=sys.stderr)
    return summary


def summarise(rows: list) -> dict:
    by = {}
    for r in rows:
        d = by.setdefault(r["discipline"], Counter())
        d["articles"] += 1
        d["use:" + r["use"]] += 1
        d["licence:" + r["licence"]] += 1
        d["split:" + r["split"]] += 1
        d["structured_abstract"] += int(r["structured_abstract"])
    return {"articles": len(rows),
            "train_use": sum(r["use"] == "train" for r in rows),
            "eval_use": sum(r["use"] == "eval" for r in rows),
            "words": sum(r["words"] for r in rows),
            "by_discipline": {k: dict(v) for k, v in sorted(by.items())}}


def read_manifest(path: Path = common.MANIFEST) -> list:
    rows = [json.loads(line) for line in
            Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    for r in rows:
        common.check_manifest_row(r)
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("step", choices=["find", "fetch", "manifest", "all",
                                     "summary"])
    ap.add_argument("--cache", type=Path, default=None,
                    help="full-text cache, outside the repo "
                         "(default ~/.researchly/corpus)")
    ap.add_argument("--out", type=Path, default=common.MANIFEST)
    ap.add_argument("--per-discipline", type=int, default=80)
    ap.add_argument("--discipline", action="append",
                    choices=common.DISCIPLINES)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    if a.step == "summary":
        print(json.dumps(summarise(read_manifest(a.out)), indent=1))
        return 0
    cache = common.outside_repo(a.cache or common.default_cache())
    if a.step in ("find", "all"):
        find(cache, a.per_discipline, a.discipline)
    if a.step in ("fetch", "all"):
        fetch(cache, a.workers)
    if a.step in ("manifest", "all"):
        manifest(cache, a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
