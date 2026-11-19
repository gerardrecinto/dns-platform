#!/usr/bin/env bash
# kind cluster with Calico: cluster DNS forwards lab.example to BIND, tenants are isolated.
set -euo pipefail
cd "$(dirname "$0")/.."
ok() { echo "PASS $*"; }
docker compose exec -T dns-primary pgrep named >/dev/null || { echo "run scripts/e2e.sh first so BIND is serving lab.example"; exit 1; }

kind delete cluster --name dns-lab >/dev/null 2>&1 || true
kind create cluster --name dns-lab --config k8s/kind.yaml >/dev/null
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.29.1/manifests/calico.yaml >/dev/null
kubectl -n kube-system rollout status ds/calico-node --timeout=240s >/dev/null
kubectl wait --for=condition=Ready nodes --all --timeout=240s >/dev/null

docker network connect kind dns-lab-primary 2>/dev/null || true
LAB_DNS=$(docker inspect -f '{{(index .NetworkSettings.Networks "kind").IPAddress}}' dns-lab-primary)
sed "s/__LAB_DNS__/$LAB_DNS/" k8s/coredns-stub.yaml.tpl | kubectl apply -f - >/dev/null
kubectl -n kube-system rollout restart deploy/coredns >/dev/null
kubectl -n kube-system rollout status deploy/coredns --timeout=120s >/dev/null

kubectl apply -f k8s/tenants.yaml >/dev/null
kubectl -n tenant-a run web --image=nginx:1.27-alpine --port=80 --labels=app=web >/dev/null
kubectl -n tenant-a expose pod web --port=80 >/dev/null
kubectl -n tenant-a wait --for=condition=Ready pod/web --timeout=120s >/dev/null
WEB_IP=$(kubectl -n tenant-a get pod web -o jsonpath='{.status.podIP}')

# 1. pods resolve a name that only BIND knows
kubectl -n tenant-a run dnscheck --image=busybox:1.36 --restart=Never --command -- sleep 600 >/dev/null
kubectl -n tenant-a wait --for=condition=Ready pod/dnscheck --timeout=120s >/dev/null
out=$(kubectl -n tenant-a exec dnscheck -- nslookup api.lab.example)
echo "$out" | grep -q "10.20.0.10" && ok "pod resolves api.lab.example through CoreDNS to BIND" || { echo "$out"; echo FAIL; exit 1; }

# 2. same-namespace traffic works, cross-tenant traffic is dropped
kubectl -n tenant-a exec dnscheck -- wget -qO- -T 5 http://web >/dev/null && ok "tenant-a reaches its own service"
kubectl -n tenant-b run intruder --image=busybox:1.36 --restart=Never --command -- sleep 600 >/dev/null
kubectl -n tenant-b wait --for=condition=Ready pod/intruder --timeout=120s >/dev/null
if kubectl -n tenant-b exec intruder -- wget -qO- -T 5 "http://$WEB_IP" >/dev/null 2>&1; then echo "FAIL tenant-b reached tenant-a"; exit 1; fi
ok "tenant-b cannot reach tenant-a (NetworkPolicy enforced by Calico)"

# 3. quota blocks an over-sized pod
out=$(kubectl -n tenant-a run hog --image=busybox:1.36 --restart=Never --overrides='{"spec":{"containers":[{"name":"hog","image":"busybox:1.36","command":["sleep","60"],"resources":{"requests":{"cpu":"2"},"limits":{"cpu":"2"}}}]}}' 2>&1 || true)
if echo "$out" | grep -q "exceeded quota"; then ok "quota rejected a 2 CPU pod in a 500m tenant"; else echo "$out"; echo "FAIL quota not enforced"; exit 1; fi

# 4. RBAC stays inside the namespace
[ "$(kubectl auth can-i create pods -n tenant-a --as=alice --as-group=tenant-a-devs)" = yes ] && ok "tenant-a group can create pods in tenant-a"
[ "$(kubectl auth can-i create pods -n tenant-b --as=alice --as-group=tenant-a-devs)" = no ] && ok "tenant-a group cannot create pods in tenant-b"
echo "ALL PASS"
