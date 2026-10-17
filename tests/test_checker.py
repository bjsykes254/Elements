import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import check_statutes as cs  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
URL18 = "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/Chapter_14/GS_14-18.html"
ART6 = "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/ByArticle/Chapter_14/Article_6.html"


def real_data():
    return json.loads((ROOT / "elements-nc.json").read_text(encoding="utf-8"))


def mini(snapshot):
    return {"meta": {"watch_articles": []},
            "offenses": [{"id": "off_a", "review": {"status": "verified"}, "cross_checks": [],
                          "statutes": [{"cite": "G.S. 14-18", "url": URL18, "text_snapshot": snapshot,
                                        "last_session_law_seen": "1997-443, s. 19.25(q)"}]}]}


def fetcher(pages):
    def f(url):
        if url not in pages:
            raise cs.FetchError("no page " + url)
        return pages[url]
    return f


class CheckerTests(unittest.TestCase):
    def setUp(self):
        self.html18 = (FIX / "GS_14-18.html").read_text(encoding="utf-8")
        self.text18, self.hist18 = cs.section_text(self.html18)

    def test_real_snapshot_matches_live_page_layout(self):
        # The text saved from the browser must equal what this parser reads from the same page.
        snap = next(s["text_snapshot"] for o in real_data()["offenses"] for s in o["statutes"] if s["url"] == URL18)
        self.assertEqual(cs.squash(snap), cs.squash(self.text18))
        self.assertEqual(cs.sha256(snap), next(s["text_sha256"] for o in real_data()["offenses"] for s in o["statutes"] if s["url"] == URL18))

    def test_session_law_parsed(self):
        self.assertEqual(cs.last_session_law(self.hist18), "1997-443, s. 19.25(q)")

    def test_unchanged(self):
        res = cs.run_check(mini(self.text18), fetcher({URL18: self.html18}))
        self.assertEqual((len(res["unchanged"]), len(res["changed"]), cs.exit_code(res)), (1, 0, 0))

    def test_changed_text_is_reported_with_diff_and_records(self):
        html = self.html18.replace("Class D felony", "Class C felony")
        res = cs.run_check(mini(self.text18), fetcher({URL18: html}))
        self.assertEqual(cs.exit_code(res), 1)
        c = res["changed"][0]
        self.assertIn("off_a (verified)", c["affects"])
        self.assertTrue(any("[added: C]" in d and "[removed: D]" in d for d in c["diff"]))
        self.assertIn("[added: C]", cs.render(res))

    def test_repealed(self):
        html = '<html><body><p><a name="GSDocumentHeader"></a><span>&sect; 14-18. &nbsp;Repealed by Session Laws 2030, c. 1, s. 1.</span></p></body></html>'
        res = cs.run_check(mini(self.text18), fetcher({URL18: html}))
        self.assertEqual(cs.exit_code(res), 1)
        self.assertIn("repealed", res["changed"][0]["kind"])

    def test_page_not_found_counts_as_change(self):
        def f(url):
            raise cs.NotFound(url)
        res = cs.run_check(mini(self.text18), f)
        self.assertEqual(cs.exit_code(res), 1)

    def test_fetch_failure_is_incomplete_not_clean(self):
        res = cs.run_check(mini(self.text18), fetcher({}))
        self.assertEqual(cs.exit_code(res), 2)
        self.assertIn("incomplete", cs.render(res))

    def test_no_snapshot_is_listed_not_flagged(self):
        res = cs.run_check(mini(None), fetcher({URL18: self.html18}))
        self.assertEqual((len(res["no_baseline"]), cs.exit_code(res)), (1, 0))

    def test_article_headings_and_changes(self):
        html = (FIX / "Article_6.html").read_text(encoding="utf-8")
        heads = cs.article_headings(html)
        self.assertEqual(len(heads), 5)
        self.assertTrue(heads[0].startswith("§ 14-17."))
        d = mini(self.text18)
        d["meta"]["watch_articles"] = [{"label": "Art 6", "url": ART6, "headings": heads}]
        pages = {URL18: self.html18, ART6: html}
        self.assertEqual(cs.exit_code(cs.run_check(d, fetcher(pages))), 0)
        pages[ART6] = html.replace("</body>", '<p><span>&sect; 14-18.5. &nbsp;A new section.</span></p></body>')
        res = cs.run_check(d, fetcher(pages))
        self.assertEqual(cs.exit_code(res), 1)
        self.assertIn("14-18.5", res["articles"][0]["added"][0])

    def test_instruction_listing(self):
        html = ('<a href="/sites/default/files/pji-master-2025/criminal/214.10%20First%20Degree%20Burglary%20%5B2011%5D.pdf">x</a>'
                '<a href="/sites/default/files/pji-master-2025/criminal/206.10%20First%20Degree%20Murder%20%5B2020%5D.pdf">y</a>')
        found = cs.instruction_listing(html)
        self.assertEqual(sorted(found), ["206.10", "214.10"])
        self.assertEqual(cs.instruction_number("216.05 Misdemeanor Larceny [2002].pdf"), "216.05")

    def test_accept_updates_snapshot_and_flags_records(self):
        with tempfile.TemporaryDirectory() as td:
            data = mini(self.text18)
            data["offenses"][0]["statutes"][0]["text_snapshot"] = self.text18.replace("Class D", "Class C")
            p = Path(td) / "d.json"
            p.write_text(json.dumps(data), encoding="utf-8")
            off = Path(td) / "pages"
            off.mkdir()
            (off / "GS_14-18.html").write_text(self.html18, encoding="utf-8")
            rc = cs.main(["--data", str(p), "--offline-dir", str(off), "accept", "14-18", "--yes"])
            self.assertEqual(rc, 0)
            out = json.loads(p.read_text(encoding="utf-8"))
            r = out["offenses"][0]["review"]
            self.assertEqual(r["status"], "needs_review")
            self.assertIsNone(r.get("verified_by"))
            self.assertEqual(cs.squash(out["offenses"][0]["statutes"][0]["text_snapshot"]), cs.squash(self.text18))
            self.assertEqual(out["offenses"][0]["statutes"][0]["last_session_law_seen"], "1997-443, s. 19.25(q)")


if __name__ == "__main__":
    unittest.main()
