import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import pytest
import yaml

from dnsops.infoblox import Wapi, sync

DB = {}
CALLS = []


class Stub(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        CALLS.append(("GET", u.path, self.headers.get("Authorization")))
        name = parse_qs(u.query)["name"][0]
        self._send([dict(v, _ref=f"record:a/{k}:{name}", name=name) for k, v in DB.items() if k == name])

    def _body(self):
        return json.loads(self.rfile.read(int(self.headers["Content-Length"])))

    def do_POST(self):
        b = self._body()
        CALLS.append(("POST", b["name"], None))
        DB[b["name"]] = {"ipv4addr": b["ipv4addr"], "ttl": b.get("ttl")}
        self._send("ok")

    def do_PUT(self):
        b = self._body()
        CALLS.append(("PUT", b["name"], None))
        DB[b["name"]] = {"ipv4addr": b["ipv4addr"], "ttl": b.get("ttl")}
        self._send("ok")


@pytest.fixture()
def wapi():
    DB.clear()
    CALLS.clear()
    srv = HTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield Wapi(f"http://127.0.0.1:{srv.server_port}", "admin", "pw")
    srv.shutdown()


DOC = yaml.safe_load(open("zones/lab.example.yml"))


def test_dry_run_changes_nothing(wapi):
    result = sync(wapi, DOC, dry_run=True)
    assert set(result.values()) == {"would create"}
    assert DB == {} and not any(c[0] == "POST" for c in CALLS)


def test_apply_creates_then_is_idempotent(wapi):
    first = sync(wapi, DOC, dry_run=False)
    assert set(first.values()) == {"create"}
    assert DB["api.lab.example"]["ipv4addr"] == "10.20.0.10"
    assert set(sync(wapi, DOC, dry_run=False).values()) == {"unchanged"}


def test_changed_address_is_updated(wapi):
    sync(wapi, DOC, dry_run=False)
    DB["api.lab.example"]["ipv4addr"] = "10.99.0.1"
    result = sync(wapi, DOC, dry_run=False)
    assert result["api.lab.example"] == "update"
    assert DB["api.lab.example"]["ipv4addr"] == "10.20.0.10"


def test_basic_auth_header_sent(wapi):
    wapi.get_a("x.lab.example")
    assert CALLS[0][2].startswith("Basic ")
