#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: storage_system
short_description: Update a storage system on PowerProtect Data Manager
description:
- Update an existing storage system, identified by its name.
- Storage systems cannot be created or deleted through the API in 20.3.0, they appear when an inventory
  source is added; the module fails if none matches.
version_added: 1.0.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
options:
  state:
    description:
    - Only C(present) is supported.
    type: str
    choices:
    - present
    default: present
  name:
    description:
    - Name of the existing storage system, used as the key.
    type: str
    required: true
  description:
    description:
    - Storage system description.
    type: str
  location_id:
    description:
    - ID of the location of the storage system.
    type: str
  dd_location_id:
    description:
    - ID of the location for the PowerProtect Data Domain.
    type: str
  config:
    description:
    - Extra request body fields passed through as is (for example C(details)).
    - Each top-level key replaces the whole value of that field.
    - Do not put secrets here, values are not masked in diff or return values.
    type: dict
'''

EXAMPLES = r'''
- name: Set a storage system description
  fjacquet.ppdm.storage_system:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    name: dd01.example.com
    description: Primary DD
'''

RETURN = r'''
storage_system:
  description: The updated storage system.
  returned: success
  type: dict
diff:
  description: Before and after.
  returned: success
  type: dict
'''

ARGUMENT_SPEC = dict(
    state=dict(type='str', choices=['present'], default='present'),
    name=dict(type='str', required=True),
    description=dict(type='str'),
    location_id=dict(type='str'),
    dd_location_id=dict(type='str'),
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
)


def main():
    module = AnsibleModule(
        argument_spec=dict(connection_argument_spec(), **ARGUMENT_SPEC),
        supports_check_mode=True,
    )
    p = module.params
    client = client_from_module(module)
    desired = {
        "name": p["name"],
        "description": p["description"],
        "locationId": p["location_id"],
        "ddLocationId": p["dd_location_id"],
    }
    desired = {k: v for k, v in desired.items() if v is not None}
    desired.update(p["config"] or {})
    try:
        if client.find_one("storage-systems", "name", p["name"]) is None:
            module.fail_json(
                msg="storage system %r not found: storage systems cannot be created through the "
                "API, add the matching inventory source first" % p["name"]
            )
        res = client.ensure("storage-systems", desired, check_mode=module.check_mode)
    except PpdmError as err:
        fail_from(module, err)
    module.exit_json(changed=res["changed"], storage_system=res["object"], diff=res["diff"])


if __name__ == "__main__":
    main()
