# Role: edge

Deploys the front door for every app: **Caddy** terminates HTTPS and **Authelia** handles sign-in. Caddy's site
blocks and Authelia's access rules are generated from the site-wide `nas_apps` list.

## What it creates on the NAS

```
{{ nas_docker_root }}/edge/
├── compose.yaml                     # caddy + authelia, and the internal nas_edge network
├── caddy/etc/Caddyfile              # generated from nas_apps
├── caddy/data/                      # Caddy's local CA and certificates (keep this; see below)
└── authelia/
    ├── config/configuration.yml     # generated; contains no secrets
    ├── config/users_database.yml    # local users (only when LDAP is off)
    ├── config/certs/ldap-ca.crt     # FreeIPA CA (only when LDAP is on)
    ├── config/db.sqlite3            # registered passkeys and 2FA devices, encrypted
    ├── config/notification.txt      # verification codes (no email server)
    └── secrets/                     # one file per secret, mode 0600
```

It also downloads Caddy's root certificate to `artifacts/nas-root-ca.crt` on the workstation, for installing on your
devices.

## How requests are protected

Every app's site block runs these steps in a `route`, which keeps this exact order:

1. Delete `Remote-User`, `Remote-Groups`, `Remote-Email`, and `Remote-Name` from the incoming request.
2. `forward_auth` to Authelia. A user who isn't signed in is redirected to the sign-in portal (302 for GET, 303 for
   other methods). A signed-in user's identity headers are copied from Authelia's response.
3. `reverse_proxy` to the app.

Without `route`, Caddy's default directive order runs `forward_auth` before `request_header`, which would delete the
identity Authelia had just set.

## Variables

| Variable | Default | Purpose |
|---|---|---|
| `edge_caddy_version` | `2.11` | Caddy image tag |
| `edge_authelia_version` | `4.39` | Authelia image tag |
| `edge_dir` | `{{ nas_docker_root }}/edge` | Stack folder |
| `edge_fetch_root_cert` | `true` | Download Caddy's root certificate to `artifacts/` |

It also reads the site-wide `base_domain`, `edge_https_port`, `nas_apps`, `nas_edge_network`, `nas_timezone`,
`authelia_*`, and the `vault_authelia_*` secrets.

## Restarts

- **Authelia** restarts when its configuration, users, secrets, or LDAP CA change.
- **Caddy** restarts when the Caddyfile changes.
- Otherwise neither container is touched.

> [!IMPORTANT]
> Back up `caddy/data/`. It holds the local certificate authority. If it's lost, Caddy creates a new one, and every
> device must install the new root certificate.
