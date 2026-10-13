import time
import unittest

from helpers import LEAK_EMAIL, LEAK_LINK, LEAK_PATH, LEAK_TERM, pc


def cats(text, denylist=()):
    return [(m.category, m.value) for m in pc.find_matches(text, denylist)]


class SessionLinkTest(unittest.TestCase):
    def test_code_session_link_is_found(self):
        self.assertEqual(cats(f"see {LEAK_LINK} for context"), [("session-link", LEAK_LINK)])

    def test_chat_and_share_links_are_found(self):
        for url in ("https://claude." + "ai/chat/0f1e2d3c-aaaa", "https://claude." + "ai/share/abc123"):
            with self.subTest(url=url):
                self.assertEqual(cats(f"({url})"), [("session-link", url)])

    def test_the_site_itself_is_not_a_leak(self):
        self.assertEqual(cats("docs at https://claude.com/claude-code and https://claude.ai/"), [])


class HomePathTest(unittest.TestCase):
    def test_unix_mac_and_windows_home_paths_are_found(self):
        for path in (LEAK_PATH + "/projects", "/home/" + "fixtureuser/work", "C:\\Users\\" + "fixtureuser\\Desktop"):
            with self.subTest(path=path):
                self.assertEqual([c for c, _ in cats(f"cd {path}")], ["home-path"])

    def test_windows_forms_with_doubled_separators_and_any_case_are_found(self):
        for path in ("C:\\\\Users\\\\" + "fixtureuser", "c:\\users\\" + "fixtureuser", "C:/Users/" + "fixtureuser",
                     "D:\\USERS\\" + "fixtureuser"):
            with self.subTest(path=path):
                self.assertEqual([c for c, _ in cats(f"x {path}\\Desktop")], ["home-path"])

    def test_windows_shared_profiles_are_ignored(self):
        self.assertEqual(cats("C:\\Users\\Public\\Documents and C:\\Users\\Default\\x"), [])

    def test_the_case_insensitive_windows_form_does_not_leak_into_the_unix_one(self):
        self.assertEqual(cats("GET /users/profile and /users/alice and /USERS/bob"), [])

    def test_placeholders_and_ci_users_are_ignored(self):
        for text in ("/Users/<name>/x", "/home/runner/work", "/Users/Shared/data", "~/x and $HOME/y", "/Users/you/x"):
            with self.subTest(text=text):
                self.assertEqual(cats(text), [])


class EmailTest(unittest.TestCase):
    def test_email_is_found(self):
        self.assertEqual(cats(f"Reach me at {LEAK_EMAIL}."), [("email", LEAK_EMAIL)])

    def test_noreply_and_example_addresses_are_ignored(self):
        for text in ("Co-Authored-By: Claude <noreply@anthropic.com>", "a@example.com", "12345+bot@users.noreply.github.com"):
            with self.subTest(text=text):
                self.assertEqual(cats(text), [])

    def test_version_pins_are_not_emails(self):
        self.assertEqual(cats("uses: actions/checkout@v7 and pkg@1.2.3"), [])


class EmailRobustnessTest(unittest.TestCase):
    def test_a_huge_line_without_an_at_sign_is_scanned_in_linear_time(self):
        started = time.monotonic()
        self.assertEqual(cats("a" * 300000), [])
        self.assertEqual(cats("a." * 150000), [])
        self.assertLess(time.monotonic() - started, 2.0)

    def test_many_at_signs_are_scanned_in_linear_time(self):
        started = time.monotonic()
        self.assertEqual(cats("a@" * 100000), [])
        self.assertLess(time.monotonic() - started, 2.0)

    def test_a_long_prefix_does_not_hide_an_address(self):
        found = cats("x" * 200 + LEAK_EMAIL)
        self.assertEqual([c for c, _ in found], ["email"])
        self.assertTrue(found[0][1].endswith(LEAK_EMAIL.split("@")[1]))

    def test_trailing_punctuation_is_not_part_of_the_address(self):
        self.assertEqual(cats(f"({LEAK_EMAIL}), or {LEAK_EMAIL}.")[0][1], LEAK_EMAIL)
        self.assertEqual(cats(f"mail {LEAK_EMAIL}.")[0][1], LEAK_EMAIL)


class DenylistTest(unittest.TestCase):
    def test_denylist_is_case_insensitive(self):
        self.assertEqual(cats(f"the {LEAK_TERM.upper()} plan", [LEAK_TERM]), [("denylist", LEAK_TERM.upper())])

    def test_overlapping_matches_keep_only_the_first(self):
        text = LEAK_LINK
        self.assertEqual(cats(text, ["session_FIXTURE"]), [("session-link", LEAK_LINK)])

    def test_matches_are_sorted_by_position(self):
        text = f"{LEAK_EMAIL} then {LEAK_PATH}/x"
        self.assertEqual([c for c, _ in cats(text)], ["email", "home-path"])


class MaskTest(unittest.TestCase):
    def test_masked_values_do_not_contain_the_original(self):
        samples = {
            "session-link": LEAK_LINK,
            "home-path": LEAK_PATH + "/projects",
            "email": LEAK_EMAIL,
            "denylist": LEAK_TERM,
        }
        for category, value in samples.items():
            with self.subTest(category=category):
                masked = pc.mask(category, value)
                self.assertNotEqual(masked, value)
                self.assertIn("***", masked)
                self.assertNotIn("FIXTURE123", masked)
                self.assertNotIn("fixtureuser", masked)
                self.assertNotIn("fixture.person", masked)

    def test_email_keeps_the_domain_for_triage(self):
        self.assertEqual(pc.mask("email", "jane@" + "acme.dev"), "j***@acme.dev")

    def test_home_path_keeps_only_the_directory_prefix(self):
        self.assertEqual(pc.mask("home-path", "/Users/" + "jane"), "/Users/***")
        self.assertEqual(pc.mask("home-path", "C:\\Users\\" + "jane"), "C:\\Users\\***")


class FingerprintTest(unittest.TestCase):
    def test_fingerprint_is_stable_and_case_insensitive_on_the_value(self):
        a = pc.fingerprint("email", "tree", "README.md", "Jane@" + "Acme.dev")
        self.assertEqual(a, pc.fingerprint("email", "tree", "README.md", "jane@" + "acme.dev"))
        self.assertEqual(len(a), 16)

    def test_fingerprint_depends_on_category_place_and_origin(self):
        base = pc.fingerprint("email", "tree", "README.md", "jane@" + "acme.dev")
        self.assertNotEqual(base, pc.fingerprint("home-path", "tree", "README.md", "jane@" + "acme.dev"))
        self.assertNotEqual(base, pc.fingerprint("email", "patch", "README.md", "jane@" + "acme.dev"))
        self.assertNotEqual(base, pc.fingerprint("email", "tree", "OTHER.md", "jane@" + "acme.dev"))


class FindingsInTextTest(unittest.TestCase):
    def test_every_leak_on_a_line_is_masked_in_every_snippet(self):
        text = f"from {LEAK_EMAIL} at {LEAK_PATH}/x"
        found = list(pc.findings_in_text(text, [], "tree", "a.txt", lambda n: f"a.txt:{n}"))
        self.assertEqual([f["category"] for f in found], ["email", "home-path"])
        for f in found:
            self.assertNotIn("fixture.person", f["snippet"])
            self.assertNotIn("fixtureuser", f["snippet"])
            self.assertEqual(f["location"], "a.txt:1")

    def test_line_numbers_follow_the_text(self):
        found = list(pc.findings_in_text(f"ok\nok\n{LEAK_EMAIL}\n", [], "tree", "a.txt", lambda n: f"a.txt:{n}"))
        self.assertEqual(found[0]["location"], "a.txt:3")

    def test_control_characters_cannot_reach_the_terminal(self):
        text = f"\x1b[2J\x1b]0;owned\x07 mail {LEAK_EMAIL}\r\x85"
        found = list(pc.findings_in_text(text, [], "tree", "a.txt", lambda n: "bad\x1b[0mname.txt:%d" % n))
        for f in found:
            for field in ("snippet", "location"):
                self.assertFalse(any(ord(ch) < 32 and ch != "\t" or 127 <= ord(ch) < 160 for ch in f[field]), f[field])

    def test_long_lines_keep_a_window_around_the_match(self):
        line = "x" * 500 + " " + LEAK_EMAIL + " " + "y" * 500
        found = list(pc.findings_in_text(line, [], "tree", "min.js", lambda n: "min.js:1"))
        self.assertLess(len(found[0]["snippet"]), 140)
        self.assertIn("***@", found[0]["snippet"])


if __name__ == "__main__":
    unittest.main()
