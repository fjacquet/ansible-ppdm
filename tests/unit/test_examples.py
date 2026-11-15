import json
import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "docs" / "examples"
README = (EXAMPLES / "README.md").read_text()
FILES = sorted(EXAMPLES.glob("*.yml"))
DISCLAIMER = "Not yet validated against a live PPDM"
TASK_KEYWORDS = {
    "name", "when", "register", "loop", "loop_control", "no_log", "vars", "block", "rescue", "always",
    "changed_when", "failed_when", "until", "retries", "delay", "tags", "check_mode", "module_defaults",
    "environment", "delegate_to", "run_once", "ignore_errors", "args", "with_items", "notify",
}  # fmt: skip

ALL_SOURCES = """
1.0-playbook_configure_ppdm.yml
1.0-playbook_wait_ready.yml
1.1-playbook_get_ppdm_config.yml
100.0_list_agents.yml
100.1_download_agents.yml
100.2_set_dns_for_agents.yaml
100.3_playbook_copy_and_deploy_windows_agent.yaml
100.3_set_ip_for_agents.yaml
100.4_create_whitelistentry.yaml
100.4_create_whitelistentry_from_addressquery.yaml
100.5_get_agent_registration_status.yaml
100.6_get_whitelist.yaml
100.8_delete_whitelistentry.yaml
100.9_playbook-uninstall-windows-agent.yaml
110.0_get_protection_policies.yaml
110.4_playbook_start_policy.yaml
120.0_ensure_mssql_aag_local_user.yaml
120.1_playbook_add_exchange_policy.yaml
120.1_playbook_add_fs_policy.yaml
120.1_playbook_add_mssql_policy.yaml
120.2_playbook_add_assets_to_policy.yaml
120.3_playbook_start_policy.yaml
130.1_playbook_rbac_add_k8s_to_ppdm.yaml
130.2_playbook_add_k8s_policy_and_rule.yaml
130.3_playbook_start_k8s_discoveries_by_query.yaml
130.4_playbook_start_k8s_discoveries.yaml
130.4_playbook_start_k8s_policy.yaml
2.0-playbook_set_csm.yml
2.0-playbook_set_ddve.yml
2.0-playbook_test_credentials.yml
2.0-playbook_test_unassigned_credentials.yml
2.0-playbook_test_unassigned_credentials_id.yml
2.1-playbook_set_vsphere.yml
2.2-playbook_set_cdra_disabled.yml
2.2-playbook_set_cdra_enabled.yml
2.3-playbook_configure_cloud_dr_account.yml
2.3-playbook_updarte_cloud_dr_account.yml
2.4-playbook_set_cloud_dr_target.yml
2.5-playbook_set_cdrs_deployment.yml
2.6-playbook_get_cdrs_deployment.yml
2.7-playbook_delete_cdrs_deployment.yml
3.0-playbook_get_sdr.yml
3.0-playbook_set_sdr.yml
3.0-playbook_set_sdr_existing_unit.yml
3.1-playbook_set_smtp.yml
30.0-playbook_get_assets.yml
30.1-playbook_get_vm_asset_copies.yml
30.1-playbook_search_vm_asset_by_name.yml
30.2-playbook_get_k8s_asset_copies.yml
31.1-playbook_get_activities.yml
40.1-playbook_restore_vm_asset_copies.yml
40.2-playbook_restore_k8s_asset_copies.yml
9.0-playbook_replace_certs.yml
9.1-playbook_replace_license.yml
9.10-playbook_get_password_policy.yml
9.11-playbook_update_password_policy_age.yml
9.12-playbook_set_k8s_controller_config.yml
9.2-playbook_vib_details.yml
9.9-playbook_delete_ppdm_update_package.yml
9.9-playbook_get_ppdm_update_package_active.yml
9.9-playbook_get_ppdm_update_package_history.yml
9.9-playbook_install_update_ppdm.yml
9.9-playbook_precheck_update_ppdm.yml
9.9-playbook_upload_update_ppdm.yml
9.9-playbook_upload_update_ppdm_native.yml
99-playbook_upgrade_state.yml
99_get_data_domain.yml
99_get_inventory.yml
99_playbook_get_components copy.yml
99_playbook_get_components.yml
99_playbook_get_k8s_info.yml
99_re-ip_dd_after_headswap.yml
playbook_add_k8s.yml
playbook_get_k8s_policy.yml
playbook_get_rule.yml
playbook_rbac_add_k8s_to_ppdm.yml
playbook_rbac_add_k8s_to_ppdm_reg_cred.yml
playbook_rbac_add_k8s_to_ppdm_reg_cred_assetsource_enable.yml
playbook_set_k8s_root_cert.yml
playbook_start_k8s_discoveries.yml
ppdm-restore-2022.10.15-002.yml
scratch.yml
scratch_check_update_state.yml
scratch_create_flr_session.yml
scratch_get_asset_setings.yml
scratch_get_flr.yml
scratch_get_flr_sessions.yml
scratch_k8s_info.yml
time.yml
xxx_restore.yaml
""".strip().splitlines()
# The only categories allowed in the "Not converted" table.
SKIPPED_BY_REASON = {
    "windows agent or host helper": [
        "100.1_download_agents.yml",
        "100.3_playbook_copy_and_deploy_windows_agent.yaml",
        "100.9_playbook-uninstall-windows-agent.yaml",
        "120.0_ensure_mssql_aag_local_user.yaml",
    ],
    "update package upload": ["9.9-playbook_upload_update_ppdm.yml", "9.9-playbook_upload_update_ppdm_native.yml"],
    "port 14443 poller": ["99-playbook_upgrade_state.yml", "scratch_check_update_state.yml"],
    "author lab re-ip": ["99_re-ip_dd_after_headswap.yml"],
    "scratch or experiment": [
        "scratch.yml",
        "scratch_create_flr_session.yml",
        "scratch_get_asset_setings.yml",
        "scratch_get_flr_sessions.yml",
        "scratch_get_flr.yml",
        "scratch_k8s_info.yml",
        "time.yml",
        "xxx_restore.yaml",
        "ppdm-restore-2022.10.15-002.yml",
    ],
}
SKIPPED = [name for names in SKIPPED_BY_REASON.values() for name in names]

DESTRUCTIVE = {
    "40-restore-vm-copy.yml": "restore_confirm",
    "41-restore-k8s-copy.yml": "restore_confirm",
    "50-disable-cloud-dr-component.yml": "cloud_dr_confirm",
    "53-deploy-cloud-dr-server.yml": "cloud_dr_confirm",
    "55-delete-cloud-dr-server.yml": "cloud_dr_confirm",
    "89-set-local-user-setting.yml": "local_user_setting_confirm",
    "90-replace-certificate.yml": "cert_confirm",
    "91-set-license.yml": "license_confirm",
    "94-install-update-package.yml": "update_confirm",
    "95-delete-update-package.yml": "update_confirm",
    "101-approve-agent-ips.yml": "whitelist_approve_confirm",
    "102-delete-whitelist-entries.yml": "whitelist_confirm",
    "104-approve-agents-by-hostname.yml": "whitelist_approve_confirm",
    "132-add-k8s-policy-and-rule.yml": "rule_exec_confirm",
    "134-trust-kubernetes-root-certificate.yml": "certificate_trust_confirm",
    "135-set-kubernetes-controller-config.yml": "inventory_update_confirm",
}
# Writing examples left without a confirm guard on purpose; the README gives the reason.
NOT_GUARDED = {"24", "27", "51", "111"}
SECRET_RE = re.compile(r"password|token|license_key|privatekey|secretkey|userkey|secret|\"key\":", re.I)


def _walk(tasks):
    for task in tasks:
        yield task
        for section in ("block", "rescue", "always"):
            yield from _walk(task.get(section, []))


def _tasks(path):
    for play in yaml.safe_load(path.read_text()):
        if "roles" in play:
            raise AssertionError(f"{path.name}: roles section not expected")
        yield from _walk(play.get("tasks", []))


def _module_args(task):
    return {k: v for k, v in task.items() if k.startswith(("fjacquet.", "ansible."))}


def _header(path):
    return path.read_text().split("\n- name:")[0]


def _is_write(task):
    api = task.get("fjacquet.ppdm.api")
    return api is not None and str(api.get("method", "GET")).upper() != "GET"


def test_examples_exist_and_parse():
    assert len(FILES) >= 50
    for path in FILES:
        assert isinstance(yaml.safe_load(path.read_text()), list), path.name
    assert yaml.safe_load((EXAMPLES / "vars" / "example.yml").read_text())


def test_modules_are_fully_qualified():
    for path in FILES:
        for task in _tasks(path):
            if "block" in task:
                continue
            modules = [k for k in task if k not in TASK_KEYWORDS and not k.startswith("with_")]
            assert len(modules) == 1, (path.name, task.get("name"), modules)
            assert modules[0].startswith(("fjacquet.ppdm.", "ansible.builtin.")), (path.name, modules[0])


def test_no_literal_secrets():
    pattern = re.compile(r"^\s*((?:\w+_)?(?:password|token|secret|privateKey)):\s*(\S.*)$", re.I)
    for path in [*FILES, EXAMPLES / "vars" / "example.yml"]:
        for line in path.read_text().splitlines():
            match = pattern.match(line)
            if match and not line.lstrip().startswith("#"):
                assert "{{" in match.group(2), (path.name, line)


def test_header_has_credit_line_and_no_disclaimer():
    for path in FILES:
        header = _header(path)
        assert "# Inspired by bottkars/ansible_ppdm `" in header, path.name
        assert "(workflow only; rewritten for fjacquet.ppdm)" in header, path.name
        assert "PPDM_" in header, path.name


def test_disclaimer_only_in_readme():
    assert DISCLAIMER in README
    for path in [*FILES, *(EXAMPLES / "vars").glob("*.yml")]:
        assert DISCLAIMER.lower() not in path.read_text().lower(), path.name
        assert "pre-release" not in path.read_text().lower(), path.name


def _readme_rows():
    converted_part, skipped_part = README.split("## Converted")[1].split("## Not converted")
    converted = re.findall(r"^\| \[([^\]]+)\]\([^)]*\) \|.*\| ([^|]+?) \| converted \|$", converted_part, re.M)
    skipped = re.findall(r"^\| ([^|]+?) \| [^|]+ \|$", skipped_part, re.M)[1:]
    return converted, skipped


def test_readme_indexes_every_example_and_source_file():
    converted, skipped = _readme_rows()
    assert len(ALL_SOURCES) == 90
    seen = [name for _, sources in converted for name in sources.split(", ")]
    seen += [name for row in skipped for name in row.split(", ")]
    for name in ALL_SOURCES:
        assert seen.count(name) == 1, f"{name} is in {seen.count(name)} table rows, expected exactly one"
    assert set(seen) == set(ALL_SOURCES), set(seen) ^ set(ALL_SOURCES)
    listed = {example for example, _ in converted}
    for path in FILES:
        assert path.name in listed, f"{path.name} is not in the converted table"
    assert "NOTICE" in README


def test_readme_lists_exactly_the_unguarded_examples():
    match = re.search(r"are not guarded \(([\d, ]+)\)", README)
    assert match
    assert {n.strip() for n in match.group(1).split(",")} == NOT_GUARDED
    for path in FILES:
        number = path.name.split("-")[0]
        assert not (number in NOT_GUARDED and path.name in DESTRUCTIVE), path.name


def test_at_least_70_source_files_are_converted_and_credited():
    converted = [name for name in ALL_SOURCES if name not in SKIPPED]
    assert len(converted) >= 70
    credits = "\n".join(line for path in FILES for line in _header(path).splitlines() if line.startswith("#"))
    for name in converted:
        assert f"`{name}`" in credits, f"{name} is not credited in any example header"
    for name in SKIPPED:
        assert f"`{name}`" not in credits, f"{name} is skipped but credited"


def test_skip_table_only_has_the_allowed_categories():
    rows = re.findall(r"^\| ([^|]+?) \|", README.split("## Not converted")[1], re.M)
    listed = {n.strip() for row in rows[1:] for n in row.split(", ")}
    assert listed == set(SKIPPED)


def test_destructive_examples_are_guarded_by_a_preceding_assert():
    defaults = yaml.safe_load((EXAMPLES / "vars" / "example.yml").read_text())
    for name, var in DESTRUCTIVE.items():
        tasks = list(_tasks(EXAMPLES / name))
        guards = [
            i
            for i, t in enumerate(tasks)
            if "ansible.builtin.assert" in t and var in str(t["ansible.builtin.assert"].get("that"))
        ]
        writes = [i for i, t in enumerate(tasks) if _is_write(t)]
        assert guards and writes, name
        assert guards[0] < writes[0], name
        assert defaults[var] is False, var


def test_readme_lists_the_destructive_set():
    match = re.search(r"destructive or service affecting \(([\d, ]+)\)", README)
    assert match
    listed = {n.strip() for n in match.group(1).split(",")}
    assert listed == {name.split("-")[0] for name in DESTRUCTIVE}


def test_secret_bearing_tasks_have_no_log():
    for path in FILES:
        for task in _tasks(path):
            dump = json.dumps(_module_args(task))
            returns_package = "/upgrade-packages" in dump and "DELETE" not in dump
            if SECRET_RE.search(dump) or returns_package:
                assert task.get("no_log") is True, (path.name, task.get("name"))


def test_debug_never_echoes_a_secret_bearing_result():
    for path in FILES:
        tasks = list(_tasks(path))
        secret_registers = {
            t["register"] for t in tasks if "register" in t and SECRET_RE.search(json.dumps(_module_args(t)))
        }
        for task in tasks:
            if "ansible.builtin.debug" in task:
                dump = json.dumps(task["ansible.builtin.debug"]) + json.dumps(task.get("loop", ""))
                for register in secret_registers:
                    assert not re.search(rf"\b{register}\b", dump), (path.name, task.get("name"), register)
