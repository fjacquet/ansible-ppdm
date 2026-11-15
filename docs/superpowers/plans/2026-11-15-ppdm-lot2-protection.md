# Lot 2 Protection Modules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add eight modules (`protection_policy`, `protection_policy_info`, `protection_policy_assets`, `protection_policy_run`, `discovery`, `protection_rule`, `protection_rule_info`, `protection_rule_run`) plus playbooks and docs to `fjacquet.ppdm`, released as 0.2.0.

**Architecture:** Reuse the Lot 1 shared client (`plugins/module_utils/ppdm.py`), generator (`tools/generate.py` + `tools/schemas/*.yml`), doc fragment and `action_groups`. The client grows a `PATCH` update path and one `start_action` helper (POST that returns an activity, optional wait). Enum values for validation come from the committed OpenAPI via a generated `_enums.py`.

**Tech Stack:** Python 3.12+, ansible-core >= 2.20, uv, pytest with a mocked opener, ruff, ansible-lint production, ansible-test sanity/units on 3.13.

**Spec:** `docs/superpowers/specs/2026-11-15-lot2-protection-modules-design.md` (decisions section is binding: approach A for policy bodies; asset types with validation/examples/tests: VMWARE_VIRTUAL_MACHINE, FILE_SYSTEM, KUBERNETES, MICROSOFT_SQL_DATABASE; `asset_type` choices stay open for all 15).

## Global Constraints

- Branch `feat/lot2-protection`; never touch `main` directly; do not push (controller does).
- Zero runtime deps beyond ansible-core; run tools via `uv run`; unit tests under Python 3.13 (`uv run --python 3.13 pytest -q`).
- Never hand-edit generated blocks or `_routes.py`/`_enums.py`; never run `generate.py routes` in a dirty tree. Module DOCUMENTATION/ARGUMENT_SPEC come from `tools/schemas/<module>.yml` (`generate.py modules --check` must exit 0).
- Every request path, verb and body field is verified against `docs/openapi/` (policies and protections are v3 only; assignments, discoveries and rules are v2). Do not copy the community project's v2 policy calls.
- Secrets: no secret in output; `no_log` on secret options; `config`-style pass-through keys cannot collide with named options or `id`/`_links` (use `merge_config`).
- `check_mode` sends nothing for every write/action module; `wait` returns the final activity and fails unless `result.status` is OK (OK_WITH_ERRORS warns).
- Each new module is added to `meta/runtime.yml` `action_groups.ppdm` (a test enforces it).
- The "not validated against a live PPDM" disclaimer lives only in root README.md.
- Commits: explicit paths, `git commit -F <file>`, trailers `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_0148C11ULwRXo28pUmDdJZYr`.

## Review Focus

- Policy update must PATCH (no PUT exists) and must not clear fields the user did not pass.
- Policy name uniqueness unproven: more than one match must fail, never pick one (existing `find_one` rule).
- `objectives` with an unknown `type`/enum value or a missing required key fails before any request.
- Assignment of an already assigned asset, and unassign of an unassigned one, must not report a false change when the API exposes current assignments; otherwise `changed` says "request sent".
- Run/discovery on a 409 (already running) fails clearly, or is `changed: false` with `ignore_running`.
- An activity that ends COMPLETED with `result.status` FAILED must fail the task.

---

### Task 1: Client PATCH update path and `start_action` helper

**Files:**
- Modify: `plugins/module_utils/ppdm.py`
- Test: `tests/unit/module_utils/test_ppdm_ensure.py` (create if absent; follow the style of the existing ensure tests)

**Interfaces:**
- Produces: `PpdmClient.ensure(..., update_verb: str | None = None)`: when `None`, uses `PUT` if the route offers it, else `PATCH`; an explicit verb not in the route's `methods` raises `PpdmError`. `PpdmClient.start_action(path: str, body: Any, check_mode: bool, wait: bool = False, timeout: int = 600) -> dict` returning `{"changed": bool, "activity": dict | None, "response": Any}`; check mode sends nothing and returns `changed: True`; HTTP 409 raises `PpdmError` whose `.status == 409` (callers decide); with `wait`, polls `wait_activity` and raises `PpdmError` unless the final `result.status` is `OK` (a status `OK_WITH_ERRORS` returns with `"warnings": [..]` added).

- [ ] **Step 1: Write failing tests** `test_ensure_uses_patch_when_route_has_no_put`, `test_ensure_explicit_verb_not_in_route_fails`, `test_ensure_put_unchanged_for_existing_resources`, `test_start_action_check_mode_sends_nothing`, `test_start_action_wait_fails_on_failed_result`, `test_start_action_wait_warns_on_ok_with_errors`, `test_start_action_409_keeps_status`. Use a resource key with only PATCH (`protection-policies`).
- [ ] **Step 2: Run, confirm fail** (`uv run --python 3.13 pytest tests/unit/module_utils -q`).
- [ ] **Step 3: Implement** both in `ppdm.py`; `ensure` keeps the shallow merge and the Lot 1 `drop` of write-only keys, only the verb changes. Add the 409 mapping inside `start_action` (or keep `PpdmError.status`).
- [ ] **Step 4: Run all unit tests, ruff** clean; commit `feat(client): PATCH updates and start_action helper`.

### Task 2: Generated enums from the OpenAPI

**Files:**
- Modify: `tools/generate.py` (new `enums` subcommand with `--check`, like `routes`)
- Create (generated): `plugins/module_utils/_enums.py`
- Test: `tests/unit/tools/test_generate_enums.py`

**Interfaces:**
- Produces: `_enums.ENUMS: dict[str, tuple[str, ...]]` with keys `protection_policy.asset_type`, `protection_policy.purpose`, `objective.type` (union over the 15 policy variants), `discovery.level`, `protection_rule.action`, `protection_rule.inventory_source_type`, plus `OBJECTIVE_REQUIRED: tuple[str, ...]` (keys required on an objective item per the v3 schema). The generator derives them from `ProtectionPolicy` oneOf + `Discovery` + `ProtectionRule` schemas; deterministic output.

- [ ] **Step 1: Failing tests**: generator output contains the 15 asset types including the four in scope; `--check` exits 0 on committed file and 1 on a tampered copy; output is sorted/deterministic.
- [ ] **Step 2: Implement** the subcommand (reuse `_resolve`); run it once to create `_enums.py`; exclude it in ruff like `_routes.py`; add to `build_ignore` nothing (it ships).
- [ ] **Step 3: Wire `--check` into `.github/workflows/ci.yml` lint job** next to the existing generate checks; commit `feat(tools): generate enum tables from the OpenAPI`.

### Task 3: `protection_policy` and `protection_policy_info`

**Files:**
- Create: `tools/schemas/protection_policy.yml`, `tools/schemas/protection_policy_info.yml`, then generated `plugins/modules/protection_policy.py`, `plugins/modules/protection_policy_info.py`
- Modify: `meta/runtime.yml`
- Test: `tests/unit/modules/test_protection_policy.py`

**Interfaces:**
- Consumes: `PpdmClient.ensure(update_verb=None)`, `remove`, `find_one`, `merge_config`, `info_main`, `_enums.ENUMS`/`OBJECTIVE_REQUIRED`.
- Produces: `protection_policy(state=present|absent, name, asset_type (required, choices = 15 values), description, disabled, load_balance_enabled, purpose, objectives: list[dict], overrides: list[dict], config: dict)` returning `protection_policy`, `changed`, `diff`. `protection_policy_info(name, filter, id, asset_type)` returning `protection_policies`.
- Body rule: `assetType` sent from `asset_type`; objectives validated before any request (each item needs the keys in `OBJECTIVE_REQUIRED`, `type` in `ENUMS['objective.type']`) with a message naming the item index; changing `asset_type` of an existing policy fails (immutable discriminator, message says to delete and recreate).

- [ ] **Step 1: Failing tests**: create sends POST `/api/v3/protection-policies` with `assetType`; second run `changed: False`; description change sends PATCH to `/{id}`; bad objective type fails with no request; missing required objective key fails; `config` collision with `name` fails; `state=absent` deletes, check mode sends nothing; `asset_type` change on existing fails; info filter exact-name.
- [ ] **Step 2: Write both schemas** (copy `storage_system.yml`/`inventory_source.yml` structure; examples for the four in-scope asset types with a realistic `objectives` block built from the 20.3.0 v3 schema; `version_added: 0.2.0`), generate (`uv run python tools/generate.py modules`), implement `main()` bodies.
- [ ] **Step 3: Run tests, ruff, `generate.py modules --check`, sanity validate-modules in the worktree (CLAUDE.md procedure); commit `feat: protection_policy and protection_policy_info modules`.

### Task 4: `protection_policy_assets`

**Files:**
- Create: `tools/schemas/protection_policy_assets.yml`, generated `plugins/modules/protection_policy_assets.py`
- Modify: `meta/runtime.yml`
- Test: `tests/unit/modules/test_protection_policy_assets.py`

**Interfaces:**
- Consumes: `PpdmClient.request`, `find_one('protection-policies', 'name', ...)`.
- Produces: `protection_policy_assets(state=present|absent, policy (name or id), asset_ids: list[str] required)` returning `assigned`, `changed`, `diff`. Verify in the v2 spec whether current assignments can be read (assets filtered by policy id, or an assignments GET); if yes compute the delta and send only missing ids / present ids, else send all and report `changed: true` with message note "request sent". Paths `POST /api/v2/protection-policies/{id}/asset-assignments` and `.../asset-unassignments` (JSON array body, verified by the implementer).

- [ ] **Step 1: Failing tests** for: delta computed, already-assigned no request, unassign of absent no request, unknown policy fails, check mode sends nothing.
- [ ] **Step 2: Implement + schema + generate**; record in the module notes which idempotence mode applies and why.
- [ ] **Step 3: Verify all gates; commit `feat: protection_policy_assets module`.

### Task 5: `protection_policy_run` and `discovery`

**Files:**
- Create: `tools/schemas/protection_policy_run.yml`, `tools/schemas/discovery.yml`, generated modules
- Modify: `meta/runtime.yml`
- Test: `tests/unit/modules/test_protection_policy_run.py`, `tests/unit/modules/test_discovery.py`

**Interfaces:**
- Consumes: `PpdmClient.start_action`, `find_one`.
- Produces: `protection_policy_run(policy, objective_ids, asset_ids, protection_group_ids, wait, wait_timeout)` -> `POST /api/v3/protections` with `{policy:{id,objectives:[{id}...]}, source:{assetIds, protectionGroupIds}}`; at least one of `asset_ids`/`protection_group_ids` required. `discovery(level (choices from ENUMS), name, description, inventory_source (name or id), config: dict, wait, wait_timeout, ignore_running: bool=false)` -> `POST /api/v2/discoveries`; 409 fails clearly unless `ignore_running` (then `changed: false`). Both return `activity` when `wait`.

- [ ] **Step 1: Failing tests**: body shape, name->id resolution, no target fails, check mode sends nothing, wait success/FAILED/OK_WITH_ERRORS, 409 with and without `ignore_running`.
- [ ] **Step 2: Implement + schemas + generate**; required Discovery body fields verified against the v2 spec (list the final required set in the module notes).
- [ ] **Step 3: Verify gates; commit `feat: protection_policy_run and discovery modules`.

### Task 6: `protection_rule`, `protection_rule_info`, `protection_rule_run`

**Files:**
- Create: schemas for the three modules, generated modules
- Modify: `meta/runtime.yml`
- Test: `tests/unit/modules/test_protection_rule.py`, `tests/unit/modules/test_protection_rule_run.py`

**Interfaces:**
- Consumes: `ensure` (PUT, v2 rules), `remove`, `info_main`, `start_action`, `merge_config`.
- Produces: `protection_rule(state, name, description, action, inventory_source_type, priority, conditions: list[dict], condition_connector, tenant, config)` (field names verified against the `ProtectionRule` schema; choices from `ENUMS`), `protection_rule_info(name, filter, id)` returning `protection_rules`, `protection_rule_run(preview: bool=false, wait, wait_timeout)` -> `POST /api/v2/protection-rules-execution`, or with `preview: true` `POST /api/v2/protection-rules-conflicts-preview` (read-only, `changed: false`, returns `preview`).

- [ ] **Step 1: Failing tests**: create/idempotent/update via PUT, absent, check mode, invalid action fails, run sends execution, preview returns conflicts with `changed: false` and no wait.
- [ ] **Step 2: Implement + schemas + generate; Step 3: gates; commit `feat: protection_rule modules`.

### Task 7: Playbooks, docs and release prep for 0.2.0

**Files:**
- Create: `playbooks/protection/*.yml` (new playbooks: `create_vm_policy`, `create_fs_policy`, `create_k8s_policy`, `create_mssql_policy`, `assign_assets`, `run_policy`, `run_discovery`, `create_rule`, `run_rule`), update `playbooks/README.md`, `playbooks/vars/example.yml`
- Modify: root `README.md` (module list, no new disclaimer), `galaxy.yml` (version 0.2.0), `changelogs/fragments/lot2-modules.yml`, README "Lab checklist before 1.0.0" (add PATCH semantics, policy name uniqueness, assignment read mode, activity result values)
- Test: existing `tests/unit/test_playbooks.py` (it enforces FQCN, guards, header, index completeness; extend its fixtures only if a rule needs a new case)

**Interfaces:** consumes all Task 3-6 modules; playbooks follow the Lot 1 conventions (env-var connection through `module_defaults` for `group/fjacquet.ppdm.ppdm`, `no_log` on secrets, `*_confirm` assert on state-changing/destructive playbooks, `hosts: "{{ target | default('localhost') }}"`, names lowercase `_`).

- [ ] **Step 1: Write playbooks** replacing the four former "skipped" community policy/rule playbooks (see README skipped table: remove those rows, map them to the new playbooks).
- [ ] **Step 2: Run** `uv run --python 3.13 pytest -q`, ruff, generate checks, ansible-lint production on `playbooks roles` (CLAUDE.md worktree procedure), ansible-test units and sanity; build the tarball and check `ansible-doc` for the 8 modules.
- [ ] **Step 3: Commit** `docs: lot 2 playbooks, README and 0.2.0 metadata` (do not run `antsibull-changelog release`; the controller does after review).
