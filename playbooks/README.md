# Playbooks for fjacquet.ppdm

These collection playbooks show, workflow by workflow, how to do with the `fjacquet.ppdm` collection what the community project
[bottkars/ansible_ppdm](https://github.com/bottkars/ansible_ppdm) does with `uri`-based roles. Each workflow is
rewritten, no YAML is copied, and the original file is credited in a comment at the top of each playbook.

These playbooks target PPDM 20.3.0 only. Read a playbook before you run it. The pre-release status of the collection is described in the [main README](../README.md).

## Running a playbook

Connection settings and secrets come from environment variables, nothing sensitive is stored in a file:

| Variable | Used by | Meaning |
|----------|---------|---------|
| `PPDM_HOSTNAME`, `PPDM_USERNAME`, `PPDM_PASSWORD` | all | PPDM address and login |
| `PPDM_PORT` | all (optional) | REST API port, default 8443 |
| `DDVE_PASSWORD` | `sources.add_data_domain` | Data Domain password |
| `VCENTER_PASSWORD` | `sources.add_vcenter` | vCenter password |
| `PPDM_K8S_TOKEN` | `kubernetes.add_kubernetes` | Kubernetes service account token |
| `PPDM_LICENSE_KEY` | `bootstrap.set_license` | PPDM license key |
| `PPDM_NEW_PASSWORD` | `bootstrap.bootstrap` | admin password set by the initial configuration (`applicationUserPassword`) |
| `CSM_CREDENTIALS` | `sources.add_cloud_snapshot_manager` | Cloud Snapshot Manager credential secret |
| `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` | `clouddr.configure_account` | Azure account keys for Cloud DR |
| `CDRS_ADMIN_PASSWORD` | `clouddr.deploy_server` | Admin and monitor password of the Cloud DR server |
| `APP_CREDENTIAL_PASSWORD` | `protection.add_mssql_policy`, `protection.add_exchange_policy` | Operating system password for SQL Server and Exchange hosts |

Placeholders for names, ports and fingerprints are in `playbooks/vars/example.yml`: copy it, edit it, and pass your copy with
`-e @my-vars.yml`.

Every play runs `hosts: "{{ target | default('localhost') }}"` with a local connection, so the default is the control node
and nothing runs against a whole inventory by mistake. The
name is the use case directory and the file name, in lowercase letters, digits and `_` only.

```
export PPDM_HOSTNAME=ppdm.example.com PPDM_USERNAME=admin PPDM_PASSWORD=...
ansible-playbook fjacquet.ppdm.sources.add_data_domain -e @my-vars.yml
ansible-playbook fjacquet.ppdm.protection.run_policy -e @my-vars.yml
ansible-playbook playbooks/sources/add_data_domain.yml -e @my-vars.yml   # by path
```

Playbooks that change something destructive or service affecting (`assets.restore_vm_copy`, `kubernetes.restore_copy`, `clouddr.disable_component`, `clouddr.deploy_server`, `clouddr.delete_server`, `bootstrap.set_local_user_setting`, `bootstrap.replace_certificate`, `bootstrap.set_license`, `bootstrap.bootstrap`, `maintenance.install_update_package`, `maintenance.delete_update_package`, `agents.approve_agent_ips`, `agents.delete_whitelist_entries`, `agents.approve_agents_by_hostname`, `kubernetes.add_policy_and_rule`, `kubernetes.trust_root_certificate`, `kubernetes.set_controller_config`, `protection.assign_assets_to_policy`, `protection.run_policy`, `protection.run_discovery`, `protection.run_rule`) refuse to
run until their confirm variable (`restore_confirm`, `cloud_dr_confirm`, `local_user_setting_confirm`, `cert_confirm`,
`license_confirm`, `bootstrap_confirm`, `update_confirm`, `whitelist_approve_confirm`, `whitelist_confirm`, `rule_exec_confirm`,
`certificate_trust_confirm`, `inventory_update_confirm`, `assign_confirm`, `policy_run_confirm`, `discovery_confirm`, `rule_run_confirm`) is set to true. `maintenance.install_update_package` also accepts the product and telemetry EULAs and trusts the package certificate when confirmed.

Other playbooks that write are not guarded (`bootstrap.configure_smtp`, `bootstrap.set_sdr_existing_unit`, `clouddr.configure_account`, `protection.add_file_system_policy`, `protection.add_mssql_policy`): `protection.add_file_system_policy` and `protection.add_mssql_policy` update an existing policy when it differs, they PATCH and replace its whole objectives list when anything differs;  `bootstrap.configure_smtp` and `bootstrap.set_sdr_existing_unit` are idempotent updates of settings the
playbook itself creates or documents, `clouddr.configure_account` updates the account keys on every run (they are write-only, so it always reports changed).

## Unverified details

Besides the disclaimer above, these points are known guesses:

- `sources.list_unassigned_credentials`: the `consumersCount` filter is marked `x-ppdm-filter: false` in the spec, PPDM may reject it.
- `clouddr.enable_component`, `clouddr.disable_component`: the `start` and `disable` operations of the component management call have no enum in the spec.
- `bootstrap.configure_sdr`, `bootstrap.set_sdr_existing_unit`: `repositoryHost` is set to the storage system id, as in the original workflow.
- `clouddr.set_target`, `clouddr.deploy_server`: the data target body (`copiesStorageContainer.id` set to the storage account name) is taken from the original
  workflow, the spec gives no example.
- `bootstrap.get_local_user_settings`, `bootstrap.set_local_user_setting`: the community `/policies/password` endpoint does not exist in 20.3.0. `LOCAL_USER_SETTING` (deprecated in the
  spec) is the closest setting, its property names (`maxAge` here) are not listed in the spec.
- `sources.get_vib_details`: the spec requires `resourceId` too, the original workflow sent only `parentResourceId`.
- `agents.set_agent_dns_lookups`: the `APP_AGENT_SETTING` setting and its `enableLookups` property come from the original workflow, they are not
  described in the 20.3.0 spec.
- `protection.add_file_system_policy`, `protection.add_mssql_policy`, `protection.create_vm_policy`, `protection.create_k8s_policy`, `protection.add_exchange_policy`, `kubernetes.add_policy_and_rule`: policies are built from the `/api/v3` schema (objectives, operations, retentions), not from the
  original templates. `storageContainerId` is set to the Data Domain storage system id (PPDM generates the objective id, except in `protection.add_exchange_policy` and `kubernetes.add_policy_and_rule`, which send a `to_uuid` objective id): this is an assumption. The spec lists no endpoint to read storage containers.
- `protection.add_file_system_policy`, `protection.add_mssql_policy`, `protection.add_exchange_policy`, `kubernetes.add_policy_and_rule`: `preferredInterfaceId` is the first preferred interface of the Data Domain; the example stops
  with an assert when there is none, and `preferred_interface_id` overrides the derived value.
- `protection.add_file_system_policy`, `protection.add_mssql_policy`: the update check needs GET to return `startTime` and `duration` exactly as sent, else the playbooks PATCH on every run.
- `protection.create_rule`, `kubernetes.add_policy_and_rule`: the `fieldName` values (`tags` for VMs, `userTags` for Kubernetes labels, the latter from the Lot 1 playbook) and the `fieldData` shape (`type: STRING`, `values`) of the v3 filter conditions are plausible picks, not verified against a live PPDM; the module only checks the operators and enums.
- `protection.run_policy`: `protection_policy_run` requires `asset_ids` or `protection_group_ids` and cannot set `operation.backupLevel`; `Source` has no required field in the spec. `protection.run_rule` preview POSTs even in check mode (documented read-only).
- `kubernetes.trust_root_certificate`: `POST /api/v2/certificates` is used as in the original workflow; it is not idempotent.
- `protection.create_protection_group`: the protection group body per type (`type`, `subtype`, `memberAssetType`, `naturalIds`) is not verified against a live PPDM; the module checks only the enums.
- `protection.create_resource_group`: the `fieldName` (`tags`) and `fieldData` shape of the rule filter are the same plausible picks as in `protection.create_rule`.
- `agents.approve_agent_ips`, `agents.approve_agents_by_hostname`: the whitelist `expiresAt` value is built from the controller clock.

## Kubernetes cluster side

The original Kubernetes playbooks also configure the cluster (RBAC, service account token, registry secrets, namespace)
with `kubernetes.core`. That part is not covered: this collection has no Kubernetes dependency. `kubernetes.add_kubernetes` and `kubernetes.add_kubernetes_with_vcenter` take the
cluster address and the service account token from variables and `PPDM_K8S_TOKEN`; the `kubernetes.core` tasks stay
outside the PPDM workflow.

## Index

Every original file is listed in exactly one of the two tables below. Playbooks with no original file (new in 0.2.0, marked `-` and `new`) are listed in the Protection table.

### Bootstrap and first configuration

| Playbook | What it does | Modules | Former example | Original bottkars files | Status |
|----------|--------------|---------|----------------|-------------------------|--------|
| [fjacquet.ppdm.bootstrap.bootstrap](bootstrap/bootstrap.yml) | Bootstrap a new appliance with the bootstrap role: EULA, initial configuration, wait for it to finish. | `bootstrap role` | bootstrap.yml | 1.0-playbook_configure_ppdm.yml | converted |
| [fjacquet.ppdm.bootstrap.wait_for_api](bootstrap/wait_for_api.yml) | Retry a read until the REST API answers and the login works (the bootstrap role does the same before configuring). | `api` | 10 | 1.0-playbook_wait_ready.yml | converted |
| [fjacquet.ppdm.bootstrap.get_configuration](bootstrap/get_configuration.yml) | Read the appliance configuration (read-only). | `api` | 11 | 1.1-playbook_get_ppdm_config.yml | converted |
| [fjacquet.ppdm.bootstrap.test_login](bootstrap/test_login.yml) | Log in and read the credentials: a failure here means the address, port or login is wrong. | `credential_info` | 12 | 2.0-playbook_test_credentials.yml | converted |
| [fjacquet.ppdm.bootstrap.configure_smtp](bootstrap/configure_smtp.yml) | Create the SMTP configuration, or update it when it differs. | `api` | 24 | 3.1-playbook_set_smtp.yml | converted |
| [fjacquet.ppdm.bootstrap.configure_sdr](bootstrap/configure_sdr.yml) | Set the server disaster recovery (SDR) repository to an existing Data Domain storage system. | `api`, `storage_system_info` | 25 | 3.0-playbook_set_sdr.yml | converted |
| [fjacquet.ppdm.bootstrap.get_sdr_configuration](bootstrap/get_sdr_configuration.yml) | Show the server disaster recovery (SDR) configuration (read-only). | `api` | 26 | 3.0-playbook_get_sdr.yml | converted |
| [fjacquet.ppdm.bootstrap.set_sdr_existing_unit](bootstrap/set_sdr_existing_unit.yml) | Point the SDR configuration to the SysDR_<short name> unit of a Data Domain, keeping the existing credential. | `api`, `storage_system_info` | 27 | 3.0-playbook_set_sdr_existing_unit.yml | converted |
| [fjacquet.ppdm.bootstrap.get_local_user_settings](bootstrap/get_local_user_settings.yml) | Show the LOCAL_USER_SETTING common setting, the closest 20.3.0 equivalent of the community password policy (read-only). | `api` | 88 | 9.10-playbook_get_password_policy.yml | converted |
| [fjacquet.ppdm.bootstrap.set_local_user_setting](bootstrap/set_local_user_setting.yml) | Set one property of LOCAL_USER_SETTING (for example the password age), keeping the others. | `api` | 89 | 9.11-playbook_update_password_policy_age.yml | converted |
| [fjacquet.ppdm.bootstrap.replace_certificate](bootstrap/replace_certificate.yml) | Replace the appliance certificate with a key and chain read from local files; refuses to run unless cert_confirm is true. | `api` | 90 | 9.0-playbook_replace_certs.yml | converted |
| [fjacquet.ppdm.bootstrap.set_license](bootstrap/set_license.yml) | Apply a license key to the appliance license object; refuses to run unless license_confirm is true. | `api` | 91 | 9.1-playbook_replace_license.yml | converted |
| [fjacquet.ppdm.bootstrap.get_components](bootstrap/get_components.yml) | List the appliance components with their status (read-only). | `api` | 96 | 99_playbook_get_components.yml | converted |
| [fjacquet.ppdm.bootstrap.wait_for_components](bootstrap/wait_for_components.yml) | Poll the components until all of them report UP. | `api` | 99 | 99_playbook_get_components copy.yml | converted |

### Sources: Data Domain, vCenter, CSM, credentials

| Playbook | What it does | Modules | Former example | Original bottkars files | Status |
|----------|--------------|---------|----------------|-------------------------|--------|
| [fjacquet.ppdm.sources.add_data_domain](sources/add_data_domain.yml) | Trust the Data Domain certificate, create its credential and add it as an inventory source. | `certificate`, `credential`, `inventory_source` | 20 | 2.0-playbook_set_ddve.yml | converted |
| [fjacquet.ppdm.sources.add_vcenter](sources/add_vcenter.yml) | Trust the vCenter certificate, create its credential and add it as an inventory source. | `certificate`, `credential`, `inventory_source` | 21 | 2.1-playbook_set_vsphere.yml | converted |
| [fjacquet.ppdm.sources.list_unassigned_credentials](sources/list_unassigned_credentials.yml) | List credentials of type KUBERNETES that no consumer uses (read-only). | `credential_info` | 22 | 2.0-playbook_test_unassigned_credentials.yml | converted |
| [fjacquet.ppdm.sources.add_cloud_snapshot_manager](sources/add_cloud_snapshot_manager.yml) | Create the CLOUD_SNAPSHOT_MANAGER credential and inventory source for a tenant. | `credential`, `inventory_source` | 28 | 2.0-playbook_set_csm.yml | converted |
| [fjacquet.ppdm.sources.list_credential_usage](sources/list_credential_usage.yml) | Show which objects use a credential (read-only). | `api`, `credential_info` | 29 | 2.0-playbook_test_unassigned_credentials_id.yml | converted |
| [fjacquet.ppdm.sources.get_inventory_and_storage_systems](sources/get_inventory_and_storage_systems.yml) | List inventory sources (optionally filtered) and the Data Domain storage system (read-only). | `inventory_source_info`, `storage_system_info` | 97 | 99_get_inventory.yml, 99_get_data_domain.yml | converted |
| [fjacquet.ppdm.sources.get_vib_details](sources/get_vib_details.yml) | Read the vSphere VIB details below a vCenter inventory source (read-only). | `api`, `inventory_source_info` | 98 | 9.2-playbook_vib_details.yml | converted |

### Protection: policies, rules, assignments

| Playbook | What it does | Modules | Former example | Original bottkars files | Status |
|----------|--------------|---------|----------------|-------------------------|--------|
| [fjacquet.ppdm.protection.get_policies](protection/get_policies.yml) | List the protection policies (read-only). Protection policies exist only under /api/v3 in 20.3.0. | `api` | 110 | 110.0_get_protection_policies.yaml | converted |
| [fjacquet.ppdm.protection.run_policy](protection/run_policy.yml) | Run a protection policy now on the assets matching a filter and wait for the activities; refuses to run unless policy_run_confirm is true. | `api`, `protection_policy_run` | 111 | 110.4_playbook_start_policy.yaml, 120.3_playbook_start_policy.yaml, 130.4_playbook_start_k8s_policy.yaml | converted |
| [fjacquet.ppdm.protection.get_rules](protection/get_rules.yml) | List the protection rules, optionally filtered by name (read-only). | `protection_rule_info` | 112 | playbook_get_rule.yml | converted |
| [fjacquet.ppdm.protection.get_policy](protection/get_policy.yml) | Show the protection policy of a given name (read-only). | `api` | 113 | playbook_get_k8s_policy.yml | converted |
| [fjacquet.ppdm.protection.add_file_system_policy](protection/add_file_system_policy.yml) | Ensure a daily synthetic full policy on a Data Domain, updated when it differs. | `protection_policy`, `storage_system_info` | 120 | 120.1_playbook_add_fs_policy.yaml | converted |
| [fjacquet.ppdm.protection.add_mssql_policy](protection/add_mssql_policy.yml) | Create the OS credential and ensure a daily full plus hourly log policy, updated when it differs. | `credential`, `protection_policy`, `storage_system_info` | 121 | 120.1_playbook_add_mssql_policy.yaml | converted |
| [fjacquet.ppdm.protection.add_exchange_policy](protection/add_exchange_policy.yml) | Create the OS credential and a daily synthetic full policy unless one of that name exists. | `api`, `credential`, `storage_system_info` | 122 | 120.1_playbook_add_exchange_policy.yaml | converted |
| [fjacquet.ppdm.protection.assign_assets_to_policy](protection/assign_assets_to_policy.yml) | Assign the assets matching a filter to a policy, sending only the missing assignments; refuses to run unless assign_confirm is true. | `api`, `protection_policy_assets` | 123 | 120.2_playbook_add_assets_to_policy.yaml | converted |
| [fjacquet.ppdm.protection.create_vm_policy](protection/create_vm_policy.yml) | Ensure a daily full policy for VMware virtual machines on a Data Domain, updated when it differs. | `protection_policy`, `storage_system_info` | - | - | new |
| [fjacquet.ppdm.protection.create_k8s_policy](protection/create_k8s_policy.yml) | Ensure a daily full policy for Kubernetes namespaces on a Data Domain, updated when it differs. | `protection_policy`, `storage_system_info` | - | - | new |
| [fjacquet.ppdm.protection.run_discovery](protection/run_discovery.yml) | Start a discovery on an inventory source and wait for it; refuses to run unless discovery_confirm is true. | `discovery` | - | - | new |
| [fjacquet.ppdm.protection.create_rule](protection/create_rule.yml) | Ensure a v3 rule assigning the assets selected by the rule_filters variable (VMs with a tag) to a policy; the policy from create_vm_policy must exist first. | `protection_rule` | - | - | new |
| [fjacquet.ppdm.protection.run_rule](protection/run_rule.yml) | Run a v3 protection rule now; refuses to run unless rule_run_confirm is true. | `protection_rule_run` | - | - | new |
| [fjacquet.ppdm.protection.create_resource_group](protection/create_resource_group.yml) | Ensure a resource group and a v3 rule assigning the assets selected by the resource_group_rule_filters variable (VMs with a tag) to it. | `resource_group`, `protection_rule` | - | - | new |
| [fjacquet.ppdm.protection.create_protection_group](protection/create_protection_group.yml) | Ensure one protection group (storage-direct by default; 20.3.0 knows only storage-direct and Oracle Data Guard), with an optional protection policy. | `protection_group` | - | - | new |

### Kubernetes

| Playbook | What it does | Modules | Former example | Original bottkars files | Status |
|----------|--------------|---------|----------------|-------------------------|--------|
| [fjacquet.ppdm.kubernetes.get_asset_copies](kubernetes/get_asset_copies.yml) | Find a namespace asset that has a copy and list its copies (read-only). | `api` | 33 | 30.2-playbook_get_k8s_asset_copies.yml | converted |
| [fjacquet.ppdm.kubernetes.restore_copy](kubernetes/restore_copy.yml) | Restore the latest copy of a namespace (to a new namespace by default); refuses to run unless restore_confirm is true. | `api` | 41 | 40.2-playbook_restore_k8s_asset_copies.yml | converted |
| [fjacquet.ppdm.kubernetes.add_kubernetes](kubernetes/add_kubernetes.yml) | Trust the API server certificate, store the discovery token and add the cluster as an inventory source. | `certificate`, `credential`, `inventory_source` | 130 | playbook_add_k8s.yml, playbook_rbac_add_k8s_to_ppdm.yml, playbook_rbac_add_k8s_to_ppdm_reg_cred.yml, playbook_rbac_add_k8s_to_ppdm_reg_cred_assetsource_enable.yml | converted |
| [fjacquet.ppdm.kubernetes.run_discovery](kubernetes/run_discovery.yml) | Start a discovery on the Kubernetes inventory source (change k8s_hostname for another source). | `api`, `inventory_source_info` | 131 | 130.3_playbook_start_k8s_discoveries_by_query.yaml, 130.4_playbook_start_k8s_discoveries.yaml, playbook_start_k8s_discoveries.yml | converted |
| [fjacquet.ppdm.kubernetes.add_policy_and_rule](kubernetes/add_policy_and_rule.yml) | Create a Kubernetes policy, a v3 rule assigning the Kubernetes assets with a label to it, and run the rule. | `api`, `protection_rule`, `protection_rule_run`, `storage_system_info` | 132 | 130.2_playbook_add_k8s_policy_and_rule.yaml | converted |
| [fjacquet.ppdm.kubernetes.add_kubernetes_with_vcenter](kubernetes/add_kubernetes_with_vcenter.yml) | Add the cluster with its vCenter (CSI drivers as a process): trust, credential, inventory source with k8s details. | `certificate`, `credential`, `inventory_source`, `inventory_source_info` | 133 | 130.1_playbook_rbac_add_k8s_to_ppdm.yaml | converted |
| [fjacquet.ppdm.kubernetes.trust_root_certificate](kubernetes/trust_root_certificate.yml) | Add the root CA chain of the Kubernetes API server to the PPDM trust store (the chain is read from a local file). | `api` | 134 | playbook_set_k8s_root_cert.yml | converted |
| [fjacquet.ppdm.kubernetes.set_controller_config](kubernetes/set_controller_config.yml) | Replace one details.k8s.configurations entry (deep change, so a read-modify-write with the api module). | `api`, `inventory_source_info` | 135 | 9.12-playbook_set_k8s_controller_config.yml | converted |
| [fjacquet.ppdm.kubernetes.list_clusters](kubernetes/list_clusters.yml) | List the Kubernetes inventory sources with address and port (read-only). | `inventory_source_info` | 136 | 99_playbook_get_k8s_info.yml | converted |

### Cloud DR

| Playbook | What it does | Modules | Former example | Original bottkars files | Status |
|----------|--------------|---------|----------------|-------------------------|--------|
| [fjacquet.ppdm.clouddr.enable_component](clouddr/enable_component.yml) | Start the Cloud DR (cdr) component when it is disabled. | `api` | 23 | 2.2-playbook_set_cdra_enabled.yml | converted |
| [fjacquet.ppdm.clouddr.disable_component](clouddr/disable_component.yml) | Disable the Cloud DR (cdr) component; refuses to run unless cloud_dr_confirm is true. | `api` | 50 | 2.2-playbook_set_cdra_disabled.yml | converted |
| [fjacquet.ppdm.clouddr.configure_account](clouddr/configure_account.yml) | Wait for the Cloud DR component, then create the Azure account or update its keys when it exists. | `api` | 51 | 2.3-playbook_configure_cloud_dr_account.yml, 2.3-playbook_updarte_cloud_dr_account.yml | converted |
| [fjacquet.ppdm.clouddr.set_target](clouddr/set_target.yml) | Create the data target (storage account) of the Azure Cloud DR account. | `api` | 52 | 2.4-playbook_set_cloud_dr_target.yml | converted |
| [fjacquet.ppdm.clouddr.deploy_server](clouddr/deploy_server.yml) | Deploy the Cloud DR server in the cloud (this creates billable cloud resources); refuses to run unless cloud_dr_confirm is true. | `api` | 53 | 2.5-playbook_set_cdrs_deployment.yml | converted |
| [fjacquet.ppdm.clouddr.get_server](clouddr/get_server.yml) | Show the Cloud DR server configuration (read-only). | `api` | 54 | 2.6-playbook_get_cdrs_deployment.yml | converted |
| [fjacquet.ppdm.clouddr.delete_server](clouddr/delete_server.yml) | Delete the Cloud DR server deployment; refuses to run unless cloud_dr_confirm is true. | `api` | 55 | 2.7-playbook_delete_cdrs_deployment.yml | converted |

### Agents

| Playbook | What it does | Modules | Former example | Original bottkars files | Status |
|----------|--------------|---------|----------------|-------------------------|--------|
| [fjacquet.ppdm.agents.get_registration_status](agents/get_registration_status.yml) | List the protection agents with their registration status (read-only; replaces the unversioned /agents-list call). | `api` | 100 | 100.0_list_agents.yml, 100.5_get_agent_registration_status.yaml | converted |
| [fjacquet.ppdm.agents.approve_agent_ips](agents/approve_agent_ips.yml) | Approve each IP of agent_ips on the agent whitelist (24 hours) unless already approved and not expired. | `api` | 101 | 100.4_create_whitelistentry.yaml, 100.6_get_whitelist.yaml | converted |
| [fjacquet.ppdm.agents.delete_whitelist_entries](agents/delete_whitelist_entries.yml) | Delete the whitelist entries listed in whitelist_ids; refuses to run unless whitelist_confirm is true. | `api` | 102 | 100.8_delete_whitelistentry.yaml | converted |
| [fjacquet.ppdm.agents.set_agent_dns_lookups](agents/set_agent_dns_lookups.yml) | Set the enableLookups property of APP_AGENT_SETTING (agent_enable_lookups true uses DNS, false uses IP). | `api` | 103 | 100.2_set_dns_for_agents.yaml, 100.3_set_ip_for_agents.yaml | converted |
| [fjacquet.ppdm.agents.approve_agents_by_hostname](agents/approve_agents_by_hostname.yml) | Look up the address of each registered agent by host name and approve it on the whitelist (24 hours). | `api` | 104 | 100.4_create_whitelistentry_from_addressquery.yaml | converted |

### Assets, copies, activities and VM restore

| Playbook | What it does | Modules | Former example | Original bottkars files | Status |
|----------|--------------|---------|----------------|-------------------------|--------|
| [fjacquet.ppdm.assets.get_assets](assets/get_assets.yml) | List assets, optionally filtered with a PPDM filter string (read-only). | `api` | 30 | 30.0-playbook_get_assets.yml | converted |
| [fjacquet.ppdm.assets.get_vm_asset_copies](assets/get_vm_asset_copies.yml) | Find a protected VM asset by name and list its copies (read-only). | `api` | 31 | 30.1-playbook_get_vm_asset_copies.yml, 30.1-playbook_search_vm_asset_by_name.yml | converted |
| [fjacquet.ppdm.assets.get_activities](assets/get_activities.yml) | List activities, optionally filtered with a PPDM filter string (read-only). | `api` | 32 | 31.1-playbook_get_activities.yml | converted |
| [fjacquet.ppdm.assets.restore_vm_copy](assets/restore_vm_copy.yml) | Restore the latest copy of a VM to its original location; refuses to run unless restore_confirm is true. | `api` | 40 | 40.1-playbook_restore_vm_asset_copies.yml | converted |
| [fjacquet.ppdm.assets.find_assets](assets/find_assets.yml) | Find assets by name and type and hosts by name, and show name, id and type (read-only). | `asset_info`, `host_info` | - | - | new |

### Maintenance: update packages

| Playbook | What it does | Modules | Former example | Original bottkars files | Status |
|----------|--------------|---------|----------------|-------------------------|--------|
| [fjacquet.ppdm.maintenance.get_update_packages](maintenance/get_update_packages.yml) | List the ACTIVE update package (set update_category to HISTORY for the history; read-only). | `api` | 92 | 9.9-playbook_get_ppdm_update_package_active.yml, 9.9-playbook_get_ppdm_update_package_history.yml | converted |
| [fjacquet.ppdm.maintenance.precheck_update_package](maintenance/precheck_update_package.yml) | Start the precheck of the active update package and show its validation details. | `api` | 93 | 9.9-playbook_precheck_update_ppdm.yml | converted |
| [fjacquet.ppdm.maintenance.install_update_package](maintenance/install_update_package.yml) | Install the active update package; refuses to run unless update_confirm is true. | `api` | 94 | 9.9-playbook_install_update_ppdm.yml | converted |
| [fjacquet.ppdm.maintenance.delete_update_package](maintenance/delete_update_package.yml) | Delete the active update package; refuses to run unless update_confirm is true. | `api` | 95 | 9.9-playbook_delete_ppdm_update_package.yml | converted |

The bottkars community project is credited in [NOTICE](../NOTICE).

The former example number is the file-name prefix the playbook had under `docs/examples/`, kept so the mapping to the community source files stays traceable.

## Not converted

| Original bottkars file | Reason |
|------------------------|--------|
| 100.1_download_agents.yml, 100.3_playbook_copy_and_deploy_windows_agent.yaml, 100.9_playbook-uninstall-windows-agent.yaml | Agent download, deployment and uninstall on Windows hosts: they run on the agent host, not through the PPDM REST API |
| 120.0_ensure_mssql_aag_local_user.yaml | Creates a Windows local user and SQL Server logins on the database hosts (`ansible.windows`, `community.general.mssql_script`), not PPDM REST |
| 9.9-playbook_upload_update_ppdm.yml, 9.9-playbook_upload_update_ppdm_native.yml | Upload the update package with `curl` or a native multipart upload; the `api` module only sends JSON bodies and cannot upload a file |
| 99-playbook_upgrade_state.yml, scratch_check_update_state.yml | Poll the upgrade status on port 14443, a different service than the REST API port |
| 99_re-ip_dd_after_headswap.yml | One-off re-IP helper for the author's lab after a Data Domain head swap |
| scratch.yml, scratch_create_flr_session.yml, scratch_get_asset_setings.yml, scratch_get_flr_sessions.yml, scratch_get_flr.yml, scratch_k8s_info.yml, time.yml, xxx_restore.yaml, ppdm-restore-2022.10.15-002.yml | Scratch and experiment files of the original project (file level restore experiments with lab ids, an epoch conversion demo, restore request fragments, variable stubs); `scratch.yml` also contains a literal password, which is not carried over |
