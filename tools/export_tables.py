#!/usr/bin/env python3
"""Flatten elements-nc.json into CSV tables you can open in a spreadsheet or Positron's Data Explorer.

  py tools/export_tables.py            writes exports/offenses.csv, exports/elements.csv, exports/offense_elements.csv

The tables are a read-only view. Edit elements-nc.json, then run this again. Uses only the standard library.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def write(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # BOM so Excel reads accents and quotes correctly
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main(argv):
    data_file = ROOT / (argv[1] if len(argv) > 1 else "elements-nc.json")
    d = json.loads(data_file.read_text(encoding="utf-8"))
    out = ROOT / "exports"
    out.mkdir(exist_ok=True)
    cats = {c["id"]: c for c in d["categories"]}
    els = {e["id"]: e for e in d["elements"]}

    def path_of(cat):
        names = []
        while cat:
            names.append(cats[cat]["name"])
            cat = cats[cat].get("parent")
        return " > ".join(reversed(names))

    used = {}
    long_rows = []
    off_rows = []
    for o in d["offenses"]:
        e = o["elements"]
        for i in e.get("all_of", []):
            long_rows.append([o["id"], o["name"], i, els[i]["name"], "required", ""])
            used[i] = used.get(i, 0) + 1
        for r in e.get("any_of_routes", []):
            for i in r["all_of"]:
                long_rows.append([o["id"], o["name"], i, els[i]["name"], "one route needed", r["route"]])
                used[i] = used.get(i, 0) + 1
        rv = o.get("review", {})
        st = o.get("statutes", [])
        off_rows.append([
            o["id"], o["name"], path_of(o["category"]), o["class"], o["grade"], rv.get("status", ""),
            "; ".join(s["cite"] for s in st), "; ".join(s.get("last_session_law_seen") or "" for s in st),
            len(e.get("all_of", [])), len(e.get("any_of_routes", [])), len(o.get("special_rules", [])),
            o["punishment_note"], o.get("explain_like_5", ""), "; ".join(o.get("aliases", [])),
            rv.get("statute_text_compared_on", ""), rv.get("comparison_note", ""),
            len(o.get("cross_checks", [])), rv.get("verified_by") or "", rv.get("verified_on") or "",
            " | ".join(o.get("special_rules", [])),
        ])
    write(out / "offenses.csv",
          ["id", "name", "where_in_statute_tree", "class", "grade", "review_status", "statutes", "last_session_law_seen",
           "required_elements", "route_groups", "special_rules", "punishment_note", "explain_like_5", "aliases",
           "text_compared_on", "comparison_note", "cross_checks", "verified_by", "verified_on", "special_rules_text"],
          off_rows)
    write(out / "elements.csv",
          ["id", "name", "plain", "source", "statute_cite", "note", "negates", "used_by_offenses"],
          [[e["id"], e["name"], e["plain"], e.get("source", ""), e.get("statute_cite", ""), e.get("note", ""),
            e.get("negates", ""), used.get(e["id"], 0)] for e in d["elements"]])
    write(out / "offense_elements.csv",
          ["offense_id", "offense_name", "element_id", "element_name", "role", "route"], long_rows)
    print(f"{len(off_rows)} offenses, {len(d['elements'])} elements, {len(long_rows)} offense-element links -> {out}")


if __name__ == "__main__":
    main(sys.argv)
