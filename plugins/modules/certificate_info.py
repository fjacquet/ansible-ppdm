#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

# BEGIN GENERATED
# fmt: off
DOCUMENTATION = r'''
module: certificate_info
short_description: Get certificates from PowerProtect Data Manager
description:
- Read-only query of certificates. Never changes anything.
- Returns every matching object, all pages.
version_added: 1.0.0
author:
- Frederic Jacquet (@fjacquet)
extends_documentation_fragment:
- fjacquet.ppdm.ppdm
options:
  name:
    description:
    - Return only the object whose name equals this value exactly.
    type: str
  filter:
    description:
    - PPDM filter string, for example C(name lk "prod%").
    type: str
  id:
    description:
    - Return only the object with this ID. Mutually exclusive with I(name) and I(filter).
    type: str
'''

EXAMPLES = r'''
- name: List all certificates
  fjacquet.ppdm.certificate_info:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
  register: result

- name: Get one by name
  fjacquet.ppdm.certificate_info:
    hostname: ppdm.example.com
    username: admin
    password: "{{ ppdm_password }}"
    name: demo
'''

RETURN = r'''
certificates:
  description: Matching objects, an empty list when nothing matches.
  returned: always
  type: list
  elements: dict
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
    info_main("certificates", "certificates", ARGUMENT_SPEC, secret_fields=())


if __name__ == "__main__":
    main()
