import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import validate_data as vd  # noqa: E402


def data():
    return json.loads((ROOT / "elements-nc.json").read_text(encoding="utf-8"))


class ValidatorTests(unittest.TestCase):
    def test_real_data_is_clean(self):
        problems, _ = vd.validate(data())
        self.assertEqual(problems, [])

    def test_catches_unknown_element(self):
        d = data()
        d["offenses"][0]["elements"]["all_of"].append("no_such_element")
        self.assertTrue(any("unknown element" in p for p in vd.validate(d)[0]))

    def test_catches_edited_snapshot(self):
        d = data()
        s = d["offenses"][0]["statutes"][0]
        s["text_snapshot"] = s["text_snapshot"].replace("Class A", "Class B", 1)
        self.assertTrue(any("text_sha256" in p for p in vd.validate(d)[0]))

    def test_verified_needs_name_date_and_text(self):
        d = data()
        o = next(x for x in d["offenses"] if x["id"] == "nc_assault_simple")
        o["review"]["status"] = "verified"
        problems = vd.validate(d)[0]
        self.assertTrue(any("verified without" in p for p in problems))
        self.assertTrue(any("no saved text" in p for p in problems))

    def test_catches_bad_flow_result(self):
        d = data()
        d["flows"][0]["nodes"][d["flows"][0]["start"]]["options"][0].pop("next", None)
        d["flows"][0]["nodes"][d["flows"][0]["start"]]["options"][0]["result"] = "nope"
        self.assertTrue(any("not an offense" in p for p in vd.validate(d)[0]))

    def test_bad_status(self):
        d = data()
        d["offenses"][0]["review"]["status"] = "done"
        self.assertTrue(any("bad review status" in p for p in vd.validate(d)[0]))


if __name__ == "__main__":
    unittest.main()
