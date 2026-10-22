import contextlib
import io
import json
import unittest
from pathlib import Path
from unittest import mock

from helpers import commit, git, init_repo, load_capy, tb
from repo_case import RepoCase

capy = load_capy()  # the vendored engine: its own `check` is the judge of every batch we write


class BoardRepo(RepoCase):
    """main, two merged branches, a squash-merged one, a unique one, a stash and a dirty worktree."""

    def setUp(self):
        super().setUp()
        for name in ("feat/a", "feat/b"):
            self.work(name, {f"{name[-1]}.txt": "x\n"})
            git(self.repo, "merge", "-q", "--no-ff", "-m", f"merge {name}", name)
        self.work("feat/s", {"s.txt": "s\n"})
        commit(self.repo, "unrelated", {"u.txt": "u\n"})
        git(self.repo, "merge", "-q", "--squash", "feat/s")
        git(self.repo, "commit", "-q", "-m", "squash feat/s")
        self.work("spike/x", {"x.txt": "x\n"}, message="wip: x")
        (self.repo / "a.txt").write_text("dirty\n")
        git(self.repo, "stash", "push", "-q", "-m", "wip handoff")
        git(self.repo, "branch", "dirty")
        wt = self.tmp / "dirty-wt"
        git(self.repo, "worktree", "add", "-q", str(wt), "dirty")
        (wt / "scratch.txt").write_text("x\n")

    def build(self, **kw):
        return tb.build_scan(self.repo, self.inv(), now=1_800_000_000, stamp="20261014-120000", **kw)


class BuildScanTest(BoardRepo):
    def test_the_batch_is_accepted_by_the_engine(self):
        batch, _ = self.build()
        self.assertEqual(capy.validate(batch), [])

    def test_the_group_card_comes_first_and_covers_exactly_the_p1_and_p2_items(self):
        batch, scan = self.build()
        self.assertEqual(batch["items"][0]["id"], "G")
        members = scan["group"]["members"]
        by_id = {e["id"]: e for e in scan["items"]}
        self.assertTrue(all(by_id[m]["proof"] in ("P1", "P2") for m in members))
        self.assertEqual(sorted(by_id[m]["name"] for m in members), ["feat/a", "feat/b"])
        self.assertIn("2 items", batch["items"][0]["title"])

    def test_cards_and_entries_line_up_one_to_one(self):
        batch, scan = self.build()
        self.assertEqual([c["id"] for c in batch["items"][1:]], [e["id"] for e in scan["items"]])
        self.assertEqual(tb.scan_problems(batch, scan), [])

    def test_confirm_marks_exactly_what_is_not_provably_merged(self):
        batch, scan = self.build()
        proof = {e["id"]: e["proof"] for e in scan["items"]}
        kind = {e["id"]: e["kind"] for e in scan["items"]}
        for card in batch["items"][1:]:
            risky = proof[card["id"]] in ("P3", "P4") or kind[card["id"]] == "stash"
            self.assertEqual("confirm" in card, risky, card["title"])

    def test_the_board_speaks_in_its_own_words_and_paints_delete_as_danger(self):
        batch, _ = self.build()
        self.assertEqual(batch["labels"]["approve"], {"text": "Delete", "tone": "danger"})
        self.assertEqual(batch["labels"]["reject"], {"text": "Keep", "tone": "safe"})
        self.assertEqual(batch["labels"]["maybe"], {"text": "Later", "tone": "caution"})
        batch, _ = self.build(lang="pt-BR")
        self.assertEqual(batch["labels"]["approve"], {"text": "Apagar", "tone": "danger"})
        self.assertEqual(batch["labels"]["reject"], {"text": "Manter", "tone": "safe"})
        self.assertEqual(batch["labels"]["maybe"], {"text": "Depois", "tone": "caution"})

    def test_what_is_never_touched_is_a_field_of_the_first_card(self):
        batch, scan = self.build()
        first = batch["items"][0]
        field = [f for f in first["fields"] if f["label"] == "Do not touch"][0]["text"]
        self.assertIn("`main`: base branch of the repository", field)
        self.assertIn("`dirty-wt`:", field)
        self.assertNotIn(str(self.tmp), field)  # a worktree is named by its folder, not its absolute path
        self.assertEqual(first["meta"], {"Base": "main", "gh": "no (git only)"})
        self.assertEqual(len(scan["untouched"]), 2)

    def test_a_worktree_card_is_titled_by_its_folder_and_keeps_the_full_path_in_a_field(self):
        git(self.repo, "branch", "wtc")
        wt = self.tmp / "wtc"
        git(self.repo, "worktree", "add", "-q", str(wt), "wtc")
        batch, scan = self.build()
        card = [c for c in batch["items"] if c["title"].startswith("Remove the worktree")][0]
        self.assertEqual(card["title"], "Remove the worktree wtc?")
        self.assertIn(str(wt), [f for f in card["fields"] if f["label"] == "Worktree"][0]["text"])
        self.assertIn("`wtc` (worktree, P1)", batch["items"][0]["fields"][0]["text"])

    def test_p4_cards_list_the_unique_commits_and_the_backup_ref(self):
        batch, scan = self.build()
        entry = [e for e in scan["items"] if e["name"] == "spike/x"][0]
        card = [c for c in batch["items"] if c["id"] == entry["id"]][0]
        text = json.dumps(card, ensure_ascii=False)
        self.assertIn("wip: x", text)
        self.assertIn("refs/tidy-board/backup/spike/x", text)
        self.assertTrue(entry["backup"])

    def test_a_stash_card_names_its_files_and_a_sha_based_backup(self):
        batch, scan = self.build()
        entry = [e for e in scan["items"] if e["kind"] == "stash"][0]
        card = [c for c in batch["items"] if c["id"] == entry["id"]][0]
        text = json.dumps(card, ensure_ascii=False)
        self.assertIn("a.txt", text)
        self.assertIn("refs/tidy-board/backup/stash-" + entry["sha"][:12], text)

    def test_the_sidecar_records_what_apply_needs_to_recheck(self):
        _, scan = self.build()
        self.assertEqual(scan["base"], "main")
        self.assertEqual(scan["repo"], str(self.repo))
        for e in scan["items"]:
            self.assertRegex(e["sha"], r"^[0-9a-f]{40}$")
            self.assertIn(e["kind"], ("branch", "worktree", "stash"))

    def test_a_worktree_with_ignored_files_asks_for_confirmation_and_stays_out_of_the_group(self):
        commit(self.repo, "ignore", {".gitignore": "*.env\n"})
        git(self.repo, "branch", "wti")
        wt = self.tmp / "wti"
        git(self.repo, "worktree", "add", "-q", str(wt), "wti")
        (wt / "secret.env").write_text("TOKEN=1\n")
        batch, scan = self.build()
        entry = [e for e in scan["items"] if e["kind"] == "worktree" and e["name"] == str(wt)][0]
        self.assertEqual(entry["proof"], "P1")
        self.assertNotIn(entry["id"], scan["group"]["members"])
        card = [c for c in batch["items"] if c["id"] == entry["id"]][0]
        self.assertIn("confirm", card)
        text = json.dumps(card, ensure_ascii=False)
        self.assertIn("secret.env", text)
        self.assertEqual(capy.validate(batch), [])

    def test_a_single_safe_item_gets_no_group_card(self):
        for name in ("feat/b",):
            git(self.repo, "branch", "-D", name)
        git(self.repo, "branch", "-D", "feat/a")
        git(self.repo, "branch", "only-safe")
        batch, scan = self.build()
        self.assertIsNone(scan["group"])
        self.assertNotIn("G", [c["id"] for c in batch["items"]])
        self.assertEqual(capy.validate(batch), [])

    def test_nothing_to_offer_builds_nothing(self):
        empty = init_repo(self.tmp / "empty")
        commit(empty, "init", {"a.txt": "x\n"})
        self.assertIsNone(tb.build_scan(empty, tb.inventory(empty, "main", "off")))

    def test_a_backtick_in_a_name_cannot_break_the_card_markup(self):
        git(self.repo, "branch", "odd`name")
        batch, scan = self.build()
        card = [c for c in batch["items"] if "odd" in c["title"]][0]
        self.assertNotIn("`name", json.dumps(card))
        self.assertIn("odd'name", card["title"])
        self.assertEqual(capy.validate(batch), [])


class ScanProblemsTest(BoardRepo):
    def pair(self):
        return self.build()

    def problems(self, mutate):
        batch, scan = self.pair()
        mutate(batch, scan)
        return tb.scan_problems(batch, scan)

    def test_a_clean_pair_has_no_problems(self):
        self.assertEqual(self.problems(lambda b, s: None), [])

    def test_a_duplicate_id_unknown_kind_bad_proof_and_bad_sha_are_reported(self):
        def mutate(b, s):
            s["items"][1]["id"] = s["items"][0]["id"]
            s["items"][0]["kind"] = "tag"
            s["items"][0]["proof"] = "P9"
            s["items"][0]["sha"] = "abc"
        errs = self.problems(mutate)
        for fragment in ("id duplicado", "'kind' deve ser", "'proof' deve ser", "'sha' deve ser um id de commit completo"):
            self.assertTrue(any(fragment in e for e in errs), (fragment, errs))

    def test_the_group_only_accepts_p1_and_p2_items(self):
        def mutate(b, s):
            risky = [e["id"] for e in s["items"] if e["proof"] in ("P3", "P4")][0]
            s["group"]["members"].append(risky)
        self.assertTrue(any("so aceita itens P1 ou P2" in e for e in self.problems(mutate)))

    def test_a_card_without_an_entry_and_an_entry_without_a_card_are_reported(self):
        def mutate(b, s):
            s["items"].pop()
            b["items"].pop(1)
        errs = self.problems(mutate)
        self.assertTrue(any("nao tem entrada no scan.json" in e or "nao tem card" in e for e in errs), errs)

    def test_a_worktree_needs_its_path(self):
        def mutate(b, s):
            wt = [e for e in s["items"] if e["kind"] == "worktree"]
            if not wt:
                s["items"].append({"id": "T99", "kind": "worktree", "name": "w", "sha": "0" * 40, "proof": "P1", "path": None})
                b["items"].append({"id": "T99", "title": "w"})
            else:
                wt[0]["path"] = None
        self.assertTrue(any("precisa de 'path'" in e for e in self.problems(mutate)))

    def test_garbage_shapes_do_not_crash(self):
        self.assertTrue(tb.scan_problems({"items": []}, {"items": "x"}))
        self.assertTrue(tb.scan_problems({"items": "x"}, {"items": []}))
        self.assertTrue(tb.scan_problems([], {}))


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = tb.main(list(argv))
    return rc, out.getvalue(), err.getvalue()


class ScanCliTest(BoardRepo):
    def test_scan_writes_a_batch_the_engine_accepts_and_check_passes(self):
        out = self.tmp / "board"
        rc, stdout, _ = run_cli("scan", str(self.repo), "--gh", "off", "--out", str(out))
        self.assertEqual(rc, 0, stdout)
        self.assertIn(f"TIDY-BOARD DIR: {out}", stdout)
        self.assertIn("TIDY-BOARD ITENS:", stdout)
        self.assertIn("NAO TOCAR: main (branch base do repositório)", stdout)
        self.assertIn("; idioma en", stdout)
        batch = json.loads((out / "batch.json").read_text(encoding="utf-8"))
        self.assertEqual(capy.validate(batch), [])
        rc, stdout, _ = run_cli("check", str(out))
        self.assertEqual(rc, 0)
        self.assertIn("ok:", stdout)

    def test_the_files_are_private(self):
        out = self.tmp / "board"
        run_cli("scan", str(self.repo), "--gh", "off", "--out", str(out))
        for name in ("batch.json", "scan.json"):
            self.assertEqual((out / name).stat().st_mode & 0o777, 0o600)

    def test_the_default_folder_is_inside_the_repository_and_named_after_the_batch(self):
        rc, stdout, _ = run_cli("scan", str(self.repo), "--gh", "off")
        self.assertEqual(rc, 0)
        folders = list((self.repo / ".tidy-board").iterdir())
        self.assertEqual(len(folders), 1)
        self.assertTrue(folders[0].name.startswith("tidy-r-"))
        self.assertEqual(json.loads((folders[0] / "batch.json").read_text(encoding="utf-8"))["batch_id"], folders[0].name)

    def test_two_scans_in_the_same_second_never_share_a_folder(self):
        with mock.patch.object(tb.time, "strftime", return_value="20261014-120000"):
            self.assertEqual(run_cli("scan", str(self.repo), "--gh", "off")[0], 0)
            rc, _, err = run_cli("scan", str(self.repo), "--gh", "off")
        self.assertEqual(rc, 2)
        self.assertIn("ja existe", err)

    def test_check_rejects_an_edited_scan(self):
        out = self.tmp / "board"
        run_cli("scan", str(self.repo), "--gh", "off", "--out", str(out))
        scan = json.loads((out / "scan.json").read_text(encoding="utf-8"))
        scan["items"][0]["sha"] = "nothex"
        (out / "scan.json").write_text(json.dumps(scan), encoding="utf-8")
        rc, _, err = run_cli("check", str(out))
        self.assertEqual(rc, 1)
        self.assertIn("'sha' deve ser um id de commit completo", err)

    def test_check_on_a_missing_folder_is_a_clean_error(self):
        rc, _, err = run_cli("check", str(self.tmp / "nope"))
        self.assertEqual(rc, 2)
        self.assertIn("erro:", err)

    def test_scan_outside_a_repository_is_a_clean_error(self):
        rc, _, err = run_cli("scan", str(self.tmp))
        self.assertEqual(rc, 2)
        self.assertIn("nao e um repositorio git", err)

    def test_scan_with_nothing_to_clean_says_so_and_writes_nothing(self):
        empty = init_repo(self.tmp / "empty")
        commit(empty, "init", {"a.txt": "x\n"})
        rc, stdout, _ = run_cli("scan", str(empty), "--gh", "off")
        self.assertEqual(rc, 0)
        self.assertIn("nada para limpar", stdout)
        self.assertFalse((empty / ".tidy-board").exists())

    def test_an_unknown_base_is_a_clean_error(self):
        rc, _, err = run_cli("scan", str(self.repo), "--base", "nope")
        self.assertEqual(rc, 2)
        self.assertIn("a base 'nope' nao existe", err)

    def test_a_long_board_gets_a_warning_from_check(self):
        out = self.tmp / "board"
        run_cli("scan", str(self.repo), "--gh", "off", "--out", str(out))
        scan = json.loads((out / "scan.json").read_text(encoding="utf-8"))
        batch = json.loads((out / "batch.json").read_text(encoding="utf-8"))
        template = scan["items"][0]
        for n in range(100, 100 + tb.WARN_CARDS):
            scan["items"].append({**template, "id": f"T{n}"})
            batch["items"].append({"id": f"T{n}", "title": "x"})
        (out / "scan.json").write_text(json.dumps(scan), encoding="utf-8")
        (out / "batch.json").write_text(json.dumps(batch), encoding="utf-8")
        rc, _, err = run_cli("check", str(out))
        self.assertEqual(rc, 0)
        self.assertIn("a revisao cansa", err)

# ---------------------------------------------------------------- the cards' language (tidy-board 0.2.0)

import re as _re

PLACEHOLDER = _re.compile(r"\{(\w+)\}")


class LanguageTableTest(unittest.TestCase):
    def test_both_tables_have_the_same_keys_and_placeholders(self):
        self.assertEqual(tb.LANGS, ("en", "pt-BR"))
        self.assertEqual(tb.DEFAULT_LANG, "en")
        en, pt = tb.TEXT["en"], tb.TEXT["pt-BR"]
        self.assertEqual(set(en), set(pt))
        for key in en:
            with self.subTest(key=key):
                self.assertEqual(set(PLACEHOLDER.findall(en[key])), set(PLACEHOLDER.findall(pt[key])))
        self.assertEqual(set(tb.LABELS), set(tb.LANGS))
        for code in tb.WHY_CODES:
            self.assertIn("why_" + code, en)
        for proof in tb.PROOFS:
            self.assertIn("proof_" + proof, en)

    def test_the_portuguese_table_has_accents(self):
        text = " ".join(tb.TEXT["pt-BR"].values())
        for word in ("repositório", "único", "Não tocar", "à frente"):
            self.assertIn(word, text)

    def test_reasons_pr_remote_and_age_render_in_both_languages(self):
        self.assertEqual(tb.reason_text({"name": "x", "why": "base_branch"}, "en"), "base branch of the repository")
        self.assertEqual(tb.reason_text({"name": "x", "why": "dirty", "count": 3}, "pt-BR"),
                         "3 arquivo(s) alterado(s) ou não rastreado(s): apagar perderia trabalho sem sha para recuperar")
        self.assertEqual(tb.reason_text({"name": "x", "why": "main_worktree", "path": "/w`t"}, "en"), "in use by the main worktree (/w't)")
        self.assertEqual(tb.pr_text({"pr": None}, "en"), "")
        self.assertEqual(tb.pr_text({"pr": {}}, "pt-BR"), "sem PR mergeado")
        self.assertEqual(tb.pr_text({"pr": {"number": 7, "tip_matches": True}}, "en"), "#7 merged (the tip matches)")
        self.assertEqual(tb.pr_text({"pr": {"number": 7, "tip_matches": False}}, "pt-BR"), "#7 mergeado (a ponta é DIFERENTE da do PR)")
        self.assertEqual(tb.remote_text({"remote": None, "name": "x"}, "en"), "")
        self.assertEqual(tb.remote_text({"remote": "exists", "name": "feat/x"}, "en"), "origin/feat/x still exists (it will not be touched)")
        self.assertEqual(tb.remote_text({"remote": "removed", "name": "w", "branch": "feat/y"}, "pt-BR"), "origin/feat/y já foi removida")
        now = 1_800_000_000
        self.assertEqual([tb.age_text(now - d * 86400, now, "en") for d in (0, 1, 2)], ["today", "1 day ago", "2 days ago"])
        self.assertEqual([tb.age_text(now - d * 86400, now, "pt-BR") for d in (0, 1, 2)], ["hoje", "há 1 dia", "há 2 dias"])

    def test_an_unknown_language_is_refused_by_the_builder(self):
        with self.assertRaises(tb.TidyError) as ctx:
            tb.check_lang("xx")
        self.assertIn("idioma invalido", str(ctx.exception))


class LanguageBoardTest(BoardRepo):
    def test_english_is_the_default_and_pt_br_is_the_old_wording_with_accents(self):
        batch, scan = self.build()
        self.assertEqual((batch["lang"], scan["lang"]), ("en", "en"))
        titles = [c["title"] for c in batch["items"]]
        self.assertIn("Delete the branch feat/a?", titles)
        self.assertTrue(any(title.startswith("Discard the stash ") for title in titles), titles)
        self.assertEqual(batch["title"], "Cleanup of r")
        self.assertEqual(batch["subtitle"], "base: main - gh: no - 5 items")
        self.assertEqual(batch["items"][0]["tag"], "group P1/P2")
        batch, scan = self.build(lang="pt-BR")
        self.assertEqual((batch["lang"], scan["lang"]), ("pt-BR", "pt-BR"))
        titles = [c["title"] for c in batch["items"]]
        self.assertIn("Apagar a branch feat/a?", titles)
        self.assertEqual(batch["title"], "Limpeza de r")
        self.assertEqual(batch["subtitle"], "base: main - gh: não - 5 itens")
        self.assertEqual(batch["items"][0]["title"], "Apagar os 2 itens provados como mergeados?")
        field = [f for f in batch["items"][0]["fields"] if f["label"] == "Não tocar"][0]["text"]
        self.assertIn("`main`: branch base do repositório", field)
        self.assertIn("Vale para os itens abaixo em que você não marcar Manter ou Depois.", [f["text"] for f in batch["items"][0]["fields"]][1])
        self.assertEqual(batch["items"][0]["meta"], {"Base": "main", "gh": "não (só git local)"})

    def test_both_languages_build_the_same_board_shape(self):
        en, en_scan = self.build()
        pt, pt_scan = self.build(lang="pt-BR")
        self.assertEqual([c["id"] for c in en["items"]], [c["id"] for c in pt["items"]])
        for a, b in zip(en["items"], pt["items"]):
            with self.subTest(card=a["id"]):
                self.assertEqual(len(a["fields"]), len(b["fields"]))
                self.assertEqual("confirm" in a, "confirm" in b)
                self.assertEqual(a.get("meta", {}).keys(), b.get("meta", {}).keys())
        self.assertEqual({k: v for k, v in en_scan.items() if k not in ("lang", "untouched")},
                         {k: v for k, v in pt_scan.items() if k not in ("lang", "untouched")})
        self.assertEqual(capy.validate(pt), [])
        self.assertEqual(tb.scan_problems(pt, pt_scan), [])

    def test_a_scan_in_either_language_passes_check_and_the_older_shape_without_lang_still_does(self):
        batch, scan = self.build(lang="pt-BR")
        self.assertEqual(tb.scan_problems(batch, scan), [])
        del scan["lang"]
        self.assertEqual(tb.scan_problems(batch, scan), [])
        scan["lang"] = "xx"
        self.assertTrue(any("'lang' deve ser en ou pt-BR" in e for e in tb.scan_problems(batch, scan)))
        scan["lang"] = None  # null counts as omitted
        self.assertEqual(tb.scan_problems(batch, scan), [])


class LanguageCliTest(BoardRepo):
    def test_scan_lang_reaches_both_files_and_the_command_line_stays_portuguese(self):
        out = self.tmp / "board"
        rc, stdout, _ = run_cli("scan", str(self.repo), "--gh", "off", "--out", str(out), "--lang", "pt-BR")
        self.assertEqual(rc, 0, stdout)
        batch = json.loads((out / "batch.json").read_text(encoding="utf-8"))
        scan = json.loads((out / "scan.json").read_text(encoding="utf-8"))
        self.assertEqual((batch["lang"], scan["lang"]), ("pt-BR", "pt-BR"))
        self.assertEqual(batch["labels"]["approve"]["text"], "Apagar")
        self.assertEqual(capy.validate(batch), [])
        self.assertIn("NAO TOCAR: main (branch base do repositório)", stdout)
        self.assertIn("; idioma pt-BR", stdout)
        self.assertEqual(run_cli("check", str(out))[0], 0)

    def test_an_unknown_lang_is_refused_before_anything_is_written(self):
        out = self.tmp / "board"
        with self.assertRaises(SystemExit) as ctx:
            run_cli("scan", str(self.repo), "--gh", "off", "--out", str(out), "--lang", "xx")
        self.assertEqual(ctx.exception.code, 2)
        self.assertFalse(out.exists())
        self.assertFalse((self.repo / ".tidy-board").exists())

    def test_check_rejects_a_bad_lang_edited_into_scan_json(self):
        out = self.tmp / "board"
        run_cli("scan", str(self.repo), "--gh", "off", "--out", str(out))
        scan = json.loads((out / "scan.json").read_text(encoding="utf-8"))
        scan["lang"] = "xx"
        (out / "scan.json").write_text(json.dumps(scan), encoding="utf-8")
        rc, _, err = run_cli("check", str(out))
        self.assertEqual(rc, 1)
        self.assertIn("'lang' deve ser en ou pt-BR", err)
