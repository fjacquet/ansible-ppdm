# Live lab validation log (PPDM 20.3, AWS lab)

Started 2026-11-16 against a disposable PPDM 20.3 appliance. Probe and phase playbooks live in `tools/lab/`;
raw results stay in `.ansible/lab-results/` (git-ignored, never committed). Credentials come from `.env`
(git-ignored, loaded with `uv run --env-file .env`, never read by the assistant).

## Connection

- Public EC2 name, REST API on 8443 (443 only serves the UI; nginx answers 401 on `/api/` there).
- The API gateway certificate is issued to the private name, so the new `tls_server_name` option (branch
  `feat/tls-server-name`) is used with a pinned chain (`ca_path`). Nothing is verified-off.

## Phase 1: read-only (PASS)

All 17 `*_info` modules return successfully against the live appliance. No secret-bearing field in users,
credentials or storage systems. Real alert severities, categories, role names and certificate states match the
documented enums.

## Phase 2: writes and idempotence (in progress)

| Check | Result |
| --- | --- |
| resource_group create, re-run | PASS (changed, then unchanged) |
| resource_group update (PATCH) | **BUG**: PPDM requires the `id` in the PATCH body ("request id doesn't match the request body"); the client strips it as read-only. Confirmed fix: send `id` in the PATCH body (200) |
| protection_rule create (v3) | **BUG/MODEL GAP**: PPDM needs `filterTemplate` ({name, objectSubtype, args}); for `ASSIGN_RESOURCE_GROUP` it requires `priority` and `filters` to be null (the server generates the filters). The 0.3.0 raw-`filters` model is incomplete |
| protection_rule with VMWARE_VIRTUAL_MACHINE template | rejected: asset type not enabled in this lab (no vCenter); retry with another type |
| smtp create, re-run | PASS (changed, then unchanged); earlier 422 was an invalid test address |
| protection_group create | **BUG**: server requires `subtype` (spec says optional); creates fine with `subtype: GENERIC` |
| user create | password policy: min 9 chars with lower, upper, digit and special character; probe password was too weak (not a module bug) |

## To fix (0.4.1)

1. PATCH body must carry the object `id` (all `ensure` PATCH paths: resource group, rule, protection group, restore plan).
2. `protection_rule`: add `filter_template`; make `priority` and `filters` optional per action; update docs.
3. `protection_group`: default `subtype` to `GENERIC`.
4. Add `tls_server_name` (done, `feat/tls-server-name`).
5. Document the user password policy.

## Still to validate

Rules with an enabled asset type, rule PATCH and re-run, resource-group-assigning rule execution, actions
(`activity_action`, `alert_acknowledge`, `protection_rule_run`) and `wait` on v3 statuses, then the service-affecting
modules (`restore_plan_run`, `upgrade_package_action` precheck) only with explicit approval.
