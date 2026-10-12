import json
import socket
import tempfile
import unittest
from argparse import Namespace

from helpers import ab, make_batch


class ServePortInUseTest(unittest.TestCase):
    def test_port_in_use_does_not_archive_previous_round(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = make_batch(tmp)
            ab.Store(d).set_item("A01", {"decision": "approved"})
            make_batch(tmp, round=2)  # rodada nova esperando para ser servida
            with socket.socket() as busy:
                busy.bind(("127.0.0.1", 0))
                busy.listen()
                port = busy.getsockname()[1]
                with self.assertRaises(SystemExit):
                    ab.cmd_serve(Namespace(dir=str(d), port=port, open=False, exit_on_finish=False))
            self.assertEqual(sorted(p.name for p in d.iterdir()), ["batch.json", "decisions.json"])
            self.assertEqual(json.loads((d / "decisions.json").read_text(encoding="utf-8"))["round"], 1)
