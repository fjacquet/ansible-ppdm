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
    removed = {
        "protection_rule.action",
        "protection_rule.inventory_source_type",
        "protection_rule.condition_connector",
        "condition.operator",
        "protection_rule_run.inventory_source_type",
        "protection_rule_run.preview_action",
    }
    assert not removed & set(enums)


def test_schema_choices_match_enums():
    import yaml
    from ansible_collections.fjacquet.ppdm.plugins.module_utils._enums import ENUMS

    schemas = Path(__file__).resolve().parents[3] / "tools" / "schemas"
    pairs = {
        ("protection_rule", "action"): "rule.action_name",
        ("protection_rule", "variant"): "rule.variant",
        ("protection_rule", "scopes"): "rule.scope",
        ("protection_rule", "categories"): "rule.category",
        ("protection_rule_run", "action_name"): "rule_run.action_name",
        ("protection_rule_run", "object_subtypes"): "rule_run.object_subtype",
        ("discovery", "level"): "discovery.level",
        ("asset_info", "asset_type"): "asset.type",
        ("protection_group", "type"): "protection_group.type",
        ("protection_group", "subtype"): "protection_group.subtype",
        ("protection_group", "member_asset_type"): "protection_group.member_asset_type",
        ("protection_group", "backup_strategy"): "protection_group.backup_strategy",
        ("activity_action", "retry_options"): "activity.retry_option",
        ("alert_acknowledge", "acknowledge_state"): "alert.acknowledge_state",
        ("alert_info", "severity"): "alert.severity",
        ("alert_info", "category"): "alert.category",
        ("restore_plan", "fallback_strategy"): "restore_plan.fallback_strategy",
        ("restore_plan_run", "execution_type"): "restore_plan_run.execution_type",
        ("upgrade_package_info", "category"): "upgrade_package.category",
    }
    for (mod, opt), key in pairs.items():
        opts = yaml.safe_load((schemas / (mod + ".yml")).read_text())["options"]
        assert tuple(sorted(opts[opt]["choices"])) == ENUMS[key], (mod, opt)


def test_v3_rule_and_group_enums():
    enums, _unused = build_enums(SPECS)
    assert {"ASSIGN_PROTECTION_POLICY", "ASSIGN_RESOURCE_GROUP"} <= set(enums["rule.action_name"])
    assert enums["rule.scope"] == ("ASSET", "GENERAL", "POLICY")
    assert enums["rule.category"] == ("LIST_VIEW", "TREE_VIEW")
    assert "ADVANCED" in enums["rule.variant"] and "SIMPLE" in enums["rule.variant"]
    assert enums["rule_filter.object_type"] == ("ASSET", "COPY", "FILE", "FILEGROUP")
    assert enums["rule_filter.type"] == ("EXCLUDE", "INCLUDE")
    assert enums["rule_filter.operator"] == ("AND", "OR")
    assert "VMWARE_VIRTUAL_MACHINE" in enums["rule_filter.object_subtype"]
    assert "MATCH_REGEX" in enums["rule_condition.operator"]
    assert enums["rule_condition.logical_operator"] == ("AND", "OR")
    assert enums["rule_run.action_name"] == ("ASSIGN_PROTECTION_POLICY", "ASSIGN_RESOURCE_GROUP")
    assert "ORACLE_DATABASE" in enums["rule_run.object_subtype"]
    assert enums["protection_group.type"] == (
        "ORACLE_DATA_GUARD",
        "POWER_MAX_STORAGE_DIRECT_APPLICATION",
        "STORAGE_DIRECT_APPLICATION",
    )
    assert enums["protection_group.subtype"] == ("GENERIC", "MEDITECH")
    assert enums["protection_group.member_asset_type"] == ("ORACLE_DATABASE", "POWERSTORE_BLOCK", "POWER_MAX_BLOCK")
    assert "BACKUP_ALL" in enums["protection_group.backup_strategy"]


def test_lot4_enums():
    enums, _unused = build_enums(SPECS)
    assert enums["activity.retry_option"] == ("ALL", "FROM_FAILED_STEP", "NO_AUDIT_LOG", "VIRTUAL_GROUP")
    assert enums["alert.severity"] == ("CRITICAL", "INFORMATIONAL", "WARNING")
    assert enums["alert.category"] == tuple(sorted(enums["alert.category"])) and enums["alert.category"]
    assert enums["alert.acknowledge_state"] == ("ACKNOWLEDGED", "UNACKNOWLEDGED")
    assert enums["restore_plan.fallback_strategy"] == ("CANCEL_ON_FAILURE", "CONTINUE_ON_FAILURE")
    assert enums["restore_plan_run.execution_type"] == ("IMMEDIATELY", "SCHEDULE")
    assert enums["upgrade_package.category"] == ("ACTIVE", "HISTORY")
