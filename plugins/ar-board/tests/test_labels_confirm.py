import unittest

from helpers import ab


def board(items=None, **extra):
    b = {"batch_id": "t", "title": "T", "items": items or [{"id": "A01", "title": "x"}]}
    b.update(extra)
    return b


def has(errs, fragment):
    return any(fragment in e for e in errs)


GOOD = {"approve": {"text": "Apagar", "tone": "danger"}, "reject": {"text": "Manter", "tone": "safe"},
        "maybe": {"text": "Depois", "tone": "caution"}}


class LabelsValidateTest(unittest.TestCase):
    def test_a_board_without_labels_is_valid(self):
        self.assertEqual(ab.validate(board()), [])

    def test_labels_with_every_tone_are_valid(self):
        self.assertEqual(ab.validate(board(labels=GOOD)), [])

    def test_the_tone_is_optional_and_null_labels_count_as_omitted(self):
        self.assertEqual(ab.validate(board(labels={"approve": {"text": "Apagar"}})), [])
        self.assertEqual(ab.validate(board(labels=None)), [])

    def test_labels_must_be_an_object(self):
        self.assertTrue(has(ab.validate(board(labels=["Apagar"])), "'labels' deve ser objeto"))

    def test_an_unknown_key_is_rejected_so_a_typo_is_not_silent(self):
        errs = ab.validate(board(labels={"aprove": {"text": "Apagar"}}))
        self.assertTrue(has(errs, "chave desconhecida 'aprove'"), errs)

    def test_each_label_must_be_an_object(self):
        self.assertTrue(has(ab.validate(board(labels={"approve": "Apagar"})), "labels.approve: deve ser objeto"))

    def test_each_label_needs_a_short_non_empty_text(self):
        for bad in (None, "", "   ", 7, "x" * (ab.MAX_LABEL + 1)):
            with self.subTest(text=bad):
                errs = ab.validate(board(labels={"reject": {"text": bad}}))
                self.assertTrue(has(errs, "labels.reject: 'text' obrigatorio"), errs)
        self.assertEqual(ab.validate(board(labels={"reject": {"text": "x" * ab.MAX_LABEL}})), [])

    def test_an_unknown_tone_is_rejected(self):
        errs = ab.validate(board(labels={"maybe": {"text": "Depois", "tone": "red"}}))
        self.assertTrue(has(errs, "labels.maybe: 'tone' deve ser safe, danger ou caution"), errs)

    def test_label_errors_do_not_hide_item_errors(self):
        errs = ab.validate(board(items=[{"id": "A01"}], labels={"x": {}}))
        self.assertTrue(has(errs, "chave desconhecida"), errs)
        self.assertTrue(has(errs, "'title' obrigatorio"), errs)


class ConfirmValidateTest(unittest.TestCase):
    def item(self, **over):
        it = {"id": "A01", "title": "x"}
        it.update(over)
        return board(items=[it])

    def test_confirm_text_is_accepted_and_null_counts_as_omitted(self):
        self.assertEqual(ab.validate(self.item(confirm="Apaga trabalho unico.")), [])
        self.assertEqual(ab.validate(self.item(confirm=None)), [])

    def test_confirm_must_be_non_empty_text(self):
        for bad in ("", "   ", 3, ["x"]):
            with self.subTest(confirm=bad):
                self.assertTrue(has(ab.validate(self.item(confirm=bad)), "'confirm' deve ser texto nao vazio"))

    def test_confirm_is_rejected_on_question_cards(self):
        errs = ab.validate(self.item(confirm="certeza?", open=True, fields=[{"label": "Contexto", "text": "c"}]))
        self.assertTrue(has(errs, "'confirm' nao vale em card de pergunta"), errs)


class LabelsSummaryTest(unittest.TestCase):
    BATCH = {"batch_id": "t", "title": "T", "labels": GOOD,
             "items": [{"id": "A01", "title": "um"}, {"id": "A02", "title": "dois"}, {"id": "A03", "title": "tres"}]}
    STATE = {"round": 1, "finished": True, "batch_note": "",
             "items": {"A01": {"decision": "approved"}, "A02": {"decision": "rejected"}}}

    def test_the_text_summary_uses_the_custom_wording(self):
        out = ab.render_summary(self.BATCH, self.STATE)
        self.assertIn("## Apagar (1)", out)
        self.assertIn("## Manter (1)", out)
        self.assertIn("## Depois (0)", out)
        self.assertNotIn("## Aprovados", out)

    def test_the_json_summary_keeps_its_keys(self):
        import json
        data = json.loads(ab.render_summary(self.BATCH, self.STATE, as_json=True))
        self.assertEqual([r["id"] for r in data["approved"]], ["A01"])
        self.assertEqual([r["id"] for r in data["rejected"]], ["A02"])
        self.assertEqual([r["id"] for r in data["pending"]], ["A03"])

    def test_a_partial_labels_object_only_renames_what_it_names(self):
        b = {**self.BATCH, "labels": {"approve": {"text": "Apagar"}}}
        out = ab.render_summary(b, self.STATE)
        self.assertIn("## Apagar (1)", out)
        self.assertIn("## Rejeitados (1)", out)
        self.assertIn("## Talvez (0)", out)

    def test_boards_without_labels_are_unchanged(self):
        b = {k: v for k, v in self.BATCH.items() if k != "labels"}
        out = ab.render_summary(b, self.STATE)
        self.assertIn("## Aprovados (1)", out)
        self.assertIn("## Rejeitados (1)", out)
