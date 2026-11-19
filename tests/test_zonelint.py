import copy

import yaml

from dnsops import zonelint

GOOD = yaml.safe_load(open("zones/lab.example.yml"))


def with_record(**rec):
    doc = copy.deepcopy(GOOD)
    doc["records"].append(rec)
    return doc


def test_lab_zone_is_clean():
    assert zonelint.lint(GOOD) == []


def test_apex_cname_rejected():
    errs = zonelint.lint(with_record(name="@", type="CNAME", value="x.lab.example."))
    assert any("apex" in e for e in errs)


def test_cname_next_to_other_data_rejected():
    errs = zonelint.lint(with_record(name="api", type="CNAME", value="x.lab.example."))
    assert any("cannot share" in e for e in errs)


def test_relative_cname_target_rejected():
    errs = zonelint.lint(with_record(name="alias", type="CNAME", value="api"))
    assert any("trailing dot" in e or "end with a dot" in e for e in errs)


def test_bad_ip_and_ttl_rejected():
    errs = zonelint.lint(with_record(name="bad", type="A", value="10.0.0.999", ttl=5))
    assert any("IPv4" in e for e in errs) and any("ttl" in e for e in errs)


def test_duplicate_rejected():
    errs = zonelint.lint(with_record(name="api", type="A", value="10.20.0.10"))
    assert any("duplicate" in e for e in errs)


def test_missing_glue_rejected():
    doc = copy.deepcopy(GOOD)
    doc["records"] = [r for r in doc["records"] if not (r["name"] == "ns2" and r["type"] == "A")]
    assert any("glue" in e for e in zonelint.lint(doc))


def test_single_ns_rejected():
    doc = copy.deepcopy(GOOD)
    doc["records"] = [r for r in doc["records"] if not (r["type"] == "NS" and r["value"] == "ns2.lab.example.")]
    assert any("two NS" in e for e in zonelint.lint(doc))


def test_srv_needs_four_fields():
    errs = zonelint.lint(with_record(name="_x._tcp", type="SRV", value="10 5060 host.lab.example."))
    assert any("SRV" in e or "fields" in e for e in errs)
