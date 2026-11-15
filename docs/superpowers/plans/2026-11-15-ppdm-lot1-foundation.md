# fjacquet.ppdm Lot 1 (foundation, bootstrap, inventory) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `fjacquet.ppdm` 0.1.0 (pre-release): shared REST client, generator, generic `api` module, Lot 1 modules and the `bootstrap` role for PPDM 20.3.0.

**Architecture:** One `module_utils/ppdm.py` client (login, version routing from a generated table, pagination, idempotent ensure, activity wait) used by thin modules. A generator reads the committed OpenAPI files and emits the routes table and the module `DOCUMENTATION`/`argument_spec` blocks from per-module YAML schemas.

**Tech Stack:** Python 3.10+, ansible-core (maintained releases), `ansible.module_utils.urls.open_url` (no `requests`), `uv`, pytest, ansible-test sanity, ansible-lint, antsibull-changelog, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-15-fjacquet-ppdm-collection-design.md` (read it first; Lots 2 and 3 are out of scope here).

## Global Constraints

- Namespace/name `fjacquet.ppdm`; license GPL-3.0-or-later; module names have no `ppdm_` prefix.
- Zero runtime Python deps beyond ansible-core; HTTP only via `ansible.module_utils.urls.open_url`.
- `validate_certs` default **true**, option `ca_path`; `password` is `no_log`; env fallbacks `PPDM_HOSTNAME`, `PPDM_USERNAME`, `PPDM_PASSWORD`, `PPDM_PORT` (default 8443).
- No `state: get`. Mutating: `state: present|absent`. Reads: `*_info`. Singletons: `present` only.
- API version is chosen per resource from the generated table, never globally.
- List calls paginate: `page` (1-based) and `pageSize` (default 100, max 10000) until `page.totalPages`; response envelope `{content, page}`.
- Non-2xx always `fail_json(msg, status, body)`; no tolerated-status lists.
- PUT replaces the whole object: GET, merge only user-supplied keys, compare, PUT only on a difference; strip `_links` and OpenAPI `readOnly` fields.
- `check_mode` correct everywhere; return `diff`.
- Specs committed under `docs/openapi/` (21200, 21201, 21202 only); `build_ignore`: `docs/superpowers/`, `docs/openapi/`, `tools/`, `.venv`.
- Releases are `0.x` until a live PPDM 20.3 run validates Lot 1; no lab exists yet, so tests are mocked.
- Always `uv run ...`; commits end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.

## Review Focus

- Empty list result (`content: []`, `totalPages: 0`): `*_info` returns `[]`, no error, no infinite loop.
- More than one page of results (e.g. 250 items at `pageSize` 100): all items returned, in order.
- Login failure (401, connection refused, TLS error): clear `fail_json`, no stack trace, password never in output.
- Two objects match the same name (non-unique key): module fails with both ids rather than picking one.
- Run twice with identical input: second run `changed=false`, no PUT sent.
- Check mode with a difference: `changed=true`, no write request sent.

## File Structure

- `pyproject.toml`, `galaxy.yml`, `meta/runtime.yml`, `README.md`, `NOTICE`, `LICENSE`, `CLAUDE.md`: packaging and docs.
- `docs/openapi/*.json`: committed specs.
- `tools/generate.py`, `tools/schemas/<module>.yml`: generator.
- `plugins/module_utils/_routes.py`: GENERATED routes table (committed).
- `plugins/module_utils/ppdm.py`: client. `plugins/doc_fragments/ppdm.py`: connection docs.
- `plugins/modules/*.py`: modules. `roles/bootstrap/`: role.
- `tests/unit/...`, `.github/workflows/ci.yml`, `changelogs/`.

## Finding that adjusts the spec

In 20.3.0 `/api/v2/storage-systems` has only GET and PUT (no POST/DELETE): Data Domain creation goes through `inventory-sources`. So Lot 1 `storage_system` updates an existing system (`present` only) and `storage_system_info` reads; adding a DD is `inventory_source`. `eulas` paths are `/api/v2/eulas/{PPDM|TELEMETRY|data-manager}` (GET, PATCH).

---

### Task 1: Scaffold the collection with uv

**Files:**
- Create: `pyproject.toml`, `galaxy.yml`, `meta/runtime.yml`, `README.md`, `NOTICE`, `LICENSE`, `CLAUDE.md`, `changelogs/config.yaml`, `changelogs/fragments/.gitkeep`, `plugins/{modules,module_utils,doc_fragments}/__init__.py`, `tests/unit/conftest.py`
- Copy: `<csm-powerscale-demo>/docs/openapi/{21200,21201,21202}-20.3.0.json` to `docs/openapi/`

**Interfaces:**
- Produces: importable package layout at `ansible_collections/fjacquet/ppdm` for tests and sanity; `uv run pytest` and `uv run ansible-test` work.

- [ ] **Step 1:** `uv init --bare`; dev group in `pyproject.toml`: `ansible-core`, `ansible-lint`, `antsibull-changelog`, `ansible-creator`, `pytest`, `pytest-mock`, `pyyaml`. Run `uv sync`.
- [ ] **Step 2:** Scaffold with `uv run ansible-creator init collection fjacquet.ppdm /tmp/scaffold --exclude role`; copy only what the layout needs (galaxy.yml, meta, changelog config per ansible-new-collection skill, `.pre-commit-config.yaml`); delete all `sample_*` plugins.
- [ ] **Step 3:** `galaxy.yml`: version `0.1.0`, GPL-3.0-or-later, author from git config, repository `https://github.com/fjacquet/ansible-ppdm` (confirm repo name with the author), `build_ignore` per Global Constraints. `README.md`: "unofficial, not affiliated with Dell" + attribution to `bottkars/ansible_ppdm` workflows; `NOTICE` carries the attribution.
- [ ] **Step 4:** Local layout for `ansible-test`: `ln -s` the repo into `.ansible_collections/ansible_collections/fjacquet/ppdm` (gitignore it) and document the command in `CLAUDE.md`.
- [ ] **Step 5:** Verify: `uv run ansible-galaxy collection build --force` succeeds and the tarball lacks `docs/openapi`, `tools`, `docs/superpowers`.
- [ ] **Step 6:** Commit `chore: scaffold fjacquet.ppdm collection`.

### Task 2: Generator part 1 — routes table

**Files:**
- Create: `tools/generate.py`, `tools/__init__.py`, `plugins/module_utils/_routes.py` (generated), `tests/unit/tools/test_generate_routes.py`

**Interfaces:**
- Produces: `tools.generate.build_routes(openapi_dir: Path) -> dict[str, dict]` where key is a resource slug (e.g. `"credentials"`) and value `{"version": "v2"|"v3", "base": "/api/v2/credentials", "item": "/api/v2/credentials/{id}", "methods": set[str], "readonly": sorted list[str]}`. When both v2 and v3 expose a collection, the higher version wins. `_routes.py` exposes `ROUTES` (same shape, methods as sorted list).
- CLI: `uv run python tools/generate.py routes` (default dir `docs/openapi`, override `PPDM_OPENAPI_DIR`).

- [ ] **Step 1:** Test `test_protection_policies_routes_to_v3`: `build_routes(Path("docs/openapi"))["protection-policies"]["version"] == "v3"` and `base == "/api/v3/protection-policies"`.
- [ ] **Step 2:** Test `test_credentials_v2_and_methods`: version `v2`, `{"GET","POST"} <= methods`; item methods include `PUT`, `DELETE`. Test `test_readonly_fields_from_schema`: `"id"` in `credentials` readonly list (verify against the spec; adjust to a field the spec actually marks `readOnly`).
- [ ] **Step 3:** Run, expect FAIL (module missing).
- [ ] **Step 4:** Implement `build_routes`: parse the three files, group paths by slug (`/api/vN/<slug>` and `/api/vN/<slug>/{param}`), resolve `$ref` in the request-body schema of PUT/POST to collect `readOnly` properties. Write `_routes.py` with a "GENERATED, do not edit" header, sorted output.
- [ ] **Step 5:** Run tests, expect PASS; `uv run python tools/generate.py routes` produces a stable file (run twice, `git diff` empty).
- [ ] **Step 6:** Commit `feat: generate resource routes table from OpenAPI`.

### Task 3: Client core (login, request, errors, pagination)

**Files:**
- Create: `plugins/module_utils/ppdm.py`, `tests/unit/module_utils/test_ppdm_client.py`

**Interfaces:**
- Produces:
  - `class PpdmError(Exception)`: `.status: int|None`, `.body: Any`, `.msg: str`.
  - `class PpdmClient(hostname, username, password, port=8443, validate_certs=True, ca_path=None, timeout=30, opener=open_url)`; `login() -> None` (POST `/api/v2/login`, stores `access_token`, retries not built in); `request(method, path, query=None, body=None) -> Any` (raises `PpdmError` on non-2xx/transport error, parses JSON, `None` for 204); `list_all(resource: str, filter: str|None=None, order_by: str|None=None) -> list[dict]` (uses `ROUTES[resource]["base"]`, paginates `page`/`pageSize=100` until `totalPages`, URL-encodes `filter`).
  - `connection_argument_spec() -> dict` with the env fallbacks from Global Constraints; `client_from_module(module) -> PpdmClient` which turns `PpdmError` into `module.fail_json(msg=..., status=..., body=...)` via a helper `fail_from(module, err)`.
- The opener is injected so tests pass a fake; production uses `open_url`.

- [ ] **Step 1:** Tests with a fake opener recording calls: `test_login_sets_bearer_header`, `test_list_all_paginates_250_items_in_three_requests` (pages of 100/100/50, assert `page=1..3` queries and result order), `test_list_all_empty_returns_empty_list_and_one_request`, `test_filter_is_url_encoded` (`name eq "a b"`), `test_non_2xx_raises_ppdm_error_with_status_and_body`, `test_login_failure_never_leaks_password` (error text excludes the password), `test_ca_path_and_validate_certs_passed_to_opener`.
- [ ] **Step 2:** Run, expect FAIL.
- [ ] **Step 3:** Implement per Interfaces. Map `HTTPError`/`URLError`/`SSLValidationError` to `PpdmError`; read the PPDM error JSON body when present.
- [ ] **Step 4:** Run, expect PASS.
- [ ] **Step 5:** Commit `feat: add PPDM client with login, paging and error mapping`.

### Task 4: Client idempotence and activity wait

**Files:**
- Modify: `plugins/module_utils/ppdm.py`; Test: `tests/unit/module_utils/test_ppdm_ensure.py`

**Interfaces:**
- Consumes: Task 3 client, `ROUTES`.
- Produces:
  - `PpdmClient.find_one(resource, key: str, value: str) -> dict|None`: `list_all` with `filter=f'{key} eq "{value}"'`; two matches raise `PpdmError` listing both ids.
  - `PpdmClient.ensure(resource, desired: dict, key="name", check_mode=False) -> dict` returning `{"changed": bool, "object": dict, "diff": {"before": dict, "after": dict}}`: find; create with POST if absent; else merge `desired` over existing (only keys in `desired`), strip `_links` and `ROUTES[resource]["readonly"]`, compare, PUT to `item` only when different; `check_mode` never sends writes. 
  - `PpdmClient.remove(resource, key, value, check_mode=False) -> dict` (`{"changed": bool, "diff": ...}`), DELETE only if present.
  - `PpdmClient.wait_activity(activity_id: str, timeout: int, interval: int = 5) -> dict`: polls `/activities/{id}` until state in `{COMPLETED, FAILED, CANCELED}` (confirm the enum in the OpenAPI `Activity.state`), raises `PpdmError` on timeout.
  - `strip_readonly(resource: str, obj: dict) -> dict` (module-level, pure).
- [ ] **Step 1:** Tests: `test_ensure_creates_when_absent`, `test_ensure_no_put_when_identical` (second run, `changed=False`, zero write calls), `test_ensure_puts_when_different_and_strips_links`, `test_ensure_check_mode_reports_change_without_writing`, `test_find_one_duplicate_names_fails_with_both_ids`, `test_remove_absent_is_noop`, `test_wait_activity_returns_on_terminal_state`, `test_wait_activity_times_out`.
- [ ] **Step 2:** Run, expect FAIL. **Step 3:** implement. **Step 4:** run, expect PASS.
- [ ] **Step 5:** Commit `feat: idempotent ensure/remove and activity wait`.

### Task 5: Doc fragment, action group, schema-driven doc generation

**Files:**
- Create: `plugins/doc_fragments/ppdm.py`, `tools/schemas/_example.yml`, `tests/unit/tools/test_generate_docs.py`
- Modify: `tools/generate.py`, `meta/runtime.yml`, `.github/workflows/` (later task)

**Interfaces:**
- Produces: doc fragment `fjacquet.ppdm.ppdm` documenting `hostname, port, username, password, validate_certs, ca_path, timeout` consistently with `connection_argument_spec()`. `meta/runtime.yml` `action_groups: {ppdm: [<module names>]}` (module-defaults usable as `group/fjacquet.ppdm.ppdm`; verify with a tiny playbook test since the syntax is unconfirmed).
- Schema file shape (`tools/schemas/<module>.yml`): `module`, `resource`, `key` (default `name`), `kind` (`ensure|info|singleton|action`), `short_description`, `description`, `options: {name: {type, required, choices, description, no_log, default}}`, `examples`, `return`.
- `tools.generate.render_module_blocks(schema: dict) -> tuple[str, str]` returns the `DOCUMENTATION` text and the `argument_spec` source; CLI `uv run python tools/generate.py modules [--check]` rewrites text between `# BEGIN GENERATED` / `# END GENERATED` markers in each `plugins/modules/<module>.py`; `--check` exits 1 if any file would change.
- [ ] **Step 1:** Tests: `test_render_includes_extends_documentation_fragment`, `test_argument_spec_matches_documentation_options` (parse both, same option names/types/required), `test_check_mode_fails_on_drift`.
- [ ] **Step 2-4:** run FAIL, implement, run PASS. **Step 5:** commit `feat: schema-driven module docs and connection doc fragment`.

### Task 6: `api` module

**Files:**
- Create: `plugins/modules/api.py`, `tools/schemas/api.yml`, `tests/unit/modules/test_api.py`

**Interfaces:**
- Consumes: Tasks 3, 5. Options: `method` (GET|POST|PUT|PATCH|DELETE, default GET), `path` (must start with `/api/`), `query` (dict), `body` (dict), `all_pages` (bool, default true), `wait`/`wait_timeout` for responses that return an activity id. Returns `{changed, status, result}`.
- Behavior: GET auto-paginates when `all_pages` and the response has `content`/`page`; non-GET reports `changed=true`; non-GET in check mode is not sent (`changed=true`, `skipped_write=true`).
- [ ] **Step 1:** Tests: `test_get_paginates_all_pages`, `test_post_marks_changed`, `test_check_mode_does_not_send_post`, `test_path_must_start_with_api`, `test_http_error_fails_with_body`.
- [ ] **Step 2-4:** FAIL, implement (schema -> generate -> hand-written `main()`), PASS. **Step 5:** commit `feat: add api module`.

### Task 7: Info modules

**Files:**
- Create: `plugins/modules/{credential_info,inventory_source_info,storage_system_info,certificate_info}.py`, matching schemas, `tests/unit/modules/test_info_modules.py`

**Interfaces:**
- Consumes: Tasks 3-5. Common options: `name` (exact match, optional), `filter` (PPDM filter string), `id` (optional). Return `{changed: false, items: list[dict]}`; empty result is `[]`, not a failure. Credentials never return secrets (strip `password`/`privateKey`-like fields reported in the spec).
- [ ] **Step 1:** Tests per module (one parametrized): `test_info_returns_all_pages`, `test_info_empty_is_empty_list`, `test_info_by_name_builds_filter`, `test_credential_info_has_no_secret_fields`.
- [ ] **Step 2-4:** FAIL, implement via shared helper `info_main(schema_name)` in the module_utils, PASS. **Step 5:** commit `feat: add info modules for Lot 1 resources`.

### Task 8: Mutating modules (`credential`, `inventory_source`, `storage_system`)

**Files:**
- Create: the three modules, schemas, `tests/unit/modules/test_{credential,inventory_source,storage_system}.py`

**Interfaces:**
- Consumes: `PpdmClient.ensure/remove`. `credential`: `state present|absent`, `name`, `type`, `username`, `password` (`no_log`), key `name`. `inventory_source`: `state present|absent`, `name`, `type` (VCENTER, KUBERNETES, DATADOMAINSYSTEM, ...; take enum from the spec), `address`, `port`, `credential_id`, `trust_certificate`; key `name` (confirm uniqueness against the spec; fall back to `address`+`type` filter if names are not unique). `storage_system`: `present` only, updates an existing object by `name`, fails if absent.
- Each returns `{changed, object, diff}`; passwords never appear in `diff` (mask before returning).
- [ ] **Step 1:** Tests per module: create, idempotent re-run (no PUT), update on diff, check mode, absent when missing; `test_password_masked_in_diff`; `test_storage_system_missing_fails`.
- [ ] **Step 2-4:** FAIL, implement, PASS. **Step 5:** commit `feat: add credential, inventory_source and storage_system modules`.

### Task 9: Singleton modules (`eula`, `certificate`)

**Files:**
- Create: `plugins/modules/{eula,certificate}.py`, schemas, tests

**Interfaces:**
- `eula`: option `name` (choices `PPDM|TELEMETRY|data-manager`, default `PPDM`), `accepted` (bool); GET then PATCH `/api/v2/eulas/{name}` only if not already accepted. `certificate`: `state present|absent`, trust/acceptance of a host certificate; operations come from `/api/v2/certificates` (GET with `host`, `port`, `type=Host` query, POST, `PUT /{certId}`, DELETE) as the spec shows; the builder derives exact fields from the spec and bottkars' `accept_ppdm_host_certificate` and `add_ppdm_certificate_chain` roles.
- [ ] **Step 1:** Tests: `test_eula_already_accepted_no_patch`, `test_eula_accepts_when_not_accepted`, `test_eula_check_mode`, `test_certificate_idempotent`, `test_certificate_absent`.
- [ ] **Step 2-4:** FAIL, implement, PASS. **Step 5:** commit `feat: add eula and certificate modules`.

### Task 10: `bootstrap` role

**Files:**
- Create: `roles/bootstrap/{tasks/main.yml,defaults/main.yml,meta/main.yml,meta/argument_specs.yml,README.md}`

**Interfaces:**
- Consumes: Lot 1 modules. Variables prefixed `bootstrap_`: `bootstrap_hostname`, `bootstrap_username`, `bootstrap_password` (`no_log`), `bootstrap_wait_timeout` (default 3000), `bootstrap_eula_accept` (default false, must be explicit), `bootstrap_configuration` (dict, optional).
- Sequence: retry `fjacquet.ppdm.api` login-based readiness (`until` success, retries from timeout) -> accept EULA if `bootstrap_eula_accept` -> if `bootstrap_configuration` given: `PUT /api/v2/configurations/{id}` via `api` (id from `GET /api/v2/configurations`) -> poll `config-status` until `SUCCESS` (`until`, bounded). No port 14443 logic.
- [ ] **Step 1:** `uv run ansible-lint roles/bootstrap` passes (production profile). **Step 2:** `ansible-playbook --syntax-check` on an example in `docs/examples/bootstrap.yml`. **Step 3:** Commit `feat: add bootstrap role`. (No Molecule: needs a live PPDM.)

### Task 11: CI, changelog, docs, release gate

**Files:**
- Create: `.github/workflows/ci.yml`, `changelogs/fragments/lot1.yml`, `docs/examples/*.yml`; Modify: `README.md`, `CLAUDE.md`

- [ ] **Step 1:** CI jobs: `uv sync`, `ansible-lint`, `yamllint`, `python tools/generate.py routes && modules --check` then `git diff --exit-code`, `ansible-test sanity --docker` (or `--venv`) in the `ansible_collections` path, `uv run pytest`, `ansible-galaxy collection build`; publish on tag using secret `ANSIBLE_GALAXY_API_KEY` (document in README that the Galaxy `fjacquet` namespace and token must be created by the author first).
- [ ] **Step 2:** Run locally: `uv run ansible-test sanity` and `uv run pytest`; both must pass, including `validate-modules`.
- [ ] **Step 3:** README: install, auth via env/`module_defaults`, module list, "0.x until lab-validated" notice, unofficial disclaimer. Add an example per module.
- [ ] **Step 4:** `uv run antsibull-changelog release --version 0.1.0` produces `CHANGELOG.rst`; commit `chore: ci, docs and 0.1.0 changelog`.

---

## Self-review notes

- Spec coverage: client, per-resource version routing, pagination, error mapping, TLS defaults, idempotence/diff/check_mode, async wait, `api`, info modules, credential/inventory_source/storage_system/eula/certificate, bootstrap role, generator (routes + docs from one schema + drift check), uv, CI, build_ignore, pre-release gating, attribution. Lots 2 and 3 intentionally absent.
- Open for the executor to confirm against the spec while implementing: `Activity.state` terminal values, `inventory_source` uniqueness key, credential secret field names, exact certificate request bodies, `readOnly` flags per resource.
- Needs the author: GitHub repo name, Galaxy namespace and token.
