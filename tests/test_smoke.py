import shutil
import tempfile
import unittest

from helpers import ROOT, LiveServer, ab, make_batch


class SmokeTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = make_batch(tmp.name)

    def test_example_batch_loads(self):
        shutil.copy(ROOT / "examples" / "batch.example.json", self.d / "batch.json")
        self.assertEqual(ab.load_batch(self.d)["batch_id"], "exemplo-2026-10-12")

    def test_page_requires_token(self):
        with LiveServer(self.d) as s:
            self.assertEqual(s.get("/")[0], 403)
            self.assertEqual(s.get("/?t=tok")[0], 200)
