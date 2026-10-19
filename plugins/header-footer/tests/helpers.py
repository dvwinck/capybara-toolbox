import sys

sys.dont_write_bytecode = True  # never leave __pycache__ inside the plugin (it would ship with it)

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent  # the plugin directory (plugins/header-footer)
REPO = ROOT.parent.parent  # the marketplace repository root
SKILL = ROOT / "skills" / "header-footer"
SCRIPT = SKILL / "scripts" / "header_footer.py"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_hf():
    return load_module(SCRIPT, "header_footer")


def load_sync():
    return load_module(ROOT / "tools" / "sync.py", "header_footer_sync")


class ConfigDirCase(unittest.TestCase):
    """Every test gets its own Claude config directory through CLAUDE_CONFIG_DIR."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        patcher = mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.home)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.hf = load_hf()

    def write_config(self, cfg):
        (self.home / "header-footer.json").write_text(json.dumps(cfg), encoding="utf-8")

    def read_json(self, name):
        return json.loads((self.home / name).read_text(encoding="utf-8"))

    def run_cli(self, *argv, stdin=""):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = self.hf.main(list(argv), stdin=io.StringIO(stdin))
        return rc, out.getvalue(), err.getvalue()


def run_like_a_windows_pipe(home, *argv, stdin=""):
    """Run the script as a hook does, with cp1252 stdio as on a Windows pipe. PYTHONIOENCODING stands in
    for the code page, so the script runs without -I here (-I would ignore the variable)."""
    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(home), PYTHONIOENCODING="cp1252", PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, str(SCRIPT), *argv], input=stdin.encode("utf-8"), capture_output=True, env=env)


class WindowsDatetime(datetime):
    """A datetime whose strftime rejects glibc/BSD extensions such as %-H, as Windows does; no format
    string is rejected on every platform, so the tests stand in for the strict one."""

    def strftime(self, fmt):
        if "%-" in fmt:
            raise ValueError("Invalid format string")
        return super().strftime(fmt)


def git_repo(path, branch="feature-x"):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    subprocess.run(["git", "init", "-q", "-b", branch, str(path)], check=True, env=env)
    return Path(path)


def strip_ansi(text):
    import re
    return re.sub(r"\x1b\[[0-9;]*m", "", text)
