# dns-platform-lab

A small DNS and Kubernetes platform you can run on a laptop: BIND9 primary and secondary servers built by Ansible, a deploy pipeline that blocks bad zones and rolls back, monitoring, and a Kubernetes cluster that forwards a zone to BIND and keeps tenants apart.

It is for platform and SRE engineers who want to see how DNS changes can be tested, shipped and reversed. Everything runs in Docker on one host. Nothing here has run against a real cloud account, an Infoblox Grid or bare metal.

## Run it

Needs Docker, kind, kubectl and Python 3.10 or later. About 5 minutes the first time.

```bash
git clone https://github.com/gerardrecinto/dns-platform-lab.git && cd dns-platform-lab
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q          # 19 unit tests
bash scripts/e2e.sh                     # real BIND9: ends with ALL PASS
bash scripts/k8s-e2e.sh                 # Calico kind cluster: ends with ALL PASS
```

If `e2e.sh` fails on the first Docker build, check that Docker is running (`docker info`). Logs from each BIND container are in `docker logs dns-lab-primary`.

For monitoring: `docker compose --profile observability up -d`, then Prometheus is on :9090, Grafana on :3000 and Loki on :3100.

## What `scripts/e2e.sh` proves

1. Ansible converges both servers; a second run changes nothing.
2. The secondary receives the zone over a TSIG-signed transfer; `dnsops drift` finds no difference from the zone file.
3. A new record reaches the secondary.
4. A zone with a CNAME at the apex is rejected by lint, and the primary's serial does not move.
5. A deploy whose verification fails is rolled back to the last good zone at a higher serial (failure injected with `INJECT_VERIFY_FAILURE=1`).
6. After the secondary's `named` is killed, `dnsops heal` restarts it and it serves the zone again.

`scripts/k8s-e2e.sh` adds: a pod resolves `api.lab.example` through CoreDNS to BIND; tenant B cannot reach tenant A; a 2 CPU pod is rejected in a 500m tenant; one tenant's group cannot create pods in the other namespace.

## One zone file, many targets

`zones/lab.example.yml` is the only place records are written.

| Target | How | Status |
|---|---|---|
| BIND9 | `ansible/roles/bind9` renders and validates the zone | run in CI on real BIND9 |
| Route 53, Cloud DNS, Cloudflare | `terraform/` reads the file with `yamldecode`; Cloud DNS and Cloudflare use modules from [terraform-infra-blueprints](https://github.com/gerardrecinto/terraform-infra-blueprints) | validated and plan-tested with mocked providers |
| Infoblox | `python -m dnsops infoblox-sync` reconciles A records over WAPI, dry run by default | tested against a local stub server only |

## Layout

```
dnsops/            lint, drift check, watchdog, Infoblox client (Python)
ansible/           bind9 role: options, TSIG key, primary and secondary zones
scripts/           e2e.sh, k8s-e2e.sh, deploy.sh (lint, converge, verify, roll back)
terraform/         fan-out to Route 53, Cloud DNS, Cloudflare, with plan tests
k8s/               kind + Calico config, CoreDNS stub zone, tenant namespaces
observability/     Prometheus rules, Loki and promtail, Grafana dashboard
```

## Limits

- Two BIND containers on one Docker network, not bare metal, hypervisors or Ceph.
- Rollback is a redeploy of the last good file at a higher serial; there is no scheduler that triggers it on its own.
- The Prometheus alert rules pass `promtool check rules`; I have not triggered them end to end.
- DNSSEC is off for the BIND lab zone. The Cloud DNS module turns it on for public zones, not exercised.
- The Infoblox client covers A records only.

MIT license.
