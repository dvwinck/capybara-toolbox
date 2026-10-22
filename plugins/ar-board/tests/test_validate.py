import contextlib
import io
import json
import tempfile
import unittest
from argparse import Namespace

from helpers import EXAMPLE, ab, make_batch


def batch(**item):
    return {"batch_id": "t", "title": "T", "items": [{"id": "A01", "title": "x", **item}]}


class ValidateTest(unittest.TestCase):
    def test_shipped_example_is_valid(self):
        data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        self.assertEqual(ab.validate(data), [])

    def test_minimal_item_is_valid(self):
        self.assertEqual(ab.validate(batch()), [])

    def test_round_must_be_positive_integer(self):
        for bad in ("x", "2", 0, -1, 1.5, True, None):
            with self.subTest(round=bad):
                b = batch()
                b["round"] = bad
                self.assertTrue(any("'round'" in e for e in ab.validate(b)))
        b = batch()
        b["round"] = 3
        self.assertEqual(ab.validate(b), [])

    def test_optional_item_fields_must_have_the_right_type(self):
        cases = [
            ("image", 5),
            ("tag", 1),
            ("meta", ["a"]),
            ("risk", "alto"),
            ("risk", {"level": 1}),
            ("risk", {"level": "alto", "text": []}),
            ("fields", [{"label": 1, "text": "x"}]),
            ("fields", [{"label": "a", "text": None}]),
        ]
        for key, value in cases:
            with self.subTest(**{key: value}):
                errs = ab.validate(batch(**{key: value}))
                self.assertTrue(any("'%s'" % key in e for e in errs), errs)

    def test_null_optional_fields_count_as_absent(self):
        for key in ("tag", "image", "meta", "risk", "fields"):
            with self.subTest(key=key):
                self.assertEqual(ab.validate(batch(**{key: None})), [])

    def test_fields_that_are_falsy_but_not_null_are_still_rejected(self):
        for bad in ({}, "", 0, False):
            with self.subTest(fields=bad):
                self.assertTrue(any("'fields'" in e for e in ab.validate(batch(fields=bad))))

    def test_risk_keys_are_typed_only_when_present(self):
        self.assertEqual(ab.validate(batch(risk={})), [])
        self.assertEqual(ab.validate(batch(risk={"level": "alto"})), [])

    def test_build_and_page_work_with_null_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = make_batch(tmp, items=[{"id": "A01", "title": "x", "fields": None}])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ab.cmd_build(Namespace(dir=str(d), lang=None)), 0)
            self.assertIn("(it.fields || [])", ab.PAGE)  # the page treats null fields as none

    def test_build_works_with_null_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = make_batch(tmp, items=[{"id": "A01", "title": "x", "image": None}])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ab.cmd_build(Namespace(dir=str(d), lang=None)), 0)

    def test_load_batch_rejects_bad_round(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = make_batch(tmp, round="x")
            with self.assertRaises(SystemExit):
                ab.load_batch(d)
