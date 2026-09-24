# Role: timesheet

Deploys the [timesheet app](../../../timesheet-calc/) by copying its source to the NAS and building the image there.
No registry is needed.

## Behavior

- **Source sync:** copies `timesheet_src_dir` from the workstation to `{{ timesheet_dir }}/src/`. It skips caches,
  virtualenvs, VCS folders, tests, and build output (`timesheet_source_exclude_parts`).
- **Rebuild only on change:** the image is rebuilt only if at least one source file changed during this run.
- **Runs behind Caddy only:**
  - Header authentication is on (`TIMESHEET_AUTH_MODE=header`).
  - It has no published port and sits only on the internal `nas_edge` network.
  - Its filesystem is read-only, with limits of 256 MB of memory and half a CPU core.

> [!NOTE]
> The sync adds and updates files but doesn't delete them. If you remove a source file, delete it from
> `{{ timesheet_dir }}/src/` on the NAS too.

## Variables

| Variable | Default | Purpose |
|---|---|---|
| `timesheet_dir` | `{{ nas_docker_root }}/timesheet` | Stack folder on the NAS |
| `timesheet_source_exclude_parts` | caches, VCS, tests, build output | Regex fragments for paths not sent to the NAS |

The site-wide settings it reads are `timesheet_src_dir` (source on the workstation), `timesheet_allowed_users`
(optional allowlist), and `nas_edge_network`.

## Requirements

It uses the `community.general.filetree` lookup. That collection is included with the full `ansible` package; with
`ansible-core` alone, run `ansible-galaxy collection install -r requirements.yml`.
