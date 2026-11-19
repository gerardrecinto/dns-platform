import yaml

from dnsops import drift

DOC = yaml.safe_load(open("zones/lab.example.yml"))


def test_expected_expands_names_and_quotes_txt():
    want = drift.expected(DOC)
    assert want[("api.lab.example.", "A")] == {"10.20.0.10"}
    assert want[("lab.example.", "TXT")] == {'"v=spf1 -all"'}
    assert want[("www.lab.example.", "CNAME")] == {"api.lab.example."}


def test_diff_reports_missing_extra_and_changed():
    want = {("a.", "A"): {"1.1.1.1"}, ("b.", "A"): {"2.2.2.2"}}
    got = {("a.", "A"): {"1.1.1.2"}, ("c.", "A"): {"3.3.3.3"}}
    problems = drift.diff(want, got)
    assert len(problems) == 3
    assert drift.diff(want, want) == []
