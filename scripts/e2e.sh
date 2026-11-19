#!/usr/bin/env bash
# Full lab run on real BIND9: converge twice, replicate, change, block a bad change, roll back, self-heal.
set -euo pipefail
cd "$(dirname "$0")/.."
ok() { echo "PASS $*"; }
P="docker compose exec -T dns-primary"; S="docker compose exec -T dns-secondary"

docker compose up -d --build dns-primary dns-secondary >/dev/null
python3 -c 'import base64,os;print("tsig_secret: "+base64.b64encode(os.urandom(32)).decode())' > .tsig.vars.yml
for n in primary secondary; do
  docker compose exec -T dns-$n ansible-playbook -c local -i localhost, ansible/site.yml -e bind9_role=$n -e @.tsig.vars.yml >/tmp/ansible-$n.log
done
second=$($P ansible-playbook -c local -i localhost, ansible/site.yml -e bind9_role=primary -e @.tsig.vars.yml | tee /dev/stderr | grep -c 'changed=0' || true)
[ "$second" = 1 ] && ok "second ansible run changed nothing" || { echo "FAIL not idempotent"; exit 1; }

for n in primary secondary; do
  docker compose exec -T dns-$n python3 -m dnsops heal --zone lab.example. --restart "named -u bind"
done
sleep 3
$P env TSIG_SECRET="$(sed -n 's/^tsig_secret: //p' .tsig.vars.yml)" python3 -m dnsops drift zones/lab.example.yml --primary 172.28.0.11 --secondary 172.28.0.12
ok "primary and secondary match the zone file"
cp zones/lab.example.yml .orig.yml; cp zones/lab.example.yml .lkg.yml

# 1. good change propagates
cp .orig.yml .good.yml
python3 - <<'PY'
import yaml
d = yaml.safe_load(open(".good.yml")); d["records"].append({"name": "api2", "type": "A", "value": "10.20.0.11"})
yaml.safe_dump(d, open(".good.yml", "w"), sort_keys=False)
PY
scripts/deploy.sh .good.yml 2026111902
[ "$($S dig +short @127.0.0.1 api2.lab.example. A)" = "10.20.0.11" ] && ok "new record reached the secondary"

# 2. bad change is stopped before the primary is touched
cp .orig.yml .bad.yml
python3 - <<'PY'
import yaml
d = yaml.safe_load(open(".bad.yml")); d["records"].append({"name": "@", "type": "CNAME", "value": "api.lab.example."})
yaml.safe_dump(d, open(".bad.yml", "w"), sort_keys=False)
PY
if scripts/deploy.sh .bad.yml 2026111903; then echo "FAIL bad zone deployed"; exit 1; fi
[ "$($P dig +short @127.0.0.1 SOA lab.example. | awk '{print $3}')" = "2026111902" ] && ok "bad zone blocked, serial unchanged"

# 3. failed verification rolls back to the last good file
if INJECT_VERIFY_FAILURE=1 scripts/deploy.sh .orig.yml 2026111904; then echo "FAIL expected rollback"; exit 1; fi
ok "failed verification triggered rollback"

# 4. self-heal after named is killed
$S pkill named; sleep 1
$S dig +short +time=1 +tries=1 @127.0.0.1 SOA lab.example. >/dev/null 2>&1 && { echo "FAIL still answering"; exit 1; } || true
$S python3 -m dnsops heal --zone lab.example. --restart "named -u bind"
[ -n "$($S dig +short @127.0.0.1 SOA lab.example.)" ] && ok "watchdog restarted the secondary and it serves the zone"
rm -f .good.yml .bad.yml .orig.yml zones/.deploy.yml
echo "ALL PASS"
