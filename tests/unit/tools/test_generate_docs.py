import ast

import yaml

from tools import generate
from ansible_collections.fjacquet.ppdm.plugins.doc_fragments.ppdm import ModuleDocFragment
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import connection_argument_spec

SCHEMA = {
    "module": "widget",
    "resource": "widgets",
    "key": "name",
    "kind": "ensure",
    "short_description": "Manage widgets",
    "description": ["Create or remove widgets."],
    "options": {
        "name": {"type": "str", "required": True, "description": "Widget name."},
        "mode": {"type": "str", "choices": ["a", "b"], "default": "a", "description": "Mode."},
        "secret": {"type": "str", "no_log": True, "description": "A secret."},
    },
    "examples": "- name: x\n  fjacquet.ppdm.widget:\n    name: w\n",
    "return": "{}\n",
}


def _spec(src):
    return eval(src.split("=", 1)[1], {"dict": dict})  # trusted: our own generator output


def test_render_includes_extends_documentation_fragment():
    doc, _ = generate.render_module_blocks(SCHEMA)
    assert yaml.safe_load(doc)["extends_documentation_fragment"] == ["fjacquet.ppdm.ppdm"]


def test_argument_spec_matches_documentation_options():
    doc, src = generate.render_module_blocks(SCHEMA)
    opts = yaml.safe_load(doc)["options"]
    spec = _spec(src)
    assert set(opts) == set(spec)
    for name, o in opts.items():
        assert o["type"] == spec[name]["type"]
        assert o.get("required", False) == spec[name].get("required", False)
        assert o.get("default") == spec[name].get("default")
        assert o.get("choices") == spec[name].get("choices")
    assert spec["secret"]["no_log"] is True


def test_fragment_matches_connection_argument_spec():
    opts = yaml.safe_load(ModuleDocFragment.DOCUMENTATION)["options"]
    spec = connection_argument_spec()
    assert set(opts) == set(spec)
    for name, o in opts.items():
        assert o["type"] == spec[name]["type"]
        assert o.get("required", False) == spec[name].get("required", False)
        assert o.get("default") == spec[name].get("default")


def test_check_mode_fails_on_drift(tmp_path):
    schemas = tmp_path / "schemas"
    mods = tmp_path / "modules"
    schemas.mkdir()
    mods.mkdir()
    (schemas / "widget.yml").write_text(yaml.safe_dump(SCHEMA))
    (schemas / "_skipped.yml").write_text(yaml.safe_dump({**SCHEMA, "module": "skipped"}))
    assert generate.main(["modules", "--check"], schemas, mods) == 1  # file missing
    assert generate.main(["modules"], schemas, mods) == 0
    assert not (mods / "skipped.py").exists()
    assert generate.main(["modules", "--check"], schemas, mods) == 0
    path = mods / "widget.py"
    path.write_text(path.read_text().replace("Manage widgets", "Tampered"))
    assert generate.main(["modules", "--check"], schemas, mods) == 1
    assert generate.main(["modules"], schemas, mods) == 0
    assert "Manage widgets" in path.read_text()
    assert generate.main(["modules", "--check"], schemas, mods) == 0


def test_generated_module_compiles_and_keeps_hand_code(tmp_path):
    schemas = tmp_path / "s"
    mods = tmp_path / "m"
    schemas.mkdir()
    mods.mkdir()
    (schemas / "widget.yml").write_text(yaml.safe_dump(SCHEMA))
    generate.main(["modules"], schemas, mods)
    path = mods / "widget.py"
    path.write_text(path.read_text() + "\n# hand written\n")
    generate.main(["modules"], schemas, mods)
    text = path.read_text()
    assert text.endswith("# hand written\n")
    ast.parse(text)
