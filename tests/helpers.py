import importlib.util
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "ar_board.py"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ab = load_module(SCRIPT, "ar_board")


def make_batch(tmp, **extra):
    batch = {
        "batch_id": "t",
        "title": "T",
        "items": [{"id": "A01", "title": "x"}, {"id": "A02", "title": "y"}],
    }
    batch.update(extra)
    d = Path(tmp)
    (d / "batch.json").write_text(json.dumps(batch), encoding="utf-8")
    return d


class LiveServer:
    """Sobe o servidor real em uma thread, na porta 0 (livre)."""

    def __init__(self, d):
        self.store = ab.Store(d)
        self.token = "tok"
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), ab.make_handler(self.store, self.token))
        self.base = "http://127.0.0.1:%d" % self.srv.server_address[1]
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.srv.shutdown()
        self.srv.server_close()

    def post(self, path, body, token=None):
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(body).encode("utf-8"),
            headers={"X-AR-Token": self.token if token is None else token, "Content-Type": "application/json"},
        )
        return self._open(req)

    def get(self, path):
        return self._open(urllib.request.Request(self.base + path))

    def _open(self, req):
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.read().decode("utf-8")


def load_sync():
    return load_module(ROOT / "tools" / "sync.py", "sync_tool")
