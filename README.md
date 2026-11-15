# fjacquet.ppdm

[![CI](https://github.com/fjacquet/ansible-ppdm/actions/workflows/ci.yml/badge.svg)](https://github.com/fjacquet/ansible-ppdm/actions/workflows/ci.yml)
[![License: GPL v3+](https://img.shields.io/badge/license-GPL--3.0--or--later-blue.svg)](LICENSE)
[![Ansible Galaxy](https://img.shields.io/badge/galaxy-fjacquet.ppdm-660198.svg)](https://galaxy.ansible.com/ui/repo/published/fjacquet/ppdm/)
[![ansible-core](https://img.shields.io/badge/ansible--core-%E2%89%A5%202.20-1A1918.svg)](https://docs.ansible.com/projects/ansible/latest/)
[![Pre-release](https://img.shields.io/badge/status-0.x%20pre--release-orange.svg)](#)

Ansible collection for Dell PowerProtect Data Manager (PPDM) 20.3.0: modules, a bootstrap role and ready-to-run playbooks
that talk to the PPDM REST API.

This collection is **unofficial**. It is not affiliated with, endorsed by, or supported by Dell Technologies.
PowerProtect is a trademark of Dell Technologies.

> **0.x pre-release, not yet validated against a live PPDM 20.3.** Endpoints and request bodies follow the 20.3.0
> OpenAPI files, but nothing has been run against a real appliance. Try it on a lab first.

Lab checklist before 1.0.0:

- PUT-replace with write-only fields: confirm that an update does not clear or overwrite secrets (credential
  `password`, SMTP `password`, Cloud DR `secretKey`) when they are not part of the request body.
- `certificate` `state=absent` lists with `nocache=true`: confirm it still finds the stored trust-store entry.
- Bootstrap readiness: confirm how a 401/403 is handled while the appliance is still starting (the wait stops at the first one).

## Requirements

- ansible-core 2.20 or later (on the control node).
- Network access from the control node to the PPDM REST API (default port 8443).

No other runtime dependency.

## Installation

```
ansible-galaxy collection install fjacquet.ppdm
```

## Authentication

Every module reads its connection settings from environment variables, so no secret has to live in a playbook:

| Variable | Meaning |
|----------|---------|
| `PPDM_HOSTNAME` | PPDM host name or IP address |
| `PPDM_USERNAME` | PPDM user |
| `PPDM_PASSWORD` | PPDM password |
| `PPDM_PORT` | REST port, default 8443 |

To share explicit values across tasks, use the `ppdm` action group:

```yaml
- hosts: localhost
  module_defaults:
    group/fjacquet.ppdm.ppdm:
      hostname: "{{ lookup('env', 'PPDM_HOSTNAME') }}"
      username: "{{ lookup('env', 'PPDM_USERNAME') }}"
      password: "{{ lookup('env', 'PPDM_PASSWORD') }}"
  tasks:
    - fjacquet.ppdm.storage_system_info:
```

## Modules

| Module | Purpose |
|--------|---------|
| `fjacquet.ppdm.api` | Call any PPDM REST endpoint (GET, POST, PUT, PATCH, DELETE) |
| `fjacquet.ppdm.certificate_info` | Get certificates |
| `fjacquet.ppdm.certificate` | Trust or remove a host certificate |
| `fjacquet.ppdm.credential_info` | Get credentials |
| `fjacquet.ppdm.credential` | Create, update or delete credentials |
| `fjacquet.ppdm.eula` | Accept an end user license agreement |
| `fjacquet.ppdm.inventory_source_info` | Get inventory sources |
| `fjacquet.ppdm.inventory_source` | Create, update or delete inventory sources |
| `fjacquet.ppdm.storage_system_info` | Get storage systems |
| `fjacquet.ppdm.storage_system` | Update a storage system |

Run `ansible-doc fjacquet.ppdm.<module>` for the options and examples.

## Roles

- `fjacquet.ppdm.bootstrap`: brings a freshly deployed PPDM to a configured state (wait for the API, accept the EULA, apply the
  initial configuration, wait for it to finish). See `roles/bootstrap/README.md`.

## Playbooks

58 playbooks grouped by use case (bootstrap, sources, protection, assets, agents, kubernetes, clouddr, maintenance) ship with
the collection and run by name, for example:

```
ansible-playbook fjacquet.ppdm.sources.add_data_domain -e @my-vars.yml
```

See `playbooks/README.md` for the list, the variables and the confirm flags of the destructive ones.

## Security notes

- Masked in module output and logs: the login password and token, and the `password` key of `credential` (one level of
  JSON escaping only: a secret inside a doubly escaped string is not masked). Nothing else is masked: not the `result`
  of `fjacquet.ppdm.api`, not the `config` option of `inventory_source` and `storage_system`, not nested credential fields.
- For `fjacquet.ppdm.api`, the request `body` and the returned `result` are not masked. For `inventory_source` and
  `storage_system`, the `config` is not masked either. Do not put secrets there unless you also set `no_log: true` on
  the task.
- The certificate trust gate stores the certificate PPDM presents before the fingerprint pin is checked.
  Verify the fingerprint out of band and review what was stored.
- HTTP redirects are never followed (`follow_redirects: none`), so the Authorization header is never forwarded.
- The `hostname` option accepts a DNS name or an IP literal only (allowlist), not a URL.

## Attribution

The workflows are reimplemented from [bottkars/ansible_ppdm](https://github.com/bottkars/ansible_ppdm) as Python modules and
playbooks. No YAML is copied. See `NOTICE`.

## License

GPL-3.0-or-later. See `LICENSE`.

## Development

Tools run through [uv](https://docs.astral.sh/uv/):

```
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python tools/generate.py modules --check
```

`ansible-test` needs a checkout under a real `.../ansible_collections/fjacquet/ppdm/` path: use a git worktree, then
`uv run --project <repo> ansible-test units --python 3.13` from inside it. Create the worktree with
`git worktree add --detach <dir>/ansible_collections/fjacquet/ppdm HEAD`.
