import copy
import json
import tempfile
import unittest

from helpers import LiveServer, ab, make_batch

CTX = [{"label": "Contexto", "text": "porque sim"}]
ITEMS = [
    {"id": "Q01", "title": "Um", "fields": CTX, "choices": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
     "recommended": ["a"], "why": "w"},
    {"id": "Q02", "title": "Dois", "fields": CTX, "multiple": True, "min": 1, "max": 2,
     "choices": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}, {"id": "c", "label": "C"}]},
    {"id": "Q03", "title": "Tres", "fields": CTX, "open": True},
    {"id": "A01", "title": "proposta"},
]


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = make_batch(tmp.name, items=ITEMS)
        self.store = ab.Store(self.d)

    def entry(self, iid):
        return self.store.state["items"].get(iid)

    def snapshot(self):
        return json.dumps(self.store.state["items"], sort_keys=True)

    def rejected(self, iid, body):
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.store.set_item(iid, body)
        self.assertEqual(self.snapshot(), before, "a rejected request must leave no trace")


class SingleChoiceTest(Base):
    def test_choose_switch_and_undo(self):
        self.store.set_item("Q01", {"choice": "a"})
        self.assertEqual(self.entry("Q01")["choice"], "a")
        self.store.set_item("Q01", {"choice": "b"})
        self.assertEqual(self.entry("Q01")["choice"], "b")
        self.store.set_item("Q01", {"choice": None})
        self.assertIsNone(self.entry("Q01"))

    def test_other_and_choice_are_exclusive(self):
        self.store.set_item("Q01", {"choice": "a"})
        self.store.set_item("Q01", {"other": True, "comment": "algo"})
        e = self.entry("Q01")
        self.assertNotIn("choice", e)
        self.assertTrue(e["other"])
        self.store.set_item("Q01", {"choice": "b"})
        e = self.entry("Q01")
        self.assertEqual(e["choice"], "b")
        self.assertNotIn("other", e)
        self.assertEqual(e["comment"], "algo")  # a comment survives

    def test_more_context_clears_the_answer_and_is_cleared_by_one(self):
        self.store.set_item("Q01", {"choice": "a"})
        self.store.set_item("Q01", {"decision": "maybe", "choice": None, "other": False})
        self.assertEqual(self.entry("Q01"), {"decision": "maybe", "at": self.entry("Q01")["at"]})
        self.store.set_item("Q01", {"choice": "b"})
        self.assertNotIn("decision", self.entry("Q01"))

    def test_clearing_decision_with_null(self):
        self.store.set_item("Q01", {"decision": "maybe"})
        self.store.set_item("Q01", {"decision": None})
        self.assertIsNone(self.entry("Q01"))

    def test_invalid_requests_leave_no_trace(self):
        self.store.set_item("Q01", {"choice": "a", "comment": "k"})
        for body in (
            {"choice": "zzz"},
            {"choice": 3},
            {"choice": ["a"]},
            {"choices": ["a"]},  # list on a single-choice card
            {"other": "sim"},
            {"decision": "approved"},
            {"decision": "rejected"},
            {"decision": "maybe", "choice": "a"},  # contradictory
            {"decision": "maybe", "other": True},
        ):
            with self.subTest(body=body):
                self.rejected("Q01", body)


class MultipleChoiceTest(Base):
    def test_set_a_list_and_empty_it(self):
        self.store.set_item("Q02", {"choices": ["a", "c"]})
        self.assertEqual(self.entry("Q02")["choices"], ["a", "c"])
        self.store.set_item("Q02", {"choices": []})
        self.assertIsNone(self.entry("Q02"))

    def test_other_can_join_a_selection(self):
        self.store.set_item("Q02", {"choices": ["a"], "other": True, "comment": "mais um"})
        e = self.entry("Q02")
        self.assertEqual(e["choices"], ["a"])
        self.assertTrue(e["other"])

    def test_max_counts_other(self):
        self.rejected("Q02", {"choices": ["a", "b", "c"]})  # 3 > max 2
        self.rejected("Q02", {"choices": ["a", "b"], "other": True})  # 2 + other = 3 > max 2
        self.store.set_item("Q02", {"choices": ["a"], "other": True})  # 1 + other = 2 is fine
        self.rejected("Q02", {"choices": ["a", "b"]})  # other is already on: 3 > max 2

    def test_invalid_lists_leave_no_trace(self):
        for body in (
            {"choices": ["a", "a"]},
            {"choices": ["zzz"]},
            {"choices": [1]},
            {"choices": "a"},
            {"choice": "a"},  # scalar on a multiple card
        ):
            with self.subTest(body=body):
                self.rejected("Q02", body)


class OpenAndProposalCardsTest(Base):
    def test_open_card_takes_only_comment_and_maybe(self):
        self.store.set_item("Q03", {"comment": "limpar"})
        self.assertEqual(self.entry("Q03")["comment"], "limpar")
        self.store.set_item("Q03", {"decision": "maybe"})
        for body in ({"choice": "a"}, {"choices": ["a"]}, {"other": True}, {"decision": "approved"}):
            with self.subTest(body=body):
                self.rejected("Q03", body)

    def test_proposal_card_rejects_question_keys(self):
        for body in ({"choice": "a"}, {"choices": []}, {"other": True}):
            with self.subTest(body=body):
                self.rejected("A01", body)
        self.store.set_item("A01", {"decision": "approved"})  # unchanged behaviour
        self.assertEqual(self.entry("A01")["decision"], "approved")


class AnswerOfTest(unittest.TestCase):
    Q1, Q2, Q3 = ITEMS[0], ITEMS[1], ITEMS[2]

    def test_pending_when_nothing_is_answered(self):
        for card in (self.Q1, self.Q2, self.Q3):
            with self.subTest(card=card["id"]):
                self.assertIsNone(ab.answer_of(card, None))
                self.assertIsNone(ab.answer_of(card, {}))

    def test_single_choice(self):
        self.assertEqual(ab.answer_of(self.Q1, {"choice": "b"}), {"kind": "choice", "id": "b", "label": "B"})

    def test_other_needs_text(self):
        self.assertIsNone(ab.answer_of(self.Q1, {"other": True}))
        self.assertIsNone(ab.answer_of(self.Q1, {"other": True, "comment": "   "}))
        self.assertEqual(ab.answer_of(self.Q1, {"other": True, "comment": " algo "}), {"kind": "other", "text": "algo"})

    def test_open_needs_text(self):
        self.assertIsNone(ab.answer_of(self.Q3, {"comment": " "}))
        self.assertEqual(ab.answer_of(self.Q3, {"comment": "limpar"}), {"kind": "open", "text": "limpar"})

    def test_multiple_respects_min_and_other(self):
        self.assertEqual(ab.answer_of(self.Q2, {"choices": ["a", "c"]}),
                         {"kind": "choices", "ids": ["a", "c"], "labels": ["A", "C"]})
        self.assertIsNone(ab.answer_of(self.Q2, {"choices": []}))
        self.assertIsNone(ab.answer_of(self.Q2, {"choices": ["a"], "other": True}))  # other without text
        self.assertEqual(ab.answer_of(self.Q2, {"choices": ["a"], "other": True, "comment": "x"}),
                         {"kind": "choices", "ids": ["a"], "labels": ["A"], "other": "x"})
        card = copy.deepcopy(self.Q2)
        card["min"] = 2
        self.assertIsNone(ab.answer_of(card, {"choices": ["a"]}))

    def test_null_min_and_max_count_as_omitted(self):
        card = copy.deepcopy(self.Q2)
        card["min"] = None
        card["max"] = None
        self.assertEqual(ab.validate({"batch_id": "t", "title": "T", "items": [card]}), [])
        self.assertEqual(ab.answer_of(card, {"choices": ["a"]}), {"kind": "choices", "ids": ["a"], "labels": ["A"]})
        self.assertIsNone(ab.answer_of(card, {"choices": []}))

    def test_more_context_wins_over_everything(self):
        self.assertEqual(ab.answer_of(self.Q1, {"decision": "maybe", "choice": "a"}), {"kind": "unsure"})

    def test_a_choice_id_that_no_longer_exists_is_pending(self):
        self.assertIsNone(ab.answer_of(self.Q1, {"choice": "removida"}))
        self.assertEqual(ab.answer_of(self.Q2, {"choices": ["a", "removida"]}),
                         {"kind": "choices", "ids": ["a"], "labels": ["A"]})
        self.assertIsNone(ab.answer_of(self.Q2, {"choices": ["removida"]}))

    def test_ids_named_like_object_internals_are_plain_ids(self):
        card = {"id": "Q", "title": "t", "fields": CTX,
                "choices": [{"id": "constructor", "label": "C"}, {"id": "__proto__", "label": "P"}]}
        self.assertEqual(ab.answer_of(card, {"choice": "constructor"}), {"kind": "choice", "id": "constructor", "label": "C"})
        self.assertEqual(ab.answer_of(card, {"choice": "__proto__"}), {"kind": "choice", "id": "__proto__", "label": "P"})
        self.assertIsNone(ab.answer_of(card, {"choice": "toString"}))


class ValidStateTest(unittest.TestCase):
    def state(self, entry):
        return {"batch_id": "t", "round": 1, "items": {"Q01": entry}}

    def test_well_formed_answers_are_accepted(self):
        for entry in ({"choice": "a"}, {"choices": ["a", "b"]}, {"other": True, "comment": "x"}, {"decision": "maybe"}):
            with self.subTest(entry=entry):
                self.assertTrue(ab.valid_state(self.state(entry)))

    def test_hand_edited_wrong_types_are_unreadable(self):
        for entry in ({"choice": ["a"]}, {"choice": 3}, {"choices": "a"}, {"choices": [1]},
                      {"choices": {"a": 1}}, {"other": "sim"}, {"other": 1}):
            with self.subTest(entry=entry):
                self.assertFalse(ab.valid_state(self.state(entry)))

    def test_a_state_with_wrong_types_is_ignored_on_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = make_batch(tmp, items=ITEMS)
            (d / "decisions.json").write_text(json.dumps(
                {"batch_id": "t", "round": 1, "items": {"Q01": {"choice": ["a"]}}, "batch_note": ""}), encoding="utf-8")
            store = ab.Store(d)
            self.assertEqual(store.state["items"], {})


class HttpRoundTripTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = make_batch(tmp.name, items=ITEMS)

    def saved(self):
        return json.loads((self.d / "decisions.json").read_text(encoding="utf-8"))["items"]

    def test_choice_round_trip(self):
        with LiveServer(self.d) as s:
            self.assertEqual(s.post("/api/item", {"id": "Q01", "choice": "a"})[0], 200)
            self.assertEqual(self.saved()["Q01"]["choice"], "a")
            self.assertEqual(s.post("/api/item", {"id": "Q02", "choices": ["a", "b"], "other": False, "choice": None})[0], 200)
            self.assertEqual(self.saved()["Q02"]["choices"], ["a", "b"])

    def test_the_page_body_for_each_card_kind_is_accepted(self):
        with LiveServer(self.d) as s:
            self.assertEqual(s.post("/api/item", {"id": "Q01", "decision": None, "choice": "b", "choices": None, "other": False})[0], 200)
            self.assertEqual(s.post("/api/item", {"id": "Q02", "decision": None, "choice": None, "choices": ["c"], "other": False})[0], 200)
            self.assertEqual(s.post("/api/item", {"id": "Q03", "decision": "maybe"})[0], 200)

    def test_invalid_answers_are_400_and_leave_no_trace(self):
        with LiveServer(self.d) as s:
            self.assertEqual(s.post("/api/item", {"id": "Q01", "choice": "zzz"})[0], 400)
            self.assertEqual(s.post("/api/item", {"id": "Q02", "choices": ["a", "b", "c"]})[0], 400)
            self.assertEqual(s.post("/api/item", {"id": "A01", "choice": "a"})[0], 400)
            s.post("/api/note", {"text": "n"})  # forces a save
            self.assertEqual(self.saved(), {})


if __name__ == "__main__":
    unittest.main()
