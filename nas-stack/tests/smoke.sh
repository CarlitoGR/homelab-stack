#!/usr/bin/env bash
# Post-deploy security smoke test. Needs no credentials; run from the Ansible controller after `ansible-playbook`.
#   tests/smoke.sh [base_domain] [https_port] [subdomains...]
#   tests/smoke.sh home.lan 8443 timesheet status
set -uo pipefail

DOMAIN="${1:-home.lan}"
PORT="${2:-8443}"
if (($# > 2)); then APPS=("${@:3}"); else APPS=(timesheet status); fi

SUFFIX=$([[ "$PORT" == 443 ]] && echo "" || echo ":$PORT")
PORTAL="https://auth.${DOMAIN}${SUFFIX}"
CA="$(cd "$(dirname "$0")/.." && pwd)/artifacts/nas-root-ca.crt"
if [[ -f "$CA" ]]; then TLS=(--cacert "$CA"); else TLS=(-k); echo "WARN  $CA missing: skipping TLS verification"; fi

pass=0
fail=0
check() { # name, actual, expected-substring
  if [[ "$2" == *"$3"* ]]; then echo "PASS  $1"; ((pass++)); else echo "FAIL  $1 (got '$2', expected '$3')"; ((fail++)); fi
}
status() { curl -s "${TLS[@]}" -o /dev/null -w '%{http_code} %{redirect_url}' --max-time 10 "$@"; }

check "Sign-in portal is up with a trusted certificate" "$(status "$PORTAL/")" "200"

for app in "${APPS[@]}"; do
  url="https://${app}.${DOMAIN}${SUFFIX}"
  check "$app: anonymous GET is sent to sign-in" "$(status "$url/")" "302 $PORTAL/"
  check "$app: forged Remote-User GET is sent to sign-in" "$(status -H 'Remote-User: admin' "$url/")" "302 $PORTAL/"
  check "$app: forged Remote-User POST is sent to sign-in" \
    "$(status -X POST -H 'Remote-User: admin' -H 'Content-Type: application/json' -d '{}' "$url/api/calc")" "303 $PORTAL/"
done

check "Bad credentials are rejected" \
  "$(curl -s "${TLS[@]}" -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' \
      -d "{\"username\":\"smoke-$RANDOM\",\"password\":\"wrong\"}" "$PORTAL/api/firstfactor")" "401"

NAS_IP=$(getent hosts "auth.${DOMAIN}" | awk '{print $1; exit}')
if [[ -n "$NAS_IP" ]]; then
  curl -s --max-time 5 -o /dev/null "http://${NAS_IP}:8000/api/healthz"
  rc=$?
  # 7 = connection refused, 28 = timed out: both mean the port is not published. 0 means it is.
  if ((rc == 7 || rc == 28)); then result="blocked"; else result="reachable (curl exit $rc)"; fi
  check "App port 8000 is not published on $NAS_IP" "$result" "blocked"
else
  echo "SKIP  auth.${DOMAIN} does not resolve on this machine: cannot test direct port access"
fi

echo "---"
echo "passed=$pass failed=$fail"
exit $((fail > 0))
