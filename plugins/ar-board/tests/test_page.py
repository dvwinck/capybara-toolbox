import re
import unittest

from helpers import REPO, ab


class PageGuardsTest(unittest.TestCase):
    """Guardas de regressao sobre o JS embutido. O comportamento real foi verificado
    manualmente em um navegador (a suite nao executa JavaScript)."""

    def test_decision_keys_ignore_autorepeat(self):
        self.assertIn("ev.repeat && (k === 'a' || k === 'r' || k === 'm')", ab.PAGE)

    def test_clear_cancels_pending_autosave(self):
        self.assertIn("Object.keys(timers).forEach(k => clearTimeout(timers[k])); pend = {};", ab.PAGE)

    def test_opens_on_first_undecided_item(self):
        self.assertIn("items.findIndex(it => !(S.items[it.id] || {}).decision)", ab.PAGE)

    def test_held_enter_on_a_button_is_swallowed(self):
        self.assertIn("ev.repeat && ev.key === 'Enter' && ev.target.tagName === 'BUTTON'", ab.PAGE)

    def test_clear_waits_for_inflight_requests(self):
        self.assertIn("Promise.all(Array.from(inflight)).then(() => post('/api/reset', {}))", ab.PAGE)


def _luminance(hex_color):
    r, g, b = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]

    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(a, b):
    hi, lo = sorted([_luminance(a), _luminance(b)], reverse=True)
    return (hi + 0.05) / (lo + 0.05)


class PageThemeTest(unittest.TestCase):
    def theme_blocks(self):
        blocks = re.findall(r":root\{([^}]*)\}", ab.PAGE)
        self.assertEqual(len(blocks), 2, "expected a dark :root and a light :root")
        return [dict(re.findall(r"--([\w-]+):(#[0-9a-fA-F]{6})", b)) for b in blocks]

    def test_page_carries_capybara_branding(self):
        batch = {"batch_id": "t", "title": "T", "items": [{"id": "A01", "title": "x"}]}
        page = ab.render_page(batch, {"items": {}}, "tok", True).decode("utf-8")
        self.assertIn('class="mascot"', page)
        self.assertIn('rel="icon"', page)
        for token in ("__MASCOT__", "__FAVICON__", "__TITLE__", "__BOOT__"):
            self.assertNotIn(token, page)

    def test_text_color_pairs_meet_wcag_aa_in_both_themes(self):
        pairs = [("fg", "bg"), ("fg", "panel"), ("fg", "panel2"), ("mut", "bg"), ("mut", "panel"), ("mut", "panel2"),
                 ("ok", "ok-bg"), ("ok", "panel"), ("no", "no-bg"), ("no", "panel"), ("mb", "mb-bg"), ("mb", "panel"),
                 ("acc", "bg"), ("accfg", "acc")]
        for name, theme in zip(("dark", "light"), self.theme_blocks()):
            for fg, bg in pairs:
                with self.subTest(theme=name, pair=f"{fg}/{bg}"):
                    self.assertGreaterEqual(contrast(theme[fg], theme[bg]), 4.5)

    def test_each_theme_declares_its_color_scheme(self):
        blocks = re.findall(r":root\{([^}]*)\}", ab.PAGE)
        self.assertIn("color-scheme:dark", blocks[0])
        self.assertIn("color-scheme:light", blocks[1])
        self.assertIn("accent-color:var(--acc)", ab.PAGE)

    def test_empty_hint_takes_no_space(self):
        self.assertIn("#hint:empty{display:none}", ab.PAGE)

    def test_user_text_that_looks_like_a_template_token_is_left_alone(self):
        batch = {"batch_id": "t", "title": "__BOOT__ __MASCOT__", "items": [{"id": "A01", "title": "x"}]}
        page = ab.render_page(batch, {"items": {}}, "tok", True).decode("utf-8")
        self.assertIn("<title>__BOOT__ __MASCOT__</title>", page)


class MascotTest(unittest.TestCase):
    def test_mascot_matches_the_repository_logo(self):
        svg = (REPO / "assets" / "logo.svg").read_text(encoding="utf-8")
        body = svg.split("</title>", 1)[1].rsplit("</svg>", 1)[0]
        compact = " ".join(line.strip() for line in body.splitlines() if line.strip())
        self.assertEqual(ab.MASCOT_BODY, compact)


class QuestionPageGuardsTest(unittest.TestCase):
    """String guards for the question UI; the real behaviour is verified by hand in a browser
    (the suite does not run JavaScript). The reference is docs/refinements/question-board-prototype.html."""

    def test_a_card_is_a_question_when_it_has_choices_or_is_open(self):
        self.assertIn("const isQ = it => (it.choices != null || it.open === true);", ab.PAGE)

    def test_option_ids_are_looked_up_in_a_null_prototype_map(self):
        self.assertIn("const m = Object.create(null);", ab.PAGE)
        self.assertNotIn("in {}", ab.PAGE)

    def test_other_counts_toward_the_maximum(self):
        self.assertIn("if(!e.other && sel.length >= max)", ab.PAGE)
        self.assertIn("sel.length + (e.other ? 1 : 0) >= max", ab.PAGE)

    def test_enter_never_advances_an_unanswered_question(self):
        self.assertIn("if(!st){showHint(", ab.PAGE)
        self.assertIn("if(k === 'enter' && (ev.target === document.body))", ab.PAGE)

    def test_decision_letters_are_ignored_on_question_cards(self):
        self.assertIn("if(k === 'a' || k === 'r') return;", ab.PAGE)

    def test_number_keys_choose_and_ignore_autorepeat(self):
        self.assertIn("if(/^[1-9]$/.test(k)){if(!ev.repeat) pick(+k); return;}", ab.PAGE)

    def test_options_expose_their_state_to_assistive_technology(self):
        self.assertIn('aria-checked="', ab.PAGE)
        self.assertIn("(it.multiple ? 'checkbox' : 'radio')", ab.PAGE)
        self.assertIn("(it.multiple ? 'group' : 'radiogroup')", ab.PAGE)

    def test_question_title_uses_the_system_serif(self):
        self.assertIn("font:600 24px/1.3 ui-serif", ab.PAGE)

    def test_hidden_attribute_wins_over_display_rules(self):
        self.assertIn("[hidden]{display:none!important}", ab.PAGE)

    def test_typing_an_answer_refreshes_the_card_state(self):
        self.assertIn("if(S.finished || isQ(items[idx])){S.finished = false; render();}", ab.PAGE)

    def test_review_screen_and_offline_export_are_wired(self):
        self.assertIn("function renderReview(){", ab.PAGE)
        self.assertIn("o.kind = 'question'", ab.PAGE)
        self.assertIn("(BOOT.live || hasQ) ? '' : 'none'", ab.PAGE)

    def test_question_labels_are_escaped_not_injected(self):
        batch = {"batch_id": "t", "title": "T", "items": [{
            "id": "Q01", "title": "x", "fields": [{"label": "C", "text": "t"}],
            "choices": [{"id": "a", "label": "</script><img onerror=1>"}, {"id": "b", "label": "B"}]}]}
        page = ab.render_page(batch, {"items": {}}, "tok", True).decode("utf-8")
        self.assertNotIn("</script><img", page)  # the boot JSON cannot close the script tag
        self.assertIn("esc(o.label)", ab.PAGE)  # and the DOM path escapes the label


class QuestionContrastTest(PageThemeTest):
    def test_accent_text_on_both_panels_meets_aa(self):
        for name, theme in zip(("dark", "light"), self.theme_blocks()):
            for fg, bg in (("acc", "panel"), ("acc", "panel2")):
                with self.subTest(theme=name, pair=f"{fg}/{bg}"):
                    self.assertGreaterEqual(contrast(theme[fg], theme[bg]), 4.5)

    def test_control_boundaries_meet_3_to_1(self):
        # WCAG 1.4.11: the border of an option row must stand out; --line (about 1.5:1) cannot do it
        for name, theme in zip(("dark", "light"), self.theme_blocks()):
            for fg, bg in (("mut", "panel"), ("mut", "panel2"), ("acc", "panel")):
                with self.subTest(theme=name, pair=f"{fg}/{bg}"):
                    self.assertGreaterEqual(contrast(theme[fg], theme[bg]), 3.0)

    def test_option_rows_are_outlined_with_a_strong_token(self):
        self.assertIn(".opt{", ab.PAGE)
        opt_rule = re.search(r"\.opt\{[^}]*\}", ab.PAGE).group(0)
        self.assertIn("border:1.5px solid var(--mut)", opt_rule)
        self.assertNotIn("var(--line)", opt_rule)
