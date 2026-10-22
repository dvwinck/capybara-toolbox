import re
import unicodedata
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
        self.assertIn("items.findIndex(it => !status(it))", ab.PAGE)

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
        self.assertIn("if(k === 'enter' && (ev.target === document.body || ev.target.classList.contains('opt')))", ab.PAGE)

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

    def test_keyboard_activation_keeps_the_focus_on_the_option(self):
        # Enter/Space on a focused option re-renders the card; without this the focus drops to <body>
        # and a keyboard user cannot toggle the next option of a multiple-choice card
        self.assertIn("const n = +b.dataset.n, kb = ev.detail === 0, before = idx;", ab.PAGE)
        self.assertIn("if(kb && document.activeElement !== $('#cmt'))", ab.PAGE)

    def test_enter_on_a_focused_option_confirms_instead_of_toggling(self):
        # a focused <button> fires click on Enter; the handler must take Enter first (preventDefault) so a
        # keyboard user never accepts an option, recommended or not, by pressing Enter to confirm
        self.assertIn("ev.target.classList.contains('opt')", ab.PAGE)
        self.assertIn("{ev.preventDefault(); confirmCard(); return;}", ab.PAGE)

    def test_a_stale_saved_option_id_is_dropped_when_the_selection_changes(self):
        self.assertIn("const lab = qlabels(it), sel = (e.choices || []).filter(i => i in lab);", ab.PAGE)
        self.assertIn("delete e.decision;\n    e.choices = sel;", ab.PAGE)

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


# ---------------------------------------------------------------- the switchable language (ar-board 1.4.0)

PT_WORDS = {  # words of the old Portuguese page: any of them in a literal outside the table is a leftover
    "aprovar", "rejeitar", "talvez", "pular", "comentar", "escolher", "confirmar", "contexto", "navegar", "avancar",
    "decidir", "comentario", "resposta", "respostas", "obrigatoria", "opcional", "lote", "itens", "rodada", "decisao",
    "decisoes", "concluir", "concluido", "avisar", "agente", "baixar", "copiar", "copiado", "limpar", "resultado", "nota",
    "observacao", "aperte", "cancela", "confirmacao", "cancelada", "escreva", "campo", "maximo", "opcoes", "opcao",
    "desmarque", "marcada", "precisa", "precisam", "revise", "responder", "alterar", "voltar", "corrigir", "conexao",
    "servidor", "cole", "arquivo", "vivo", "recomendada", "recomendamos", "outra", "pergunta", "aberta", "primeiro",
    "respondida", "respondidas", "terminei", "volte", "diga", "sozinho", "todas", "deste", "mesmo", "assim", "proxima",
    "mudar", "risco", "anterior", "proximo", "salva", "foca", "vale", "qualquer", "aprovou", "rejeitou", "ficou", "duvida",
    "treina", "sim", "nao", "sem", "idioma", "sair", "escolha", "mais",
}
PROSE = re.compile(r"[A-Za-zÀ-ɏ]{4,}\s+[A-Za-zÀ-ɏ]{4,}")  # two words: text, not a token
JS_LITERAL = re.compile(r"'(?:[^'\\\n]|\\.)*'|\"(?:[^\"\\\n]|\\.)*\"")
TAG_BITS = re.compile(r"<[^>]*>|<[^>]*$|^[^<]*>")  # whole tags, an unclosed tag at the end, a tag's tail at the start
ALLOWED_TEXT = ("Capybara Toolbox",)  # the brand line in the footer


def page_body():
    """(markup of <body> before the script, the script's code)."""
    body = ab.PAGE.split("<body>", 1)[1]
    script = re.search(r"<script>(.*?)</script>", body, re.S).group(1)
    return body[:body.index("<script>")], script


def plain(text):
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("ascii").lower()


def looks_like_text(fragment):
    clean = TAG_BITS.sub(" ", fragment)
    words = set(re.split(r"[^a-z]+", plain(clean)))
    return bool(PROSE.search(clean)) or bool(words & PT_WORDS)


class PageLanguageGuardTest(unittest.TestCase):
    """The page's text comes from the I18N table: no literal of the markup or the JavaScript may read as prose
    (in either language), and every key the page asks for exists, and every key of the table is asked for."""

    def test_no_literal_of_the_page_reads_as_text_outside_the_table(self):
        markup, script = page_body()
        left = [m.group(0) for m in JS_LITERAL.finditer(script) if looks_like_text(m.group(0)[1:-1])]
        for node in re.split(r"<[^>]*>", markup):
            node = node.strip()
            if node and not any(a in node for a in ALLOWED_TEXT) and looks_like_text(node):
                left.append(node)
        self.assertEqual(left, [], "text left outside the I18N table:\n" + "\n".join(left))

    def test_every_key_the_page_uses_exists_and_every_key_of_the_table_is_used(self):
        markup, script = page_body()
        used = set(re.findall(r"T\('([a-z_]+)'", script)) | set(re.findall(r'data-tp?="([a-z_]+)"', markup))
        self.assertEqual(used - set(ab.I18N["en"]), set(), "keys missing from the table")
        self.assertEqual(set(ab.I18N["en"]) - used, set(), "table keys the page never uses")
        dynamic = set(re.findall(r"(?<!function )T\((?!')[^)]*\)", script))
        self.assertEqual(dynamic, {"T(el.dataset.t)", "T(el.dataset.tp)"})  # the only non-literal lookups

    def test_the_precedence_is_saved_toggle_then_boot_then_english(self):
        self.assertIn("let lang = LANGS.includes(BOOT.lang) ? BOOT.lang : 'en';", ab.PAGE)
        self.assertIn("const saved = localStorage.getItem('ar-board:lang'); if(LANGS.includes(saved)) lang = saved;", ab.PAGE)
        self.assertIn("localStorage.setItem('ar-board:lang', l)", ab.PAGE)
        self.assertIn("function setLang(l){if(!LANGS.includes(l)) return;", ab.PAGE)

    def test_the_toggle_sits_in_the_header_and_sets_html_lang(self):
        self.assertIn('<html lang="en">', ab.PAGE)
        self.assertIn("document.documentElement.lang = lang;", ab.PAGE)
        self.assertIn('<button type="button" data-lang="en">EN</button><button type="button" data-lang="pt-BR">PT</button>', ab.PAGE)
        self.assertIn("if(b) setLang(b.dataset.lang);", ab.PAGE)
        self.assertLess(ab.PAGE.index('id="live"'), ab.PAGE.index('id="lang"'))

    def test_switching_re_renders_without_a_reload_and_keeps_the_card_labels(self):
        self.assertIn("applyLang(); render();}", ab.PAGE)
        self.assertIn("  applyLabels();\n", ab.PAGE)  # batch labels win over the table after every switch
        self.assertIn("$('#bF').textContent = hasQ ? T('review_finish') : T('finish');", ab.PAGE)
        self.assertNotIn("location.reload", ab.PAGE)

    def test_risk_levels_accept_english_words_and_keep_the_css_classes(self):
        for pair in ("['low','baixo']", "['medium','medio']", "['high','alto']", "['baixo','baixo']"):
            self.assertIn(pair, ab.PAGE)
        self.assertIn("const RISK = Object.create(null);", ab.PAGE)
        self.assertIn("const lvl = RISK[norm(it.risk.level)] || 'medio';", ab.PAGE)
        for cls in (".risk.baixo{", ".risk.medio{", ".risk.alto{"):
            self.assertIn(cls, ab.PAGE)

    def test_the_key_letters_do_not_change_with_the_language(self):
        for key in ("<kbd>A</kbd>", "<kbd>R</kbd>", "<kbd>M</kbd>", "<kbd>S</kbd>", "<kbd>C</kbd>"):
            self.assertIn(key, ab.PAGE)
        self.assertIn("if(k === 'a') decide('approved');", ab.PAGE)
        self.assertIn("else if(k === 's') go(idx+1);", ab.PAGE)
        self.assertIn("else if(k === 'c'){ev.preventDefault(); $('#cmt').focus();}", ab.PAGE)

    def test_batch_labels_and_confirm_are_card_content_shown_as_written(self):
        self.assertIn("LBL[p[1]] = l.text; CNT[p[1]] = l.text.toLowerCase();", ab.PAGE)
        self.assertIn("T('confirm_label', {label: esc((LB.approve ? LB.approve.text : T('approve')).toLowerCase())})", ab.PAGE)
        self.assertIn("rich(it.confirm) + '<b>' + T('armed_hint') + '</b></div>'", ab.PAGE)

    def test_the_export_and_the_decisions_carry_no_language(self):
        self.assertNotIn("lang:", ab.PAGE.split("function exportObj(){", 1)[1].split("}\n", 1)[0])
        self.assertNotIn("'/api/lang'", ab.PAGE)

    def test_the_rendered_page_shows_the_table_values_and_no_old_literal(self):
        batch = {"batch_id": "t", "title": "T", "items": [{"id": "A01", "title": "x"}]}
        page = ab.render_page(batch, {"items": {}}, "tok", True).decode("utf-8")
        self.assertIn('"done_banner": "Finished.', page)
        self.assertIn('"done_banner": "Concluído.', page)
        self.assertNotIn("Concluido. Volte", page)
        self.assertNotIn("avancar ao decidir", page)
