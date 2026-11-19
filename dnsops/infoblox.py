"""Small Infoblox WAPI client for A records, plus a reconcile step.

Written against the documented WAPI paths (record:a). Tested only against a
local stub server, never against a real Grid.
"""
import base64
import json
import urllib.parse
import urllib.request


class Wapi:
    def __init__(self, base_url, user, password, version="v2.12", view="default", opener=None):
        self.base = f"{base_url.rstrip('/')}/wapi/{version}"
        self.view = view
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        self.headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}
        self.open = opener or urllib.request.urlopen

    def _call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"{self.base}/{path}", data=data, method=method, headers=self.headers)
        with self.open(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    def get_a(self, name):
        q = urllib.parse.urlencode({"name": name, "view": self.view, "_return_fields": "name,ipv4addr,ttl"})
        return self._call("GET", f"record:a?{q}")

    def ensure_a(self, name, ip, ttl=None, dry_run=False):
        found = self.get_a(name)
        if not found:
            action = "create"
        elif found[0]["ipv4addr"] != ip or (ttl is not None and found[0].get("ttl") != ttl):
            action = "update"
        else:
            return "unchanged"
        if dry_run:
            return f"would {action}"
        body = {"name": name, "ipv4addr": ip, "view": self.view}
        if ttl is not None:
            body.update(ttl=ttl, use_ttl=True)
        if action == "create":
            self._call("POST", "record:a", body)
        else:
            self._call("PUT", found[0]["_ref"], body)
        return action


def sync(wapi, doc, dry_run=True):
    """Make the Grid match the A records in the zone file. Returns {fqdn: action}."""
    zone = doc["zone"].rstrip(".")
    result = {}
    for r in doc["records"]:
        if r["type"] != "A":
            continue
        fqdn = zone if r["name"] == "@" else f"{r['name']}.{zone}"
        result[fqdn] = wapi.ensure_a(fqdn, r["value"], r.get("ttl"), dry_run=dry_run)
    return result
