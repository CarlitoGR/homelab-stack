# Role: uptime_kuma

Deploys [Uptime Kuma](https://github.com/louislam/uptime-kuma) for uptime monitoring and alerts. It's also the
simplest role in the repo, so use it as the template when [adding an app](../../README.md#adding-an-app).

## Networking

The container joins two networks:
- **`default`:** outbound access, for sending alerts (email, Telegram, push) and checking outside websites.
- **`nas_edge`:** reachable through Caddy, and able to check internal apps directly.

For the timesheet app, add an HTTP monitor for `http://timesheet:8000/api/healthz`. That endpoint needs no sign-in.

Authelia restricts access to the `admins` group (set in `nas_apps`). Uptime Kuma also has its own login, which you
create on first visit.

## Variables

| Variable | Default | Purpose |
|---|---|---|
| `uptime_kuma_version` | `2` | Image tag |
| `uptime_kuma_dir` | `{{ nas_docker_root }}/uptime-kuma` | Stack folder; monitoring data is in `data/` |
