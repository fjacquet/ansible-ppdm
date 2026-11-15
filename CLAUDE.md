# CLAUDE.md

Ansible collection `fjacquet.ppdm` for Dell PowerProtect Data Manager 20.3.0.
Unofficial, not affiliated with Dell. GPL-3.0-or-later.

## Constraints

- Zero runtime dependencies beyond ansible-core.
- Always run tools via `uv run` (dev deps live in `[dependency-groups] dev`).
- `galaxy.yml` `build_ignore` excludes `docs/superpowers/`, `docs/openapi/`, `tools/`, `.venv`, `.pytest_cache`, `.superpowers/`.
- `.superpowers/` is controller scratch space. Do not touch it.
- `requires_ansible` is `>=2.20.0` (oldest maintained ansible-core per the release matrix).

## Commands

Unit tests (plain pytest, from the repo root):

```
uv run pytest
```

`tests/unit/conftest.py` registers `ansible_collections.fjacquet.ppdm` to point at the repo root when it is not already importable, so tests can import `ansible_collections.fjacquet.ppdm.plugins...`. CI does not need a symlink.

Ansible test runs (`ansible-test` needs the cwd to be a physical `.../ansible_collections/fjacquet/ppdm/` path; a symlink is rejected because the cwd resolves to the real repo path). Use a git worktree outside the repo:

```
git worktree add --detach ~/.cache/ppdm-ac/ansible_collections/fjacquet/ppdm HEAD
cd ~/.cache/ppdm-ac/ansible_collections/fjacquet/ppdm
uv run --project ~/Projects/ansible-ppdm ansible-test units --python 3.13
```

The worktree only contains committed state. Refresh it after each commit:

```
git -C ~/.cache/ppdm-ac/ansible_collections/fjacquet/ppdm checkout --detach <sha>
```

Build check (tarball must not contain the excluded paths):

```
uv run ansible-galaxy collection build --force --output-path <scratch-dir>
```

## Layout

- `plugins/modules/`, `plugins/module_utils/`, `plugins/doc_fragments/` (`ppdm.py`: connection options, kept in sync with `connection_argument_spec()` by a test).
- `tools/schemas/<module>.yml`: single source of each module's DOCUMENTATION and argument_spec (see `_example.yml`). `uv run python tools/generate.py modules [--check]` rewrites the `# BEGIN GENERATED`/`# END GENERATED` block in `plugins/modules/<module>.py` (creates a skeleton if missing). Both outputs are committed.
- `meta/runtime.yml`: `requires_ansible` and `action_groups.ppdm`; each new module must be added to action_groups (a test enforces it).
- `changelogs/`: antsibull-changelog config and fragments.
- `docs/openapi/`: PPDM 20.3.0 OpenAPI specs (21200, 21201, 21202).
- `docs/superpowers/`: design spec and implementation plan (not shipped).
