import contextlib
import io
import json
import tempfile
import unittest
from argparse import Namespace

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
