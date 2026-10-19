#!/usr/bin/env python3
"""Checks elements-nc.json for mistakes that would break the page or overstate what has been checked.

  py tools/validate_data.py            (uses elements-nc.json)
  py tools/validate_data.py other.json

Prints problems (exit code 1) and notes (do not fail). Standard library only.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

STATUSES = {"draft", "verified", "needs_review"}


def norm(s):
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def offense_elements(o):
    e = o["elements"]
    s = set(e.get("all_of", [])) | set(e.get("variant_b2_requires", []))
    for r in e.get("any_of_routes", []):
        s |= set(r["all_of"])
    return s


def validate(d, base="."):
    base = Path(base)
    problems, notes = [], []
    P = lambda *a: problems.append(" ".join(str(x) for x in a))
    N = lambda *a: notes.append(" ".join(str(x) for x in a))
    els = {}
    for e in d["elements"]:
        if e["id"] in els:
            P("duplicate element id", e["id"])
        els[e["id"]] = e
        if not e.get("plain"):
            P("element has no plain text", e["id"])
    cats = {c["id"] for c in d["categories"]}
    offs = {}
    for o in d["offenses"]:
        if o["id"] in offs:
            P("duplicate offense id", o["id"])
        offs[o["id"]] = o
    for o in d["offenses"]:
        oid = o["id"]
        if o["category"] not in cats:
            P("bad category", oid)
        for k in ("class", "grade", "jurisdiction", "punishment_note"):
            if not o.get(k):
                P("missing", k, oid)
        if not o.get("explain_like_5"):
            P("missing explain_like_5", oid)
        if not o.get("statutes"):
            P("no statutes", oid)
        for i in offense_elements(o):
            if i not in els:
                P("unknown element", oid, i)
        r = o.get("review", {})
        st = r.get("status")
        if st not in STATUSES:
            P("bad review status", oid, st)
        if st == "verified":
            if not r.get("verified_by") or not r.get("verified_on"):
                P("verified without verified_by/verified_on", oid)
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(r.get("verified_on"))):
                P("verified_on should look like 2026-10-17", oid)
        elif r.get("verified_by") or r.get("verified_on"):
            N("not verified but has verified_by/verified_on:", oid)
        for s in o.get("statutes", []):
            if not s.get("url", "").startswith("https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/"):
                P("statute url not on ncleg.gov", oid, s.get("cite"))
            if s.get("text_snapshot"):
                P("text_snapshot should live in sources/, not in the data file", oid, s.get("cite"))
            sf = s.get("source_file")
            if sf:
                path = base / sf
                if not path.exists():
                    P("source_file does not exist", oid, sf)
                else:
                    snap = path.read_text(encoding="utf-8")
                    if hashlib.sha256(norm(snap).encode("utf-8")).hexdigest() != s.get("text_sha256"):
                        P("saved text does not match text_sha256", oid, sf)
                    if s.get("heading") and s["heading"] not in norm(snap):
                        P("statute heading not found in saved text", oid, s.get("cite"))
                    sl = s.get("last_session_law_seen")
                    if not sl:
                        P("saved text without last_session_law_seen", oid, s.get("cite"))
                    elif sl not in snap:
                        P("last_session_law_seen not found in saved text", oid, s.get("cite"), sl)
                    if not s.get("text_captured_on"):
                        P("saved text without text_captured_on", oid, s.get("cite"))
            elif st == "verified":
                P("verified but statute has no saved text", oid, s.get("cite"))
        for c in o.get("cross_checks", []):
            for k in ("label", "url", "checked_on", "note"):
                if not c.get(k):
                    P("cross_check missing", k, oid)
    for e in d["elements"]:
        if "negates" in e and e["negates"] not in els:
            P("bad negates", e["id"])
        for i in e.get("implies", []):
            if i not in els:
                P("bad implies", e["id"], i)
    used = set()
    for o in d["offenses"]:
        used |= offense_elements(o)
    for f in d["flows"]:
        for n in f["nodes"].values():
            for op in n["options"]:
                used.add(op["adds_element"])
    for i in els:
        if i not in used:
            N("element not used by any offense or flow:", i)
    for p in d["compare_presets"]:
        for i in p["ids"]:
            if i not in offs:
                P("bad compare preset", p["label"], i)

    def covers(pk, oe):
        if pk in oe or any(i in oe for i in els[pk].get("implies", [])):
            return True
        return any(pk in els[x].get("implies", []) for x in oe)

    reached = set()

    def walk(flow, nid, picks, seen):
        node = flow["nodes"].get(nid)
        if node is None:
            P("flow", flow["id"], "missing node", nid)
            return
        if nid in seen:
            P("flow", flow["id"], "cycle at", nid)
            return
        for op in node["options"]:
            if op["adds_element"] not in els:
                P("flow", flow["id"], "unknown element", op["adds_element"])
                continue
            p = picks + [op["adds_element"]]
            if "next" in op:
                walk(flow, op["next"], p, seen | {nid})
                continue
            res = op.get("result")
            if res not in offs:
                P("flow", flow["id"], "result is not an offense:", res)
                continue
            reached.add(res)
            oe = offense_elements(offs[res])
            for pk in p:
                if "negates" not in els[pk] and not covers(pk, oe):
                    P("flow", flow["id"], "pick", pk, "is not an element of", res)

    for f in d["flows"]:
        walk(f, f["start"], [], set())
    for oid in sorted(set(offs) - reached):
        N("offense not reachable in Build mode (compare and find only):", oid)
    for a in d.get("meta", {}).get("watch_articles", []):
        if not a.get("headings"):
            N("watched article has no baseline yet:", a.get("label"))
    return problems, notes


def main(argv):
    path = Path(argv[1] if len(argv) > 1 else "elements-nc.json")
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception as ex:
        print("PROBLEM: file is not valid JSON:", ex)
        return 1
    problems, notes = validate(d, path.parent)
    print("%d offenses, %d elements, %d flows" % (len(d["offenses"]), len(d["elements"]), len(d["flows"])))
    by = {}
    for o in d["offenses"]:
        by.setdefault(o.get("review", {}).get("status", "?"), []).append(o["id"])
    print("review status:", ", ".join("%s %d" % (k, len(v)) for k, v in sorted(by.items())))
    for n in notes:
        print("note:", n)
    for p in problems:
        print("PROBLEM:", p)
    print("OK" if not problems else "%d problem(s)" % len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
