import contextlib
import io
import json
import tempfile
import unittest
from argparse import Namespace

from helpers import ab, make_batch


def card(**over):
    item = {
        "id": "Q01",
        "title": "Qual?",
        "fields": [{"label": "Contexto", "text": "porque sim"}],
        "choices": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
    }
    item.update(over)
    return item


def board(*items):
    return {"batch_id": "t", "title": "T", "items": list(items)}


def errors(**over):
    return ab.validate(board(card(**over)))


def has(errs, fragment):
    return any(fragment in e for e in errs)


class QuestionKindTest(unittest.TestCase):
    def test_minimal_question_is_valid(self):
        self.assertEqual(errors(), [])

    def test_proposal_cards_are_untouched(self):
        self.assertEqual(ab.validate(board({"id": "A01", "title": "x"})), [])
        self.assertFalse(ab.is_question({"id": "A01", "title": "x"}))
        self.assertFalse(ab.is_question({"id": "A01", "title": "x", "open": False}))
        self.assertFalse(ab.is_question({"id": "A01", "title": "x", "choices": None, "open": None}))
        self.assertTrue(ab.is_question({"id": "Q", "title": "x", "choices": []}))  # present, so validated (and rejected)
        self.assertTrue(ab.is_question({"id": "Q", "title": "x", "open": True}))

    def test_mixed_board_is_valid(self):
        self.assertEqual(ab.validate(board(card(), {"id": "A01", "title": "proposta"})), [])

    def test_open_must_be_boolean(self):
        self.assertTrue(has(errors(open="sim"), "'open'"))


class ChoicesTest(unittest.TestCase):
    def test_option_count_is_two_to_eight(self):
        def n_choices(n):
            return [{"id": "o%d" % i, "label": "O%d" % i} for i in range(n)]

        for n in (0, 1, 9):
            with self.subTest(n=n):
                self.assertTrue(has(errors(choices=n_choices(n)), "'choices'"))
        for n in (2, 8):
            with self.subTest(n=n):
                self.assertEqual(errors(choices=n_choices(n)), [])

    def test_choices_must_be_a_list(self):
        for bad in ("a", {"id": "a"}, 5):
            with self.subTest(choices=bad):
                self.assertTrue(has(errors(choices=bad), "'choices'"))

    def test_option_ids_are_restricted(self):
        for bad in ("", "a b", "x" * 33, 5, None, "ç", "a/b"):
            with self.subTest(id=bad):
                self.assertTrue(has(errors(choices=[{"id": bad, "label": "A"}, {"id": "b", "label": "B"}]), "'id'"))

    def test_ids_named_like_object_internals_are_accepted(self):
        for name in ("constructor", "__proto__", "toString", "A-1_b", "x" * 32):
            with self.subTest(id=name):
                self.assertEqual(errors(choices=[{"id": name, "label": "A"}, {"id": "b", "label": "B"}]), [])

    def test_duplicate_ids_are_rejected(self):
        self.assertTrue(has(errors(choices=[{"id": "a", "label": "A"}, {"id": "a", "label": "B"}]), "duplicado"))

    def test_label_is_required_and_text(self):
        for bad in (None, "", "   ", 3):
            with self.subTest(label=bad):
                self.assertTrue(has(errors(choices=[{"id": "a", "label": bad}, {"id": "b", "label": "B"}]), "'label'"))

    def test_effect_is_optional_text(self):
        self.assertEqual(errors(choices=[{"id": "a", "label": "A", "effect": "x"}, {"id": "b", "label": "B"}]), [])
        self.assertTrue(has(errors(choices=[{"id": "a", "label": "A", "effect": 1}, {"id": "b", "label": "B"}]), "'effect'"))

    def test_option_must_be_an_object(self):
        self.assertTrue(has(errors(choices=["a", "b"]), "deve ser objeto"))


class OpenCardTest(unittest.TestCase):
    def test_open_card_has_no_choices(self):
        self.assertEqual(errors(choices=None, open=True), [])
        self.assertTrue(has(errors(open=True), "'open' nao combina com 'choices'"))

    def test_open_card_rejects_multiple_recommended_and_limits(self):
        for key, value in (("multiple", True), ("min", 1), ("max", 2), ("recommended", ["a"]), ("why", "x")):
            with self.subTest(key=key):
                self.assertTrue(has(errors(choices=None, open=True, **{key: value}), "'open' nao combina com '%s'" % key))


class MultipleTest(unittest.TestCase):
    THREE = [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}, {"id": "c", "label": "C"}]

    def test_valid_multiple(self):
        self.assertEqual(errors(choices=self.THREE, multiple=True), [])
        self.assertEqual(errors(choices=self.THREE, multiple=True, min=1, max=2), [])
        self.assertEqual(errors(choices=self.THREE, multiple=True, min=3, max=3), [])

    def test_multiple_must_be_boolean(self):
        self.assertTrue(has(errors(multiple="sim"), "'multiple'"))

    def test_min_and_max_must_be_integers_and_not_bool(self):
        for key in ("min", "max"):
            for bad in ("1", 1.5, True, [1]):
                with self.subTest(key=key, value=bad):
                    self.assertTrue(has(errors(choices=self.THREE, multiple=True, **{key: bad}), "'%s'" % key))

    def test_min_and_max_need_multiple(self):
        for key in ("min", "max"):
            with self.subTest(key=key):
                self.assertTrue(has(errors(**{key: 1}), "so vale com 'multiple'"))

    def test_range_must_fit_the_option_count(self):
        for kw in ({"min": 0}, {"min": 2, "max": 1}, {"max": 4}, {"min": 4}):
            with self.subTest(**kw):
                self.assertTrue(has(errors(choices=self.THREE, multiple=True, **kw), "min <= max"))


class RecommendedTest(unittest.TestCase):
    def test_recommended_must_name_existing_ids(self):
        self.assertEqual(errors(recommended=["a"], why="x"), [])
        self.assertTrue(has(errors(recommended=["zzz"], why="x"), "'recommended'"))

    def test_recommended_needs_a_reason(self):
        for why in (None, "", "  "):
            with self.subTest(why=why):
                self.assertTrue(has(errors(recommended=["a"], why=why), "'why'"))

    def test_single_choice_takes_at_most_one_recommendation(self):
        self.assertTrue(has(errors(recommended=["a", "b"], why="x"), "'recommended'"))

    def test_multiple_recommendation_respects_max(self):
        three = MultipleTest.THREE
        self.assertEqual(errors(choices=three, multiple=True, max=2, recommended=["a", "b"], why="x"), [])
        self.assertTrue(has(errors(choices=three, multiple=True, max=2, recommended=["a", "b", "c"], why="x"), "'recommended'"))

    def test_recommended_must_be_a_list_of_text_without_duplicates(self):
        for bad in ("a", [1], ["a", "a"]):
            with self.subTest(recommended=bad):
                self.assertTrue(has(errors(recommended=bad, why="x"), "'recommended'"))

    def test_why_must_be_text(self):
        self.assertTrue(has(errors(why=3), "'why'"))


class ContextTest(unittest.TestCase):
    def test_question_needs_context(self):
        for bad in (None, [], [{"label": "Contexto", "text": "   "}]):
            with self.subTest(fields=bad):
                self.assertTrue(has(errors(fields=bad), "contexto"))

    def test_open_card_needs_context_too(self):
        self.assertTrue(has(errors(choices=None, open=True, fields=None), "contexto"))

    def test_proposal_does_not_need_context(self):
        self.assertEqual(ab.validate(board({"id": "A01", "title": "x"})), [])


class CheckWarningTest(unittest.TestCase):
    def run_check(self, n):
        with tempfile.TemporaryDirectory() as tmp:
            d = make_batch(tmp, items=[card(id="Q%02d" % i) for i in range(n)])
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = ab.cmd_check(Namespace(dir=str(d)))
            return rc, out.getvalue(), err.getvalue()

    def test_eight_questions_do_not_warn(self):
        rc, out, err = self.run_check(8)
        self.assertEqual(rc, 0)
        self.assertIn("ok: 8 itens", out)
        self.assertEqual(err, "")

    def test_nine_questions_warn_but_pass(self):
        rc, out, err = self.run_check(9)
        self.assertEqual(rc, 0)
        self.assertIn("aviso", err)
        self.assertIn("9 perguntas", err)

    def test_shipped_question_example_is_valid(self):
        from helpers import ROOT

        path = ROOT / "skills" / "question-board" / "examples" / "batch.example.json"
        if path.exists():  # created in Task 5
            self.assertEqual(ab.validate(json.loads(path.read_text(encoding="utf-8"))), [])


class DocumentedExamplesTest(unittest.TestCase):
    def test_card_examples_in_the_docs_pass_check(self):
        import re

        from helpers import ROOT

        found = 0
        for rel in ("docs/reference.md", "docs/pt-BR/guia-completo.md"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            for block in re.findall(r"```json\n(.*?)```", text, re.S):
                try:
                    data = json.loads(block)
                except ValueError:
                    continue
                if isinstance(data, dict) and "choices" in data and "title" in data:
                    found += 1
                    with self.subTest(doc=rel):
                        self.assertEqual(ab.validate(board(data)), [])
        self.assertGreaterEqual(found, 2)
