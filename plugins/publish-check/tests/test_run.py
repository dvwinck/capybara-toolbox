import json
import tempfile
import unittest
from pathlib import Path

from helpers import LEAK_EMAIL, LEAK_TERM, commit, init_repo, pc


class RunTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.repo = init_repo(self.tmp / "repo")
        commit(self.repo, "initial", {"a.txt": f"mail {LEAK_EMAIL}\nthe {LEAK_TERM} plan\n"})

    def run_cli(self, *argv):
        return pc.run(pc.parser().parse_args([str(self.repo), *argv]))

    def test_findings_without_any_config(self):
        report = self.run_cli()
        self.assertEqual(report["counts"]["email"], 2)  # once in the tree, once in the patch that added it
        self.assertFalse(report["clean"])

    def test_config_in_the_repository_is_discovered_and_adds_the_denylist(self):
        (self.repo / pc.CONFIG_NAME).write_text(json.dumps({"denylist": [LEAK_TERM]}), encoding="utf-8")
        report = self.run_cli()
        self.assertGreater(report["counts"]["denylist"], 0)

    def test_allow_list_removes_exactly_the_accepted_findings(self):
        before = self.run_cli()
        accepted = [f["fingerprint"] for f in before["findings"] if f["category"] == "email"]
        cfg = self.tmp / "accept.json"
        cfg.write_text(json.dumps({"allow": accepted}), encoding="utf-8")
        after = self.run_cli("--config", str(cfg))
        self.assertEqual(after["counts"]["email"], 0)
        self.assertEqual(after["allowed"], len(accepted))
        self.assertEqual(len(after["findings"]), len(before["findings"]) - len(accepted))

    def test_denylist_file_outside_the_repository(self):
        names = self.tmp / "names.txt"
        names.write_text(LEAK_TERM + "\n", encoding="utf-8")
        report = self.run_cli("--denylist", str(names))
        self.assertGreater(report["counts"]["denylist"], 0)

    def test_explicit_config_that_does_not_exist_is_an_error(self):
        with self.assertRaises(pc.ScanError):
            self.run_cli("--config", str(self.tmp / "absent.json"))


if __name__ == "__main__":
    unittest.main()
