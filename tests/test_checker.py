import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import check_statutes as cs  # noqa: E402
from adapters import nc  # noqa: E402
from adapters.common import norm, sha256, squash  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
URL18 = "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/Chapter_14/GS_14-18.html"
ART6 = "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/ByArticle/Chapter_14/Article_6.html"


def mini(snapshot_in=None, base=None):
    """A tiny data set with one verified offense. Writes the saved text into base/sources/NC/."""
    entry = {"cite": "G.S. 14-18", "url": URL18, "last_session_law_seen": "1997-443, s. 19.25(q)"}
    if snapshot_in is not None:
        p = Path(base) / "sources" / "NC" / "GS_14-18.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(snapshot_in, encoding="utf-8")
        entry["source_file"] = "sources/NC/GS_14-18.txt"
    return {"meta": {"jurisdiction": "NC", "watch_articles": []},
            "offenses": [{"id": "off_a", "review": {"status": "verified"}, "cross_checks": [], "statutes": [entry]}]}


def fetcher(pages):
    def f(url):
        if url not in pages:
            raise cs.FetchError("no page " + url)
        return pages[url]
    return f


class CheckerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.html18 = (FIX / "GS_14-18.html").read_text(encoding="utf-8")
        self.text18, self.hist18 = nc.section_text(self.html18)

    def tearDown(self):
        self.tmp.cleanup()

    def run_check(self, data, pages):
        return cs.run_check(data, fetcher(pages), base=self.base)

    def test_real_saved_text_matches_live_page_layout(self):
        # The text saved from the browser must equal what the parser reads from the same page.
        saved = (ROOT / "sources" / "NC" / "GS_14-18.txt").read_text(encoding="utf-8")
        self.assertEqual(squash(saved), squash(self.text18))
        data = json.loads((ROOT / "elements-nc.json").read_text(encoding="utf-8"))
        entry = next(s for o in data["offenses"] for s in o["statutes"] if s["url"] == URL18)
        self.assertEqual(sha256(saved), entry["text_sha256"])

    def test_session_law_parsed(self):
        self.assertEqual(nc.last_session_law(self.hist18), "1997-443, s. 19.25(q)")

    def test_unchanged(self):
        res = self.run_check(mini(self.text18, self.base), {URL18: self.html18})
        self.assertEqual((len(res["unchanged"]), len(res["changed"]), cs.exit_code(res)), (1, 0, 0))

    def test_spacing_and_line_breaks_do_not_count(self):
        spaced = self.text18.replace(". ", ".\n\n")
        res = self.run_check(mini(spaced, self.base), {URL18: self.html18})
        self.assertEqual(cs.exit_code(res), 0)

    def test_changed_text_is_reported_with_diff_and_records(self):
        html = self.html18.replace("Class D felony", "Class C felony")
        res = self.run_check(mini(self.text18, self.base), {URL18: html})
        self.assertEqual(cs.exit_code(res), 1)
        c = res["changed"][0]
        self.assertIn("off_a (verified)", c["affects"])
        self.assertTrue(any("[added: C]" in d and "[removed: D]" in d for d in c["diff"]))
        self.assertIn("[added: C]", cs.render(res))

    def test_repealed(self):
        html = '<html><body><p><a name="GSDocumentHeader"></a><span>&sect; 14-18. &nbsp;Repealed by Session Laws 2030, c. 1, s. 1.</span></p></body></html>'
        res = self.run_check(mini(self.text18, self.base), {URL18: html})
        self.assertEqual(cs.exit_code(res), 1)
        self.assertIn("repealed", res["changed"][0]["kind"])

    def test_page_not_found_counts_as_change(self):
        def f(url):
            raise cs.NotFound(url)
        res = cs.run_check(mini(self.text18, self.base), f, base=self.base)
        self.assertEqual(cs.exit_code(res), 1)

    def test_fetch_failure_is_incomplete_not_clean(self):
        res = self.run_check(mini(self.text18, self.base), {})
        self.assertEqual(cs.exit_code(res), 2)
        self.assertIn("incomplete", cs.render(res))

    def test_missing_saved_file_is_an_error(self):
        d = mini(self.text18, self.base)
        (self.base / "sources" / "NC" / "GS_14-18.txt").unlink()
        res = self.run_check(d, {URL18: self.html18})
        self.assertEqual(cs.exit_code(res), 2)

    def test_no_saved_text_is_listed_not_flagged(self):
        res = self.run_check(mini(None, self.base), {URL18: self.html18})
        self.assertEqual((len(res["no_baseline"]), cs.exit_code(res)), (1, 0))

    def test_article_headings_and_changes(self):
        html = (FIX / "Article_6.html").read_text(encoding="utf-8")
        heads = nc.article_headings(html)
        self.assertEqual(len(heads), 5)
        self.assertTrue(heads[0].startswith("§ 14-17."))
        d = mini(self.text18, self.base)
        d["meta"]["watch_articles"] = [{"label": "Art 6", "url": ART6, "headings": heads}]
        pages = {URL18: self.html18, ART6: html}
        self.assertEqual(cs.exit_code(self.run_check(d, pages)), 0)
        pages[ART6] = html.replace("</body>", '<p><span>&sect; 14-18.5. &nbsp;A new section.</span></p></body>')
        res = self.run_check(d, pages)
        self.assertEqual(cs.exit_code(res), 1)
        self.assertIn("14-18.5", res["articles"][0]["added"][0])

    def test_instruction_listing(self):
        html = ('<a href="/sites/default/files/pji-master-2025/criminal/214.10%20First%20Degree%20Burglary%20%5B2011%5D.pdf">x</a>'
                '<a href="/sites/default/files/pji-master-2025/criminal/206.10%20First%20Degree%20Murder%20%5B2020%5D.pdf">y</a>')
        self.assertEqual(sorted(nc.instruction_listing(html)), ["206.10", "214.10"])
        self.assertEqual(nc.instruction_number("216.05 Misdemeanor Larceny [2002].pdf"), "216.05")

    def test_section_key_and_file_name(self):
        self.assertEqual(nc.section_key(URL18), "14-18")
        self.assertEqual(nc.section_file_name(URL18), "GS_14-18")

    def test_accept_refreshes_saved_text_and_flags_records(self):
        data = mini(self.text18.replace("Class D", "Class C"), self.base)
        p = self.base / "d.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        pages = self.base / "pages"
        pages.mkdir()
        (pages / "GS_14-18.html").write_text(self.html18, encoding="utf-8")
        rc = cs.main(["--data", str(p), "--offline-dir", str(pages), "accept", "14-18", "--yes"])
        self.assertEqual(rc, 0)
        out = json.loads(p.read_text(encoding="utf-8"))
        r = out["offenses"][0]["review"]
        self.assertEqual(r["status"], "needs_review")
        self.assertIsNone(r.get("verified_by"))
        s = out["offenses"][0]["statutes"][0]
        self.assertEqual(s["source_file"], "sources/NC/GS_14-18.txt")
        self.assertEqual(squash((self.base / s["source_file"]).read_text(encoding="utf-8")), squash(self.text18))
        self.assertEqual(s["text_sha256"], sha256(self.text18))
        self.assertEqual(s["last_session_law_seen"], "1997-443, s. 19.25(q)")

    def test_accept_first_capture_creates_file_and_keeps_status(self):
        data = mini(None, self.base)
        data["offenses"][0]["review"]["status"] = "draft"
        p = self.base / "d.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        pages = self.base / "pages"
        pages.mkdir()
        (pages / "GS_14-18.html").write_text(self.html18, encoding="utf-8")
        self.assertEqual(cs.main(["--data", str(p), "--offline-dir", str(pages), "accept", "14-18", "--yes"]), 0)
        out = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(out["offenses"][0]["review"]["status"], "draft")
        self.assertTrue((self.base / "sources" / "NC" / "GS_14-18.txt").exists())


if __name__ == "__main__":
    unittest.main()
