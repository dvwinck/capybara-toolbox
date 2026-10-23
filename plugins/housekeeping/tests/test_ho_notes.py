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
        """A pt-BR note: these tests pin the layout every note written before 0.4.0 has, which is the pt-BR layout.
        EnglishNoteTest pins the English default."""
        kw.setdefault("lang", "pt-BR")
        return ho.write_note(self.repo, self.draft() if draft is None else draft, **kw)


class WriteTest(NoteCase):
    def test_the_note_is_saved_with_the_git_section_the_draft_and_a_data_block(self):
        res = self.write()
        text = Path(res["path"]).read_text(encoding="utf-8")
        self.assertEqual(Path(res["path"]).name, "2026-10-14-090507.md")
        self.assertEqual(Path(res["path"]).parent, self.repo / ".handoff")
        self.assertTrue(text.startswith("# Handoff - 2026-10-14 09:05 - main\n\n| Metainfo da sessao | |\n|---|---|\n"))
        self.assertIn("\n\n## Estado do git\n", text)
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
        self.assertIn("symbolic link", str(ctx.exception))
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
        self.assertTrue(any("the tip of main moved" in m and "(1 new commit)" in m for m in res["drift"]), res["drift"])
        self.assertTrue(res["citations"][0]["moved"])

    def test_a_deleted_cited_file_and_a_new_dirty_file_are_reported(self):
        self.write(draft="## O que foi feito\n`file:src/a.py`\n")
        (self.repo / "src" / "a.py").unlink()
        (self.repo / "fresh.txt").write_text("x\n", encoding="utf-8")
        res = ho.resume(self.repo)
        self.assertFalse(res["citations"][0]["verified"])
        self.assertTrue(any("new dirty files: fresh.txt" in m for m in res["drift"]), res["drift"])
        self.assertTrue(any("src/a.py" in m for m in res["drift"]))  # it is now a deleted, modified file

    def test_a_different_branch_and_stashes_and_ahead_counts(self):
        self.write()
        git(self.repo, "checkout", "-q", "-b", "other")
        commit(self.repo, "o1", {"o.txt": "1\n"})
        (self.repo / "src" / "a.py").write_text("stash\n", encoding="utf-8")
        git(self.repo, "stash", "-q")
        drift = ho.resume(self.repo)["drift"]
        self.assertTrue(any("the branch was main and is now other" in m for m in drift), drift)
        self.assertTrue(any("ahead/behind the base changed: 0/0 -> 1/0" in m for m in drift), drift)
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
        self.assertIn("could not create the notes folder", str(ctx.exception))

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
        self.assertIn("could not read the note", str(ctx.exception))


class HostileDataBlockTest(NoteCase):
    """A note is planted data: a line of repeated openers must not make resume, verify or the citation check slow."""
    BOUND = 3.0  # the lazy regex took 9 s for 150 KB, 36 s for 300 KB and minutes for a megabyte; the scan takes well under a second
    OPEN = "<!-- handoff:data {"

    def timed(self, fn, *args):
        start = time.monotonic()
        result = fn(*args)
        return result, time.monotonic() - start

    def plant(self, text):
        folder = self.repo / ".handoff"
        folder.mkdir(exist_ok=True)
        (folder / "9999-12-31-235959.md").write_text(text, encoding="utf-8")

    def real_block(self):
        return ho.data_block({"schema": 1, "facts": ho.collect(self.repo), "citations": []})

    def test_a_long_line_of_unclosed_openers_is_fast_for_every_reader(self):
        text = "# n\n`file:src/a.py`\n" + self.OPEN * 12000 + "\n"  # about 230 KB (20 s with the lazy regex)
        for name, fn in [("parse_data", ho.parse_data), ("tool_spans", ho.tool_spans), ("check_note", lambda t: ho.check_note(self.repo, t))]:
            with self.subTest(name):
                _result, seconds = self.timed(fn, text)
                self.assertLess(seconds, self.BOUND, f"{name}: {seconds:.2f}s")
        self.assertIsNone(ho.parse_data(text))

    def test_a_planted_newest_note_of_openers_does_not_stall_resume(self):
        self.plant("# n\n`file:src/a.py`\n" + self.OPEN * 12000 + "\n")
        res, seconds = self.timed(ho.resume, self.repo)
        self.assertLess(seconds, self.BOUND, f"resume: {seconds:.2f}s")
        self.assertFalse(res["has_data"])
        self.assertTrue(res["citations"][0]["verified"])

    def test_a_long_run_of_openers_followed_by_a_real_block_still_finds_the_block(self):
        for opener in ("<!-- handoff:data ", self.OPEN):
            with self.subTest(opener=opener):
                text = "# n\n`file:src/a.py`\n" + opener * 12000 + self.real_block() + "\n"
                data, seconds = self.timed(ho.parse_data, text)
                self.assertLess(seconds, self.BOUND, f"{seconds:.2f}s")
                self.assertEqual(data["facts"]["branch"], "main")
                _spans, seconds = self.timed(ho.tool_spans, text)
                self.assertLess(seconds, self.BOUND, f"{seconds:.2f}s")

    def test_many_closed_blocks_on_one_line_are_fast_and_the_last_one_wins(self):
        text = "# n\n" + "<!-- handoff:data {} -->" * 40000 + self.real_block() + "\n"
        data, seconds = self.timed(ho.parse_data, text)
        self.assertLess(seconds, self.BOUND, f"{seconds:.2f}s")
        self.assertEqual(data["facts"]["branch"], "main")

    def test_the_last_block_on_a_line_of_its_own_is_found_as_before(self):
        a, b = '{"x":1}', '{"y":2}'
        text = f"t\n<!-- handoff:data {a} -->\nmid\n<!-- handoff:data {b} --> tail\n<!-- handoff:data {{ unclosed\n"
        start, end, body = ho.last_data_block(text)
        self.assertEqual((body, text[start:end]), (b, f"<!-- handoff:data {b} -->"))
        # a closer on the next line does not close an opener, and the block must hold at least `{}`
        self.assertIsNone(ho.last_data_block("<!-- handoff:data {\n} -->\n"))
        self.assertIsNone(ho.last_data_block("no block here\n"))
        self.assertEqual(ho.last_data_block("<!-- handoff:data {} -->")[2], "{}")
        self.assertEqual(ho.last_data_block("<!-- handoff:data {} -->\r\n")[2], "{}")


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


LINK = "https://claude.ai/" + "code/session_01ABC"  # assembled at run time: publish-check flags a session link in the tree
FRONT = f"""---
Nome da sessao: config sonarqube
Modelo: Claude Sonnet 5.5 (`claude-sonnet-5-5`)
Sessao: {LINK}
Pedido original: "analise o code base | crie uma proposta"
Status: Proposta. Nada aplicado.
---
"""


class MetainfoHeaderTest(NoteCase):
    """The header every note starts with: the agent's rows, then the ones the tool knows."""

    def note(self, front="", **kw):
        return Path(self.write(draft=front + self.draft(), **kw)["path"]).read_text(encoding="utf-8")

    def test_the_header_is_always_there_even_without_a_metainfo_block(self):
        text = self.note()
        self.assertIn("| Metainfo da sessao | |\n|---|---|\n| Gravada em | 2026-10-14 09:05 |\n| Repositorio | r |\n\n## Estado do git", text)

    def test_the_agents_rows_come_first_in_order_and_the_tool_rows_after(self):
        text = self.note(FRONT)
        rows = [l for l in text.split("\n\n")[1].splitlines()[2:]]
        self.assertEqual([r.split(" | ")[0].lstrip("| ") for r in rows],
                         ["Nome da sessao", "Modelo", "Sessao", "Pedido original", "Status", "Gravada em", "Repositorio"])
        self.assertIn(f"| Sessao | {LINK} |", text)
        self.assertIn("| Modelo | Claude Sonnet 5.5 (`claude-sonnet-5-5`) |", text)

    def test_a_pipe_in_a_value_cannot_break_the_table(self):
        self.assertIn('| Pedido original | "analise o code base \\| crie uma proposta" |', self.note(FRONT))

    def test_the_block_is_not_left_in_the_body_and_the_draft_survives(self):
        text = self.note(FRONT)
        self.assertEqual(text.count("Nome da sessao"), 2)  # the table row and the data block
        self.assertNotIn("\n---\n", text)
        self.assertIn("## O que foi feito", text)

    def test_the_rows_are_recorded_in_the_data_block(self):
        meta = ho.parse_data(self.note(FRONT))["meta"]
        self.assertEqual(meta[0], ["Nome da sessao", "config sonarqube"])
        self.assertEqual(meta[-1], ["Repositorio", "r"])

    def test_the_header_never_adds_citations_and_resume_ignores_it(self):
        self.note(FRONT)
        res = ho.resume(self.repo)
        self.assertEqual([c["value"] for c in res["citations"]], [self.first[:7], "src/a.py", "main", "ghost", "docs/missing.md"])
        self.assertEqual(res["drift"], [])

    def test_line_numbers_still_count_the_lines_of_the_whole_draft(self):
        draft = FRONT + "## O que foi feito\n`file:ghost.py`\n"
        res = self.write(draft=draft)
        self.assertEqual(draft.splitlines()[res["citations"][0]["line"] - 1], "`file:ghost.py`")

    def test_a_hr_that_is_not_a_block_is_left_alone(self):
        text = self.note("---\n")  # an opener with no closer
        self.assertIn("\n---\n", text)
        self.assertEqual(ho.split_front("## O que foi feito\n---\nx: y\n---\n"), ([], "## O que foi feito\n---\nx: y\n---\n", 0))

    def test_blank_lines_before_the_block_and_around_it_are_fine(self):
        rows, body, skipped = ho.split_front("\n\n---\nModelo: m\n\nStatus: s\n---\n\n## O que foi feito\nx\n")
        self.assertEqual((rows, skipped), ([("Modelo", "m"), ("Status", "s")], 7))
        self.assertTrue(body.lstrip("\n").startswith("## O que foi feito"))

    def test_a_line_that_is_not_chave_valor_is_an_error_naming_the_line(self):
        with self.assertRaises(ho.HandoffError) as cm:
            self.write(draft="---\nModelo: m\nsem dois pontos\n---\n## O que foi feito\nx\n")
        self.assertIn("line 3", str(cm.exception))
        self.assertFalse((self.repo / ".handoff").exists())

    def test_bad_rows_are_refused_and_nothing_is_written(self):
        bad = {"a typed citation": "Memoria: `file:src/a.py`", "a tool key": "Repositorio: x", "a repeated key": "Modelo: a\nmodelo: b",
               "a long value": "Escopo: " + "x" * (ho.MAX_META_VALUE + 1), "a long key": "k" * 41 + ": v",
               "a control character": "Escopo: a\x07b"}
        for why, rows in bad.items():
            with self.subTest(why):
                with self.assertRaises(ho.HandoffError):
                    self.write(draft=f"---\n{rows}\n---\n" + self.draft())
        self.assertFalse((self.repo / ".handoff").exists())

    def test_a_value_may_hold_colons_and_untyped_backticks(self):
        text = self.note("---\nRepo analisado: `repos/x`, origin/base @ `32cc76d`: ok\n---\n")
        self.assertIn("| Repo analisado | `repos/x`, origin/base @ `32cc76d`: ok |", text)

    def test_the_tool_rows_hold_no_backticks_even_in_a_strange_folder_name(self):
        odd = init_repo(self.tmp / "`x`")
        commit(odd, "c", {"a.txt": "a\n"})
        text = Path(ho.write_note(odd, "## O que foi feito\nx\n", lang="pt-BR")["path"]).read_text(encoding="utf-8")
        self.assertIn("| Repositorio | 'x' |", text)

    def test_missing_expected_rows_are_reported(self):
        self.assertEqual(self.write()["missing_meta"], ["Modelo", "Pedido original", "Status"])
        self.assertEqual(self.write(draft="---\nmodelo: m\nStatus: s\n---\n" + self.draft())["missing_meta"], ["Pedido original"])
        self.assertEqual(self.write(draft=FRONT + self.draft())["missing_meta"], [])

    def test_a_note_written_before_the_header_existed_still_resumes(self):
        folder = self.repo / ".handoff"
        folder.mkdir()
        facts = ho.collect(self.repo)
        old = ("# Handoff - 2026-10-14 09:05 - main\n\n" + ho.git_section(facts, "pt-BR") + "\n\n## O que foi feito\n`file:src/a.py`\n\n"
               + ho.data_block({"schema": 1, "facts": facts, "citations": []}) + "\n")
        (folder / "2026-10-14-090507.md").write_text(old, encoding="utf-8")
        res = ho.resume(self.repo)
        self.assertEqual([(c["type"], c["value"]) for c in res["citations"]], [("file", "src/a.py")])
        self.assertEqual(res["drift"], [])

    def test_a_header_with_a_planted_citation_is_still_masked_when_the_data_block_is_gone(self):
        path = Path(self.write(draft=self.draft())["path"])
        text = path.read_text(encoding="utf-8")
        text = text.replace("| Repositorio | r |", "| Repositorio | `file:nope.py` |")
        path.write_text(text[:text.index("<!-- handoff:data")], encoding="utf-8")
        res = ho.resume(self.repo)
        self.assertNotIn("nope.py", [c["value"] for c in res["citations"]])

    def test_a_malformed_meta_in_the_data_block_means_no_exact_header_but_no_crash(self):
        path = Path(self.write(draft=self.draft())["path"])
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace('"meta":[', '"meta":[1,'), encoding="utf-8")
        res = ho.resume(self.repo)
        self.assertEqual([c["value"] for c in res["citations"]][:2], [self.first[:7], "src/a.py"])


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------- the note's language (housekeeping 0.4.0)

import ast
import re

PLACEHOLDER = re.compile(r"\{(\w+)\}")
HO_PRINTING = ("git", "repo_root", "detect_base", "commit_by_id", "check_citation", "notes_folder", "clean_meta_text",
               "split_front", "clean_meta", "write_note", "drift", "read_note", "resume", "citation_lines", "parser",
               "read_draft", "main", "run_command")
HO_PT_WORDS = {"nao", "encontrado", "repositorio", "existe", "ambiguo", "citacao", "caracteres", "controle", "invalido",
               "hexadecimais", "nome", "expressao", "revisao", "remota", "caminho", "relativo", "raiz", "sai", "arquivo",
               "arvore", "trabalho", "link", "simbolico", "recuso", "escrever", "ler", "pasta", "metainfo", "invalida",
               "linha", "rascunho", "chave", "valor", "resuma", "repetida", "reservada", "ferramenta", "grava", "tipada",
               "cabecalho", "secao", "cabem", "gravado", "consegui", "criar", "nota", "notas", "gravar",
               "agora", "novos", "antigo", "ponta", "mudou", "frente", "atras", "sujos", "estao", "rode", "primeiro",
               "verificado", "verificadas", "conferencia", "bloco", "dados", "conferidas", "nada", "desde", "erro",
               "estrutura", "funda", "demais", "lida", "cabe", "falha", "leitura", "escrita", "gravada", "citacoes",
               "problema", "aviso", "falta", "fatos", "confere", "mostra", "recente", "padrao", "especifica", "entrada"}


class LanguageTablesTest(unittest.TestCase):
    def test_both_tables_have_the_same_keys_and_placeholders_and_are_plain_ascii(self):
        for table in (ho.NOTE, ho.MSG):
            en, pt = table["en"], table["pt-BR"]
            self.assertEqual(set(en), set(pt))
            for key in en:
                with self.subTest(key=key):
                    a, b = en[key], pt[key]
                    if isinstance(a, tuple):
                        self.assertEqual(len(a), len(b))
                        a, b = " ".join(a), " ".join(b)
                    self.assertEqual(set(PLACEHOLDER.findall(a)), set(PLACEHOLDER.findall(b)))
                    self.assertTrue(a.isascii() and b.isascii(), key)

    def test_the_pt_br_note_texts_are_those_of_0_3_1(self):
        pt = ho.NOTE["pt-BR"]
        self.assertEqual((pt["unverified"], pt["meta_title"], pt["git_title"]), (" [nao verificado]", "Metainfo da sessao", "## Estado do git"))
        self.assertEqual(pt["sections"], ("O que foi feito", "Decisoes e por que", "Proximos passos", "O que falhou ou travou"))
        self.assertEqual(pt["expected"], ("Modelo", "Pedido original", "Status"))
        self.assertEqual((pt["written_at"], pt["repository"]), ("Gravada em", "Repositorio"))

    def test_no_portuguese_literal_is_left_in_the_functions_that_print(self):
        tree = ast.parse(Path(ho.__file__).read_text(encoding="utf-8"))
        found = []
        for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in HO_PRINTING):
            body = fn.body[1:] if isinstance(fn.body[0], ast.Expr) and isinstance(fn.body[0].value, ast.Constant) else fn.body
            for node in (n for stmt in body for n in ast.walk(stmt)):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if set(re.split(r"[^a-z]+", node.value.lower())) & HO_PT_WORDS:
                        found.append(f"{fn.name}: {node.value!r}")
        self.assertEqual(found, [], "Portuguese left outside NOTE and MSG:\n" + "\n".join(found))


class EnglishNoteTest(NoteCase):
    def note(self, draft, **kw):
        res = ho.write_note(self.repo, draft, **kw)
        return res, Path(res["path"]).read_text(encoding="utf-8")

    def test_the_default_note_is_english(self):
        draft = "---\nModel: m\nOriginal request: r\nStatus: s\n---\n## What was done\nFixed `file:src/a.py` and `file:gone.py`.\n"
        res, text = self.note(draft)
        self.assertTrue(text.startswith("# Handoff - 2026-10-14 09:05 - main\n\n| Session metainfo | |\n|---|---|\n| Model | m |\n"))
        self.assertIn("| Written at | 2026-10-14 09:05 |\n| Repository | r |\n\n## Git state\n", text)
        self.assertIn(f"- Branch: main, tip {self.first[:7]}", text)
        self.assertIn("- Against the base main: 0 ahead, 0 behind", text)
        self.assertIn("`file:gone.py` [not verified]", text)
        self.assertNotIn("`file:src/a.py` [not verified]", text)
        self.assertEqual(ho.parse_data(text)["lang"], "en")
        self.assertEqual(res["missing"], ["Decisions and why", "Next steps", "What failed or got stuck"])
        self.assertEqual(res["missing_meta"], [])

    def test_keys_and_headings_count_in_either_language(self):
        draft = "---\nModelo: m\nOriginal request: r\nstatus: s\n---\n## O que foi feito\nx\n## Decisions and why\ny\n"
        res, _ = self.note(draft)
        self.assertEqual(res["missing_meta"], [])
        self.assertEqual(res["missing"], ["Next steps", "What failed or got stuck"])
        res, _ = self.note(draft, lang="pt-BR")
        self.assertEqual(res["missing"], ["Proximos passos", "O que falhou ou travou"])

    def test_the_tools_keys_are_reserved_in_both_languages(self):
        for key in ("Written at", "Repository", "Gravada em", "Repositorio"):
            with self.subTest(key=key), self.assertRaises(ho.HandoffError):
                ho.write_note(self.repo, f"---\n{key}: x\n---\n## What was done\nx\n")

    def test_the_tool_parts_are_masked_in_either_language_with_or_without_the_data_block(self):
        commit(self.repo, "rename `file:old.py` and `branch:nope`", {"b.txt": "b\n"})
        for lang in ("en", "pt-BR"):
            with self.subTest(lang=lang):
                path = Path(ho.write_note(self.repo, "## What was done\n`file:src/a.py`\n", lang=lang)["path"])
                text = path.read_text(encoding="utf-8")
                self.assertEqual([c["value"] for c in ho.check_note(self.repo, text)], ["src/a.py"])
                cut = text[:text.index("<!-- handoff:data")]  # no data block: the patterns of both languages
                self.assertEqual([c["value"] for c in ho.check_note(self.repo, cut)], ["src/a.py"])
                path.unlink()

    def test_a_note_without_lang_in_its_data_block_is_read_as_pt_br(self):
        path = Path(ho.write_note(self.repo, "## O que foi feito\n`file:src/a.py`\n", lang="pt-BR")["path"])
        text = path.read_text(encoding="utf-8")
        self.assertIn('"lang":"pt-BR",', text)
        path.write_text(text.replace('"lang":"pt-BR",', ""), encoding="utf-8")  # what 0.3.1 wrote
        res = ho.resume(self.repo)
        self.assertEqual(([c["value"] for c in res["citations"]], res["drift"]), (["src/a.py"], []))
