# Role: preflight

Validates everything it can **before** the playbook changes the NAS, so a typo fails in seconds with a clear message
instead of half-deploying. It runs first and is tagged `always`, so it also runs with `--tags`.

## Checks

| Check | Fails when |
|---|---|
| Site settings | `base_domain` has no dot; subdomains are duplicated or use the reserved `auth`; a `policy` isn't `one_factor`, `two_factor`, or `deny` |
| Secrets | Any Authelia secret is shorter than 64 characters or still contains `CHANGE_ME` |
| Local users | No users defined, a hash isn't argon2id, or a placeholder hash remains (skipped when LDAP is on) |
| LDAP | Address isn't `ldap://` or `ldaps://`, or no bind password (only when LDAP is on) |
| Timesheet source | No `Dockerfile` under `timesheet_src_dir` on the workstation |
| NAS | `docker` or `docker-compose` missing at the configured paths (Container Manager not installed) |

Secret values are never printed: every secret check uses `no_log`.

It also creates `nas_docker_root` if it's missing.

## Variables

None of its own. It reads the site settings in `inventory/group_vars/nas/main.yml` and the secrets in `vault.yml`.
