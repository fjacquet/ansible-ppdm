#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: restore_plan
short_description: Manage restore plans on PowerProtect Data Manager
description:
- Create, update or remove a restore plan, identified by its name.
- Updates use PATCH.
- Restore plan names are assumed to be unique (the plan is found by exact name); if two plans share the
  name the module fails and lists the IDs.
version_added: 0.4.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
- action_common_attributes
notes:
- Unofficial collection, not affiliated with Dell. Written against the PowerProtect Data Manager 20.3.0
  REST API.
- The server-owned fields C(createdAt), C(id), C(lastRun), C(state), C(stateReason) and C(updatedAt) are
  never sent and are ignored by the idempotence check.
- I(restore_groups) and I(schedule) are compared as a subset, in order and with the same list length,
  so fields PPDM adds (such as the C(id), C(state) and C(stateReason) of each restore group) do not cause
  a change.
- PPDM refuses to delete a restore plan while it runs (HTTP 409), the module then fails with the PPDM
  message.
- The C(extendedData) of a restore group is free-form and may carry credentials. It is passed and returned
  as is, not masked.
seealso:
- module: fjacquet.ppdm.restore_plan_info
  description: List restore plans.
options:
  state:
    description:
    - Whether the restore plan must exist.
    type: str
    choices:
    - present
    - absent
    default: present
  name:
    description:
    - Restore plan name, used as the key.
    type: str
    required: true
  description:
    description:
    - Restore plan description.
    type: str
  fallback_strategy:
    description:
    - What the plan does when a restore group fails (the C(fallbackStrategy) field).
    type: str
    choices:
    - CANCEL_ON_FAILURE
    - CONTINUE_ON_FAILURE
  restore_groups:
    description:
    - Restore groups of the plan, sent as C(restoreGroups) and passed to PPDM as is, only checked to be
      a list of dicts. The C(assetType) of a group is C(VMWARE_VIRTUAL_MACHINE) in 20.3.0.
    - The list replaces the whole list on PPDM.
    type: list
    elements: dict
  schedule:
    description:
    - Schedule of the plan, for example C({startTime}).
    type: dict
  config:
    description:
    - Extra request body fields passed through as is.
    - The module fails when C(config) contains C(id) or C(_links), the server owns them.
    - The module fails when C(config) contains a key that a named option sets (C(name), C(description),
      C(fallbackStrategy), C(restoreGroups) and C(schedule)), use the option instead.
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
- name: Create a restore plan
  fjacquet.ppdm.restore_plan:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    name: dr-web
    fallback_strategy: CONTINUE_ON_FAILURE
    restore_groups:
      - name: web-vms
        assetType: VMWARE_VIRTUAL_MACHINE

- name: Remove a restore plan
  fjacquet.ppdm.restore_plan:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    name: dr-web
    state: absent
'''

RETURN = r'''
restore_plan:
  description: The managed restore plan.
  returned: success
  type: dict
  sample: {"id": "1", "name": "dr-web"}
diff:
  description: Before and after.
  returned: success
  type: dict
  sample: {"before": {}, "after": {"name": "dr-web"}}
'''

ARGUMENT_SPEC = dict(
    state=dict(type='str', choices=['present', 'absent'], default='present'),
    name=dict(type='str', required=True),
    description=dict(type='str'),
    fallback_strategy=dict(type='str', choices=['CANCEL_ON_FAILURE', 'CONTINUE_ON_FAILURE']),
    restore_groups=dict(type='list', elements='dict'),
    schedule=dict(type='dict'),
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

READONLY = ("createdAt", "id", "lastRun", "state", "stateReason", "updatedAt")


def main():
    module = AnsibleModule(argument_spec=dict(connection_argument_spec(), **ARGUMENT_SPEC), supports_check_mode=True)
    p = module.params
    client = client_from_module(module)
    try:
        if p["state"] == "absent":
            res = client.remove("restore-plans", "name", p["name"], check_mode=module.check_mode)
        else:
            desired = merge_config(
                {
                    "name": p["name"],
                    "description": p["description"],
                    "fallbackStrategy": p["fallback_strategy"],
                    "restoreGroups": p["restore_groups"],
                    "schedule": p["schedule"],
                },
                p["config"],
            )
            res = client.ensure(
                "restore-plans",
                desired,
                check_mode=module.check_mode,
                readonly=READONLY,
                subset_keys=("restoreGroups", "schedule"),
            )
    except PpdmError as err:
        fail_from(module, err)
    module.exit_json(changed=res["changed"], restore_plan=res.get("object", {}), diff=res["diff"])


if __name__ == "__main__":
    main()
