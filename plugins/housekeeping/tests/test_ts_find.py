import time
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

    def test_an_indented_trailing_comment_after_code(self):
        text = "def f(x):\n    y = 1  # TODO: later\n\treturn x  // FIXME(alice): broken\n        z = 2  ## TODO deeper\n"
        self.assertEqual(found(text), [(2, "TODO", "later"), (3, "FIXME", "(alice): broken"), (4, "TODO", "deeper")])

    def test_near_misses_are_not_markers(self):
        for line in ["# TODOS later", "# todo: lower", "# Todo: mixed", "# XXX", "# HACK", "We should TODO this",
                     'x = "TODO"', "#define TODO_FLAG 1", "# FIXMEs", "TODO: not in a comment", "x = 1 # NOTODO here",
                     "http://example.com/TODO", '    url = "http://x/TODO"', "\tcall()  # TODOS later"]:
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


class HostileLineTest(unittest.TestCase):
    """A tracked file is data and may hold one huge line: finding must stay close to linear."""

    N = 200000

    def timed(self, line):
        start = time.monotonic()
        result = ts.find_todos(line + "\n")
        return result, time.monotonic() - start

    def test_long_runs_of_whitespace_and_closers_finish_in_bounded_time(self):
        n = self.N
        for name, line in [("spaces inside the text", "# TODO: a" + " " * n + "b"),
                           ("spaces after the colon", "# TODO:" + " " * n + "b"),
                           ("closers", "/* TODO: a" + " */" * n),
                           ("closers and text", "/* TODO: a" + " */" * n + " b"),
                           ("spaces before a trailing marker", "x" + " " * n + "# TODO: b"),
                           ("trailing markers", "x" + " # TODO: a" * (n // 10)),
                           ("hashes", "#" * n), ("hashes then marker", "#" * n + " TODO"),
                           ("slashes", "/" * n), ("stars", "*" * n), ("dashes", "-" * n), ("semicolons", ";" * n + " "),
                           ("code then hashes", "x " + "#" * n + "a"), ("code then slashes", "x " + "/" * n + "a"),
                           ("code then spaced hashes", "x" + " #" * n),
                           ("indented code then spaced hashes", " " * 10 + "x" + " #" * n),
                           ("indented spaces before a trailing marker", " " * (n // 2) + "x" + " " * (n // 2) + "# TODO: b"),
                           ("leading spaces", " " * n + "x"), ("leading spaces then marker", " " * n + "# TODO: x")]:
            with self.subTest(name):
                _result, seconds = self.timed(line)
                self.assertLess(seconds, 2.0, f"{name}: {seconds:.2f}s")

    def test_ordinary_comments_still_yield_their_text(self):
        self.assertEqual(found("/* TODO: x */\n"), [(1, "TODO", "x")])
        self.assertEqual(found("# TODO:" + " " * self.N + "b\n"), [(1, "TODO", "b")])
        self.assertEqual(found("/* TODO: x" + " " * 5000 + "*/\n"), [(1, "TODO", "x")])


class LineNumberTest(unittest.TestCase):
    """Lines are counted the way git counts them: by the newline only."""

    def test_characters_that_splitlines_splits_on_do_not_move_the_line_number(self):
        for name, sep in [("form feed", "\x0c"), ("file separator", "\x1c"), ("next line", "\x85"),
                          ("line separator", "\u2028"), ("paragraph separator", "\u2029"), ("lone carriage return", "\r"),
                          ("vertical tab", "\x0b")]:
            with self.subTest(name):
                self.assertEqual(found(f"a{sep}b\n# TODO: x\n"), [(2, "TODO", "x")])

    def test_crlf_files_count_lines_and_strip_the_return(self):
        (_line, _marker, _body, ctx), = ts.find_todos("a\r\nb\r\n# TODO: x\r\nd\r\n")
        self.assertEqual(ctx, [(1, "a"), (2, "b"), (3, "# TODO: x"), (4, "d")])
        self.assertEqual(found("a\r\n# TODO: x\r\n"), [(2, "TODO", "x")])

    def test_no_bogus_final_line_and_a_missing_final_newline_still_counts(self):
        (_l, _m, _b, ctx), = ts.find_todos("# TODO: x\n")
        self.assertEqual(ctx, [(1, "# TODO: x")])
        self.assertEqual(found("a\n# TODO: last"), [(2, "TODO", "last")])
        self.assertEqual(found("\n\n# TODO: x\n"), [(3, "TODO", "x")])


if __name__ == "__main__":
    unittest.main()
