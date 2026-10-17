"""North Carolina adapter: https://www.ncleg.gov General Statutes (one HTML page per section)."""
import re
import time
import urllib.parse

from .common import norm, parse

JURISDICTION = "NC"
SECTION_URL = "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/Chapter_14/GS_{section}.html"
SOG_LIST = ("https://www.sog.unc.edu/resources/microsites/north-carolina-pattern-jury-instructions/"
            "north-carolina-pattern-jury-instructions-criminal-cases")
WATCH_ARTICLES = [
    {"id": "art6", "label": "Chapter 14, Article 6 (Homicide)",
     "url": "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/ByArticle/Chapter_14/Article_6.html"},
    {"id": "art8", "label": "Chapter 14, Article 8 (Assaults)",
     "url": "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/ByArticle/Chapter_14/Article_8.html"},
    {"id": "art14", "label": "Chapter 14, Article 14 (Burglary and other housebreakings)",
     "url": "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/ByArticle/Chapter_14/Article_14.html"},
    {"id": "art16", "label": "Chapter 14, Article 16 (Larceny and related offenses)",
     "url": "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/ByArticle/Chapter_14/Article_16.html"},
]


def section_key(url):
    """'.../GS_14-52.html' -> '14-52' (used as the file name and in the accept command)."""
    m = re.search(r"GS_(.+)\.html$", url)
    return m.group(1) if m else url.rsplit("/", 1)[-1]


def section_file_name(url):
    """File name (without extension) for the saved text of a section."""
    return "GS_" + section_key(url)


def section_text(html):
    """Text of a single-section page, from the section heading through the history note."""
    p = parse(html)
    start = next((i for i, t in enumerate(p.paras) if t.startswith("§")), None)
    if start is None:
        raise ValueError("page has no section heading (unexpected layout)")
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
    return [norm(t)[:200] for t in parse(html).paras if t.startswith("§")]


def is_repealed(text):
    head = text[:160]
    return bool(re.match(r"§+\s*\d+[\w.\-]*(?:\s+through\s+\d+[\w.\-]*)?[.:]\s*"
                         r"(Repealed|Reserved|Expired|Recodified|Transferred)", head, re.I))


# ---- Pattern jury instructions (UNC School of Government), watched alongside the statutes ----

def instruction_number(name):
    m = re.match(r"(\d{3}(?:\.\d+[A-Za-z]*)?)\s", name)
    return m.group(1) if m else None


def instruction_listing(html):
    """Map instruction number -> file names found in the School of Government list."""
    found = {}
    for href in parse(html).links:
        if "pji-master" not in href or not href.lower().endswith(".pdf"):
            continue
        name = urllib.parse.unquote(href.rsplit("/", 1)[-1])
        n = instruction_number(name)
        if n:
            found.setdefault(n, []).append(name)
    return found


def check_secondary(data, fetch, pause=0.0, errors=(Exception,)):
    items, notes = [], []
    urls = {}
    for o in data["offenses"]:
        for c in o.get("cross_checks", []):
            if "pji-master" in c.get("url", ""):
                urls.setdefault(c["url"], []).append(o["id"])
    if not urls:
        return items, notes
    time.sleep(pause)
    try:
        listing = instruction_listing(fetch(SOG_LIST))
    except errors as ex:
        return items, ["Could not read the pattern jury instruction list: %s" % ex]
    total = sum(len(v) for v in listing.values())
    if total < 20:
        return items, ["The instruction list looked too short to trust (%d files); instruction check skipped." % total]
    for url, recs in urls.items():
        name = urllib.parse.unquote(url.rsplit("/", 1)[-1])
        num = instruction_number(name)
        if not num:
            continue
        current = listing.get(num)
        if current is None:
            items.append({"number": num, "records": sorted(set(recs)), "what": "no longer found in the list (renumbered or withdrawn?)"})
        elif name not in current:
            items.append({"number": num, "records": sorted(set(recs)), "what": "a different version is now listed: " + "; ".join(current)})
    return items, notes
