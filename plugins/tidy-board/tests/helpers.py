import sys

sys.dont_write_bytecode = True  # never leave __pycache__ inside the plugin (it would ship with it)

import importlib.util
import os
import subprocess

os.environ.pop("CAPYBARA_LANG", None)  # the defaults the suite pins must not depend on the shell that runs it
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the plugin directory (plugins/tidy-board)
REPO = ROOT.parent.parent  # the marketplace repository root
SKILL_DIR = ROOT / "skills" / "tidy-board"
SCRIPT = SKILL_DIR / "scripts" / "tidy_board.py"
CAPY = SKILL_DIR / "scripts" / "capy_board.py"
ENGINE = REPO / "plugins" / "ar-board" / "skills" / "ar-board" / "scripts" / "ar_board.py"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tb = load_module(SCRIPT, "tidy_board")


def load_sync():
    return load_module(ROOT / "tools" / "sync.py", "tidy_board_sync")


def load_capy():
    """The vendored engine, to validate the batches the tool writes with the real `check`."""
    return load_module(CAPY, "capy_board")


def _env(date=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="Alice Example",
        GIT_AUTHOR_EMAIL="alice@example.com",
        GIT_COMMITTER_NAME="Alice Example",
        GIT_COMMITTER_EMAIL="alice@example.com",
    )
    if date:
        env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    return env


def git(repo, *args, date=None, input=None, check=True):
    r = subprocess.run(["git", "-C", str(repo), "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args],
                       env=_env(date), capture_output=True, text=True, input=input)
    if check and r.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {r.stderr}")
    return r.stdout


def init_repo(path, branch="main"):
    Path(path).mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", branch)
    return Path(path)


def commit(repo, message, files=None, date=None):
    """Commit `files` ({relative path: text}) and return the new commit id."""
    for rel, text in (files or {}).items():
        target = Path(repo) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        git(repo, "add", "--", rel)
    git(repo, "commit", "-q", "--allow-empty", "-m", message, date=date)
    return git(repo, "rev-parse", "HEAD").strip()
