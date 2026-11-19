"""Pre-deploy checks on a zone file in YAML form. Returns a list of problems."""
import ipaddress
import re

SUPPORTED = {"A", "AAAA", "CNAME", "NS", "TXT", "SRV", "MX", "CAA"}
LABEL = re.compile(r"^(@|[A-Za-z0-9_]([A-Za-z0-9_-]{0,61}[A-Za-z0-9_])?(\.[A-Za-z0-9_]([A-Za-z0-9_-]{0,61}[A-Za-z0-9_])?)*)$")
TTL_MIN, TTL_MAX = 30, 86400


def lint(doc):
    errors = []
    zone = doc.get("zone", "")
    if not zone.endswith("."):
        errors.append("zone must be a fully qualified name ending with a dot")
    records = doc.get("records") or []
    seen = set()
    by_name = {}
    for i, r in enumerate(records):
        where = f"record {i} ({r.get('name')} {r.get('type')})"
        name, rtype, value = r.get("name"), r.get("type"), str(r.get("value", ""))
        if not name or not LABEL.match(name):
            errors.append(f"{where}: invalid name")
            continue
        if rtype not in SUPPORTED:
            errors.append(f"{where}: unsupported type")
            continue
        ttl = r.get("ttl", doc.get("ttl", 300))
        if not TTL_MIN <= ttl <= TTL_MAX:
            errors.append(f"{where}: ttl {ttl} outside {TTL_MIN}-{TTL_MAX}")
        key = (name, rtype, value)
        if key in seen:
            errors.append(f"{where}: duplicate record")
        seen.add(key)
        by_name.setdefault(name, []).append(rtype)
        errors.extend(_check_value(where, rtype, value))
    for name, types in by_name.items():
        if "CNAME" in types and len(types) > 1:
            errors.append(f"{name}: CNAME cannot share a name with other records")
        if name == "@" and "CNAME" in types:
            errors.append("@: CNAME at the zone apex")
        if types.count("CNAME") > 1:
            errors.append(f"{name}: more than one CNAME")
    apex_ns = [r for r in records if r.get("name") == "@" and r.get("type") == "NS"]
    if len(apex_ns) < 2:
        errors.append("zone needs at least two NS records")
    hosts = {r["name"] for r in records if r.get("type") in ("A", "AAAA") and "name" in r}
    for r in apex_ns:
        target = str(r.get("value", ""))
        if target.endswith("." + zone):
            label = target[: -len(zone) - 1]
            if label not in hosts:
                errors.append(f"NS {target} has no A or AAAA glue in the zone")
    return errors


def _check_value(where, rtype, value):
    if rtype == "A":
        try:
            ipaddress.IPv4Address(value)
        except ValueError:
            return [f"{where}: not an IPv4 address"]
    elif rtype == "AAAA":
        try:
            ipaddress.IPv6Address(value)
        except ValueError:
            return [f"{where}: not an IPv6 address"]
    elif rtype in ("CNAME", "NS"):
        if not value.endswith("."):
            return [f"{where}: target must end with a dot, or it is read relative to the zone"]
    elif rtype in ("MX", "SRV"):
        parts = value.split()
        need = 2 if rtype == "MX" else 4
        if len(parts) != need or not parts[-1].endswith("."):
            return [f"{where}: expected {need} fields ending in a name with a trailing dot"]
    elif rtype == "TXT" and len(value) > 255:
        return [f"{where}: TXT string longer than 255 characters"]
    return []
