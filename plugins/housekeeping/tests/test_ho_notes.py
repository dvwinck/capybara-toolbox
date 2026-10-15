import os
import stat
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from helpers import commit, git, init_repo, load_handoff

ho = load_handoff()
FULL = """## O que foi feito
Fixed `commit:%s` and edited `file:src/a.py`.

## Decisoes e por que
Kept `branch:main`; rejected `branch:ghost`.

## Proximos passos
Write `file:docs/missing.md`.

## O que falhou ou travou
Nothing.
"""


class NoteCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.repo = init_repo(self.tmp / "r")
        self.first = commit(self.repo, "first", {"src/a.py": "one\n"})
        self.clock = mock.patch.object(ho, "NOW", lambda: time.struct_time((2026, 10, 14, 9, 5, 7, 2, 287, -1)))
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def draft(self):
        return FULL % self.first[:7]

    def write(self, draft=None, **kw):
        return ho.write_note(self.repo, self.draft() if draft is None else draft, **kw)


class WriteTest(NoteCase):
    def test_the_note_is_saved_with_the_git_section_the_draft_and_a_data_block(self):
        res = self.write()
        text = Path(res["path"]).read_text(encoding="utf-8")
        self.assertEqual(Path(res["path"]).name, "2026-10-14-090507.md")
        self.assertEqual(Path(res["path"]).parent, self.repo / ".handoff")
        self.assertTrue(text.startswith("# Handoff - 2026-10-14 09:05 - main\n\n## Estado do git\n"))
        self.assertIn(f"- Branch: main, ponta {self.first[:7]}", text)
        self.assertIn("- Em relacao a base main: 0 a frente, 0 atras", text)
        self.assertIn("## Decisoes e por que", text)
        self.assertEqual(ho.parse_data(text)["facts"]["tip"], self.first)

    def test_every_word_of_the_draft_survives_and_only_failures_are_marked(self):
        res = self.write()
        text = Path(res["path"]).read_text(encoding="utf-8")
        self.assertIn("`branch:ghost` [nao verificado]", text)
        self.assertIn("`file:docs/missing.md` [nao verificado]", text)
        self.assertNotIn("`branch:main` [nao verificado]", text)
        stripped = text.replace(" [nao verificado]", "")
        for line in self.draft().strip("\n").splitlines():
            self.assertIn(line, stripped)
        self.assertEqual([(c["value"], c["verified"]) for c in res["citations"]],
                         [(self.first[:7], True), ("src/a.py", True), ("main", True), ("ghost", False), ("docs/missing.md", False)])

    def test_missing_sections_are_reported_not_invented(self):
        res = self.write(draft="## O que foi feito\nOnly this.\n")
        self.assertEqual(res["missing"], ["Decisoes e por que", "Proximos passos", "O que falhou ou travou"])
        self.assertNotIn("Proximos passos", Path(res["path"]).read_text(encoding="utf-8"))

    def test_the_note_is_private(self):
        mode = stat.S_IMODE(os.stat(self.write()["path"]).st_mode)
        self.assertEqual(mode, 0o600)

    def test_two_notes_in_the_same_second_never_share_a_file(self):
        names = [Path(self.write()["path"]).name for _ in range(3)]
        self.assertEqual(names, ["2026-10-14-090507.md", "2026-10-14-090507-2.md", "2026-10-14-090507-3.md"])

    def test_a_custom_folder_is_created(self):
        res = self.write(out_dir=str(self.tmp / "notes" / "deep"))
        self.assertEqual(Path(res["path"]).parent, self.tmp / "notes" / "deep")

    def test_a_commit_subject_that_could_end_an_html_comment_round_trips(self):
        commit(self.repo, "tricky --> subject -- with dashes", {"b.txt": "b\n"})
        res = self.write()
        text = Path(res["path"]).read_text(encoding="utf-8")
        self.assertEqual(text.count("-->"), 1 + text.count("-->") - 1)  # only the real closing one is in the data block
        data_line = [l for l in text.splitlines() if l.startswith("<!-- handoff:data")][0]
        self.assertEqual(data_line.count("-->"), 1)
        self.assertEqual(ho.parse_data(text)["facts"]["commits"][0]["subject"], "tricky --> subject -- with dashes")

    def test_a_corrupt_data_block_is_ignored(self):
        self.assertIsNone(ho.parse_data("<!-- handoff:data {not json} -->"))
        self.assertIsNone(ho.parse_data("no block"))
        self.assertIsNone(ho.parse_data('<!-- handoff:data {"x":1} -->'))

    def test_the_git_section_has_no_backtick_spans_so_it_is_never_mistaken_for_citations(self):
        (self.repo / "new.txt").write_text("x\n", encoding="utf-8")
        text = Path(self.write()["path"]).read_text(encoding="utf-8")
        section = text.split("## O que foi feito")[0]
        self.assertNotIn("`", section)
        self.assertIn("- Arquivos novos (nao rastreados): 1 (new.txt)", section)

    def test_a_long_list_of_files_is_cut(self):
        for i in range(12):
            (self.repo / f"n{i:02}.txt").write_text("x\n", encoding="utf-8")
        text = Path(self.write()["path"]).read_text(encoding="utf-8")
        self.assertIn("e mais 4)", text)


class SymlinkedFolderTest(NoteCase):
    def link_notes_folder(self):
        outside = self.tmp / "elsewhere"
        outside.mkdir()
        os.symlink(outside, self.repo / ".handoff")
        return outside

    def test_a_notes_folder_that_is_a_symlink_is_never_written_through(self):
        outside = self.link_notes_folder()
        with self.assertRaises(ho.HandoffError) as ctx:
            self.write()
        self.assertIn("link simbolico", str(ctx.exception))
        self.assertEqual(list(outside.iterdir()), [])

    def test_a_notes_folder_that_is_a_symlink_is_never_read_either(self):
        outside = self.link_notes_folder()
        (outside / "2026-10-14-090507.md").write_text("# planted\n", encoding="utf-8")
        with self.assertRaises(ho.HandoffError):
            ho.resume(self.repo)

    def test_an_explicit_out_folder_is_the_persons_choice(self):
        outside = self.tmp / "chosen"
        outside.mkdir()
        res = self.write(out_dir=str(outside))
        self.assertEqual(Path(res["path"]).parent, outside)


class UntrustedNoteTest(NoteCase):
    def plant(self, data_json):
        folder = self.repo / ".handoff"
        folder.mkdir()
        (folder / "2026-10-14-090507.md").write_text("# n\n`file:src/a.py`\n<!-- handoff:data %s -->\n" % data_json, encoding="utf-8")

    def test_a_data_block_with_the_wrong_shape_is_ignored_not_a_crash(self):
        bad_facts = ['{"facts":{"modified":"nope"}}', '{"facts":{"branch":1,"tip":null,"upstream":null,"base":null,"ahead":null,"behind":null,"modified":[],"untracked":[],"stashes":0}}',
                     '{"facts":{"branch":null,"tip":null,"upstream":null,"base":null,"ahead":null,"behind":null,"modified":[1],"untracked":[],"stashes":0}}',
                     '{"facts":{"branch":null,"tip":null,"upstream":null,"base":null,"ahead":null,"behind":null,"modified":[],"untracked":[],"stashes":"2"}}',
                     '{"facts":[]}', '{"facts":{}}']
        for data in bad_facts:
            with self.subTest(data=data[:60]):
                (self.repo / ".handoff").mkdir(exist_ok=True)
                self.assertIsNone(ho.parse_data("<!-- handoff:data %s -->" % data))

    def test_resume_of_a_note_with_an_unusable_data_block_still_checks_citations(self):
        self.plant('{"facts":{"modified":"nope"}}')
        res = ho.resume(self.repo)
        self.assertFalse(res["has_data"])
        self.assertIsNone(res["drift"])
        self.assertTrue(res["citations"][0]["verified"])

    def test_a_recorded_base_that_is_hostile_or_gone_falls_back_to_detection(self):
        facts = ho.collect(self.repo)
        for base in ("--output=/tmp/x", "deleted-branch"):
            with self.subTest(base=base):
                data = {"schema": 1, "facts": dict(facts, base=base), "citations": []}
                (self.repo / ".handoff").mkdir(exist_ok=True)
                (self.repo / ".handoff" / "2026-10-14-090507.md").write_text("# n\n" + ho.data_block(data) + "\n", encoding="utf-8")
                res = ho.resume(self.repo)
                self.assertIsNotNone(res["drift"])


class NewestNoteTest(NoteCase):
    def test_newest_by_timestamp_then_by_collision_number(self):
        folder = self.repo / ".handoff"
        folder.mkdir()
        for name in ("2026-10-14-090507.md", "2026-10-14-090507-2.md", "2026-10-14-090507-10.md", "2026-10-13-235959.md", "notes.md", "2026-10-14-09.md"):
            (folder / name).write_text("x\n", encoding="utf-8")
        self.assertEqual(ho.newest_note(folder).name, "2026-10-14-090507-10.md")

    def test_no_notes_is_none(self):
        self.assertIsNone(ho.newest_note(self.repo / ".handoff"))

    def test_a_symlinked_note_is_ignored(self):
        folder = self.repo / ".handoff"
        folder.mkdir()
        outside = self.tmp / "outside.md"
        outside.write_text("secret\n", encoding="utf-8")
        os.symlink(outside, folder / "2026-10-14-090507.md")
        self.assertIsNone(ho.newest_note(folder))


class ResumeTest(NoteCase):
    def test_nothing_changed_means_no_drift_and_verified_citations(self):
        self.write(draft="## O que foi feito\n`file:src/a.py` and `branch:main`\n")
        res = ho.resume(self.repo)
        self.assertEqual(res["drift"], [])
        self.assertTrue(all(c["verified"] and not c["moved"] for c in res["citations"]))
        self.assertTrue(res["has_data"])

    def test_a_new_commit_moves_the_tip_and_the_cited_branch(self):
        self.write(draft="## O que foi feito\n`branch:main`\n")
        commit(self.repo, "later", {"b.txt": "b\n"})
        res = ho.resume(self.repo)
        self.assertTrue(any("a ponta de main mudou" in m and "(1 commits novos)" in m for m in res["drift"]), res["drift"])
        self.assertTrue(res["citations"][0]["moved"])

    def test_a_deleted_cited_file_and_a_new_dirty_file_are_reported(self):
        self.write(draft="## O que foi feito\n`file:src/a.py`\n")
        (self.repo / "src" / "a.py").unlink()
        (self.repo / "fresh.txt").write_text("x\n", encoding="utf-8")
        res = ho.resume(self.repo)
        self.assertFalse(res["citations"][0]["verified"])
        self.assertTrue(any("arquivos sujos novos: fresh.txt" in m or "fresh.txt" in m for m in res["drift"]))
        self.assertTrue(any("src/a.py" in m for m in res["drift"]))  # it is now a deleted, modified file

    def test_a_different_branch_and_stashes_and_ahead_counts(self):
        self.write()
        git(self.repo, "checkout", "-q", "-b", "other")
        commit(self.repo, "o1", {"o.txt": "1\n"})
        (self.repo / "src" / "a.py").write_text("stash\n", encoding="utf-8")
        git(self.repo, "stash", "-q")
        drift = ho.resume(self.repo)["drift"]
        self.assertTrue(any("a branch era main e agora e other" in m for m in drift), drift)
        self.assertTrue(any("a frente/atras da base mudou: 0/0 -> 1/0" in m for m in drift), drift)
        self.assertTrue(any("stashes: 0 -> 1" in m for m in drift), drift)

    def test_a_note_without_a_data_block_still_gets_its_citations_checked(self):
        folder = self.repo / ".handoff"
        folder.mkdir()
        note = folder / "2026-10-14-090507.md"
        note.write_text("# By hand\n`file:src/a.py` `file:nope.py`\n", encoding="utf-8")
        res = ho.resume(self.repo)
        self.assertIsNone(res["drift"])
        self.assertFalse(res["has_data"])
        self.assertEqual([c["verified"] for c in res["citations"]], [True, False])

    def test_an_explicit_file_is_used_instead_of_the_newest(self):
        first = self.write()["path"]
        self.write(draft="## O que foi feito\nlater\n")
        self.assertEqual(ho.resume(self.repo, first)["path"], first)

    def test_without_any_note_it_is_an_error(self):
        with self.assertRaises(ho.HandoffError):
            ho.resume(self.repo)

    def test_a_symlink_given_as_the_file_is_refused(self):
        outside = self.tmp / "o.md"
        outside.write_text("x\n", encoding="utf-8")
        os.symlink(outside, self.tmp / "link.md")
        with self.assertRaises(ho.HandoffError):
            ho.resume(self.repo, str(self.tmp / "link.md"))


def cannot_read_modes():
    """True when file permissions do not stop this process (root): the chmod tests are meaningless there."""
    return hasattr(os, "geteuid") and os.geteuid() == 0


class FailedWritesTest(NoteCase):
    def folder_has_no_notes(self, folder):
        self.assertEqual(list(Path(folder).glob("*")) if Path(folder).is_dir() else [], [])

    def test_a_notes_folder_that_is_a_regular_file_is_an_error_not_a_traceback(self):
        (self.repo / ".handoff").write_text("not a folder\n", encoding="utf-8")
        with self.assertRaises(ho.HandoffError) as ctx:
            self.write()
        self.assertIn("pasta", str(ctx.exception))

    def test_an_out_path_that_is_a_file_is_an_error(self):
        target = self.tmp / "afile"
        target.write_text("x\n", encoding="utf-8")
        with self.assertRaises(ho.HandoffError):
            self.write(out_dir=str(target))
        with self.assertRaises(ho.HandoffError):
            self.write(out_dir=str(target / "inside"))

    def test_a_draft_that_cannot_be_encoded_leaves_no_file_behind(self):
        with self.assertRaises(ho.HandoffError):
            self.write(draft="## O que foi feito\nbad \udcff byte\n")
        self.folder_has_no_notes(self.repo / ".handoff")

    def test_a_write_that_fails_midway_removes_the_partial_note(self):
        with mock.patch.object(ho.os, "write", side_effect=OSError(28, "No space left on device")):
            with self.assertRaises(ho.HandoffError):
                self.write()
        self.folder_has_no_notes(self.repo / ".handoff")

    def test_a_failed_write_does_not_shadow_the_last_good_note(self):
        good = self.write()["path"]
        with mock.patch.object(ho.os, "write", side_effect=OSError(28, "No space left on device")):
            with self.assertRaises(ho.HandoffError):
                self.write()
        self.assertEqual(str(ho.newest_note(self.repo / ".handoff")), good)

    def test_a_folder_that_cannot_be_created_is_an_error(self):
        locked = self.tmp / "locked"
        locked.mkdir()
        if cannot_read_modes():
            self.skipTest("running as root")
        os.chmod(locked, 0o500)
        self.addCleanup(os.chmod, locked, 0o700)
        with self.assertRaises(ho.HandoffError):
            self.write(out_dir=str(locked / "sub"))


class UnreadableNoteTest(NoteCase):
    def test_an_unreadable_note_is_an_error_not_a_traceback(self):
        note = Path(self.write()["path"])
        if cannot_read_modes():
            self.skipTest("running as root")
        os.chmod(note, 0)
        self.addCleanup(os.chmod, note, 0o600)
        with self.assertRaises(ho.HandoffError) as ctx:
            ho.resume(self.repo)
        self.assertIn("nao consegui ler", str(ctx.exception))


class DeepDataBlockTest(NoteCase):
    def plant(self, body):
        folder = self.repo / ".handoff"
        folder.mkdir()
        (folder / "2026-10-14-090507.md").write_text("# n\n`file:src/a.py`\n<!-- handoff:data %s -->\n" % body, encoding="utf-8")

    def test_a_deeply_nested_data_block_is_no_data_block(self):
        body = '{"a":' + "[" * 100000 + "]" * 100000 + "}"
        self.assertIsNone(ho.parse_data("<!-- handoff:data %s -->" % body))
        self.plant(body)
        res = ho.resume(self.repo)
        self.assertFalse(res["has_data"])
        self.assertTrue(res["citations"][0]["verified"])

    def test_planted_citations_of_the_wrong_shape_do_not_crash_resume(self):
        facts = ho.collect(self.repo)
        for citations in (5, "x", [1, "a"], [{"type": ["x"], "value": {}}], {"a": 1}, None):
            with self.subTest(citations=repr(citations)):
                data = {"schema": 1, "facts": facts, "citations": citations}
                folder = self.repo / ".handoff"
                folder.mkdir(exist_ok=True)
                (folder / "2026-10-14-090507.md").write_text("# n\n`file:src/a.py`\n" + ho.data_block(data) + "\n", encoding="utf-8")
                res = ho.resume(self.repo)
                self.assertTrue(res["has_data"])
                self.assertEqual(res["drift"], [])


class ToolPartsAreNotCitationsTest(NoteCase):
    """The git section and the data block quote commit subjects, branch and file names verbatim; only the agent's
    own text is checked, by `write`, `resume` and `verify` alike."""

    def setUp(self):
        super().setUp()
        commit(self.repo, "rename `file:old.py` to a.py and `branch:nope`", {"b.txt": "b\n"})

    def test_resume_checks_only_the_agents_citations(self):
        self.write(draft="## O que foi feito\n`file:src/a.py`\n")
        res = ho.resume(self.repo)
        self.assertEqual([(c["type"], c["value"]) for c in res["citations"]], [("file", "src/a.py")])
        self.assertEqual(res["drift"], [])

    def test_a_draft_without_headings_still_gets_checked_after_the_git_section(self):
        self.write(draft="just `file:src/a.py` and `file:ghost.py`\n")
        res = ho.resume(self.repo)
        self.assertEqual([c["verified"] for c in res["citations"]], [True, False])

    def test_a_file_named_like_a_citation_is_not_one(self):
        (self.repo / "`file:yy.py`").write_text("x\n", encoding="utf-8")
        (self.repo / "x\n\n`file:ww.py`").write_text("x\n", encoding="utf-8")
        git(self.repo, "checkout", "-q", "-b", "`bq`")
        self.write(draft="## O que foi feito\n`file:src/a.py`\n")
        res = ho.resume(self.repo)
        self.assertEqual([(c["type"], c["value"]) for c in res["citations"]], [("file", "src/a.py")])
        self.assertEqual(res["drift"], [])

    def test_a_note_without_a_usable_data_block_still_masks_the_git_section(self):
        path = Path(self.write(draft="## O que foi feito\n`file:src/a.py`\n")["path"])
        text = path.read_text(encoding="utf-8")
        path.write_text(text[:text.index("<!-- handoff:data")], encoding="utf-8")
        res = ho.resume(self.repo)
        self.assertFalse(res["has_data"])
        self.assertEqual([(c["type"], c["value"]) for c in res["citations"]], [("file", "src/a.py")])

    def test_a_hand_written_note_is_checked_in_full(self):
        folder = self.repo / ".handoff"
        folder.mkdir()
        (folder / "2026-10-14-090507.md").write_text("# By hand\n\n## Estado do git\n\n- `file:nope.py`\n", encoding="utf-8")
        self.assertEqual([c["verified"] for c in ho.resume(self.repo)["citations"]], [False])

    def test_line_numbers_still_point_into_the_note(self):
        res = self.write(draft="## O que foi feito\n\n`file:ghost.py`\n")
        text = Path(res["path"]).read_text(encoding="utf-8")
        shown = ho.resume(self.repo)["citations"][0]["line"]
        self.assertEqual(text.splitlines()[shown - 1].strip(), "`file:ghost.py` [nao verificado]")


if __name__ == "__main__":
    unittest.main()
