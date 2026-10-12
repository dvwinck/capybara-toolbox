import contextlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT, load_sync

DIST = ["README.md", "SKILL.md", "install.sh", "CHECKSUMS.sha256", "scripts/ar_board.py", "examples/batch.example.json"]


def run_sync(sync, argv, root):
    with contextlib.redirect_stdout(io.StringIO()):
        return sync.main(argv, root=Path(root))


def copy_package(dest):
    for rel in DIST:
        (Path(dest) / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, Path(dest) / rel)


class PackageTest(unittest.TestCase):
    def test_repository_package_is_in_sync(self):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "sync.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_install_script_installs_identical_copy(self):
        with tempfile.TemporaryDirectory() as home:
            r = subprocess.run(["bash", str(ROOT / "install.sh")], env={**os.environ, "HOME": home}, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            installed = Path(home, ".claude", "ar-board", "ar_board.py").read_bytes()
            self.assertEqual(installed, (ROOT / "scripts" / "ar_board.py").read_bytes())

    def test_install_script_rejects_tampered_package(self):
        with tempfile.TemporaryDirectory() as pkg, tempfile.TemporaryDirectory() as home:
            copy_package(pkg)
            with open(Path(pkg, "README.md"), "a", encoding="utf-8") as f:
                f.write("\nadulterado\n")
            r = subprocess.run(["bash", str(Path(pkg, "install.sh"))], env={**os.environ, "HOME": home}, capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertFalse(Path(home, ".claude", "ar-board", "ar_board.py").exists())


class SyncToolTest(unittest.TestCase):
    def test_detects_drift_and_fixes_it(self):
        sync = load_sync()
        with tempfile.TemporaryDirectory() as tmp:
            copy_package(tmp)
            self.assertEqual(run_sync(sync, ["--check"], tmp), 0)
            with open(Path(tmp, "scripts", "ar_board.py"), "a", encoding="utf-8") as f:
                f.write("# marcador-de-teste\n")
            self.assertEqual(run_sync(sync, ["--check"], tmp), 1)
            self.assertEqual(run_sync(sync, [], tmp), 0)
            self.assertEqual(run_sync(sync, ["--check"], tmp), 0)
            self.assertIn("# marcador-de-teste", Path(tmp, "SKILL.md").read_text(encoding="utf-8"))

    def test_version_bump_propagates_but_history_rows_are_untouched(self):
        sync = load_sync()
        with tempfile.TemporaryDirectory() as tmp:
            copy_package(tmp)
            script = Path(tmp, "scripts", "ar_board.py")
            text = script.read_text(encoding="utf-8")
            text = re.sub(r"ar-board \d+\.\d+\.\d+", "ar-board 9.9.9", text)
            text = re.sub(r'VERSION = "\d+\.\d+\.\d+"', 'VERSION = "9.9.9"', text)
            script.write_text(text, encoding="utf-8")
            run_sync(sync, [], tmp)
            self.assertIn("ar-board 9.9.9", Path(tmp, "install.sh").read_text(encoding="utf-8"))
            readme = Path(tmp, "README.md").read_text(encoding="utf-8")
            self.assertIn("**Versão:** 9.9.9", readme)
            self.assertIn("| 1.0.2 |", readme)  # historico preservado
