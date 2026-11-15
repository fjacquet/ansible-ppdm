#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: host_info
short_description: Get hosts from PowerProtect Data Manager
description:
- Read-only query of hosts. Never changes anything.
- Returns every matching object, all pages.
- The 20.3.0 schema of hosts has no password or token field, only credential IDs (references), so nothing
  is masked.
version_added: 0.3.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
- action_common_attributes
notes:
- Unofficial collection, not affiliated with Dell. Written against the PowerProtect Data Manager 20.3.0
  REST API.
- The 20.3.0 schema of hosts holds only credential IDs, never a password or token.
options:
  type:
    description:
    - Return only hosts of this type (exact match on the type field, for example C(APP_HOST) or C(ESX_HOST),
      combined with I(name) or I(filter) when given).
    type: str
  name:
    description:
    - Return only the object whose name equals this value exactly (case-sensitive, checked again on the
      result, whatever the server filter returns). Mutually exclusive with I(filter) and I(id).
    type: str
  filter:
    description:
    - PPDM filter string, for example C(name lk "prod%"). It is passed to PPDM unchanged and its result
      is not re-checked. Mutually exclusive with I(name) and I(id).
    type: str
  id:
    description:
    - Return only the object with this ID. Mutually exclusive with I(name) and I(filter). A 404 or 204
      answer gives an empty list, a 404 also happens when this PPDM version does not support the endpoint.
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
- name: List all hosts
  fjacquet.ppdm.host_info:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
  register: result

- name: List application hosts
  fjacquet.ppdm.host_info:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    type: APP_HOST
'''

RETURN = r'''
hosts:
  description: Matching objects, an empty list when nothing matches.
  returned: always
  type: list
  elements: dict
  sample: [{"id": "h1", "name": "db01", "type": "APP_HOST"}]
'''

ARGUMENT_SPEC = dict(
    type=dict(type='str'),
    name=dict(type='str'),
    filter=dict(type='str'),
    id=dict(type='str'),
)
# fmt: on
# END GENERATED

from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import info_main


def main():
    info_main("hosts", "hosts", ARGUMENT_SPEC, extra_eq={"type": "type"})


if __name__ == "__main__":
    main()
