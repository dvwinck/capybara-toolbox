import http.client
import json
import tempfile
import unittest

from helpers import LiveServer, make_batch


class HttpBase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = make_batch(tmp.name)

    def saved_items(self):
        return json.loads((self.d / "decisions.json").read_text(encoding="utf-8"))["items"]


class AtomicityTest(HttpBase):
    def test_rejected_requests_leave_no_trace(self):
        with LiveServer(self.d) as s:
            self.assertEqual(s.post("/api/item", {"id": "A01", "decision": "approved", "comment": 5})[0], 400)
            self.assertEqual(s.post("/api/item", {"id": "A02", "decision": "x"})[0], 400)
            s.post("/api/note", {"text": "n"})  # forca um save do estado
            self.assertEqual(self.saved_items(), {})

    def test_valid_request_still_works(self):
        with LiveServer(self.d) as s:
            self.assertEqual(s.post("/api/item", {"id": "A01", "decision": "approved", "comment": "ok"})[0], 200)
            self.assertEqual(self.saved_items()["A01"]["decision"], "approved")
            self.assertEqual(s.post("/api/item", {"id": "A01", "decision": None, "comment": ""})[0], 200)
            self.assertEqual(self.saved_items(), {})


class MalformedInputTest(HttpBase):
    def test_non_string_decision_is_400(self):
        with LiveServer(self.d) as s:
            for bad in ([], {}, 1, True):
                with self.subTest(decision=bad):
                    self.assertEqual(s.post("/api/item", {"id": "A01", "decision": bad})[0], 400)

    def test_non_ascii_token_is_403(self):
        with LiveServer(self.d) as s:
            self.assertEqual(s.get("/?t=%C3%A9")[0], 403)

    def test_negative_content_length_is_400(self):
        with LiveServer(self.d) as s:
            conn = http.client.HTTPConnection("127.0.0.1", s.srv.server_address[1], timeout=3)
            conn.putrequest("POST", "/api/note")
            conn.putheader("X-AR-Token", s.token)
            conn.putheader("Content-Length", "-1")
            conn.endheaders()
            self.assertEqual(conn.getresponse().status, 400)
            conn.close()
