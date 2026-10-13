import json
import tempfile
import unittest
from pathlib import Path

from helpers import pc


class LoadConfigTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def write(self, text, name=".publish-check.json"):
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_valid_config_returns_denylist_and_allow(self):
        path = self.write(json.dumps({"denylist": ["Acme"], "allow": ["0123456789abcdef"]}))
        self.assertEqual(pc.load_config(path), (["Acme"], ["0123456789abcdef"]))

    def test_missing_keys_default_to_empty(self):
        self.assertEqual(pc.load_config(self.write("{}")), ([], []))

    def test_unknown_keys_are_rejected(self):
        with self.assertRaisesRegex(pc.ScanError, "unknown keys deny"):
            pc.load_config(self.write(json.dumps({"deny": ["x"]})))

    def test_wrong_types_are_rejected(self):
        for body in ('{"denylist": "Acme"}', '{"allow": [1, 2]}', "[]"):
            with self.subTest(body=body):
                with self.assertRaises(pc.ScanError):
                    pc.load_config(self.write(body))

    def test_invalid_json_and_missing_file_are_errors(self):
        with self.assertRaisesRegex(pc.ScanError, "not valid JSON"):
            pc.load_config(self.write("{nope"))
        with self.assertRaisesRegex(pc.ScanError, "cannot read config"):
            pc.load_config(self.dir / "absent.json")

    def test_denylist_file_skips_blank_lines_and_comments(self):
        path = self.write("# internal names\nAcme\n\n  Zephyr  \n", "names.txt")
        self.assertEqual(pc.read_denylist_file(path), ["Acme", "Zephyr"])

    def test_missing_denylist_file_is_an_error(self):
        with self.assertRaisesRegex(pc.ScanError, "cannot read denylist"):
            pc.read_denylist_file(self.dir / "absent.txt")


if __name__ == "__main__":
    unittest.main()
