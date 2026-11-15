# Design: Lot 3, protection rules on the v3 API, plus configuration modules (groups, asset reads)

Date: 2026-11-15. Status: draft for approval (nothing implemented). Builds on the Lot 1 and Lot 2 designs and the
shared client (`plugins/module_utils/ppdm.py`). Target release: 0.3.0 (still a 0.x pre-release).

## Why

The three rule modules shipped in 0.2.0 call the v2 rule API (`/api/v2/protection-rules*`), deprecated since PPDM
20.2 and removed in 20.6. Their body also rests on assumptions the 20.3.0 spec does not back (flat `conditions`,
`assetAttributeName: tag`). The v3 API (`/api/v3/rules`) is the only one that survives. The author's target use of
the collection is first of all configuration, so the same release adds the missing configuration targets that
rules and policies point at: protection groups, resource groups, and read-only lookups for assets and hosts (so
playbooks stop guessing `asset_ids`).

## Verified facts (20.3.0 OpenAPI, 21201 = v2, 21202 = v3)

- **Rules v3:** `/api/v3/rules` (GET list with `page`, `pageSize`, `filter`, `orderby`; POST 201) and
  `/api/v3/rules/{id}` (GET, PATCH 200, DELETE; no PUT). `Rule` fields: `name`, `description`, `priority` (int),
  `action {name, args[]}`, `filters[]` (also a singular `filter` and a `filterTemplate`), `variant`
  (`INCLUDE_EXCLUDE_ALL_FIELDS`, `EXCLUDE_FILE_NAME_AND_PATH`, `INCLUDE_FILE_NAME_AND_PATH`, `INCLUDE_FILE_PATH`,
  `SIMPLE`, `ADVANCED`), `scopes[]` (`POLICY`, `ASSET`, `GENERAL`), `categories[]` (`TREE_VIEW`, `LIST_VIEW`).
  Read-only: `id`, `createdAt`, `updatedAt`, `lastRunAt`, `lastMigratedAt`, `status`, `uniqueHash`.
- `action.name` values: `ASSIGN_RESOURCE_GROUP`, `ASSIGN_PROTECTION_POLICY` (the two executable ones), plus
  `SELECT_FILES`, `SELECT_ASSETS_FOR_RESTORE_PLAN`, `SELECT_COPIES_FOR_RESTORE_PLAN`, `SELECT_COPIES`.
  The arg key carrying the policy id is `PROTECTION_POLICY_ID` (builder: confirm the arg item shape in the spec).
- `RuleFilter`: `objectType` (ASSET, COPY, FILE, FILEGROUP), `objectSubtype` (the 16 asset types), `type`
  (INCLUDE, EXCLUDE), `operator` (AND, OR), `conditions[]`, `displayOrder`. `RuleLogicalCondition`: `operator`
  (AND, OR) over nested `conditions[]`. `RuleRelationalCondition`: `fieldName`, `operator` (IN, NOT_IN, EQUALS,
  CONTAINS, BEGINS_WITH, ENDS_WITH, DOES_NOT_EQUAL, DOES_NOT_CONTAIN, LESS_THAN, GREATER_THAN, MATCH_REGEX, ...),
  `fieldData`.
- **Run:** `POST /api/v3/rule-execution` (202), body `RuleExecution {ruleId, actionName, objectType: ASSET,
  objectSubtypes[]}`. **Preview:** `POST /api/v3/protection-policy-rule-conflict-preview` (200, paged).
  **Extras not in scope now:** `rule-priority-change`, `rule-consistency`, `rule-deletion-by-criteria`,
  `rule-filter-translation`.
- **Groups and reads exist in v2 only (no v3 equivalent):** `/api/v2/protection-groups` (GET, POST 200) and
  `/{id}` (GET, PATCH, DELETE 204); `/api/v2/resource-groups` (GET, POST 201) and `/{id}` (GET, PATCH,
  DELETE 204); `/api/v2/assets` (GET, with `queryState`), `/api/v2/hosts` (GET). `ProtectionGroup` carries `name`,
  `description`, `type`, `subtype`, `memberAssetType`, `autoAssignToPolicy`, `protectionPolicyRef`,
  `naturalIds`, `backupStrategy` and read-only status fields; `ResourceGroup` carries `name`, `description` and
  read-only `id`, `numberOfResources`, `createdBy`. (Builder: extract the full required/read-only/enum sets from
  the spec with the generator, as in Lot 2.)

## Scope

1. **Rewrite on v3** (breaking, no v2 compatibility layer): `protection_rule`, `protection_rule_info`,
   `protection_rule_run`, and playbooks `protection/create_rule.yml`, `protection/run_rule.yml`.
2. **New modules:** `protection_group`, `protection_group_info`, `resource_group`, `resource_group_info`,
   `asset_info`, `host_info`.
3. Release as 0.3.0 with `breaking_changes` fragments, README module list and lab checklist updated, one new
   playbook per new module group where a use case exists (builder's call, keep it small).

## Modules

- **`protection_rule`** (`state: present|absent`, key `name`, exact match through the shared `find_one`): typed
  options `name`, `description`, `priority`, `action` (`name` choice, `protection_policy` name or id resolved
  through the client when the action is ASSIGN_PROTECTION_POLICY, `resource_group` likewise for
  ASSIGN_RESOURCE_GROUP), `variant`, `scopes`, `categories`, and `filters`: a list of dicts passed through after
  validation (required keys, enum values for `objectType`, `objectSubtype`, `type`, operators; nested
  logical/relational shape checked by the shared `plugins/module_utils/protection_rule.py`, rewritten). Enums come
  from `generate.py enums` (v3 spec). `config` for extra top-level keys keeps the Lot 2 collision rule. Create =
  POST, update = PATCH (the `ensure` PATCH path already exists), delete = DELETE. Read-only fields are stripped
  before comparison and before sending.
- **`protection_rule_info`**: `name`, `id`, `filter`; returns `protection_rules`.
- **`protection_rule_run`**: `rule` (name or id) runs `rule-execution`; `preview: true` calls the conflict preview
  (read-only, `changed: false`); `wait`/`wait_timeout` as in the other action modules (202 body must be checked on
  a lab: activity or not, the Lot 1/2 lesson); `check_mode` sends nothing, except that preview still POSTs
  (documented read-only, kept from Lot 2).
- **`protection_group`** (`state`, key `name`): typed common fields plus `config`; create POST, update PATCH only,
  delete DELETE; policy reference resolved by name. **`resource_group`** likewise (smaller). Both with `_info`.
- **`asset_info`, `host_info`**: read-only, `name`, `id`, `filter`, `asset_type` (assets), pagination through the
  shared `info_main`. No write modules for assets or hosts in this lot.
- All modules generated from `tools/schemas/*.yml`, listed in `meta/runtime.yml` action_groups, doc fragment and
  connection options as in Lot 1/2.

## Approaches considered

- **Rule body (A, recommended):** typed top-level options plus validated `filters` pass-through. Matches how
  `protection_policy.objectives` works, stays small, and the nested condition tree is too open to type fully.
  (B) Fully typed condition options: unmaintainable, rejected. (C) Raw `body`: no better than `api`, rejected.
- **v2 compatibility:** none. The API disappears in 20.6, the modules are 0.x pre-release, and a shim would be dead
  code that nobody can test. Accepted cost: users of the 0.2.0 rule modules must rewrite their tasks (changelog
  `breaking_changes`).
- **Delivery (decided by the author: B):** one branch and one 0.3.0 release for rules v3 plus the configuration
  modules. Cost: a larger PR and mixed risk, mitigated by task-level reviews per module.

## Constraints

Same as Lot 1/2: stdlib only, secure by default, `check_mode` correct, `validate-modules`/pep8/ruff/ansible-lint
production clean, TDD with a mocked opener, `uv` only, generated files never hand-edited (`_routes.py`: never run
`generate.py routes`), the "not validated against a live PPDM" disclaimer only in the root README, new unknowns go
to the README lab checklist, bottkars/ansible_ppdm code is not copied.

## Goals / non-goals / anti-goals

- Goal: the rule modules work against the API that remains in 20.6; configuration playbooks need no `api` calls.
- Non-goals: monitoring (activities, alerts), restore, users/roles/SMTP, rule priority change and the other
  rule helper endpoints, write support for assets and hosts, v2 compatibility.
- Anti-goal: shipping rule options that look validated but encode unverified attribute names. Unverified names
  (`fieldName` values, `args` item shape, `fieldData` shape, 202 body of rule-execution) go to the lab checklist.

## Calls made after the builder check (author to confirm)

1. **Protection groups are narrow in 20.3.0:** `type` is only ORACLE_DATA_GUARD, POWER_MAX_STORAGE_DIRECT_APPLICATION
   or STORAGE_DIRECT_APPLICATION; `memberAssetType` only ORACLE_DATABASE, POWER_MAX_BLOCK, POWERSTORE_BLOCK. Call:
   keep `protection_group` (+ `_info`) as a thin CRUD with typed `type`, `subtype`, `member_asset_type`,
   `auto_assign_to_policy`, `protection_policy` (name or id, sent as `protectionPolicyRef`), `backup_strategy`,
   `natural_ids` (membership is by `naturalIds`, not asset ids) and `config`. No `asset_info` wiring. The `README`
   says it covers storage-direct and Oracle Data Guard groups only. Shape of `protectionPolicyRef` (id only?): builder reads it from the spec; if
   unclear it goes to the lab checklist.
2. **Resource groups:** bare name/description CRUD plus `_info`. Members come only from rules (`ASSIGN_RESOURCE_GROUP`).
   No playbook unless the builder finds a real use case.
3. **Name or id resolution:** `find_one` exact match on name; no match or several matches fails with the ids listed
   (Lot 2 behaviour); a value that is not found by name is never silently passed through as an id. An explicit
   `*_id` option is accepted where the id is already known.
4. **Rule idempotency:** compare only user-supplied keys, with the `ensure` subset logic already used for policy
   `objectives`; `filters` compared as sent, in order. The server possibly re-ordering conditions goes to the lab
   checklist (a flapping `changed`).
5. **Preview body:** the spec says `{rule: Rule}`, a candidate rule. `protection_rule_run preview: true` sends the
   existing rule fetched by name or id as `{rule: <rule>}`. Run body: `{ruleId, actionName, objectType: ASSET}`;
   `object_subtypes` is an optional list, default omitted (the API decides).
6. **Breaking change:** the old option names are simply gone (the argument spec rejects unknown options with
   Ansible's standard message); the changelog `breaking_changes` lists the mapping old to new.
7. **Routes:** `_routes.py` already contains `rules`, `rule-execution`, the preview, groups, assets and hosts
   (checked). The builder adds nothing by hand and never runs `generate.py routes`.
8. **Status codes:** protection group POST 200, resource group POST 201 and rules POST 201, DELETE 204: the builder
   checks `ensure`/`remove` accept 200/201/204 and adds tests, nothing more.

## Left to the builder

Exact option names and validation messages, whether `protection_rule` accepts a convenience `filters` shorthand
(no, unless the spec makes the tree trivial), fixtures, how the playbooks look, the shape of `args` and
`fieldData` (read the spec schemas), and the decomposition into tasks.
