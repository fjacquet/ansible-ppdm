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
    "name",
    "when",
    "register",
    "loop",
    "loop_control",
    "no_log",
    "vars",
    "block",
    "rescue",
    "always",
    "changed_when",
    "failed_when",
    "until",
    "retries",
    "delay",
    "tags",
    "check_mode",
    "module_defaults",
    "environment",
    "delegate_to",
    "run_once",
    "ignore_errors",
    "args",
    "with_items",
    "notify",
}
SKIPPED = (
    ["99_playbook_get_components copy.yml"]
    + """
100.1_download_agents.yml 100.3_playbook_copy_and_deploy_windows_agent.yaml 100.9_playbook-uninstall-windows-agent.yaml
120.0_ensure_mssql_aag_local_user.yaml 9.9-playbook_upload_update_ppdm_native.yml 9.9-playbook_upload_update_ppdm.yml
99-playbook_upgrade_state.yml scratch_check_update_state.yml 99_re-ip_dd_after_headswap.yml
2.0-playbook_test_unassigned_credentials_id.yml 3.0-playbook_get_sdr.yml
3.0-playbook_set_sdr_existing_unit.yml 100.4_create_whitelistentry_from_addressquery.yaml
130.4_playbook_start_k8s_discoveries.yaml playbook_start_k8s_discoveries.yml playbook_add_k8s.yml
playbook_rbac_add_k8s_to_ppdm.yml playbook_rbac_add_k8s_to_ppdm_reg_cred.yml
playbook_rbac_add_k8s_to_ppdm_reg_cred_assetsource_enable.yml playbook_get_k8s_policy.yml
2.2-playbook_set_cdra_disabled.yml 2.0-playbook_test_credentials.yml 1.0-playbook_wait_ready.yml scratch.yml
scratch_create_flr_session.yml scratch_get_asset_setings.yml scratch_get_flr_sessions.yml scratch_get_flr.yml
scratch_k8s_info.yml time.yml xxx_restore.yaml ppdm-restore-2022.10.15-002.yml 99_playbook_get_k8s_info.yml
2.0-playbook_set_csm.yml 2.3-playbook_configure_cloud_dr_account.yml 2.3-playbook_updarte_cloud_dr_account.yml
2.4-playbook_set_cloud_dr_target.yml 2.5-playbook_set_cdrs_deployment.yml 2.6-playbook_get_cdrs_deployment.yml
2.7-playbook_delete_cdrs_deployment.yml 120.1_playbook_add_exchange_policy.yaml 120.1_playbook_add_fs_policy.yaml
120.1_playbook_add_mssql_policy.yaml 130.2_playbook_add_k8s_policy_and_rule.yaml playbook_get_rule.yml
120.2_playbook_add_assets_to_policy.yaml 30.2-playbook_get_k8s_asset_copies.yml
40.2-playbook_restore_k8s_asset_copies.yml 100.2_set_dns_for_agents.yaml 100.3_set_ip_for_agents.yaml
9.10-playbook_get_password_policy.yml 9.11-playbook_update_password_policy_age.yml
9.12-playbook_set_k8s_controller_config.yml 9.2-playbook_vib_details.yml
""".split()
)


def _tasks(path):
    for play in yaml.safe_load(path.read_text()):
        for task in play.get("tasks", []):
            yield task
        if "roles" in play:
            raise AssertionError(f"{path.name}: roles section not expected")


def test_examples_exist_and_parse():
    assert len(FILES) >= 20
    for path in FILES:
        assert isinstance(yaml.safe_load(path.read_text()), list), path.name
    assert yaml.safe_load((EXAMPLES / "vars" / "example.yml").read_text())


def test_modules_are_fully_qualified():
    for path in FILES:
        for task in _tasks(path):
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
        text = path.read_text()
        header = text.split("\n- name:")[0]
        assert "# Inspired by bottkars/ansible_ppdm `" in header, path.name
        assert "(workflow only; rewritten for fjacquet.ppdm)" in header, path.name
        assert "PPDM_" in header, path.name


def test_disclaimer_only_in_readme():
    assert DISCLAIMER in README
    for path in [*FILES, *(EXAMPLES / "vars").glob("*.yml")]:
        assert DISCLAIMER.lower() not in path.read_text().lower(), path.name
        assert "pre-release" not in path.read_text().lower(), path.name


def test_readme_indexes_every_example_and_skipped_source():
    for path in FILES:
        assert path.name in README, path.name
    for name in SKIPPED:
        assert name in README, name
    assert "NOTICE" in README


DESTRUCTIVE = {
    "40-restore-vm-copy.yml": "restore_confirm",
    "90-replace-certificate.yml": "cert_confirm",
    "91-set-license.yml": "license_confirm",
    "94-install-update-package.yml": "update_confirm",
    "95-delete-update-package.yml": "update_confirm",
    "102-delete-whitelist-entries.yml": "whitelist_confirm",
}
SECRET_RE = re.compile(r"password|token|license_key|privatekey|cred_password|\"key\":", re.I)


def _is_write(task):
    api = task.get("fjacquet.ppdm.api")
    return api is not None and str(api.get("method", "GET")).upper() != "GET"


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
            args = {k: v for k, v in task.items() if k.startswith(("fjacquet.", "ansible."))}
            dump = json.dumps(args)
            returns_package = "/upgrade-packages" in dump and "DELETE" not in dump
            if SECRET_RE.search(dump) or returns_package:
                assert task.get("no_log") is True, (path.name, task.get("name"))
