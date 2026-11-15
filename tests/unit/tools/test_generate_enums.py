from pathlib import Path

from tools.generate import build_enums, main, render_enums

SPECS = Path(__file__).resolve().parents[3] / "docs" / "openapi"
ENUMS_FILE = Path(__file__).resolve().parents[3] / "plugins" / "module_utils" / "_enums.py"


def test_policy_asset_types_cover_fifteen_variants():
    enums, _required = build_enums(SPECS)
    types = enums["protection_policy.asset_type"]
    assert len(types) == 15
    assert {"VMWARE_VIRTUAL_MACHINE", "FILE_SYSTEM", "ORACLE_DATABASE", "KUBERNETES"} <= set(types)


def test_other_enums_and_required_keys():
    enums, required = build_enums(SPECS)
    assert "BACKUP" in enums["objective.type"]
    assert "CENTRALIZED" in enums["protection_policy.purpose"]
    assert "DataCopies" in enums["discovery.level"]
    assert enums["protection_rule.action"] == ("MOVE_TO_GROUP",)
    assert "VMWARE_VIRTUAL_MACHINE" in enums["protection_rule.inventory_source_type"]
    assert "type" in required


def test_output_sorted_and_deterministic():
    enums, required = build_enums(SPECS)
    assert all(v == tuple(sorted(v)) for v in enums.values())
    assert list(enums) == sorted(enums)
    assert render_enums(enums, required) == render_enums(*build_enums(SPECS))


def test_committed_file_matches_and_check_flags_tamper(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.generate.ENUMS_FILE", tmp_path / "_enums.py")
    (tmp_path / "_enums.py").write_text(ENUMS_FILE.read_text())
    assert main(["enums", "--check"]) == 0
    (tmp_path / "_enums.py").write_text(ENUMS_FILE.read_text() + "# tampered\n")
    assert main(["enums", "--check"]) == 1


def test_rule_enums():
    enums, _unused = build_enums(SPECS)
    assert enums["protection_rule.condition_connector"] == ("AND", "NONE", "OR")
    assert "EQUALS" in enums["condition.operator"] and len(enums["condition.operator"]) == 15
    assert "DR" in enums["protection_rule_run.inventory_source_type"]
    assert enums["protection_rule_run.preview_action"] == ("CREATE", "EDIT")


def test_schema_choices_match_enums():
    import yaml
    from ansible_collections.fjacquet.ppdm.plugins.module_utils._enums import ENUMS

    schemas = Path(__file__).resolve().parents[3] / "tools" / "schemas"
    pairs = {
        ("protection_rule", "action"): "protection_rule.action",
        ("protection_rule", "inventory_source_type"): "protection_rule.inventory_source_type",
        ("protection_rule", "condition_connector"): "protection_rule.condition_connector",
        ("protection_rule_run", "inventory_source_type"): "protection_rule_run.inventory_source_type",
        ("protection_rule_run", "preview_action"): "protection_rule_run.preview_action",
        ("discovery", "level"): "discovery.level",
    }
    for (mod, opt), key in pairs.items():
        opts = yaml.safe_load((schemas / (mod + ".yml")).read_text())["options"]
        assert tuple(sorted(opts[opt]["choices"])) == ENUMS[key], (mod, opt)
