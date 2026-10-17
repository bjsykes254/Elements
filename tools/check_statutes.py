#!/usr/bin/env python3
"""Elements statute change checker.

Uses only the Python standard library.

  py tools/check_statutes.py check      Compare saved statute text with ncleg.gov and write a report.
  py tools/check_statutes.py baseline   Save the current list of sections in each watched article.
  py tools/check_statutes.py accept 14-52
                                        After you have reviewed a change: refresh the saved text for
                                        that section and flag the records that cite it for re-checking.

Exit codes for `check`: 0 nothing needs attention, 1 something changed or needs a look,
2 some pages could not be read (the check is incomplete; never treat this as "no change").

The checker never edits record wording and never marks anything verified.
"""
import argparse
import difflib
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

UA = "ElementsStatuteChecker/1.0 (+https://github.com/bjsykes254/Elements; personal educational project)"
DELAY_SECONDS = 1.5
SOG_LIST = ("https://www.sog.unc.edu/resources/microsites/north-carolina-pattern-jury-instructions/"
            "north-carolina-pattern-jury-instructions-criminal-cases")
DEFAULT_ARTICLES = [
    {"id": "art6", "label": "Chapter 14, Article 6 (Homicide)",
     "url": "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/ByArticle/Chapter_14/Article_6.html"},
    {"id": "art8", "label": "Chapter 14, Article 8 (Assaults)",
     "url": "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/ByArticle/Chapter_14/Article_8.html"},
    {"id": "art14", "label": "Chapter 14, Article 14 (Burglary and other housebreakings)",
     "url": "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/ByArticle/Chapter_14/Article_14.html"},
    {"id": "art16", "label": "Chapter 14, Article 16 (Larceny and related offenses)",
     "url": "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/ByArticle/Chapter_14/Article_16.html"},
]


class FetchError(Exception):
    pass


class NotFound(Exception):
    pass


def norm(s):
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def squash(s):
    return re.sub(r"\s+", "", s)


def sha256(s):
    return hashlib.sha256(norm(s).encode("utf-8")).hexdigest()


class PageParser(HTMLParser):
    BLOCK = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "br", "table"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paras, self.cur, self.skip = [], [], 0
        self.links = []
        self.hist, self.in_hist = [], False

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag in ("script", "style"):
            self.skip += 1
        if tag in self.BLOCK:
            self.flush()
        if tag == "a":
            if d.get("href"):
                self.links.append(d["href"])
            if d.get("name") == "HistoryNote":
                self.in_hist = True
                self.hist.append("")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        if tag in self.BLOCK:
            self.flush()
        if tag == "a":
            self.in_hist = False

    def handle_data(self, data):
        if self.skip:
            return
        self.cur.append(data)
        if self.in_hist and self.hist:
            self.hist[-1] += data

    def flush(self):
        t = norm("".join(self.cur))
        if t:
            self.paras.append(t)
        self.cur = []

    def close(self):
        super().close()
        self.flush()


def parse(html):
    p = PageParser()
    p.feed(html)
    p.close()
    return p


def section_text(html):
    """Text of a single-section page, from the section heading through the history note."""
    p = parse(html)
    start = next((i for i, t in enumerate(p.paras) if t.startswith("§")), None)
    if start is None:
        raise FetchError("page has no section heading (unexpected layout)")
    text = norm(" ".join(p.paras[start:]))
    history = norm(p.hist[-1]) if p.hist else ""
    if not history:
        m = re.search(r"\(([^()]*(?:\([^()]*\)[^()]*)*)\)\s*$", text)
        history = m.group(0) if m else ""
    return text, history


def last_session_law(history):
    h = history.strip().strip("()").strip().rstrip(".")
    items = [i.strip() for i in h.split(";") if i.strip()]
    return items[-1] if items else ""


def article_headings(html):
    p = parse(html)
    return [norm(t)[:200] for t in p.paras if t.startswith("§")]


def instruction_listing(html):
    """Map instruction number -> list of decoded file names found in the SOG listing."""
    p = parse(html)
    found = {}
    for href in p.links:
        if "pji-master" not in href or not href.lower().endswith(".pdf"):
            continue
        name = urllib.parse.unquote(href.rsplit("/", 1)[-1])
        n = instruction_number(name)
        if n:
            found.setdefault(n, []).append(name)
    return found


def instruction_number(name):
    m = re.match(r"(\d{3}(?:\.\d+[A-Za-z]*)?)\s", name)
    return m.group(1) if m else None


def word_diff(old, new, limit=12):
    a, b = old.split(), new.split()
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        ctx = " ".join(a[max(0, i1 - 6):i1])
        removed, added = " ".join(a[i1:i2]), " ".join(b[j1:j2])
        after = " ".join(a[i2:i2 + 4])
        piece = "…" + ctx + " " if ctx else ""
        if removed:
            piece += "[removed: " + removed[:300] + "] "
        if added:
            piece += "[added: " + added[:300] + "]"
        if after:
            piece += " " + after + "…"
        out.append(piece.strip())
        if len(out) >= limit:
            out.append("(more changes not shown)")
            break
    return out


def make_fetcher(offline_dir=None):
    def fetch(url):
        if offline_dir:
            p = Path(offline_dir) / (url.rsplit("/", 1)[-1] if "sog.unc.edu" not in url else "sog_list.html")
            if not p.exists():
                raise FetchError("no offline copy of " + url)
            return p.read_text(encoding="utf-8", errors="replace")
        last = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    return r.read().decode(r.headers.get_content_charset() or "utf-8", "replace")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    raise NotFound(url)
                last = e
            except Exception as e:  # network trouble: try again
                last = e
            time.sleep(3 * (attempt + 1))
        raise FetchError("%s: %s" % (url, last))
    return fetch


def collect_sections(data):
    """url -> dict(cites, records, snapshot, last_sl, entries)."""
    out = {}
    for o in data["offenses"]:
        for s in o.get("statutes", []):
            u = s["url"]
            e = out.setdefault(u, {"cites": set(), "records": [], "snapshot": None, "last_sl": None, "entries": []})
            e["cites"].add(s["cite"])
            e["records"].append(o["id"])
            e["entries"].append(s)
            if s.get("text_snapshot") and not e["snapshot"]:
                e["snapshot"] = s["text_snapshot"]
                e["last_sl"] = s.get("last_session_law_seen")
    return out


def run_check(data, fetch, pause=0.0, today=None):
    today = today or date.today().isoformat()
    res = {"date": today, "changed": [], "unchanged": [], "no_baseline": [], "errors": [],
           "articles": [], "articles_unchecked": [], "instructions": [], "instruction_notes": []}
    status_of = {o["id"]: o.get("review", {}).get("status", "draft") for o in data["offenses"]}
    for url, e in collect_sections(data).items():
        time.sleep(pause)
        label = "; ".join(sorted(e["cites"]))
        affects = ["%s (%s)" % (r, status_of[r]) for r in dict.fromkeys(e["records"])]
        try:
            html = fetch(url)
            text, history = section_text(html)
        except NotFound:
            res["changed"].append({"url": url, "label": label, "affects": affects,
                                   "kind": "page not found: the section may have been renumbered or repealed", "diff": []})
            continue
        except FetchError as ex:
            res["errors"].append({"url": url, "what": str(ex)})
            continue
        head = text[:160]
        repealed = bool(re.match(r"§+\s*\d+[\w.\-]*(?:\s+through\s+\d+[\w.\-]*)?[.:]\s*(Repealed|Reserved|Expired|Recodified|Transferred)", head, re.I))
        if not e["snapshot"]:
            res["no_baseline"].append({"url": url, "label": label, "affects": affects})
            continue
        if repealed:
            res["changed"].append({"url": url, "label": label, "affects": affects,
                                   "kind": "section now reads as repealed, reserved or transferred", "diff": [text[:300]]})
        elif squash(text) != squash(e["snapshot"]):
            res["changed"].append({"url": url, "label": label, "affects": affects, "kind": "text changed",
                                   "old_sl": e["last_sl"], "new_sl": last_session_law(history),
                                   "diff": word_diff(norm(e["snapshot"]), text)})
        else:
            res["unchanged"].append({"url": url, "label": label})
    for art in data.get("meta", {}).get("watch_articles", DEFAULT_ARTICLES):
        time.sleep(pause)
        try:
            heads = article_headings(fetch(art["url"]))
        except (FetchError, NotFound) as ex:
            res["errors"].append({"url": art["url"], "what": str(ex)})
            continue
        old = art.get("headings") or []
        if not old:
            res["articles_unchecked"].append({"label": art["label"], "url": art["url"], "count": len(heads)})
            continue
        added = [h for h in heads if h not in old]
        removed = [h for h in old if h not in heads]
        if added or removed:
            res["articles"].append({"label": art["label"], "url": art["url"], "added": added, "removed": removed})
    # Pattern jury instructions
    urls = {}
    for o in data["offenses"]:
        for c in o.get("cross_checks", []):
            if "pji-master" in c.get("url", ""):
                urls.setdefault(c["url"], []).append(o["id"])
    if urls:
        time.sleep(pause)
        try:
            listing = instruction_listing(fetch(SOG_LIST))
        except (FetchError, NotFound) as ex:
            listing = {}
            res["instruction_notes"].append("Could not read the pattern jury instruction list: %s" % ex)
        if listing and sum(len(v) for v in listing.values()) < 20:
            res["instruction_notes"].append("The instruction list looked too short to trust (%d files); instruction check skipped." % sum(len(v) for v in listing.values()))
            listing = {}
        for url, recs in urls.items():
            name = urllib.parse.unquote(url.rsplit("/", 1)[-1])
            num = instruction_number(name)
            if not listing or not num:
                continue
            current = listing.get(num)
            if current is None:
                res["instructions"].append({"number": num, "records": sorted(set(recs)), "what": "no longer found in the list (renumbered or withdrawn?)"})
            elif name not in current:
                res["instructions"].append({"number": num, "records": sorted(set(recs)), "what": "a different version is now listed: " + "; ".join(current)})
    return res


def exit_code(res):
    if res["changed"] or res["articles"] or res["instructions"]:
        return 1
    if res["errors"]:
        return 2
    return 0


def render(res):
    L = ["# Statute check, %s" % res["date"], ""]
    n_changed = len(res["changed"]) + len(res["articles"]) + len(res["instructions"])
    L.append("**%d sections unchanged, %d need attention, %d could not be read.**" % (len(res["unchanged"]), n_changed, len(res["errors"])))
    if res["errors"]:
        L += ["", "> Some pages could not be read, so this check is incomplete. No news is not good news here."]
    if res["changed"]:
        L += ["", "## Sections that changed"]
        for c in res["changed"]:
            L += ["", "### %s: %s" % (c["label"], c["kind"]), c["url"], "",
                  "Records that cite it: " + ", ".join(c["affects"])]
            if c.get("new_sl") and c.get("new_sl") != c.get("old_sl"):
                L.append("Latest session law in the history note: `%s` (was `%s`)" % (c["new_sl"], c.get("old_sl")))
            for d in c["diff"]:
                L.append("- " + d)
            L.append("")
            L.append("Next: read the new text, edit the affected records to match, then run `py tools/check_statutes.py accept %s`." % re.sub(r".*GS_(.*)\.html", r"\1", c["url"]))
    if res["articles"]:
        L += ["", "## Sections added to or removed from a watched article"]
        for a in res["articles"]:
            L += ["", "### " + a["label"], a["url"]]
            for h in a["added"]:
                L.append("- new or changed heading: " + h)
            for h in a["removed"]:
                L.append("- heading gone or changed: " + h)
    if res["instructions"]:
        L += ["", "## Pattern jury instructions"]
        for i in res["instructions"]:
            L.append("- N.C.P.I.-Crim. %s (used by %s): %s" % (i["number"], ", ".join(i["records"]), i["what"]))
    for n in res["instruction_notes"]:
        L += ["", "_" + n + "_"]
    if res["errors"]:
        L += ["", "## Could not read"]
        for e in res["errors"]:
            L.append("- %s: %s" % (e["url"], e["what"]))
    if res["no_baseline"]:
        L += ["", "## No saved text to compare with"]
        L.append("These sections have no `text_snapshot` yet because they haven't been read word for word:")
        for n in res["no_baseline"]:
            L.append("- %s (%s)" % (n["label"], ", ".join(n["affects"])))
    if res["articles_unchecked"]:
        L += ["", "## Article lists without a baseline"]
        for a in res["articles_unchecked"]:
            L.append("- %s: run `py tools/check_statutes.py baseline` once (%d headings found)" % (a["label"], a["count"]))
    return "\n".join(L) + "\n"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def cmd_check(a):
    data = load(a.data)
    res = run_check(data, make_fetcher(a.offline_dir), pause=0 if a.offline_dir else DELAY_SECONDS)
    report = render(res)
    if a.report:
        Path(a.report).write_text(report, encoding="utf-8")
    print(report)
    return exit_code(res)


def cmd_baseline(a):
    data = load(a.data)
    fetch = make_fetcher(a.offline_dir)
    arts = data.setdefault("meta", {}).setdefault("watch_articles", [dict(x) for x in DEFAULT_ARTICLES])
    for art in arts:
        heads = article_headings(fetch(art["url"]))
        if len(heads) < 3:
            print("Only %d headings found for %s; leaving it alone." % (len(heads), art["label"]))
            continue
        art["headings"], art["captured_on"] = heads, date.today().isoformat()
        print("%s: saved %d headings" % (art["label"], len(heads)))
        time.sleep(0 if a.offline_dir else DELAY_SECONDS)
    save(a.data, data)
    return 0


def cmd_accept(a):
    data = load(a.data)
    secs = collect_sections(data)
    urls = [u for u in secs if u.endswith("GS_%s.html" % a.section)]
    if not urls:
        print("No record cites section %s." % a.section)
        return 1
    url = urls[0]
    text, history = section_text(make_fetcher(a.offline_dir)(url))
    old = secs[url]["snapshot"]
    if old and squash(old) == squash(text):
        print("Saved text already matches the live page. Nothing to do.")
        return 0
    if old:
        print("\n".join(word_diff(norm(old), text)))
    ids = list(dict.fromkeys(secs[url]["records"]))
    print("\nThis will save the new text for %s and flag these records: %s" % (a.section, ", ".join(ids)))
    if not a.yes and input("Continue? [y/N] ").strip().lower() != "y":
        print("Cancelled.")
        return 1
    sl, today = last_session_law(history), date.today().isoformat()
    for s in secs[url]["entries"]:
        s.update(text_snapshot=text, text_captured_on=today, text_sha256=sha256(text), last_session_law_seen=sl)
    for o in data["offenses"]:
        if o["id"] in ids:
            r = o.setdefault("review", {})
            before = r.get("status", "draft")
            if before == "verified":
                r["status"] = "needs_review"
                r["verified_by"], r["verified_on"] = None, None
            r.setdefault("history", []).append({"on": today, "event": "statute text for G.S. %s updated; was %s" % (a.section, before)})
    save(a.data, data)
    print("Saved. Edit the flagged records to match the new text, then verify them again.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="elements-nc.json")
    ap.add_argument("--offline-dir", help="read saved HTML pages from this folder instead of the internet (for tests)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--report", help="also write the report to this file")
    sub.add_parser("baseline")
    ac = sub.add_parser("accept")
    ac.add_argument("section", help="for example 14-52")
    ac.add_argument("--yes", action="store_true")
    a = ap.parse_args(argv)
    return {"check": cmd_check, "baseline": cmd_baseline, "accept": cmd_accept}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
