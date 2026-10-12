"""Regression tests for the protections described in docs/reference.md (Security model)."""
import http.client
import json
import os
import tempfile
import unittest
from pathlib import Path

from helpers import LiveServer, ab, make_batch


class SecurityBase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.outside = Path(tmp.name)
        (self.outside / "secret.png").write_bytes(b"\x89PNG secret")
        batch = self.outside / "batch"
        batch.mkdir()
        self.d = make_batch(batch)

    def raw(self, server, method, path, host="default", headers=None, body=None):
        """Sends a request byte-for-byte (no client-side normalisation of path or Host)."""
        conn = http.client.HTTPConnection("127.0.0.1", server.srv.server_address[1], timeout=5)
        self.addCleanup(conn.close)
        conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        if host == "default":
            host = "127.0.0.1:%d" % server.srv.server_address[1]
        if host is not None:
            conn.putheader("Host", host)
        for k, v in (headers or {}).items():
            conn.putheader(k, v)
        if body is not None:
            conn.putheader("Content-Length", str(len(body)))
        conn.endheaders(body)
        r = conn.getresponse()
        r.read()
        return r


class TokenTest(SecurityBase):
    def test_missing_or_wrong_token_is_403(self):
        with LiveServer(self.d) as s:
            for path in ("/", "/?t=wrong", "/api/state", "/api/state?t=tok2"):
                with self.subTest(path=path):
                    self.assertEqual(self.raw(s, "GET", path).status, 403)
            self.assertEqual(self.raw(s, "GET", "/?t=tok").status, 200)

    def test_post_with_the_token_only_in_the_query_is_403(self):
        with LiveServer(self.d) as s:
            body = json.dumps({"text": "x"}).encode("utf-8")
            r = self.raw(s, "POST", "/api/note?t=tok", headers={"Content-Type": "application/json"}, body=body)
            self.assertEqual(r.status, 403)
            self.assertEqual(s.store.state["batch_note"], "")
            self.assertEqual(s.post("/api/note", {"text": "x"})[0], 200)  # header still works


class HostHeaderTest(SecurityBase):
    def test_foreign_host_is_403(self):
        with LiveServer(self.d) as s:
            for host in ("evil.com", "127.0.0.1.nip.io", "evil.com:%d" % s.srv.server_address[1], "", None):
                with self.subTest(host=host):
                    self.assertEqual(self.raw(s, "GET", "/?t=tok", host=host).status, 403)

    def test_loopback_hosts_are_accepted(self):
        with LiveServer(self.d) as s:
            port = s.srv.server_address[1]
            for host in ("127.0.0.1:%d" % port, "localhost:%d" % port, "localhost"):
                with self.subTest(host=host):
                    self.assertEqual(self.raw(s, "GET", "/?t=tok", host=host).status, 200)


class FilesTest(SecurityBase):
    def test_path_traversal_is_404(self):
        with LiveServer(self.d) as s:
            for path in ("/files/..%2Fsecret.png", "/files/../secret.png", "/files/%2e%2e/secret.png",
                         "/files/%2e%2e%2fsecret.png", "/files/sub/..%2F..%2Fsecret.png"):
                with self.subTest(path=path):
                    self.assertEqual(self.raw(s, "GET", path + "?t=tok").status, 404)

    def test_symlink_pointing_outside_the_batch_folder_is_404(self):
        os.symlink(self.outside / "secret.png", self.d / "link.png")
        with LiveServer(self.d) as s:
            self.assertEqual(self.raw(s, "GET", "/files/link.png?t=tok").status, 404)

    def test_svg_inside_the_batch_folder_is_served_sandboxed(self):
        (self.d / "pic.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', encoding="utf-8")
        with LiveServer(self.d) as s:
            r = self.raw(s, "GET", "/files/pic.svg?t=tok")
            self.assertEqual(r.status, 200)
            self.assertEqual(r.getheader("Content-Security-Policy"), "sandbox")
            self.assertEqual(r.getheader("X-Content-Type-Options"), "nosniff")

    def test_disallowed_extension_is_404(self):
        (self.d / "notes.txt").write_text("x", encoding="utf-8")
        with LiveServer(self.d) as s:
            self.assertEqual(self.raw(s, "GET", "/files/notes.txt?t=tok").status, 404)
            self.assertEqual(self.raw(s, "GET", "/files/batch.json?t=tok").status, 404)


class HeadersTest(SecurityBase):
    def test_page_csp_is_strict_and_forbids_framing(self):
        with LiveServer(self.d) as s:
            csp = self.raw(s, "GET", "/?t=tok").getheader("Content-Security-Policy")
            directives = [d.strip() for d in csp.split(";")]
            self.assertIn("default-src 'none'", directives)
            self.assertIn("frame-ancestors 'none'", directives)
            self.assertIn("base-uri 'none'", directives)
            self.assertIn("form-action 'none'", directives)

    def test_unsupported_method_is_501(self):
        with LiveServer(self.d) as s:
            self.assertEqual(self.raw(s, "OPTIONS", "/?t=tok").status, 501)

    def test_server_header_does_not_reveal_the_python_version(self):
        with LiveServer(self.d) as s:
            for method, path in (("GET", "/?t=tok"), ("GET", "/"), ("OPTIONS", "/")):
                with self.subTest(method=method, path=path):
                    server = self.raw(s, method, path).getheader("Server")
                    self.assertEqual(server, "ar-board")


class RenderEscapingTest(unittest.TestCase):
    def page(self, title="T", item_title="x"):
        batch = {"batch_id": "t", "title": title, "items": [{"id": "A01", "title": item_title}]}
        return ab.render_page(batch, {"items": {}}, "tok", True).decode("utf-8")

    def test_boot_data_cannot_close_the_script_tag(self):
        page = self.page(item_title="</script><script>alert(1)</script>")
        self.assertEqual(page.count("</script>"), 1)  # only the page's own closing tag
        self.assertIn("<\\/script>", page)

    def test_unicode_line_separators_are_escaped_in_boot(self):
        page = self.page(item_title="a b c")
        self.assertNotIn(" ", page)
        self.assertNotIn(" ", page)
        self.assertIn("a\\u2028b\\u2029c", page)

    def test_title_is_html_escaped(self):
        page = self.page(title="<img src=x onerror=alert(1)> & co")
        self.assertIn("<title>&lt;img src=x onerror=alert(1)&gt; &amp; co</title>", page)


if __name__ == "__main__":
    unittest.main()
