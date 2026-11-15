# Example playbooks for fjacquet.ppdm

These playbooks show, workflow by workflow, how to do with the `fjacquet.ppdm` collection what the community project
[bottkars/ansible_ppdm](https://github.com/bottkars/ansible_ppdm) does with `uri`-based roles. Each workflow is
rewritten, no YAML is copied, and the original file is credited in a comment at the top of each example.

> **Not yet validated against a live PPDM.** The collection is a 0.x pre-release and these examples target PPDM
> 20.3.0 only. Their endpoints and request bodies were checked against the 20.3.0 OpenAPI files in `docs/openapi/`,
> not against a running appliance. Read an example before you run it, and try it on a lab first.

## Running an example

Connection settings and secrets come from environment variables, nothing sensitive is stored in a file:

| Variable | Used by | Meaning |
|----------|---------|---------|
| `PPDM_HOSTNAME`, `PPDM_USERNAME`, `PPDM_PASSWORD` | all | PPDM address and login |
| `PPDM_PORT` | all (optional) | REST API port, default 8443 |
| `DDVE_PASSWORD` | 20 | Data Domain password |
| `VCENTER_PASSWORD` | 21 | vCenter password |
| `PPDM_K8S_TOKEN` | 130 | Kubernetes service account token |
| `PPDM_LICENSE_KEY` | 91 | PPDM license key |

Placeholders for names, ports and fingerprints are in `vars/example.yml`: copy it, edit it, and pass your copy with
`-e @my-vars.yml`.

```
export PPDM_HOSTNAME=ppdm.example.com PPDM_USERNAME=admin PPDM_PASSWORD=...
ansible-playbook -i localhost, docs/examples/20-add-data-domain.yml
```

Examples that change something destructive or service affecting (40, 90, 91, 94, 95, 102) refuse to run until
their confirm variable (`restore_confirm`, `cert_confirm`, `license_confirm`, `update_confirm`, `whitelist_confirm`)
is set to true. 94 also accepts the product and telemetry EULAs and trusts the package certificate when confirmed.

## Unverified details

- 22: the `consumersCount` filter is marked `x-ppdm-filter: false` in the spec, PPDM may reject it.
- 23: the `start` operation of the component management call has no enum in the spec.
- 25: `repositoryHost` is set to the storage system id, as in the original workflow.

## Converted

| Example | What it does | Module | Original bottkars file | Status |
|---------|--------------|--------|------------------------|--------|
| [bootstrap.yml](bootstrap.yml) | Accept the EULA, apply the initial configuration, wait for it | `fjacquet.ppdm.bootstrap` role | 1.0-playbook_configure_ppdm.yml, 1.0-playbook_wait_ready.yml | converted |
| [11-get-configuration.yml](11-get-configuration.yml) | Read the appliance configuration | `api` | 1.1-playbook_get_ppdm_config.yml | converted |
| [20-add-data-domain.yml](20-add-data-domain.yml) | Trust certificate, credential, inventory source | `certificate`, `credential`, `inventory_source` | 2.0-playbook_set_ddve.yml | converted |
| [21-add-vcenter.yml](21-add-vcenter.yml) | Same for a vCenter | `certificate`, `credential`, `inventory_source` | 2.1-playbook_set_vsphere.yml | converted |
| [22-list-unassigned-credentials.yml](22-list-unassigned-credentials.yml) | List unused Kubernetes credentials | `credential_info` | 2.0-playbook_test_unassigned_credentials.yml | converted |
| [23-enable-cloud-dr-component.yml](23-enable-cloud-dr-component.yml) | Start the Cloud DR component | `api` | 2.2-playbook_set_cdra_enabled.yml | converted |
| [24-configure-smtp.yml](24-configure-smtp.yml) | Create or update the SMTP configuration | `api` | 3.1-playbook_set_smtp.yml | converted |
| [25-configure-sdr.yml](25-configure-sdr.yml) | Point server disaster recovery to a Data Domain | `api`, `storage_system_info` | 3.0-playbook_set_sdr.yml, 3.0-playbook_get_sdr.yml | converted |
| [30-get-assets.yml](30-get-assets.yml) | List assets | `api` | 30.0-playbook_get_assets.yml | converted |
| [31-get-vm-asset-copies.yml](31-get-vm-asset-copies.yml) | List the copies of a VM | `api` | 30.1-playbook_get_vm_asset_copies.yml, 30.1-playbook_search_vm_asset_by_name.yml | converted |
| [32-get-activities.yml](32-get-activities.yml) | List activities | `api` | 31.1-playbook_get_activities.yml | converted |
| [40-restore-vm-copy.yml](40-restore-vm-copy.yml) | Restore the latest VM copy to production | `api` | 40.1-playbook_restore_vm_asset_copies.yml | converted |
| [90-replace-certificate.yml](90-replace-certificate.yml) | Replace the web certificate | `api` | 9.0-playbook_replace_certs.yml | converted |
| [91-set-license.yml](91-set-license.yml) | Set the license key | `api` | 9.1-playbook_replace_license.yml | converted |
| [92-get-update-packages.yml](92-get-update-packages.yml) | List update packages | `api` | 9.9-playbook_get_ppdm_update_package_active.yml, 9.9-playbook_get_ppdm_update_package_history.yml | converted |
| [93-precheck-update-package.yml](93-precheck-update-package.yml) | Precheck the active update package | `api` | 9.9-playbook_precheck_update_ppdm.yml | converted |
| [94-install-update-package.yml](94-install-update-package.yml) | Install the active update package | `api` | 9.9-playbook_install_update_ppdm.yml | converted |
| [95-delete-update-package.yml](95-delete-update-package.yml) | Delete the active update package | `api` | 9.9-playbook_delete_ppdm_update_package.yml | converted |
| [96-get-components.yml](96-get-components.yml) | List components | `api` | 99_playbook_get_components.yml | converted |
| [97-get-inventory-and-storage-systems.yml](97-get-inventory-and-storage-systems.yml) | List inventory sources and storage systems | `inventory_source_info`, `storage_system_info` | 99_get_inventory.yml, 99_get_data_domain.yml | converted |
| [100-get-agent-registration-status.yml](100-get-agent-registration-status.yml) | List agent registration status | `api` | 100.5_get_agent_registration_status.yaml | converted |
| [101-approve-agent-ips.yml](101-approve-agent-ips.yml) | Approve agent IPs on the whitelist | `api` | 100.4_create_whitelistentry.yaml, 100.6_get_whitelist.yaml | converted |
| [102-delete-whitelist-entries.yml](102-delete-whitelist-entries.yml) | Delete whitelist entries | `api` | 100.8_delete_whitelistentry.yaml | converted |
| [110-get-protection-policies.yml](110-get-protection-policies.yml) | List protection policies (`/api/v3` only) | `api` | 110.0_get_protection_policies.yaml | converted |
| [111-run-protection-policy.yml](111-run-protection-policy.yml) | Run a protection policy now | `api` | 110.4_playbook_start_policy.yaml, 120.3_playbook_start_policy.yaml, 130.4_playbook_start_k8s_policy.yaml | converted |
| [130-add-kubernetes.yml](130-add-kubernetes.yml) | Add a Kubernetes cluster (PPDM side) | `certificate`, `credential`, `inventory_source` | 130.1_playbook_rbac_add_k8s_to_ppdm.yaml | converted |
| [131-run-discovery.yml](131-run-discovery.yml) | Start a discovery | `api`, `inventory_source_info` | 130.3_playbook_start_k8s_discoveries_by_query.yaml | converted |

The bottkars community project is credited in [NOTICE](../../NOTICE).

## Not converted

| Original bottkars file | Reason |
|------------------------|--------|
| 100.1_download_agents.yml, 100.3_playbook_copy_and_deploy_windows_agent.yaml, 100.9_playbook-uninstall-windows-agent.yaml, 120.0_ensure_mssql_aag_local_user.yaml | Agent download or deployment on Windows hosts, outside the PPDM REST API |
| 9.9-playbook_upload_update_ppdm_native.yml, 9.9-playbook_upload_update_ppdm.yml | Update package upload through `curl` or a native upload, not supported by the `api` module |
| 99-playbook_upgrade_state.yml, scratch_check_update_state.yml | Poll the upgrade status on port 14443, outside the REST API port |
| 99_re-ip_dd_after_headswap.yml | One-off re-IP helper that only makes sense on the author's lab |
| 99_playbook_get_components copy.yml, 2.0-playbook_test_unassigned_credentials_id.yml, 3.0-playbook_get_sdr.yml, 3.0-playbook_set_sdr_existing_unit.yml, 100.4_create_whitelistentry_from_addressquery.yaml, 130.4_playbook_start_k8s_discoveries.yaml, playbook_start_k8s_discoveries.yml, playbook_add_k8s.yml, playbook_rbac_add_k8s_to_ppdm.yml, playbook_rbac_add_k8s_to_ppdm_reg_cred.yml, playbook_rbac_add_k8s_to_ppdm_reg_cred_assetsource_enable.yml, playbook_get_k8s_policy.yml, 2.2-playbook_set_cdra_disabled.yml | Duplicates or variants of a converted workflow (the opposite operation, a second lookup, the same call from another entry point) |
| 2.0-playbook_test_credentials.yml, 1.0-playbook_wait_ready.yml | Token and readiness checks, covered by the `bootstrap` role and by the modules logging in themselves |
| scratch.yml, scratch_create_flr_session.yml, scratch_get_asset_setings.yml, scratch_get_flr_sessions.yml, scratch_get_flr.yml, scratch_k8s_info.yml, time.yml, xxx_restore.yaml, ppdm-restore-2022.10.15-002.yml, 99_playbook_get_k8s_info.yml | Scratch and experiment files of the original project |
| 2.0-playbook_set_csm.yml | Not converted yet: Cloud Snapshot Manager tenant setup, the body of the inventory source (`externalTenant`) is not covered by the `inventory_source` options |
| 2.3-playbook_configure_cloud_dr_account.yml, 2.3-playbook_updarte_cloud_dr_account.yml, 2.4-playbook_set_cloud_dr_target.yml, 2.5-playbook_set_cdrs_deployment.yml, 2.6-playbook_get_cdrs_deployment.yml, 2.7-playbook_delete_cdrs_deployment.yml | Not converted yet: Azure Cloud DR account, target and server deployment, the request bodies were not verified against the spec |
| 120.1_playbook_add_exchange_policy.yaml, 120.1_playbook_add_fs_policy.yaml, 120.1_playbook_add_mssql_policy.yaml, 130.2_playbook_add_k8s_policy_and_rule.yaml, playbook_get_rule.yml | Not converted yet: policy and rule creation use large per-asset-type bodies in `/api/v3` and `/api/v2/protection-rules`, to be done once the v3 policy schema is mapped |
| 120.2_playbook_add_assets_to_policy.yaml | `POST /api/v2/protection-policies/{id}/asset-assignments` takes a JSON array as body, the `api` module accepts a dict only |
| 30.2-playbook_get_k8s_asset_copies.yml, 40.2-playbook_restore_k8s_asset_copies.yml | Not converted yet: Kubernetes copy listing and restore, same pattern as 31 and 40 with a namespace filter |
| 100.2_set_dns_for_agents.yaml, 100.3_set_ip_for_agents.yaml | Not converted yet: the `APP_AGENT_SETTING` common setting is not described in the 20.3.0 spec |
| 9.10-playbook_get_password_policy.yml, 9.11-playbook_update_password_policy_age.yml | The `/policies/password` endpoint does not exist in the 20.3.0 spec |
| 9.12-playbook_set_k8s_controller_config.yml | Lab-specific OpenShift exclusion list, and the deep merge of `details.k8s` is not supported by `inventory_source` (shallow `config` merge) |
| 9.2-playbook_vib_details.yml | Lab-specific vCenter and resource IDs, only a single GET of `/api/v2/vib-details` |
