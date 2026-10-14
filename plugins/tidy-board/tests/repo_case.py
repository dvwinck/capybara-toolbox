import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import commit, git, init_repo, tb


class RepoCase(unittest.TestCase):
    """A throwaway repository on `main` with one commit, plus builders for the situations the board meets."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()  # git reports real paths (/private/var on macOS)
        self.repo = init_repo(self.tmp / "r")
        commit(self.repo, "init", {"a.txt": "one\n"})

    def work(self, name, files, message="work", date=None):
        """A branch with one commit, left unmerged; back on main afterwards."""
        git(self.repo, "checkout", "-q", "-b", name)
        sha = commit(self.repo, message, files, date=date)
        git(self.repo, "checkout", "-q", "main")
        return sha

    def inv(self, gh="off"):
        return tb.inventory(self.repo, tb.detect_base(self.repo), gh)

    def by_name(self, inv=None):
        return {i["name"]: i for i in (inv or self.inv())["items"]}

    def gh_calls(self):
        return len(self.gh_log.read_text().splitlines()) if self.gh_log.exists() else 0

    def fake_gh(self, payload, exit_code=0):
        """Put a `gh` on PATH that prints `payload` as the merged-PR list (and logs each call)."""
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir(exist_ok=True)
        data = self.tmp / "gh.json"
        data.write_text(json.dumps(payload), encoding="utf-8")
        script = bin_dir / "gh"
        self.gh_log = self.tmp / "gh.log"
        script.write_text(f"#!/bin/sh\necho call >> '{self.gh_log}'\ncat '{data}'\nexit {exit_code}\n", encoding="utf-8")
        script.chmod(0o755)
        patcher = mock.patch.dict(os.environ, {"PATH": str(bin_dir) + os.pathsep + os.environ["PATH"]})
        patcher.start()
        self.addCleanup(patcher.stop)
