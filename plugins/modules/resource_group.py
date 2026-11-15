#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: resource_group
short_description: Manage resource groups on PowerProtect Data Manager
description:
- Create, update or remove a resource group, identified by its name.
- Updates use PATCH.
- Resource group names are assumed to be unique (the group is found by exact name); if two groups share
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
- The C(ResourceGroup) schema of the 20.3.0 OpenAPI has no required field.
- The server-owned fields C(createdAt), C(createdBy), C(id), C(numberOfResources) and C(updatedAt) are
  never sent and are ignored by the idempotence check.
- A resource group has no member list.
- Assets join a group only through a protection rule with C(action=ASSIGN_RESOURCE_GROUP).
- See M(fjacquet.ppdm.protection_rule).
seealso:
- module: fjacquet.ppdm.resource_group_info
  description: List resource groups.
- module: fjacquet.ppdm.protection_rule
  description: Manage protection rules, which assign assets to a resource group.
options:
  state:
    description:
    - Whether the resource group must exist.
    type: str
    choices:
    - present
    - absent
    default: present
  name:
    description:
    - Resource group name, used as the key.
    type: str
    required: true
  description:
    description:
    - Resource group description.
    type: str
  config:
    description:
    - Extra request body fields passed through as is.
    - The module fails when C(config) contains C(id) or C(_links), the server owns them.
    - The module fails when C(config) contains a key that a named option sets (C(name) and C(description)),
      use the option instead.
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
- name: Create a resource group
  fjacquet.ppdm.resource_group:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    name: web
    description: Web tier

- name: Remove a resource group
  fjacquet.ppdm.resource_group:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    name: web
    state: absent
'''

RETURN = r'''
resource_group:
  description: The managed resource group.
  returned: success
  type: dict
  sample: {"id": "1", "name": "web", "description": "Web tier"}
diff:
  description: Before and after.
  returned: success
  type: dict
  sample: {"before": {}, "after": {"name": "web"}}
'''

ARGUMENT_SPEC = dict(
    state=dict(type='str', choices=['present', 'absent'], default='present'),
    name=dict(type='str', required=True),
    description=dict(type='str'),
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

# server-owned, never sent (ROUTES lists none for resource-groups)
READONLY = ("createdAt", "createdBy", "id", "numberOfResources", "updatedAt")


def main():
    module = AnsibleModule(
        argument_spec=dict(connection_argument_spec(), **ARGUMENT_SPEC),
        supports_check_mode=True,
    )
    p = module.params
    client = client_from_module(module)
    try:
        if p["state"] == "absent":
            res = client.remove("resource-groups", "name", p["name"], check_mode=module.check_mode)
        else:
            desired = merge_config({"name": p["name"], "description": p["description"]}, p["config"])
            res = client.ensure("resource-groups", desired, check_mode=module.check_mode, readonly=READONLY)
    except PpdmError as err:
        fail_from(module, err)
    module.exit_json(changed=res["changed"], resource_group=res.get("object", {}), diff=res["diff"])


if __name__ == "__main__":
    main()
