from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_action_group_lists_every_module():
    group = yaml.safe_load((ROOT / "meta" / "runtime.yml").read_text())["action_groups"]["ppdm"]
    modules = {p.stem for p in (ROOT / "plugins" / "modules").glob("*.py") if p.stem != "__init__"}
    assert modules <= set(group), f"add to meta/runtime.yml action_groups.ppdm: {sorted(modules - set(group))}"
