# Lot 4: monitoring, configuration, ops modules and example playbooks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the read-only monitoring modules (`activity_info`, `alert_info`, `copy_info`), the small action modules (`activity_action`, `alert_acknowledge`), the configuration modules (`smtp`, `smtp_info`, `user`, `user_info`, `role_info`), the ops modules written without a lab (`restore_plan`, `restore_plan_info`, `restore_plan_run`, `upgrade_package_info`, `upgrade_package_action`), three example playbooks for the Lot 3 modules, and release 0.4.0.

**Architecture:** The same pattern as Lots 2 and 3. `tools/schemas/<module>.yml` is the single source of DOCUMENTATION and argument_spec (`uv run python tools/generate.py modules`). Module bodies sit under `# END GENERATED` and use the shared `PpdmClient` (`ensure`, `remove`, `find_one`, `list_all`, `get_all`, `request`, `start_action`, `await_activity`, `wait_activity`, `info_main`). Choices come from `generate.py enums`.

`_routes.py` already holds `activities` (v3, GET only), `alerts` (v2, GET/PATCH), `latest-copies` (v2, GET, no item), `smtp` (v2, GET/POST/PUT/DELETE), `users` (v2, GET/POST/PUT/DELETE), `roles` (v2, GET), `restore-plans` (v2, GET/POST/PATCH/DELETE), `upgrade-packages` (v2, GET/POST/PUT/DELETE) and `assets`. None of them lists any `readonly` key.

`copies` is **not** in `_routes.py`, and regenerating would not add it: neither spec has a `/api/vN/copies` collection base, and `build_routes` skips such slugs. Sub-paths (`/cancel`, `/retry`, `/steps`, `/acknowledgements`, `/test`, `/execute`, `/precheck`, `/revert`, `/assets/{id}/copies`, `/copies/{id}`) are never routes either. Modules build them as literal strings with `quote_id`, as `discovery` and `protection_policy_assets` do. Never hand-edit `_routes.py`, and never run `generate.py routes`.

**Tech Stack:** Python 3.13 (ansible-core 2.20+, stdlib only), pytest with the mocked opener in `tests/unit/helpers.py` (`FakeOpener`, `Resp`, `http_error`, `run_module`), ruff, ansible-test, ansible-lint, antsibull-changelog, uv.

**Spec:** `docs/superpowers/specs/2026-11-16-lot4-monitoring-and-ops-design.md`. Endpoint facts below were read from `docs/openapi/21201-20.3.0.json` (v2) and `21202-20.3.0.json` (v3).

## Global Constraints

- Run everything through `uv run` (`uv run --python 3.13 pytest -q`). No runtime dependency beyond ansible-core. `requires_ansible >=2.20.0`.
- Work on branch `feat/lot4-monitoring-ops`.
  - Commit with `git commit -F <file>`, the message file under `/private/tmp/claude-501/-Users-fjacquet-Projects-ansible-ppdm/83d0e71b-878a-49b1-83b3-483968f10517/scratchpad/`. Never use a heredoc.
  - `git add` explicit paths only.
  - Trailers: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_0148C11ULwRXo28pUmDdJZYr`.
  - Never commit under `.superpowers/`. Never push.
  - macOS `sed -i` needs an extension, so prefer the Edit tool.
- Modules have no `ppdm_` prefix. Add every new module to `meta/runtime.yml` `action_groups.ppdm`; `tests/unit/test_runtime_groups.py` enforces it.
- Never hand-edit the generated blocks (`# BEGIN GENERATED` / `# END GENERATED`) or `_enums.py`. Edit `tools/schemas/*.yml` or `tools/generate.py`, then run `generate.py modules` / `generate.py enums`.
- Every new module and option gets DOCUMENTATION `version_added: 0.4.0`.
  - Notes carry only the line "Unofficial collection, not affiliated with Dell. Written against the PowerProtect Data Manager 20.3.0 REST API."
  - The "not validated against a live PPDM" disclaimer lives only in the root `README.md`.
  - Each unverified body shape goes to the list in "Lab checklist items" below, which Task 12 consumes.
- **No module option may reuse a connection option name** (`hostname`, `username`, `password`, `port`, `validate_certs`, `ca_path`, `timeout`). `dict(connection_argument_spec(), **ARGUMENT_SPEC)` would silently override it. SMTP and user fields are therefore renamed (see Tasks 6 and 7). Task 1 adds a guard test.
- Secrets get `no_log: true` in the schema. They never appear in `diff`, the return values or an error message: use `ensure(secret_keys=...)`, `info_main(secret_fields=...)` and `client.scrub_text`.
- Modules that refuse to act without `confirm: true` (`activity_action` with `action=cancel`, `restore_plan_run`, `upgrade_package_action`) fail **before** `client_from_module` (no login, no request) when it is false, in check mode too.
- check_mode is correct everywhere: no POST/PUT/PATCH/DELETE in check mode, except the read-only GETs.
- `validate-modules`, pep8, pylint (full `ansible-test sanity`), ruff and ansible-lint (production profile) must all be clean.
- TDD: write the failing test, see it fail, implement, see it pass, then commit. Every commit keeps `uv run --python 3.13 pytest -q` green.

## Review Focus

- `await_activity` accepts the v3 `result.status` values (Task 1). Without that fix every waited activity of 0.3.0 and Lot 4 fails, because `wait_activity` polls `/api/v3/activities/{id}`.
- No password (connection, SMTP, user, lockbox passphrase, upgrade token) can reach `diff`, the return values, `msg` or an error `body`. This covers Tasks 6, 7 and 10. Assert it in the tests, with a sentinel string searched in `json.dumps(out)`.
- `confirm` refusal sends no request at all, in check mode too. This covers Tasks 5, 9 and 10. Assert `op.calls == []`.
- `smtp` never POSTs a second configuration when one exists with a different `mailServer`. It is a singleton (Task 6).
- `latest-copies` is called with `filter` only, with no `page`/`pageSize`, because strict REST validation rejects undocumented query parameters (Task 4).
- `upgrade_package_action` is a no-op on an already installed package, and refuses `revert` on a package that is not revertable (Task 10).

---

### Task 1: shared client fixes (v3 activity status, `info_main` keys, singleton `ensure`/`remove`, option-collision guard)

**Files:**

- Modify: `plugins/module_utils/ppdm.py`
- Modify: `tools/schemas/discovery.yml`, `protection_policy_run.yml`, `protection_rule_run.yml` (status wording only), then regenerate
- Test: `tests/unit/module_utils/test_ppdm_ensure.py`
- Test: `tests/unit/modules/test_info_modules.py`
- Test: create `tests/unit/modules/test_option_names.py`

**Interfaces:**

- **`await_activity(activity_id, timeout)`**
  - Success when `result.status` is in `{"OK", "SUCCESS"}`.
  - Warning when it is in `{"OK_WITH_ERRORS", "COMPLETED_WITH_EXCEPTIONS"}`.
  - Anything else is a `PpdmError`, as today.
  - The v3 `ActivityStatus` enum is `SUCCESS, COMPLETED_WITH_EXCEPTIONS, FAILED, CANCELED, SKIPPED, RETRIED`. The v2 enum is `OK, OK_WITH_ERRORS, ...`. Keep both so the existing fixtures stay green.
  - Put the two sets in module constants next to `ACTIVITY_TERMINAL_STATES`, and fix its comment. The v3 `ActivityState` is `QUEUED, RUNNING, CANCELING, RETRYING, COMPLETED`.
- **`info_main(resource, result_key, argument_spec, secret_fields=(), extra_eq=None, name_key="name")`**
  - Read `name`, `id` and `filter` with `p.get(...)`, so a module may omit any of them. `smtp_info` omits all three; `alert_info` and `activity_info` have no `name`.
  - `name_key` is the field that `name` is matched against, in both the server filter and the client re-check. `user_info` passes `"username"`.
  - Build the `mutually_exclusive` pairs only from the options present in `argument_spec`. validate-modules raises `mutually_exclusive-unknown` for a term that is not in the spec (checked in `validate_modules/main.py`), so the fixed three pairs would break `alert_info` and `smtp_info` at sanity. Unit-test it: a spec with only `id` and `filter` gives exactly one pair.
- **`ensure(..., key="name")` and `remove(resource, key, value, ...)`** accept `key=None` for singleton resources.
  - The existing object is the only item of `list_all(resource)`: none means create, more than one means `PpdmError("<resource>: N objects exist, expected at most one (ids: ...)")`, with the ids scrubbed.
  - `remove(resource, None, None, ...)` deletes that single item.
  - The `create=False` error message reads `desired[key]`. With `key=None` it must say "<resource>: no object exists" instead of raising a KeyError.
  - Nothing else changes (secret handling, PUT/PATCH choice, check mode).
- **Option-name guard:** a test in `test_option_names.py`. For every `plugins/modules/*.py` that defines `ARGUMENT_SPEC`, it asserts `set(ARGUMENT_SPEC) & set(connection_argument_spec()) == set()`. No module is skipped, `api.py` included.

- [ ] **Step 1: Failing tests.**
  - `await_activity`: `SUCCESS` returns without warnings, `COMPLETED_WITH_EXCEPTIONS` adds one warning, `CANCELED` raises with the body kept, `OK` still passes.
  - `ensure(key=None)`:
    - 0 items gives a POST.
    - 1 item with a difference gives a PUT to `/api/v2/smtp/<id>`. Use `smtp` as the fixture resource.
    - 1 item that is the same gives no write.
    - 2 items fails with no write.
  - `remove(key=None)`: DELETE of the single item, and a no-op when there are none.
  - `info_main` with `name_key="username"` filters `username eq "x"` and re-checks it client-side.
  - A spec without `name`/`filter`/`id` lists everything.
  - The option guard test passes today; that is a regression guard only.
- [ ] **Step 2: Run, expect FAIL:** `uv run --python 3.13 pytest tests/unit/module_utils/test_ppdm_ensure.py tests/unit/modules/test_info_modules.py tests/unit/modules/test_option_names.py -q`.
- [ ] **Step 3: Implement.** Keep the diff small: the singleton lookup is one helper used by both `ensure` and `remove`. Update the three schemas so they say "C(OK)/C(SUCCESS) ... C(OK_WITH_ERRORS)/C(COMPLETED_WITH_EXCEPTIONS) only warns", then run `uv run python tools/generate.py modules`.
- [ ] **Step 4: Run** the full `uv run --python 3.13 pytest -q`, `generate.py modules --check`, `uv run ruff check . && uv run ruff format --check .`. All must PASS.
- [ ] **Step 5: Commit** (`fix: accept v3 activity result statuses; singleton ensure and info_main name_key`).

### Task 2: Lot 4 enums

**Files:**

- Modify: `tools/generate.py` (`build_enums`) and `plugins/module_utils/_enums.py` (generated)
- Test: `tests/unit/tools/test_generate_enums.py`

**Interfaces:** produces these `ENUMS` keys. Read each one with `get(<schema>)` and `_prop`/`_resolve`, never with raw `["properties"][x]["enum"]` on a `$ref`. `get()` takes the highest spec that defines the name. All the schemas below exist in exactly one spec (checked): the v3-only ones are the two activity options, the rest are v2-only.

| Key | Source schema.property (spec) | Used by |
|-----|-------------------------------|---------|
| `activity.retry_option` | `RetryActivityOption` enum (v3): `ALL, FROM_FAILED_STEP, NO_AUDIT_LOG, VIRTUAL_GROUP` | `activity_action.retry_options` |
| `alert.severity` | `Alert.severity` (v2): `CRITICAL, INFORMATIONAL, WARNING` | `alert_info.severity` |
| `alert.category` | `Alert.category` (v2) | `alert_info.category` |
| `alert.acknowledge_state` | `AlertAcknowledgement.acknowledgeState` (v2): `ACKNOWLEDGED, UNACKNOWLEDGED` | `alert_acknowledge.acknowledge_state` |
| `restore_plan.fallback_strategy` | `RestorePlan.fallbackStrategy` (v2): `CANCEL_ON_FAILURE, CONTINUE_ON_FAILURE` | `restore_plan.fallback_strategy` |
| `restore_plan_run.execution_type` | `RestorePlanExecutionRequest.executionType` (v2): `IMMEDIATELY, SCHEDULE` | `restore_plan_run.execution_type` |
| `upgrade_package.category` | `UpgradePackage.category` (v2): `ACTIVE, HISTORY` | `upgrade_package_info.category` |

Add no key that is not used as `choices` (`CancelActivityOption` has the single value `VIRTUAL_GROUP`, so `activity_action` gets no cancel options; note it in the docs).

- [ ] **Step 1: Failing test:** the seven keys exist with the values above, sorted.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement**, then `uv run python tools/generate.py enums`.
- [ ] **Step 4: Run** the full pytest, `generate.py enums --check`, and ruff. All must PASS.
- [ ] **Step 5: Commit** (`feat: Lot 4 enums from the OpenAPI specs`).

### Task 3: `activity_info` and `alert_info`

**Files:**

- Create: `tools/schemas/activity_info.yml`, `tools/schemas/alert_info.yml`
- Create: `plugins/modules/activity_info.py`, `plugins/modules/alert_info.py`
- Create: `tests/unit/modules/test_activity_info.py`
- Modify: `meta/runtime.yml`
- Modify: `tests/unit/modules/test_info_modules.py` (`alert_info` gets its own tests; it is not part of the `MODULES` parametrisation, which assumes `name`)

**Interfaces:**

- **`activity_info`** has a custom main, because `info_main` cannot add steps.
  - Options:
    - `id` (str)
    - `filter` (str), mutually exclusive with `id`
    - `steps` (bool, default false; only valid with `id`, otherwise fail before any request)
  - With `id`: `GET /api/v3/activities/<quote_id>` (200; a 404 gives an empty list). With `steps`, also `client.get_all("/api/v3/activities/<id>/steps")` (paged `ActivityStepsPage`), attached as `steps` to the returned activity.
  - Without `id`: `client.list_all("activities", filter=p["filter"])`.
  - Returns `activities` (a list).
  - Docs:
    - Recommend a `filter` (an unfiltered list pages through every activity, up to `MAX_ITEMS`).
    - State the v3 `state`/`result.status` values.
- **`alert_info`** is `info_main("alerts", "alerts", ARGUMENT_SPEC, extra_eq={"severity": "severity", "category": "category"})`.
  - Options: `id`, `filter`, `severity` (choices `alert.severity`), `category` (choices `alert.category`). There is no `name`, because alerts have none.
  - Endpoint: `GET /api/v2/alerts` (paged), and `/api/v2/alerts/{id}`.
  - The acknowledgement state is nested (`acknowledgement.acknowledgeState`), so it is reachable only through `filter`. Give an example in EXAMPLES.

- [ ] **Step 1: Failing tests:**
  - `activity_info`:
    - by id
    - by id with steps: two GETs, the steps attached
    - 404 gives an empty list
    - a filter is forwarded, checked with `parse_qs`
    - `steps` without `id` fails with no request
    - check mode is identical
  - `alert_info`:
    - list
    - `severity` is ANDed into the filter and re-checked
    - by id
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Write** the schemas, run `generate.py modules`, write the bodies, update `runtime.yml`.
- [ ] **Step 4: Run** the full pytest, `generate.py modules --check`, and ruff. All must PASS.
- [ ] **Step 5: Commit** (`feat: add activity_info and alert_info modules`).

### Task 4: `copy_info`

**Files:**

- Create: `tools/schemas/copy_info.yml`, `plugins/modules/copy_info.py`, `tests/unit/modules/test_copy_info.py`
- Modify: `meta/runtime.yml`

**Interfaces:** a custom main with literal paths (`copies` has no route).

- Options, with exactly one of the first three required (`required_one_of` + `mutually_exclusive`):
  - `id` (str)
  - `asset_id` (str)
  - `latest_asset_ids` (list of str)
  - `filter` (str, only with `asset_id` or `latest_asset_ids`, ANDed in parentheses)
- With `id`: `GET /api/v3/copies/<quote_id>`, which answers 200. The spec lists no 404; treat a 404 or a 204 as an empty list anyway. Document that this endpoint is Administrator-only.
- With `asset_id`: `client.get_all("/api/v2/assets/<quote_id>/copies", query={"filter": ...})`. The answer is the paged `AssetCopies`.
- With `latest_asset_ids`:
  - Send **one** `client.request("GET", "/api/v2/latest-copies", query={"filter": 'assetId in ("a", "b")' [+ ' and (<filter>)']})`. The spec documents only `filter` (no `page`/`pageSize`) and requires an `assetId` term.
  - Quote every id with the escaping of `filter_eq`. Factor that one-liner out of `filter_eq` and reuse it; do not copy it.
  - The answer is `Copies` `{content: [...]}`. Return `content`.
  - An empty list fails before any request.
- Returns `copies` (a list).
- The v2/v3 `Copy` schemas have no credential/password field: say so in the report, and mask nothing.

- [ ] **Step 1: Failing tests:**
  - each mode sends the exact path and query, and `latest-copies` has no `page` key
  - the filter is escaped for an id containing `"`
  - 404 by id gives an empty list
  - two modes at once fail with no request
  - an empty `latest_asset_ids` fails
- [ ] **Steps 2-5** as Task 3. Commit (`feat: add copy_info module`).

### Task 5: `activity_action` and `alert_acknowledge`

**Files:**

- Create: `tools/schemas/activity_action.yml`, `tools/schemas/alert_acknowledge.yml`
- Create: `plugins/modules/activity_action.py`, `plugins/modules/alert_acknowledge.py`
- Create: `tests/unit/modules/test_activity_action.py`, `tests/unit/modules/test_alert_acknowledge.py`
- Modify: `meta/runtime.yml`

**Interfaces:**

- **`activity_action`**
  - Options:
    - `id` (str, required)
    - `action` (`cancel` | `retry`, required)
    - `retry_options` (list, choices `activity.retry_option`, retry only)
    - `confirm` (bool, default false; required true for `cancel`)
    - `wait` (bool, default false)
    - `wait_timeout` (int, default 600)
  - Flow:
    1. Check `confirm` (cancel, before login).
    2. `GET /api/v3/activities/<id>`. A 404 fails.
    3. Cancel on an activity with `state == "COMPLETED"` gives `changed=false` and no POST.
    4. Otherwise, `"CANCEL"` (or `"RETRY"`) must be in `supportedActions`. If it is not, fail with the state, and send no POST.
    5. Send `client.start_action("/api/v3/activities/<id>/cancel", {}, check_mode)` or `.../retry` with `{"retryOptions": [...]}` (omitted when unset). Both answer 202 `ActivityInterventionResponse {activityId}` (required).
  - `wait`:
    - Retry: `await_activity(<response activityId>)` (the new activity). A response without `activityId` fails.
    - Cancel: `client.wait_activity(id, timeout)` on the original activity. A `CANCELED` (or any) result is success, because `await_activity` would raise on `CANCELED`.
  - Returns `activity` (the GET, or the final activity when waited) and `response`.
- **`alert_acknowledge`**
  - Options: `ids` (list of str, required, non-empty), `acknowledge_state` (choices `alert.acknowledge_state`, default `ACKNOWLEDGED`).
  - Flow:
    1. `GET /api/v2/alerts/<id>` for each id. A 404 fails, listing the missing ids, before any write.
    2. Keep the alerts whose `acknowledgement.acknowledgeState` differs from the desired state. None means `changed=false`.
    3. Otherwise, outside check mode, send `POST /api/v2/alerts/acknowledgements` with body `{"messageIds": [...], "acknowledgement": {"acknowledgeState": ...}}` (`MessageBulk`, required `acknowledgement`, `messageIds`). It answers **207** `MessageBulk` with `bulkResults[{id, acknowledgement, errorResponseObject}]`.
    4. Any item with an `errorResponseObject` fails the module, with the scrubbed messages and the results kept.
  - Returns `changed`, `updated_ids`, `results`.
  - The per-alert `PUT /api/v2/alerts/{id}/acknowledgement` is not used (one call for all).

- [ ] **Step 1: Failing tests:**
  - cancel without confirm: `op.calls == []`, in check mode too
  - cancel of a COMPLETED activity: no POST
  - action not in `supportedActions`: fails with no POST
  - cancel sends the exact path and `{}`
  - retry with options sends the exact body
  - retry with wait polls the new id
  - cancel with wait ending `CANCELED` does not fail
  - check mode sends no POST
  - acknowledge skips already acknowledged alerts
  - all already acknowledged: no POST, `changed` false
  - a 207 with one `errorResponseObject` fails
  - a 404 id fails with no POST
  - unacknowledge works
- [ ] **Steps 2-5** as Task 3. Commit (`feat: add activity_action and alert_acknowledge modules`).

### Task 6: `smtp` and `smtp_info`

**Files:**

- Create: `tools/schemas/smtp.yml`, `tools/schemas/smtp_info.yml`
- Create: `plugins/modules/smtp.py`, `plugins/modules/smtp_info.py`
- Create: `tests/unit/modules/test_smtp.py`
- Modify: `meta/runtime.yml`

**Interfaces:**

- `Smtp` (v2) has required `mailServer`, and the fields `id, mailFrom, port, recipient, username, password, isStartTls`. No field is flagged readOnly, so pass `readonly=("id",)`.
- The resource is a singleton ("Only one SMTP configuration is allowed"): use `ensure("smtp", desired, key=None, ...)` and `remove("smtp", None, None, ...)` from Task 1.
- Verbs:
  - POST `/api/v2/smtp` answers 200 `Smtp` or 201 with an empty body. `ensure` already falls back to the sent body.
  - The update is **PUT** `/api/v2/smtp/{id}` (200). The route has no PATCH, so `ensure` picks PUT.
  - DELETE answers 200 or 204.
- **`smtp`** options. The names avoid the connection options:

  | Option | Field / behaviour |
  |--------|-------------------|
  | `state` | `present` \| `absent` |
  | `mail_server` | → `mailServer` (required when present) |
  | `mail_from` | → `mailFrom` |
  | `recipient` | → `recipient` |
  | `smtp_port` | int → `port` |
  | `smtp_username` | → `username` |
  | `smtp_password` | no_log → `password` |
  | `start_tls` | bool → `isStartTls` |
  | `update_password` | `on_create` \| `always`, the `credential` pattern |
  | `test` | bool, default false |
  | `config` | dict, through `merge_config` |

  - `ensure(..., secret_keys=("password",), update_secrets=p["update_password"])`.
  - `test`: after the ensure, outside check mode, send `POST /api/v2/smtp/test`.
    - The body is `SmtpTest`, required `mailServer` and `recipient`, from the desired values. Include `password` only when `smtp_password` is set.
    - It answers 200 with an empty body.
    - `test` without `recipient` fails before any request.
    - The test sends a real email, which is why it is skipped in check mode. A test does not set `changed` by itself.
- **`smtp_info`**: `info_main("smtp", "smtp", {}, secret_fields=("password",))`, with no options. Returns `smtp` (a list, at most one item). A secret listed in `secret_fields` is dropped from each object, not masked; document that.

- [ ] **Step 1: Failing tests:**
  - create: POST body exact, `password` masked in `smtp` and `diff`, sentinel absent from `json.dumps(out)`
  - an update on a `mailServer` change PUTs to the existing id and never POSTs
  - idempotent no-op without a password
  - `update_password=always` forces the PUT
  - absent DELETEs
  - two existing configs fail
  - test sent after the ensure
  - test skipped in check mode
  - test without recipient fails
  - `smtp_info` drops `password`
- [ ] **Steps 2-5** as Task 3. Commit (`feat: add smtp and smtp_info modules`).

### Task 7: `user`, `user_info`, `role_info`

**Files:**

- Create: `tools/schemas/user.yml`, `tools/schemas/user_info.yml`, `tools/schemas/role_info.yml`
- Create: the three module files and `tests/unit/modules/test_user.py`
- Modify: `meta/runtime.yml`
- Modify: `tests/unit/modules/test_info_modules.py` (`role_info` in `MODULES`, `/api/v2/roles`, `roles`)

**Interfaces:**

- Endpoints:
  - `/api/v2/users`: GET paged; POST 201 (also 409 and 422); PUT `/{id}` 200; DELETE 204.
  - The route has no PATCH, so `ensure` picks **PUT**. PUT is a full replacement, and `ensure` already sends the existing object merged with the desired fields, minus `WRITE_ONLY_KEYS` (`password` included).
  - The `User` schema requires `emailAddress, firstName, lastName, username`. Pass `readonly=("id", "createdDate")`.
  - **The spec marks `/api/v2/users` deprecated** (replacement `/api/v3/identity-access-provisions`). Lot 4 stays on v2 as the spec says. Put it in the module notes and in the lab checklist.
- **`user`** options:

  | Option | Field / behaviour |
  |--------|-------------------|
  | `state` | `present` \| `absent` |
  | `name` | required → `username`; the key is `username` |
  | `first_name` | → `firstName` |
  | `last_name` | → `lastName` |
  | `email` | → `emailAddress` |
  | `user_password` | no_log → `password` |
  | `update_password` | `on_create` \| `always` |
  | `force_password_change` | bool → `forcePasswordChange` |
  | `role` / `role_id` | mutually exclusive → `roleId`; `role` is resolved with `find_one("roles", "name", v)`, no match fails "role X not found" with no write |
  | `config` | dict |

  - On create, `first_name`, `last_name`, `email` and `user_password` are required. When any of them is None, the module calls `client.find_one("users", "username", name)` before `ensure`. If no user exists, it fails with no write. If the user exists, `ensure` runs, which makes a second GET; the fixtures expect `GET users, GET users, PUT`. With all four set there is no pre-check (`GET users, POST`).
  - Secret-name check: `force_password_change` is a bool and `update_password` has choices, so validate-modules does not require `no_log` on them. `is_potential_secret_option` exempts both types. `smtp_username` and `smtp_port` do not match `NO_LOG_REGEX`.
  - `ensure("users", desired, key="username", secret_keys=("password",), update_secrets=p["update_password"], readonly=READONLY)`.
  - Returns `user` and `diff`.
- **`user_info`**: `info_main("users", "users", ARGUMENT_SPEC, secret_fields=("password",), name_key="username")`, with options `name`, `filter`, `id`.
- **`role_info`**: `info_main("roles", "roles", ARGUMENT_SPEC)`, with options `name`, `filter`, `id`. A role carries `name`, `displayName`, `privilegeList`, `systemRole`.

- [ ] **Step 1: Failing tests:**
  - create with role name: GET roles, GET users, POST body exact; `user_password` sentinel absent from `json.dumps(out)`
  - update PUTs only on a difference, never sends `password` unless `update_password=always`
  - absent DELETE 204
  - check mode sends no write
  - unknown role fails with no write
  - create with no email fails with no write
  - `user_info` filters `username eq` and drops `password`
- [ ] **Steps 2-5** as Task 3. Commit (`feat: add user, user_info and role_info modules`).

### Task 8: `restore_plan` and `restore_plan_info`

**Files:**

- Create: `tools/schemas/restore_plan.yml`, `tools/schemas/restore_plan_info.yml`
- Create: the two module files and `tests/unit/modules/test_restore_plan.py`
- Modify: `meta/runtime.yml`
- Modify: `tests/unit/modules/test_info_modules.py` (`restore_plan_info`, `/api/v2/restore-plans`, `restore_plans`)

**Interfaces:**

- Endpoints:
  - `/api/v2/restore-plans`: POST 201; PATCH `/{id}` 200 (also 409); DELETE `/{id}` 204, or **409 while the plan runs** (surfaced as the PpdmError message).
  - The route has no PUT, so `ensure` already picks **PATCH**. `ensure` is reused as is.
- `READONLY = ("createdAt", "id", "lastRun", "state", "stateReason", "updatedAt")`. The spec flags none of them, so pass them explicitly.
- Options:
  - `state`
  - `name` (required)
  - `description`
  - `fallback_strategy` (choices `restore_plan.fallback_strategy`)
  - `restore_groups` (list of dict, sent as `restoreGroups`; item shape `RestoreGroup`, where `assetType` is only `VMWARE_VIRTUAL_MACHINE` in 20.3.0; not validated beyond being a list of dicts)
  - `schedule` (dict, sent as `schedule`, `{startTime}`)
  - `config`
- Compare with `ensure(..., subset_keys=("restoreGroups", "schedule"))`. The server adds `id`, `state` and `stateReason` to each restore group. Lists are compared in order, by index, with equal length.
- Returns `restore_plan` and `diff`.
- **`restore_plan_info`**: `info_main("restore-plans", "restore_plans", ...)`, with options `name`, `filter`, `id`. `RestoreGroup.extendedData` is free-form and may carry credentials (an unknown). Drop nothing, and put it on the lab checklist.

- [ ] **Step 1: Failing tests:**
  - create: POST body exact
  - idempotent no-op when the server echoes the read-only fields and the per-group `id`/`state`
  - update PATCHes only on a difference
  - absent DELETE 204
  - DELETE 409 fails with the message
  - check mode sends no write
  - ambiguous name fails
  - `config` collision fails
- [ ] **Steps 2-5** as Task 3. Commit (`feat: add restore_plan and restore_plan_info modules`).

### Task 9: `restore_plan_run`

**Files:**

- Create: `tools/schemas/restore_plan_run.yml`, `plugins/modules/restore_plan_run.py`, `tests/unit/modules/test_restore_plan_run.py`
- Modify: `meta/runtime.yml`

**Interfaces:**

- Options:
  - `plan` (str, required: a name first, then an id, as `find_policy` in `protection_policy_run`)
  - `execution_type` (choices `restore_plan_run.execution_type`, default `IMMEDIATELY`)
  - `schedule_time` (str, ISO 8601; required with `SCHEDULE`, refused with `IMMEDIATELY`)
  - `confirm` (bool, default false, must be true)
  - `wait` (bool)
  - `wait_timeout` (int, default 600)
- `wait` with `SCHEDULE` is an error before any request.
- Request: `client.start_action("/api/v2/restore-plans/<quote_id>/execute", {"executionType": ..., ["scheduleTime": ...]}, check_mode)`.
- The answer is 201 (immediate) or 202 (scheduled) `RestorePlanExecutionResult {executionType, activities: [{activityId, restoreGroupId}]}`. A 409 (already running) is the PpdmError message.
- `wait`: mirror the results loop of `protection_policy_run`. Poll every `activityId` with `await_activity`; one failure does not hide the others; an empty `activities` or an entry without `activityId` fails with `wait`, and only warns without it.
- Returns `result` (the answer), `activities` (when waited) and `warnings`.

- [ ] **Step 1: Failing tests:**
  - no confirm: `op.calls == []`
  - run by name and by id, body exact
  - `SCHEDULE` without `schedule_time` fails
  - `wait` with `SCHEDULE` fails
  - wait polls two activities, one `FAILED`: fails with both reported
  - check mode sends no POST
  - unknown plan fails
- [ ] **Steps 2-5** as Task 3. Commit (`feat: add restore_plan_run module`).

### Task 10: `upgrade_package_info` and `upgrade_package_action`

**Files:**

- Create: `tools/schemas/upgrade_package_info.yml`, `tools/schemas/upgrade_package_action.yml`
- Create: the two module files and `tests/unit/modules/test_upgrade_package_action.py`
- Modify: `meta/runtime.yml`
- Modify: `tests/unit/modules/test_info_modules.py`

**Interfaces:**

- **Secrets of `UpgradePackage`:** `lockboxPassphrase` and `upgradeToken`. Neither is in `WRITE_ONLY_KEYS`, and neither must be returned. The module returns `_mask`-style `MASK` values for both.
- **`upgrade_package_info`**: `info_main("upgrade-packages", "upgrade_packages", ARGUMENT_SPEC, secret_fields=("lockboxPassphrase", "upgradeToken"), extra_eq={"category": "category"})`.
  - Options: `name`, `filter`, `id`, `category` (choices `upgrade_package.category`).
  - Endpoint: `GET /api/v2/upgrade-packages` (paged).
- **`upgrade_package_action`** options:
  - `action` (`precheck` | `upgrade` | `revert`, required)
  - `id` (str; default: the single package with `category eq "ACTIVE"`, where none or several fail, as the `maintenance.install_update_package` playbook does)
  - `confirm` (bool, default false, must be true for **every** action, as the spec says)
  - `force` (bool, default false; sent as query `forceUpgrade=true|false` on the upgrade, **always explicit** because the spec default is `'true'`)
  - `trust_certificate` (bool, default false → `certificateTrustedByUser`)
  - `accept_eula` (bool, default false → `eula.productEulaAccepted` and `eula.telemetryEulaAccepted`)
  - `lockbox_passphrase` (no_log → `lockboxPassphrase`, sent only when set, needed when `lockboxResetRequired`)
  - `wait` (bool, **precheck only**; with `upgrade`/`revert` it is an error, because the appliance restarts. Document polling with `upgrade_package_info` and the `bootstrap.wait_for_api` playbook instead.)
  - `wait_timeout` (int)
- Flow: confirm check (before login), then `GET /api/v2/upgrade-packages/<id>`, then:

  | `action` | Already done (`changed=false`, no request) | Refused (fail, no request) | Request and success code |
  |----------|-------------------------------------------|----------------------------|--------------------------|
  | `precheck` | (none) | `state` starts with `INSTALLED` | `POST .../<id>/precheck`, no body; 200 or 202 `UpgradePackage` (`activityId` polled with `await_activity` when `wait`) |
  | `upgrade` | `state` starts with `INSTALLED` | `state` not in `AVAILABLE`, `FAILED` (the documented precondition) | `PUT .../<id>?forceUpgrade=<force>` with the GET body minus `_links` (and minus `lockboxPassphrase` unless set), merged with `state: INSTALLED`, `certificateTrustedByUser`, `eula` and the passphrase. Only **202** (`UpgradePackage`) is success; the spec gives 200 the `ErrorMessage` schema, so a 200 fails with its scrubbed message. Read `client.last_status`. |
  | `revert` | `state == "REVERTED"` | `revertSupported` is not true, or `type != "HOTFIX"` | `POST .../<id>/revert`, no body; 202 `RevertResponse {activityId, id}` |

- Requests go through `client.request`, or `start_action` for the POSTs. In check mode nothing is sent and `changed=true`, except on the no-op rows.
- Returns `upgrade_package` (masked) and `response` (masked).

- [ ] **Step 1: Failing tests:**
  - no confirm: `op.calls == []`, check mode too
  - the default id from one ACTIVE package; two ACTIVE packages fail
  - upgrade PUT body exact and `forceUpgrade=false` in the query
  - upgrade on `INSTALLED` is a no-op
  - upgrade on `PROCESSING` fails
  - a 200 answer to the PUT fails
  - revert refused when not revertable
  - precheck with wait polls the activity
  - wait with upgrade fails
  - `upgradeToken`/`lockboxPassphrase` sentinels absent from `json.dumps(out)`
  - `upgrade_package_info` drops both
- [ ] **Steps 2-5** as Task 3. Commit (`feat: add upgrade_package_info and upgrade_package_action modules`).

### Task 11: example playbooks for the Lot 3 modules

**Files:**

- Create: `playbooks/protection/create_resource_group.yml`, `playbooks/protection/create_protection_group.yml`, `playbooks/assets/find_assets.yml`
- Modify: `playbooks/vars/example.yml`, `playbooks/README.md`, root `README.md` (playbook count `63` → `66`)
- Test: `tests/unit/test_playbooks.py` (existing guards; no new set entry is expected, see below)

**Interfaces:** consumes the Lot 3 option names (`resource_group`, `protection_rule` with `action: ASSIGN_RESOURCE_GROUP` + `resource_group`, `protection_group`, `asset_info`, `host_info`).

Conventions enforced by `test_playbooks.py`:

- File and directory names match `^[a-z][a-z0-9_]*$`.
- `hosts: "{{ target | default('localhost') }}"`.
- FQCN modules only, one per task.
- The header comment (before the first `- name:`) contains `PPDM_`.
- New playbooks carry **no** "Inspired by bottkars" credit line.
- No literal secret.
- README index rows look like `| [fjacquet.ppdm.<usecase>.<name>](<usecase>/<name>.yml) | <what> | <modules> | - | - | new |`. Status `new` iff the sources column is `-`.

Playbooks:

- **`protection.create_resource_group`**: ensure the resource group (`resource_group_name`, `resource_group_description`), then a v3 rule `resource_group_rule_name` with `action: ASSIGN_RESOURCE_GROUP`, `resource_group: "{{ resource_group_name }}"` and `filters: "{{ resource_group_rule_filters }}"` (a VM-tag filter tree like `rule_filters`).
- **`protection.create_protection_group`**: ensure one protection group. Variables: `protection_group_name`, `protection_group_type` (default `STORAGE_DIRECT_APPLICATION`; the README row says that 20.3.0 knows only storage-direct and Oracle Data Guard), `protection_group_subtype`, `protection_group_member_asset_type`, `protection_group_natural_ids`, and an optional `protection_group_policy` (omitted with `default(omit)`).
- **`assets.find_assets`**: read-only. `asset_info` with `name`/`asset_type` from `find_asset_name`/`find_asset_type` (both `default(omit)`), then `host_info` with `find_host_name`, then a `debug` of a projection (`name`, `id`, `type`) of each.

None of the three is destructive under `_is_write`. `resource_group`, `protection_rule` and `protection_group` are idempotent ensures and are not in `CURATED_WRITES`. Follow the `protection.create_rule` precedent:

- Do not add them to `DESTRUCTIVE` or `NOT_GUARDED`.
- Do not add a `*_confirm` variable.
- Leave the README "destructive or service affecting" and "are not guarded" sentences unchanged, since the tests compare them with those sets.

The spec asks for no playbooks for the new run/action modules, so add none. Note it in the report.

Add "Unverified details" bullets in `playbooks/README.md` for:

- the protection group body per type
- the resource-group rule filter `fieldName` (same doubt as `create_rule`)

- [ ] **Step 1:** Add the three README rows first (Protection and Assets sections) and run `uv run --python 3.13 pytest tests/unit/test_playbooks.py -q`. Expect FAIL (rows without files).
- [ ] **Step 2:** Write the playbooks and the vars.
- [ ] **Step 3:** Run `uv run --python 3.13 pytest -q` (PASS), then `ANSIBLE_COLLECTIONS_PATH=~/.cache/ppdm-ac uv run ansible-lint --profile production playbooks/protection/create_resource_group.yml playbooks/protection/create_protection_group.yml playbooks/assets/find_assets.yml` (clean; refresh the worktree first, see Task 12).
- [ ] **Step 4: Commit** (`feat: add resource group, protection group and asset lookup playbooks`).

### Task 12: release 0.4.0

**Files:**

- Modify: `README.md` (module table and lab checklist)
- Modify: `meta/runtime.yml` (verify that all 15 new modules are listed)
- Create: `changelogs/fragments/lot4-monitoring-ops.yml`
- Modify: `galaxy.yml` (`version: 0.4.0`)
- Modify (via antsibull-changelog): `changelogs/changelog.yaml`, `CHANGELOG.rst`

Steps:

- [ ] **Step 1: README.**
  - Add 15 rows to the module table: `activity_info`, `activity_action`, `alert_info`, `alert_acknowledge`, `copy_info`, `smtp_info`, `smtp`, `user_info`, `user`, `role_info`, `restore_plan_info`, `restore_plan`, `restore_plan_run`, `upgrade_package_info`, `upgrade_package_action`. One-line purposes, with the `_info` row before its module, as in the existing table.
  - Replace the existing "Activity results: confirm the `result.status` values (`OK`, ...)" bullet with the v3 wording.
  - Append every item of "Lab checklist items" below.
  - Add no new disclaimer sentence.
- [ ] **Step 2: Changelog fragment:**
  - `release_summary`
  - `minor_changes`: the 15 modules, the three playbooks, `info_main` `name_key`, singleton `ensure`/`remove`
  - `bugfixes`: waited activities failed on the v3 `SUCCESS`/`COMPLETED_WITH_EXCEPTIONS` statuses in `discovery`, `protection_policy_run`, `protection_rule_run`
  - `known_issues`: `user`/`user_info` use the v2 users API, which 20.3.0 marks deprecated

  Then run `uv run antsibull-changelog lint` and `uv run antsibull-changelog release --version 0.4.0`, and bump `galaxy.yml`.
- [ ] **Step 3: Gates.** Run all of them and report each result. Run the local gates, commit (Step 4), then refresh the worktree to that sha and run the ansible-test gates there. If any gate fails, fix it in a new commit, never an amend, and rerun.
  - `uv run ruff check . && uv run ruff format --check .`
  - `uv run --python 3.13 pytest -q`
  - `uv run python tools/generate.py modules --check` and `uv run python tools/generate.py enums --check` (the latter is not in CI)
  - `git -C ~/.cache/ppdm-ac/ansible_collections/fjacquet/ppdm checkout --detach <sha>`. Then from inside that directory:
    - `uv run --project /Users/fjacquet/Projects/ansible-ppdm ansible-test sanity --python 3.13` (**full**, no `--test` subset: CI runs pylint too)
    - `uv run --project /Users/fjacquet/Projects/ansible-ppdm ansible-test units --python 3.13`
  - `ANSIBLE_COLLECTIONS_PATH=~/.cache/ppdm-ac uv run ansible-lint --profile production` (repo root)
  - `gitleaks detect --source . --no-banner` (uses `.gitleaksignore`)
  - `uv run ansible-galaxy collection build --force --output-path <scratch>` and `tar tzf` on the result: no `docs/superpowers`, `docs/openapi`, `tools/`, `.superpowers`, `.venv`, `.pytest_cache`.
- [ ] **Step 4: Commit** (`chore: release 0.4.0 changelog and README`). Do not push, merge or tag: the controller asks the author first.

## Lab checklist items (consumed by Task 12)

- Activities: confirm that `GET /api/v3/activities/{id}` reports `result.status` `SUCCESS`/`COMPLETED_WITH_EXCEPTIONS` (v3), and whether any path still returns the v2 `OK`/`OK_WITH_ERRORS`.
- `activity_action`:
  - confirm that cancel/retry accept an empty body `{}`;
  - confirm that retry answers a **new** `activityId`;
  - confirm that a cancelled activity ends `COMPLETED` with `result.status` `CANCELED`.
- `alert_acknowledge`: confirm the 207 `bulkResults` shape and that `errorResponseObject` is set only on failed items.
- `copy_info`:
  - confirm that `/api/v2/latest-copies` rejects `page`/`pageSize` under strict validation;
  - confirm the `assetId in (...)` filter syntax;
  - confirm that `/api/v3/copies/{id}` answers 404 for an unknown id.
- `smtp`:
  - confirm that POST answers 201 with an empty body or 200 with the object;
  - confirm that PUT without `password` keeps the stored password;
  - confirm that `smtp/test` uses the body `recipient` (the endpoint text says `mailRecipient`).
- `user`:
  - `/api/v2/users` is deprecated in 20.3.0 (replacement `/api/v3/identity-access-provisions`);
  - confirm that PUT without `password` keeps it;
  - confirm that the role is matched by `name` (not `displayName`).
- `restore_plan`:
  - confirm that PATCH replaces `restoreGroups` as a whole list and keeps their order;
  - confirm the read-only set;
  - confirm whether `restoreGroups[].extendedData` can carry credentials.
- `restore_plan_run`: confirm the 201/202 `activities` list and that one activity is started per restore group.
- `upgrade_package_action`:
  - confirm that the PUT needs the GET body including `upgradeToken`;
  - confirm that 202 is the only success (the spec gives 200 an `ErrorMessage`);
  - confirm the `forceUpgrade` semantics;
  - confirm when `lockboxPassphrase` is required;
  - confirm that precheck answers an `activityId`;
  - confirm that revert applies only to `HOTFIX` packages with `revertSupported`.
- `protection.create_protection_group`: confirm the minimal body for `STORAGE_DIRECT_APPLICATION` and `ORACLE_DATA_GUARD`.
