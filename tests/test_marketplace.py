import contextlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("marketplace_tool", REPO / "tools" / "marketplace.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def run(argv, root):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = tool.main(argv, root=Path(root))
    return rc, out.getvalue()


class RealCatalogTest(unittest.TestCase):
    def test_catalog_is_in_sync(self):
        r = subprocess.run([sys.executable, str(REPO / "tools" / "marketplace.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_catalog_identity(self):
        market = json.loads((REPO / tool.MARKET).read_text(encoding="utf-8"))
        self.assertEqual(market["name"], "capybara-toolbox")
        self.assertIn("ar-board", [p["name"] for p in market["plugins"]])
        self.assertTrue((REPO / "LICENSE").exists())

    def test_catalog_has_no_unverifiable_fields(self):
        market = json.loads((REPO / tool.MARKET).read_text(encoding="utf-8"))
        self.assertNotIn("$schema", market)
        self.assertNotIn("version", market.get("metadata", {}))  # per-plugin versions live in the entries


class CatalogToolTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / ".claude-plugin").mkdir()
        shutil.copy2(REPO / tool.MARKET, self.root / tool.MARKET)
        shutil.copytree(REPO / "plugins" / "ar-board" / ".claude-plugin", self.root / "plugins" / "ar-board" / ".claude-plugin")

    def manifest(self):
        return self.root / "plugins" / "ar-board" / ".claude-plugin" / "plugin.json"

    def test_version_drift_is_detected_and_fixed(self):
        data = json.loads(self.manifest().read_text(encoding="utf-8"))
        data["version"] = "9.9.9"
        self.manifest().write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        self.assertEqual(run(["--check"], self.root)[0], 1)
        self.assertEqual(run([], self.root)[0], 0)
        self.assertEqual(run(["--check"], self.root)[0], 0)
        market = json.loads((self.root / tool.MARKET).read_text(encoding="utf-8"))
        self.assertEqual(market["plugins"][0]["version"], "9.9.9")

    def test_homepage_and_repository_are_synced_from_the_manifest(self):
        data = json.loads(self.manifest().read_text(encoding="utf-8"))
        data["homepage"] = "https://example.invalid/home"
        data["repository"] = "https://example.invalid/repo"
        self.manifest().write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        self.assertEqual(run(["--check"], self.root)[0], 1)
        self.assertEqual(run([], self.root)[0], 0)
        entry = json.loads((self.root / tool.MARKET).read_text(encoding="utf-8"))["plugins"][0]
        self.assertEqual(entry["homepage"], "https://example.invalid/home")
        self.assertEqual(entry["repository"], "https://example.invalid/repo")

    def test_plugin_directory_missing_from_catalog_is_reported(self):
        (self.root / "plugins" / "orphan").mkdir()
        rc, out = run(["--check"], self.root)
        self.assertEqual(rc, 1)
        self.assertIn("plugins/orphan", out)

    def test_missing_manifest_is_reported(self):
        self.manifest().unlink()
        rc, out = run(["--check"], self.root)
        self.assertEqual(rc, 1)
        self.assertIn("plugin.json not found", out)

    def test_name_mismatch_is_reported(self):
        data = json.loads(self.manifest().read_text(encoding="utf-8"))
        data["name"] = "something-else"
        self.manifest().write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        rc, out = run(["--check"], self.root)
        self.assertEqual(rc, 1)
        self.assertIn("something-else", out)
