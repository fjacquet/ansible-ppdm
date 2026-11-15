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
| `CSM_CREDENTIALS` | 28 | Cloud Snapshot Manager credential secret |
| `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` | 51 | Azure account keys for Cloud DR |
| `CDRS_ADMIN_PASSWORD` | 53 | Admin and monitor password of the Cloud DR server |
| `APP_CREDENTIAL_PASSWORD` | 121, 122 | Operating system password for SQL Server and Exchange hosts |

Placeholders for names, ports and fingerprints are in `vars/example.yml`: copy it, edit it, and pass your copy with
`-e @my-vars.yml`.

```
export PPDM_HOSTNAME=ppdm.example.com PPDM_USERNAME=admin PPDM_PASSWORD=...
ansible-playbook -i localhost, docs/examples/20-add-data-domain.yml
```

Examples that change something destructive or service affecting (40, 41, 50, 53, 55, 89, 90, 91, 94, 95, 101, 102, 104, 132, 134, 135) refuse to
run until their confirm variable (`restore_confirm`, `cloud_dr_confirm`, `local_user_setting_confirm`, `cert_confirm`,
`license_confirm`, `update_confirm`, `whitelist_approve_confirm`, `whitelist_confirm`, `rule_exec_confirm`,
`certificate_trust_confirm`, `inventory_update_confirm`) is set to true. 94 also accepts the product and telemetry EULAs and trusts the package certificate when confirmed.

Other examples that write are not guarded (24, 27, 51, 111): 24, 27 and 51 are idempotent updates of settings the
example itself creates or documents, and 111 starts one backup of an existing policy without changing any state.

## Unverified details

Besides the disclaimer above, these points are known guesses:

- 22: the `consumersCount` filter is marked `x-ppdm-filter: false` in the spec, PPDM may reject it.
- 23, 50: the `start` and `disable` operations of the component management call have no enum in the spec.
- 25, 27: `repositoryHost` is set to the storage system id, as in the original workflow.
- 52, 53: the data target body (`copiesStorageContainer.id` set to the storage account name) is taken from the original
  workflow, the spec gives no example.
- 88, 89: the community `/policies/password` endpoint does not exist in 20.3.0. `LOCAL_USER_SETTING` (deprecated in the
  spec) is the closest setting, its property names (`maxAge` here) are not listed in the spec.
- 98: the spec requires `resourceId` too, the original workflow sent only `parentResourceId`.
- 103: the `APP_AGENT_SETTING` setting and its `enableLookups` property come from the original workflow, they are not
  described in the 20.3.0 spec.
- 120, 121, 122, 132: policies are built from the `/api/v3` schema (objectives, operations, retentions), not from the
  original templates. `storageContainerId` is set to the Data Domain storage system id and the objective id is a
  generated UUID: both are assumptions. The spec lists no endpoint to read storage containers.
- 120, 121, 122, 132: `preferredInterfaceId` is the first preferred interface of the Data Domain; the example stops
  with an assert when there is none, and `preferred_interface_id` overrides the derived value.
- 134: `POST /api/v2/certificates` is used as in the original workflow; it is not idempotent.
- 101, 104: the whitelist `expiresAt` value is built from the controller clock.

## Kubernetes cluster side

The original Kubernetes playbooks also configure the cluster (RBAC, service account token, registry secrets, namespace)
with `kubernetes.core`. That part is not covered: this collection has no Kubernetes dependency. 130 and 133 take the
cluster address and the service account token from variables and `PPDM_K8S_TOKEN`; the `kubernetes.core` tasks stay
outside the PPDM workflow.

## Converted

Every original file is listed in exactly one of the two tables below.

| Example | What it does | Modules | Original bottkars files | Status |
|---------|--------------|---------|-------------------------|--------|
| [bootstrap.yml](bootstrap.yml) | Bootstrap a new appliance with the bootstrap role: EULA, initial configuration, wait for it to finish. | `bootstrap role` | 1.0-playbook_configure_ppdm.yml | converted |
| [10-wait-for-api.yml](10-wait-for-api.yml) | Retry a read until the REST API answers and the login works (the bootstrap role does the same before configuring). | `api` | 1.0-playbook_wait_ready.yml | converted |
| [11-get-configuration.yml](11-get-configuration.yml) | Read the appliance configuration (read-only). | `api` | 1.1-playbook_get_ppdm_config.yml | converted |
| [12-test-login.yml](12-test-login.yml) | Log in and read the credentials: a failure here means the address, port or login is wrong. | `credential_info` | 2.0-playbook_test_credentials.yml | converted |
| [20-add-data-domain.yml](20-add-data-domain.yml) | Trust the Data Domain certificate, create its credential and add it as an inventory source. | `certificate`, `credential`, `inventory_source` | 2.0-playbook_set_ddve.yml | converted |
| [21-add-vcenter.yml](21-add-vcenter.yml) | Trust the vCenter certificate, create its credential and add it as an inventory source. | `certificate`, `credential`, `inventory_source` | 2.1-playbook_set_vsphere.yml | converted |
| [22-list-unassigned-credentials.yml](22-list-unassigned-credentials.yml) | List credentials of type KUBERNETES that no consumer uses (read-only). | `credential_info` | 2.0-playbook_test_unassigned_credentials.yml | converted |
| [23-enable-cloud-dr-component.yml](23-enable-cloud-dr-component.yml) | Start the Cloud DR (cdr) component when it is disabled. | `api` | 2.2-playbook_set_cdra_enabled.yml | converted |
| [24-configure-smtp.yml](24-configure-smtp.yml) | Create the SMTP configuration, or update it when it differs. | `api` | 3.1-playbook_set_smtp.yml | converted |
| [25-configure-sdr.yml](25-configure-sdr.yml) | Set the server disaster recovery (SDR) repository to an existing Data Domain storage system. | `api`, `storage_system_info` | 3.0-playbook_set_sdr.yml | converted |
| [26-get-sdr-configuration.yml](26-get-sdr-configuration.yml) | Show the server disaster recovery (SDR) configuration (read-only). | `api` | 3.0-playbook_get_sdr.yml | converted |
| [27-set-sdr-existing-unit.yml](27-set-sdr-existing-unit.yml) | Point the SDR configuration to the SysDR_<short name> unit of a Data Domain, keeping the existing credential. | `api`, `storage_system_info` | 3.0-playbook_set_sdr_existing_unit.yml | converted |
| [28-add-cloud-snapshot-manager.yml](28-add-cloud-snapshot-manager.yml) | Create the CLOUD_SNAPSHOT_MANAGER credential and inventory source for a tenant. | `credential`, `inventory_source` | 2.0-playbook_set_csm.yml | converted |
| [29-list-credential-usage.yml](29-list-credential-usage.yml) | Show which objects use a credential (read-only). | `api`, `credential_info` | 2.0-playbook_test_unassigned_credentials_id.yml | converted |
| [30-get-assets.yml](30-get-assets.yml) | List assets, optionally filtered with a PPDM filter string (read-only). | `api` | 30.0-playbook_get_assets.yml | converted |
| [31-get-vm-asset-copies.yml](31-get-vm-asset-copies.yml) | Find a protected VM asset by name and list its copies (read-only). | `api` | 30.1-playbook_get_vm_asset_copies.yml, 30.1-playbook_search_vm_asset_by_name.yml | converted |
| [32-get-activities.yml](32-get-activities.yml) | List activities, optionally filtered with a PPDM filter string (read-only). | `api` | 31.1-playbook_get_activities.yml | converted |
| [33-get-k8s-asset-copies.yml](33-get-k8s-asset-copies.yml) | Find a namespace asset that has a copy and list its copies (read-only). | `api` | 30.2-playbook_get_k8s_asset_copies.yml | converted |
| [40-restore-vm-copy.yml](40-restore-vm-copy.yml) | Restore the latest copy of a VM to its original location; refuses to run unless restore_confirm is true. | `api` | 40.1-playbook_restore_vm_asset_copies.yml | converted |
| [41-restore-k8s-copy.yml](41-restore-k8s-copy.yml) | Restore the latest copy of a namespace (to a new namespace by default); refuses to run unless restore_confirm is true. | `api` | 40.2-playbook_restore_k8s_asset_copies.yml | converted |
| [50-disable-cloud-dr-component.yml](50-disable-cloud-dr-component.yml) | Disable the Cloud DR (cdr) component; refuses to run unless cloud_dr_confirm is true. | `api` | 2.2-playbook_set_cdra_disabled.yml | converted |
| [51-configure-cloud-dr-account.yml](51-configure-cloud-dr-account.yml) | Wait for the Cloud DR component, then create the Azure account or update its keys when it exists. | `api` | 2.3-playbook_configure_cloud_dr_account.yml, 2.3-playbook_updarte_cloud_dr_account.yml | converted |
| [52-set-cloud-dr-target.yml](52-set-cloud-dr-target.yml) | Create the data target (storage account) of the Azure Cloud DR account. | `api` | 2.4-playbook_set_cloud_dr_target.yml | converted |
| [53-deploy-cloud-dr-server.yml](53-deploy-cloud-dr-server.yml) | Deploy the Cloud DR server in the cloud (this creates billable cloud resources); refuses to run unless cloud_dr_confirm is true. | `api` | 2.5-playbook_set_cdrs_deployment.yml | converted |
| [54-get-cloud-dr-server.yml](54-get-cloud-dr-server.yml) | Show the Cloud DR server configuration (read-only). | `api` | 2.6-playbook_get_cdrs_deployment.yml | converted |
| [55-delete-cloud-dr-server.yml](55-delete-cloud-dr-server.yml) | Delete the Cloud DR server deployment; refuses to run unless cloud_dr_confirm is true. | `api` | 2.7-playbook_delete_cdrs_deployment.yml | converted |
| [88-get-local-user-settings.yml](88-get-local-user-settings.yml) | Show the LOCAL_USER_SETTING common setting, the closest 20.3.0 equivalent of the community password policy (read-only). | `api` | 9.10-playbook_get_password_policy.yml | converted |
| [89-set-local-user-setting.yml](89-set-local-user-setting.yml) | Set one property of LOCAL_USER_SETTING (for example the password age), keeping the others. | `api` | 9.11-playbook_update_password_policy_age.yml | converted |
| [90-replace-certificate.yml](90-replace-certificate.yml) | Replace the appliance certificate with a key and chain read from local files; refuses to run unless cert_confirm is true. | `api` | 9.0-playbook_replace_certs.yml | converted |
| [91-set-license.yml](91-set-license.yml) | Apply a license key to the appliance license object; refuses to run unless license_confirm is true. | `api` | 9.1-playbook_replace_license.yml | converted |
| [92-get-update-packages.yml](92-get-update-packages.yml) | List the ACTIVE update package (set update_category to HISTORY for the history; read-only). | `api` | 9.9-playbook_get_ppdm_update_package_active.yml, 9.9-playbook_get_ppdm_update_package_history.yml | converted |
| [93-precheck-update-package.yml](93-precheck-update-package.yml) | Start the precheck of the active update package and show its validation details. | `api` | 9.9-playbook_precheck_update_ppdm.yml | converted |
| [94-install-update-package.yml](94-install-update-package.yml) | Install the active update package; refuses to run unless update_confirm is true. | `api` | 9.9-playbook_install_update_ppdm.yml | converted |
| [95-delete-update-package.yml](95-delete-update-package.yml) | Delete the active update package; refuses to run unless update_confirm is true. | `api` | 9.9-playbook_delete_ppdm_update_package.yml | converted |
| [96-get-components.yml](96-get-components.yml) | List the appliance components with their status (read-only). | `api` | 99_playbook_get_components.yml | converted |
| [97-get-inventory-and-storage-systems.yml](97-get-inventory-and-storage-systems.yml) | List inventory sources (optionally filtered) and the Data Domain storage system (read-only). | `inventory_source_info`, `storage_system_info` | 99_get_inventory.yml, 99_get_data_domain.yml | converted |
| [98-get-vib-details.yml](98-get-vib-details.yml) | Read the vSphere VIB details below a vCenter inventory source (read-only). | `api`, `inventory_source_info` | 9.2-playbook_vib_details.yml | converted |
| [99-wait-for-components.yml](99-wait-for-components.yml) | Poll the components until all of them report UP. | `api` | 99_playbook_get_components copy.yml | converted |
| [100-get-agent-registration-status.yml](100-get-agent-registration-status.yml) | List the protection agents with their registration status (read-only; replaces the unversioned /agents-list call). | `api` | 100.0_list_agents.yml, 100.5_get_agent_registration_status.yaml | converted |
| [101-approve-agent-ips.yml](101-approve-agent-ips.yml) | Approve each IP of agent_ips on the agent whitelist (24 hours) unless already approved and not expired. | `api` | 100.4_create_whitelistentry.yaml, 100.6_get_whitelist.yaml | converted |
| [102-delete-whitelist-entries.yml](102-delete-whitelist-entries.yml) | Delete the whitelist entries listed in whitelist_ids; refuses to run unless whitelist_confirm is true. | `api` | 100.8_delete_whitelistentry.yaml | converted |
| [103-set-agent-dns-lookups.yml](103-set-agent-dns-lookups.yml) | Set the enableLookups property of APP_AGENT_SETTING (agent_enable_lookups true uses DNS, false uses IP). | `api` | 100.2_set_dns_for_agents.yaml, 100.3_set_ip_for_agents.yaml | converted |
| [104-approve-agents-by-hostname.yml](104-approve-agents-by-hostname.yml) | Look up the address of each registered agent by host name and approve it on the whitelist (24 hours). | `api` | 100.4_create_whitelistentry_from_addressquery.yaml | converted |
| [110-get-protection-policies.yml](110-get-protection-policies.yml) | List the protection policies (read-only). Protection policies exist only under /api/v3 in 20.3.0. | `api` | 110.0_get_protection_policies.yaml | converted |
| [111-run-protection-policy.yml](111-run-protection-policy.yml) | Start the first objective of a protection policy found by name (POST /api/v3/protections). | `api` | 110.4_playbook_start_policy.yaml, 120.3_playbook_start_policy.yaml, 130.4_playbook_start_k8s_policy.yaml | converted |
| [112-get-protection-rules.yml](112-get-protection-rules.yml) | List the protection rules, optionally filtered by name (read-only). | `api` | playbook_get_rule.yml | converted |
| [113-get-protection-policy.yml](113-get-protection-policy.yml) | Show the protection policy of a given name (read-only). | `api` | playbook_get_k8s_policy.yml | converted |
| [120-add-file-system-policy.yml](120-add-file-system-policy.yml) | Create a daily synthetic full policy on a Data Domain unless one of that name exists. | `api`, `storage_system_info` | 120.1_playbook_add_fs_policy.yaml | converted |
| [121-add-mssql-policy.yml](121-add-mssql-policy.yml) | Create the OS credential and a daily full plus hourly log policy unless one of that name exists. | `api`, `credential`, `storage_system_info` | 120.1_playbook_add_mssql_policy.yaml | converted |
| [122-add-exchange-policy.yml](122-add-exchange-policy.yml) | Create the OS credential and a daily synthetic full policy unless one of that name exists. | `api`, `credential`, `storage_system_info` | 120.1_playbook_add_exchange_policy.yaml | converted |
| [123-assign-assets-to-policy.yml](123-assign-assets-to-policy.yml) | Assign the assets matching a filter to a policy (the body is a JSON array of asset ids). | `api` | 120.2_playbook_add_assets_to_policy.yaml | converted |
| [130-add-kubernetes.yml](130-add-kubernetes.yml) | Trust the API server certificate, store the discovery token and add the cluster as an inventory source. | `certificate`, `credential`, `inventory_source` | playbook_add_k8s.yml, playbook_rbac_add_k8s_to_ppdm.yml, playbook_rbac_add_k8s_to_ppdm_reg_cred.yml, playbook_rbac_add_k8s_to_ppdm_reg_cred_assetsource_enable.yml | converted |
| [131-run-discovery.yml](131-run-discovery.yml) | Start a discovery on the Kubernetes inventory source (change k8s_hostname for another source). | `api`, `inventory_source_info` | 130.3_playbook_start_k8s_discoveries_by_query.yaml, 130.4_playbook_start_k8s_discoveries.yaml, playbook_start_k8s_discoveries.yml | converted |
| [132-add-k8s-policy-and-rule.yml](132-add-k8s-policy-and-rule.yml) | Create a Kubernetes policy, a rule moving namespaces with a label to it, and run the rules. | `api`, `storage_system_info` | 130.2_playbook_add_k8s_policy_and_rule.yaml | converted |
| [133-add-kubernetes-with-vcenter.yml](133-add-kubernetes-with-vcenter.yml) | Add the cluster with its vCenter (CSI drivers as a process): trust, credential, inventory source with k8s details. | `certificate`, `credential`, `inventory_source`, `inventory_source_info` | 130.1_playbook_rbac_add_k8s_to_ppdm.yaml | converted |
| [134-trust-kubernetes-root-certificate.yml](134-trust-kubernetes-root-certificate.yml) | Add the root CA chain of the Kubernetes API server to the PPDM trust store (the chain is read from a local file). | `api` | playbook_set_k8s_root_cert.yml | converted |
| [135-set-kubernetes-controller-config.yml](135-set-kubernetes-controller-config.yml) | Replace one details.k8s.configurations entry (deep change, so a read-modify-write with the api module). | `api`, `inventory_source_info` | 9.12-playbook_set_k8s_controller_config.yml | converted |
| [136-list-kubernetes-clusters.yml](136-list-kubernetes-clusters.yml) | List the Kubernetes inventory sources with address and port (read-only). | `inventory_source_info` | 99_playbook_get_k8s_info.yml | converted |

The bottkars community project is credited in [NOTICE](../../NOTICE).

## Not converted

| Original bottkars file | Reason |
|------------------------|--------|
| 100.1_download_agents.yml, 100.3_playbook_copy_and_deploy_windows_agent.yaml, 100.9_playbook-uninstall-windows-agent.yaml | Agent download, deployment and uninstall on Windows hosts: they run on the agent host, not through the PPDM REST API |
| 120.0_ensure_mssql_aag_local_user.yaml | Creates a Windows local user and SQL Server logins on the database hosts (`ansible.windows`, `community.general.mssql_script`), not PPDM REST |
| 9.9-playbook_upload_update_ppdm.yml, 9.9-playbook_upload_update_ppdm_native.yml | Upload the update package with `curl` or a native multipart upload; the `api` module only sends JSON bodies and cannot upload a file |
| 99-playbook_upgrade_state.yml, scratch_check_update_state.yml | Poll the upgrade status on port 14443, a different service than the REST API port |
| 99_re-ip_dd_after_headswap.yml | One-off re-IP helper for the author's lab after a Data Domain head swap |
| scratch.yml, scratch_create_flr_session.yml, scratch_get_asset_setings.yml, scratch_get_flr_sessions.yml, scratch_get_flr.yml, scratch_k8s_info.yml, time.yml, xxx_restore.yaml, ppdm-restore-2022.10.15-002.yml | Scratch and experiment files of the original project (file level restore experiments with lab ids, an epoch conversion demo, restore request fragments, variable stubs); `scratch.yml` also contains a literal password, which is not carried over |
