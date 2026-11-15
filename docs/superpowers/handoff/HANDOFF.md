# Handoff: fjacquet.ppdm Lot 1 (2026-11-15)

State: branch `feat/lot1-foundation`, HEAD `e7f553f`, clean tree. 333 tests, ruff, `generate.py modules --check`,
validate-modules and pep8 green. Spec: `docs/superpowers/specs/2026-11-15-fjacquet-ppdm-collection-design.md`.
Plan: `docs/superpowers/plans/2026-11-15-ppdm-lot1-foundation.md` (tasks 1-10 done, plus added tasks 10a ruff, 10b hardening, S security).

Work was paused by a usage limit (weekly limit resets 2026-11-17 22:00 Europe/Zurich).

## Remaining, in order
1. **Task Q2** (security residuals): `task-q2-brief.md` in this folder. Nothing was started.
2. **Task Q** (quality/hygiene), from `audit-quality.md` sections 1-6 (no brief written yet): README (module list, install, auth, examples),
   galaxy.yml tags/homepage/documentation, `version_added: 0.1.0`, `no-smart-quotes` sanity ignore for docs/openapi,
   pylint test cleanup (`_` names, duplicate kwarg in test_inventory_source.py:66), `.ansible-lint` exclude_paths,
   `.gitignore` (.ansible/, .ruff_cache/), build_ignore (CLAUDE.md, pyproject.toml, uv.lock, .pre-commit-config.yaml, .ruff_cache, .github),
   RETURN samples/attributes/notes/seealso, SPDX headers, docstrings/type hints in ppdm.py, storage_system double GET.
3. **Task 11** (plan): GitHub Actions CI (ruff, ansible-lint, ansible-test sanity/units, build, publish on tag), `antsibull-changelog release --version 0.1.0`, release `0.1.0` pre-release.
4. Final whole-branch review (most capable model), then merge `feat/lot1-foundation` to `main`.

## Open decisions / not verified (need a live PPDM 20.3 lab)
- Certificate flow, `config-status`, PUT-replace semantics, nested `credentials` comparison, name case sensitivity, token/password echo in errors.
- Galaxy namespace `fjacquet` must be created by the author (galaxy.ansible.com, sign in with GitHub) and the API token stored as repo secret `ANSIBLE_GALAXY_API_KEY`; GitHub repo name assumed `fjacquet/ansible-ppdm`.
- A stale copy of the collection exists in `~/.ansible/collections/ansible_collections/fjacquet/ppdm` (made by ansible-lint) and can shadow the worktree: delete it, or set ANSIBLE_COLLECTIONS_PATH to a dir with only the worktree.
- `ansible-test` needs the worktree at `~/.cache/ppdm-ac/ansible_collections/fjacquet/ppdm` (see CLAUDE.md).
