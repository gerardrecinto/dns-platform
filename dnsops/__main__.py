import argparse
import getpass
import os
import sys

import yaml

from . import drift, heal, infoblox, zonelint


def load(path):
    with open(path) as f:
        return yaml.safe_load(f)


def main(argv=None):
    p = argparse.ArgumentParser(prog="dnsops")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("lint", help="check a zone file before it is deployed")
    s.add_argument("zonefile")

    s = sub.add_parser("drift", help="compare primary and secondary with the zone file")
    s.add_argument("zonefile")
    s.add_argument("--primary", required=True)
    s.add_argument("--secondary", required=True)
    s.add_argument("--key-name", default="xfer-key")
    s.add_argument("--secret-env", default="TSIG_SECRET", help="environment variable holding the TSIG secret")

    s = sub.add_parser("heal", help="restart a nameserver that stopped answering")
    s.add_argument("--server", default="127.0.0.1")
    s.add_argument("--zone", required=True)
    s.add_argument("--restart", required=True)

    s = sub.add_parser("infoblox-sync", help="reconcile A records into an Infoblox Grid")
    s.add_argument("zonefile")
    s.add_argument("--grid", required=True, help="https://grid-master.example.com")
    s.add_argument("--user", required=True)
    s.add_argument("--view", default="default")
    s.add_argument("--apply", action="store_true", help="write changes; default is a dry run")

    a = p.parse_args(argv)
    if a.cmd == "lint":
        errors = zonelint.lint(load(a.zonefile))
        for e in errors:
            print(f"ERROR {e}")
        print("lint ok" if not errors else f"{len(errors)} problem(s)")
        return 1 if errors else 0
    if a.cmd == "drift":
        doc = load(a.zonefile)
        zone = doc["zone"]
        ps, ss = drift.soa_serial(a.primary, zone), drift.soa_serial(a.secondary, zone)
        problems = []
        if ps != ss:
            problems.append(f"serial mismatch: primary {ps} secondary {ss}")
        problems += [f"primary {x}" for x in drift.diff(drift.expected(doc), drift.axfr(a.primary, zone, a.key_name, os.environ[a.secret_env]))]
        problems += [f"secondary {x}" for x in drift.check_secondary(doc, a.secondary)]
        for x in problems:
            print(f"DRIFT {x}")
        print(f"no drift, serial {ps}" if not problems else f"{len(problems)} difference(s)")
        return 1 if problems else 0
    if a.cmd == "heal":
        check = lambda: _answers(a.server, a.zone)  # noqa: E731
        state = heal.heal(check, heal.shell_restart(a.restart))
        print(state)
        return 0 if state != "failed" else 1
    if a.cmd == "infoblox-sync":
        pw = os.environ.get("INFOBLOX_PASSWORD") or getpass.getpass("Infoblox password: ")
        w = infoblox.Wapi(a.grid, a.user, pw, view=a.view)
        for fqdn, action in infoblox.sync(w, load(a.zonefile), dry_run=not a.apply).items():
            print(f"{action:12} {fqdn}")
        return 0


def _answers(server, zone):
    try:
        return drift.soa_serial(server, zone, timeout=1) is not None
    except Exception:
        return False


if __name__ == "__main__":
    sys.exit(main())
