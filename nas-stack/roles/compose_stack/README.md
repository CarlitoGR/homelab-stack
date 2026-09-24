# Role: compose_stack

Reusable helper that brings one Docker Compose project up and keeps it current. Every app role finishes by including
it.

1. Runs `docker-compose up --detach --remove-orphans --wait`: creates or updates containers and waits until they're
   running and healthy.
2. Adds `--build` when `compose_stack_build` is true.
3. Restarts the services in `compose_stack_restart_services`.

Step 3 exists because Compose only notices changes to `compose.yaml` itself. When a mounted config file changes, such
as a Caddyfile, Compose sees nothing and the container keeps its old config. The calling role registers its template
tasks and passes the affected services, so only what actually changed is restarted.

## Variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `compose_stack_name` | yes | | Compose project name, shown in Container Manager |
| `compose_stack_dir` | yes | | Folder on the NAS containing `compose.yaml` |
| `compose_stack_build` | no | `false` | Rebuild images defined with `build:` |
| `compose_stack_restart_services` | no | `[]` | Services to restart after `up` |

It also uses the site-wide `nas_compose_bin`.

## Example

```yaml
- name: Render config
  ansible.builtin.template:
    src: app.conf.j2
    dest: "{{ myapp_dir }}/config/app.conf"
    mode: "0644"
  register: myapp_config

- name: Start or update myapp
  ansible.builtin.include_role:
    name: compose_stack
  vars:
    compose_stack_name: myapp
    compose_stack_dir: "{{ myapp_dir }}"
    compose_stack_restart_services: "{{ ['myapp'] if myapp_config is changed else [] }}"
```

## Change reporting

`up` reports *changed* only when Compose output shows a container was created, recreated, started, built, or pulled.
An unchanged stack reports *ok*, which is what keeps a repeat run of the whole playbook at `changed=0`.
