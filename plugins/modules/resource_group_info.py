#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: resource_group_info
short_description: Get resource groups from PowerProtect Data Manager
description:
- Read-only query of resource groups. Never changes anything.
- Returns every matching object, all pages.
version_added: 0.3.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
- action_common_attributes
notes:
- Unofficial collection, not affiliated with Dell. Written against the PowerProtect Data Manager 20.3.0
  REST API.
seealso:
- module: fjacquet.ppdm.resource_group
  description: Manage resource groups.
options:
  name:
    description:
    - Return only the object whose name equals this value exactly (case-sensitive, checked again on the
      result, whatever the server filter returns). Mutually exclusive with I(filter) and I(id).
    type: str
  filter:
    description:
    - PPDM filter string, for example C(name lk "gold%"). It is passed to PPDM unchanged and its result
      is not re-checked. Mutually exclusive with I(name) and I(id).
    type: str
  id:
    description:
    - Return only the object with this ID. Mutually exclusive with I(name) and I(filter). A 404 answer
      gives an empty list.
    type: str
attributes:
  platform:
    platforms: all
  check_mode:
    support: full
    details: Read-only, behaves the same in check mode.
  diff_mode:
    support: none
'''

EXAMPLES = r'''
- name: List all resource groups
  fjacquet.ppdm.resource_group_info:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
  register: result

- name: Get one by name
  fjacquet.ppdm.resource_group_info:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    name: web
'''

RETURN = r'''
resource_groups:
  description: Matching objects, an empty list when nothing matches.
  returned: always
  type: list
  elements: dict
  sample: [{"id": "1", "name": "web", "description": "Web tier"}]
'''

ARGUMENT_SPEC = dict(
    name=dict(type='str'),
    filter=dict(type='str'),
    id=dict(type='str'),
)
# fmt: on
# END GENERATED

from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import info_main


def main():
    info_main("resource-groups", "resource_groups", ARGUMENT_SPEC)


if __name__ == "__main__":
    main()
