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

### Probe 3 results (rules and users)

- Only `POWERSTORE_BLOCK` is an enabled asset type in this lab; a rule for any other type is rejected with "The asset
  type X is not enabled".
- `POST /api/v3/rules` with `filterTemplate` (`ALL_ASSETS_BY_TYPE`, `objectSubtype`, `args: [{ASSET_TYPE, values}]`),
  `action` `ASSIGN_RESOURCE_GROUP` with `RESOURCE_GROUP_ID`, and no `priority` or `filters`: **201**.
- The server generated `filters` in the shape the validator already enforces: filter, then one logical condition, then
  relational conditions with `fieldName: type`, `operator: EQUALS`, `fieldData: {type: STRING, values: [...]}`,
  `displayValues: null`, `displayOrder` set. Stored rule also has `filter`, `filterTemplate`, `occVersion`, and
  `priority`, `variant`, `scopes`, `categories` all null.
- User create with a compliant password (>= 9 chars, lower, upper, digit, special): PASS, and the re-run is unchanged
  (`update_password: on_create`).

### Probe 4 results (rule PATCH)

- PATCH without `id` in the body: **400** "A parameter / property / argument value is not valid."
- PATCH with `id` only: **200**, `occVersion` moves 4.7 to 4.8. No `occVersion` needed in the request.
- PATCH with a stale `occVersion` (0): **412** "OCC version mismatch. provided=0 current=4.8". The server enforces
  optimistic concurrency only when the client sends `occVersion`.
- Conclusion: the fix is `id` in the PATCH body, nothing more. `occVersion` stays read-only and is stripped.
- A new rule starts `status: CREATING`, then becomes `ACTIVE` with `lastRunAt` set within seconds (the server runs it
  on creation).

## Phase 2 re-run with the fixes (commit 750b06f): PASS

resource_group create, re-run, PATCH update, delete; protection_rule (POWERSTORE_BLOCK `filter_template`) create, re-run
unchanged despite server-generated `filters`, PATCH update, delete, delete again unchanged; smtp create, re-run
unchanged, delete; protection_group (default `subtype` GENERIC) create and delete. User create and idempotence were
validated in probe 3 (the phase 2 user step is not a reliable signal, it reports neither change nor failure).

## Fixed in 0.4.1 (branch feat/lab-validation)

PATCH `id`, `protection_rule.filter_template`, `protection_group` default `subtype`, `tls_server_name`, `docs/validation`
in `build_ignore`. Still open: document the user password policy.

## Was to fix (0.4.1)

1. PATCH body must carry the object `id` (all `ensure` PATCH paths: resource group, rule, protection group, restore plan).
2. `protection_rule`: add `filter_template`; make `priority` and `filters` optional per action; update docs.
3. `protection_group`: default `subtype` to `GENERIC`.
4. Add `tls_server_name` (done, `feat/tls-server-name`).
5. Document the user password policy.
6. Add `docs/validation` to `build_ignore` (done in `galaxy.yml`, uncommitted).

## Still to validate

Rules with an enabled asset type, rule PATCH and re-run, resource-group-assigning rule execution, actions
(`activity_action`, `alert_acknowledge`, `protection_rule_run`) and `wait` on v3 statuses, then the service-affecting
modules (`restore_plan_run`, `upgrade_package_action` precheck) only with explicit approval.
