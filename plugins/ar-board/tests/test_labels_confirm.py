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
