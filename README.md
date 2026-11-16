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
- Bootstrap config-status poll: confirm when PPDM switches to the new admin password (the poll uses it from the first try and stops on the first 401/403).
- `protection_policy` update uses PATCH: confirm that whole-list `objectives` and `overrides` replace the existing lists and that stripping the read-only fields is enough for PPDM to accept the body.
- Protection policy names are not enforced unique by the API: confirm the behaviour on a duplicate name (the module fails and lists the ids).
- `protection_policy_assets` idempotence reads `GET /api/v2/protection-policies/<id>/asset-assignments`: confirm it returns Asset objects with an `id`, as the module assumes.
- Activity results: confirm that `GET /api/v3/activities/{id}` reports `result.status` `SUCCESS`, `COMPLETED_WITH_EXCEPTIONS` or `FAILED` (v3), whether any path still returns the v2 values `OK`, `OK_WITH_ERRORS`, and that the 202 bodies of `/api/v3/protections` and `/api/v2/discoveries` are not activities (`activityId` and `taskId` are polled).
- `activity_info`: confirm how deep v3 paging goes on `/api/v3/activities`.
- `activity_action`: confirm that cancel and retry accept an empty body `{}`, that retry answers a new `activityId`, that a cancelled activity ends `COMPLETED` with `result.status` `CANCELED`, and what the 202 bodies of retry and cancel contain.
- `alert_acknowledge`: confirm the 207 `bulkResults` shape, that `errorResponseObject` is set only on failed items (only failures are reported) and the `acknowledgementCount` value.
- `copy_info`: confirm that `/api/v2/latest-copies` rejects `page`/`pageSize` under strict validation, the `assetId in (...)` filter syntax, and that `/api/v3/copies/{id}` answers 404 for an unknown id (the module treats it as not found).
- `smtp`: confirm that POST answers 201 with an empty body or 200 with the object. A PUT without `password` may clear the relay password (the same unverified point as in the first item), and the `update_password` semantics differ from `user`. Confirm that `smtp/test` takes the body field `recipient` (the endpoint text says `mailRecipient`).
- `user` and `user_info` use `/api/v2/users`, which 20.3.0 deprecates in favour of `/api/v3/identity-access-provisions`. Confirm that PUT without `password` keeps it and that the role is matched by `name` (not `displayName`).
- `restore_plan`: confirm that PATCH replaces `restoreGroups` as a whole list and keeps their order, and confirm the read-only set. `restoreGroups[].extendedData` is free-form and may carry credentials; it is not masked (credentials are normally referenced by id), so use `no_log: true` if you put secrets there.
- `restore_plan_run`: confirm the 201/202 `activities` list, that one activity is started per restore group, and how `wait` behaves with an empty response body.
- `upgrade_package_action`: service-affecting, untested on a live appliance. Confirm that the PUT needs the GET body including `upgradeToken`, that 202 is the only success (the spec gives 200 an `ErrorMessage`), the `forceUpgrade` semantics, when `lockboxPassphrase` is required, and that revert applies only to `HOTFIX` packages with `revertSupported`. The precheck `wait` polls `resp.activityId`, which the spec ties to hotfix and revert: it may be missing after a precheck. The default revert id picks the `ACTIVE` package. Confirm how the `INSTALLED_CORE` and `WITH_ERRORS` states are handled.
- `restore_plan_run` and `upgrade_package_action` are service-affecting and have not been run on a live appliance.
- `protection.create_protection_group`: confirm the minimal body for `STORAGE_DIRECT_APPLICATION` and `ORACLE_DATA_GUARD`.
- `protection_policy` `overrides`: confirm whether GET returns an empty `overrides` list or omits it, since an empty list removes all overrides.
- `protection_policy` compares reordered `objectives` by index: confirm PPDM keeps the order of the objectives it stores.
- `protection.add_file_system_policy` and `protection.add_mssql_policy` compare the policy with `startTime`/`duration`: confirm GET returns them exactly as sent (else the fs/mssql policy playbooks PATCH on every run).
- Rule `filters`: confirm the `fieldName`/`fieldData` shapes PPDM accepts (a minimal tag or name condition per asset type). The `tags` (VMs) and `userTags` (Kubernetes) `fieldName` values are unverified guesses.
- Rule `args` items `{name, values}` for `PROTECTION_POLICY_ID` and `RESOURCE_GROUP_ID`: confirm the shape.
- Rules carry no `protectionPolicyRef`, the policy is the `action.args[PROTECTION_POLICY_ID]` item. Protection group `protectionPolicyRef`: confirm PPDM accepts `{id}` only on POST/PATCH, and whether `autoAssignToPolicy` without a policy reference is rejected.
- Confirm whether PPDM re-orders `filters` conditions or `natural_ids` (a flapping `changed`).
- Protection group `PATCH` of `naturalIds`: confirm it replaces the whole list (protection groups have no `rules`).
- Rule `scopes` and `categories` are compared in order: confirm PPDM keeps the order it stores (else a flapping `changed`).
- `protection_rule_run`: confirm the 202 body of `rule-execution` (activity or not), the preview semantics, that an explicit `action_name` differing from the rule action is handled, and that preview accepts the rule body including read-only fields.
- `protection_policy_run` requires `asset_ids` or `protection_group_ids` and cannot set `operation.backupLevel`; `Source` has no required field in the spec.
- `protection_rule_run` preview POSTs even in check mode (documented as read-only): confirm it changes nothing.

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
