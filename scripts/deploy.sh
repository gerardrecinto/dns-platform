#!/usr/bin/env bash
# Deploy one zone file to the lab pair: lint, converge the primary, wait for the secondary,
# check for drift, and roll back to the last good file if verification fails.
# usage: scripts/deploy.sh zones/lab.example.yml <serial>
set -euo pipefail
cd "$(dirname "$0")/.."
ZONE=${1:?zone file}; SERIAL=${2:?serial}
KEY=".tsig.vars.yml"; LKG=".lkg.yml"
P="docker compose exec -T dns-primary"; S="docker compose exec -T dns-secondary"
secret() { sed -n 's/^tsig_secret: //p' "$KEY"; }

converge() { # file serial
  cp "$1" zones/.deploy.yml
  $P ansible-playbook -c local -i localhost, ansible/site.yml -e bind9_role=primary -e @"$KEY" -e zone_file=/lab/zones/.deploy.yml -e zone_serial="$2" >/dev/null
  $P rndc reload >/dev/null
}
verify() { # file serial
  [ "${INJECT_VERIFY_FAILURE:-0}" = 1 ] && return 1
  for _ in $(seq 1 30); do
    [ "$($S dig +short +norecurse @127.0.0.1 SOA lab.example. | awk '{print $3}')" = "$2" ] && break
    sleep 1
  done
  $P env TSIG_SECRET="$(secret)" python3 -m dnsops drift /lab/zones/.deploy.yml --primary 172.28.0.11 --secondary 172.28.0.12
}

.venv/bin/python -m dnsops lint "$ZONE"
converge "$ZONE" "$SERIAL"
if verify "$ZONE" "$SERIAL"; then
  cp "$ZONE" "$LKG"; echo "deployed serial $SERIAL"
else
  echo "verification failed, rolling back to last good zone at serial $((SERIAL + 1))"
  converge "$LKG" "$((SERIAL + 1))"
  verify "$LKG" "$((SERIAL + 1))"
  exit 1
fi
