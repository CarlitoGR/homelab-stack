#!/usr/bin/env bash
# Runs the whole playbook against THIS machine twice, with docker/docker-compose replaced by stubs.
# Passes when the second run reports changed=0. Needs no NAS, no Docker, and no real secrets: safe for CI.
#   tests/idempotency.sh
# If you have an encrypted vault.yml, export ANSIBLE_VAULT_PASSWORD_FILE first (Ansible still loads the file).
set -euo pipefail
cd "$(dirname "$0")/.."

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

stub="$work/compose-stub"
printf '#!/bin/sh\necho "$*" >> "%s/compose.log"\n' "$work" > "$stub"
chmod +x "$stub"

cat > "$work/vars.yml" << EOF
ansible_connection: local
ansible_become: false
ansible_python_interpreter: $(command -v python3)
nas_docker_root: $work/docker
nas_docker_bin: $stub
nas_compose_bin: $stub
edge_fetch_root_cert: false
vault_become_password: unused
vault_authelia_jwt_secret: $(openssl rand -hex 64)
vault_authelia_session_secret: $(openssl rand -hex 64)
vault_authelia_storage_encryption_key: $(openssl rand -hex 64)
vault_authelia_users:
  - username: ci
    displayname: CI
    email: ci@example.com
    password_hash: '\$argon2id\$v=19\$m=65536,t=3,p=4\$c2FsdHNhbHRzYWx0\$aGFzaGhhc2hoYXNoaGFzaGhhc2g'
    groups: [admins]
EOF

run() {
  local recap
  recap="$(ansible-playbook site.yml -e "@$work/vars.yml" | grep -E '^\S+ +: ok=')"
  echo "run $1: $recap" >&2
  sed -E 's/.*changed=([0-9]+).*failed=([0-9]+).*/\1 \2/' <<< "$recap"
}

read -r changed1 failed1 <<< "$(run 1)"
read -r changed2 failed2 <<< "$(run 2)"

if ((failed1 + failed2 > 0)); then echo "FAIL: tasks failed" >&2; exit 1; fi
if ((changed1 == 0)); then echo "FAIL: first run changed nothing; the test did not deploy" >&2; exit 1; fi
if ((changed2 != 0)); then echo "FAIL: second run changed $changed2 tasks; the playbook is not idempotent" >&2; exit 1; fi
echo "PASS: first run changed $changed1, second run changed 0" >&2
