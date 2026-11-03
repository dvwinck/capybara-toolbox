import contextlib
import io
import tempfile
import unittest
from argparse import Namespace

from helpers import ab, make_batch

KEY = "MLK" + "-4608"  # built at run time, like the other fixtures that look like real identifiers


def card(**over):
    item = {"id": "A01", "title": "Do the thing", "fields": [{"label": "What", "text": "plain words"}]}
    item.update(over)
    return item


def board(*items, **extra):
    b = {"batch_id": "t", "title": "T", "items": list(items)}
    b.update(extra)
    return b


def entry(term=KEY, **over):
    e = {"term": term, "explanation": "what it is"}
    e.update(over)
    return e


def has(errs, fragment):
    return any(fragment in e for e in errs)


class GlossaryShapeTest(unittest.TestCase):
    def test_a_card_without_glossary_is_valid(self):
        self.assertEqual(ab.validate(board(card())), [])

    def test_null_counts_as_omitted(self):
        self.assertEqual(ab.validate(board(card(glossary=None))), [])

    def test_a_complete_glossary_is_valid_with_and_without_url(self):
        g = [entry(url="https://example.com/browse/" + KEY), entry("ETL")]
        self.assertEqual(ab.validate(board(card(glossary=g))), [])

    def test_glossary_must_be_a_list(self):
        self.assertTrue(has(ab.validate(board(card(glossary={"term": "x"}))), "'glossary'"))

    def test_an_entry_needs_term_and_explanation(self):
        for bad in ({"term": "X"}, {"explanation": "y"}, {"term": " ", "explanation": "y"}, {"term": "X", "explanation": ""}, "X", None, 3):
            with self.subTest(bad=bad):
                self.assertTrue(has(ab.validate(board(card(glossary=[bad]))), "glossary entry 0"), bad)

    def test_url_must_be_http_or_https_text(self):
        for bad in ("javascript:alert(1)", "ftp://x.org/a", "//x.org", "http://", "https://a b", 5, ""):
            with self.subTest(bad=bad):
                self.assertTrue(has(ab.validate(board(card(glossary=[entry(url=bad)]))), "'url'"), bad)

    def test_a_term_cannot_repeat_ignoring_case(self):
        errs = ab.validate(board(card(glossary=[entry("ETL"), entry("etl")])))
        self.assertTrue(has(errs, "listed twice"))

    def test_the_messages_follow_the_language(self):
        errs = ab.validate(board(card(glossary=[{"term": "X"}])), "pt-BR")
        self.assertTrue(has(errs, "glossario"))

    def test_a_question_card_takes_a_glossary_too(self):
        q = card(choices=[{"id": "a", "label": "A"}, {"id": "b", "label": "B"}], glossary=[entry()])
        self.assertEqual(ab.validate(board(q)), [])


class GlossaryGapsTest(unittest.TestCase):
    def gaps(self, **over):
        return ab.glossary_gaps(card(**over))

    def test_plain_text_has_no_gaps(self):
        self.assertEqual(self.gaps(), [])

    def test_issue_keys_acronyms_and_numbers_are_found_in_order(self):
        text = "ETL blocks %s and PPR-B, see #123" % KEY
        self.assertEqual(self.gaps(fields=[{"label": "Why", "text": text}]), ["ETL", KEY, "PPR-B", "#123"])

    def test_every_place_the_person_reads_is_scanned(self):
        it = card(
            title="About ETL",
            risk={"level": "low", "text": "touches SLA"},
            choices=[{"id": "a", "label": "Use RLS", "effect": "needs DDL"}, {"id": "b", "label": "b"}],
            why="because CDC",
            meta={"Area": "OKR"},
        )
        self.assertEqual(ab.glossary_gaps(it), ["ETL", "SLA", "RLS", "DDL", "CDC", "OKR"])

    def test_a_glossary_term_covers_the_identifier_in_any_card_text(self):
        it = card(fields=[{"label": "Why", "text": "ETL and %s" % KEY}], glossary=[entry("etl"), entry(KEY)])
        self.assertEqual(ab.glossary_gaps(it), [])

    def test_a_term_that_contains_the_identifier_as_a_whole_word_covers_it(self):
        it = card(fields=[{"label": "Why", "text": "the SLA"}], glossary=[entry("SLA (service agreement)")])
        self.assertEqual(ab.glossary_gaps(it), [])

    def test_a_longer_key_is_not_covered_by_its_prefix(self):
        it = card(fields=[{"label": "Why", "text": "PPR-B"}], glossary=[entry("PPR")])
        self.assertEqual(ab.glossary_gaps(it), ["PPR-B"])

    def test_code_spans_are_ignored(self):
        self.assertEqual(self.gaps(fields=[{"label": "What", "text": "run `ETL-RUN` and `#12`"}]), [])

    def test_common_abbreviations_and_standards_are_ignored(self):
        text = "the API returns JSON over HTTPS in UTF-8 with SHA-256, OK, see the PR"
        self.assertEqual(self.gaps(fields=[{"label": "What", "text": text}]), [])

    def test_lowercase_and_mixed_case_words_are_not_identifiers(self):
        self.assertEqual(self.gaps(fields=[{"label": "What", "text": "Etl, state.json, ar_board, X-STATUS.md, A1"}]), [])

    def test_the_glossary_text_itself_is_not_scanned(self):
        it = card(glossary=[entry("ETL", explanation="moves data; SLA applies")])
        self.assertEqual(ab.glossary_gaps(it), [])

    def test_the_card_id_and_tag_are_not_scanned(self):
        self.assertEqual(ab.glossary_gaps(card(id="ZZ-9", tag="URGENT")), [])

    def test_each_identifier_is_listed_once(self):
        self.assertEqual(self.gaps(fields=[{"label": "What", "text": "ETL ETL ETL"}]), ["ETL"])


class GlossaryCheckCommandTest(unittest.TestCase):
    def run_check(self, batch_items, **extra):
        with tempfile.TemporaryDirectory() as tmp:
            import json
            from pathlib import Path
            (Path(tmp) / "batch.json").write_text(json.dumps(board(*batch_items, **extra)), encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = ab.cmd_check(Namespace(dir=tmp))
        return code, out.getvalue(), err.getvalue()

    def test_a_missing_entry_warns_on_stderr_and_does_not_block(self):
        code, out, err = self.run_check([card(id="A07", fields=[{"label": "Why", "text": "blocked by %s" % KEY}])])
        self.assertEqual(code, 0)
        self.assertIn("ok:", out)
        self.assertIn("warning: item A07", err)
        self.assertIn(KEY, err)

    def test_a_covered_batch_prints_no_warning(self):
        code, out, err = self.run_check([card(fields=[{"label": "Why", "text": KEY}], glossary=[entry()])])
        self.assertEqual((code, err), (0, ""))

    def test_the_warning_follows_the_batch_language_and_stays_ascii(self):
        _, _, err = self.run_check([card(fields=[{"label": "Why", "text": "ETL"}])], lang="pt-BR")
        self.assertIn("aviso: o item A01", err)
        self.assertTrue(err.isascii())

    def test_the_bundled_example_has_no_gap(self):
        from helpers import EXAMPLE
        import json
        b = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        self.assertEqual(ab.validate(b), [])
        self.assertEqual(ab.glossary_warnings(b), [])


class GlossaryPageTest(unittest.TestCase):
    def page(self):
        return ab.PAGE

    def test_the_card_renders_the_glossary_open_with_a_safe_link(self):
        page = self.page()
        self.assertIn("function glossHtml", page)
        self.assertIn("h += glossHtml(it);", page)
        self.assertIn(r"/^https?:\/\//i.test(x.url", page)
        self.assertIn('rel="noopener noreferrer"', page)

    def test_the_glossary_text_is_escaped_not_injected(self):
        page = self.page()
        self.assertIn("esc(x.term)", page)
        self.assertIn("rich(x.explanation", page)
        self.assertIn("esc(x.url)", page)


if __name__ == "__main__":
    unittest.main()
