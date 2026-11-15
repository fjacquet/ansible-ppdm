import json
import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAYBOOKS = ROOT / "playbooks"
README = (PLAYBOOKS / "README.md").read_text()
FILES = sorted(p for p in PLAYBOOKS.glob("*/*.yml") if p.parent.name != "vars")
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
VARS = PLAYBOOKS / "vars" / "example.yml"


def _fqcn(path):
    return f"fjacquet.ppdm.{path.parent.name}.{path.stem}"


def _short(path):
    return f"{path.parent.name}.{path.stem}"


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
    "assets.restore_vm_copy": "restore_confirm",
    "kubernetes.restore_copy": "restore_confirm",
    "clouddr.disable_component": "cloud_dr_confirm",
    "clouddr.deploy_server": "cloud_dr_confirm",
    "clouddr.delete_server": "cloud_dr_confirm",
    "bootstrap.set_local_user_setting": "local_user_setting_confirm",
    "bootstrap.replace_certificate": "cert_confirm",
    "bootstrap.set_license": "license_confirm",
    "maintenance.install_update_package": "update_confirm",
    "maintenance.delete_update_package": "update_confirm",
    "agents.approve_agent_ips": "whitelist_approve_confirm",
    "agents.delete_whitelist_entries": "whitelist_confirm",
    "agents.approve_agents_by_hostname": "whitelist_approve_confirm",
    "kubernetes.add_policy_and_rule": "rule_exec_confirm",
    "kubernetes.trust_root_certificate": "certificate_trust_confirm",
    "kubernetes.set_controller_config": "inventory_update_confirm",
}
# Writing playbooks left without a confirm guard on purpose; the README gives the reason.
NOT_GUARDED = {
    "bootstrap.configure_smtp",
    "bootstrap.set_sdr_existing_unit",
    "clouddr.configure_account",
    "protection.run_policy",
}
SECRET_RE = re.compile(r"password|token|license_key|privatekey|secretkey|userkey|secret|\"key\":", re.I)


def _walk(tasks):
    for task in tasks:
        yield task
        for section in ("block", "rescue", "always"):
            yield from _walk(task.get(section, []))


def _tasks(path):
    for play in yaml.safe_load(path.read_text()):
        if "roles" in play:
            raise AssertionError(f"{_short(path)}: roles section not expected")
        yield from _walk(play.get("tasks", []))


def _module_args(task):
    return {k: v for k, v in task.items() if k.startswith(("fjacquet.", "ansible."))}


def _header(path):
    return path.read_text().split("\n- name:")[0]


def _is_write(task):
    api = task.get("fjacquet.ppdm.api")
    return api is not None and str(api.get("method", "GET")).upper() != "GET"


def test_playbooks_exist_and_parse():
    assert len(FILES) >= 50
    for path in FILES:
        assert isinstance(yaml.safe_load(path.read_text()), list), _short(path)
    assert yaml.safe_load(VARS.read_text())


def test_modules_are_fully_qualified():
    for path in FILES:
        for task in _tasks(path):
            if "block" in task:
                continue
            modules = [k for k in task if k not in TASK_KEYWORDS and not k.startswith("with_")]
            assert len(modules) == 1, (_short(path), task.get("name"), modules)
            assert modules[0].startswith(("fjacquet.ppdm.", "ansible.builtin.")), (_short(path), modules[0])


def test_no_literal_secrets():
    pattern = re.compile(r"^\s*((?:\w+_)?(?:password|token|secret|privateKey)):\s*(\S.*)$", re.I)
    for path in [*FILES, VARS]:
        for line in path.read_text().splitlines():
            match = pattern.match(line)
            if match and not line.lstrip().startswith("#"):
                assert "{{" in match.group(2), (_short(path), line)


def test_header_has_credit_line_and_no_disclaimer():
    for path in FILES:
        header = _header(path)
        assert "# Inspired by bottkars/ansible_ppdm `" in header, _short(path)
        assert "(workflow only; rewritten for fjacquet.ppdm)" in header, _short(path)
        assert "PPDM_" in header, _short(path)


def test_disclaimer_only_in_readme():
    root_readme = (PLAYBOOKS.parent / "README.md").read_text()
    assert DISCLAIMER.lower() in root_readme.lower()
    assert DISCLAIMER.lower() not in README.lower()
    for path in [*FILES, *(PLAYBOOKS / "vars").glob("*.yml")]:
        assert DISCLAIMER.lower() not in path.read_text().lower(), _short(path)
        assert "pre-release" not in path.read_text().lower(), _short(path)


def _readme_rows():
    converted_part, skipped_part = README.split("## Index")[1].split("## Not converted")
    converted = re.findall(r"^\| \[([^\]]+)\]\(([^)]*)\) \|.*\| ([^|]+?) \| converted \|$", converted_part, re.M)
    skipped = re.findall(r"^\| ([^|]+?) \| [^|]+ \|$", skipped_part, re.M)[1:]
    return converted, skipped


def test_readme_indexes_every_example_and_source_file():
    converted, skipped = _readme_rows()
    assert len(ALL_SOURCES) == 90
    seen = [name for _unused, _unused, sources in converted for name in sources.split(", ")]
    seen += [name for row in skipped for name in row.split(", ")]
    for name in ALL_SOURCES:
        assert seen.count(name) == 1, f"{name} is in {seen.count(name)} table rows, expected exactly one"
    assert set(seen) == set(ALL_SOURCES), set(seen) ^ set(ALL_SOURCES)
    listed = {fqcn for fqcn, _unused, _unused in converted}
    for path in FILES:
        assert _fqcn(path) in listed, f"{_fqcn(path)} is not in the converted table"
    assert listed == {_fqcn(path) for path in FILES}
    assert "NOTICE" in README


def test_readme_maps_each_fqcn_to_its_use_case_directory():
    converted, _unused = _readme_rows()
    for fqcn, link, _unused in converted:
        _unused, _unused, usecase, name = fqcn.split(".")
        assert link == f"{usecase}/{name}.yml", f"{fqcn} links to {link}"
        assert (PLAYBOOKS / link).is_file(), link


def test_names_are_addressable():
    for path in FILES:
        assert NAME_RE.match(path.stem), path
        assert NAME_RE.match(path.parent.name), path
    for directory in PLAYBOOKS.iterdir():
        if directory.is_dir():
            assert NAME_RE.match(directory.name) or directory.name in {"vars", "files", "templates", "tasks"}, directory


def test_hosts_come_from_the_target_variable():
    for path in FILES:
        for play in yaml.safe_load(path.read_text()):
            assert "target" in str(play.get("hosts")), (_short(path), play.get("hosts"))


def test_header_credits_match_the_readme_row_of_each_example():
    converted, _unused = _readme_rows()
    row = {fqcn: set(sources.split(", ")) for fqcn, _unused, sources in converted}
    for path in FILES:
        text = path.read_text()
        credit = text[text.index("Inspired by") : text.index("(workflow only")]
        header = set(re.findall(r"`([^`]+)`", credit))
        assert header == row[_fqcn(path)], f"{_short(path)}: header and README differ: {header ^ row[_fqcn(path)]}"


def test_readme_lists_exactly_the_unguarded_examples():
    match = re.search(r"are not guarded \(([\w.`, ]+)\)", README)
    assert match
    assert {n.strip(" `") for n in match.group(1).split(",")} == NOT_GUARDED
    assert not NOT_GUARDED & set(DESTRUCTIVE)
    assert NOT_GUARDED <= {_short(path) for path in FILES}


def test_at_least_70_source_files_are_converted_and_credited():
    converted = [name for name in ALL_SOURCES if name not in SKIPPED]
    assert len(converted) >= 70
    credits = "\n".join(line for path in FILES for line in _header(path).splitlines() if line.startswith("#"))
    for name in converted:
        assert f"`{name}`" in credits, f"{name} is not credited in any playbook header"
    for name in SKIPPED:
        assert f"`{name}`" not in credits, f"{name} is skipped but credited"


def test_skip_table_only_has_the_allowed_categories():
    rows = re.findall(r"^\| ([^|]+?) \|", README.split("## Not converted")[1], re.M)
    listed = {n.strip() for row in rows[1:] for n in row.split(", ")}
    assert listed == set(SKIPPED)


def test_destructive_examples_are_guarded_by_a_preceding_assert():
    defaults = yaml.safe_load(VARS.read_text())
    for name, var in DESTRUCTIVE.items():
        tasks = list(_tasks(PLAYBOOKS / f"{name.replace('.', '/')}.yml"))
        guards = [
            i
            for i, t in enumerate(tasks)
            if "ansible.builtin.assert" in t and f"{var} | bool" in str(t["ansible.builtin.assert"].get("that"))
        ]
        writes = [i for i, t in enumerate(tasks) if _is_write(t)]
        assert guards and writes, name
        assert guards[0] < writes[0], name
        assert defaults[var] is False, var


def test_readme_lists_the_destructive_set():
    match = re.search(r"destructive or service affecting \(([\w.`, ]+)\)", README)
    assert match
    assert {n.strip(" `") for n in match.group(1).split(",")} == set(DESTRUCTIVE)


def test_secret_bearing_tasks_have_no_log():
    for path in FILES:
        for task in _tasks(path):
            dump = json.dumps(_module_args(task))
            returns_package = "/upgrade-packages" in dump and "DELETE" not in dump
            if SECRET_RE.search(dump) or returns_package:
                assert task.get("no_log") is True, (_short(path), task.get("name"))


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
                    assert not re.search(rf"\b{register}\b", dump), (_short(path), task.get("name"), register)
