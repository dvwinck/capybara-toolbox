import unittest

from helpers import load_todo_sweep

ts = load_todo_sweep()


def found(text):
    return [(line, marker, body) for line, marker, body, _ctx in ts.find_todos(text)]


class MarkerTest(unittest.TestCase):
    def test_a_comment_that_starts_with_the_marker(self):
        text = "# TODO: shell\n// FIXME handle it\n-- TODO sql\n/* TODO block */\n * TODO inside a block\n; TODO ini\n#TODO tight\n"
        self.assertEqual(found(text), [
            (1, "TODO", "shell"), (2, "FIXME", "handle it"), (3, "TODO", "sql"), (4, "TODO", "block"),
            (5, "TODO", "inside a block"), (6, "TODO", "ini"), (7, "TODO", "tight")])

    def test_a_trailing_comment_after_code(self):
        text = "x = 1  # TODO: later\nfoo();  // FIXME(alice): broken\n"
        self.assertEqual(found(text), [(1, "TODO", "later"), (2, "FIXME", "(alice): broken")])

    def test_near_misses_are_not_markers(self):
        for line in ["# TODOS later", "# todo: lower", "# Todo: mixed", "# XXX", "# HACK", "We should TODO this",
                     'x = "TODO"', "#define TODO_FLAG 1", "# FIXMEs", "TODO: not in a comment", "x = 1 # NOTODO here",
                     "http://example.com/TODO"]:
            with self.subTest(line=line):
                self.assertEqual(found(line + "\n"), [])

    def test_the_text_loses_its_colon_and_a_closing_comment_and_is_capped(self):
        self.assertEqual(found("// TODO:   spaced  */\n"), [(1, "TODO", "spaced")])
        self.assertEqual(found("# TODO\n"), [(1, "TODO", "")])
        self.assertEqual(len(found("# TODO " + "x" * 500 + "\n")[0][2]), 200)

    def test_context_is_two_lines_each_way_trimmed_and_numbered(self):
        text = "a\nb\nc\n# TODO: here\nd\ne\nf\n"
        (_line, _marker, _body, ctx), = ts.find_todos(text)
        self.assertEqual(ctx, [(2, "b"), (3, "c"), (4, "# TODO: here"), (5, "d"), (6, "e")])
        (_l, _m, _b, edge), = ts.find_todos("# TODO: first\nb\n")
        self.assertEqual([n for n, _t in edge], [1, 2])
        (_l, _m, _b, long), = ts.find_todos("# TODO " + "y" * 400 + "\n")
        self.assertEqual(len(long[0][1]), 160)

    def test_windows_line_endings_and_an_empty_text(self):
        self.assertEqual(found("# TODO: crlf\r\nx\r\n"), [(1, "TODO", "crlf")])
        self.assertEqual(found(""), [])


class IdentityTest(unittest.TestCase):
    def test_the_id_depends_on_file_text_and_occurrence_never_on_the_line(self):
        a = ts.todo_id("src/a.py", "fix it", 0)
        self.assertEqual(a, ts.todo_id("src/a.py", "fix it", 0))
        self.assertNotEqual(a, ts.todo_id("src/b.py", "fix it", 0))
        self.assertNotEqual(a, ts.todo_id("src/a.py", "fix it", 1))
        self.assertNotEqual(a, ts.todo_id("src/a.py", "other", 0))
        self.assertEqual(len(a), 16)


if __name__ == "__main__":
    unittest.main()
