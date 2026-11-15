# Design: `fjacquet.ppdm` Ansible collection for PowerProtect Data Manager 20.3.0

Date: 2026-11-15. Status: draft for approval.

## Intent and why

Automate PowerProtect Data Manager (PPDM) 20.3.0 through its REST API with a
clean, idempotent, documented Ansible collection. Used for the author's own
and client projects, and published publicly on GitHub and Ansible Galaxy.
This is the author's first Galaxy publication; the `fjacquet` Galaxy
namespace does not exist yet.

No official PPDM Ansible collection was found (Dell publishes collections for
PowerStore, PowerFlex, Unity, OpenManage; none for PPDM). The collection is
unofficial and not affiliated with Dell. Dell is only named as the product
vendor; no Dell branding.

## Prior art

- `bottkars/ansible_ppdm` (Karsten Bott, Dell evangelist, copying allowed by
  him per the author): ~70 `uri`-based roles and ~70 playbooks, API v2,
  last push 2024-05. Fast and field-proven for workflow coverage, but: no
  collection, no modules, no tests/docs, no pagination (silently truncates at
  the first 100 items), tolerant HTTP status lists that hide errors
  (`200,500`, `-1`), `validate_certs: false` hard-coded, token handled by hand.
  Only 2 of its 70 roles were read in depth; the others were scanned by URL and
  HTTP method. Its protection-policy roles call `/api/v2/protection-policies`,
  which does not exist in the 20.3.0 spec (see Constraints).
- `dellemc.networker` (`ansible-networker`): one module per resource with
  `state: get|create|delete|...`. Anti-pattern we avoid (see rules).

We reuse its workflow knowledge and endpoint ordering, ported into Python
modules, not copied YAML. Attribution in README and `NOTICE`; a short
confirmation message to the author of that repo is a courtesy to send, not a
blocker.

## Goals

- Complete, idempotent modules for the ~10 core workflows below, with full
  `DOCUMENTATION`/`EXAMPLES`/`RETURN`, `check_mode`, `--diff`.
- A generic escape hatch (`api`) so any of the ~480 documented endpoints is
  reachable before a dedicated module exists.
- Passes `ansible-test sanity` (incl. `validate-modules`), `ansible-lint`
  (production profile), unit tests; releasable to Galaxy with a changelog.
- Zero Python runtime dependencies beyond ansible-core.

## Non-goals

- Not one module per API resource (~190). Coverage grows with need.
- No integration with PPDM versions other than 20.3.0 in v1 (earlier 19.x/
  20.x may work through `api`; untested).
- No Dell-supported status; no use of Dell logos or the `dellemc` namespace.
- No role-per-API-call like bottkars. Roles only for real multi-step
  workflows (bootstrap).

## Anti-goals (failure even if it "works")

- Tolerating HTTP errors to make tasks look green.
- Modules that are not idempotent or that lie in `check_mode`.
- `state: get`-style multiplexing in a single module.
- Secrets in logs, or TLS verification off by default.
- Silent truncation of list results.

## Constraints and verified facts (from the 20.3.0 OpenAPI files)

- Three specs: `21200` (v1, 2 paths), `21201` (v2, 379 paths), `21202` (v3,
  99 paths). Auth: `POST /api/v2/login` -> `access_token` (JWT Bearer). Base
  URL `https://<host>:8443`.
- **API version is per resource.** In 20.3.0, `protection-policies`
  (list/create/get/update/delete) exists only under `/api/v3`; v2 keeps only
  `/api/v2/protection-policies/{id}/asset-assignments` and
  `.../asset-unassignments`. Same pattern likely for identity-providers,
  avamars, activities, copies. A generated `resource -> version -> path`
  table decides, never a global version.
- **Pagination.** List endpoints take `page` (1-based, default 1) and
  `pageSize` (default 100, max 10000), plus `filter` (e.g. `name eq "x"`,
  URL-encoded) and `orderby`. Response: `{content: [...], page: {number,
  size, totalElements, totalPages, ...}}`.
- **No unauthenticated readiness endpoint exists in the spec.** bottkars'
  `:443/#/fresh` probe is meaningless (URL fragments are never sent). Probe =
  retry `POST /login` (refused/5xx = not ready). Bootstrap progress =
  `GET /api/v2/configurations/{configurationId}/config-status` until
  `SUCCESS`. PPDM upgrade status lives on port 14443
  (`/upgrade/status`, taken from bottkars, not in the spec; unverified).
- PUT replaces the whole object; `_links` must be stripped from a GET result
  before it is sent back.
- Dev environment: `uv`. `ansible-test` only runs from a path of the form
  `.../ansible_collections/fjacquet/ppdm/`.
- Not verified: the exact `meta/runtime.yml` `action_groups` syntax (to be
  confirmed by a test, using the usual `group/fjacquet.ppdm.ppdm` convention);
  `ansible.module_utils.secrets.register_secret` is NOT used (version
  dependency, unnecessary: the token never leaves the module).

## Approaches considered

1. **Hand-written, ~15-20 modules (networker style).** High quality, ~10% API
   coverage, every PPDM update manual. Rejected as the only strategy.
2. **Fully generated, ~190 flat modules.** Total coverage but no
   idempotence, heavy sanity surface, poor quality for a public collection.
   Rejected.
3. **Hybrid (chosen by the author).** Shared client + ~10 hand-written
   idempotent modules + generic `api` module + a generator for the
   machine-derived parts (resource/version/path table, `argument_spec` and
   matching `DOCUMENTATION` fragments, coverage report).

## Design

### Identity
- Namespace/name: `fjacquet.ppdm`. License GPL-3.0-or-later. Python
  3.10+ (controller), `requires_ansible` = currently maintained ansible-core
  releases at scaffold time (2.16 is EOL; builder picks the floor). Repo root = collection root
  (`galaxy.yml` at root). Local `ansible-test`: symlink or checkout into
  `ansible_collections/fjacquet/ppdm/`.
- No `ppdm_` prefix on modules: FQCN already carries it.

### Layout
```
galaxy.yml  README.md  NOTICE  LICENSE  CLAUDE.md  pyproject.toml (uv)
meta/runtime.yml                 requires_ansible + action_groups
plugins/doc_fragments/ppdm.py    connection options docs
plugins/module_utils/ppdm.py     client (see below)
plugins/modules/*.py
roles/bootstrap/                 wait ready, EULA, config, certs
tools/generate.py                reads docs/openapi -> tables, specs, report
tests/unit/ tests/sanity/ tests/integration/ (manual)
changelogs/  docs/  .github/workflows/ci.yml
```
`galaxy.yml` `build_ignore` excludes `docs/superpowers/`, `tools/`, the
OpenAPI copies, `.venv`, tests data not needed in the artifact.

### Shared client (`module_utils/ppdm.py`)
- Uses `ansible.module_utils.urls.open_url` only (no `requests`).
- Connection args via doc fragment + `env_fallback`: `hostname`
  (`PPDM_HOSTNAME`), `port` (default 8443), `username`, `password`
  (`no_log`), `validate_certs` (**default true**), `ca_path`, `timeout`.
- Login once per module run, token in memory only.
- Version routing per resource from a generated table.
- `list_all()` paginates through `totalPages`; filters URL-encoded.
- Errors: non-2xx -> `fail_json(msg=..., status=..., body=<PPDM error body>)`.
  No tolerant status lists.
- Strips `_links` and read-only fields before PUT.
- `wait_activity(id, timeout)` polls `/activities/{id}` to a terminal state.
- An action group in `meta/runtime.yml` lets users set connection options
  once with `module_defaults`.

### Module rules
- Names: `<resource>` (mutating, `state: present|absent`), `<resource>_info`
  (read-only), action modules for verbs (`protection_policy_run`,
  `restore`...). **No `state: get`.**
- Idempotence: GET existing (by unique key, e.g. name) -> merge only
  user-supplied keys -> compare -> PUT/POST only if different. `check_mode`
  returns the correct `changed` without writing. `diff` returns before/after.
- Async: return the activity id; `wait` (bool) and `wait_timeout` options.
- All modules: FQCN-correct examples, full `RETURN`, `no_log` on secrets.

### Delivery in three lots (full design doc for lot N+1 is not needed now)
- **Lot 1 (foundation + bootstrap + inventory):** client, doc fragment,
  action group, generator, `api`, generic `info`-style reads, `eula`,
  `certificate`, `storage_system` (DD/DDVE), `inventory_source`
  (vCenter/K8s), `credential`, role `bootstrap`.
- **Lot 2 (protection):** `protection_policy` (v3), `protection_group`,
  `protection_rule`, asset assignment, `asset_info`.
- **Lot 3 (ops):** `restore`, `activity_info`, `alert_info`, `copy_info`,
  `smtp`, `upgrade`.
Module list is a proposal built from bottkars' real workflows; the author may
reorder per client need.

### Tooling and CI
- `uv`: `pyproject.toml` dev group (ansible-core, ansible-lint,
  antsibull-changelog, ansible-creator, pytest, molecule if roles need it).
  Run everything via `uv run`.
- Scaffold with `ansible-creator init collection fjacquet.ppdm`, then remove
  sample content; changelog via `antsibull-changelog`.
- CI (GitHub Actions): ansible-lint, yamllint, `ansible-test sanity`, unit
  tests with mocked `open_url`, collection build, publish on tag using a
  `ANSIBLE_GALAXY_API_KEY` secret. Integration tests (live PPDM) are
  manual/optional.
- Galaxy: author creates the `fjacquet` namespace by signing in to
  galaxy.ansible.com with GitHub (to confirm in the UI) and supplies the API
  token as a repo secret.

### Generator scope
`tools/generate.py` reads the three OpenAPI files and emits: the resource ->
version -> path table used by the client; `argument_spec` **and** the matching
`DOCUMENTATION` options for curated modules from one source (avoids
`validate-modules` drift); an API coverage report (endpoints with/without a
dedicated module). It does not emit finished modules.

## Decided by the author
- Hybrid approach; namespace `fjacquet.ppdm`; no Dell namespace; public
  Galaxy + GitHub; `uv`; modules without `ppdm_` prefix; `git init` for this
  repo.

## Left to the builder
- Exact option names per module, exact `argument_spec` details.
- Supported ansible-core / Python matrix at release time.
- Unit-test fixture strategy for the mocked client.
- Whether `bootstrap` needs Molecule (it requires a live PPDM; likely not).
- Order of modules inside a lot.

## Open items / not verified
- bottkars' remaining 68 roles read only by URL/method; mine them per module
  when implementing it.
- Galaxy namespace creation and name availability.
- `action_groups` syntax; PPDM upgrade status endpoint on :14443.
- No live PPDM available yet to the builder: acceptance depends on a lab.

## Calls made after the builder check (author may overrule)
- **OpenAPI inputs:** the three specs are NOT committed (Dell redistribution
  rights unknown). They live outside the repo; `tools/generate.py` takes the
  directory as an argument or `PPDM_OPENAPI_DIR`. The generated
  resource/version/path table IS committed (small, derived), so CI and
  contributors never need the specs.
- **Generator source of truth:** one hand-written YAML schema per curated
  module in `tools/schemas/<module>.yml` (options, types, docs, resource,
  unique key). The generator rewrites the `DOCUMENTATION` block and
  `argument_spec` inside the module file between marker comments; both are
  committed so `validate-modules` sees static strings. CI fails if the
  generator output differs from the committed files.
- **Read-only fields:** derived from OpenAPI `readOnly` flags into the
  generated table; `_links` always stripped.
- **Unique key and singletons:** per-module `key` in its schema (default
  `name`). Singleton resources (e.g. `eula`, SMTP) support `state: present`
  only.
- **`api` module:** takes method + path (not operationId), optional `query`
  and `body`; GET auto-paginates (`all_pages`, default true); non-GET always
  reports `changed: true`; in check mode non-GET calls are not sent.
- **`bootstrap` role:** thin wrapper over Lot 1 modules
  (login-retry readiness, `configurations`/`config-status`, EULA,
  certificate). Anything on port 14443 (upgrade) is deferred to Lot 3.
