# nas-stack

Ansible deployment for a Synology DS1525+ (DSM 7.2+): Caddy (HTTPS) and Authelia (passwords + passkeys/2FA) in front
of the timesheet app and Uptime Kuma. Idempotent: a second run with no changes reports `changed=0` and restarts nothing.

```
Browser ──HTTPS :8443──▶ Caddy ──forward_auth──▶ Authelia (sign-in, passkeys, 2FA; FreeIPA optional)
                           │
                           └── internal network only ──▶ timesheet   uptime-kuma
```

- **Apps have no published ports.** They sit on an internal Docker network reachable only through Caddy. That is what
  makes it safe for the timesheet app to trust the `Remote-User` header.
- **Caddy strips client-sent identity headers, then asks Authelia.** Only Authelia can set who the user is.
- **Access is deny-by-default.** Each app in `nas_apps` gets an explicit Authelia rule; unlisted hosts get nothing.

## Prerequisites

| Where | What |
|---|---|
| DSM | Container Manager installed (Package Center) |
| DSM | SSH on: Control Panel → Terminal & SNMP → Enable SSH service |
| DSM | An account in the `administrators` group (it can `sudo` with its own password) |
| DSM | Recommended: the `docker` shared folder on the NVMe storage pool |
| Network | `auth`, `timesheet`, and `status` under your `base_domain` resolve to the NAS IP (router DNS, AdGuard Home, or hosts files) |
| Controller | Ansible 9+ (`pip install ansible`), `ssh`, `curl`, `openssl`; this folder next to `timesheet-calc/` |

Remote access: use Tailscale on the NAS and publish nothing on your router. So the hostnames resolve away from home,
enable subnet routing for your LAN and add a split-DNS entry for `base_domain` in the Tailscale admin console.

## First deployment

1. **Inventory.** In `inventory/hosts.yml`, set the NAS IP and your DSM admin username. Review
   `inventory/group_vars/nas/main.yml`, mainly `base_domain` and `nas_timezone`.

2. **Secrets.**
   ```bash
   cp inventory/group_vars/nas/vault.yml.example inventory/group_vars/nas/vault.yml
   openssl rand -hex 64      # run three times: JWT secret, session secret, storage encryption key
   ```
   Generate your password hash on any Docker host (the NAS works over SSH):
   ```bash
   sudo docker run --rm -it authelia/authelia:4.39 authelia crypto hash generate argon2
   ```
   Paste the `Digest:` value into `password_hash`, and fill in the rest of `vault.yml`.

3. **Encrypt the vault.**
   ```bash
   openssl rand -base64 32 > .vault_pass && chmod 600 .vault_pass     # git-ignored
   export ANSIBLE_VAULT_PASSWORD_FILE="$PWD/.vault_pass"              # add to your shell profile or .envrc
   ansible-vault encrypt inventory/group_vars/nas/vault.yml
   ```
   The password file is set by environment variable rather than in `ansible.cfg`, so a fresh copy of this folder
   still works (lint, `--syntax-check`) before any vault exists.

4. **Test the SSH connection, then deploy.**
   ```bash
   ansible nas -m ansible.builtin.ping
   ansible-playbook site.yml
   ```
   The first run pulls images and builds the timesheet app: allow 5 to 10 minutes.

5. **Trust the certificate.** The playbook saves Caddy's root certificate to `artifacts/nas-root-ca.crt`. Install it
   on each device as a trusted root:
   - **Windows:** double-click → Install Certificate → Local Machine → Trusted Root Certification Authorities.
   - **macOS:** open it in Keychain Access (System keychain) → set it to Always Trust.
   - **iPhone:** AirDrop or email it and install the profile, then turn on full trust under
     Settings → General → About → Certificate Trust Settings.
   - **Android:** Settings → Security → Encryption & credentials → Install a certificate → CA certificate.
   - **Firefox:** uses its own store. Settings → Privacy & Security → Certificates → Import.

6. **Run the smoke test.**
   ```bash
   tests/smoke.sh home.lan 8443 timesheet status
   ```
   It checks, without credentials, that every app redirects to sign-in, that forged identity headers are rejected,
   that bad passwords fail, and that the app port is not published. It exits non-zero on any failure.

## First sign-in and registering a passkey

1. Open `https://timesheet.home.lan:8443` → you're sent to the sign-in page → enter your username and password.
2. Both apps require two-factor, so Authelia asks you to register a device. Choose **Passkey / security key** (or a
   one-time-code app).
3. Authelia emails a one-time code to confirm it's you. No email server is configured, so the code is written to a
   file on the NAS instead:
   ```bash
   ssh nasadmin@<nas-ip> sudo tail -20 /volume1/docker/edge/authelia/config/notification.txt
   ```
4. Enter the code and finish registration. After that, you can sign in with the passkey alone.

## Day-to-day operations

| Task | How |
|---|---|
| Deploy only one part | `ansible-playbook site.yml --tags timesheet` (or `edge`, `uptime_kuma`) |
| Update the timesheet app | Change the code in `timesheet-calc/`, rerun. It rebuilds only if a source file changed. |
| Upgrade Caddy, Authelia, or Kuma | Change `edge_caddy_version`, `edge_authelia_version`, or `uptime_kuma_version`, then rerun. Read Authelia's release notes before a minor-version jump. |
| Add or remove a user | Edit `vault_authelia_users` (`ansible-vault edit ...`), rerun. Authelia restarts automatically. |
| Reset a password | Generate a new hash, replace it in the vault, rerun |
| Preview changes | `ansible-playbook site.yml --check --diff` (compose commands are skipped in check mode) |

**Never change `vault_authelia_storage_encryption_key` after the first deploy.** It encrypts the stored passkeys
and 2FA devices; changing it locks everyone out of their second factor. The other two secrets can be rotated; doing
so signs everyone out.

## Adding another app

1. Create `roles/<app>/` with `tasks/main.yml`, `defaults/main.yml`, and `templates/compose.yaml.j2`. Use
   `roles/uptime_kuma` as the pattern:
   - Join the external `{{ nas_edge_network }}` network, and publish no `ports:`.
   - Finish with `include_role: compose_stack`.
2. Add an entry to `nas_apps` in `group_vars` with its subdomain, `container:port` upstream, and policy.
3. Add the role to `site.yml`, add the hostname to DNS, and rerun.

Caddy's site and Authelia's access rule are generated from `nas_apps`, so there is nothing else to edit.

Some apps have their own clients that can't handle a browser sign-in page, such as Vaultwarden's mobile apps.
They need an Authelia `bypass` rule for their API paths, so treat those individually.

## Using FreeIPA accounts

Set `authelia_ldap_enabled: true` and fill in `authelia_ldap` in `group_vars`:

- **Bind account:** a system account with read access, e.g. `uid=authelia,cn=sysaccounts,cn=etc,<base_dn>`.
- **Password:** put the bind password in `vault_authelia_ldap_password`.
- **CA certificate:** set `ca_cert_src` to your IPA CA certificate, for example `/etc/ipa/ca.crt` copied to the
  controller. Authelia verifies the LDAPS certificate against it.
- **Groups:** FreeIPA groups work directly in `nas_apps[].groups`.

The local users file is then ignored.

## Troubleshooting

| Symptom | Likely cause → fix |
|---|---|
| `python3: not found` on connect | DSM build without system Python → install Python 3 from Package Center and set `ansible_python_interpreter: /usr/local/bin/python3` |
| Preflight: Docker or Compose missing | Container Manager not installed, or different paths → check with `ssh nas 'ls /usr/local/bin/docker*'` |
| Browser shows a certificate warning | The root certificate isn't installed on that device (step 5) |
| Redirect loop or "unable to determine cookie domain" | The URL's host isn't under `base_domain`, or you used the IP instead of the hostname |
| Sign-in works but the app shows "Your sign-in has expired" | The Authelia session ended → reload the page |
| Stack fails with `--wait` | A container is unhealthy → `sudo docker logs authelia` (or `caddy`, `timesheet`) on the NAS |
| Port 8443 already in use | Change `edge_https_port`, rerun, and use the new port in URLs |

## Verification performed before delivery

This playbook was not run on a physical DS1525+. Everything short of that was verified:

- **Local deployment:** the playbook ran against a local target with a stand-in for `docker-compose`. The first run
  made 13 changes; the second made 0, with no rebuilds or restarts. Editing only the Caddyfile restarted only Caddy.
- **Config validation:** the rendered Authelia config passed `authelia validate-config` (v4.39.28), and the Caddyfile
  passed `caddy validate` and `caddy fmt` (v2.11.4).
- **Live attack test:** real Caddy, Authelia, and the app were run together with the rendered configs. All 10 checks
  passed, including:
  - A forged `Remote-User` header is blocked.
  - For a signed-in user, a forged header is overwritten with the real identity.
  - A two-factor app still requires the second factor after the password.
  - An unlisted host is refused.
- **Lint:** clean on `ansible-lint` (production profile) and `yamllint`.
