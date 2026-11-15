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
