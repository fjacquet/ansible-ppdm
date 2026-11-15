# Quality audit, fjacquet.ppdm @ 7699dcc (feat/lot1-foundation)

Read-only. Worktree `~/.cache/ppdm-ac/.../fjacquet/ppdm` detached at 7699dcc. Docker down, so sanity ran locally on Python 3.13.
Raw sanity output: `/private/tmp/claude-501/-Users-fjacquet-Projects-ansible-ppdm/83d0e71b-878a-49b1-83b3-483968f10517/scratchpad/sanity.txt`.
Skills used: `ansible-good-practices:ansible-good-practices` and `ansible-zen:ansible-zen` were both invoked (loaded). I did not run the ansible-know MCP module checks or any auto-fix (read-only). The review itself was done manually against the CoP rules.

Severity: B = blocker for a Galaxy release, S = should fix, N = nice to have.

## 1. Sanity (22 of 24 tests pass, validate-modules passes)

Failed: `no-smart-quotes`, `pylint`.

- B `no-smart-quotes`: `docs/openapi/21201-20.3.0.json:1:1386863` contains a Unicode quote. ansible-test scans every file in the collection, and `build_ignore` does not help. Fix: add `tests/sanity/ignore-2.22.txt` (and the other supported core versions) with `docs/openapi/21201-20.3.0.json no-smart-quotes`, then re-run to confirm the entry is accepted. If it is not, ASCII-fold that character in the spec.
- S `pylint` `repeated-keyword`: `tests/unit/modules/test_inventory_source.py:66:10`, "multiple values for keyword argument 'address'". This is a real bug in the test call, not a naming issue. Fix: remove the duplicate kwarg.
- S `pylint` `disallowed-name` ("_"), 30 hits. This is the known deferred item.
  - `tests/unit/module_utils/test_ppdm_ensure.py`: 23 hits (lines 184-204 among them)
  - `tests/unit/modules/test_info_modules.py:31` (2)
  - `tests/unit/tools/test_generate_docs.py:43,219` (2)
  - `tests/unit/conftest.py` (1), `tests/unit/helpers.py` (1), `tests/unit/module_utils/test_ppdm_client.py` (1)
  - Fix: rename `_` to `unused`/`dummy`, or add a pylint ignore entry in `tests/sanity/ignore-*.txt`.
  - The first 5 lines of the raw output were truncated, so see `sanity.txt` for exact line numbers of the 1-hit files.

## 2. ansible-lint --profile production (17 failures; the profile reached was "min")

- B `galaxy[no-changelog]` `galaxy.yml:1`: there is no `CHANGELOG.rst` or `changelogs/changelog.yaml`. Only `changelogs/config.yaml` and an empty `fragments/.gitkeep` exist. Fix: add a release-summary fragment, run `antsibull-changelog release`, and commit the generated `CHANGELOG.rst` and `changelog.yaml`.
- B `galaxy[tags]` and `galaxy[tags-format]` `galaxy.yml:1`: `data-protection` is an invalid tag (tags must be alphanumeric), and none of the required tags is present. Fix: `tags: [storage, infrastructure, tools, dell, powerprotect, backup]`. Valid-set tags are `application, cloud, database, eda, infrastructure, linux, monitoring, networking, security, storage, tools, windows`.
- S `meta-runtime[unsupported-version]` `meta/runtime.yml:1`: lint's accepted list tops out at `>=2.19.0`, but `requires_ansible: ">=2.20.0"` is intentional per CLAUDE.md. This is a lint-data lag. Fix: either set `>=2.19.0` if the collection actually supports it, or silence the rule in `.ansible-lint` with a comment explaining why.
- S `yaml[line-length]` x13 in `tools/schemas/*.yml`: `certificate.yml:9,10,13,38`, `certificate_info.yml:17`, `credential.yml:21,42`, `credential_info.yml:18`, `inventory_source.yml:22,38`, `inventory_source_info.yml:17`, `storage_system.yml:32`, `storage_system_info.yml:17`. `tools/` is not shipped. Fix: add `.ansible-lint` with `exclude_paths: [tools/, docs/openapi/, .superpowers/]`.
- N Environment: ansible-lint also warned that a second copy of `fjacquet.ppdm` 0.1.0 exists in `~/.ansible/collections/ansible_collections` (an installed copy that shadows the worktree). Remove it so audits do not read stale code.
- Role `roles/bootstrap`: no violations.

## 3. Good practices (CoP), manual review plus the skill's rule set

PASS: FQCN everywhere, `bootstrap_` prefixed variables, `__bootstrap_` internal vars, `meta/argument_specs.yml` present and complete (`no_log` set on the password), `defaults/main.yml` free of dangerous defaults, bootstrap-prefixed tags, check mode honoured in the role and the modules, and the example playbook passes `ansible-playbook --syntax-check`.

- B Module docs: every module has `version_added: 1.0.0` while `galaxy.yml` is `0.1.0`. This is wrong in the published docs. Fix: set `version_added: 0.1.0` in `tools/schemas/*.yml` and regenerate with `uv run python tools/generate.py modules`.
- S RETURN blocks: no `sample` and no `contains` for dict returns (`certificate`, `credential`, `eula`, `inventory_source`, `storage_system`, `diff`, `activity`, `result`). `returned: success` is fine. Fix: add samples plus `contains` for `diff` (`before`/`after`).
- S No `attributes:` (check_mode, diff_mode support) and no `notes:` (for example the PPDM 20.3.0 target, shallow merge, secrets write-only), and no `seealso:`. Fix: add `ansible.builtin.uri` and the Dell PPDM REST API docs as seealso, plus `attributes: check_mode/diff_mode: support: full`, ideally through a shared `attributes` doc fragment.
- S No CI: `.github/` does not exist. Fix: add a workflow running `ruff`, `ansible-test sanity/units` and `ansible-lint`, and `ansible-galaxy collection build` on tag.
- S `.gitignore`: `.ansible/` is missing (ansible-lint creates it in the repo root). Add `.ansible/`. Also add `.ruff_cache/` for safety, even though ruff writes its own `.gitignore` inside the cache directory.
- S No role tests (no molecule scenario or integration targets); only unit tests of argument_specs.
- N Role `roles/bootstrap/meta/main.yml`: `platforms: GenericLinux` is not meaningful for a REST-only role. Add `role_name`/`namespace` only if it is ever published standalone.
- N Module headers use the legacy `# GNU General Public License v3.0+ (see COPYING ...)` line but there is no `COPYING` file (the file is `LICENSE`). Fix: add `# SPDX-License-Identifier: GPL-3.0-or-later`.

## 4. Zen of Ansible (modules, role, docs). Score 7.5 out of 10

Strengths: schema-generated docs and argument specs give one source of truth, shallow and obvious module interfaces, sane defaults, and good error messages.

- S Principles 1/2/16 (Ansible is not Python, hard to explain): `roles/bootstrap/tasks/main.yml:21` (`__bootstrap_retries` ceil/max Jinja) and `:70-73` (`dict2items | rejectattr | items2dict | combine`) are hard to read. Fix: compute the retry count as `bootstrap_wait_timeout // bootstrap_wait_delay`, and let the config body be built by a small module or by a `combine` plus `dict2items` filter step.
- S Principles 3/15: the role does a 4-task wait/fail dance plus 3 fail tasks for config. Fix: let `fjacquet.ppdm.api` grow a `wait_for` readiness option, or put the polling into a dedicated module.
- N Principle 12 (convention over configuration): `eula` has a lower-case `data-manager` choice among upper-case ones (`plugins/modules/eula.py`, ARGUMENT_SPEC `name` choices). Document why, or normalize.
- N `credential_info`/other info modules: the `id` description says "a 404 also happens when this PPDM version does not support the endpoint", which is confusing. Reword.

## 5. Collection hygiene

- B README (`README.md`, 17 lines): says "No modules are published yet" while 10 modules and a role exist. It has no module list, install instructions (`ansible-galaxy collection install`), authentication/env vars (`PPDM_HOSTNAME`/`PPDM_USERNAME`/`PPDM_PASSWORD`/`PPDM_PORT`), `module_defaults` group example, requirements (ansible-core >= 2.20), or role usage. The unofficial notice and the bottkars attribution are present and consistent with `NOTICE`. Fix: expand the README (module table, install, auth, 2 examples, bootstrap role, support/issue link).
- S `galaxy.yml`: missing `homepage` and `documentation` (repository and issues are present; version 0.1.0, license, description and tags are otherwise fine apart from the tags problem in section 2). Fix: add `homepage` (the repo URL) and `documentation` (the repo README or docs URL).
- S `build_ignore` is incomplete. I built the tarball into the scratchpad. It correctly excludes `docs/openapi`, `docs/superpowers`, `tools`, `.superpowers` and `.venv`. It does include:
  - `CLAUDE.md`, `pyproject.toml`, `uv.lock`, `.pre-commit-config.yaml`
  - `.ruff_cache/` (49 entries, only present on a dev machine, but add it)
  - `tests/unit/*` (acceptable for a collection, but `conftest.py` rewires imports)
  - Fix: add `CLAUDE.md`, `pyproject.toml`, `uv.lock`, `.pre-commit-config.yaml`, `.ruff_cache`, `.ansible`, `.github` to `build_ignore`.
- S `meta/runtime.yml`: `requires_ansible` OK and `action_groups.ppdm` lists all 10 modules (matches `plugins/modules/`, also enforced by `tests/unit/test_runtime_groups.py`). Nothing to fix beyond the lint note in section 2.
- OK: LICENSE (GPL-3.0) and NOTICE are consistent with `galaxy.yml` license. `docs/examples/bootstrap.yml` passes `ansible-playbook --syntax-check`. `uv run ruff check .` is clean. The repo working tree stayed clean (`git status` empty; only the worktree got `tests/output/`).
- N `changelogs/config.yaml` title is "Fjacquet Ppdm Collection". Change it to "fjacquet.ppdm Collection".

## 6. Python quality (`plugins/`)

- S `plugins/modules/inventory_source.py` (the `desired.update(p["config"] or {})` line) and `plugins/modules/storage_system.py` (same pattern): `config` can overwrite `name`/`type`, changing the lookup key that `ensure()` reads via `desired[key]`. Fix: apply config first and then the explicit options, or reject keys that collide with named options.
- S `storage_system.py` calls `client.find_one(...)` and then `client.ensure(...)`, which repeats `find_one`. That is a double GET and a race window. Fix: add an `ensure(..., create=False)` flag so it fails when the object is missing.
- S Missing docstrings and type hints on public helpers in `plugins/module_utils/ppdm.py`: `strip_readonly` (:24), `filter_eq` (:29), `PpdmError` (:38), `PpdmClient.login` (:79), `request` (:88), `list_all` (:160), `find_one` (:174), `ensure` (:191, has a one-line docstring only), `remove` (:242), `connection_argument_spec` (:281), `fail_from` (:298), `client_from_module` (:302). Add one-line docstrings and type hints. `from __future__ import annotations` is already in place.
- N `info_main` in `module_utils/ppdm.py:320-347` calls the private `client._route` (:332) and has the `filter` parameter shadowing the builtin in `list_all` (:160). Rename the parameter to `filter_expr` (the API param name stays `filter`) and expose a public `get_one`.
- N Duplicated boilerplate: `AnsibleModule(argument_spec=dict(connection_argument_spec(), **ARGUMENT_SPEC), supports_check_mode=True, ...)` is repeated in 6 modules, and credential/inventory_source/storage_system share the pattern `desired = {...}; filter None; ensure/remove; exit_json(changed, <obj>, diff)`. A small `ensure_main(resource, key, build_desired, secret_keys)` in `module_utils` would cut ~60 lines. Not a blocker.
- N Inconsistent error handling: `certificate.py` and `eula.py` call `module.fail_json` inside the `try` (works because fail_json raises SystemExit, but mixes two styles with `PpdmError`). Prefer raising `PpdmError` and letting `fail_from` handle it.
- N `_mask` is shallow (`ppdm.py:34`): nested secrets inside `config` are not masked. Documented for `storage_system` only; add the same warning to `inventory_source`.
- OK: no import-time side effects (login happens in `client_from_module`; `_routes.py` is a static dict), Python 3.10 compatible (no `match`, no 3.11+ syntax, annotations are deferred), the `_scrub` of the password on error paths is good, and no dead code was found by ruff.

## Totals

Blocker 5, should fix 17, nice to have 10 (counted per bullet above, grouped duplicates counted once).

Top 5: (1) README stale and incomplete; (2) no changelog (`galaxy[no-changelog]`); (3) galaxy tags invalid/missing; (4) `version_added: 1.0.0` vs collection 0.1.0; (5) sanity `no-smart-quotes` on `docs/openapi/21201-20.3.0.json`.
