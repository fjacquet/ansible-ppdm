#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: protection_group
short_description: Manage protection groups on PowerProtect Data Manager
description:
- Create, update or remove a protection group, identified by its name.
- PowerProtect Data Manager 20.3.0 only knows Oracle Data Guard and Storage Direct (PowerMax and PowerStore)
  protection groups, see I(type).
- The members of a group are chosen by I(natural_ids), there is no member list of asset ids.
- Updates use PATCH.
- Protection group names are assumed to be unique (the group is found by exact name); if two groups share
  the name the module fails and lists the IDs.
version_added: 0.3.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
- action_common_attributes
notes:
- Unofficial collection, not affiliated with Dell. Written against the PowerProtect Data Manager 20.3.0
  REST API.
- The C(ProtectionGroup) schema of the 20.3.0 OpenAPI has no required field.
- The server-derived fields C(id), C(createdAt), C(updatedAt), C(lastAvailableCopyTime), C(lastDiscoveryStatus),
  C(protectionStatus), C(operatingSystems) and C(supportedProtectionProtocols) are never sent and are
  ignored by the idempotence check.
- The policy reference is sent as C(protectionPolicyRef) with only its C(id). PPDM adds C(name) and C(backupMechanism)
  itself, so they do not cause a change.
seealso:
- module: fjacquet.ppdm.protection_group_info
  description: List protection groups.
- module: fjacquet.ppdm.protection_policy
  description: Manage protection policies.
options:
  state:
    description:
    - Whether the protection group must exist.
    type: str
    choices:
    - present
    - absent
    default: present
  name:
    description:
    - Protection group name, used as the key.
    type: str
    required: true
  description:
    description:
    - Protection group description.
    type: str
  type:
    description:
    - Type of the protection group.
    type: str
    choices:
    - ORACLE_DATA_GUARD
    - POWER_MAX_STORAGE_DIRECT_APPLICATION
    - STORAGE_DIRECT_APPLICATION
  subtype:
    description:
    - Subtype, for C(STORAGE_DIRECT_APPLICATION) groups.
    type: str
    choices:
    - GENERIC
    - MEDITECH
  member_asset_type:
    description:
    - Asset type of the member assets.
    type: str
    choices:
    - ORACLE_DATABASE
    - POWERSTORE_BLOCK
    - POWER_MAX_BLOCK
  backup_strategy:
    description:
    - Backup strategy of the group.
    type: str
    choices:
    - BACKUP_ALL
    - BACKUP_BY_RANK
    - BACKUP_CUSTOM
    - BACKUP_PRIMARY_ONLY
    - BACKUP_STANDALONE
  auto_assign_to_policy:
    description:
    - Whether member assets are automatically assigned to the protection policy given by I(protection_policy)
      or I(protection_policy_id).
    type: bool
  protection_policy:
    description:
    - Name of the protection policy, resolved to its id (sent as C(protectionPolicyRef.id)). The module
      fails when no policy or several policies have this name. Mutually exclusive with I(protection_policy_id).
    type: str
  protection_policy_id:
    description:
    - Id of the protection policy, used as is. Mutually exclusive with I(protection_policy).
    type: str
  natural_ids:
    description:
    - Natural ids that decide which assets belong to the group. The list replaces the whole list on PPDM.
    type: list
    elements: str
  config:
    description:
    - Extra request body fields passed through as is, for example C(dataBackupRole) or C(logBackupRole).
    - The module fails when C(config) contains C(id) or C(_links), the server owns them.
    - The module fails when C(config) contains a key that a named option sets (C(name), C(description),
      C(type), C(subtype), C(memberAssetType), C(backupStrategy), C(autoAssignToPolicy), C(protectionPolicyRef)
      and C(naturalIds)), use the option instead.
    - Each top-level key replaces the whole value of that field, the merge with the existing object is
      shallow (top-level keys only).
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
- name: Create an Oracle Data Guard protection group
  fjacquet.ppdm.protection_group:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    name: ora-dg
    type: ORACLE_DATA_GUARD
    member_asset_type: ORACLE_DATABASE
    backup_strategy: BACKUP_PRIMARY_ONLY
    auto_assign_to_policy: true
    protection_policy: oracle-gold
    natural_ids: ["orcl-dg-1"]

- name: Remove a protection group
  fjacquet.ppdm.protection_group:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    name: ora-dg
    state: absent
'''

RETURN = r'''
protection_group:
  description: The managed protection group.
  returned: success
  type: dict
  sample: {"id": "1", "name": "ora-dg", "type": "ORACLE_DATA_GUARD"}
diff:
  description: Before and after.
  returned: success
  type: dict
  sample: {"before": {}, "after": {"name": "ora-dg"}}
'''

ARGUMENT_SPEC = dict(
    state=dict(type='str', choices=['present', 'absent'], default='present'),
    name=dict(type='str', required=True),
    description=dict(type='str'),
    type=dict(
        type='str',
        choices=[
            'ORACLE_DATA_GUARD',
            'POWER_MAX_STORAGE_DIRECT_APPLICATION',
            'STORAGE_DIRECT_APPLICATION',
        ],
    ),
    subtype=dict(type='str', choices=['GENERIC', 'MEDITECH']),
    member_asset_type=dict(type='str', choices=['ORACLE_DATABASE', 'POWERSTORE_BLOCK', 'POWER_MAX_BLOCK']),
    backup_strategy=dict(
        type='str',
        choices=[
            'BACKUP_ALL',
            'BACKUP_BY_RANK',
            'BACKUP_CUSTOM',
            'BACKUP_PRIMARY_ONLY',
            'BACKUP_STANDALONE',
        ],
    ),
    auto_assign_to_policy=dict(type='bool'),
    protection_policy=dict(type='str'),
    protection_policy_id=dict(type='str'),
    natural_ids=dict(type='list', elements='str'),
    config=dict(type='dict'),
)
# fmt: on
# END GENERATED

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import (
    PpdmError,
    client_from_module,
    connection_argument_spec,
    fail_from,
    merge_config,
)

# server-derived (the ProtectionGroup schema marks none readOnly, ROUTES lists none), never sent
READONLY = (
    "id",
    "createdAt",
    "updatedAt",
    "lastAvailableCopyTime",
    "lastDiscoveryStatus",
    "protectionStatus",
    "operatingSystems",
    "supportedProtectionProtocols",
)


def policy_id(client, p):
    """The policy id (name resolved through the client, an id used as is); None when no option sets it."""
    if p["protection_policy_id"] is not None:
        return p["protection_policy_id"]
    if p["protection_policy"] is None:
        return None
    found = client.find_one("protection-policies", "name", p["protection_policy"])
    if not found:
        raise PpdmError("protection policy %s not found" % client.scrub_text(p["protection_policy"], 200))
    return found["id"]


def main():
    module = AnsibleModule(
        argument_spec=dict(connection_argument_spec(), **ARGUMENT_SPEC),
        mutually_exclusive=[("protection_policy", "protection_policy_id")],
        supports_check_mode=True,
    )
    p = module.params
    client = client_from_module(module)
    try:
        if p["state"] == "absent":
            res = client.remove("protection-groups", "name", p["name"], check_mode=module.check_mode)
        else:
            named = {
                "name": p["name"],
                "description": p["description"],
                "type": p["type"],
                "subtype": p["subtype"],
                "memberAssetType": p["member_asset_type"],
                "backupStrategy": p["backup_strategy"],
                "autoAssignToPolicy": p["auto_assign_to_policy"],
                "naturalIds": p["natural_ids"],
                "protectionPolicyRef": None,
            }
            desired = merge_config(named, p["config"])  # before any request: bad input sends nothing
            pid = policy_id(client, p)
            if pid is not None:
                desired["protectionPolicyRef"] = {"id": pid}
            res = client.ensure(
                "protection-groups",
                desired,
                check_mode=module.check_mode,
                readonly=READONLY,
                subset_keys=("protectionPolicyRef",),
            )
    except PpdmError as err:
        fail_from(module, err)
    module.exit_json(changed=res["changed"], protection_group=res.get("object", {}), diff=res["diff"])


if __name__ == "__main__":
    main()
