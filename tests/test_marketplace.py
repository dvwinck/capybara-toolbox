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

    def test_catalog_lists_every_plugin(self):
        market = json.loads((REPO / tool.MARKET).read_text(encoding="utf-8"))
        names = [p["name"] for p in market["plugins"]]
        self.assertEqual(names, ["ar-board", "publish-check", "tidy-board", "housekeeping"])

    def test_ci_runs_every_plugin_suite_and_sync_tool(self):
        ci = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("plugins/*/tests", ci)
        self.assertIn("plugins/*/tools/sync.py", ci)
        self.assertNotIn("plugins/ar-board/tests", ci)
        self.assertNotIn("plugins/ar-board/tools/sync.py", ci)

    def test_every_plugin_has_a_test_suite_a_sync_tool_and_both_readmes(self):
        for d in sorted((REPO / "plugins").iterdir()):
            with self.subTest(plugin=d.name):
                self.assertTrue((d / "tests").is_dir())
                self.assertTrue((d / "tools" / "sync.py").is_file())
                self.assertTrue((d / "README.md").is_file())
                self.assertTrue((d / "README.pt-BR.md").is_file())
                self.assertTrue((d / "CHANGELOG.md").is_file())

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
        for manifest_dir in sorted((REPO / "plugins").glob("*/.claude-plugin")):
            shutil.copytree(manifest_dir, self.root / manifest_dir.relative_to(REPO))

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
