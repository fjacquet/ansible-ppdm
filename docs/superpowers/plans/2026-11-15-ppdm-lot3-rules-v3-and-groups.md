# Lot 3: protection rules on v3, groups, asset and host reads Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the three rule modules from the removed-in-20.6 v2 API to `/api/v3/rules`, and add the configuration modules `protection_group`, `resource_group`, `asset_info`, `host_info` (+ group `_info`), released as 0.3.0.

**Architecture:** Same pattern as Lot 2: `tools/schemas/<module>.yml` is the single source of DOCUMENTATION and argument_spec (`uv run python tools/generate.py modules`), module bodies sit under the `# END GENERATED` marker and use the shared `PpdmClient` (`ensure`, `remove`, `find_one`, `start_action`, `await_activity`, `info_main`). Enums come from `generate.py enums` out of the OpenAPI files. `_routes.py` already holds `rules`, `rule-execution`, `protection-policy-rule-conflict-preview`, `protection-groups`, `resource-groups`, `assets`, `hosts`: never hand-edit it, never run `generate.py routes`.

**Tech Stack:** Python 3.13 (ansible-core 2.20+, stdlib only), pytest with the mocked opener in `tests/unit/helpers.py` (`FakeOpener`, `Resp`, `listing`, `methods`, `run_module`), ruff, ansible-test, ansible-lint, antsibull-changelog, uv.

**Spec:** `docs/superpowers/specs/2026-11-15-lot3-rules-v3-and-groups-design.md` (read it first, including "Calls made after the builder check").

## Global Constraints

- Run everything through `uv run` (`uv run --python 3.13 pytest -q`); zero runtime dependency beyond ansible-core; `requires_ansible >=2.20.0`.
- Branch `feat/lot3-rules-v3-groups`. Commits: `git commit -F <file>` (message file under `/private/tmp/claude-501/-Users-fjacquet-Projects-ansible-ppdm/83d0e71b-878a-49b1-83b3-483968f10517/scratchpad/`), explicit-path `git add`, trailers `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_0148C11ULwRXo28pUmDdJZYr`. Never commit under `.superpowers/`. Never push.
- Modules have no `ppdm_` prefix; every module is added to `meta/runtime.yml` `action_groups.ppdm` (a test enforces it).
- Generated blocks (`# BEGIN GENERATED` / `# END GENERATED`) and `_enums.py` are never hand-edited: edit `tools/schemas/*.yml` or `tools/generate.py`, then run `generate.py modules` / `generate.py enums`.
- The "not validated against a live PPDM" disclaimer lives only in the root `README.md`; module docs carry only the "Unofficial collection, not affiliated with Dell. Written against the PowerProtect Data Manager 20.3.0 REST API." note. Unknowns go to the README "Lab checklist before 1.0.0".
- Ansible modules: DOCUMENTATION `version_added: 0.3.0`; check_mode correct; no secret in output; `validate-modules`, pep8, ruff, ansible-lint (production profile) clean.
- Updates of v3 rules and groups use PATCH (`ensure` picks PATCH when the route has no PUT). bottkars/ansible_ppdm code is not copied.
- TDD: write the failing test, see it fail, implement, see it pass, then commit.

## Review Focus

- A `filters` value that is not a list of dicts, a dict with a bad `objectType`/`objectSubtype`/`type`/`operator`, or a nested `conditions` item that is neither a logical nor a relational condition must raise `PpdmError` before any request (Task 1 tests, Task 2 test).
- A policy/resource-group name that matches nothing or several objects must fail with a message (ids listed, scrubbed) and send no write; the value is never passed through as an id (Task 2, 5, 6).
- `check_mode`: no write request for any module; `protection_rule_run preview` POSTs but is read-only and `changed` is false (Tasks 2, 3, 5, 6).
- `asset_info`/`host_info` outputs can carry credentials or tokens in nested fields: confirm masking or document it (Task 7).
- Old v2 option names (`conditions`, `condition_connector`, `policy`, `inventory_source_type`, `tenant`, `rules` on the run module) are rejected by the argument spec and no request is sent (Task 2, 3).

---

### Task 1: v3 rule enums and shared validation

**Files:**

- Modify: `tools/generate.py` (`build_enums`), `plugins/module_utils/_enums.py` (generated), `plugins/module_utils/protection_rule.py`
- Test: `tests/unit/tools/test_generate_enums.py`, create `tests/unit/test_protection_rule_utils.py`

**Interfaces:**

- Produces `ENUMS` keys (sorted tuples read from the v3 spec schemas `Rule`, `RuleAction`, `RuleFilter`, `RuleLogicalCondition`, `RuleRelationalCondition`, `RuleExecution`, `ProtectionGroup` (v2)): `rule.action_name`, `rule.variant`, `rule.scope`, `rule.category`, `rule_filter.object_type`, `rule_filter.object_subtype`, `rule_filter.type`, `rule_filter.operator`, `rule_condition.operator` (relational), `rule_condition.logical_operator`, `rule_run.action_name`, `rule_run.object_subtype`, `protection_group.type`, `protection_group.subtype`, `protection_group.member_asset_type`, `protection_group.backup_strategy`. The old keys `protection_rule.*`, `condition.operator`, `protection_rule_run.*` are removed with their v2 lookups.
- Produces in `protection_rule.py`: `validate_filters(filters: list | None) -> None` (raises `PpdmError`), `validate_rule_body(rule: dict) -> None` (checks `action.name`, `variant`, `scopes`, `categories`, then `validate_filters(rule.get("filters"))`). Remove `validate_conditions`.

- [ ] **Step 1: Failing tests.** `test_generate_enums.py`: assert the new keys exist with the spec values (e.g. `rule.action_name` contains `ASSIGN_PROTECTION_POLICY` and `ASSIGN_RESOURCE_GROUP`; `rule_condition.operator` contains `MATCH_REGEX`; `protection_group.type` equals `("ORACLE_DATA_GUARD","POWER_MAX_STORAGE_DIRECT_APPLICATION","STORAGE_DIRECT_APPLICATION")`) and the old keys are gone. `test_protection_rule_utils.py`: `validate_filters` accepts a filter `{objectType: ASSET, objectSubtype: VMWARE_VIRTUAL_MACHINE, type: INCLUDE, operator: AND, conditions: [{operator: AND, conditions: [{fieldName: x, operator: EQUALS, fieldData: {...}}]}]}`; raises `PpdmError` for: non-list, item not dict, bad `objectType`, bad `type`, `conditions` not a list, a condition that is not a dict, relational condition with an operator outside the enum, nesting deeper than 8 levels. `validate_rule_body` raises for an unknown `action.name`.
- [ ] **Step 2: Run, expect FAIL** (`uv run --python 3.13 pytest tests/unit/tools/test_generate_enums.py tests/unit/test_protection_rule_utils.py -q`).
- [ ] **Step 3: Implement** `build_enums` changes and `uv run python tools/generate.py enums`; implement the validators (a condition with a `conditions` key is logical, one with `fieldName` is relational, anything else is an error; keep unknown extra keys such as `displayOrder`/`fieldData` untouched; shape of `fieldData` is not validated, see spec `RuleFilterFieldData` and record the shape in a test fixture).
- [ ] **Step 4: Run** the two test files plus `generate.py enums --check`: PASS (the rule module tests still import `validate_conditions` until Task 2, so run the full suite only after Task 2; note it in the report).
- [ ] **Step 5: Commit** (`feat: v3 rule enums and filter validation`).

### Task 2: `protection_rule` and `protection_rule_info` on v3

**Files:**

- Modify: `tools/schemas/protection_rule.yml`, `tools/schemas/protection_rule_info.yml`, generated parts of `plugins/modules/protection_rule.py` and `protection_rule_info.py`, rewrite bodies
- Test: rewrite `tests/unit/modules/test_protection_rule.py`, update `tests/unit/modules/test_info_modules.py` (`protection_rule_info` path `/api/v3/rules`)

**Interfaces:**

- Consumes: `validate_filters`, `ENUMS["rule.*"]` (Task 1); `PpdmClient.ensure/remove/find_one`, `merge_config`, `info_main`.
- Options of `protection_rule` (all v2 options removed): `state` (present|absent, default present), `name` (required), `description`, `priority` (int), `action` (str, choices `rule.action_name`), `protection_policy` / `protection_policy_id`, `resource_group` / `resource_group_id` (each pair mutually exclusive; the name forms are resolved with `find_one("protection-policies"|"resource-groups","name",v)`, no match fails `protection policy X not found`), `variant`, `scopes` (list, choices), `categories` (list, choices), `filters` (list of dict), `config` (dict, same collision rule: fails on `id`, `_links` and on any key a named option sets).
- Body sent: `{name, description, priority, action: {name, args: [{name: "PROTECTION_POLICY_ID"|"RESOURCE_GROUP_ID", values: [id]}]}, variant, scopes, categories, filters}`; omitted when the option is None. `protection_policy*` is only valid with `action=ASSIGN_PROTECTION_POLICY`, `resource_group*` only with `ASSIGN_RESOURCE_GROUP`, else a `PpdmError` before any request. Read-only stripped and ignored in comparison: `createdAt, updatedAt, lastRunAt, lastMigratedAt, status, uniqueHash`. `filters` and `action.args` compared as in `ensure(subset_keys=...)` (read `ppdm.py` `is_subset`/`ensure` to choose the keys; filters compared in order). Resource `"rules"`; returns `protection_rule`, `diff`.
- `protection_rule_info`: resource `rules`, result key `protection_rules`, options `name`, `filter`, `id`.

- [ ] **Step 1: Failing tests** in `test_protection_rule.py` (keep the file's `run`/`body` helpers): create with policy name (GETs for policy then rule list, POST `/api/v3/rules` returning 201, exact body above), create with resource group, idempotent no-op when the server echoes extra fields (`uniqueHash`, `status`), update sends PATCH `/api/v3/rules/<id>` only on a real difference, `state=absent` DELETE `/api/v3/rules/<id>` and no-op when missing, check_mode sends no POST/PATCH/DELETE, unknown policy name fails with no write, ambiguous name (two rules) fails listing ids, `protection_policy` with `action=ASSIGN_RESOURCE_GROUP` fails, invalid filters fail before any request, `config` collision fails, and an old v2 option (`conditions=[...]`) is rejected by the argument spec.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Rewrite** both schemas (docs in English, examples with a v3 filter tree; notes: Unofficial line only; document that `filters` replaces the whole list and is compared in order), regenerate (`uv run python tools/generate.py modules`), write the module bodies on the Lot 2 pattern.
- [ ] **Step 4: Run** `uv run --python 3.13 pytest -q`: PASS (the full suite now works; `protection_rule_run` tests still reference v2 and are rewritten in Task 3, so skip them with `--deselect` for this task and say so in the report), `generate.py modules --check`, ruff check/format.
- [ ] **Step 5: Commit** (`feat!: move protection_rule and protection_rule_info to the v3 rules API`).

### Task 3: `protection_rule_run` on v3

**Files:**

- Modify: `tools/schemas/protection_rule_run.yml`, generated part and body of `plugins/modules/protection_rule_run.py`
- Test: rewrite `tests/unit/modules/test_protection_rule_run.py`

**Interfaces:**

- Consumes: `validate_rule_body`, `ENUMS["rule_run.*"]`, `client.start_action(path, body, check_mode) -> {"changed", "response"}`, `client.await_activity(activity_id, timeout) -> {"activity", ["warnings"]}`, and the `wait` handling of `plugins/modules/protection_policy_run.py` (mirror it: with `wait` an answer without `activityId` fails, without `wait` only a warning).
- Options (v2 `rules`, `inventory_source_type`, `preview_action` removed): `rule` (str, required: name or id, found by name first then id as the old `find_rule`, resource `rules`), `action_name` (choices `rule_run.action_name`, default: the rule's `action.name`, fail if that is not executable), `object_subtypes` (list, choices; default omitted), `preview` (bool, default false), `wait` (bool), `wait_timeout` (int).
- Run: `POST /api/v3/rule-execution` body `{"ruleId": id, "actionName": ..., "objectType": "ASSET"[, "objectSubtypes": [...]]}`. Preview: `POST /api/v3/protection-policy-rule-conflict-preview` body `{"rule": <the existing rule>}`, always sent (also in check mode, read-only), `changed=False`, returns `preview`. `wait`/`wait_timeout` with `preview` is an error.

- [ ] **Step 1: Failing tests:** run by name and by id (exact body), `object_subtypes` forwarded, default action taken from the rule, non-executable action fails, unknown rule fails with no POST, check_mode sends no `rule-execution` POST, preview body and `changed False` and POST in check mode, `wait` with activity polls (use the `FakeOpener` activity fixtures of `test_protection_policy_run.py`), `wait` without `activityId` fails, v2 options rejected.
- [ ] **Step 2: Run, expect FAIL.** Step 3: rewrite schema, `generate.py modules`, body. Step 4: full `uv run --python 3.13 pytest -q` PASS, ruff, `generate.py modules --check`.
- [ ] **Step 5: Commit** (`feat!: move protection_rule_run to the v3 rule execution API`).

### Task 4: rule playbooks and docs

**Files:**

- Modify: `playbooks/protection/create_rule.yml`, `run_rule.yml`, `get_rules.yml`, `playbooks/kubernetes/add_policy_and_rule.yml` (only the part that calls the v2 rule API: port it to `protection_rule` or to a v3 `api` body, builder's call), `playbooks/vars/example.yml`, `playbooks/README.md` (rows, "Unverified details", remove the v2-deprecation lines), root `README.md` (module list unchanged here; remove the two v2 lab-checklist bullets about `tag`/flat conditions and the v2 deprecation, add bullets in Task 8)
- Test: `tests/unit/test_playbooks.py` (existing guards must stay green; add a guard that no playbook calls `/api/v2/protection-rules` or `/api/v2/rules`)

**Interfaces:** Consumes the Task 2/3 option names. `rule_run_confirm` guard stays. `create_rule.yml` builds a v3 filter tree from variables (a `rule_filters` list var in `vars/example.yml`) instead of the v2 `rule_tag`.

- [ ] **Step 1: Failing guard test** (no v2 rule path in any playbook), see it fail on the current playbooks. Step 2: port the playbooks and README rows (status column semantics are enforced by `_readme_rows`). Step 3: `uv run --python 3.13 pytest tests/unit/test_playbooks.py -q` PASS, ansible-lint on playbooks (see Task 8 commands). Step 4: Commit (`feat!: port the rule playbooks to the v3 rule modules`).

### Task 5: `resource_group` and `resource_group_info`

**Files:**

- Create: `tools/schemas/resource_group.yml`, `tools/schemas/resource_group_info.yml`, `plugins/modules/resource_group.py`, `plugins/modules/resource_group_info.py`, `tests/unit/modules/test_resource_group.py`
- Modify: `meta/runtime.yml`, `tests/unit/modules/test_info_modules.py` (add `resource_group_info`, `/api/v2/resource-groups`, `resource_groups`)

**Interfaces:** resource `resource-groups`, key `name`, `kind: ensure`. Options: `state`, `name` (required), `description`, `config`. Read-only: `createdAt, createdBy, id, numberOfResources, updatedAt` (strip before compare/send). Create POST (201), update PATCH, delete DELETE (204). Returns `resource_group`, `diff`. Info returns `resource_groups` with `name`, `filter`, `id`. Members come only from rules (note in docs).

- [ ] **Step 1: Failing tests:** create (POST body exact), idempotent no-op with echoed read-only fields, update PATCH, absent DELETE 204, check_mode no write, ambiguous name fails, `config` collision. Step 2 FAIL. Step 3: schemas, `generate.py modules`, bodies, runtime.yml. Step 4: full pytest PASS, ruff, `generate.py modules --check`. Step 5: Commit (`feat: add resource_group and resource_group_info modules`).

### Task 6: `protection_group` and `protection_group_info`

**Files:** same layout as Task 5 with `protection_group*`, `tests/unit/modules/test_protection_group.py`, `meta/runtime.yml`, `tests/unit/modules/test_info_modules.py`.

**Interfaces:** resource `protection-groups` (v2, POST 200, PATCH, DELETE 204). Options: `state`, `name` (required), `description`, `type` (choices `protection_group.type`), `subtype` (choices), `member_asset_type` (choices), `backup_strategy` (choices), `auto_assign_to_policy` (bool), `protection_policy` / `protection_policy_id` (mutually exclusive; name resolved with `find_one("protection-policies","name",v)`, sent as `protectionPolicyRef: {id: <id>}`; read the `protectionPolicyRef` schema in `docs/openapi/21201-20.3.0.json` and use its real shape, and if the spec leaves it unclear put the doubt in the README lab checklist), `natural_ids` (list of str), `config` (collision rule). Read-only from the `ProtectionGroup` schema (`id, createdAt, updatedAt, lastAvailableCopyTime, lastDiscoveryStatus, protectionStatus` and any other readOnly property: derive them from the spec) are stripped. Docs state that 20.3.0 only knows Oracle Data Guard and Storage Direct groups.

- [ ] **Step 1: Failing tests:** create with policy name (body exact, `protectionPolicyRef`), idempotent no-op, update PATCH only on a diff, delete, check_mode no write, unknown/ambiguous policy fails with no write, bad `type` rejected by the argument spec. Steps 2-5 as Task 5. Commit (`feat: add protection_group and protection_group_info modules`).

### Task 7: `asset_info` and `host_info`

**Files:** Create `tools/schemas/asset_info.yml`, `host_info.yml`, `plugins/modules/asset_info.py`, `host_info.py`; modify `meta/runtime.yml`, `tests/unit/modules/test_info_modules.py`.

**Interfaces:** `info_main("assets", "assets", ARGUMENT_SPEC, secret_fields=<see below>, extra_eq={"asset_type": "type"})` and `info_main("hosts", "hosts", ARGUMENT_SPEC, ...)` with options `name`, `id`, `filter`, plus `asset_type` (choices read from the `Asset.type` enum of `docs/openapi/21201-20.3.0.json`, add them to `generate.py enums` as `asset.type` if the spec has an enum, otherwise a plain str) on `asset_info`, and `type` (str, exact match on `type`) on `host_info` via `extra_eq`. Read `info_main`'s `secret_fields` handling and the `Asset`/`Host` schemas: list every nested field that can hold a credential/token/password (e.g. `credentials`) and mask it in the returned objects, with a test; if none exist say so in the docs and the report. Results are all pages (`MAX_ITEMS` cap as `list_all`).

- [ ] **Step 1: Failing tests** in `test_info_modules.py` (the parametrised `MODULES` list gains both) plus: `asset_type` filter ANDed into the server filter and re-checked client-side, masking of the secret fields found. Steps 2-5 as Task 5. Commit (`feat: add asset_info and host_info modules`).

### Task 8: release preparation

**Files:** `README.md` (module table: add the six new modules and `resource_group_info`, `protection_group_info`; lab checklist bullets below), `meta/runtime.yml` (verify), `changelogs/fragments/lot3-rules-v3.yml`, `galaxy.yml` (`version: 0.3.0`), `changelogs/changelog.yaml` + `CHANGELOG.rst` (via antsibull-changelog), `playbooks/README.md`.

- [ ] **Step 1:** README: replace the v2-deprecation and `tag`/flat-conditions checklist bullets with: `filters` `fieldName`/`fieldData` shapes accepted by PPDM (a minimal tag/name condition per asset type); `args` item shape `{name, values}` for `PROTECTION_POLICY_ID` / `RESOURCE_GROUP_ID`; the 202 body of `rule-execution` (activity or not) and the preview semantics; whether PPDM re-orders `filters` conditions (a flapping `changed`); `protectionPolicyRef` shape of protection groups; `PATCH` of `rules` replaces whole lists. No new disclaimer sentence.
- [ ] **Step 2:** Changelog fragment `changelogs/fragments/lot3-rules-v3.yml` with `breaking_changes` (the three rule modules moved to the v3 API, old option names `conditions`, `condition_connector`, `inventory_source_type`, `tenant`, `policy`, `rules`, `preview_action` are gone with the mapping to `filters`, `action` + `protection_policy`, `object_subtypes`, `rule`; `protection.create_rule`/`run_rule` variables changed) and `minor_changes`/release summary for the new modules. Run `uv run antsibull-changelog lint` then `uv run antsibull-changelog release --version 0.3.0`, bump `galaxy.yml`.
- [ ] **Step 3: Gates:** `uv run ruff check . && uv run ruff format --check .`; `uv run --python 3.13 pytest -q`; `uv run python tools/generate.py modules --check` and `enums --check`; refresh the worktree (`git -C ~/.cache/ppdm-ac/ansible_collections/fjacquet/ppdm checkout --detach <sha>`), then there `uv run --project ~/Projects/ansible-ppdm ansible-test sanity --python 3.13 validate-modules pep8` and `ansible-test units --python 3.13`; `ANSIBLE_COLLECTIONS_PATH=~/.cache/ppdm-ac uv run ansible-lint --profile production`; `gitleaks detect`; build check (`uv run ansible-galaxy collection build --force --output-path <scratch>`: tarball has no `docs/superpowers`, `docs/openapi`, `tools`, `.superpowers`). All must pass; report each result.
- [ ] **Step 4: Commit** (`chore: release 0.3.0 changelog and README`). Do not push, merge or tag: the controller asks the author first.
