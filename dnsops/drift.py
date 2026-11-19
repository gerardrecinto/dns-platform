"""Compare what the servers answer with what the zone file says should be there."""
import dns.message
import dns.query
import dns.rdatatype
import dns.tsigkeyring
import dns.zone

SKIP = {"SOA"}


def expected(doc):
    """Map (name, type) to the set of rdata strings the zone file promises."""
    zone = doc["zone"]
    out = {}
    for r in doc["records"]:
        name = zone if r["name"] == "@" else f"{r['name']}.{zone}"
        value = str(r["value"])
        if r["type"] == "TXT":
            value = f'"{value}"'
        out.setdefault((name.lower(), r["type"]), set()).add(value)
    return out


def soa_serial(server, zone, port=53, timeout=3):
    q = dns.message.make_query(zone, "SOA")
    resp = dns.query.udp(q, server, port=port, timeout=timeout)
    for rrset in resp.answer:
        if rrset.rdtype == dns.rdatatype.SOA:
            return rrset[0].serial
    return None


def axfr(server, zone, key_name, secret, port=53):
    keyring = dns.tsigkeyring.from_text({key_name: secret})
    z = dns.zone.from_xfr(dns.query.xfr(server, zone, port=port, keyring=keyring, keyname=key_name, keyalgorithm="hmac-sha256", relativize=False), relativize=False)
    out = {}
    for name, node in z.nodes.items():
        for rdataset in node.rdatasets:
            rtype = dns.rdatatype.to_text(rdataset.rdtype)
            if rtype in SKIP:
                continue
            out.setdefault((name.to_text().lower(), rtype), set()).update(r.to_text() for r in rdataset)
    return out


def query_set(server, name, rtype, port=53, timeout=3):
    q = dns.message.make_query(name, rtype)
    resp = dns.query.udp(q, server, port=port, timeout=timeout)
    got = set()
    for rrset in resp.answer:
        if dns.rdatatype.to_text(rrset.rdtype) == rtype:
            got.update(r.to_text() for r in rrset)
    return got


def diff(want, got):
    """Return human readable differences between two (name, type) maps."""
    problems = []
    for key in sorted(want.keys() | got.keys()):
        w, g = want.get(key, set()), got.get(key, set())
        if w != g:
            problems.append(f"{key[0]} {key[1]}: expected {sorted(w)} got {sorted(g)}")
    return problems


def check_secondary(doc, server, port=53):
    """Ask a secondary for every expected record set; no zone transfer needed."""
    got = {k: query_set(server, k[0], k[1], port=port) for k in expected(doc)}
    return diff(expected(doc), got)
