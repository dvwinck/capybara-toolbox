import json
import unittest

from helpers import ab

CTX = [{"label": "Contexto", "text": "porque sim"}]
Q1 = {"id": "Q01", "title": "Um", "fields": CTX, "choices": [{"id": "a", "label": "Opcao A"}, {"id": "b", "label": "Opcao B"}],
      "recommended": ["a"], "why": "w"}
Q2 = {"id": "Q02", "title": "Dois", "fields": CTX, "multiple": True, "max": 2, "recommended": ["a", "b"], "why": "w",
      "choices": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}, {"id": "c", "label": "C"}]}
Q3 = {"id": "Q03", "title": "Tres", "fields": CTX, "open": True}
Q4 = {"id": "Q04", "title": "Quatro", "fields": CTX, "choices": [{"id": "x", "label": "X"}, {"id": "y", "label": "Y"}]}
A1 = {"id": "A01", "title": "proposta"}


def batch(*items):
    return {"batch_id": "t", "title": "T", "items": list(items)}


def state(**entries):
    return {"round": 1, "finished": True, "batch_note": "", "items": entries}


def as_json(b, s):
    return json.loads(ab.render_summary(b, s, as_json=True))


class JsonSummaryTest(unittest.TestCase):
    def test_every_answer_kind(self):
        b = batch(Q1, Q2, Q3, Q4)
        s = state(
            Q01={"choice": "a", "comment": "gostei"},
            Q02={"choices": ["a", "b"]},
            Q03={"comment": "limpar-branches"},
            Q04={"other": True, "comment": "outra coisa"},
        )
        data = as_json(b, s)
        rows = {r["id"]: r for r in data["answered"]}
        self.assertEqual(rows["Q01"]["answer"], {"kind": "choice", "id": "a", "label": "Opcao A"})
        self.assertIs(rows["Q01"]["recommended_taken"], True)
        self.assertEqual(rows["Q01"]["comment"], "gostei")
        self.assertEqual(rows["Q02"]["answer"], {"kind": "choices", "ids": ["a", "b"], "labels": ["A", "B"]})
        self.assertIs(rows["Q02"]["recommended_taken"], True)
        self.assertEqual(rows["Q03"]["answer"], {"kind": "open", "text": "limpar-branches"})
        self.assertIsNone(rows["Q03"]["recommended_taken"])
        self.assertEqual(rows["Q04"]["answer"], {"kind": "other", "text": "outra coisa"})
        self.assertIsNone(rows["Q04"]["recommended_taken"])
        self.assertEqual(rows["Q04"]["comment"], "")  # the comment *is* the answer, not repeated
        self.assertEqual(data["pending"], [])
        self.assertEqual(data["unsure"], [])

    def test_recommended_taken_is_false_when_another_option_is_chosen(self):
        data = as_json(batch(Q1), state(Q01={"choice": "b"}))
        self.assertIs(data["answered"][0]["recommended_taken"], False)

    def test_recommended_taken_is_none_without_a_recommendation(self):
        data = as_json(batch(Q4), state(Q04={"choice": "x"}))
        self.assertIsNone(data["answered"][0]["recommended_taken"])

    def test_multiple_with_other_is_not_the_recommendation(self):
        data = as_json(batch(Q2), state(Q02={"choices": ["a", "b"], "other": True, "comment": "mais"}))
        row = data["answered"][0]
        self.assertEqual(row["answer"]["other"], "mais")
        self.assertIs(row["recommended_taken"], False)

    def test_unsure_and_pending(self):
        data = as_json(batch(Q1, Q3, Q4), state(Q01={"decision": "maybe", "comment": "explique melhor"}))
        self.assertEqual([r["id"] for r in data["unsure"]], ["Q01"])
        self.assertEqual(data["unsure"][0]["comment"], "explique melhor")
        self.assertEqual([r["id"] for r in data["pending"]], ["Q03", "Q04"])
        self.assertEqual(data["answered"], [])

    def test_a_stale_choice_id_reads_as_pending(self):
        data = as_json(batch(Q1), state(Q01={"choice": "removida"}))
        self.assertEqual([r["id"] for r in data["pending"]], ["Q01"])
        self.assertEqual(data["answered"], [])

    def test_mixed_board_keeps_proposal_groups(self):
        data = as_json(batch(Q1, A1), state(Q01={"choice": "a"}, A01={"decision": "approved", "comment": "ok"}))
        self.assertEqual([r["id"] for r in data["approved"]], ["A01"])
        self.assertEqual([r["id"] for r in data["answered"]], ["Q01"])
        self.assertEqual(data["pending"], [])

    def test_proposal_only_board_output_is_unchanged(self):
        data = as_json(batch(A1), state(A01={"decision": "approved"}))
        self.assertEqual(set(data), {"batch_id", "round", "finished", "batch_note", "approved", "rejected", "maybe", "pending"})


class NullLimitsTest(unittest.TestCase):
    def test_summary_survives_a_card_with_null_min_and_max(self):
        card = {**Q2, "min": None, "max": None}
        data = as_json(batch(card), state(Q02={"choices": ["a"]}))
        self.assertEqual([r["id"] for r in data["answered"]], ["Q02"])


class TextSummaryTest(unittest.TestCase):
    def test_sections_and_lines(self):
        b = batch(Q1, Q3, Q4)
        s = state(Q01={"choice": "a", "comment": "gostei"}, Q03={"decision": "maybe"})
        out = ab.render_summary(b, s)
        self.assertIn("## Answered (1)", out)
        self.assertIn("- Q01 - Um", out)
        self.assertIn("answer: Opcao A (recommended)", out)
        self.assertIn("user comment: 'gostei'", out)
        self.assertIn("## Need context (1)", out)
        self.assertIn("- Q03 - Tres", out)
        self.assertIn("## No decision (1)", out)
        self.assertLess(out.index("## Answered"), out.index("## No decision"))
        out = ab.render_summary(b, s, lang="pt-BR")  # the pt-BR summary is the one the engine printed before
        self.assertIn("## Respondidas (1)", out)
        self.assertIn("resposta: Opcao A (recomendada)", out)
        self.assertIn("comentario do usuario: 'gostei'", out)
        self.assertIn("## Precisam de contexto (1)", out)
        self.assertIn("## Sem decisao (1)", out)
        self.assertLess(out.index("## Respondidas"), out.index("## Sem decisao"))

    def test_other_and_open_lines(self):
        out = ab.render_summary(batch(Q3, Q4), state(Q03={"comment": "limpar"}, Q04={"other": True, "comment": "x y"}))
        self.assertIn("answer: limpar", out)
        self.assertIn("answer: Other: x y", out)

    def test_proposal_only_text_has_no_question_sections(self):
        out = ab.render_summary(batch(A1), state(A01={"decision": "approved"}))
        self.assertNotIn("Answered", out)
        self.assertNotIn("Need context", out)
        self.assertIn("## Approved (1)", out)


class HelpersTest(unittest.TestCase):
    def test_answer_text(self):
        self.assertEqual(ab.answer_text({"kind": "choice", "id": "a", "label": "A"}), "A")
        self.assertEqual(ab.answer_text({"kind": "choices", "ids": ["a", "b"], "labels": ["A", "B"]}), "A + B")
        self.assertEqual(ab.answer_text({"kind": "choices", "ids": ["a"], "labels": ["A"], "other": "z"}), "A + Other: z")
        self.assertEqual(ab.answer_text({"kind": "other", "text": "z"}), "Other: z")
        self.assertEqual(ab.answer_text({"kind": "other", "text": "z"}, "pt-BR"), "Outra: z")
        self.assertEqual(ab.answer_text({"kind": "open", "text": "z"}), "z")


if __name__ == "__main__":
    unittest.main()
