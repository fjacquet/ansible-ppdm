#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: protection_policy
short_description: Manage protection policies on PowerProtect Data Manager
description:
- Create, update or remove a protection policy, identified by its name, through the v3 API.
- Updates use PATCH, the only update verb the API offers for policies.
- Names are not enforced unique by the API; if two policies share the name the module fails and lists
  both IDs.
- The asset type of an existing policy cannot be changed, the module fails and asks to delete and recreate
  the policy.
version_added: 0.2.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
- action_common_attributes
notes:
- Unofficial collection, not affiliated with Dell. Written against the PowerProtect Data Manager 20.3.0
  REST API.
- I(objectives) and I(overrides) are lists that replace the whole list on PPDM. To update them without
  churn, copy them with their C(id) values from M(fjacquet.ppdm.protection_policy_info) and edit the copy.
- Idempotence treats each desired item as a subset of the existing item at the same index (same list length),
  so ids and defaults PPDM adds do not cause a change; a real difference sends your lists as given.
- The structure of I(objectives) (C(target), C(operations), C(retentions), C(config), C(options)) depends
  on I(asset_type), see the examples and the PPDM 20.3.0 REST API reference.
seealso:
- module: fjacquet.ppdm.protection_policy_info
  description: List protection policies.
options:
  state:
    description:
    - Whether the policy must exist.
    type: str
    choices:
    - present
    - absent
    default: present
  name:
    description:
    - Policy name, used as the key.
    type: str
    required: true
  asset_type:
    description:
    - Asset type protected by the policy (the C(assetType) discriminator). Required when I(state=present).
      Cannot be changed on an existing policy.
    type: str
    choices:
    - CLOUD_DIRECTOR_VAPP
    - FILE_SYSTEM
    - GENERIC_APPLICATION_ASSET
    - HYPERV_VIRTUAL_MACHINE
    - KUBERNETES
    - MICROSOFT_EXCHANGE_DATABASE
    - MICROSOFT_SQL_DATABASE
    - NAS_SHARE
    - NATIVEEDGE_VIRTUAL_MACHINE
    - NUTANIX_VIRTUAL_MACHINE
    - ORACLE_DATABASE
    - POWERSTORE_BLOCK
    - POWER_MAX_BLOCK
    - SAP_HANA_DATABASE
    - VMWARE_VIRTUAL_MACHINE
  description:
    description:
    - Policy description.
    type: str
  disabled:
    description:
    - Whether the policy is disabled (deprecated by PPDM 20.3.0 but still accepted).
    type: bool
  load_balance_enabled:
    description:
    - Whether SQL AAG load balancing is enabled for the policy.
    type: bool
  purpose:
    description:
    - Purpose of the policy. The module fails when it differs from the existing policy, PPDM cannot change
      it through PATCH.
    type: str
    choices:
    - CENTRALIZED
    - EXCLUSION
    - SELF_SERVICE
  objectives:
    description:
    - Objectives of the policy, passed to PPDM as is after validation.
    - Each item must be a dict with C(type) one of C(ARCHIVE), C(BACKUP), C(CLOUD_DR), C(CLOUD_TIER),
      C(OBJECT_STORAGE_BACKUP), C(REPLICATION), C(SNAPSHOT) or C(VAULT).
    - PPDM 20.3 requires a UUID C(id) on each new objective, operation and retention (verified on a live
      lab, HTTP 400 otherwise), generate them yourself. A C(SNAPSHOT) operation must not set C(backupLevel).
    - Timestamps such as C(window.startTime) are compared as instants, so C(...00.000Z) and C(...00Z)
      are the same.
    - The whole list replaces the existing one, nested values are not merged. Copy existing objectives
      with their ids from M(fjacquet.ppdm.protection_policy_info) to update them.
    - A run is unchanged when each desired objective is a subset of the existing one at the same index
      (same list length).
    type: list
    elements: dict
  overrides:
    description:
    - Schedule skip overrides (at most 10), passed to PPDM as is.
    - An empty list removes all overrides.
    - Compared like I(objectives), a subset of the existing list at the same indexes is unchanged.
    type: list
    elements: dict
  config:
    description:
    - The module also fails when C(config) contains C(id) or C(_links), the server owns them.
    - The module fails when C(config) contains a key that a named option sets (C(name), C(assetType),
      C(description), C(disabled), C(loadBalanceEnabled), C(purpose), C(objectives) and C(overrides)),
      use the option instead.
    - Extra request body fields passed through as is.
    - Each top-level key replaces the whole value of that field, the merge with the existing object is
      shallow (top-level keys only), nested values are not merged.
    - Do not put secrets here, values are not masked in diff or return values.
    type: dict
attributes:
  platform:
    platforms: all
  check_mode:
    support: full
  diff_mode:
    support: full
'''

EXAMPLES = r'''
- name: Daily VM backup policy
  fjacquet.ppdm.protection_policy:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    name: vm-gold
    asset_type: VMWARE_VIRTUAL_MACHINE
    purpose: CENTRALIZED
    objectives:
      - type: BACKUP
        target:
          storageContainerId: "{{ storage_container_id }}"
        operations:
          - backupLevel: FULL
            schedule:
              recurrence:
                pattern:
                  type: DAILY
                  interval: 1
              window:
                startTime: "2026-01-01T20:00:00.000Z"
                duration: PT8H
        retentions:
          - time:
              - type: RETENTION
                unitType: DAY
                unitValue: 30
        config:
          backupMechanism: VADP
          dataConsistency: CRASH_CONSISTENT

- name: File system backup policy
  fjacquet.ppdm.protection_policy:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    name: fs-daily
    asset_type: FILE_SYSTEM
    purpose: CENTRALIZED
    objectives:
      - type: BACKUP
        target:
          storageContainerId: "{{ storage_container_id }}"
        operations:
          - backupLevel: FULL
            schedule:
              recurrence:
                pattern:
                  type: DAILY
                  interval: 1
              window:
                startTime: "2026-01-01T20:00:00.000Z"
                duration: PT8H
        retentions:
          - time:
              - type: RETENTION
                unitType: DAY
                unitValue: 30
        config:
          backupMechanism: AUTO
          dataConsistency: CRASH_CONSISTENT

- name: Kubernetes backup policy
  fjacquet.ppdm.protection_policy:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    name: k8s-daily
    asset_type: KUBERNETES
    purpose: CENTRALIZED
    objectives:
      - type: BACKUP
        target:
          storageContainerId: "{{ storage_container_id }}"
        operations:
          - backupLevel: FULL
            schedule:
              recurrence:
                pattern:
                  type: DAILY
                  interval: 1
              window:
                startTime: "2026-01-01T20:00:00.000Z"
                duration: PT8H
        retentions:
          - time:
              - type: RETENTION
                unitType: DAY
                unitValue: 30
        config:
          dataConsistency: CRASH_CONSISTENT

- name: SQL Server backup policy with full and log backups
  fjacquet.ppdm.protection_policy:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    name: sql-prod
    asset_type: MICROSOFT_SQL_DATABASE
    purpose: CENTRALIZED
    objectives:
      - type: BACKUP
        target:
          storageContainerId: "{{ storage_container_id }}"
        operations:
          - backupLevel: FULL
            schedule:
              recurrence:
                pattern:
                  type: DAILY
                  interval: 1
              window:
                startTime: "2026-01-01T20:00:00.000Z"
                duration: PT8H
          - backupLevel: LOG
            schedule:
              recurrence:
                pattern:
                  type: DAILY
                  interval: 1
              window:
                startTime: "2026-01-01T20:00:00.000Z"
                duration: PT8H
        retentions:
          - time:
              - type: RETENTION
                unitType: DAY
                unitValue: 30
        config:
          dataConsistency: APPLICATION_CONSISTENT
          parallelism: 4

- name: Remove a policy
  fjacquet.ppdm.protection_policy:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    name: vm-gold
    asset_type: VMWARE_VIRTUAL_MACHINE
    state: absent
'''

RETURN = r'''
protection_policy:
  description: The managed protection policy.
  returned: success
  type: dict
  sample: {"id": "1", "name": "vm-gold", "assetType": "VMWARE_VIRTUAL_MACHINE", "purpose": "CENTRALIZED"}
diff:
  description: Before and after.
  returned: success
  type: dict
  sample: {"before": {}, "after": {"name": "vm-gold", "assetType": "VMWARE_VIRTUAL_MACHINE"}}
'''

ARGUMENT_SPEC = dict(
    state=dict(type='str', choices=['present', 'absent'], default='present'),
    name=dict(type='str', required=True),
    asset_type=dict(
        type='str',
        choices=[
            'CLOUD_DIRECTOR_VAPP',
            'FILE_SYSTEM',
            'GENERIC_APPLICATION_ASSET',
            'HYPERV_VIRTUAL_MACHINE',
            'KUBERNETES',
            'MICROSOFT_EXCHANGE_DATABASE',
            'MICROSOFT_SQL_DATABASE',
            'NAS_SHARE',
            'NATIVEEDGE_VIRTUAL_MACHINE',
            'NUTANIX_VIRTUAL_MACHINE',
            'ORACLE_DATABASE',
            'POWERSTORE_BLOCK',
            'POWER_MAX_BLOCK',
            'SAP_HANA_DATABASE',
            'VMWARE_VIRTUAL_MACHINE',
        ],
    ),
    description=dict(type='str'),
    disabled=dict(type='bool'),
    load_balance_enabled=dict(type='bool'),
    purpose=dict(type='str', choices=['CENTRALIZED', 'EXCLUSION', 'SELF_SERVICE']),
    objectives=dict(type='list', elements='dict'),
    overrides=dict(type='list', elements='dict'),
    config=dict(type='dict'),
)
# fmt: on
# END GENERATED

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.fjacquet.ppdm.plugins.module_utils._enums import ENUMS
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import (
    PpdmError,
    client_from_module,
    connection_argument_spec,
    fail_from,
    merge_config,
)


def validate_objectives(objectives):
    """Fail before any request; only `type` is required (`id` is PATCH-only, to reference an existing objective)."""
    for i, obj in enumerate(objectives or []):
        if not isinstance(obj, dict) or obj.get("type") not in ENUMS["objective.type"]:
            raise PpdmError(
                "objectives[%d]: 'type' is required and must be one of %s" % (i, ", ".join(ENUMS["objective.type"]))
            )


def main():
    module = AnsibleModule(
        argument_spec=dict(connection_argument_spec(), **ARGUMENT_SPEC),
        required_if=[("state", "present", ("asset_type",))],
        supports_check_mode=True,
    )
    p = module.params
    client = client_from_module(module)
    try:
        if p["state"] == "absent":
            res = client.remove("protection-policies", "name", p["name"], check_mode=module.check_mode)
        else:
            validate_objectives(p["objectives"])
            named = {
                "name": p["name"],
                "assetType": p["asset_type"],
                "description": p["description"],
                "disabled": p["disabled"],
                "loadBalanceEnabled": p["load_balance_enabled"],
                "purpose": p["purpose"],
                "objectives": p["objectives"],
                "overrides": p["overrides"],
            }
            desired = merge_config(named, p["config"])
            existing = client.find_one("protection-policies", "name", p["name"])
            if existing and existing.get("assetType") != p["asset_type"]:
                raise PpdmError(
                    "protection policy %s has asset type %s, it cannot be changed to %s: delete and recreate it"
                    % (p["name"], client.scrub_text(existing.get("assetType"), 64), p["asset_type"])
                )
            if existing and p["purpose"] and existing.get("purpose") not in (None, p["purpose"]):
                raise PpdmError(
                    "protection policy %s has purpose %s, PPDM cannot change it to %s through PATCH"
                    % (p["name"], client.scrub_text(existing.get("purpose"), 64), p["purpose"])
                )
            res = client.ensure(
                "protection-policies",
                desired,
                check_mode=module.check_mode,
                readonly=("createdAt", "updatedAt", "disablementInfo"),
                subset_keys=("objectives", "overrides"),
            )
    except PpdmError as err:
        fail_from(module, err)
    module.exit_json(changed=res["changed"], protection_policy=res.get("object", {}), diff=res["diff"])


if __name__ == "__main__":
    main()
