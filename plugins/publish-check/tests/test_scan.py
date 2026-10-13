import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import LEAK_EMAIL, LEAK_LINK, LEAK_PATH, LEAK_TERM, commit, git, init_repo, pc


class RepoCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = init_repo(Path(tmp.name) / "repo")

    def scan(self, denylist=(), **kw):
        findings, stats = pc.scan(self.repo, list(denylist), **kw)
        return findings, stats

    def where(self, findings, where):
        return [f for f in findings if f["where"] == where]


class TreeScanTest(RepoCase):
    def test_tracked_file_leak_is_found_with_file_and_line(self):
        commit(self.repo, "add notes", {"notes.md": f"intro\ncontact {LEAK_EMAIL}\n"})
        findings, stats = self.scan()
        tree = self.where(findings, "tree")
        self.assertEqual([(f["category"], f["location"]) for f in tree], [("email", "notes.md:2")])
        self.assertEqual(stats["files"], 1)

    def test_untracked_but_not_ignored_file_is_scanned_and_ignored_file_is_not(self):
        commit(self.repo, "base", {".gitignore": "secret.txt\n", "ok.txt": "fine\n"})
        (self.repo / "new.txt").write_text(f"path {LEAK_PATH}/x\n", encoding="utf-8")
        (self.repo / "secret.txt").write_text(f"mail {LEAK_EMAIL}\n", encoding="utf-8")
        findings, _ = self.scan()
        self.assertEqual([f["location"] for f in self.where(findings, "tree")], ["new.txt:1"])

    def test_clean_repository_has_no_findings(self):
        commit(self.repo, "clean\n\nCo-Authored-By: Claude <noreply@anthropic.com>", {"a.txt": "hello\n"})
        findings, stats = self.scan()
        self.assertEqual(findings, [])
        self.assertEqual(stats, {"files": 1, "commits": 1, "skipped": 0})


class HistoryScanTest(RepoCase):
    def test_leak_only_in_an_old_commit_message_is_found(self):
        commit(self.repo, f"first\n\nsee {LEAK_LINK}", {"a.txt": "one\n"})
        commit(self.repo, "second", {"a.txt": "two\n"})
        findings, stats = self.scan()
        msgs = self.where(findings, "commit-message")
        self.assertEqual([f["category"] for f in msgs], ["session-link"])
        self.assertRegex(msgs[0]["location"], r"^[0-9a-f]{7} message line 3$")
        self.assertEqual(stats["commits"], 2)

    def test_author_and_committer_fields_are_scanned_separately(self):
        commit(self.repo, "by two people", {"a.txt": "x\n"},
               author=("Pat Author", LEAK_EMAIL), committer=("Chris Committer", "chris@" + "other-fixture.dev"))
        findings, _ = self.scan()
        self.assertEqual([f["location"].split()[1] for f in self.where(findings, "commit-author")], ["author"])
        self.assertEqual([f["location"].split()[1] for f in self.where(findings, "commit-committer")], ["committer"])

    def test_same_author_and_committer_is_reported_once(self):
        commit(self.repo, "solo", {"a.txt": "x\n"}, author=("Pat", LEAK_EMAIL))
        findings, _ = self.scan()
        self.assertEqual(len(self.where(findings, "commit-author")), 1)
        self.assertEqual(self.where(findings, "commit-committer"), [])

    def test_leak_added_then_removed_is_found_in_the_patch(self):
        commit(self.repo, "add", {"conf.txt": f"ok\nhome={LEAK_PATH}\n"})
        commit(self.repo, "remove it", {"conf.txt": "ok\n"})
        findings, _ = self.scan()
        self.assertEqual(self.where(findings, "tree"), [])
        patches = self.where(findings, "patch")
        self.assertEqual([f["category"] for f in patches], ["home-path"])
        self.assertRegex(patches[0]["location"], r"^[0-9a-f]{7} conf\.txt:2$")

    def test_other_branches_are_scanned(self):
        commit(self.repo, "main work", {"a.txt": "x\n"})
        git(self.repo, "checkout", "-q", "-b", "feature")
        commit(self.repo, f"feature {LEAK_EMAIL}", {"b.txt": "y\n"})
        git(self.repo, "checkout", "-q", "main")
        findings, _ = self.scan()
        self.assertEqual([f["category"] for f in self.where(findings, "commit-message")], ["email"])

    def test_annotated_tag_message_is_scanned_but_lightweight_tags_are_not(self):
        commit(self.repo, "release", {"a.txt": "x\n"})
        git(self.repo, "tag", "-a", "v1", "-m", f"release notes {LEAK_LINK}")
        git(self.repo, "tag", "light")
        findings, _ = self.scan()
        tags = self.where(findings, "tag")
        self.assertEqual([(f["category"], f["location"]) for f in tags], [("session-link", "tag v1")])

    def test_denylist_terms_are_found_everywhere(self):
        commit(self.repo, f"about {LEAK_TERM}", {"a.txt": f"{LEAK_TERM.lower()} notes\n"})
        findings, _ = self.scan(denylist=[LEAK_TERM])
        self.assertEqual({f["where"] for f in findings if f["category"] == "denylist"},
                         {"tree", "commit-message", "patch"})

    def test_max_commits_and_since_limit_the_history(self):
        commit(self.repo, f"old {LEAK_EMAIL}", {"a.txt": "1\n"}, date="2020-01-01T00:00:00")
        commit(self.repo, "new", {"a.txt": "2\n"}, date="2024-01-01T00:00:00")
        full, stats = self.scan()
        self.assertEqual(len(self.where(full, "commit-message")), 1)
        self.assertEqual(stats["commits"], 2)
        limited, stats = self.scan(max_commits=1)
        self.assertEqual(self.where(limited, "commit-message"), [])
        self.assertEqual(stats["commits"], 1)
        recent, stats = self.scan(since="2022-01-01")
        self.assertEqual(self.where(recent, "commit-message"), [])
        self.assertEqual(stats["commits"], 1)


class RobustnessTest(RepoCase):
    def test_a_repository_without_commits_still_scans_the_tree(self):
        (self.repo / "draft.txt").write_text(f"mail {LEAK_EMAIL}\n", encoding="utf-8")
        findings, stats = self.scan()
        self.assertEqual([f["where"] for f in findings], ["tree"])
        self.assertEqual(stats["commits"], 0)

    def test_text_that_is_not_utf8_is_scanned_not_fatal(self):
        commit(self.repo, "base", {"ok.txt": "fine\n"})
        (self.repo / "latin1.txt").write_bytes(b"caf\xe9 mail " + LEAK_EMAIL.encode() + b"\n")
        findings, _ = self.scan()
        self.assertEqual([f["location"] for f in findings if f["where"] == "tree"], ["latin1.txt:1"])

    def test_paths_with_spaces_and_accents_are_reported_correctly(self):
        commit(self.repo, "add", {"dir with space/a\u00e7\u00e3o.txt": f"mail {LEAK_EMAIL}\n"})
        findings, _ = self.scan()
        self.assertEqual([f["location"] for f in self.where(findings, "tree")], ["dir with space/a\u00e7\u00e3o.txt:1"])
        patch = self.where(findings, "patch")
        self.assertRegex(patch[0]["location"], r"^[0-9a-f]{7} dir with space/a\u00e7\u00e3o\.txt:1$")

    def test_a_shallow_clone_is_detected(self):
        commit(self.repo, "one", {"a.txt": "1\n"})
        commit(self.repo, "two", {"a.txt": "2\n"})
        self.assertFalse(pc.is_shallow(self.repo))
        with tempfile.TemporaryDirectory() as d:
            clone = Path(d) / "clone"
            git(self.repo, "clone", "-q", "--depth", "1", "file://" + str(self.repo), str(clone))
            self.assertTrue(pc.is_shallow(clone))


class AdversarialInputTest(RepoCase):
    """Content written by a malicious committer must not make the scan skip or misread anything."""

    def test_added_lines_that_look_like_diff_headers_are_still_scanned(self):
        commit(self.repo, "add", {"a.txt": f"ok\n++ b/other.txt\n++ mail {LEAK_EMAIL}\n+++ mail {LEAK_EMAIL}\n"})
        findings, _ = self.scan()
        patches = self.where(findings, "patch")
        self.assertEqual(len(patches), 2)
        self.assertTrue(all(f["location"].endswith(" a.txt:" + n) for f, n in zip(patches, ("3", "4"))),
                        [f["location"] for f in patches])

    def test_record_separator_characters_in_a_message_do_not_hide_later_text(self):
        commit(self.repo, "one\x1e two\x1f three\n\n" + f"see {LEAK_EMAIL}", {"a.txt": "x\n"})
        findings, stats = self.scan()
        self.assertEqual([f["category"] for f in self.where(findings, "commit-message")], ["email"])
        self.assertEqual(stats["commits"], 1)

    def test_a_git_failure_is_an_error_not_a_clean_scan(self):
        sha = commit(self.repo, "add", {"a.txt": "hello\n"})
        blob = git(self.repo, "rev-parse", "HEAD:a.txt").strip()
        os.remove(self.repo / ".git" / "objects" / blob[:2] / blob[2:])
        with self.assertRaises(pc.ScanError):
            self.scan()

    def test_a_hostile_repository_config_cannot_run_programs(self):
        marker = self.repo.parent / "PWNED"
        hook = self.repo.parent / "hook.sh"
        hook.write_text(f"#!/bin/sh\ntouch '{marker}'\nprintf '\\0'\n", encoding="utf-8")
        hook.chmod(0o755)
        commit(self.repo, "base", {"a.txt": "x\n"})
        git(self.repo, "config", "core.fsmonitor", str(hook))
        self.scan()
        self.assertFalse(marker.exists(), "scanning ran a program named by the repository's own config")

    def test_files_that_cannot_be_scanned_are_counted_not_ignored(self):
        commit(self.repo, "base", {"ok.txt": "fine\n"})
        (self.repo / "blob.bin").write_bytes(b"\0\1\2" + LEAK_EMAIL.encode())
        (self.repo / "big.txt").write_text(LEAK_EMAIL + "\n" + "x" * 2000, encoding="utf-8")
        with mock.patch.object(pc, "MAX_FILE_BYTES", 1000):
            findings, stats = self.scan()
        self.assertEqual(self.where(findings, "tree"), [])
        self.assertEqual(stats["skipped"], 2)
        self.assertEqual(stats["files"], 1)


class FingerprintAcrossCommitsTest(RepoCase):
    def fingerprints(self, findings, where):
        return {f["fingerprint"] for f in self.where(findings, where)}

    def test_the_same_author_in_many_commits_is_one_fingerprint(self):
        for i in range(3):
            commit(self.repo, f"change {i}", {"a.txt": f"{i}\n"}, author=("Pat", LEAK_EMAIL))
        findings, _ = self.scan()
        self.assertEqual(len(self.where(findings, "commit-author")), 3)
        self.assertEqual(len(self.fingerprints(findings, "commit-author")), 1)

    def test_the_same_value_added_to_the_same_file_twice_is_one_fingerprint(self):
        commit(self.repo, "one", {"conf.txt": f"mail {LEAK_EMAIL}\n"})
        commit(self.repo, "two", {"conf.txt": f"mail {LEAK_EMAIL}\nmore\n"})
        commit(self.repo, "three", {"conf.txt": f"more\nmail {LEAK_EMAIL}\nagain\n"})
        findings, _ = self.scan()
        self.assertGreater(len(self.where(findings, "patch")), 1)
        self.assertEqual(len(self.fingerprints(findings, "patch")), 1)

    def test_a_new_value_or_a_new_file_is_a_new_fingerprint(self):
        commit(self.repo, "one", {"a.txt": f"mail {LEAK_EMAIL}\n"})
        commit(self.repo, "two", {"b.txt": f"mail {LEAK_EMAIL}\n"})
        commit(self.repo, "three", {"c.txt": "mail other.person@" + "acme-fixture.dev\n"})
        findings, _ = self.scan()
        self.assertEqual(len(self.fingerprints(findings, "patch")), 3)

    def test_dependabot_trailers_are_not_findings(self):
        commit(self.repo, "bump\n\nSigned-off-by: dependabot[bot] <support@github.com>", {"a.txt": "x\n"})
        findings, _ = self.scan()
        self.assertEqual(findings, [])


class RepoRootTest(unittest.TestCase):
    def test_a_directory_that_is_not_a_repository_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(pc.ScanError):
                pc.repo_root(Path(d))

    def test_a_subdirectory_resolves_to_the_repository_root(self):
        with tempfile.TemporaryDirectory() as d:
            repo = init_repo(Path(d) / "r")
            (repo / "sub").mkdir()
            self.assertEqual(pc.repo_root(repo / "sub").resolve(), repo.resolve())


if __name__ == "__main__":
    unittest.main()
