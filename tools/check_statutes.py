#!/usr/bin/env python3
"""Elements statute change checker.

Uses only the Python standard library. Everything specific to one state lives in tools/adapters/.

  py tools/check_statutes.py check      Compare saved statute text with the official site and write a report.
  py tools/check_statutes.py baseline   Save the current list of sections in each watched article.
  py tools/check_statutes.py accept 14-52
                                        Save (or refresh) the text for one section in sources/<state>/ and
                                        flag the records that cite it. Use it after you have read the
                                        live text, and after a reported change once you have edited the records.

Exit codes for `check`: 0 nothing needs attention, 1 something changed or needs a look,
2 some pages could not be read (the check is incomplete; never treat this as "no change").

The checker never edits record wording and never marks anything verified.
"""
import argparse
import difflib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adapters  # noqa: E402
from adapters.common import norm, parse, sha256, squash  # noqa: E402,F401

UA = "ElementsStatuteChecker/1.0 (+https://github.com/bjsykes254/Elements; personal educational project)"
DELAY_SECONDS = 1.5


class FetchError(Exception):
    pass


class NotFound(Exception):
    pass


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
            name = url.rsplit("/", 1)[-1] if "sog.unc.edu" not in url else "sog_list.html"
            p = Path(offline_dir) / name
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


def source_path(base, jurisdiction, ad, url):
    """Where the saved text for a section lives, relative to the data file."""
    return "sources/%s/%s.txt" % (jurisdiction, ad.section_file_name(url))


def collect_sections(data, base):
    """url -> dict(cites, records, snapshot, last_sl, entries, missing_file)."""
    out = {}
    for o in data["offenses"]:
        for s in o.get("statutes", []):
            e = out.setdefault(s["url"], {"cites": set(), "records": [], "snapshot": None, "last_sl": None,
                                          "entries": [], "missing_file": None})
            e["cites"].add(s["cite"])
            e["records"].append(o["id"])
            e["entries"].append(s)
            sf = s.get("source_file")
            if sf and e["snapshot"] is None:
                p = Path(base) / sf
                if p.exists():
                    e["snapshot"] = p.read_text(encoding="utf-8")
                    e["last_sl"] = s.get("last_session_law_seen")
                else:
                    e["missing_file"] = sf
    return out


def run_check(data, fetch, base=".", pause=0.0, today=None):
    ad = adapters.load(data["meta"]["jurisdiction"])
    today = today or date.today().isoformat()
    res = {"date": today, "changed": [], "unchanged": [], "no_baseline": [], "errors": [],
           "articles": [], "articles_unchecked": [], "instructions": [], "instruction_notes": []}
    status_of = {o["id"]: o.get("review", {}).get("status", "draft") for o in data["offenses"]}
    for url, e in collect_sections(data, base).items():
        time.sleep(pause)
        label = "; ".join(sorted(e["cites"]))
        affects = ["%s (%s)" % (r, status_of[r]) for r in dict.fromkeys(e["records"])]
        if e["missing_file"]:
            res["errors"].append({"url": url, "what": "saved text file is missing: " + e["missing_file"]})
            continue
        try:
            text, history = ad.section_text(fetch(url))
        except NotFound:
            res["changed"].append({"url": url, "label": label, "affects": affects,
                                   "kind": "page not found: the section may have been renumbered or repealed", "diff": []})
            continue
        except (FetchError, ValueError) as ex:
            res["errors"].append({"url": url, "what": str(ex)})
            continue
        if not e["snapshot"]:
            res["no_baseline"].append({"url": url, "label": label, "affects": affects})
        elif ad.is_repealed(text):
            res["changed"].append({"url": url, "label": label, "affects": affects,
                                   "kind": "section now reads as repealed, reserved or transferred", "diff": [text[:300]]})
        elif squash(text) != squash(e["snapshot"]):
            res["changed"].append({"url": url, "label": label, "affects": affects, "kind": "text changed",
                                   "old_sl": e["last_sl"], "new_sl": ad.last_session_law(history),
                                   "diff": word_diff(norm(e["snapshot"]), text)})
        else:
            res["unchanged"].append({"url": url, "label": label})
    for art in data["meta"].get("watch_articles", ad.WATCH_ARTICLES):
        time.sleep(pause)
        try:
            heads = ad.article_headings(fetch(art["url"]))
        except (FetchError, NotFound, ValueError) as ex:
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
    if hasattr(ad, "check_secondary"):
        items, notes = ad.check_secondary(data, fetch, pause, errors=(FetchError, NotFound))
        res["instructions"], res["instruction_notes"] = items, notes
    return res


def exit_code(res):
    if res["changed"] or res["articles"] or res["instructions"]:
        return 1
    if res["errors"]:
        return 2
    return 0


def render(res, ad=None):
    L = ["# Statute check, %s" % res["date"], ""]
    n_changed = len(res["changed"]) + len(res["articles"]) + len(res["instructions"])
    L.append("**%d sections unchanged, %d need attention, %d could not be read.**" % (len(res["unchanged"]), n_changed, len(res["errors"])))
    if res["errors"]:
        L += ["", "> Some pages could not be read, so this check is incomplete. No news is not good news here."]
    if res["changed"]:
        L += ["", "## Sections that changed"]
        for c in res["changed"]:
            key = re.sub(r".*GS_(.*)\.html", r"\1", c["url"])
            L += ["", "### %s: %s" % (c["label"], c["kind"]), c["url"], "",
                  "Records that cite it: " + ", ".join(c["affects"])]
            if c.get("new_sl") and c.get("new_sl") != c.get("old_sl"):
                L.append("Latest session law in the history note: `%s` (was `%s`)" % (c["new_sl"], c.get("old_sl")))
            for d in c["diff"]:
                L.append("- " + d)
            L += ["", "Next: read the new text, edit the affected records to match, then run `py tools/check_statutes.py accept %s`." % key]
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
        L += ["", "## No saved text to compare with",
              "These sections haven't been read word for word yet, so there is nothing to compare:"]
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
    res = run_check(data, make_fetcher(a.offline_dir), base=Path(a.data).parent,
                    pause=0 if a.offline_dir else DELAY_SECONDS)
    report = render(res)
    if a.report:
        Path(a.report).write_text(report, encoding="utf-8")
    print(report)
    return exit_code(res)


def cmd_baseline(a):
    data = load(a.data)
    ad = adapters.load(data["meta"]["jurisdiction"])
    fetch = make_fetcher(a.offline_dir)
    arts = data["meta"].setdefault("watch_articles", [dict(x) for x in ad.WATCH_ARTICLES])
    for art in arts:
        heads = ad.article_headings(fetch(art["url"]))
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
    base = Path(a.data).parent
    ad = adapters.load(data["meta"]["jurisdiction"])
    jur = data["meta"]["jurisdiction"]
    secs = collect_sections(data, base)
    urls = [u for u in secs if ad.section_key(u) == a.section]
    if not urls:
        print("No record cites section %s." % a.section)
        return 1
    url = urls[0]
    text, history = ad.section_text(make_fetcher(a.offline_dir)(url))
    old = secs[url]["snapshot"]
    if old and squash(old) == squash(text):
        print("Saved text already matches the live page. Nothing to do.")
        return 0
    if old:
        print("\n".join(word_diff(norm(old), text)))
    ids = list(dict.fromkeys(secs[url]["records"]))
    verb = "refresh" if old else "save"
    print("\nThis will %s the text for %s in sources/ and note it on these records: %s" % (verb, a.section, ", ".join(ids)))
    if not a.yes and input("Continue? [y/N] ").strip().lower() != "y":
        print("Cancelled.")
        return 1
    sl, today = ad.last_session_law(history), date.today().isoformat()
    rel = source_path(base, jur, ad, url)
    out = base / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    # one paragraph per line is easier to read in Git; spacing never counts as a change
    out.write_text(text + "\n", encoding="utf-8", newline="\n")
    for s in secs[url]["entries"]:
        s.pop("text_snapshot", None)
        s.update(source_file=rel, text_captured_on=today, text_sha256=sha256(text), last_session_law_seen=sl)
    for o in data["offenses"]:
        if o["id"] in ids:
            r = o.setdefault("review", {})
            before = r.get("status", "draft")
            if old and before == "verified":
                r["status"] = "needs_review"
                r["verified_by"], r["verified_on"] = None, None
            r.setdefault("history", []).append({"on": today, "event": "saved text for G.S. %s %s; status was %s" % (a.section, "refreshed" if old else "captured", before)})
    save(a.data, data)
    print("Saved %s." % rel)
    if old:
        print("Edit the flagged records to match the new text, then verify them again.")
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
