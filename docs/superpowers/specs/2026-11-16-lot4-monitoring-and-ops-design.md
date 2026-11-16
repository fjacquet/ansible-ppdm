# Design: Lot 4, example playbooks, monitoring, configuration and ops modules

Date: 2026-11-16. Status: approved by the author ("Ok", scope as below, "Everything built", one branch, one PR).
Builds on the Lot 1 to 3 designs and the shared client (`plugins/module_utils/ppdm.py`). Target release: 0.4.0
(still a 0.x pre-release).

## Why

Lot 3 left example playbooks for the new modules undone and the original "ops" lot (activities, alerts, copies,
smtp, users, restore, upgrade) unbuilt. The author's use is configuration first, then monitoring, then ops. The
generic `api` module covers all of it today, so this lot adds curated, idempotent, check-mode-correct modules where
the API shape is stable, and says plainly where it does not.

## Scope

1. **Example playbooks** for the Lot 3 modules: `protection.create_resource_group` (resource group plus an
   assigning rule), `protection.create_protection_group` (storage-direct and Oracle Data Guard only),
   `assets.find_assets` (read-only lookup with `asset_info` and `host_info`).
2. **Monitoring, read-only:** `activity_info` (`/api/v3/activities`, by id or filter, optional steps),
   `alert_info` (`/api/v2/alerts`), `copy_info` (by copy id `/api/v3/copies/{id}`, by asset
   `/api/v2/assets/{id}/copies`, or latest copies `/api/v2/latest-copies`).
3. **Small action modules:** `activity_action` (cancel or retry an activity, `wait`), `alert_acknowledge`
   (acknowledge one or several alerts).
4. **Configuration:** `smtp` + `smtp_info` (`/api/v2/smtp`, with a test option on `/api/v2/smtp/test`), `user` +
   `user_info` (`/api/v2/users`), `role_info` (`/api/v2/roles`). User passwords are `no_log` and never appear in
   diff or return values.
5. **Ops, written without a live lab:** `restore_plan`, `restore_plan_info`, `restore_plan_run`
   (`/api/v2/restore-plans`, `/{id}/execute`); `upgrade_package_info` and `upgrade_package_action` (precheck,
   upgrade, revert on `/api/v2/upgrade-packages/{id}/...`), the latter requiring an explicit `confirm: true`.
6. Release 0.4.0: changelog fragments, README module table and lab checklist, `galaxy.yml`.

## Non-goals

Direct restore through `restored-copies` (the body differs for each of the 16 asset types; `api` stays the answer),
DR server backup, NAS utilities, cloud tiering, SNMP users, v2 compatibility shims.

## Approaches

Same hybrid approach as Lots 1 to 3: curated modules on the shared client, schema in `tools/schemas/*.yml` as the
single source of DOCUMENTATION and argument_spec, enums generated from the OpenAPI specs. Considered and rejected:
modules per asset-type restore (unmaintainable without a lab), a generic "action" module (that is `api`).

## Constraints

Same as Lots 1 to 3: stdlib only, secure by default, `check_mode` correct, `validate-modules`/pep8/pylint
(full `ansible-test sanity`, not a subset)/ruff/ansible-lint production clean, TDD with a mocked opener, `uv` only,
generated files never hand-edited (`_routes.py`: never run `generate.py routes` by hand-merging; check what is
already there), the "not validated against a live PPDM" disclaimer only in the root README, every unverified body
shape goes to the README lab checklist, `no_log` for secrets, every module in `meta/runtime.yml` action_groups.
Destructive or service-affecting actions (`upgrade_package_action`, `restore_plan_run`, activity cancel) refuse to
act without an explicit confirmation option, and their playbooks follow the `*_confirm` convention enforced by
`tests/unit/test_playbooks.py`.

## Left to the builder

Exact option names and validation, which routes `_routes.py` already holds, fixtures, task decomposition, the
spec-derived required/read-only/enum sets (extract them with the generator as in Lots 2 and 3), and whether
`restore_plan` can reuse `ensure` as is (the plan must check the verb: v2 restore plans update with PATCH).
