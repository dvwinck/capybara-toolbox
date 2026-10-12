import unittest

from helpers import ab


class PageGuardsTest(unittest.TestCase):
    """Guardas de regressao sobre o JS embutido. O comportamento real e verificado
    manualmente no navegador (ver Task 4, Step 5 do plano)."""

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
