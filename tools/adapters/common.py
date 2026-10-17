"""Helpers shared by every state adapter."""
import hashlib
import re
from html.parser import HTMLParser


def norm(s):
    """Collapse all whitespace (including non-breaking spaces) to single spaces."""
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def squash(s):
    """Remove all whitespace, so spacing differences never count as a change."""
    return re.sub(r"\s+", "", s)


def sha256(s):
    return hashlib.sha256(norm(s).encode("utf-8")).hexdigest()


class PageParser(HTMLParser):
    """Turns an HTML page into a list of paragraphs, and collects links and history notes."""
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
