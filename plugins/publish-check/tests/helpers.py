import sys

sys.dont_write_bytecode = True  # never leave __pycache__ inside the plugin (it would ship with it)

import importlib.util
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the plugin directory (plugins/publish-check)
REPO = ROOT.parent.parent  # the marketplace repository root
SKILL_DIR = ROOT / "skills" / "publish-check"
SCRIPT = SKILL_DIR / "scripts" / "publish_check.py"

# Fixture leaks are assembled at run time so that scanning this very repository does not flag the tests.
LEAK_LINK = "https://claude." + "ai/code/session_FIXTURE123"
LEAK_PATH = "/Users/" + "fixtureuser"
LEAK_EMAIL = "fixture.person@" + "acme-fixture.dev"
LEAK_TERM = "Project-" + "Zephyr"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pc = load_module(SCRIPT, "publish_check")


def load_sync():
    return load_module(ROOT / "tools" / "sync.py", "publish_check_sync")


def _env(author=("Alice Example", "alice@example.com"), committer=None, date=None):
    committer = committer or author
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME=author[0],
        GIT_AUTHOR_EMAIL=author[1],
        GIT_COMMITTER_NAME=committer[0],
        GIT_COMMITTER_EMAIL=committer[1],
    )
    if date:
        env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    return env


def git(repo, *args, author=("Alice Example", "alice@example.com"), committer=None, date=None):
    r = subprocess.run(["git", "-C", str(repo), "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args],
                       env=_env(author, committer, date), capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {r.stderr}")
    return r.stdout


def init_repo(path):
    Path(path).mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    return Path(path)


def commit(repo, message, files=None, remove=(), author=("Alice Example", "alice@example.com"), committer=None,
           date=None):
    for rel, text in (files or {}).items():
        target = Path(repo) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        git(repo, "add", "--", rel)
    for rel in remove:
        git(repo, "rm", "-q", "--", rel)
    git(repo, "commit", "-q", "--allow-empty", "-m", message, author=author, committer=committer, date=date)
    return git(repo, "rev-parse", "HEAD").strip()
