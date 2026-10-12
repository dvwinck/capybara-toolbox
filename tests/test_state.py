import contextlib
import io
import json
import os
import stat
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from helpers import ab, make_batch


class StaleStateTest(unittest.TestCase):
    """Rodada 1 concluida com A01 aprovado; o agente prepara a rodada 2 (mesmo id A01,
    outra proposta) e consulta antes de o servidor da rodada 2 subir."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = make_batch(tmp.name)
        store = ab.Store(self.d)
        store.set_item("A01", {"decision": "approved"})
        store.set_finished(True)
        make_batch(tmp.name, round=2, items=[{"id": "A01", "title": "OUTRA PROPOSTA"}])

    def run_cli(self, fn, **kw):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = fn(Namespace(dir=str(self.d), **kw))
        return rc, out.getvalue()

    def test_wait_does_not_return_on_previous_round(self):
        rc, out = self.run_cli(ab.cmd_wait, timeout=1)
        self.assertEqual(rc, 2)
        self.assertIn("TIMEOUT", out)

    def test_summary_ignores_previous_round(self):
        _, out = self.run_cli(ab.cmd_summary, json=True)
        data = json.loads(out)
        self.assertEqual(data["approved"], [])
        self.assertEqual([r["id"] for r in data["pending"]], ["A01"])
        self.assertEqual(data["round"], 2)

    def test_summary_ignores_other_batch_id(self):
        make_batch(self.d, batch_id="outro", items=[{"id": "A01", "title": "z"}])
        _, out = self.run_cli(ab.cmd_summary, json=True)
        self.assertEqual(json.loads(out)["approved"], [])


class CorruptStateTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = make_batch(tmp.name)

    def test_summary_survives_unreadable_decisions_json(self):
        (self.d / "decisions.json").write_text("{nao e json", encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ab.cmd_summary(Namespace(dir=str(self.d), json=True))
        self.assertEqual(len(json.loads(out.getvalue())["pending"]), 2)

    def test_store_survives_decisions_json_that_is_not_an_object(self):
        (self.d / "decisions.json").write_text("[1]", encoding="utf-8")
        store = ab.Store(self.d)
        self.assertEqual(store.state["items"], {})


class PrivateFilesTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self.d = make_batch(tmp.name)
        old = os.umask(0o022)
        self.addCleanup(os.umask, old)

    def mode(self, path):
        return stat.S_IMODE(os.stat(path).st_mode)

    def test_decisions_json_is_created_private(self):
        ab.Store(self.d)
        self.assertEqual(self.mode(self.d / "decisions.json"), 0o600)

    def test_write_private_is_never_group_or_world_readable(self):
        p = self.d / "x.json"
        ab.write_private(p, "{}")
        self.assertEqual(self.mode(p), 0o600)

    def test_save_does_not_follow_a_planted_symlink(self):
        victim = Path(self.tmp) / "victim.txt"
        victim.write_text("ORIGINAL", encoding="utf-8")
        (self.d / "decisions.tmp").symlink_to(victim)
        ab.Store(self.d)
        self.assertEqual(victim.read_text(encoding="utf-8"), "ORIGINAL")
        self.assertEqual(json.loads((self.d / "decisions.json").read_text(encoding="utf-8"))["batch_id"], "t")


class ResetTest(unittest.TestCase):
    def test_reset_clears_finished_at(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ab.Store(make_batch(tmp))
            store.set_finished(True)
            self.assertIn("finished_at", store.state)
            store.reset()
            self.assertNotIn("finished_at", store.state)
            self.assertFalse(store.state["finished"])
