# fjacquet.ppdm

[![CI](https://github.com/fjacquet/ansible-ppdm/actions/workflows/ci.yml/badge.svg)](https://github.com/fjacquet/ansible-ppdm/actions/workflows/ci.yml)
[![License: GPL v3+](https://img.shields.io/badge/license-GPL--3.0--or--later-blue.svg)](LICENSE)
[![Ansible Galaxy](https://img.shields.io/badge/galaxy-fjacquet.ppdm-660198.svg)](https://galaxy.ansible.com/ui/repo/published/fjacquet/ppdm/)
[![ansible-core](https://img.shields.io/badge/ansible--core-%E2%89%A5%202.20-1A1918.svg)](https://docs.ansible.com/projects/ansible/latest/)
[![Status](https://img.shields.io/badge/status-1.0%20lab--validated%20(partial)-green.svg)](#validation-status)

Ansible collection for Dell PowerProtect Data Manager (PPDM) 20.3.0: modules, a bootstrap role and ready-to-run playbooks
that talk to the PPDM REST API.

This collection is **unofficial**. It is not affiliated with, endorsed by, or supported by Dell Technologies.
PowerProtect is a trademark of Dell Technologies.

## Validation status

> **1.0.0.** The modules and playbooks were exercised against one disposable PowerProtect Data
> Manager 20.3.0 appliance (AWS, 2026-11-16), and the bugs found there are fixed in this release. That lab had no vCenter,
> no Data Domain and no protected data, so a part of the collection could only be checked against the OpenAPI files.
> Try every write on a lab before production, and read the lists below.

**Validated on the live lab:**

- Connection and TLS (including `tls_server_name` with a pinned CA chain), login and token refresh.
- All `*_info` modules (read-only).
- Idempotent create, re-run, update (PATCH) and delete: `resource_group`, `protection_rule` (with `filter_template`),
  `protection_policy`, `protection_group`, `smtp`, `user`, `credential`.
- `alert_acknowledge` (check mode, acknowledge, re-run, restore), `protection_rule_run` (resource group rules by id,
  policy rules with `all_rules_of_action`), `discovery` with `wait` (a failed activity is reported), `activity_info`.
- `activity_action` guards: refusal without `confirm`, no-op on a finished activity, refusal when PPDM offers no action.
- Agent registration on a Linux host (`agents` playbooks), 15 read-only playbooks and the resource group, protection
  group and rule-run playbooks.

**Not validated on a live appliance** (written against the 20.3.0 OpenAPI only, treat as untested):

- `activity_action` cancel and retry success paths, `restore_plan`, `restore_plan_run`, `upgrade_package_action`
  (the last two are service-affecting), `protection_rule_run` preview success path and `wait` (PPDM 20.3 answers a rule
  run with no `activityId`), `protection_policy_run`, `protection_policy_assets`, `copy_info`, `storage_system`,
  `inventory_source` for vCenter or Data Domain, `certificate`, Cloud DR and Kubernetes playbooks, bootstrap playbooks
  that change the appliance (`bootstrap`, `set_license`, `replace_certificate`).
- `discovery` can only start from an inventory source. PPDM needs `/hosts/<id>` to discover an agent host, use the
  `api` module for that.
- Behaviour that only shows on real data: rule `filters` for asset types other than the lab's, ordering of lists PPDM
  stores, the `smtp` and `user` password handling on update (`user` uses `/api/v2/users`, which 20.3.0 deprecates).

**Facts learned from the live appliance:** PATCH needs the object `id` in the body; a v3 rule is built from a
`filterTemplate` (and `priority` and `filters` must be unset for `ASSIGN_RESOURCE_GROUP`); a new protection group needs a
`subtype`; a new policy needs client-supplied UUIDs on objectives, operations and retentions; policy timestamps come
back without milliseconds; PPDM runs `ASSIGN_PROTECTION_POLICY` rules only all together; local user passwords need 9 to
100 characters with a lower case letter, an upper case letter, a digit and a special character.

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
| `PPDM_TLS_SERVER_NAME` | name the certificate is verified against (optional) |

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

### Certificate issued for another name

When PPDM is reached through an address its certificate was not issued for (for example an AWS public DNS name
while the certificate carries `ip-10-0-14-147.eu-west-1.compute.internal`), verification fails with "IP address
mismatch". Set `tls_server_name` to verify the certificate against that name (also sent as SNI) while still connecting
to `hostname`. Chain verification stays fully on (`validate_certs`, `ca_path`); this does not disable it.

```yaml
- fjacquet.ppdm.storage_system_info:
    hostname: ec2-203-0-113-10.eu-west-1.compute.amazonaws.com
    tls_server_name: ip-10-0-14-147.eu-west-1.compute.internal
    ca_path: /etc/ssl/ppdm-ca.pem
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
| `fjacquet.ppdm.discovery` | Start a discovery on an inventory source |
| `fjacquet.ppdm.inventory_source_info` | Get inventory sources |
| `fjacquet.ppdm.inventory_source` | Create, update or delete inventory sources |
| `fjacquet.ppdm.protection_policy_info` | Get protection policies |
| `fjacquet.ppdm.protection_policy` | Create, update or delete protection policies |
| `fjacquet.ppdm.protection_policy_assets` | Assign or unassign assets to a protection policy |
| `fjacquet.ppdm.protection_policy_run` | Run a protection policy now |
| `fjacquet.ppdm.protection_rule_info` | Get protection rules |
| `fjacquet.ppdm.protection_rule` | Create, update or delete protection rules |
| `fjacquet.ppdm.protection_rule_run` | Run a protection rule or preview its conflicts |
| `fjacquet.ppdm.resource_group_info` | Get resource groups |
| `fjacquet.ppdm.resource_group` | Create, update or delete resource groups |
| `fjacquet.ppdm.protection_group_info` | Get protection groups |
| `fjacquet.ppdm.protection_group` | Create, update or delete protection groups |
| `fjacquet.ppdm.asset_info` | Get assets |
| `fjacquet.ppdm.host_info` | Get hosts |
| `fjacquet.ppdm.storage_system_info` | Get storage systems |
| `fjacquet.ppdm.storage_system` | Update a storage system |
| `fjacquet.ppdm.activity_info` | Get activities |
| `fjacquet.ppdm.activity_action` | Cancel or retry an activity |
| `fjacquet.ppdm.alert_info` | Get alerts |
| `fjacquet.ppdm.alert_acknowledge` | Acknowledge or unacknowledge alerts |
| `fjacquet.ppdm.copy_info` | Get copies (backups) |
| `fjacquet.ppdm.smtp_info` | Get the SMTP configuration |
| `fjacquet.ppdm.smtp` | Create, update or delete the SMTP configuration |
| `fjacquet.ppdm.user_info` | Get users |
| `fjacquet.ppdm.user` | Create, update or delete local users |
| `fjacquet.ppdm.role_info` | Get roles |
| `fjacquet.ppdm.restore_plan_info` | Get restore plans |
| `fjacquet.ppdm.restore_plan` | Create, update or delete restore plans |
| `fjacquet.ppdm.restore_plan_run` | Execute a restore plan |
| `fjacquet.ppdm.upgrade_package_info` | Get upgrade packages |
| `fjacquet.ppdm.upgrade_package_action` | Precheck, install or revert an upgrade package |

Run `ansible-doc fjacquet.ppdm.<module>` for the options and examples.

## Roles

- `fjacquet.ppdm.bootstrap`: brings a freshly deployed PPDM to a configured state (wait for the API, accept the EULA, apply the
  initial configuration, wait for it to finish). See `roles/bootstrap/README.md`.

## Playbooks

66 playbooks grouped by use case (bootstrap, sources, protection, assets, agents, kubernetes, clouddr, maintenance) ship with
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
