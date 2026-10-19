import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import validate_data as vd  # noqa: E402


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        shutil.copytree(ROOT / "sources", self.base / "sources")
        self.d = json.loads((ROOT / "elements-nc.json").read_text(encoding="utf-8"))

    def tearDown(self):
        self.tmp.cleanup()

    def problems(self):
        return vd.validate(self.d, self.base)[0]

    def test_real_data_is_clean(self):
        self.assertEqual(vd.validate(json.loads((ROOT / "elements-nc.json").read_text(encoding="utf-8")), ROOT)[0], [])

    def test_catches_unknown_element(self):
        self.d["offenses"][0]["elements"]["all_of"].append("no_such_element")
        self.assertTrue(any("unknown element" in p for p in self.problems()))

    def test_catches_edited_saved_text(self):
        f = self.base / "sources" / "NC" / "GS_14-17.txt"
        f.write_text(f.read_text(encoding="utf-8").replace("Class A", "Class B", 1), encoding="utf-8")
        self.assertTrue(any("text_sha256" in p for p in self.problems()))

    def test_catches_missing_saved_file(self):
        (self.base / "sources" / "NC" / "GS_14-17.txt").unlink()
        self.assertTrue(any("does not exist" in p for p in self.problems()))

    def test_text_must_not_sit_in_data_file(self):
        self.d["offenses"][0]["statutes"][0]["text_snapshot"] = "text"
        self.assertTrue(any("should live in sources" in p for p in self.problems()))

    def test_verified_needs_name_date_and_text(self):
        o = next(x for x in self.d["offenses"] if x["id"] == "nc_assault_simple")
        o["review"]["status"] = "verified"
        for st in o["statutes"]:
            st.pop("source_file", None)
            st.pop("text_sha256", None)
        problems = self.problems()
        self.assertTrue(any("verified without" in p for p in problems))
        self.assertTrue(any("no saved text" in p for p in problems))

    def test_catches_bad_flow_result(self):
        f = self.d["flows"][0]
        op = f["nodes"][f["start"]]["options"][0]
        op.pop("next", None)
        op["result"] = "nope"
        self.assertTrue(any("not an offense" in p for p in self.problems()))

    def test_catches_wrong_heading(self):
        self.d["offenses"][0]["statutes"][0]["heading"] = "Something the statute does not say"
        self.assertTrue(any("heading not found" in p for p in self.problems()))

    def test_bad_status(self):
        self.d["offenses"][0]["review"]["status"] = "done"
        self.assertTrue(any("bad review status" in p for p in self.problems()))


if __name__ == "__main__":
    unittest.main()
