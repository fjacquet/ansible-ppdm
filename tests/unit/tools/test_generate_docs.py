import ast
import re

import pytest
import yaml
from ansible_collections.fjacquet.ppdm.plugins.doc_fragments.ppdm import (
    ModuleDocFragment,
)
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import (
    connection_argument_spec,
)

from tools import generate

TQ = "'" * 3
SCHEMA = {
    "module": "widget",
    "resource": "widgets",
    "key": "name",
    "kind": "ensure",
    "short_description": "Manage widgets",
    "description": ["Create or remove widgets."],
    "options": {
        "name": {"type": "str", "required": True, "description": "Widget name."},
        "mode": {
            "type": "str",
            "choices": ["a", "b"],
            "default": "a",
            "description": "Mode.",
        },
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


def _setup(tmp_path, schema):
    s, m = tmp_path / "s", tmp_path / "m"
    s.mkdir()
    m.mkdir()
    (s / "widget.yml").write_text(yaml.safe_dump(schema))
    return s, m


@pytest.mark.parametrize("field", ["examples", "return"])
def test_triple_quote_rejected(field):
    with pytest.raises(ValueError, match="widget.*triple"):
        generate.render_generated_block({**SCHEMA, field: "a " + TQ + " b"})


def test_triple_quote_in_description_rejected():
    opts = {"name": {**SCHEMA["options"]["name"], "description": "it " + TQ + " breaks"}}
    with pytest.raises(ValueError, match="DOCUMENTATION"):
        generate.render_generated_block({**SCHEMA, "options": opts})


def test_trailing_quote_text_compiles():
    ast.parse(generate.render_generated_block({**SCHEMA, "examples": "x: 'y'", "return": "z: 'w'"}))


def test_missing_or_reordered_markers_clear_error(tmp_path):
    s, m = _setup(tmp_path, SCHEMA)
    generate.main(["modules"], s, m)
    path = m / "widget.py"
    good = path.read_text()
    for bad in (
        good.replace(generate.BEGIN, ""),
        good.replace(generate.END, ""),
        generate.END + "\n" + good.replace(generate.END, ""),
    ):
        path.write_text(bad)
        with pytest.raises(ValueError, match="widget.py.*markers"):
            generate.update_module_text(bad, SCHEMA, str(path))
        assert generate.main(["modules", "--check"], s, m) == 2
        assert generate.main(["modules"], s, m) == 2


def test_alias_round_trip():
    opts = {
        **SCHEMA["options"],
        "name": {**SCHEMA["options"]["name"], "aliases": ["n"]},
    }
    doc, src = generate.render_module_blocks({**SCHEMA, "options": opts})
    assert yaml.safe_load(doc)["options"]["name"]["aliases"] == ["n"]
    assert _spec(src)["name"]["aliases"] == ["n"]


def test_unknown_option_key_fails_loudly():
    opts = {"name": {**SCHEMA["options"]["name"], "suboptions": {}}}
    with pytest.raises(ValueError, match="widget.*name.*suboptions"):
        generate.render_module_blocks({**SCHEMA, "options": opts})


def _env_names(text):
    return set(re.findall(r"E\((PPDM_\w+)\)", text))


def test_fragment_env_and_choices_match_spec():
    opts = yaml.safe_load(ModuleDocFragment.DOCUMENTATION)["options"]
    for name, s in connection_argument_spec().items():
        assert opts[name].get("choices") == s.get("choices")
        spec_env = set(s["fallback"][1]) if "fallback" in s else set()
        assert _env_names(" ".join(opts[name]["description"])) == spec_env, name


def test_env_name_mismatch_detected():
    mutated = ModuleDocFragment.DOCUMENTATION.replace("PPDM_HOSTNAME", "PPDM_HOST")
    opts = yaml.safe_load(mutated)["options"]
    assert _env_names(" ".join(opts["hostname"]["description"])) != set(
        connection_argument_spec()["hostname"]["fallback"][1]
    )


def test_generated_block_is_wrapped_in_fmt_off_on():
    lines = generate.render_generated_block(SCHEMA).splitlines()
    assert lines[:2] == [generate.BEGIN, "# fmt: off"]
    assert lines[-2:] == ["# fmt: on", generate.END]


@pytest.mark.parametrize("key", ["module", "short_description", "description", "examples", "return"])
def test_missing_schema_key_names_file_and_key(tmp_path, capsys, key):
    s, m = _setup(tmp_path, {k: v for k, v in SCHEMA.items() if k != key})
    assert generate.main(["modules"], s, m) == 2
    err = capsys.readouterr().err
    assert "widget.yml" in err and repr(key) in err


@pytest.mark.parametrize("key", ["type", "description"])
def test_missing_option_key_names_file_option_and_key(tmp_path, capsys, key):
    opts = {"name": {k: v for k, v in SCHEMA["options"]["name"].items() if k != key}}
    s, m = _setup(tmp_path, {**SCHEMA, "options": opts})
    assert generate.main(["modules"], s, m) == 2
    err = capsys.readouterr().err
    assert "widget.yml" in err and "name" in err and repr(key) in err


def test_module_name_must_match_file_name(tmp_path, capsys):
    s, m = _setup(tmp_path, {**SCHEMA, "module": "gadget"})
    assert generate.main(["modules"], s, m) == 2
    assert "widget.yml" in capsys.readouterr().err and not (m / "gadget.py").exists()


def test_skeleton_has_no_coding_line_or_noqa():
    text = generate.module_skeleton(SCHEMA)
    assert "coding:" not in text and "noqa" not in text
    ast.parse(text)


def test_long_choices_are_wrapped_one_per_line_and_parse():
    choices = [f"CHOICE_NUMBER_{i:03d}" for i in range(12)]
    opts = {"mode": {"type": "str", "choices": choices, "description": "Mode."}}
    _, src = generate.render_module_blocks({**SCHEMA, "options": opts})
    ast.parse(src)
    assert all(f"            '{c}',\n" in src for c in choices)
    assert _spec(src)["mode"]["choices"] == choices
