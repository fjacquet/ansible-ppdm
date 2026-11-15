# Design: Lot 2, `protection_policy`, `protection_run` and `discovery` modules

Date: 2026-11-15. Status: draft for approval (nothing implemented). Builds on the Lot 1 design
(`2026-11-15-fjacquet-ppdm-collection-design.md`) and its shared client (`plugins/module_utils/ppdm.py`).

## Why

Protection policies are the heart of PPDM automation: create a policy, assign assets, run it now, and discover
new assets. Today users reach them only through `fjacquet.ppdm.api` with hand-built JSON. Dedicated modules give
idempotent policy management, a clean "run now" action and a discovery trigger, with documented options and
`check_mode`. The community project this collection learned from calls the v2 policy endpoints that no longer
exist for policies in 20.3.0; the v3 API is the only one, so correctness here is a differentiator.

## Verified facts (20.3.0 OpenAPI, files 21201 = v2, 21202 = v3)

- **Policies:** `/api/v3/protection-policies` (GET list with `page`, `pageSize`, `filter`, `orderby`; POST create)
  and `/api/v3/protection-policies/{id}` (GET, PATCH, DELETE; no PUT). The body is the oneOf `ProtectionPolicy`
  discriminated by `assetType`, 15 variants: VMWARE_VIRTUAL_MACHINE, FILE_SYSTEM, KUBERNETES, MICROSOFT_SQL_DATABASE,
  MICROSOFT_EXCHANGE_DATABASE, ORACLE_DATABASE, SAP_HANA_DATABASE, NAS_SHARE, GENERIC_APPLICATION_ASSET,
  HYPERV_VIRTUAL_MACHINE, NUTANIX_VIRTUAL_MACHINE, NATIVEEDGE_VIRTUAL_MACHINE, CLOUD_DIRECTOR_VAPP,
  POWER_MAX_BLOCK, POWERSTORE_BLOCK.
  Common fields (`ProtectionPolicyCommon`, only `assetType` required): `name`, `description`, `disabled`,
  `loadBalanceEnabled`, `purpose` (EXCLUSION | SELF_SERVICE | CENTRALIZED), `overrides[]`, read-only `id`,
  `createdAt`, `updatedAt`, `disablementInfo`. Every variant adds `objectives[]` whose items carry `type`
  (BACKUP, SNAPSHOT, REPLICATION, CLOUD_TIER, CLOUD_DR, VAULT, ARCHIVE...), `target` (`storageTargetId`,
  `storageContainerId`, `preferredInterfaceId`, `cloudUnit`), `operations[]` (schedules), `retentions[]`, a
  type-specific `config` and `options`.
- **Assignment:** `POST /api/v2/protection-policies/{id}/asset-assignments` and `.../asset-unassignments`: the body
  is a JSON array (the `api` module accepts list bodies since Q3).
- **Run now:** `POST /api/v3/protections` (202), body `ProtectionNowRequest`: `policy{id, objectives[]}` and
  `source{assetIds[], protectionGroupIds[]}`. (The v2 `/protection-policies/{id}/protections` path used by the
  community project does not exist in 20.3.0.)
- **Discovery:** `POST /api/v2/discoveries` (202, 409 when one is running), body `Discovery`: required `start`,
  `level` (ManagementInterface, INVENTORY_SOURCE, Device, HOST, HOSTFULL, NE...), `name`, `description`,
  `extendedDiscoveryData`, `schedule`, and the target ids; `GET /api/v2/discoveries` lists them.
- **Asynchrony:** `202` responses carry an activity; success/failure is in the activity `result.status`, and the only
  terminal `state` is COMPLETED (Lot 1 finding). The client already has `wait_activity`.

## Modules

1. **`protection_policy`** (`state: present|absent`, key `name`; assumed unique, verify on a lab).
   - Idempotent create/update through `ensure` (v3 route). PATCH is the only update verb: the module sends the
     merged object with `PATCH` (the client needs a `PATCH` update path next to `PUT`; routes table says which verbs
     exist per resource).
   - Options: `name`, `asset_type` (required, choices = the 15 discriminator values), `description`, `disabled`,
     `load_balance_enabled`, `purpose`, `objectives` (list of dicts, passed through after validation of required keys
     and enum values taken from the spec), `overrides` (list), `config` (extra top-level keys, same collision rule as
     `inventory_source`: cannot override named options or `id`/`_links`).
   - Returns `protection_policy` (object), `changed`, `diff`.
2. **`protection_policy_info`**: `name`, `filter`, `id`, `asset_type`; returns `protection_policies`.
3. **`protection_policy_assets`** (`state: present|absent`): assign/unassign assets by id to a policy (the array
   bodies). Idempotence by reading the current assignments when the spec exposes them (verify); otherwise report
   `changed` honestly as "request sent".
4. **`protection_policy_run`** (action module, no `state`): runs a policy now (`POST /api/v3/protections`): options
   `policy` (name or id), `objective_ids` (optional), `asset_ids`, `protection_group_ids`, `wait`, `wait_timeout`.
   Always `changed: true` when sent; `check_mode` sends nothing; with `wait` returns the final activity and fails
   unless `result.status` is OK (OK_WITH_ERRORS warns). Resolves the policy name to an id with the shared client.
5. **`discovery`** (action module): starts a discovery (`POST /api/v2/discoveries`): options `level`, `name`,
   `description`, `inventory_source` (name or id, resolved through the shared client), `config` (pass-through for
   `extendedDiscoveryData`/`schedule`), `wait`/`wait_timeout`. A 409 (already running) fails with a clear message
   unless `ignore_running: true` (then `changed: false`).
6. **`protection_rule`** (`state: present|absent`, key `name`): automatic assignment rules,
   `/api/v2/protection-rules` (GET list, POST) and `/api/v2/protection-rules/{id}` (GET, PUT, DELETE); body fields
   from the `ProtectionRule` schema (`name`, `description`, `action`, `inventorySourceType`, `priority`,
   `conditions`/`rules`, `conditionConnector`/`logicalOperator`, `tenant`). Same options pattern as the policy
   (typed common fields + validated pass-through for conditions, `config` extras). `protection_rule_info` for reads,
   and `protection_rule_run` for `POST /api/v2/protection-rules-execution` (action, `wait`) plus an optional
   conflicts preview (`POST /api/v2/protection-rules-conflicts-preview`) exposed as `preview: true` on the run
   module (read-only, `changed: false`).
7. Shared pieces: reuse `PpdmClient.ensure/find_one/wait_activity`, the doc fragment and action group; no new
   dependency. All modules generated-doc via `tools/schemas`, listed in `meta/runtime.yml` action_groups.

## Approaches considered for the policy body

- **A. Typed options for common fields + `objectives` as a validated pass-through (recommended).** Small, honest,
  works for all 15 asset types, validated against enums extracted by the generator from the spec (so docs and
  validation cannot drift). Downside: users write the objectives structure themselves (examples per asset type
  in the docs help).
- **B. Fully typed options per asset type (15 variants x objectives x operations x retentions).** Rich but huge
  (hundreds of options), unmaintainable by hand, and the generator would have to emit nested suboptions it does not
  support. Rejected for v1.
- **C. A pure pass-through `body` (like `api`).** Cheapest, but no validation and no better than `api`: rejected.
- Hybrid growth path: start with A and add typed convenience options (e.g. `retention_days`, `schedule`) for the
  two most used asset types (VMWARE_VIRTUAL_MACHINE, FILE_SYSTEM) only when a client needs them.

## Constraints

- Same rules as Lot 1: secure by default, no secrets in output, `check_mode` correct, `validate-modules`/pep8/ruff/
  ansible-lint production clean, TDD with mocked opener, pre-release `0.x` until a live PPDM validates PATCH
  semantics, name uniqueness and activity results.
- Generator work needed first: nested enums extraction for `objectives` validation (read from the v3 spec), and
  `PATCH` as an update verb in the client/route table.

## Decided by the author (2026-11-15)

1. Policy body: approach A (typed common fields + validated `objectives` pass-through).
2. Asset types with validation, examples and tests in v1: VMWARE_VIRTUAL_MACHINE, FILE_SYSTEM, KUBERNETES,
   MICROSOFT_SQL_DATABASE; the `asset_type` choices stay open for all 15.
3. Scope: everything above is in this lot, including `protection_policy_assets` AND `protection_rule`
   (+ `protection_rule_info`, `protection_rule_run`).
4. Names (controller's reading of "protection_policy et discovery": the run module keeps the `protection_policy`
   prefix): `protection_policy`, `protection_policy_info`, `protection_policy_assets`, `protection_policy_run`,
   `discovery`. Rule modules follow the same prefix style (`protection_rule`, `protection_rule_info`,
   `protection_rule_run`). Renaming before implementation is cheap if this reading is wrong.
5. Timing: after the `0.1.0` release of Lot 1, on a NEW branch (not `feat/lot1-foundation`).

## Left to the builder
Exact option names and validation messages, the number of examples per asset type, whether the client grows a
generic `update_verb` parameter or per-resource verb table for PATCH, and the test fixtures.
